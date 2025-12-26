"""Abstract base class for vault implementations."""
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any


class BaseVault(ABC):
    """Abstract base class for vault/secrets management."""

    @abstractmethod
    def store_secret(
        self,
        key: str,
        value: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Store a secret in the vault.
        
        Args:
            key: Secret key/name
            value: Secret value to store
            metadata: Optional metadata about the secret
            
        Returns:
            URI/reference to the stored secret
        """
        pass

    @abstractmethod
    def get_secret(self, uri: str) -> Optional[str]:
        """
        Retrieve a secret from the vault.
        
        Args:
            uri: URI/reference to the secret
            
        Returns:
            Secret value or None if not found
        """
        pass

    @abstractmethod
    def update_secret(
        self,
        uri: str,
        value: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Update an existing secret.
        
        Args:
            uri: URI/reference to the secret
            value: New secret value
            metadata: Optional metadata update
            
        Returns:
            True if updated successfully, False otherwise
        """
        pass

    @abstractmethod
    def delete_secret(self, uri: str) -> bool:
        """
        Delete a secret from the vault.
        
        Args:
            uri: URI/reference to the secret
            
        Returns:
            True if deleted successfully, False otherwise
        """
        pass

    @abstractmethod
    def ping(self) -> bool:
        """
        Check if vault connection is alive.
        
        Returns:
            True if connected, False otherwise
        """
        pass

    @abstractmethod
    def close(self) -> None:
        """Close vault connection."""
        pass
