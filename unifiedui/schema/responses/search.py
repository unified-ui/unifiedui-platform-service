"""Response schemas for global search."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class SearchResultItem(BaseModel):
    """Single search result item."""

    type: str
    id: str
    name: str
    description: Optional[str] = None
    match_field: str
    is_active: Optional[bool] = None
    tags: list[str] = []


class SearchResponse(BaseModel):
    """Global search response."""

    results: list[SearchResultItem]
    total: int
    query: str
