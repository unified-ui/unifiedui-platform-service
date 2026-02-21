"""Dependency injection for recent visits handler."""

from unifiedui.handlers.dependencies import get_cache_client, get_db_client
from unifiedui.handlers.recent_visits import RecentVisitsHandler


def get_recent_visits_handler() -> RecentVisitsHandler:
    """Create and return a RecentVisitsHandler instance.

    Returns:
        RecentVisitsHandler with injected dependencies.
    """
    return RecentVisitsHandler(
        db_client=get_db_client(),
        cache_client=get_cache_client(),
    )
