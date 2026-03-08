"""Response schemas for recent visits."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class RecentVisitResponse(BaseModel):
    """Single recent visit response."""

    id: str
    tenant_id: str
    user_id: str
    resource_type: str
    resource_id: str
    resource_name: str
    visited_at: datetime


class RecentVisitListResponse(BaseModel):
    """Recent visit list response."""

    visits: list[RecentVisitResponse]
    total: int
