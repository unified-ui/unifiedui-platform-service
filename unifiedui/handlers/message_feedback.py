"""Handler for message feedback business logic."""

import uuid

from sqlalchemy import select

from unifiedui.core.database.client import SQLAlchemyClient
from unifiedui.core.database.models import Conversation, MessageFeedback
from unifiedui.exc.conversations import ConversationNotFoundError
from unifiedui.exc.message_feedback import MessageFeedbackNotFoundError
from unifiedui.schema.requests.message_feedback import MessageFeedbackResponse, UpsertMessageFeedbackRequest


class MessageFeedbackHandler:
    """Handler class for message feedback CRUD operations."""

    def __init__(self, db_client: SQLAlchemyClient) -> None:
        """Initialize the handler.

        Args:
            db_client: SQLAlchemy database client.
        """
        self.db_client = db_client

    def _ensure_conversation(self, session, tenant_id: str, conversation_id: str) -> None:
        """Ensure the conversation exists and belongs to the tenant."""
        stmt = select(Conversation.id).where(Conversation.id == conversation_id, Conversation.tenant_id == tenant_id)
        if session.execute(stmt).scalar_one_or_none() is None:
            raise ConversationNotFoundError(conversation_id)

    def upsert(
        self,
        tenant_id: str,
        conversation_id: str,
        message_id: str,
        user_id: str,
        request: UpsertMessageFeedbackRequest,
    ) -> MessageFeedbackResponse:
        """Create or update feedback for a message authored by the given user.

        Args:
            tenant_id: Tenant scope.
            conversation_id: Owning conversation.
            message_id: Message identifier (opaque, from agent-service).
            user_id: Principal id of the feedback author.
            request: Validated request payload.

        Returns:
            The persisted feedback entry as a response model.
        """
        with self.db_client.get_session() as session:
            self._ensure_conversation(session, tenant_id, conversation_id)

            stmt = select(MessageFeedback).where(
                MessageFeedback.tenant_id == tenant_id,
                MessageFeedback.message_id == message_id,
                MessageFeedback.user_id == user_id,
            )
            existing = session.execute(stmt).scalar_one_or_none()

            if existing is None:
                entry = MessageFeedback(
                    id=str(uuid.uuid4()),
                    tenant_id=tenant_id,
                    conversation_id=conversation_id,
                    message_id=message_id,
                    user_id=user_id,
                    rating=request.rating.value,
                    reasons=[r.value for r in request.reasons],
                    comment=request.comment,
                )
                session.add(entry)
            else:
                existing.rating = request.rating.value
                existing.reasons = [r.value for r in request.reasons]
                existing.comment = request.comment
                entry = existing

            session.flush()
            session.refresh(entry)
            return MessageFeedbackResponse.model_validate(entry)

    def get_for_user(
        self, tenant_id: str, conversation_id: str, message_id: str, user_id: str
    ) -> MessageFeedbackResponse:
        """Return the feedback this user has left on the given message."""
        with self.db_client.get_session() as session:
            self._ensure_conversation(session, tenant_id, conversation_id)
            stmt = select(MessageFeedback).where(
                MessageFeedback.tenant_id == tenant_id,
                MessageFeedback.message_id == message_id,
                MessageFeedback.user_id == user_id,
            )
            entry = session.execute(stmt).scalar_one_or_none()
            if entry is None:
                raise MessageFeedbackNotFoundError(message_id, user_id)
            return MessageFeedbackResponse.model_validate(entry)

    def delete(self, tenant_id: str, conversation_id: str, message_id: str, user_id: str) -> None:
        """Delete the user's feedback for the given message."""
        with self.db_client.get_session() as session:
            self._ensure_conversation(session, tenant_id, conversation_id)
            stmt = select(MessageFeedback).where(
                MessageFeedback.tenant_id == tenant_id,
                MessageFeedback.message_id == message_id,
                MessageFeedback.user_id == user_id,
            )
            entry = session.execute(stmt).scalar_one_or_none()
            if entry is None:
                raise MessageFeedbackNotFoundError(message_id, user_id)
            session.delete(entry)

    def list_for_conversation(self, tenant_id: str, conversation_id: str) -> list[MessageFeedbackResponse]:
        """List all feedback entries for a conversation."""
        with self.db_client.get_session() as session:
            self._ensure_conversation(session, tenant_id, conversation_id)
            stmt = (
                select(MessageFeedback)
                .where(
                    MessageFeedback.tenant_id == tenant_id,
                    MessageFeedback.conversation_id == conversation_id,
                )
                .order_by(MessageFeedback.created_at.desc())
            )
            entries = session.execute(stmt).scalars().all()
            return [MessageFeedbackResponse.model_validate(e) for e in entries]
