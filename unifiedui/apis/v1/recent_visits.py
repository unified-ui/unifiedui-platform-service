"""API routes for recent visit endpoints."""

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from unifiedui.core.middleware.apis.v1.auth import authenticate
from unifiedui.handlers.dependencies.recent_visits import get_recent_visits_handler
from unifiedui.handlers.recent_visits import RecentVisitsHandler
from unifiedui.logger import get_logger
from unifiedui.schema.requests.recent_visits import SyncRecentVisitsRequest
from unifiedui.schema.responses.recent_visits import RecentVisitListResponse

if TYPE_CHECKING:
    from unifiedui.core.identity.users import ContextIdentityUser

logger = get_logger(__name__)

router = APIRouter(prefix="/users/{user_id}/recent-visits")


@router.get("", response_model=RecentVisitListResponse)
@authenticate()
async def list_recent_visits(
    request: Request,
    tenant_id: str,
    user_id: str,
    limit: int = Query(20, ge=1, le=50, description="Max results"),
    handler: RecentVisitsHandler = Depends(get_recent_visits_handler),
):
    """List recent visits for a user."""
    try:
        user: ContextIdentityUser = request.state.user
        actual_user_id = user.identity.get_id()
        if user_id != actual_user_id:
            raise HTTPException(status_code=403, detail="Cannot access other user's visits")
        return handler.list_recent_visits(
            tenant_id=tenant_id,
            user_id=actual_user_id,
            limit=limit,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to list recent visits: %s", e)
        raise HTTPException(status_code=500, detail="Failed to list recent visits")


@router.post("/sync", response_model=RecentVisitListResponse)
@authenticate()
async def sync_recent_visits(
    request: Request,
    tenant_id: str,
    user_id: str,
    request_body: SyncRecentVisitsRequest,
    handler: RecentVisitsHandler = Depends(get_recent_visits_handler),
):
    """Batch-sync recent visits from frontend localStorage."""
    try:
        user: ContextIdentityUser = request.state.user
        actual_user_id = user.identity.get_id()
        if user_id != actual_user_id:
            raise HTTPException(status_code=403, detail="Cannot sync other user's visits")
        return handler.sync_recent_visits(
            tenant_id=tenant_id,
            user_id=actual_user_id,
            request=request_body,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to sync recent visits: %s", e)
        raise HTTPException(status_code=500, detail="Failed to sync recent visits")
