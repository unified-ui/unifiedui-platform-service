"""API routes for config suggestions endpoints."""

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from unifiedui.core.middleware.apis.v1.auth import authenticate
from unifiedui.handlers.config_suggestions import ConfigSuggestionsHandler
from unifiedui.handlers.dependencies.config_suggestions import (
    get_config_suggestions_handler,
)
from unifiedui.logger import get_logger
from unifiedui.schema.responses.config_suggestions import ConfigSuggestionsResponse

if TYPE_CHECKING:
    from unifiedui.core.identity.users import ContextIdentityUser

logger = get_logger(__name__)

router = APIRouter(prefix="/config-suggestions")


@router.get("", response_model=ConfigSuggestionsResponse)
@authenticate()
async def get_config_suggestions(
    request: Request,
    tenant_id: str,
    type: str = Query(..., description="Platform type (e.g. N8N, MICROSOFT_FOUNDRY, REST_API)"),
    q: str | None = Query(None, description="Optional substring filter for suggestion values"),
    handler: ConfigSuggestionsHandler = Depends(get_config_suggestions_handler),
):
    """Return distinct config field values from existing agents and workflows.

    Enables the frontend to suggest previously used endpoint URLs
    when configuring new agents or workflows.
    """
    try:
        _: ContextIdentityUser = request.state.user
        return handler.get_suggestions(
            tenant_id=tenant_id,
            platform_type=type,
            query=q,
        )
    except HTTPException:
        raise
    except Exception:
        logger.exception("Error fetching config suggestions")
        raise HTTPException(status_code=500, detail="Failed to fetch config suggestions")
