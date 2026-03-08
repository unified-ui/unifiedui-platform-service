"""Vault dependency injection with singleton pattern."""

from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING

from unifiedui.core.config import settings
from unifiedui.core.vault.client import BaseVaultClient  # noqa: TC001 - FastAPI evaluates annotations at runtime
from unifiedui.handlers.dependencies.cache import get_cache_client
from unifiedui.logger import get_logger
from unifiedui.vault.azure_keyvault.client import AzureKeyVaultClient
from unifiedui.vault.dotenv.client import DotEnvVaultClient
from unifiedui.vault.hashicorp_vault.client import HashiCorpVaultClient

if TYPE_CHECKING:
    from unifiedui.core.caching.client import BaseCacheClient

logger = get_logger(__name__)

# Global vault client for testing
_vault_client: BaseVaultClient | None = None

# Singleton instances for application service vault (keys) and secrets vault
_app_service_vault: BaseVaultClient | None = None
_secrets_vault: BaseVaultClient | None = None


def _create_vault_client(
    vault_type: str,
    hashicorp_addr: str | None = None,
    hashicorp_token: str | None = None,
    azure_keyvault_url: str | None = None,
    cache_client: BaseCacheClient | None = None,
) -> BaseVaultClient:
    """
    Create a vault client based on type with per-purpose credentials.

    Args:
        vault_type: Vault type (AZURE_KEYVAULT, HASHICORP_VAULT, DOTENV)
        hashicorp_addr: HashiCorp Vault address for this purpose
        hashicorp_token: HashiCorp Vault token for this purpose
        azure_keyvault_url: Azure Key Vault URL for this purpose
        cache_client: Optional cache client for caching encrypted secrets

    Returns:
        Vault client instance

    Raises:
        RuntimeError: If vault type is not supported or required config is missing
    """
    vault_type_upper = vault_type.upper()

    if vault_type_upper == "AZURE_KEYVAULT":
        if not azure_keyvault_url:
            logger.error("Azure KeyVault URL not configured")
            raise RuntimeError("Azure KeyVault URL must be set when using Azure KeyVault")

        return AzureKeyVaultClient(vault_url=azure_keyvault_url, cache_client=cache_client)

    elif vault_type_upper == "HASHICORP_VAULT":
        if not hashicorp_addr:
            logger.error("HashiCorp Vault address not configured")
            raise RuntimeError("HashiCorp Vault address must be set when using HashiCorp Vault")

        return HashiCorpVaultClient(url=hashicorp_addr, token=hashicorp_token, cache_client=cache_client)

    elif vault_type_upper == "DOTENV":
        return DotEnvVaultClient(cache_client=cache_client)

    else:
        logger.error("Unsupported vault type: %s", vault_type)
        raise RuntimeError(f"Unsupported vault type: {vault_type}. Supported: AZURE_KEYVAULT, HASHICORP_VAULT, DOTENV")


@lru_cache
def get_vault_client() -> BaseVaultClient | None:
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

    logger.info("Initializing vault client: %s", vault_type)

    # Get cache client if caching is enabled
    base_cache_client = None
    if settings.cache_enabled and settings.secrets_encryption_key:
        cache_wrapper = get_cache_client()
        if cache_wrapper:
            base_cache_client = cache_wrapper.client

    return _create_vault_client(
        vault_type,
        hashicorp_addr=settings.secrets_hashicorp_vault_addr,
        hashicorp_token=settings.secrets_hashicorp_vault_token,
        azure_keyvault_url=settings.secrets_azure_keyvault_url,
        cache_client=base_cache_client,
    )


def get_app_service_vault() -> BaseVaultClient | None:
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

    vault_type = settings.app_vault_type or settings.vault_type
    if not vault_type:
        logger.info("No app service vault configured (vault_type not set)")
        return None

    logger.info("Initializing app service vault: %s", vault_type)

    # App service vault typically doesn't need caching as keys are long-lived
    _app_service_vault = _create_vault_client(
        vault_type,
        hashicorp_addr=settings.app_hashicorp_vault_addr,
        hashicorp_token=settings.app_hashicorp_vault_token,
        azure_keyvault_url=settings.app_azure_keyvault_url,
    )
    return _app_service_vault


def get_secrets_vault() -> BaseVaultClient | None:
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

    vault_type = settings.secrets_vault_type or settings.vault_type
    if not vault_type:
        logger.info("No secrets vault configured (vault_type not set)")
        return None

    logger.info("Initializing secrets vault: %s", vault_type)

    # Secrets vault can use caching for better performance
    base_cache_client = None
    if settings.cache_enabled and settings.secrets_encryption_key:
        cache_wrapper = get_cache_client()
        if cache_wrapper:
            base_cache_client = cache_wrapper.client

    _secrets_vault = _create_vault_client(
        vault_type,
        hashicorp_addr=settings.secrets_hashicorp_vault_addr,
        hashicorp_token=settings.secrets_hashicorp_vault_token,
        azure_keyvault_url=settings.secrets_azure_keyvault_url,
        cache_client=base_cache_client,
    )
    return _secrets_vault


def set_test_vault_client(vault_client: BaseVaultClient | None) -> None:
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
