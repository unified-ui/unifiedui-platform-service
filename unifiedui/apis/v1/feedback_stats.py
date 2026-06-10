"""API routes for feedback statistics."""

from datetime import datetime
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from unifiedui.core.middleware.apis.v1.auth import authenticate
from unifiedui.handlers.dependencies.feedback_stats import get_feedback_stats_handler
from unifiedui.handlers.feedback_stats import FeedbackStatsHandler
from unifiedui.logger import get_logger
from unifiedui.schema.responses.feedback_stats import FeedbackStatsBatchResponse

if TYPE_CHECKING:
    from unifiedui.core.identity.users import ContextIdentityUser

logger = get_logger(__name__)

router = APIRouter(prefix="/feedback")


def _parse_chat_agent_ids(value: str | None) -> list[str] | None:
    """Parse a comma-separated chat_agent_id query string into a list.

    Args:
        value: Raw query parameter value (may be None or empty).

    Returns:
        List of trimmed, non-empty IDs or None if no IDs were provided.
    """
    if not value:
        return None
    ids = [part.strip() for part in value.split(",") if part.strip()]
    return ids or None


@router.get("/stats", response_model=FeedbackStatsBatchResponse)
@authenticate()
async def get_feedback_stats(
    request: Request,
    tenant_id: str,
    chat_agent_id: str | None = Query(default=None),
    from_date: datetime | None = Query(default=None, alias="from"),
    to_date: datetime | None = Query(default=None, alias="to"),
    handler: FeedbackStatsHandler = Depends(get_feedback_stats_handler),
) -> FeedbackStatsBatchResponse:
    """Get aggregated feedback statistics for the tenant.

    Supports optional filtering by a comma-separated list of chat agent IDs
    and a date range. Returns both an overall aggregate and a per-agent
    breakdown.
    """
    try:
        _user: ContextIdentityUser = request.state.user
        return handler.get_feedback_stats(
            tenant_id=tenant_id,
            chat_agent_ids=_parse_chat_agent_ids(chat_agent_id),
            from_date=from_date,
            to_date=to_date,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get feedback stats: %s", e)
        raise HTTPException(status_code=500, detail="Failed to get feedback stats")
