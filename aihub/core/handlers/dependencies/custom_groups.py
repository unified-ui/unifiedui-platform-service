"""Custom group handler dependency for FastAPI."""
from typing import Optional

from fastapi import Depends

from aihub.core.database.client import SQLAlchemyClient
from aihub.core.handlers.custom_groups import CustomGroupHandler
from aihub.caching.client import CacheClient
from aihub.core.handlers.dependencies.database import get_db_client
from aihub.core.handlers.dependencies.cache import get_cache_client


def get_custom_group_handler(
    db_client: SQLAlchemyClient = Depends(get_db_client),
    cache_client: Optional[CacheClient] = Depends(get_cache_client)
) -> CustomGroupHandler:
    """
    Get a CustomGroupHandler instance as a dependency.
    
    Args:
        db_client: SQLAlchemy database client dependency
        cache_client: Optional cache client dependency
        
    Returns:
        CustomGroupHandler instance
    """
    return CustomGroupHandler(db_client, cache_client)
