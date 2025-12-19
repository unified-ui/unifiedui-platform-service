"""Vault dependency injection."""
from functools import lru_cache
from typing import Optional

from aihub.core.config import settings
from aihub.core.vault.client import BaseVaultClient
from aihub.vault.azure_keyvault.client import AzureKeyVaultClient
from aihub.vault.hashicorp_vault.client import HashiCorpVaultClient
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
    vault_type = settings.VAULT_TYPE
    
    if not vault_type:
        logger.info("No vault configured (VAULT_TYPE not set)")
        return None
    
    logger.info(f"Initializing vault client: {vault_type}")
    
    if vault_type.upper() == "AZURE_KEYVAULT":
        if not settings.AZURE_KEYVAULT_VAULT_NAME:
            logger.error("Azure KeyVault name not configured")
            raise RuntimeError("AZURE_KEYVAULT_VAULT_NAME must be set when using Azure KeyVault")
        
        cache_enabled = settings.CACHE_ENABLED and bool(settings.SECRETS_ENCRYPTION_KEY)
        return AzureKeyVaultClient(
            vault_name=settings.AZURE_KEYVAULT_VAULT_NAME,
            cache_enabled=cache_enabled,
            encryption_key=settings.SECRETS_ENCRYPTION_KEY,
            redis_host=settings.REDIS_HOST if cache_enabled else None,
            redis_port=settings.REDIS_PORT if cache_enabled else None,
            redis_password=settings.REDIS_PASSWORD if cache_enabled else None,
            redis_db=settings.REDIS_DB if cache_enabled else 0,
        )
    
    elif vault_type.upper() == "HASHICORP_VAULT":
        if not settings.VAULT_ADDR:
            logger.error("HashiCorp Vault address not configured")
            raise RuntimeError("VAULT_ADDR must be set when using HashiCorp Vault")
        
        cache_enabled = settings.CACHE_ENABLED and bool(settings.SECRETS_ENCRYPTION_KEY)
        return HashiCorpVaultClient(
            vault_addr=settings.VAULT_ADDR,
            token=settings.VAULT_TOKEN,
            cache_enabled=cache_enabled,
            encryption_key=settings.SECRETS_ENCRYPTION_KEY,
            redis_host=settings.REDIS_HOST if cache_enabled else None,
            redis_port=settings.REDIS_PORT if cache_enabled else None,
            redis_password=settings.REDIS_PASSWORD if cache_enabled else None,
            redis_db=settings.REDIS_DB if cache_enabled else 0,
        )
    
    else:
        logger.error(f"Unsupported vault type: {vault_type}")
        raise RuntimeError(f"Unsupported vault type: {vault_type}. Supported: AZURE_KEYVAULT, HASHICORP_VAULT")
