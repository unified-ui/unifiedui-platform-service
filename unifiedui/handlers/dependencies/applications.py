"""Application handler dependency for FastAPI."""
from typing import Optional

from fastapi import Depends

from unifiedui.core.database.client import SQLAlchemyClient
from unifiedui.handlers.applications import ApplicationHandler
from unifiedui.core.vault.client import BaseVaultClient
from unifiedui.caching.client import CacheClient
from unifiedui.handlers.dependencies.database import get_db_client
from unifiedui.handlers.dependencies.cache import get_cache_client
from unifiedui.handlers.dependencies.vault import get_secrets_vault


def get_application_handler(
    db_client: SQLAlchemyClient = Depends(get_db_client),
    cache_client: Optional[CacheClient] = Depends(get_cache_client),
    vault_client: Optional[BaseVaultClient] = Depends(get_secrets_vault)
) -> ApplicationHandler:
    """
    Get an ApplicationHandler instance as a dependency.
    
    Args:
        db_client: SQLAlchemy database client dependency
        cache_client: Optional cache client dependency
        vault_client: Optional vault client dependency for secret management
        
    Returns:
        ApplicationHandler instance
    """
    return ApplicationHandler(db_client, cache_client, vault_client)
