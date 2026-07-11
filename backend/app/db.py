"""Database access for Supabase Postgres.

A single pooled SQLAlchemy engine used for CRUD. The backend has already
authenticated the JWT, so CRUD queries are explicitly scoped with
`WHERE user_id = :me` and `user_id` is taken from the token, never the body.

The text-to-SQL path does NOT use this engine: it builds a per-request,
RLS-scoped NullPool engine (SET ROLE authenticated + JWT claims stamped on
every connection) so Postgres Row Level Security physically restricts
LLM-generated SQL to the caller's rows — see services/library_query.py.
"""

from sqlalchemy import create_engine

from .config import get_settings

_settings = get_settings()

# Pooled engine for ordinary (fixed, code-scoped) queries.
engine = create_engine(
    _settings.database_url,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=5,
)
