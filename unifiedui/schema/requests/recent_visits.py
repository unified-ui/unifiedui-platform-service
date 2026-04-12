"""Request schemas for recent visits."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

ALLOWED_RESOURCE_TYPES = {"chat_agent", "workflow", "external_app", "chat_widget"}


class RecentVisitItem(BaseModel):
    """Single recent visit item for sync."""

    resource_type: str = Field(max_length=50)
    resource_id: str
    resource_name: str = Field(max_length=255)

    @field_validator("resource_type")
    @classmethod
    def validate_resource_type(cls, v: str) -> str:
        """Validate that resource_type is allowed (no 'conversation')."""
        if v not in ALLOWED_RESOURCE_TYPES:
            allowed = ", ".join(sorted(ALLOWED_RESOURCE_TYPES))
            raise ValueError(f"resource_type must be one of: {allowed}")
        return v


class SyncRecentVisitsRequest(BaseModel):
    """Request to batch-sync recent visits from frontend."""

    visits: list[RecentVisitItem] = Field(max_length=50)
