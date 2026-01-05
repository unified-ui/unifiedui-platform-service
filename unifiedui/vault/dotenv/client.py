"""DotEnv vault client implementation."""
from typing import Optional, Any

from unifiedui.core.vault.client import BaseVaultClient
from unifiedui.core.vault.vault import BaseVault
from unifiedui.vault.dotenv.vault import DotEnvVault
from unifiedui.logger import get_logger

logger = get_logger(__name__)


class DotEnvVaultClient(BaseVaultClient):
    """
    DotEnv vault client for local development.
    
    Wraps DotEnvVault with the standard vault client interface,
    including optional encrypted caching support.
    """

    def __init__(self, cache_client: Optional[Any] = None):
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
