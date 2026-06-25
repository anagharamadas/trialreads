"""
One-time import: old SQLite library.db  →  Supabase Postgres `public.library`.

Reads every row from the legacy SQLite table and inserts it into Supabase,
tagging each row with YOUR Supabase auth user_id so it lands under your account
(and is protected by RLS).

Usage:
    cd backend
    python scripts/import_existing_library.py \
        --source /path/to/old/data/library.db \
        --user-id <YOUR_SUPABASE_USER_UUID>

DATABASE_URL is read from backend/.env (the same Supabase Postgres connection
string the API will use). Connecting as the postgres user bypasses RLS, which is
exactly what we want for a trusted server-side seed.

Safety: if the target user already has rows, the script refuses to run unless you
pass --force (which first deletes that user's existing rows, then re-imports).
"""

import argparse
import os
import sqlite3
import sys
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Load backend/.env regardless of where the script is invoked from.
ENV_PATH = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(ENV_PATH)

ALLOWED_STATUS = {"Yet to Buy", "Reading", "Ready to Start", "Finished"}


def read_sqlite_rows(source: Path):
    """Return list of (book, author, status, year) from the legacy SQLite db."""
    if not source.exists():
        sys.exit(f"❌ Source SQLite file not found: {source}")
    conn = sqlite3.connect(str(source))
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT Book, Author, Status, Year FROM library").fetchall()
    conn.close()

    cleaned = []
    for r in rows:
        book = (r["Book"] or "").strip()
        if not book:
            continue  # skip blank titles
        author = (r["Author"] or "").strip() or None
        status = (r["Status"] or "").strip()
        if status not in ALLOWED_STATUS:
            sys.exit(f"❌ Row {book!r} has invalid Status {status!r}; "
                     f"allowed: {sorted(ALLOWED_STATUS)}")
        year = r["Year"]
        year = int(year) if year is not None else None  # SQLite stores 2015.0
        cleaned.append({"book": book, "author": author, "status": status, "year": year})
    return cleaned


def main():
    ap = argparse.ArgumentParser(description="Import legacy SQLite library into Supabase.")
    ap.add_argument("--source", required=True, help="Path to the old data/library.db")
    ap.add_argument("--user-id", required=True, help="Your Supabase auth user UUID")
    ap.add_argument("--force", action="store_true",
                    help="If the user already has rows, delete them first, then re-import")
    args = ap.parse_args()

    db_url = os.getenv("DATABASE_URL")
    if not db_url or "[YOUR-PASSWORD]" in db_url or "YOUR-PROJECT-ref" in db_url:
        sys.exit("❌ DATABASE_URL is not set/filled in backend/.env "
                 "(Supabase → Settings → Database → Connection string → URI).")

    rows = read_sqlite_rows(Path(args.source).expanduser())
    print(f"Read {len(rows)} books from {args.source}")

    engine = create_engine(db_url)
    with engine.begin() as conn:
        existing = conn.execute(
            text("SELECT count(*) FROM public.library WHERE user_id = :uid"),
            {"uid": args.user_id},
        ).scalar_one()

        if existing and not args.force:
            sys.exit(f"❌ User already has {existing} rows. Re-run with --force to "
                     f"replace them, or pick a clean user.")
        if existing and args.force:
            conn.execute(text("DELETE FROM public.library WHERE user_id = :uid"),
                         {"uid": args.user_id})
            print(f"--force: deleted {existing} existing rows for this user")

        conn.execute(
            text("""
                INSERT INTO public.library (user_id, book, author, status, year)
                VALUES (:uid, :book, :author, :status, :year)
            """),
            [{"uid": args.user_id, **r} for r in rows],
        )

        total = conn.execute(
            text("SELECT count(*) FROM public.library WHERE user_id = :uid"),
            {"uid": args.user_id},
        ).scalar_one()

    print(f"✅ Imported {len(rows)} books. User now has {total} rows in Supabase.")


if __name__ == "__main__":
    main()
