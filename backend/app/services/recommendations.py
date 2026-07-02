"""Book recommendations — ported from the original recommendation_system.py.

Asks the LLM for exactly 5 similar books in a fixed format, parses them into
{title, author, reason}, and attaches an Amazon search link to each. The parser
depends on the exact prompt format — keep the two in sync.

Simplified during the port: the original wrapped a single-node LangGraph
StateGraph that added nothing over a direct call, so this calls ChatOpenAI
directly (same model, temp 0.1, same prompt/format).
"""

import re
import urllib.parse

from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI


def generate_amazon_link(book_title: str, author_name: str) -> str:
    """Amazon search URL for 'title author' (no Amazon API call)."""
    query = urllib.parse.quote(f"{book_title} {author_name}".strip())
    return f"https://www.amazon.com/s?k={query}"


def _prompt(book_name: str, author_name: str) -> str:
    return f"""
    You are a helpful assistant who recommends books similar to one the user likes.

    Book: {book_name}
    Author: {author_name}

    Please provide exactly 5 book recommendations similar to this book.
    Format each recommendation EXACTLY as follows:

    1. [Book Title] by [Author Name]
       Reason: [Brief explanation of why it's similar]

    2. [Book Title] by [Author Name]
       Reason: [Brief explanation of why it's similar]

    Continue for all 5. Always include both the book title and the author name.
    """


def _clean(text: str) -> str:
    """Strip markdown/bracket decoration the model sometimes adds (**bold**, [Title])."""
    return text.strip().strip("*").strip("[]").strip()


def parse_recommendations(response_text: str) -> list[dict]:
    """Parse the fixed 'N. Title by Author / Reason: ...' format into dicts."""
    recommendations: list[dict] = []
    current: dict = {}

    for raw in response_text.split("\n"):
        line = raw.strip()
        if not line:
            continue

        if re.match(r"^\d+\.", line):
            if current:
                recommendations.append(current)
            current = {}
            content = re.sub(r"^\d+\.\s*", "", line)
            if " by " in content:
                title, author = content.split(" by ", 1)
                current["title"] = _clean(title)
                current["author"] = _clean(author)
            else:
                current["title"] = _clean(content)
                current["author"] = ""
        elif current:
            reason = re.sub(r"^Reason:\s*", "", line, flags=re.IGNORECASE)
            if "reason" not in current:
                current["reason"] = reason
            else:
                current["reason"] += " " + reason

    if current:
        recommendations.append(current)
    return recommendations


def recommend(book_name: str, author_name: str, api_key: str) -> dict:
    chat = ChatOpenAI(temperature=0.1, model="gpt-4o-mini", openai_api_key=api_key)
    response = chat.invoke([HumanMessage(content=_prompt(book_name, author_name))])
    text = response.content

    recs = parse_recommendations(text)
    for r in recs:
        r["amazon_link"] = generate_amazon_link(r.get("title", ""), r.get("author", ""))

    return {"original_response": text, "recommendations": recs}
