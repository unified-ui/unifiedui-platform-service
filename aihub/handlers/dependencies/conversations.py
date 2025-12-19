"""Conversation handler dependency for FastAPI."""
from typing import Optional

from fastapi import Depends

from aihub.core.database.client import SQLAlchemyClient
from aihub.handlers.conversations import ConversationHandler
from aihub.caching.client import CacheClient
from aihub.handlers.dependencies.database import get_db_client
from aihub.handlers.dependencies.cache import get_cache_client


def get_conversation_handler(
    db_client: SQLAlchemyClient = Depends(get_db_client),
    cache_client: Optional[CacheClient] = Depends(get_cache_client)
) -> ConversationHandler:
    """
    Get a ConversationHandler instance as a dependency.
    
    Args:
        db_client: SQLAlchemy database client dependency
        cache_client: Optional cache client dependency
        
    Returns:
        ConversationHandler instance
    """
    return ConversationHandler(db_client, cache_client)
