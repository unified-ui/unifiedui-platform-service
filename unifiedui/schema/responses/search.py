"""Response schemas for global search."""

from __future__ import annotations

from pydantic import BaseModel


class SearchResultItem(BaseModel):
    """Single search result item."""

    type: str
    id: str
    name: str
    description: str | None = None
    match_field: str
    is_active: bool | None = None
    tags: list[str] = []
    sub_type: str | None = None


class SearchResponse(BaseModel):
    """Global search response."""

    results: list[SearchResultItem]
    total: int
    query: str
