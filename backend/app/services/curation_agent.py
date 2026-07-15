"""Shelf-curation agent (Phase 2, M5).

Two-stage design, chosen for reliability with gpt-4o-mini:

  1. A LangGraph ReAct agent (create_react_agent, same pattern as book_agent.py)
     with a single tool, search_google_books — its only research window. It asks
     clarifying questions, researches, and (when ready) presents a reading list.
  2. A structured-output extraction pass (with_structured_output) reads the
     agent's latest message and reliably pulls out an ordered list if one is
     present — far more dependable than asking gpt-4o-mini to emit a nested
     tool call itself.

Grounding is enforced by construction: every extracted book is re-validated
against Google Books (`_ground`); anything it can't confirm is dropped, and the
cover image comes from the validated record. The agent never writes to the DB —
writes happen only when the user accepts, via /shelves/{id}/books/bulk.
"""

import logging
import os

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from opentelemetry import trace
from pydantic import BaseModel, Field

from ..config import get_settings
from .. import llm_observability
from . import google_books, hardcover

logger = logging.getLogger(__name__)
settings = get_settings()
tracer = trace.get_tracer("trialreads.curate")

MAX_HISTORY = 20
RECURSION_LIMIT = 16
MAX_ITEMS = 10

RESEARCH_PROMPT = (
    "You are TrialReads' reading-list curator. You help a user build an ordered "
    "reading list (a 'shelf') that takes them from foundations to a specific goal.\n\n"
    "1. If the user's goal is vague, ask 2 to 4 focused clarifying questions "
    "BEFORE recommending anything — current knowledge level, time budget, "
    "theory-vs-practice preference, and any region-specific angle. Ask, then "
    "stop and wait for their answer.\n"
    "2. Once the goal is clear, use the search_google_books tool to find and "
    "VERIFY candidate books. You may ONLY recommend books that appear in the "
    "tool's results — never invent titles or authors from memory. Recommend "
    "published BOOKS only — no magazines, journals, periodicals, or courses.\n"
    "3. When ready, present a reading list of 5 to 10 books (NEVER more than 10, "
    "even if the user asks for more) as a numbered list in reading order "
    "(foundations first, building toward the goal). For each book give 'Title by "
    "Author' and a one-line reason. Start with a one-sentence overview of how the "
    "sequence builds toward the goal. If you genuinely cannot find enough good "
    "books on the topic, propose fewer (even 3 to 4) and say so honestly — never "
    "pad the list with invented or irrelevant titles."
)

_EXTRACT_PROMPT = (
    "You extract a structured reading list from an assistant's message.\n"
    "If the message presents a FINAL, ordered list of recommended books, set "
    "is_reading_list=true, copy each book's title, author, and its one-line "
    "reason IN THE ORDER GIVEN, provide a one-sentence overview, and a one- or "
    "two-sentence short_reply to show the user.\n"
    "If the message is only asking clarifying questions, or does not present a "
    "concrete list of books, set is_reading_list=false and leave the rest empty."
)


@tool
def search_google_books(query: str) -> str:
    """Search Google Books for REAL books to find and verify candidates.

    Use this before recommending anything. Returns up to 5 results with title,
    author, year and a short description. You may only recommend books that
    appear in results from this tool.
    """
    with tracer.start_as_current_span("curate.tool.search_google_books") as span:
        span.set_attribute("app.tool.query", query)
        res = google_books.search(query, 5, settings.google_books_api_key)
        span.set_attribute("app.tool.result_count", len(res))
    if not res:
        return "No results found for that query."
    lines = []
    for i, b in enumerate(res, 1):
        authors = ", ".join(b["authors"]) if b["authors"] else "Unknown"
        lines.append(
            f"{i}. {b['title']} — {authors} ({b['published_year'] or 'n.d.'}): "
            f"{b['description'][:160]}"
        )
    return "\n".join(lines)


