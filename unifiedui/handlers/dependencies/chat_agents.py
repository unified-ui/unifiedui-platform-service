"""Chat agent handler dependency for FastAPI."""

from fastapi import Depends

from unifiedui.caching.client import CacheClient
from unifiedui.core.database.client import SQLAlchemyClient
from unifiedui.core.vault.client import BaseVaultClient
from unifiedui.handlers.chat_agents import ChatAgentHandler
from unifiedui.handlers.dependencies.cache import get_cache_client
from unifiedui.handlers.dependencies.database import get_db_client
from unifiedui.handlers.dependencies.vault import get_secrets_vault


def get_chat_agent_handler(
    db_client: SQLAlchemyClient = Depends(get_db_client),
    cache_client: CacheClient | None = Depends(get_cache_client),
    vault_client: BaseVaultClient | None = Depends(get_secrets_vault),
) -> ChatAgentHandler:
    """
    Get a ChatAgentHandler instance as a dependency.

    Args:
        db_client: SQLAlchemy database client dependency
        cache_client: Optional cache client dependency
        vault_client: Optional vault client dependency for secret management

    Returns:
        ChatAgentHandler instance
    """
    return ChatAgentHandler(db_client, cache_client, vault_client)
