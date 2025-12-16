"""Dependency injection for custom group handler."""
from functools import lru_cache
from fastapi import Depends

from aihub.core.handlers.custom_groups import CustomGroupHandler
from aihub.database.client import DatabaseClient
from aihub.database.dependencies import get_db_client


@lru_cache()
def get_custom_group_handler(
    db_client: DatabaseClient = Depends(get_db_client)
) -> CustomGroupHandler:
    """
    Dependency to get custom group handler instance.
    
    Args:
        db_client: Database client dependency
    
    Returns:
        CustomGroupHandler instance
    """
    return CustomGroupHandler(db_client=db_client)
