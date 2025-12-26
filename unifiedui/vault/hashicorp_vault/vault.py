"""HashiCorp Vault implementation."""
import os
from typing import Optional, Dict, Any
import hvac

from unifiedui.core.vault.vault import BaseVault
from unifiedui.logger import get_logger

logger = get_logger(__name__)


class HashiCorpVault(BaseVault):
    """HashiCorp Vault implementation."""

    def __init__(
        self,
        url: Optional[str] = None,
        token: Optional[str] = None,
        mount_point: str = "secret"
    ):
        """
        Initialize HashiCorp Vault client.
        
        Args:
            url: Vault server URL (e.g., http://localhost:8200)
            token: Vault authentication token
            mount_point: KV secrets engine mount point (default: secret)
        """
        self.url = url or os.getenv("VAULT_ADDR", "http://localhost:8200")
        self.token = token or os.getenv("VAULT_TOKEN")
        self.mount_point = mount_point
        
        if not self.token:
            raise ValueError("VAULT_TOKEN must be provided or set in environment")
        
        try:
            self.client = hvac.Client(url=self.url, token=self.token)
            
            if not self.client.is_authenticated():
                raise ValueError("Failed to authenticate with HashiCorp Vault")
            
            logger.info(f"HashiCorp Vault initialized: {self.url}")
        except Exception as e:
            logger.error(f"Failed to initialize HashiCorp Vault: {e}")
            raise

    def store_secret(
        self,
        key: str,
        value: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Store a secret in HashiCorp Vault."""
        try:
            # Prepare secret data
            secret_data = {"value": value}
            if metadata:
                secret_data["metadata"] = metadata
            
            # Store in KV v2
            self.client.secrets.kv.v2.create_or_update_secret(
                path=key,
                secret=secret_data,
                mount_point=self.mount_point
            )
            
            # Return URI as reference
            uri = f"vault://{self.url.split('//')[1]}/{self.mount_point}/{key}"
            logger.info(f"Stored secret in HashiCorp Vault: {key}")
            return uri
        except Exception as e:
            logger.error(f"Failed to store secret in HashiCorp Vault: {e}")
            raise

    def get_secret(self, uri: str) -> Optional[str]:
        """Retrieve a secret from HashiCorp Vault."""
        try:
            # Parse URI: vault://host/mount_point/path
            parts = uri.replace("vault://", "").split("/", 2)
            if len(parts) < 3:
                logger.error(f"Invalid HashiCorp Vault URI: {uri}")
                return None
            
            mount = parts[1]
            path = parts[2]
            
            response = self.client.secrets.kv.v2.read_secret_version(
                path=path,
                mount_point=mount
            )
            
            secret_value = response["data"]["data"].get("value")
            logger.debug(f"Retrieved secret from HashiCorp Vault: {path}")
            return secret_value
        except Exception as e:
            logger.error(f"Failed to get secret from HashiCorp Vault: {e}")
            return None

    def update_secret(
        self,
        uri: str,
        value: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Update a secret in HashiCorp Vault."""
        try:
            parts = uri.replace("vault://", "").split("/", 2)
            if len(parts) < 3:
                logger.error(f"Invalid HashiCorp Vault URI: {uri}")
                return False
            
            mount = parts[1]
            path = parts[2]
            
            secret_data = {"value": value}
            if metadata:
                secret_data["metadata"] = metadata
            
            self.client.secrets.kv.v2.create_or_update_secret(
                path=path,
                secret=secret_data,
                mount_point=mount
            )
            
            logger.info(f"Updated secret in HashiCorp Vault: {path}")
            return True
        except Exception as e:
            logger.error(f"Failed to update secret in HashiCorp Vault: {e}")
            return False

    def delete_secret(self, uri: str) -> bool:
        """Delete a secret from HashiCorp Vault."""
        try:
            parts = uri.replace("vault://", "").split("/", 2)
            if len(parts) < 3:
                logger.error(f"Invalid HashiCorp Vault URI: {uri}")
                return False
            
            mount = parts[1]
            path = parts[2]
            
            # Delete latest version
            self.client.secrets.kv.v2.delete_latest_version_of_secret(
                path=path,
                mount_point=mount
            )
            
            logger.info(f"Deleted secret from HashiCorp Vault: {path}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete secret from HashiCorp Vault: {e}")
            return False

    def ping(self) -> bool:
        """Check if HashiCorp Vault connection is alive."""
        try:
            return self.client.is_authenticated()
        except Exception as e:
            logger.error(f"HashiCorp Vault ping failed: {e}")
            return False

    def close(self) -> None:
        """Close HashiCorp Vault connection."""
        # hvac client doesn't require explicit close
        logger.info("HashiCorp Vault connection closed")
