"""Database access for Supabase Postgres.

Two access patterns:

1. `engine` — a normal pooled SQLAlchemy engine used for CRUD. The backend has
   already authenticated the JWT, so CRUD queries are explicitly scoped with
   `WHERE user_id = :me` and `user_id` is taken from the token, never the body.

2. `rls_connection(user_id)` — a fresh, RLS-scoped connection for the
   text-to-SQL path. It sets `ROLE authenticated` and the JWT claims so Postgres
   Row Level Security physically restricts every query to that user's rows.
   This is the DB-level backstop behind the LLM-generated SQL.
"""

from contextlib import contextmanager

from sqlalchemy import create_engine, text

from .config import get_settings

_settings = get_settings()

# Pooled engine for ordinary (fixed, code-scoped) queries.
engine = create_engine(
    _settings.database_url,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=5,
)


@contextmanager
def rls_connection(user_id: str):
    """Yield a connection that behaves as the given authenticated user.

    RLS is enforced: even an unscoped `SELECT * FROM library` returns only this
    user's rows. Uses a transaction so SET LOCAL / claims are scoped to it and
    cleaned up on close. `user_id` originates from a verified JWT, but we still
    pass it as a bound value to avoid any injection into the claims JSON.
    """
    conn = engine.connect()
    try:
        trans = conn.begin()
        # Switch to the RLS-governed role, then stamp the JWT claims that
        # auth.uid() reads. set_config(..., true) = transaction-local.
        conn.exec_driver_sql("SET ROLE authenticated")
        conn.execute(
            text(
                "SELECT set_config('request.jwt.claims', "
                "json_build_object('sub', :uid, 'role', 'authenticated')::text, true)"
            ),
            {"uid": user_id},
        )
        yield conn
        trans.commit()
    finally:
        conn.close()
