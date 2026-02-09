"""Request schemas for notifications."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class CreateNotificationRequest(BaseModel):
    """Request to create a notification (internal webhook)."""

    tenant_id: str
    user_id: Optional[str] = None
    type: str
    title: str = Field(max_length=255)
    message: Optional[str] = Field(None, max_length=2000)
    resource_type: Optional[str] = Field(None, max_length=50)
    resource_id: Optional[str] = None
