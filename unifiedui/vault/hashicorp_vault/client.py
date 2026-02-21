"""HashiCorp Vault client implementation."""

from typing import Any

from unifiedui.core.vault.client import BaseVaultClient
from unifiedui.core.vault.vault import BaseVault
from unifiedui.logger import get_logger
from unifiedui.vault.hashicorp_vault.vault import HashiCorpVault

logger = get_logger(__name__)


class HashiCorpVaultClient(BaseVaultClient):
    """HashiCorp Vault implementation of vault client."""

    def __init__(
        self,
        url: str | None = None,
        token: str | None = None,
        mount_point: str = "secret",
        cache_client: Any | None = None,
    ):
        """
        Initialize HashiCorp Vault client.

        Args:
            url: Vault server URL
            token: Vault authentication token
            mount_point: KV secrets engine mount point
            cache_client: Optional cache client for caching encrypted secrets
        """
        super().__init__(cache_client)
        self._vault = HashiCorpVault(url=url, token=token, mount_point=mount_point)
        logger.info("HashiCorp Vault client initialized")

    def get_vault(self) -> BaseVault:
        """Get the underlying HashiCorp Vault instance."""
        return self._vault
