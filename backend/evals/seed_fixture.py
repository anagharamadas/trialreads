"""Seed the NL->SQL eval fixture into EVAL_USER_ID's library.

The golden answers in datasets/nl_sql.jsonl are true ONLY for the exact rows in
fixtures/library_fixture.json, so the eval needs a user whose library is those
rows and nothing else. This script makes that so, idempotently.

Like scripts/import_existing_library.py, it connects with DATABASE_URL as the
postgres user (which bypasses RLS) — the trusted, server-side seed path. The FK
library.user_id -> auth.users(id) means EVAL_USER_ID must already be a real
Supabase auth user: sign up a throwaway account once, grab its UUID from the
Supabase dashboard (Authentication -> Users), and put it in backend/.env as
EVAL_USER_ID.

Usage (from backend/):
    python -m evals.seed_fixture                 # uses EVAL_USER_ID from .env
    python -m evals.seed_fixture --user-id <uuid>
    python -m evals.seed_fixture --force         # required if the user has rows

Safety: refuses to touch a user that already has library rows unless --force,
which first DELETES that user's rows, then inserts the fixture. Only ever run
this against a dedicated eval/test account.
"""

import argparse
import json
import sys

from sqlalchemy import create_engine, text

from evals import config


def load_fixture() -> list[dict]:
    path = config.FIXTURES_DIR / "library_fixture.json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)["books"]


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed the NL->SQL eval fixture.")
    parser.add_argument(
        "--user-id",
        default=config.eval_user_id(),
        help="Target auth.users UUID (defaults to EVAL_USER_ID from .env).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Delete the user's existing library rows before seeding.",
    )
    args = parser.parse_args()

    user_id = (args.user_id or "").strip()
    if not user_id:
        print(
            "ERROR: no user id. Set EVAL_USER_ID in backend/.env or pass --user-id.",
            file=sys.stderr,
        )
        return 2
    if not config.database_url():
        print("ERROR: DATABASE_URL is not configured in backend/.env.", file=sys.stderr)
        return 2

    books = load_fixture()
    engine = create_engine(config.database_url())

    with engine.begin() as conn:
        existing = conn.execute(
            text("SELECT count(*) FROM public.library WHERE user_id = :uid"),
            {"uid": user_id},
        ).scalar_one()

        if existing and not args.force:
            print(
                f"REFUSING: user {user_id} already has {existing} library row(s).\n"
                "Re-run with --force to delete them and re-seed the fixture.",
                file=sys.stderr,
            )
            return 1

        if existing:
            conn.execute(
                text("DELETE FROM public.library WHERE user_id = :uid"),
                {"uid": user_id},
            )
            print(f"Deleted {existing} existing row(s) for {user_id}.")

        conn.execute(
            text(
                "INSERT INTO public.library (user_id, book, author, status, year) "
                "VALUES (:user_id, :book, :author, :status, :year)"
            ),
            [{"user_id": user_id, **b} for b in books],
        )

    print(f"Seeded {len(books)} fixture book(s) for {user_id}.")
    print("Fixture is ready — run:  python -m evals.run_eval")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
