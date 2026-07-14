"""Pydantic request/response models for the API."""

from typing import Literal, Optional

from pydantic import BaseModel, Field

Status = Literal["Yet to Buy", "Reading", "Ready to Start", "Finished"]


# ── Library CRUD ──
class BookCreate(BaseModel):
    book: str = Field(min_length=1)
    author: Optional[str] = None
    status: Status = "Yet to Buy"
    year: Optional[int] = Field(default=None, ge=1000, le=2200)


class BookUpdate(BaseModel):
    """All fields optional — partial update."""
    book: Optional[str] = Field(default=None, min_length=1)
    author: Optional[str] = None
    status: Optional[Status] = None
    year: Optional[int] = Field(default=None, ge=1000, le=2200)
    cover_url: Optional[str] = None


class Book(BaseModel):
    id: int
    book: str
    author: Optional[str] = None
    status: Status
    year: Optional[int] = None
    cover_url: Optional[str] = None


# ── AI endpoints ──
class SummariseRequest(BaseModel):
    book_name: str = Field(min_length=1)
    author_name: Optional[str] = ""


class SummariseResponse(BaseModel):
    summary: str


class RecommendRequest(BaseModel):
    book_name: str = Field(min_length=1)
    author_name: Optional[str] = ""


class Recommendation(BaseModel):
    title: str
    author: str = ""
    reason: str = ""
    amazon_link: str = ""


class RecommendResponse(BaseModel):
    original_response: str
    recommendations: list[Recommendation]


class LibraryQueryRequest(BaseModel):
    query: str = Field(min_length=1)


class LibraryQueryResponse(BaseModel):
    answer: str
    sql: Optional[str] = None


# ── Shelves (Phase 2) ──
ShelfBookSource = Literal["user", "agent"]


class ShelfCreate(BaseModel):
    name: str = Field(min_length=1)
    description: Optional[str] = None


class ShelfUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1)
    description: Optional[str] = None


class Shelf(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    book_count: int = 0
    created_at: Optional[str] = None


class ShelfBookCreate(BaseModel):
    title: str = Field(min_length=1)
    author: Optional[str] = None
    cover_url: Optional[str] = None
    reason: Optional[str] = None
    reading_order: Optional[int] = None
    library_book_id: Optional[int] = None
    added_by: ShelfBookSource = "user"
    average_rating: Optional[float] = Field(default=None, ge=0, le=5)
    ratings_count: Optional[int] = Field(default=None, ge=0)
    info_link: Optional[str] = None


class ShelfBookBulkItem(BaseModel):
    title: str = Field(min_length=1)
    author: Optional[str] = None
    cover_url: Optional[str] = None
    reason: Optional[str] = None
    reading_order: Optional[int] = None
    library_book_id: Optional[int] = None
    average_rating: Optional[float] = Field(default=None, ge=0, le=5)
    ratings_count: Optional[int] = Field(default=None, ge=0)
    info_link: Optional[str] = None


class ShelfBookBulkCreate(BaseModel):
    items: list[ShelfBookBulkItem]
    added_by: ShelfBookSource = "agent"


class ShelfBookUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1)
    author: Optional[str] = None
    cover_url: Optional[str] = None
    reason: Optional[str] = None
    reading_order: Optional[int] = None
    library_book_id: Optional[int] = None


class ShelfBook(BaseModel):
    id: str
    shelf_id: str
    library_book_id: Optional[int] = None
    title: str
    author: Optional[str] = None
    cover_url: Optional[str] = None
    reason: Optional[str] = None
    reading_order: Optional[int] = None
    added_by: ShelfBookSource
    average_rating: Optional[float] = None
    ratings_count: Optional[int] = None
    info_link: Optional[str] = None


# ── Curation agent (Phase 2, M5) ──
class ChatMessage(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str


class CurateRequest(BaseModel):
    messages: list[ChatMessage]


class CurateItem(BaseModel):
    title: str
    author: str = ""
    cover_url: Optional[str] = None
    reason: str = ""
    reading_order: int
    # Google Books aggregate rating (no review text via the API; written
    # reviews are on the info_link page). None when Google has no rating.
    average_rating: Optional[float] = Field(default=None, ge=0, le=5)
    ratings_count: Optional[int] = Field(default=None, ge=0)
    info_link: Optional[str] = None


class CurateProposal(BaseModel):
    overview: str
    items: list[CurateItem]


class CurateResponse(BaseModel):
    reply: str
    proposal: Optional[CurateProposal] = None
