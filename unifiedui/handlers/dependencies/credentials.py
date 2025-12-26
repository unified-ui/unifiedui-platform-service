"""Credential handler dependency for FastAPI."""
from typing import Optional

from fastapi import Depends

from aihub.core.database.client import SQLAlchemyClient
from aihub.handlers.credentials import CredentialHandler
from aihub.core.vault.client import BaseVaultClient
from aihub.caching.client import CacheClient
from aihub.handlers.dependencies.database import get_db_client
from aihub.handlers.dependencies.cache import get_cache_client
from aihub.handlers.dependencies.vault import get_vault_client


def get_credential_handler(
    db_client: SQLAlchemyClient = Depends(get_db_client),
    vault_client: BaseVaultClient = Depends(get_vault_client),
    cache_client: Optional[CacheClient] = Depends(get_cache_client)
) -> CredentialHandler:
    """
    Get a CredentialHandler instance as a dependency.
    
    Args:
        db_client: SQLAlchemy database client dependency
        vault_client: Vault client dependency for secret management
        cache_client: Optional cache client dependency
        
    Returns:
        CredentialHandler instance
    """
    return CredentialHandler(db_client, vault_client, cache_client)
