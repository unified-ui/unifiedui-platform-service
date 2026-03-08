"""Response schemas for user favorites."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class UserFavoriteResponse(BaseModel):
    """Response schema for a single user favorite."""

    tenant_id: str
    user_id: str
    resource_id: str
    resource_type: str
    created_at: datetime
    updated_at: datetime
    created_by: str | None = None
    updated_by: str | None = None

    model_config = ConfigDict(from_attributes=True)


class UserFavoritesListResponse(BaseModel):
    """Response schema for list of user favorites."""

    favorites: list[UserFavoriteResponse]
    total: int
