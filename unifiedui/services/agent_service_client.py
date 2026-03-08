"""Agent service client for cross-service communication."""

from __future__ import annotations

from typing import TYPE_CHECKING

import httpx

from unifiedui.core.config import settings
from unifiedui.logger import get_logger

if TYPE_CHECKING:
    from unifiedui.core.vault.client import BaseVaultClient

logger = get_logger(__name__)


class AgentServiceClient:
    """HTTP client for communicating with the agent service.

    Handles cascade delete operations via X-Service-Key authentication.
    All operations are best-effort: failures are logged but do not propagate.
    """

    def __init__(self, base_url: str, app_vault: BaseVaultClient | None = None, timeout: int = 30):
        """
        Initialize the agent service client.

        Args:
            base_url: Base URL of the agent service
            app_vault: App vault client for resolving service keys
            timeout: Request timeout in seconds
        """
        self._base_url = base_url.rstrip("/")
        self._app_vault = app_vault
        self._timeout = timeout

    def _get_service_key(self) -> str | None:
        """
        Retrieve the platform-to-agent service key from app vault.

        Returns:
            Service key string or None if not available
        """
        if self._app_vault:
            vault_key_name = settings.app_vault_platform_to_agent_key
            try:
                uri = self._app_vault.build_secret_uri(vault_key_name)
                return self._app_vault.get_secret(uri, use_cache=False)
            except Exception:
                logger.warning("Failed to retrieve platform-to-agent service key from app vault")

        return None

    def _build_headers(self) -> dict[str, str]:
        """
        Build request headers with X-Service-Key.

        Returns:
            Headers dict
        """
        headers: dict[str, str] = {"Content-Type": "application/json"}
        service_key = self._get_service_key()
        if service_key:
            headers["X-Service-Key"] = service_key
        return headers

    def delete_conversation_data(self, tenant_id: str, conversation_id: str) -> bool:
        """
        Delete all conversation data (messages + traces) from agent service.

        This is a best-effort operation. Failures are logged but not raised.

        Args:
            tenant_id: Tenant ID
            conversation_id: Conversation ID

        Returns:
            True if successful, False on failure
        """
        url = f"{self._base_url}/api/v1/agent-service/tenants/{tenant_id}/conversations/{conversation_id}/data"
        return self._perform_delete(url, "conversation data", tenant_id, conversation_id)

    def delete_autonomous_agent_data(self, tenant_id: str, autonomous_agent_id: str) -> bool:
        """
        Delete all autonomous agent data (traces) from agent service.

        This is a best-effort operation. Failures are logged but not raised.

        Args:
            tenant_id: Tenant ID
            autonomous_agent_id: Autonomous agent ID

        Returns:
            True if successful, False on failure
        """
        url = f"{self._base_url}/api/v1/agent-service/tenants/{tenant_id}/autonomous-agents/{autonomous_agent_id}/data"
        return self._perform_delete(url, "autonomous agent data", tenant_id, autonomous_agent_id)

    def _perform_delete(self, url: str, resource_label: str, tenant_id: str, resource_id: str) -> bool:
        """
        Perform an HTTP DELETE request with best-effort error handling.

        Args:
            url: Full URL to call
            resource_label: Human-readable resource name for logging
            tenant_id: Tenant ID for logging
            resource_id: Resource ID for logging

        Returns:
            True if successful (2xx), False on failure
        """
        try:
            headers = self._build_headers()
            with httpx.Client(timeout=self._timeout) as client:
                response = client.delete(url, headers=headers)

            if response.status_code < 300:
                logger.info(
                    f"Cascade delete {resource_label} succeeded",
                    extra={"tenant_id": tenant_id, "resource_id": resource_id},
                )
                return True

            logger.error(
                f"Cascade delete {resource_label} failed with status {response.status_code}",
                extra={
                    "tenant_id": tenant_id,
                    "resource_id": resource_id,
                    "status_code": response.status_code,
                },
            )
            return False
        except Exception as exc:
            logger.error(
                f"Cascade delete {resource_label} failed: {exc}",
                extra={"tenant_id": tenant_id, "resource_id": resource_id},
            )
            return False
