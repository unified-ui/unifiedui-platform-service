"""HashiCorp Vault client implementation."""
from typing import Optional, Any

from aihub.core.vault.client import BaseVaultClient
from aihub.core.vault.vault import BaseVault
from aihub.vault.hashicorp_vault.vault import HashiCorpVault
from aihub.logger import get_logger

logger = get_logger(__name__)


class HashiCorpVaultClient(BaseVaultClient):
    """HashiCorp Vault implementation of vault client."""

    def __init__(
        self,
        url: Optional[str] = None,
        token: Optional[str] = None,
        mount_point: str = "secret",
        cache_client: Optional[Any] = None
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
