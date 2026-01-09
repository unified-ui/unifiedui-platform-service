"""Autonomous agent handler dependency for FastAPI."""
from typing import Optional

from fastapi import Depends

from unifiedui.core.database.client import SQLAlchemyClient
from unifiedui.core.vault.client import BaseVaultClient
from unifiedui.handlers.autonomous_agents import AutonomousAgentHandler
from unifiedui.caching.client import CacheClient
from unifiedui.handlers.dependencies.database import get_db_client
from unifiedui.handlers.dependencies.cache import get_cache_client
from unifiedui.handlers.dependencies.vault import get_secrets_vault


def get_autonomous_agent_handler(
    db_client: SQLAlchemyClient = Depends(get_db_client),
    cache_client: Optional[CacheClient] = Depends(get_cache_client),
    vault_client: Optional[BaseVaultClient] = Depends(get_secrets_vault)
) -> AutonomousAgentHandler:
    """
    Get an AutonomousAgentHandler instance as a dependency.
    
    Args:
        db_client: SQLAlchemy database client dependency
        cache_client: Optional cache client dependency
        vault_client: Optional vault client for secret management
        
    Returns:
        AutonomousAgentHandler instance
    """
    return AutonomousAgentHandler(db_client, cache_client, vault_client)
