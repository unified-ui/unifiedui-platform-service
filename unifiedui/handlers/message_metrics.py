"""Business logic handler for message metric ingestion + querying."""

from __future__ import annotations

import uuid as uuid_mod
from typing import TYPE_CHECKING

from sqlalchemy import select

from unifiedui.core.database.models import MessageMetric
from unifiedui.logger import get_logger
from unifiedui.schema.requests.message_metrics import (
    MessageMetricBatchResponse,
    MessageMetricCreateRequest,
    MessageMetricResponse,
)

if TYPE_CHECKING:
    from unifiedui.core.database.client import SQLAlchemyClient

logger = get_logger(__name__)


class MessageMetricHandler:
    """Handler for the observability message_metrics table."""

    def __init__(self, db_client: SQLAlchemyClient) -> None:
        """Initialize the handler.

        Args:
            db_client: SQLAlchemy database client.
        """
        self.db_client = db_client

    def upsert(self, request: MessageMetricCreateRequest) -> tuple[MessageMetricResponse, bool]:
        """Insert a new metric, or update the existing one for the same message_id.

        Args:
            request: Metric payload.

        Returns:
            Tuple of (response, was_inserted) where was_inserted is True for inserts.
        """
        with self.db_client.get_session() as session:
            existing = session.execute(
                select(MessageMetric).where(
                    MessageMetric.tenant_id == request.tenant_id,
                    MessageMetric.message_id == request.message_id,
                )
            ).scalar_one_or_none()

            if existing is not None:
                existing.chat_agent_id = request.chat_agent_id
                existing.workflow_id = request.workflow_id
                existing.conversation_id = request.conversation_id
                existing.user_id = request.user_id
                existing.provider = request.provider
                existing.model = request.model
                existing.tokens_input = request.tokens_input
                existing.tokens_output = request.tokens_output
                existing.latency_ms = request.latency_ms
                existing.agent_type = request.agent_type
                existing.status = request.status.value
                existing.error_code = request.error_code
                session.commit()
                session.refresh(existing)
                return MessageMetricResponse.model_validate(existing), False

            metric = MessageMetric(
                id=str(uuid_mod.uuid4()),
                tenant_id=request.tenant_id,
                chat_agent_id=request.chat_agent_id,
                workflow_id=request.workflow_id,
                conversation_id=request.conversation_id,
                message_id=request.message_id,
                user_id=request.user_id,
                provider=request.provider,
                model=request.model,
                tokens_input=request.tokens_input,
                tokens_output=request.tokens_output,
                latency_ms=request.latency_ms,
                agent_type=request.agent_type,
                status=request.status.value,
                error_code=request.error_code,
            )
            session.add(metric)
            session.commit()
            session.refresh(metric)
            return MessageMetricResponse.model_validate(metric), True

    def upsert_batch(self, requests: list[MessageMetricCreateRequest]) -> MessageMetricBatchResponse:
        """Bulk-upsert message metrics in a single transaction.

        Args:
            requests: List of metric payloads (max 100, enforced by schema).

        Returns:
            MessageMetricBatchResponse with insert/update counts.
        """
        inserted = 0
        updated = 0
        with self.db_client.get_session() as session:
            for request in requests:
                existing = session.execute(
                    select(MessageMetric).where(
                        MessageMetric.tenant_id == request.tenant_id,
                        MessageMetric.message_id == request.message_id,
                    )
                ).scalar_one_or_none()

                if existing is not None:
                    existing.chat_agent_id = request.chat_agent_id
                    existing.workflow_id = request.workflow_id
                    existing.conversation_id = request.conversation_id
                    existing.user_id = request.user_id
                    existing.provider = request.provider
                    existing.model = request.model
                    existing.tokens_input = request.tokens_input
                    existing.tokens_output = request.tokens_output
                    existing.latency_ms = request.latency_ms
                    existing.agent_type = request.agent_type
                    existing.status = request.status.value
                    existing.error_code = request.error_code
                    updated += 1
                else:
                    session.add(
                        MessageMetric(
                            id=str(uuid_mod.uuid4()),
                            tenant_id=request.tenant_id,
                            chat_agent_id=request.chat_agent_id,
                            workflow_id=request.workflow_id,
                            conversation_id=request.conversation_id,
                            message_id=request.message_id,
                            user_id=request.user_id,
                            provider=request.provider,
                            model=request.model,
                            tokens_input=request.tokens_input,
                            tokens_output=request.tokens_output,
                            latency_ms=request.latency_ms,
                            agent_type=request.agent_type,
                            status=request.status.value,
                            error_code=request.error_code,
                        )
                    )
                    inserted += 1
            session.commit()

        logger.info("Bulk metric ingest complete: inserted=%d updated=%d", inserted, updated)
        return MessageMetricBatchResponse(inserted=inserted, updated=updated)
