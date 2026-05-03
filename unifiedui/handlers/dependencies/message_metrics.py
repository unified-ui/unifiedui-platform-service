"""Dependency injection for the MessageMetricHandler."""

from fastapi import Depends

from unifiedui.core.database.client import SQLAlchemyClient
from unifiedui.handlers.dependencies.database import get_db_client
from unifiedui.handlers.message_metrics import MessageMetricHandler


def get_message_metric_handler(
    db_client: SQLAlchemyClient = Depends(get_db_client),
) -> MessageMetricHandler:
    """Get a MessageMetricHandler instance as a dependency.

    Args:
        db_client: Database client dependency.

    Returns:
        MessageMetricHandler instance.
    """
    return MessageMetricHandler(db_client)
