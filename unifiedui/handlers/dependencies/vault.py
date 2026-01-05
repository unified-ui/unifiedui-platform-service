"""Vault dependency injection with singleton pattern."""
from functools import lru_cache
from typing import Optional

from unifiedui.core.config import settings
from unifiedui.core.vault.client import BaseVaultClient
from unifiedui.vault.azure_keyvault.client import AzureKeyVaultClient
from unifiedui.vault.hashicorp_vault.client import HashiCorpVaultClient
from unifiedui.vault.dotenv.client import DotEnvVaultClient
from unifiedui.handlers.dependencies.cache import get_cache_client
from unifiedui.logger import get_logger

logger = get_logger(__name__)

# Global vault client for testing
_vault_client: Optional[BaseVaultClient] = None

# Singleton instances for application service vault (keys) and secrets vault
_app_service_vault: Optional[BaseVaultClient] = None
_secrets_vault: Optional[BaseVaultClient] = None


def _create_vault_client(vault_type: str, cache_client: Optional[any] = None) -> BaseVaultClient:
    """
    Create a vault client based on type.
    
    Args:
        vault_type: Vault type (AZURE_KEYVAULT, HASHICORP_VAULT, DOTENV)
        cache_client: Optional cache client for caching encrypted secrets
        
    Returns:
        Vault client instance
        
    Raises:
        RuntimeError: If vault type is not supported or required config is missing
    """
    vault_type_upper = vault_type.upper()
    
    if vault_type_upper == "AZURE_KEYVAULT":
        if not settings.azure_keyvault_vault_name:
            logger.error("Azure KeyVault name not configured")
            raise RuntimeError("azure_keyvault_vault_name must be set when using Azure KeyVault")
        
        vault_url = f"https://{settings.azure_keyvault_vault_name}.vault.azure.net/"
        return AzureKeyVaultClient(
            vault_url=vault_url,
            cache_client=cache_client
        )
    
    elif vault_type_upper == "HASHICORP_VAULT":
        if not settings.vault_addr:
            logger.error("HashiCorp Vault address not configured")
            raise RuntimeError("vault_addr must be set when using HashiCorp Vault")
        
        return HashiCorpVaultClient(
            url=settings.vault_addr,
            token=settings.vault_token,
            cache_client=cache_client
        )
    
    elif vault_type_upper == "DOTENV":
        return DotEnvVaultClient(cache_client=cache_client)
    
    else:
        logger.error(f"Unsupported vault type: {vault_type}")
        raise RuntimeError(
            f"Unsupported vault type: {vault_type}. Supported: AZURE_KEYVAULT, HASHICORP_VAULT, DOTENV"
        )


@lru_cache
def get_vault_client() -> Optional[BaseVaultClient]:
    """
    Get vault client instance based on configuration.
    
    This is the default vault client used for credential secrets.
    
    Returns:
        Vault client instance or None if vault is not configured
        
    Raises:
        RuntimeError: If vault type is not supported
    """
    # Return test vault client if set
    if _vault_client is not None:
        return _vault_client
    
    vault_type = settings.vault_type
    
    if not vault_type:
        logger.info("No vault configured (vault_type not set)")
        return None
    
    logger.info(f"Initializing vault client: {vault_type}")
    
    # Get cache client if caching is enabled
    cache_client = None
    if settings.cache_enabled and settings.secrets_encryption_key:
        cache_client = get_cache_client()
    
    return _create_vault_client(vault_type, cache_client)


def get_app_service_vault() -> Optional[BaseVaultClient]:
    """
    Get singleton vault client for application service keys (X_AGENT_SERVICE_KEY).
    
    This vault is used for storing service-to-service authentication keys.
    For local development, uses DotEnv vault to read from environment.
    
    Returns:
        Vault client instance or None if not configured
    """
    global _app_service_vault
    
    if _app_service_vault is not None:
        return _app_service_vault
    
    vault_type = settings.vault_type
    if not vault_type:
        logger.info("No app service vault configured (vault_type not set)")
        return None
    
    logger.info(f"Initializing app service vault: {vault_type}")
    
    # App service vault typically doesn't need caching as keys are long-lived
    _app_service_vault = _create_vault_client(vault_type, cache_client=None)
    return _app_service_vault


def get_secrets_vault() -> Optional[BaseVaultClient]:
    """
    Get singleton vault client for credential secrets.
    
    This vault is used for storing user credentials (API keys, passwords, etc.).
    Supports encrypted caching for better performance.
    
    Returns:
        Vault client instance or None if not configured
    """
    global _secrets_vault
    
    if _secrets_vault is not None:
        return _secrets_vault
    
    vault_type = settings.vault_type
    if not vault_type:
        logger.info("No secrets vault configured (vault_type not set)")
        return None
    
    logger.info(f"Initializing secrets vault: {vault_type}")
    
    # Secrets vault can use caching for better performance
    cache_client = None
    if settings.cache_enabled and settings.secrets_encryption_key:
        cache_client = get_cache_client()
    
    _secrets_vault = _create_vault_client(vault_type, cache_client)
    return _secrets_vault


def set_test_vault_client(vault_client: Optional[BaseVaultClient]) -> None:
    """
    Set a test vault client for testing purposes.
    
    Args:
        vault_client: Vault client to use for testing, or None to reset
    """
    global _vault_client
    _vault_client = vault_client


def reset_vault_singletons() -> None:
    """
    Reset all vault singletons (for testing purposes).
    """
    global _vault_client, _app_service_vault, _secrets_vault
    _vault_client = None
    _app_service_vault = None
    _secrets_vault = None
    # Clear lru_cache
    get_vault_client.cache_clear()
