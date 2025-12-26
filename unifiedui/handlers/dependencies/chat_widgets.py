"""Chat widget handler dependency for FastAPI."""
from typing import Optional

from fastapi import Depends

from unifiedui.core.database.client import SQLAlchemyClient
from unifiedui.handlers.chat_widgets import ChatWidgetHandler
from unifiedui.caching.client import CacheClient
from unifiedui.handlers.dependencies.database import get_db_client
from unifiedui.handlers.dependencies.cache import get_cache_client


def get_chat_widget_handler(
    db_client: SQLAlchemyClient = Depends(get_db_client),
    cache_client: Optional[CacheClient] = Depends(get_cache_client)
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
