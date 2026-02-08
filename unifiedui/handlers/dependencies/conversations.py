"""Conversation handler dependency for FastAPI."""
from typing import Optional

from fastapi import Depends

from unifiedui.core.database.client import SQLAlchemyClient
from unifiedui.handlers.conversations import ConversationHandler
from unifiedui.caching.client import CacheClient
from unifiedui.services.agent_service_client import AgentServiceClient
from unifiedui.handlers.dependencies.database import get_db_client
from unifiedui.handlers.dependencies.cache import get_cache_client
from unifiedui.handlers.dependencies.agent_service import get_agent_service_client


def get_conversation_handler(
    db_client: SQLAlchemyClient = Depends(get_db_client),
    cache_client: Optional[CacheClient] = Depends(get_cache_client),
    agent_service_client: AgentServiceClient = Depends(get_agent_service_client)
) -> ConversationHandler:
    """
    Get a ConversationHandler instance as a dependency.
    
    Args:
        db_client: SQLAlchemy database client dependency
        cache_client: Optional cache client dependency
        agent_service_client: Agent service client for cascade delete
        
    Returns:
        ConversationHandler instance
    """
    return ConversationHandler(db_client, cache_client, agent_service_client=agent_service_client)
