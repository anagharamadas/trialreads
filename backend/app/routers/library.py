"""Library CRUD endpoints.

All routes require a valid JWT. The user_id comes from the verified token
(never from the request body), and every query is explicitly scoped
`WHERE user_id = :me`, so a user can only ever see or touch their own rows.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text

from ..auth import get_current_user_id
from ..config import get_settings
from ..db import engine
from ..rate_limit import rate_limited_user
from ..schemas import Book, BookCreate, BookUpdate, LibraryQueryRequest, LibraryQueryResponse
from ..services import library_query

router = APIRouter(prefix="/library", tags=["library"])
settings = get_settings()


@router.get("", response_model=list[Book])
def list_books(user_id: str = Depends(get_current_user_id)):
    """List the current user's books (newest first)."""
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT id, book, author, status, year, cover_url "
                "FROM public.library WHERE user_id = :me "
                "ORDER BY created_at DESC, id DESC"
            ),
            {"me": user_id},
        ).mappings().all()
    return [Book(**r) for r in rows]


@router.post("/query", response_model=LibraryQueryResponse)
def query_library(
    payload: LibraryQueryRequest, user_id: str = Depends(rate_limited_user)
):
    """Answer a natural-language question over ONLY the current user's library.

    Text-to-SQL is scoped to this user via the my_library view + RLS-scoped
    connection (see services/library_query.py). No other user's data is reachable.
    """
    result = library_query.answer_query(
        payload.query,
        user_id,
        settings.openai_api_key,
        history=[m.model_dump() for m in payload.history],
    )
    return LibraryQueryResponse(answer=result["answer"], sql=result["sql"])


@router.post("", response_model=Book, status_code=status.HTTP_201_CREATED)
def add_book(payload: BookCreate, user_id: str = Depends(get_current_user_id)):
    """Add a book for the current user."""
    with engine.begin() as conn:
        row = conn.execute(
            text(
                "INSERT INTO public.library (user_id, book, author, status, year) "
                "VALUES (:me, :book, :author, :status, :year) "
                "RETURNING id, book, author, status, year, cover_url"
            ),
            {"me": user_id, **payload.model_dump()},
        ).mappings().one()
    return Book(**row)


@router.put("/{book_id}", response_model=Book)
def update_book(
    book_id: int,
    payload: BookUpdate,
    user_id: str = Depends(get_current_user_id),
):
    """Update a book — only if it belongs to the current user."""
    fields = payload.model_dump(exclude_unset=True)
    if not fields:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="No fields to update"
        )

    set_clause = ", ".join(f"{k} = :{k}" for k in fields)
    with engine.begin() as conn:
        row = conn.execute(
            text(
                f"UPDATE public.library SET {set_clause} "
                "WHERE id = :book_id AND user_id = :me "
                "RETURNING id, book, author, status, year, cover_url"
            ),
            {**fields, "book_id": book_id, "me": user_id},
        ).mappings().one_or_none()

    if row is None:
        # Either the row doesn't exist or isn't the user's — same 404 either way
        # (don't reveal existence of other users' rows).
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book not found")
    return Book(**row)


@router.delete("/{book_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_book(book_id: int, user_id: str = Depends(get_current_user_id)):
    """Delete a book — only if it belongs to the current user."""
    with engine.begin() as conn:
        result = conn.execute(
            text("DELETE FROM public.library WHERE id = :book_id AND user_id = :me"),
            {"book_id": book_id, "me": user_id},
        )
    if result.rowcount == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book not found")
    return None
