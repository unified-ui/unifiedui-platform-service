"""Azure Key Vault package."""
from aihub.vault.azure_keyvault.client import AzureKeyVaultClient
from aihub.vault.azure_keyvault.keyvault import AzureKeyVault

__all__ = ["AzureKeyVaultClient", "AzureKeyVault"]
