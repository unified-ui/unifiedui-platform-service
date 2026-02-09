"""Response schemas for notifications."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class NotificationResponse(BaseModel):
    """Single notification response."""

    id: str
    tenant_id: str
    user_id: Optional[str] = None
    type: str
    title: str
    message: Optional[str] = None
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    is_read: bool
    created_at: datetime
    updated_at: datetime


class NotificationListResponse(BaseModel):
    """Notification list response."""

    notifications: list[NotificationResponse]
    total: int


class UnreadCountResponse(BaseModel):
    """Unread notification count response."""

    unread_count: int
