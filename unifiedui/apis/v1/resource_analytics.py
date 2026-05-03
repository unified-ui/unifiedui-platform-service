"""Per-resource analytics endpoints (chat agents and workflows)."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Request

from unifiedui.core.middleware.apis.v1.auth import authenticate
from unifiedui.handlers.analytics import AnalyticsHandler
from unifiedui.handlers.dependencies.analytics import get_analytics_handler
from unifiedui.schema.responses.analytics import (
    ChatAgentAnalyticsResponse,
    WorkflowAnalyticsResponse,
)

router = APIRouter()


@router.get(
    "/chat-agents/{chat_agent_id}/analytics",
    response_model=ChatAgentAnalyticsResponse,
)
@authenticate()
async def get_chat_agent_analytics_for_resource(
    request: Request,
    tenant_id: Annotated[str, Path(...)],
    chat_agent_id: Annotated[str, Path(...)],
    handler: Annotated[AnalyticsHandler, Depends(get_analytics_handler)],
    from_dt: Annotated[datetime | None, Query(alias="from")] = None,
    to_dt: Annotated[datetime | None, Query(alias="to")] = None,
) -> ChatAgentAnalyticsResponse:
    """Return analytics scoped to a single chat agent."""
    return handler.chat_agent_analytics(
        tenant_id=tenant_id,
        from_dt=from_dt,
        to_dt=to_dt,
        agent_ids=[chat_agent_id],
    )


@router.get(
    "/workflows/{workflow_id}/analytics",
    response_model=WorkflowAnalyticsResponse,
)
@authenticate()
async def get_workflow_analytics_for_resource(
    request: Request,
    tenant_id: Annotated[str, Path(...)],
    workflow_id: Annotated[str, Path(...)],
    handler: Annotated[AnalyticsHandler, Depends(get_analytics_handler)],
    from_dt: Annotated[datetime | None, Query(alias="from")] = None,
    to_dt: Annotated[datetime | None, Query(alias="to")] = None,
) -> WorkflowAnalyticsResponse:
    """Return analytics scoped to a single workflow."""
    return handler.workflow_analytics(
        tenant_id=tenant_id,
        from_dt=from_dt,
        to_dt=to_dt,
        workflow_ids=[workflow_id],
    )
