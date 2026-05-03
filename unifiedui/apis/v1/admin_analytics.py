"""API routes for the admin analytics endpoints."""

from datetime import datetime
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Query, Request

from unifiedui.core.database.enums import TenantRolesEnum
from unifiedui.core.middleware.apis.v1.auth import authenticate, check_permissions
from unifiedui.handlers.analytics import AnalyticsHandler
from unifiedui.handlers.dependencies.analytics import get_analytics_handler
from unifiedui.schema.responses.analytics import ChatAgentAnalyticsResponse, WorkflowAnalyticsResponse

if TYPE_CHECKING:
    from unifiedui.core.identity.users import ContextIdentityUser  # noqa: F401

router = APIRouter(prefix="/admin/analytics")


@router.get(
    "/chat-agents",
    response_model=ChatAgentAnalyticsResponse,
    summary="Chat-agent analytics",
)
@authenticate()
@check_permissions(entity="tenant", required_permissions=[TenantRolesEnum.TENANT_GLOBAL_ADMIN])
async def chat_agent_analytics(
    request: Request,
    tenant_id: str,
    from_dt: datetime | None = Query(None, alias="from"),
    to_dt: datetime | None = Query(None, alias="to"),
    agent_ids: list[str] | None = Query(None),
    handler: AnalyticsHandler = Depends(get_analytics_handler),
) -> ChatAgentAnalyticsResponse:
    """Tenant-scoped chat-agent analytics."""
    return handler.chat_agent_analytics(tenant_id=tenant_id, from_dt=from_dt, to_dt=to_dt, agent_ids=agent_ids)


@router.get(
    "/workflows",
    response_model=WorkflowAnalyticsResponse,
    summary="Workflow analytics",
)
@authenticate()
@check_permissions(entity="tenant", required_permissions=[TenantRolesEnum.TENANT_GLOBAL_ADMIN])
async def workflow_analytics(
    request: Request,
    tenant_id: str,
    from_dt: datetime | None = Query(None, alias="from"),
    to_dt: datetime | None = Query(None, alias="to"),
    workflow_ids: list[str] | None = Query(None),
    handler: AnalyticsHandler = Depends(get_analytics_handler),
) -> WorkflowAnalyticsResponse:
    """Tenant-scoped workflow analytics."""
    return handler.workflow_analytics(tenant_id=tenant_id, from_dt=from_dt, to_dt=to_dt, workflow_ids=workflow_ids)
