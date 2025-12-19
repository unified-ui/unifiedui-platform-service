"""Vault dependency injection."""
from functools import lru_cache
from typing import Optional

from aihub.core.config import settings
from aihub.core.vault.client import BaseVaultClient
from aihub.vault.azure_keyvault.client import AzureKeyVaultClient
from aihub.vault.hashicorp_vault.client import HashiCorpVaultClient
from aihub.handlers.dependencies.cache import get_cache_client
from aihub.logger import get_logger

logger = get_logger(__name__)


@lru_cache
def get_vault_client() -> Optional[BaseVaultClient]:
    """
    Get vault client instance based on configuration.
    
    Returns:
        Vault client instance or None if vault is not configured
        
    Raises:
        RuntimeError: If vault type is not supported
    """
    vault_type = settings.vault_type
    
    if not vault_type:
        logger.info("No vault configured (vault_type not set)")
        return None
    
    logger.info(f"Initializing vault client: {vault_type}")
    
    # Get cache client if caching is enabled
    cache_client = None
    if settings.cache_enabled and settings.secrets_encryption_key:
        cache_client = get_cache_client()
    
    if vault_type.upper() == "AZURE_KEYVAULT":
        if not settings.azure_keyvault_vault_name:
            logger.error("Azure KeyVault name not configured")
            raise RuntimeError("azure_keyvault_vault_name must be set when using Azure KeyVault")
        
        vault_url = f"https://{settings.azure_keyvault_vault_name}.vault.azure.net/"
        return AzureKeyVaultClient(
            vault_url=vault_url,
            cache_client=cache_client
        )
    
    elif vault_type.upper() == "HASHICORP_VAULT":
        if not settings.vault_addr:
            logger.error("HashiCorp Vault address not configured")
            raise RuntimeError("vault_addr must be set when using HashiCorp Vault")
        
        return HashiCorpVaultClient(
            url=settings.vault_addr,
            token=settings.vault_token,
            cache_client=cache_client
        )
    
    else:
        logger.error(f"Unsupported vault type: {vault_type}")
        raise RuntimeError(f"Unsupported vault type: {vault_type}. Supported: AZURE_KEYVAULT, HASHICORP_VAULT")