class _ExtractedItem(BaseModel):
    title: str
    author: str = ""
    reason: str = ""


class _Extracted(BaseModel):
    is_reading_list: bool = Field(
        description="true only if the message presents a final ordered list of books"
    )
    short_reply: str = Field(default="", description="one or two sentences for the user")
    overview: str = Field(default="", description="one-sentence overview of the sequence")
    items: list[_ExtractedItem] = Field(default_factory=list)


@tracer.start_as_current_span("curate.ground")
def _ground(overview: str, items: list[_ExtractedItem]) -> dict | None:
    """Re-validate every proposed book against Google Books; drop the rest."""
    grounded = []
    for it in items[:MAX_ITEMS]:
        title = (it.title or "").strip()
        if not title:
            continue
        gb = google_books.validate(title, (it.author or "").strip(), settings.google_books_api_key)
        if gb is None:
            logger.info("curate: dropped unverifiable book %r", title)
            continue
        # Books have authors; periodicals/magazines usually don't — drop those.
        if not gb.get("authors"):
            logger.info("curate: dropped author-less result (likely not a book) %r", title)
            continue
        author_str = ", ".join(gb["authors"]) if gb.get("authors") else (it.author or "")
        # Ratings: Hardcover first (community coverage beats Google's sparse
        # ratings), Google Books as fallback from the validation response.
        hc = hardcover.get_rating(gb["title"] or title, author_str)
        grounded.append(
            {
                "title": gb["title"] or title,
                "author": author_str,
                "cover_url": gb.get("cover_url") or None,
                "reason": (it.reason or "").strip(),
                "reading_order": 0,
                "average_rating": (hc or {}).get("average_rating", gb.get("average_rating")),
                "ratings_count": (hc or {}).get("ratings_count", gb.get("ratings_count")),
                "info_link": gb.get("info_link") or None,
            }
        )
    if not grounded:
        return None
    for i, g in enumerate(grounded, 1):
        g["reading_order"] = i
    return {"overview": (overview or "").strip(), "items": grounded}


def run_curation(messages: list[dict], api_key: str, user_id: str = "") -> dict:
    """Run one agent turn over the (capped) history. Returns {reply, proposal}."""
    os.environ["OPENAI_API_KEY"] = api_key

    # Stage 1: research + conversation.
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.2, api_key=api_key)
    agent = create_react_agent(
        llm, tools=[search_google_books], prompt=RESEARCH_PROMPT
    )
    with tracer.start_as_current_span("curate.agent_turn") as span:
        span.set_attribute("app.feature", "curate")
        span.set_attribute("app.curate.history_len", len(messages))
        result = agent.invoke(
            {"messages": messages[-MAX_HISTORY:]},
            config={
                "recursion_limit": RECURSION_LIMIT,
                **llm_observability.langchain_config("curate", user_id),
            },
        )
        msgs = result["messages"]
        agent_reply = msgs[-1].content if msgs else ""

        tokens = sum(
            (getattr(m, "usage_metadata", None) or {}).get("total_tokens", 0)
            for m in msgs
        )
        span.set_attribute("app.curate.total_tokens", tokens)

    # Stage 2: structured extraction of a reading list, if present.
    extractor = ChatOpenAI(model="gpt-4o-mini", temperature=0, api_key=api_key)
    with tracer.start_as_current_span("curate.extract"):
        ex: _Extracted = extractor.with_structured_output(_Extracted).invoke(
            [SystemMessage(content=_EXTRACT_PROMPT), HumanMessage(content=agent_reply)],
            config=llm_observability.langchain_config("curate", user_id) or None,
        )

    proposal = None
    reply = agent_reply
    if ex.is_reading_list and ex.items:
        proposal = _ground(ex.overview, ex.items)
        if proposal:
            reply = ex.short_reply or "Here's a reading list to get you there."

    logger.info("curate: tokens=%s, proposed=%s", tokens, proposal is not None)
    return {"reply": reply, "proposal": proposal}
