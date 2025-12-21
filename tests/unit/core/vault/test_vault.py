"""Unit tests for aihub/core/vault/vault.py - BaseVault abstract class."""
import pytest
from abc import ABC

from aihub.core.vault.vault import BaseVault


class MockVault(BaseVault):
    """Mock implementation of BaseVault for testing."""
    
    def __init__(self):
        self.secrets = {}
        self.counter = 0
    
    def store_secret(self, key: str, value: str, metadata=None) -> str:
        uri = f"vault://secrets/{key}/{self.counter}"
        self.secrets[uri] = {"value": value, "metadata": metadata}
        self.counter += 1
        return uri
    
    def get_secret(self, uri: str):
        if uri in self.secrets:
            return self.secrets[uri]["value"]
        return None
    
    def update_secret(self, uri: str, value: str, metadata=None) -> bool:
        if uri in self.secrets:
            self.secrets[uri]["value"] = value
            if metadata:
                self.secrets[uri]["metadata"] = metadata
            return True
        return False
    
    def delete_secret(self, uri: str) -> bool:
        if uri in self.secrets:
            del self.secrets[uri]
            return True
        return False
    
    def ping(self) -> bool:
        return True
    
    def close(self) -> None:
        pass


class TestBaseVault:
    """Test suite for BaseVault abstract base class."""
    
    def test_is_abstract_class(self):
        """Test that BaseVault is an abstract class."""
        assert issubclass(BaseVault, ABC)
    
    def test_cannot_instantiate_base_class(self):
        """Test that BaseVault cannot be instantiated directly."""
        with pytest.raises(TypeError):
            BaseVault()
    
    def test_has_store_secret_method(self):
        """Test that BaseVault defines store_secret abstract method."""
        assert hasattr(BaseVault, 'store_secret')
        assert callable(getattr(BaseVault, 'store_secret'))
    
    def test_has_get_secret_method(self):
        """Test that BaseVault defines get_secret abstract method."""
        assert hasattr(BaseVault, 'get_secret')
        assert callable(getattr(BaseVault, 'get_secret'))
    
    def test_has_update_secret_method(self):
        """Test that BaseVault defines update_secret abstract method."""
        assert hasattr(BaseVault, 'update_secret')
        assert callable(getattr(BaseVault, 'update_secret'))
    
    def test_has_delete_secret_method(self):
        """Test that BaseVault defines delete_secret abstract method."""
        assert hasattr(BaseVault, 'delete_secret')
        assert callable(getattr(BaseVault, 'delete_secret'))
    
    def test_has_ping_method(self):
        """Test that BaseVault defines ping abstract method."""
        assert hasattr(BaseVault, 'ping')
        assert callable(getattr(BaseVault, 'ping'))
    
    def test_has_close_method(self):
        """Test that BaseVault defines close abstract method."""
        assert hasattr(BaseVault, 'close')
        assert callable(getattr(BaseVault, 'close'))


class TestMockVaultImplementation:
    """Test suite for MockVault implementation to verify interface."""
    
    def test_ctore_and_get_secret(self):
        """Test storing and retrieving a secret."""
        vault = MockVault()
        uri = vault.store_secret("api_key", "secret-value-123")
        result = vault.get_secret(uri)
        assert result == "secret-value-123"
        assert uri.startswith("vault://secrets/")
    
    def test_store_secret_with_metadata(self):
        """Test storing secret with metadata."""
        vault = MockVault()
        metadata = {"owner": "admin", "env": "production"}
        uri = vault.store_secret("db_password", "secret123", metadata=metadata)
        assert uri is not None
        assert vault.get_secret(uri) == "secret123"
    
    def test_get_nonexistent_secret_returns_none(self):
        """Test getting non-existent secret returns None."""
        vault = MockVault()
        result = vault.get_secret("vault://secrets/nonexistent/0")
        assert result is None
    
    def test_update_existing_secret(self):
        """Test updating an existing secret."""
        vault = MockVault()
        uri = vault.store_secret("key1", "old_value")
        result = vault.update_secret(uri, "new_value")
        assert result is True
        assert vault.get_secret(uri) == "new_value"
    
    def test_update_nonexistent_secret(self):
        """Test updating non-existent secret returns False."""
        vault = MockVault()
        result = vault.update_secret("vault://secrets/nonexistent/0", "value")
        assert result is False
    
    def test_update_secret_with_metadata(self):
        """Test updating secret with new metadata."""
        vault = MockVault()
        uri = vault.store_secret("key1", "value1", metadata={"env": "dev"})
        result = vault.update_secret(uri, "value2", metadata={"env": "prod"})
        assert result is True
        assert vault.get_secret(uri) == "value2"
    
    def test_delete_existing_secret(self):
        """Test deleting an existing secret."""
        vault = MockVault()
        uri = vault.store_secret("temp_key", "temp_value")
        result = vault.delete_secret(uri)
        assert result is True
        assert vault.get_secret(uri) is None
    
    def test_delete_nonexistent_secret(self):
        """Test deleting non-existent secret returns False."""
        vault = MockVault()
        result = vault.delete_secret("vault://secrets/nonexistent/0")
        assert result is False
    
    def test_ping_returns_true(self):
        """Test ping returns True when vault is accessible."""
        vault = MockVault()
        assert vault.ping() is True
    
    def test_multiple_secrets(self):
        """Test managing multiple secrets."""
        vault = MockVault()
        uri1 = vault.store_secret("key1", "value1")
        uri2 = vault.store_secret("key2", "value2")
        uri3 = vault.store_secret("key3", "value3")
        
        assert vault.get_secret(uri1) == "value1"
        assert vault.get_secret(uri2) == "value2"
        assert vault.get_secret(uri3) == "value3"
    
    def test_unique_uris(self):
        """Test that each stored secret gets a unique URI."""
        vault = MockVault()
        uri1 = vault.store_secret("key1", "value1")
        uri2 = vault.store_secret("key1", "value2")
        
        assert uri1 != uri2
        assert vault.get_secret(uri1) == "value1"
        assert vault.get_secret(uri2) == "value2"
