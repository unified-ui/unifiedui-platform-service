"""Request schemas for recent visits."""
from __future__ import annotations

from pydantic import BaseModel, Field


class RecentVisitItem(BaseModel):
    """Single recent visit item for sync."""

    resource_type: str = Field(max_length=50)
    resource_id: str
    resource_name: str = Field(max_length=255)


class SyncRecentVisitsRequest(BaseModel):
    """Request to batch-sync recent visits from frontend."""

    visits: list[RecentVisitItem] = Field(max_length=50)
