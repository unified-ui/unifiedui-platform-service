"""Credential handler dependency for FastAPI."""

from fastapi import Depends

from unifiedui.caching.client import CacheClient
from unifiedui.core.database.client import SQLAlchemyClient
from unifiedui.core.vault.client import BaseVaultClient
from unifiedui.handlers.credentials import CredentialHandler
from unifiedui.handlers.dependencies.cache import get_cache_client
from unifiedui.handlers.dependencies.database import get_db_client
from unifiedui.handlers.dependencies.vault import get_secrets_vault


def get_credential_handler(
    db_client: SQLAlchemyClient = Depends(get_db_client),
    vault_client: BaseVaultClient = Depends(get_secrets_vault),
    cache_client: CacheClient | None = Depends(get_cache_client),
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
