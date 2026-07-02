"""Book summariser — ported from the original book_summariser.py.

Produces a chapter-by-chapter summary of a book's first three chapters.
Cleaned up during the port: uses a single chain (the original computed and
discarded an 'internal reasoning' chain), actually incorporates the author, and
fixes the prompt typos. Behaviour is otherwise the same: gpt-4o-mini, temp 0.
"""

import re

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI


def get_summary(book_name: str, author_name: str, api_key: str) -> str:
    chat = ChatOpenAI(temperature=0, model="gpt-4o-mini", openai_api_key=api_key)

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", "You are a helpful literary assistant. Provide concise, accurate summaries."),
            (
                "human",
                'Summarise the book "{book_name}"{author_clause} chapter by chapter '
                "for the first 3 chapters, about 250 words per chapter.",
            ),
        ]
    )
    author_clause = f" by {author_name}" if author_name else ""

    response = (prompt | chat).invoke(
        {"book_name": book_name, "author_clause": author_clause}
    )

    # Strip any <think>...</think> blocks (no-op for gpt-4o-mini; kept for parity).
    cleaned = re.sub(r"<think>.*?</think>", "", response.content, flags=re.DOTALL)
    return cleaned.strip()
