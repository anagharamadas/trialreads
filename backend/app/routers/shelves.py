"""Shelves CRUD endpoints (Phase 2).

Mirrors the library router: every route requires a valid JWT, `user_id` comes
from the token (never the body), and all queries are explicitly scoped by it.
For any shelf-book operation the shelf's ownership is verified first — a shelf
that isn't the caller's returns 404 (we don't reveal other users' shelves).
RLS is the backstop, but the pooled engine connects as the service role (which
bypasses RLS), so this code-level scoping is the real guard.

UUID path params are parsed to real uuid objects (bad ones -> 404, not 500) and
bound as-is; psycopg2 adapts them to the uuid column type, so no SQL casts.
"""

import uuid as _uuid
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.engine import Connection

from ..auth import get_current_user_id
from ..config import get_settings
from ..db import engine
from ..rate_limit import enforce_daily_limit
from ..schemas import (
    CurateRequest,
    CurateResponse,
    Shelf,
    ShelfBook,
    ShelfBookBulkCreate,
    ShelfBookCreate,
    ShelfBookUpdate,
    ShelfCreate,
    ShelfUpdate,
)
from ..services import curation_agent

router = APIRouter(prefix="/shelves", tags=["shelves"])
settings = get_settings()

_SHELF_COLS = "id::text AS id, name, description, created_at::text AS created_at"
_BOOK_COLS = (
    "id::text AS id, shelf_id::text AS shelf_id, library_book_id, title, author, "
    "cover_url, reason, reading_order, added_by"
)


def _valid_uuid(val: str, what: str) -> UUID:
    """Parse a path UUID, or 404 (not 500) if malformed."""
    try:
        return _uuid.UUID(val)
    except (ValueError, TypeError, AttributeError):
        raise HTTPException(status_code=404, detail=f"{what} not found")


def _assert_shelf_owner(conn: Connection, shelf_id: UUID, user_id: str) -> None:
    owned = conn.execute(
        text("SELECT 1 FROM public.shelves WHERE id = :s AND user_id = :me"),
        {"s": shelf_id, "me": user_id},
    ).scalar()
    if not owned:
        raise HTTPException(status_code=404, detail="Shelf not found")


# ── Shelves ───────────────────────────────────────────────────────────────
@router.get("", response_model=list[Shelf])
def list_shelves(user_id: str = Depends(get_current_user_id)):
    """List the user's shelves with a book count (single grouped query, no N+1)."""
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT s.id::text AS id, s.name, s.description, "
                "s.created_at::text AS created_at, count(sb.id) AS book_count "
                "FROM public.shelves s "
                "LEFT JOIN public.shelf_books sb ON sb.shelf_id = s.id "
                "WHERE s.user_id = :me "
                "GROUP BY s.id "
                "ORDER BY s.created_at DESC, s.id DESC"
            ),
            {"me": user_id},
        ).mappings().all()
    return [Shelf(**r) for r in rows]


@router.post("", response_model=Shelf, status_code=status.HTTP_201_CREATED)
def create_shelf(payload: ShelfCreate, user_id: str = Depends(get_current_user_id)):
    with engine.begin() as conn:
        row = conn.execute(
            text(
                "INSERT INTO public.shelves (user_id, name, description) "
                "VALUES (:me, :name, :description) "
                f"RETURNING {_SHELF_COLS}"
            ),
            {"me": user_id, **payload.model_dump()},
        ).mappings().one()
    return Shelf(**row, book_count=0)


@router.put("/{shelf_id}", response_model=Shelf)
def update_shelf(
    shelf_id: str, payload: ShelfUpdate, user_id: str = Depends(get_current_user_id)
):
    sid = _valid_uuid(shelf_id, "Shelf")
    fields = payload.model_dump(exclude_unset=True)
    if not fields:
        raise HTTPException(status_code=400, detail="No fields to update")
    set_clause = ", ".join(f"{k} = :{k}" for k in fields)
    with engine.begin() as conn:
        row = conn.execute(
            text(
                f"UPDATE public.shelves SET {set_clause} "
                "WHERE id = :sid AND user_id = :me "
                f"RETURNING {_SHELF_COLS}"
            ),
            {**fields, "sid": sid, "me": user_id},
        ).mappings().one_or_none()
        if row is None:
            raise HTTPException(status_code=404, detail="Shelf not found")
        n = conn.execute(
            text("SELECT count(*) FROM public.shelf_books WHERE shelf_id = :s"),
            {"s": sid},
        ).scalar()
    return Shelf(**row, book_count=n)


