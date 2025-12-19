"""Autonomous agent handler dependency for FastAPI."""
from typing import Optional

from fastapi import Depends

from aihub.core.database.client import SQLAlchemyClient
from aihub.handlers.autonomous_agents import AutonomousAgentHandler
from aihub.caching.client import CacheClient
from aihub.handlers.dependencies.database import get_db_client
from aihub.handlers.dependencies.cache import get_cache_client


def get_autonomous_agent_handler(
    db_client: SQLAlchemyClient = Depends(get_db_client),
    cache_client: Optional[CacheClient] = Depends(get_cache_client)
) -> AutonomousAgentHandler:
    """
    Get an AutonomousAgentHandler instance as a dependency.
    
    Args:
        db_client: SQLAlchemy database client dependency
        cache_client: Optional cache client dependency
        
    Returns:
        AutonomousAgentHandler instance
    """
    return AutonomousAgentHandler(db_client, cache_client)
