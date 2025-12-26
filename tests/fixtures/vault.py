"""Vault-related test fixtures."""
import pytest
from typing import Dict, Optional
from unittest.mock import Mock

from unifiedui.core.vault.client import BaseVaultClient
from unifiedui.core.vault.vault import BaseVault


class MockVault(BaseVault):
    """Mock vault for testing."""
    
    def __init__(self):
        """Initialize mock vault with in-memory storage."""
        self._secrets: Dict[str, str] = {}
    
    def store_secret(self, key: str, value: str, metadata: Optional[Dict] = None) -> str:
        """
        Store a secret in memory.
        
        Args:
            key: Secret key/name
            value: Secret value to store
            metadata: Optional metadata (ignored in mock)
            
        Returns:
            Secret URI
        """
        self._secrets[key] = value
        return f"mock://{key}"
    
    def get_secret(self, uri: str) -> Optional[str]:
        """
        Retrieve a secret from memory.
        
        Args:
            uri: URI/reference to the secret
            
        Returns:
            Secret value or None if not found
        """
        # Extract key from URI (mock://key -> key)
        key = uri.replace("mock://", "")
        return self._secrets.get(key)
    
    def update_secret(self, uri: str, value: str, metadata: Optional[Dict] = None) -> bool:
        """
        Update a secret in memory.
        
        Args:
            uri: URI/reference to the secret
            value: New secret value
            metadata: Optional metadata (ignored in mock)
            
        Returns:
            True if updated successfully
        """
        key = uri.replace("mock://", "")
        if key not in self._secrets:
            return False
        self._secrets[key] = value
        return True
    
    def delete_secret(self, uri: str) -> bool:
        """
        Delete a secret from memory.
        
        Args:
            uri: URI/reference to the secret
            
        Returns:
            True if deleted successfully
        """
        key = uri.replace("mock://", "")
        if key in self._secrets:
            del self._secrets[key]
            return True
        return False
    
    def ping(self) -> bool:
        """
        Check if vault connection is alive.
        
        Returns:
            Always True for mock vault
        """
        return True
    
    def close(self) -> None:
        """Close vault connection (no-op for mock)."""
        pass
    
    def list_secrets(self) -> list:
        """
        List all secret names.
        
        Returns:
            List of secret names
        """
        return list(self._secrets.keys())


class MockVaultClient(BaseVaultClient):
    """Mock vault client for testing."""
    
    def __init__(self, cache_client: Optional[any] = None):
        """Initialize mock vault client."""
        super().__init__(cache_client)
        self._vault = MockVault()
    
    def get_vault(self) -> BaseVault:
        """
        Get the mock vault instance.
        
        Returns:
            MockVault instance
        """
        return self._vault


@pytest.fixture(scope="function")
def mock_vault_client() -> MockVaultClient:
    """Create a mock vault client for testing."""
    return MockVaultClient()
