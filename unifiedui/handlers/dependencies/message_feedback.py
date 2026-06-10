"""Dependency injection for the MessageFeedbackHandler."""

from fastapi import Depends

from unifiedui.core.database.client import SQLAlchemyClient
from unifiedui.handlers.dependencies.database import get_db_client
from unifiedui.handlers.message_feedback import MessageFeedbackHandler


def get_message_feedback_handler(
    db_client: SQLAlchemyClient = Depends(get_db_client),
) -> MessageFeedbackHandler:
    """Return a MessageFeedbackHandler instance."""
    return MessageFeedbackHandler(db_client)
