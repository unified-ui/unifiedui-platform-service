"""ReACT agent handler dependency for FastAPI."""

from fastapi import Depends

from unifiedui.caching.client import CacheClient
from unifiedui.core.database.client import SQLAlchemyClient
from unifiedui.handlers.dependencies.cache import get_cache_client
from unifiedui.handlers.dependencies.database import get_db_client
from unifiedui.handlers.re_act_agents import ReActAgentHandler


def get_re_act_agent_handler(
    db_client: SQLAlchemyClient = Depends(get_db_client), cache_client: CacheClient | None = Depends(get_cache_client)
) -> ReActAgentHandler:
    """Get a ReActAgentHandler instance as a dependency.

    Args:
        db_client: SQLAlchemy database client dependency
        cache_client: Optional cache client dependency

    Returns:
        ReActAgentHandler instance
    """
    return ReActAgentHandler(db_client, cache_client)
