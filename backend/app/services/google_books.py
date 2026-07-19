"""Google Books lookups — the curation agent's only window to the outside world.

`search` powers the agent's research tool; `validate` is used server-side to
ground every proposed book (no book survives unless Google Books returns it,
which also supplies the cover image).
"""

import time

import httpx

_GB = "https://www.googleapis.com/books/v1/volumes"
_RETRIES = 2  # Google Books 503s stochastically; one retry halves the drop rate


def _clean_cover(url: str) -> str:
    return url.replace("http://", "https://").replace("&edge=curl", "") if url else ""


def search(query: str, max_results: int = 5, api_key: str = "") -> list[dict]:
    """Return up to `max_results` books for a free-form query."""
    params: dict = {"q": query, "maxResults": max_results, "printType": "books"}
    if api_key:
        params["key"] = api_key
    items = []
    for attempt in range(_RETRIES):
        try:
            r = httpx.get(_GB, params=params, timeout=15)
            if r.status_code == 200:
                items = r.json().get("items", [])
                break
        except Exception:
            pass
        if attempt + 1 < _RETRIES:
            time.sleep(0.4)

    out = []
    for it in items:
        vi = it.get("volumeInfo", {})
        links = vi.get("imageLinks", {})
        out.append(
            {
                "title": vi.get("title", ""),
                "authors": vi.get("authors", []),
                "description": (vi.get("description", "") or "")[:400],
                "published_year": (vi.get("publishedDate", "") or "")[:4],
                "cover_url": _clean_cover(
                    links.get("thumbnail") or links.get("smallThumbnail") or ""
                ),
                # Aggregate Google Books rating (the API exposes no review text;
                # written reviews live on the info_link page). Often absent.
                "average_rating": vi.get("averageRating"),
                "ratings_count": vi.get("ratingsCount"),
                "info_link": vi.get("infoLink") or "",
            }
        )
    return out


def validate(title: str, author: str = "", api_key: str = "") -> dict | None:
    """Confirm a specific book exists; returns the canonical record or None.

    Fetches the top 5 editions (one API call): canonical data comes from the
    best match, but ratings are borrowed from the first RATED edition when the
    best match has none — Google's ratings live on specific editions, and the
    top hit is often an unrated reprint of a well-rated book.
    """
    q = f"intitle:{title}"
    if author:
        q += f" inauthor:{author}"
    res = search(q, 5, api_key)
    if not res:
        return None
    best = res[0]
    if best.get("average_rating") is None:
        rated = next((r for r in res if r.get("average_rating") is not None), None)
        if rated:
            best = {
                **best,
                "average_rating": rated["average_rating"],
                "ratings_count": rated.get("ratings_count"),
            }
    return best
