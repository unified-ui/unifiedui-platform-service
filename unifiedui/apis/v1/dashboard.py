"""API routes for dashboard endpoints."""
from fastapi import APIRouter, Depends, HTTPException, Request

from unifiedui.handlers.dashboard import DashboardHandler
from unifiedui.handlers.dependencies.dashboard import get_dashboard_handler
from unifiedui.core.middleware.apis.v1.auth import authenticate
from unifiedui.core.identity.users import ContextIdentityUser
from unifiedui.schema.responses.dashboard import DashboardStatsResponse
from unifiedui.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/dashboard")


@router.get("/stats", response_model=DashboardStatsResponse)
@authenticate()
async def get_dashboard_stats(
    request: Request,
    tenant_id: str,
    handler: DashboardHandler = Depends(get_dashboard_handler),
):
    """Get dashboard quick stats for the tenant.

    Returns counts of applications, autonomous agents, and conversations
    that the authenticated user has access to.
    """
    try:
        user: ContextIdentityUser = request.state.user
        use_cache = request.headers.get("X-Use-Cache", "true").lower() != "false"
        return handler.get_dashboard_stats(
            tenant_id=tenant_id,
            user=user,
            use_cache=use_cache,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get dashboard stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to get dashboard stats")
