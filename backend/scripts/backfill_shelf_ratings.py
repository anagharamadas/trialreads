"""Backfill ratings for shelf books (Hardcover primary, Google Books fallback).

    cd backend
    python -m scripts.backfill_shelf_ratings --dry-run   # look, don't touch
    python -m scripts.backfill_shelf_ratings             # rows without a rating
    python -m scripts.backfill_shelf_ratings --all       # re-lookup every row

Behaviour:
- Rating source #1: Hardcover GraphQL (services.hardcover; needs
  HARDCOVER_API_KEY, 60 req/min — hence --sleep, default 1.0s).
- Fallback: Google Books, which also supplies info_link when missing. Talks to
  GB directly (not via services.google_books) so it can SEE status codes: 429/
  403 aborts the run cleanly (daily quota), 5xx skips the row for the next run.
- Default target: rows WHERE average_rating IS NULL. --all re-rates everything
  (use after switching rating sources).
- Uses the privileged DATABASE_URL engine (single-owner maintenance script,
  same pattern as scripts/import_existing_library.py); RLS does not apply.
"""

import argparse
import sys
import time

import httpx
from sqlalchemy import create_engine, text

from app.config import get_settings
from app.services import hardcover

GB = "https://www.googleapis.com/books/v1/volumes"


class QuotaExhausted(Exception):
    pass


class TransientError(Exception):
    pass


def lookup(title: str, author: str, api_key: str) -> dict | None:
    """Best Google Books match for title/author, or None.

    Raises QuotaExhausted on 429/403 (Google reports daily-quota exhaustion as
    either) and TransientError on 5xx/network problems (skip the row, keep
    going). Never lets httpx raise raw — its messages embed the full request
    URL including the API key.
    """
    q = f"intitle:{title}"
    if author:
        q += f" inauthor:{author}"
    params: dict = {"q": q, "maxResults": 5, "printType": "books"}
    if api_key:
        params["key"] = api_key
    try:
        r = httpx.get(GB, params=params, timeout=15)
    except httpx.HTTPError as exc:
        raise TransientError(exc.__class__.__name__)
    if r.status_code in (429, 403):
        raise QuotaExhausted(f"HTTP {r.status_code}")
    if r.status_code != 200:
        raise TransientError(f"HTTP {r.status_code}")
    items = r.json().get("items", [])
    if not items:
        return None
    # Same edition-merge as services.google_books.validate: link/identity from
    # the best match, rating borrowed from the first RATED edition.
    infos = [it.get("volumeInfo", {}) for it in items]
    best = infos[0]
    rated = next((vi for vi in infos if vi.get("averageRating") is not None), None)
    return {
        "average_rating": (rated or best).get("averageRating"),
        "ratings_count": (rated or best).get("ratingsCount"),
        "info_link": best.get("infoLink"),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true", help="report, write nothing")
    ap.add_argument("--all", action="store_true", help="re-lookup every shelf book")
    ap.add_argument("--sleep", type=float, default=1.0, help="seconds between API calls")
    args = ap.parse_args()

    settings = get_settings()
    engine = create_engine(settings.database_url)
    if not hardcover.enabled():
        print("NOTE: HARDCOVER_API_KEY not set — falling back to Google Books only.")

    where = "" if args.all else "WHERE average_rating IS NULL"
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT id, title, author, info_link "
                f"FROM public.shelf_books {where} ORDER BY created_at"
            )
        ).mappings().all()

    print(f"{len(rows)} shelf book(s) to look up{' (dry run)' if args.dry_run else ''}")
    updated = no_data = errors = 0
    try:
        for row in rows:
            hc = hardcover.get_rating(row["title"], row["author"] or "")
            rating = (hc or {}).get("average_rating")
            count = (hc or {}).get("ratings_count")
            link = row["info_link"]
            source = "hardcover"

            # Google Books: rating fallback, and info_link when missing.
            if hc is None or link is None:
                try:
                    gb = lookup(row["title"], row["author"] or "", settings.google_books_api_key)
                except QuotaExhausted as exc:
                    if hc is None:
                        print(
                            f"\nABORT: Google Books quota exhausted ({exc}) and no "
                            f"Hardcover result.\nProgress so far is saved. Re-run later.",
                            file=sys.stderr,
                        )
                        return 1
                    gb = None
                except TransientError as exc:
                    if hc is None:
                        errors += 1
                        print(f"  [skip: {exc}] {row['title']}")
                        time.sleep(args.sleep)
                        continue
                    gb = None
                if gb:
                    link = link or gb["info_link"]
                    if hc is None:
                        rating, count, source = gb["average_rating"], gb["ratings_count"], "google"

            if rating is None and link is None:
                no_data += 1
                print(f"  [no data] {row['title']}")
            else:
                print(
                    f"  [{'✓ ' + str(rating) + ' (' + source + ')' if rating is not None else 'no rating'}] "
                    f"{row['title']}"
                )
                if not args.dry_run:
                    with engine.begin() as conn:
                        conn.execute(
                            text(
                                "UPDATE public.shelf_books SET "
                                "average_rating = :ar, ratings_count = :rc, info_link = :il "
                                "WHERE id = :id"
                            ),
                            {"ar": rating, "rc": count, "il": link, "id": row["id"]},
                        )
                updated += 1
            time.sleep(args.sleep)
    finally:
        engine.dispose()

    print(
        f"\nDone: {updated} updated, {no_data} with no data from either source, "
        f"{errors} skipped on transient errors (re-run to pick those up)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
