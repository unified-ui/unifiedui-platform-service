"""DotEnv vault implementation for local development."""

import os
import threading
from typing import Any

from unifiedui.core.vault.vault import BaseVault
from unifiedui.logger import get_logger

logger = get_logger(__name__)


class DotEnvVault(BaseVault):
    """
    DotEnv-based vault implementation using environment variables.

    Primarily intended for local development and testing. Reads secrets
    from environment variables and stores runtime secrets in memory.

    URI format: dotenv://{key}
    """

    def __init__(self):
        """Initialize DotEnv vault with in-memory secret storage."""
        self._secrets: dict[str, str] = {}
        self._lock = threading.RLock()
        logger.info("DotEnv vault initialized (development mode)")

    def store_secret(self, key: str, value: str, metadata: dict[str, Any] | None = None) -> str:
        """
        Store a secret in memory.

        Note: Secrets stored via this method are only persisted in memory
        and will be lost when the application restarts.

        Args:
            key: Secret key/name
            value: Secret value to store
            metadata: Optional metadata (ignored for DotEnv vault)

        Returns:
            URI in the format "dotenv://{key}"
        """
        with self._lock:
            self._secrets[key] = value
            uri = f"dotenv://{key}"
            logger.debug("Stored secret in DotEnv vault: %s", key)
            return uri

    def build_secret_uri(self, key_name: str) -> str:
        """Build a dotenv URI for the given key name."""
        return f"dotenv://{key_name}"

    def get_secret(self, uri: str) -> str | None:
        """
        Retrieve a secret from environment variables or in-memory store.

        First checks environment variables, then falls back to in-memory store.

        Args:
            uri: URI in format "dotenv://{key}"

        Returns:
            Secret value or None if not found
        """
        key = uri.replace("dotenv://", "")

        # First check environment variables
        value = os.getenv(key)
        if value:
            logger.debug("Retrieved secret from environment: %s", key)
            return value

        # Then check in-memory store
        with self._lock:
            value = self._secrets.get(key)
            if value:
                logger.debug("Retrieved secret from in-memory store: %s", key)
                return value

        logger.warning("Secret not found: %s", key)
        return None

    def update_secret(self, uri: str, value: str, metadata: dict[str, Any] | None = None) -> bool:
        """
        Update a secret in memory.

        Note: Cannot update environment variables; only in-memory secrets
        can be updated.

        Args:
            uri: URI in format "dotenv://{key}"
            value: New secret value
            metadata: Optional metadata (ignored)

        Returns:
            True if updated successfully
        """
        key = uri.replace("dotenv://", "")

        with self._lock:
            self._secrets[key] = value
            logger.debug("Updated secret in DotEnv vault: %s", key)
            return True

    def delete_secret(self, uri: str) -> bool:
        """
        Delete a secret from in-memory store.

        Note: Cannot delete environment variables; only in-memory secrets
        can be deleted.

        Args:
            uri: URI in format "dotenv://{key}"

        Returns:
            True if deleted, False if not found
        """
        key = uri.replace("dotenv://", "")

        with self._lock:
            if key in self._secrets:
                del self._secrets[key]
                logger.debug("Deleted secret from DotEnv vault: %s", key)
                return True

            logger.debug("Secret not found for deletion: %s", key)
            return False

    def ping(self) -> bool:
        """
        Check if vault is available.

        Always returns True for DotEnv vault as it doesn't require
        external connections.
        """
        return True

    def close(self) -> None:
        """Close vault connection (no-op for DotEnv)."""
        pass
