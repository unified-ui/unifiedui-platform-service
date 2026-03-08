"""Chat widget handler dependency for FastAPI."""

from fastapi import Depends

from unifiedui.caching.client import CacheClient
from unifiedui.core.database.client import SQLAlchemyClient
from unifiedui.handlers.chat_widgets import ChatWidgetHandler
from unifiedui.handlers.dependencies.cache import get_cache_client
from unifiedui.handlers.dependencies.database import get_db_client


def get_chat_widget_handler(
    db_client: SQLAlchemyClient = Depends(get_db_client), cache_client: CacheClient | None = Depends(get_cache_client)
) -> ChatWidgetHandler:
    """
    Get a ChatWidgetHandler instance as a dependency.

    Args:
        db_client: SQLAlchemy database client dependency
        cache_client: Optional cache client dependency

    Returns:
        ChatWidgetHandler instance
    """
    return ChatWidgetHandler(db_client, cache_client)
