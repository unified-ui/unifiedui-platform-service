"""Handler dependencies for FastAPI."""
from typing import Optional

from fastapi import Depends

from aihub.core.database.client import SQLAlchemyClient
from aihub.handlers.tenants import TenantHandler
from aihub.core.vault.client import BaseVaultClient
from aihub.caching.client import CacheClient
from aihub.handlers.dependencies.database import get_db_client
from aihub.handlers.dependencies.cache import get_cache_client
from aihub.handlers.dependencies.vault import get_vault_client


def get_tenant_handler(
    db_client: SQLAlchemyClient = Depends(get_db_client),
    cache_client: Optional[CacheClient] = Depends(get_cache_client)
) -> TenantHandler:
    """
    Get a TenantHandler instance as a dependency.
    
    Args:
        db_client: SQLAlchemy database client dependency
        cache_client: Optional cache client dependency
        
    Returns:
        TenantHandler instance
    """
    return TenantHandler(db_client, cache_client)


def get_custom_group_handler(
    db_client: SQLAlchemyClient = Depends(get_db_client),
    cache_client: Optional[CacheClient] = Depends(get_cache_client)
) -> "CustomGroupHandler":
    """
    Get a CustomGroupHandler instance as a dependency.
    
    Args:
        db_client: SQLAlchemy database client dependency
        cache_client: Optional cache client dependency
        
    Returns:
        CustomGroupHandler instance
    """
    from aihub.handlers.custom_groups import CustomGroupHandler
    return CustomGroupHandler(db_client, cache_client)


def get_credential_handler(
    db_client: SQLAlchemyClient = Depends(get_db_client),
    vault_client: Optional[BaseVaultClient] = Depends(get_vault_client),
    cache_client: Optional[CacheClient] = Depends(get_cache_client)
) -> "CredentialHandler":
    """
    Get a CredentialHandler instance as a dependency.
    
    Args:
        db_client: SQLAlchemy database client dependency
        vault_client: Vault client dependency
        cache_client: Optional cache client dependency
        
    Returns:
        CredentialHandler instance
        
    Raises:
        RuntimeError: If vault client is not configured
    """
    if vault_client is None:
        raise RuntimeError("Vault client is not configured. Set VAULT_TYPE and related configuration.")
    
    from aihub.handlers.credentials import CredentialHandler
    return CredentialHandler(db_client, vault_client, cache_client)

