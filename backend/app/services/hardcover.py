"""Hardcover.app ratings — community book ratings via their GraphQL API.

Replaces Google Books as the ratings source (its ratings are sparse for niche
titles; Hardcover's community coverage is far better). Google Books remains
the grounding/covers source; Hardcover contributes ONLY the rating numbers.

Auth: HARDCOVER_API_KEY (account token from hardcover.app → Settings → API).
No key → get_rating() returns None and features behave as before.
Rate limit: 60 requests/minute — callers doing bulk lookups must pace.
"""

import logging

import httpx

from ..config import get_settings

logger = logging.getLogger(__name__)

_URL = "https://api.hardcover.app/v1/graphql"

# Hardcover forbids _ilike filters on the books table ("ilike and related
# operations are not permitted"), so lookups go through their Typesense-backed
# `search` endpoint — same fuzzy, popularity-ranked search as the website.
# Each result document carries rating / ratings_count / author_names directly.
_QUERY = """
query BookRating($q: String!) {
  search(query: $q, query_type: "Book", per_page: 5, page: 1) {
    results
  }
}
"""


def enabled() -> bool:
    return bool(get_settings().hardcover_api_key)


def _hits(results) -> list[dict]:
    """Typesense result docs, defensively unwrapped ({found, hits:[{document}]})."""
    if not isinstance(results, dict):
        return []
    return [
        h["document"]
        for h in results.get("hits") or []
        if isinstance(h, dict) and isinstance(h.get("document"), dict)
    ]


def get_rating(title: str, author: str = "") -> dict | None:
    """Return {average_rating, ratings_count} from Hardcover, or None.

    Searches title+author fuzzily; prefers a hit whose author_names match,
    else takes the top-ranked hit. Never raises — ratings are decoration,
    not worth failing a request over.
    """
    key = get_settings().hardcover_api_key
    if not key or not title:
        return None
    token = key if key.lower().startswith("bearer ") else f"Bearer {key}"
    q = f"{title} {author}".strip()
    try:
        r = httpx.post(
            _URL,
            json={"query": _QUERY, "variables": {"q": q}},
            headers={"authorization": token},
            timeout=10,
        )
        if r.status_code != 200:
            logger.warning("hardcover: HTTP %s for %r", r.status_code, title)
            return None
        payload = r.json()
        if payload.get("errors"):
            logger.warning("hardcover: GraphQL error for %r: %s", title, payload["errors"][:1])
            return None
        docs = _hits(((payload.get("data") or {}).get("search") or {}).get("results"))
    except Exception:
        logger.warning("hardcover: lookup failed for %r", title, exc_info=True)
        return None

    if not docs:
        return None
    pick = None
    if author:
        # first author surname-ish token, lowercased, matched loosely
        needle = author.split(",")[0].strip().lower()
        pick = next(
            (
                d
                for d in docs
                if any(needle in (a or "").lower() for a in d.get("author_names") or [])
            ),
            None,
        )
    pick = pick or docs[0]
    rating = pick.get("rating")
    if not rating:  # None or 0 = unrated
        return None
    return {
        # DB column is numeric(2,1); Hardcover returns e.g. 4.2317
        "average_rating": round(float(rating), 1),
        "ratings_count": pick.get("ratings_count") or 0,
    }
