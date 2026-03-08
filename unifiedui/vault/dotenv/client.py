"""DotEnv vault client implementation."""

from __future__ import annotations

from typing import TYPE_CHECKING

from unifiedui.core.vault.client import BaseVaultClient
from unifiedui.logger import get_logger
from unifiedui.vault.dotenv.vault import DotEnvVault

if TYPE_CHECKING:
    from unifiedui.core.caching.client import BaseCacheClient
    from unifiedui.core.vault.vault import BaseVault

logger = get_logger(__name__)


class DotEnvVaultClient(BaseVaultClient):
    """
    DotEnv vault client for local development.

    Wraps DotEnvVault with the standard vault client interface,
    including optional encrypted caching support.
    """

    def __init__(self, cache_client: BaseCacheClient | None = None):
        """
        Initialize DotEnv vault client.

        Args:
            cache_client: Optional cache client for caching encrypted secrets
        """
        super().__init__(cache_client)
        self._vault = DotEnvVault()
        logger.info("DotEnv vault client initialized")

    def get_vault(self) -> BaseVault:
        """Get the underlying DotEnv vault instance."""
        return self._vault
