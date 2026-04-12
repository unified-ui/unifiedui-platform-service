"""Response schemas for dashboard endpoints."""

from pydantic import BaseModel


class EntityStatsResponse(BaseModel):
    """Stats for a single entity type."""

    total: int
    active: int
    inactive: int


class DashboardStatsResponse(BaseModel):
    """Dashboard quick stats response."""

    chat_agents: EntityStatsResponse
    workflows: EntityStatsResponse
    conversations: EntityStatsResponse
    external_apps: EntityStatsResponse
