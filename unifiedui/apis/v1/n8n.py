"""API routes for N8N workflow browsing."""

from __future__ import annotations

from typing import TYPE_CHECKING

import httpx
from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel

from unifiedui.core.middleware.apis.v1.auth import authenticate
from unifiedui.handlers.credentials import CredentialHandler  # noqa: TC001
from unifiedui.handlers.dependencies import get_credential_handler
from unifiedui.logger import get_logger

if TYPE_CHECKING:
    from unifiedui.core.identity.users import ContextIdentityUser

logger = get_logger(__name__)

router = APIRouter(prefix="/n8n")


class N8NWorkflowInfo(BaseModel):
    """Single N8N workflow info."""

    id: str
    name: str
    active: bool
    url: str


class N8NWorkflowListResponse(BaseModel):
    """Response containing N8N workflows."""

    workflows: list[N8NWorkflowInfo]
    total: int


@router.get("/workflows", response_model=N8NWorkflowListResponse)
@authenticate()
async def list_n8n_workflows(
    request: Request,
    tenant_id: str,
    host: str = Query(..., description="N8N instance base URL"),
    credential_id: str = Query(..., description="API Key credential ID for N8N authentication"),
    credential_handler: CredentialHandler = Depends(get_credential_handler),
) -> N8NWorkflowListResponse:
    """Browse available workflows from an N8N instance.

    Resolves the API key from the vault using the provided credential_id,
    then calls the N8N REST API to list workflows.
    Returns an empty list on failure.
    """
    _: ContextIdentityUser = request.state.user

    try:
        api_secret = credential_handler.get_credential_secret(tenant_id, credential_id)
    except Exception:
        logger.warning("Failed to resolve N8N credential %s", credential_id)
        return N8NWorkflowListResponse(workflows=[], total=0)

    if not api_secret:
        return N8NWorkflowListResponse(workflows=[], total=0)

    clean_host = host.rstrip("/")
    url = f"{clean_host}/api/v1/workflows"
    headers = {"X-N8N-API-KEY": api_secret}

    try:
        with httpx.Client(timeout=15) as client:
            response = client.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPError as e:
        logger.warning("Failed to fetch N8N workflows: %s", e)
        return N8NWorkflowListResponse(workflows=[], total=0)

    raw_workflows = data.get("data", [])
    workflows: list[N8NWorkflowInfo] = []
    for wf in raw_workflows:
        wf_id = str(wf.get("id", ""))
        wf_name = wf.get("name", f"Workflow {wf_id}")
        wf_active = wf.get("active", False)
        wf_url = f"{clean_host}/workflow/{wf_id}"
        workflows.append(N8NWorkflowInfo(id=wf_id, name=wf_name, active=wf_active, url=wf_url))

    return N8NWorkflowListResponse(workflows=workflows, total=len(workflows))
