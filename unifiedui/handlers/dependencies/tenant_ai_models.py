"""Tenant AI model handler dependency for FastAPI."""

from fastapi import Depends

from unifiedui.caching.client import CacheClient
from unifiedui.core.database.client import SQLAlchemyClient
from unifiedui.core.vault.client import BaseVaultClient
from unifiedui.handlers.dependencies.cache import get_cache_client
from unifiedui.handlers.dependencies.database import get_db_client
from unifiedui.handlers.dependencies.vault import get_secrets_vault
from unifiedui.handlers.tenant_ai_models import TenantAIModelHandler


def get_tenant_ai_model_handler(
    db_client: SQLAlchemyClient = Depends(get_db_client),
    cache_client: CacheClient | None = Depends(get_cache_client),
    vault_client: BaseVaultClient | None = Depends(get_secrets_vault),
) -> TenantAIModelHandler:
    """Create and return a tenant AI model handler.

    Args:
        db_client: SQLAlchemy database client.
        cache_client: Optional cache client.
        vault_client: Optional vault client for secret decryption.

    Returns:
        TenantAIModelHandler instance.
    """
    return TenantAIModelHandler(db_client, cache_client, vault_client)
