"""Dependency injection for notification handler."""
from unifiedui.handlers.notifications import NotificationHandler
from unifiedui.handlers.dependencies import get_db_client, get_cache_client


def get_notification_handler() -> NotificationHandler:
    """Create and return a NotificationHandler instance.

    Returns:
        NotificationHandler with injected dependencies.
    """
    return NotificationHandler(
        db_client=get_db_client(),
        cache_client=get_cache_client(),
    )