@router.delete("/{shelf_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_shelf(shelf_id: str, user_id: str = Depends(get_current_user_id)):
    sid = _valid_uuid(shelf_id, "Shelf")
    with engine.begin() as conn:
        result = conn.execute(
            text("DELETE FROM public.shelves WHERE id = :s AND user_id = :me"),
            {"s": sid, "me": user_id},
        )
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Shelf not found")
    return None


# ── Shelf books ───────────────────────────────────────────────────────────
@router.get("/{shelf_id}/books", response_model=list[ShelfBook])
def list_shelf_books(shelf_id: str, user_id: str = Depends(get_current_user_id)):
    sid = _valid_uuid(shelf_id, "Shelf")
    with engine.connect() as conn:
        _assert_shelf_owner(conn, sid, user_id)
        rows = conn.execute(
            text(
                f"SELECT {_BOOK_COLS} FROM public.shelf_books "
                "WHERE shelf_id = :s AND user_id = :me "
                "ORDER BY reading_order ASC NULLS LAST, created_at ASC"
            ),
            {"s": sid, "me": user_id},
        ).mappings().all()
    return [ShelfBook(**r) for r in rows]


@router.post(
    "/{shelf_id}/books", response_model=ShelfBook, status_code=status.HTTP_201_CREATED
)
def add_shelf_book(
    shelf_id: str, payload: ShelfBookCreate, user_id: str = Depends(get_current_user_id)
):
    sid = _valid_uuid(shelf_id, "Shelf")
    with engine.begin() as conn:
        _assert_shelf_owner(conn, sid, user_id)
        row = conn.execute(
            text(
                "INSERT INTO public.shelf_books "
                "(shelf_id, user_id, library_book_id, title, author, cover_url, "
                " reason, reading_order, added_by) "
                "VALUES (:s, :me, :library_book_id, :title, :author, :cover_url, "
                " :reason, :reading_order, :added_by) "
                "ON CONFLICT (shelf_id, title, author) DO NOTHING "
                f"RETURNING {_BOOK_COLS}"
            ),
            {"s": sid, "me": user_id, **payload.model_dump()},
        ).mappings().one_or_none()
    if row is None:
        raise HTTPException(
            status_code=409, detail="That book is already on this shelf"
        )
    return ShelfBook(**row)


@router.post(
    "/{shelf_id}/books/bulk",
    response_model=list[ShelfBook],
    status_code=status.HTTP_201_CREATED,
)
def bulk_add_shelf_books(
    shelf_id: str,
    payload: ShelfBookBulkCreate,
    user_id: str = Depends(get_current_user_id),
):
    """Insert many books in one transaction; duplicates are skipped gracefully."""
    sid = _valid_uuid(shelf_id, "Shelf")
    inserted: list[ShelfBook] = []
    with engine.begin() as conn:
        _assert_shelf_owner(conn, sid, user_id)
        for item in payload.items:
            row = conn.execute(
                text(
                    "INSERT INTO public.shelf_books "
                    "(shelf_id, user_id, library_book_id, title, author, cover_url, "
                    " reason, reading_order, added_by) "
                    "VALUES (:s, :me, :library_book_id, :title, :author, "
                    " :cover_url, :reason, :reading_order, :added_by) "
                    "ON CONFLICT (shelf_id, title, author) DO NOTHING "
                    f"RETURNING {_BOOK_COLS}"
                ),
                {
                    "s": sid,
                    "me": user_id,
                    "added_by": payload.added_by,
                    **item.model_dump(),
                },
            ).mappings().one_or_none()
            if row is not None:
                inserted.append(ShelfBook(**row))
    return inserted


@router.put("/{shelf_id}/books/{book_id}", response_model=ShelfBook)
def update_shelf_book(
    shelf_id: str,
    book_id: str,
    payload: ShelfBookUpdate,
    user_id: str = Depends(get_current_user_id),
):
    sid = _valid_uuid(shelf_id, "Shelf")
    bid = _valid_uuid(book_id, "Book")
    fields = payload.model_dump(exclude_unset=True)
    if not fields:
        raise HTTPException(status_code=400, detail="No fields to update")
    set_clause = ", ".join(f"{k} = :{k}" for k in fields)
    with engine.begin() as conn:
        _assert_shelf_owner(conn, sid, user_id)
        row = conn.execute(
            text(
                f"UPDATE public.shelf_books SET {set_clause} "
                "WHERE id = :bid AND shelf_id = :s AND user_id = :me "
                f"RETURNING {_BOOK_COLS}"
            ),
            {**fields, "bid": bid, "s": sid, "me": user_id},
        ).mappings().one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Book not found on this shelf")
    return ShelfBook(**row)


@router.post("/{shelf_id}/curate", response_model=CurateResponse)
def curate_shelf(
    shelf_id: str,
    payload: CurateRequest,
    user_id: str = Depends(get_current_user_id),
):
    """Conversational curation agent. Verifies shelf ownership BEFORE consuming
    the daily AI quota or running any paid inference, then returns a reply and
    (when ready) a structured, Google-Books-grounded reading-list proposal.
    Never writes to the DB — the user accepts via .../books/bulk.
    """
    sid = _valid_uuid(shelf_id, "Shelf")
    with engine.connect() as conn:
        _assert_shelf_owner(conn, sid, user_id)
    enforce_daily_limit(user_id)  # after ownership: probes don't burn quota
    result = curation_agent.run_curation(
        [m.model_dump() for m in payload.messages], settings.openai_api_key
    )
    return CurateResponse(reply=result["reply"], proposal=result["proposal"])


@router.delete(
    "/{shelf_id}/books/{book_id}", status_code=status.HTTP_204_NO_CONTENT
)
def delete_shelf_book(
    shelf_id: str, book_id: str, user_id: str = Depends(get_current_user_id)
):
    sid = _valid_uuid(shelf_id, "Shelf")
    bid = _valid_uuid(book_id, "Book")
    with engine.begin() as conn:
        _assert_shelf_owner(conn, sid, user_id)
        result = conn.execute(
            text(
                "DELETE FROM public.shelf_books "
                "WHERE id = :bid AND shelf_id = :s AND user_id = :me"
            ),
            {"bid": bid, "s": sid, "me": user_id},
        )
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Book not found on this shelf")
    return None
