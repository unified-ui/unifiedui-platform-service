"""Core vault interfaces and base implementations."""

from unifiedui.core.vault.vault import BaseVault
from unifiedui.core.vault.client import BaseVaultClient

__all__ = [
    "BaseVault",
    "BaseVaultClient",
]
