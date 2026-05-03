"""Internal S2S router for ingesting message telemetry from agent-service."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status

from unifiedui.core.middleware.apis.v1.auth import authenticate_service_key
from unifiedui.handlers.dependencies.message_metrics import get_message_metric_handler
from unifiedui.handlers.message_metrics import MessageMetricHandler  # noqa: TC001 — runtime-resolved by FastAPI Depends
from unifiedui.logger import get_logger
from unifiedui.schema.requests.message_metrics import (
    MessageMetricBatchRequest,
    MessageMetricBatchResponse,
    MessageMetricCreateRequest,
    MessageMetricResponse,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/internal/metrics")


@router.post(
    "/messages",
    response_model=MessageMetricResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Ingest a single message metric (S2S)",
    description="Internal endpoint for the agent-service to push per-message telemetry. Idempotent on (tenant_id, message_id).",
)
@authenticate_service_key("X_AGENT_SERVICE_KEY")
async def ingest_message_metric(
    request: Request,
    payload: MessageMetricCreateRequest,
    handler: MessageMetricHandler = Depends(get_message_metric_handler),
) -> MessageMetricResponse:
    """Ingest a single message metric. Idempotent upsert on (tenant_id, message_id)."""
    try:
        response, _ = handler.upsert(payload)
        return response
    except Exception as e:
        logger.error("Failed to ingest message metric: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to ingest message metric",
        )


@router.post(
    "/messages:batch",
    response_model=MessageMetricBatchResponse,
    status_code=status.HTTP_200_OK,
    summary="Bulk-ingest message metrics (S2S)",
    description="Internal bulk-ingest endpoint, max 100 metrics per call.",
)
@authenticate_service_key("X_AGENT_SERVICE_KEY")
async def ingest_message_metrics_batch(
    request: Request,
    payload: MessageMetricBatchRequest,
    handler: MessageMetricHandler = Depends(get_message_metric_handler),
) -> MessageMetricBatchResponse:
    """Bulk-ingest message metrics in a single transaction."""
    try:
        return handler.upsert_batch(payload.items)
    except Exception as e:
        logger.error("Failed to bulk-ingest message metrics: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to bulk-ingest message metrics",
        )
