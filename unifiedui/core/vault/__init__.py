"""Core vault interfaces and base implementations."""

from unifiedui.core.vault.client import BaseVaultClient
from unifiedui.core.vault.vault import BaseVault

__all__ = [
    "BaseVault",
    "BaseVaultClient",
]
