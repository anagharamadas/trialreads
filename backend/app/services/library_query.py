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

from llama_index.core import SQLDatabase
from llama_index.core.query_engine import NLSQLTableQueryEngine
from llama_index.llms.openai import OpenAI
from sqlalchemy import create_engine, event
from sqlalchemy.pool import NullPool

from ..config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

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


def answer_query(user_query: str, user_id: str, api_key: str) -> dict:
    """Answer a natural-language question over ONLY this user's library."""
    # LlamaIndex resolves a default OpenAI embed model at engine init and reads
    # the key from the environment (not actually used for this text-to-SQL path,
    # but required to be present). Mirrors the original library_manager.py.
    os.environ["OPENAI_API_KEY"] = api_key

    eng = _scoped_engine(user_id)
    try:
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
        if sql:
            logger.info("Generated SQL (user %s): %s", user_id, sql)
        return {"answer": str(response), "sql": sql}
    finally:
        eng.dispose()
