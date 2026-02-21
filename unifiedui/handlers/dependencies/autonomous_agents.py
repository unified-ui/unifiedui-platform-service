"""Autonomous agent handler dependency for FastAPI."""

from fastapi import Depends

from unifiedui.caching.client import CacheClient
from unifiedui.core.database.client import SQLAlchemyClient
from unifiedui.core.vault.client import BaseVaultClient
from unifiedui.handlers.autonomous_agents import AutonomousAgentHandler
from unifiedui.handlers.dependencies.agent_service import get_agent_service_client
from unifiedui.handlers.dependencies.cache import get_cache_client
from unifiedui.handlers.dependencies.database import get_db_client
from unifiedui.handlers.dependencies.vault import get_secrets_vault
from unifiedui.services.agent_service_client import AgentServiceClient


def get_autonomous_agent_handler(
    db_client: SQLAlchemyClient = Depends(get_db_client),
    cache_client: CacheClient | None = Depends(get_cache_client),
    vault_client: BaseVaultClient | None = Depends(get_secrets_vault),
    agent_service_client: AgentServiceClient = Depends(get_agent_service_client),
) -> AutonomousAgentHandler:
    """
    Get an AutonomousAgentHandler instance as a dependency.

    Args:
        db_client: SQLAlchemy database client dependency
        cache_client: Optional cache client dependency
        vault_client: Optional vault client for secret management
        agent_service_client: Agent service client for cascade delete

    Returns:
        AutonomousAgentHandler instance
    """
    return AutonomousAgentHandler(db_client, cache_client, vault_client, agent_service_client=agent_service_client)
