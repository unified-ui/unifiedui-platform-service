"""API routes for global search endpoints."""

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from unifiedui.core.middleware.apis.v1.auth import authenticate
from unifiedui.handlers.dependencies.search import get_search_handler
from unifiedui.handlers.search import SearchHandler
from unifiedui.logger import get_logger
from unifiedui.schema.responses.search import SearchResponse

if TYPE_CHECKING:
    from unifiedui.core.identity.users import ContextIdentityUser

logger = get_logger(__name__)

router = APIRouter(prefix="/search")


@router.get("", response_model=SearchResponse)
@authenticate()
async def global_search(
    request: Request,
    tenant_id: str,
    q: str = Query("", description="Search query string"),
    types: str | None = Query(None, description="Comma-separated entity types"),
    limit: int = Query(10, ge=1, le=50, description="Max results per type"),
    handler: SearchHandler = Depends(get_search_handler),
):
    """Search across all entity types within the tenant.

    Searches chat agents, autonomous agents, and conversations
    by name and description, respecting RBAC permissions.
    """
    try:
        user: ContextIdentityUser = request.state.user
        type_list = [t.strip() for t in types.split(",")] if types else None
        return handler.search(
            tenant_id=tenant_id,
            user=user,
            query=q,
            types=type_list,
            limit=limit,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Search failed: %s", e)
        raise HTTPException(status_code=500, detail="Search failed")
