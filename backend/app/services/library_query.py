"""Per-user text-to-SQL over the personal library (the highest-risk feature).

Isolation model (defense in depth):
  1. The LLM is pointed ONLY at the `my_library` view, which self-filters to
     auth.uid() and does not even expose user_id.
  2. Queries run on a NON-POOLED engine whose every physical connection is
     stamped, via a 'connect' event, with `SET ROLE authenticated` and the
     caller's JWT claims. So Postgres RLS physically restricts every statement
     to this user's rows — even a raw `SELECT * FROM library` returns only theirs.
  3. NullPool + per-request engine.dispose() means no connection (and no role/
     claims state) is ever reused across users.

For another user's data to leak, the view filter, RLS on the base table, AND the
table scoping would all have to fail at once.
"""

import json
import logging
import os

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from llama_index.core import SQLDatabase
from llama_index.core.query_engine import NLSQLTableQueryEngine
from llama_index.llms.openai import OpenAI
from opentelemetry import trace
from sqlalchemy import create_engine, event
from sqlalchemy.pool import NullPool

from .. import llm_observability
from ..config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()
tracer = trace.get_tracer("trialreads.nl_sql")

# Chat memory (see routers/library.py): NLSQLTableQueryEngine answers ONE
# self-contained question, so follow-ups are handled by condensing the history
# + latest question into a standalone question first (the classic
# condense-question pattern). Only the last N turns matter.
MAX_HISTORY = 10

_CONDENSE_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You rewrite the LATEST user question from a conversation about a "
            "personal book library into ONE fully self-contained question, "
            "resolving pronouns and references to earlier turns (e.g. 'those "
            "books', 'that author', 'and in 2024?'). Preserve the user's "
            "intent exactly; do not answer the question. If it is already "
            "self-contained, return it unchanged. Return ONLY the rewritten "
            "question.",
        ),
        ("human", "CONVERSATION:\n{transcript}\n\nLATEST QUESTION:\n{question}"),
    ]
)


def _condense(history: list[dict], question: str, api_key: str, user_id: str) -> str:
    """Rewrite a follow-up into a standalone question using the chat history."""
    transcript = "\n".join(
        f"{m.get('role', 'user')}: {m.get('content', '')}"
        for m in history[-MAX_HISTORY:]
        if m.get("content")
    )
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0, api_key=api_key)
    out = (_CONDENSE_PROMPT | llm).invoke(
        {"transcript": transcript, "question": question},
        config=llm_observability.langchain_config("nl-sql", user_id) or None,
    )
    rewritten = (out.content or "").strip()
    return rewritten or question

VIEW = "my_library"

# Context handed to the text-to-SQL prompt. The view hides user_id entirely.
TABLE_CONTEXT = (
    "This view lists the user's personal book collection and reading history. "
    "Columns: "
    "book (the book title); "
    "author (the author's name, may be NULL); "
    "status (the reading state, exactly one of: 'Yet to Buy', 'Reading', "
    "'Ready to Start', 'Finished'); "
    "year (the integer year the user FINISHED the book; NULL unless "
    "status = 'Finished'). "
    "To count books read or finished in a given year, filter "
    "status = 'Finished' AND year = <year>."
)


def _scoped_engine(user_id: str):
    """A non-pooled engine whose connections run as the given authenticated user."""
    eng = create_engine(settings.database_url, poolclass=NullPool)
    claims = json.dumps({"sub": user_id, "role": "authenticated"})

    @event.listens_for(eng, "connect")
    def _apply_rls(dbapi_conn, _record):  # noqa: ANN001
        cur = dbapi_conn.cursor()
        cur.execute("SET ROLE authenticated")
        # session-level (false) so it holds for the whole connection lifetime
        cur.execute("SELECT set_config('request.jwt.claims', %s, false)", (claims,))
        cur.close()

    return eng


def answer_query(
    user_query: str, user_id: str, api_key: str, history: list[dict] | None = None
) -> dict:
    """Answer a natural-language question over ONLY this user's library.

    `history` (optional, oldest-first [{role, content}]) enables follow-up
    questions: the latest question is condensed into a standalone one first.
    """
    # LlamaIndex resolves a default OpenAI embed model at engine init and reads
    # the key from the environment (not actually used for this text-to-SQL path,
    # but required to be present). Mirrors the original library_manager.py.
    os.environ["OPENAI_API_KEY"] = api_key

    eng = _scoped_engine(user_id)
    # Manual span: auto-instrumentation sees "an OpenAI call" and "a DB query"
    # but can't know they form one unit of work (generate SQL → execute it).
    # Exceptions are recorded and flip the span to error status automatically.
    with tracer.start_as_current_span("nl_sql.generate_and_execute") as span:
        span.set_attribute("app.feature", "nl-sql")
        span.set_attribute("app.nl_sql.history_len", len(history or []))
        try:
            if history:
                with tracer.start_as_current_span("nl_sql.condense_question"):
                    user_query = _condense(history, user_query, api_key, user_id)
                span.set_attribute("app.nl_sql.condensed_query", user_query)
            sql_database = SQLDatabase(eng, include_tables=[VIEW], view_support=True)
            llm = OpenAI(model="gpt-4o-mini", temperature=0, api_key=api_key)
            query_engine = NLSQLTableQueryEngine(
                sql_database=sql_database,
                tables=[VIEW],
                llm=llm,
                context_query_kwargs={VIEW: TABLE_CONTEXT},
            )
            response = query_engine.query(user_query)
            sql = response.metadata.get("sql_query") if response.metadata else None
            span.set_attribute("app.nl_sql.sql_generated", bool(sql))
            if sql:
                span.set_attribute("app.nl_sql.sql", sql)
                logger.info("Generated SQL (user %s): %s", user_id, sql)
            return {"answer": str(response), "sql": sql}
        finally:
            eng.dispose()
