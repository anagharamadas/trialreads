"""Book cover lookup via Google Books (key stays server-side).

Given a title/author, returns a cover image URL (or null). Auth-guarded so the
Google Books quota isn't open to the public. Frontend calls this per book that
doesn't already have a stored cover_url.
"""

import httpx
from fastapi import APIRouter, Depends, Query

from ..auth import get_current_user_id
from ..config import get_settings
from ..services import hardcover

router = APIRouter(tags=["covers"])
settings = get_settings()

GOOGLE_BOOKS = "https://www.googleapis.com/books/v1/volumes"


@router.get("/covers")
def get_cover(
    title: str = Query(..., min_length=1),
    author: str = Query(""),
    user_id: str = Depends(get_current_user_id),
) -> dict:
    q = f"intitle:{title}"
    if author:
        q += f" inauthor:{author}"
    params: dict = {"q": q, "maxResults": 1, "printType": "books", "country": "US"}
    if settings.google_books_api_key:
        params["key"] = settings.google_books_api_key

    out: dict = {"cover_url": None, "average_rating": None, "ratings_count": None, "info_link": None}
    try:
        r = httpx.get(GOOGLE_BOOKS, params=params, timeout=10)
        items = r.json().get("items", [])
        if items:
            vi = items[0].get("volumeInfo", {})
            links = vi.get("imageLinks", {})
            url = links.get("thumbnail") or links.get("smallThumbnail")
            if url:
                # force https + drop the page-curl edge for a cleaner cover
                url = url.replace("http://", "https://").replace("&edge=curl", "")
            out.update(
                cover_url=url,
                average_rating=vi.get("averageRating"),
                ratings_count=vi.get("ratingsCount"),
                info_link=vi.get("infoLink"),
            )
    except Exception:
        pass
    # Hardcover is the preferred rating source; Google's (if any) is fallback.
    hc = hardcover.get_rating(title, author)
    if hc:
        out.update(hc)
    return out
