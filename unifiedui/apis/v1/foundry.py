"""API routes for Foundry agent discovery."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel

from unifiedui.core.middleware.apis.v1.auth import authenticate
from unifiedui.libs.foundry.client import MicrosoftFoundryClient, MicrosoftFoundryError
from unifiedui.logger import get_logger

if TYPE_CHECKING:
    from unifiedui.core.identity.users import ContextIdentityUser

logger = get_logger(__name__)

router = APIRouter(prefix="/foundry")


class FoundryAgentInfo(BaseModel):
    """Single Foundry agent info."""

    id: str
    name: str


class FoundryAgentListResponse(BaseModel):
    """Response containing discovered Foundry agents."""

    agents: list[FoundryAgentInfo]


@router.get("/agents", response_model=FoundryAgentListResponse)
@authenticate()
async def list_foundry_agents(
    request: Request,
    tenant_id: str,
    project_endpoint: str = Query(..., description="Foundry project endpoint URL"),
    api_version: str = Query("2025-11-15-preview", description="Foundry API version"),
) -> FoundryAgentListResponse:
    """Discover available agents from a Foundry project endpoint.

    Uses the Foundry token from X-Microsoft-Foundry-API-Key header.
    Returns an empty list on failure instead of raising an error.
    """
    _: ContextIdentityUser = request.state.user

    foundry_token = request.headers.get("X-Microsoft-Foundry-API-Key", "")
    if not foundry_token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            foundry_token = auth_header[7:]

    if not foundry_token:
        logger.warning("Foundry agent discovery: no token available")
        return FoundryAgentListResponse(agents=[])

    logger.info(
        "Foundry agent discovery request",
        extra={"project_endpoint": project_endpoint, "api_version": api_version},
    )

    try:
        client = MicrosoftFoundryClient(
            project_endpoint=project_endpoint,
            api_token=foundry_token,
            api_version=api_version,
        )
        raw_agents = client.list_agents()
        agents = [FoundryAgentInfo(id=a["id"], name=a["name"]) for a in raw_agents]
        logger.info("Foundry agent discovery returned %d agents", len(agents))
        return FoundryAgentListResponse(agents=agents)
    except MicrosoftFoundryError as e:
        logger.warning(
            "Foundry agent discovery failed: %s (status=%s, body=%s)",
            e.message,
            e.status_code,
            e.response_body,
        )
        return FoundryAgentListResponse(agents=[])
    except Exception:
        logger.exception("Unexpected error listing Foundry agents")
        return FoundryAgentListResponse(agents=[])
