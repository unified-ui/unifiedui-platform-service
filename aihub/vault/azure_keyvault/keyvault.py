"""Azure Key Vault implementation."""
import os
from typing import Optional, Dict, Any
from azure.keyvault.secrets import SecretClient
from azure.identity import DefaultAzureCredential

from aihub.core.vault.vault import BaseVault
from aihub.logger import get_logger

logger = get_logger(__name__)


class AzureKeyVault(BaseVault):
    """Azure Key Vault implementation."""

    def __init__(self, vault_url: Optional[str] = None):
        """
        Initialize Azure Key Vault client.
        
        Args:
            vault_url: Azure Key Vault URL (e.g., https://myvault.vault.azure.net/)
        """
        self.vault_url = vault_url or os.getenv("AZURE_KEYVAULT_URL")
        if not self.vault_url:
            raise ValueError("AZURE_KEYVAULT_URL must be provided or set in environment")
        
        try:
            credential = DefaultAzureCredential()
            self.client = SecretClient(vault_url=self.vault_url, credential=credential)
            logger.info(f"Azure Key Vault initialized: {self.vault_url}")
        except Exception as e:
            logger.error(f"Failed to initialize Azure Key Vault: {e}")
            raise

    def store_secret(
        self,
        key: str,
        value: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Store a secret in Azure Key Vault."""
        try:
            # Azure Key Vault secret names must match ^[0-9a-zA-Z-]+$
            secret_name = key.replace("_", "-").replace(".", "-")
            
            # Set secret with optional tags as metadata
            tags = metadata if metadata else {}
            secret = self.client.set_secret(secret_name, value, tags=tags)
            
            # Return URI as reference
            uri = f"azurekv://{self.vault_url.split('//')[1].split('.')[0]}/{secret.name}/{secret.properties.version}"
            logger.info(f"Stored secret in Azure Key Vault: {secret_name}")
            return uri
        except Exception as e:
            logger.error(f"Failed to store secret in Azure Key Vault: {e}")
            raise

    def get_secret(self, uri: str) -> Optional[str]:
        """Retrieve a secret from Azure Key Vault."""
        try:
            # Parse URI: azurekv://vaultname/secretname/version
            parts = uri.replace("azurekv://", "").split("/")
            if len(parts) < 2:
                logger.error(f"Invalid Azure Key Vault URI: {uri}")
                return None
            
            secret_name = parts[1]
            version = parts[2] if len(parts) > 2 else None
            
            secret = self.client.get_secret(secret_name, version=version)
            logger.debug(f"Retrieved secret from Azure Key Vault: {secret_name}")
            return secret.value
        except Exception as e:
            logger.error(f"Failed to get secret from Azure Key Vault: {e}")
            return None

    def update_secret(
        self,
        uri: str,
        value: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Update a secret in Azure Key Vault."""
        try:
            parts = uri.replace("azurekv://", "").split("/")
            if len(parts) < 2:
                logger.error(f"Invalid Azure Key Vault URI: {uri}")
                return False
            
            secret_name = parts[1]
            tags = metadata if metadata else {}
            
            self.client.set_secret(secret_name, value, tags=tags)
            logger.info(f"Updated secret in Azure Key Vault: {secret_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to update secret in Azure Key Vault: {e}")
            return False

    def delete_secret(self, uri: str) -> bool:
        """Delete a secret from Azure Key Vault."""
        try:
            parts = uri.replace("azurekv://", "").split("/")
            if len(parts) < 2:
                logger.error(f"Invalid Azure Key Vault URI: {uri}")
                return False
            
            secret_name = parts[1]
            
            # Begin delete operation (soft delete)
            poller = self.client.begin_delete_secret(secret_name)
            poller.wait()
            
            logger.info(f"Deleted secret from Azure Key Vault: {secret_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete secret from Azure Key Vault: {e}")
            return False

    def ping(self) -> bool:
        """Check if Azure Key Vault connection is alive."""
        try:
            # Try to list secrets (limited to 1)
            secrets = self.client.list_properties_of_secrets(max_page_size=1)
            list(secrets)  # Force evaluation
            return True
        except Exception as e:
            logger.error(f"Azure Key Vault ping failed: {e}")
            return False

    def close(self) -> None:
        """Close Azure Key Vault connection."""
        try:
            self.client.close()
            logger.info("Azure Key Vault connection closed")
        except Exception as e:
            logger.error(f"Failed to close Azure Key Vault: {e}")
