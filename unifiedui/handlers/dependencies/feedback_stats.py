"""Dependency injection for the FeedbackStatsHandler."""

from fastapi import Depends

from unifiedui.core.database.client import SQLAlchemyClient
from unifiedui.handlers.dependencies.database import get_db_client
from unifiedui.handlers.feedback_stats import FeedbackStatsHandler


def get_feedback_stats_handler(
    db_client: SQLAlchemyClient = Depends(get_db_client),
) -> FeedbackStatsHandler:
    """Return a FeedbackStatsHandler instance."""
    return FeedbackStatsHandler(db_client)
