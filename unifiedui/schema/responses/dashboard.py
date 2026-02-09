"""Response schemas for dashboard endpoints."""
from pydantic import BaseModel


class EntityStatsResponse(BaseModel):
    """Stats for a single entity type."""

    total: int
    active: int
    inactive: int


class DashboardStatsResponse(BaseModel):
    """Dashboard quick stats response."""

    applications: EntityStatsResponse
    autonomous_agents: EntityStatsResponse
    conversations: EntityStatsResponse
