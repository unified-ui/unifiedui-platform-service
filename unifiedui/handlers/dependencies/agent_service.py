"""Agent service client dependency for FastAPI."""
from typing import Optional

from unifiedui.core.config import settings
from unifiedui.services.agent_service_client import AgentServiceClient
from unifiedui.handlers.dependencies.vault import get_app_service_vault

_agent_service_client: Optional[AgentServiceClient] = None


def get_agent_service_client() -> AgentServiceClient:
    """
    Get a singleton AgentServiceClient instance.
    
    Returns:
        AgentServiceClient instance
    """
    global _agent_service_client

    if _agent_service_client is not None:
        return _agent_service_client

    _agent_service_client = AgentServiceClient(
        base_url=settings.agent_service_url,
        app_vault=get_app_service_vault(),
        timeout=settings.agent_service_timeout
    )
    return _agent_service_client


def set_test_agent_service_client(client: Optional[AgentServiceClient]) -> None:
    """
    Set a test agent service client for testing purposes.
    
    Args:
        client: Agent service client to use for testing, or None to reset
    """
    global _agent_service_client
    _agent_service_client = client


def reset_agent_service_client() -> None:
    """Reset the singleton agent service client."""
    global _agent_service_client
    _agent_service_client = None
