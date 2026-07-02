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
