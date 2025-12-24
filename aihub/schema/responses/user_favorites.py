"""Response schemas for user favorites."""
from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel


class UserFavoriteResponse(BaseModel):
    """Response schema for a single user favorite."""
    tenant_id: str
    user_id: str
    resource_id: str
    resource_type: str
    created_at: datetime
    updated_at: datetime
    created_by: Optional[str] = None
    updated_by: Optional[str] = None

    class Config:
        from_attributes = True


class UserFavoritesListResponse(BaseModel):
    """Response schema for list of user favorites."""
    favorites: List[UserFavoriteResponse]
    total: int
