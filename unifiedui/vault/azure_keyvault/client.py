"""Azure Key Vault client implementation."""

from typing import Any

from unifiedui.core.vault.client import BaseVaultClient
from unifiedui.core.vault.vault import BaseVault
from unifiedui.logger import get_logger
from unifiedui.vault.azure_keyvault.keyvault import AzureKeyVault

logger = get_logger(__name__)


class AzureKeyVaultClient(BaseVaultClient):
    """Azure Key Vault implementation of vault client."""

    def __init__(self, vault_url: str | None = None, cache_client: Any | None = None):
        """
        Initialize Azure Key Vault client.

        Args:
            vault_url: Azure Key Vault URL
            cache_client: Optional cache client for caching encrypted secrets
        """
        super().__init__(cache_client)
        self._vault = AzureKeyVault(vault_url=vault_url)
        logger.info("Azure Key Vault client initialized")

    def get_vault(self) -> BaseVault:
        """Get the underlying Azure Key Vault instance."""
        return self._vault
