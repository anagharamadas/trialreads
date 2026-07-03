"""Google Books lookups — the curation agent's only window to the outside world.

`search` powers the agent's research tool; `validate` is used server-side to
ground every proposed book (no book survives unless Google Books returns it,
which also supplies the cover image).
"""

import httpx

_GB = "https://www.googleapis.com/books/v1/volumes"


def _clean_cover(url: str) -> str:
    return url.replace("http://", "https://").replace("&edge=curl", "") if url else ""


def search(query: str, max_results: int = 5, api_key: str = "") -> list[dict]:
    """Return up to `max_results` books for a free-form query."""
    params: dict = {"q": query, "maxResults": max_results, "printType": "books"}
    if api_key:
        params["key"] = api_key
    try:
        r = httpx.get(_GB, params=params, timeout=15)
        items = r.json().get("items", []) if r.status_code == 200 else []
    except Exception:
        return []

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
            }
        )
    return out


def validate(title: str, author: str = "", api_key: str = "") -> dict | None:
    """Confirm a specific book exists; returns the canonical record or None."""
    q = f"intitle:{title}"
    if author:
        q += f" inauthor:{author}"
    res = search(q, 1, api_key)
    return res[0] if res else None
