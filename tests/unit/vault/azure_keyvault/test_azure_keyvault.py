"""Unit tests for aihub/vault/azure_keyvault/keyvault.py - AzureKeyVault."""
import pytest
from unittest.mock import Mock, MagicMock, patch
import os

from aihub.vault.azure_keyvault.keyvault import AzureKeyVault
from aihub.core.vault.vault import BaseVault


class TestAzureKeyVault:
    """Test suite for AzureKeyVault implementation."""
    
    @patch('aihub.vault.azure_keyvault.keyvault.SecretClient')
    @patch('aihub.vault.azure_keyvault.keyvault.DefaultAzureCredential')
    def test_initialization_with_vault_url(self, mock_credential, mock_secret_client):
        """Test initialization with explicit vault URL."""
        vault = AzureKeyVault(vault_url="https://test-vault.vault.azure.net/")
        
        assert vault.vault_url == "https://test-vault.vault.azure.net/"
        mock_credential.assert_called_once()
        mock_secret_client.assert_called_once()
    
    @patch.dict(os.environ, {"AZURE_KEYVAULT_URL": "https://env-vault.vault.azure.net/"})
    @patch('aihub.vault.azure_keyvault.keyvault.SecretClient')
    @patch('aihub.vault.azure_keyvault.keyvault.DefaultAzureCredential')
    def test_initialization_from_env(self, mock_credential, mock_secret_client):
        """Test initialization from environment variable."""
        vault = AzureKeyVault()
        
        assert vault.vault_url == "https://env-vault.vault.azure.net/"
    
    @patch('aihub.vault.azure_keyvault.keyvault.SecretClient')
    @patch('aihub.vault.azure_keyvault.keyvault.DefaultAzureCredential')
    def test_initialization_without_url_raises_error(self, mock_credential, mock_secret_client):
        """Test initialization without URL raises ValueError."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="AZURE_KEYVAULT_URL must be provided"):
                AzureKeyVault()
    
    @patch('aihub.vault.azure_keyvault.keyvault.SecretClient')
    @patch('aihub.vault.azure_keyvault.keyvault.DefaultAzureCredential')
    def test_is_base_vault_implementation(self, mock_credential, mock_secret_client):
        """Test that AzureKeyVault implements BaseVault."""
        vault = AzureKeyVault(vault_url="https://test.vault.azure.net/")
        assert isinstance(vault, BaseVault)
    
    @patch('aihub.vault.azure_keyvault.keyvault.SecretClient')
    @patch('aihub.vault.azure_keyvault.keyvault.DefaultAzureCredential')
    def test_store_secret(self, mock_credential, mock_secret_client_class):
        """Test storing a secret."""
        mock_client = Mock()
        mock_secret_client_class.return_value = mock_client
        
        mock_secret = Mock()
        mock_secret.name = "api-key"
        mock_secret.properties.version = "abc123"
        mock_client.set_secret.return_value = mock_secret
        
        vault = AzureKeyVault(vault_url="https://myvault.vault.azure.net/")
        uri = vault.store_secret("api_key", "secret-value-123")
        
        assert uri == "azurekv://myvault/api-key/abc123"
        mock_client.set_secret.assert_called_once_with("api-key", "secret-value-123", tags={})
    
    @patch('aihub.vault.azure_keyvault.keyvault.SecretClient')
    @patch('aihub.vault.azure_keyvault.keyvault.DefaultAzureCredential')
    def test_store_secret_with_metadata(self, mock_credential, mock_secret_client_class):
        """Test storing a secret with metadata."""
        mock_client = Mock()
        mock_secret_client_class.return_value = mock_client
        
        mock_secret = Mock()
        mock_secret.name = "db-password"
        mock_secret.properties.version = "v1"
        mock_client.set_secret.return_value = mock_secret
        
        vault = AzureKeyVault(vault_url="https://test.vault.azure.net/")
        metadata = {"env": "production", "owner": "admin"}
        uri = vault.store_secret("db_password", "secret123", metadata=metadata)
        
        mock_client.set_secret.assert_called_once_with("db-password", "secret123", tags=metadata)
    
    @patch('aihub.vault.azure_keyvault.keyvault.SecretClient')
    @patch('aihub.vault.azure_keyvault.keyvault.DefaultAzureCredential')
    def test_store_secret_normalizes_name(self, mock_credential, mock_secret_client_class):
        """Test that secret name is normalized (underscores to hyphens)."""
        mock_client = Mock()
        mock_secret_client_class.return_value = mock_client
        
        mock_secret = Mock()
        mock_secret.name = "my-api-key"
        mock_secret.properties.version = "v1"
        mock_client.set_secret.return_value = mock_secret
        
        vault = AzureKeyVault(vault_url="https://test.vault.azure.net/")
        vault.store_secret("my_api_key", "value")
        
        # Should replace underscores with hyphens
        mock_client.set_secret.assert_called_once_with("my-api-key", "value", tags={})
    
    @patch('aihub.vault.azure_keyvault.keyvault.SecretClient')
    @patch('aihub.vault.azure_keyvault.keyvault.DefaultAzureCredential')
    def test_get_secret(self, mock_credential, mock_secret_client_class):
        """Test retrieving a secret."""
        mock_client = Mock()
        mock_secret_client_class.return_value = mock_client
        
        mock_secret = Mock()
        mock_secret.value = "secret-value-123"
        mock_client.get_secret.return_value = mock_secret
        
        vault = AzureKeyVault(vault_url="https://test.vault.azure.net/")
        value = vault.get_secret("azurekv://myvault/api-key/abc123")
        
        assert value == "secret-value-123"
        mock_client.get_secret.assert_called_once_with("api-key", version="abc123")
    
    @patch('aihub.vault.azure_keyvault.keyvault.SecretClient')
    @patch('aihub.vault.azure_keyvault.keyvault.DefaultAzureCredential')
    def test_get_secret_without_version(self, mock_credential, mock_secret_client_class):
        """Test retrieving a secret without version (latest)."""
        mock_client = Mock()
        mock_secret_client_class.return_value = mock_client
        
        mock_secret = Mock()
        mock_secret.value = "latest-value"
        mock_client.get_secret.return_value = mock_secret
        
        vault = AzureKeyVault(vault_url="https://test.vault.azure.net/")
        value = vault.get_secret("azurekv://myvault/api-key")
        
        assert value == "latest-value"
        mock_client.get_secret.assert_called_once_with("api-key", version=None)
    
    @patch('aihub.vault.azure_keyvault.keyvault.SecretClient')
    @patch('aihub.vault.azure_keyvault.keyvault.DefaultAzureCredential')
    def test_get_secret_invalid_uri(self, mock_credential, mock_secret_client_class):
        """Test get_secret with invalid URI returns None."""
        mock_client = Mock()
        mock_secret_client_class.return_value = mock_client
        
        vault = AzureKeyVault(vault_url="https://test.vault.azure.net/")
        value = vault.get_secret("invalid-uri")
        
        assert value is None
        mock_client.get_secret.assert_not_called()
    
    @patch('aihub.vault.azure_keyvault.keyvault.SecretClient')
    @patch('aihub.vault.azure_keyvault.keyvault.DefaultAzureCredential')
    def test_get_secret_handles_error(self, mock_credential, mock_secret_client_class):
        """Test get_secret handles errors gracefully."""
        mock_client = Mock()
        mock_secret_client_class.return_value = mock_client
        mock_client.get_secret.side_effect = Exception("Secret not found")
        
        vault = AzureKeyVault(vault_url="https://test.vault.azure.net/")
        value = vault.get_secret("azurekv://myvault/missing/v1")
        
        assert value is None
    
    @patch('aihub.vault.azure_keyvault.keyvault.SecretClient')
    @patch('aihub.vault.azure_keyvault.keyvault.DefaultAzureCredential')
    def test_update_secret(self, mock_credential, mock_secret_client_class):
        """Test updating a secret."""
        mock_client = Mock()
        mock_secret_client_class.return_value = mock_client
        
        vault = AzureKeyVault(vault_url="https://test.vault.azure.net/")
        result = vault.update_secret("azurekv://myvault/api-key/v1", "new-value")
        
        assert result is True
        mock_client.set_secret.assert_called_once_with("api-key", "new-value", tags={})
    
    @patch('aihub.vault.azure_keyvault.keyvault.SecretClient')
    @patch('aihub.vault.azure_keyvault.keyvault.DefaultAzureCredential')
    def test_update_secret_with_metadata(self, mock_credential, mock_secret_client_class):
        """Test updating a secret with new metadata."""
        mock_client = Mock()
        mock_secret_client_class.return_value = mock_client
        
        vault = AzureKeyVault(vault_url="https://test.vault.azure.net/")
        metadata = {"updated": "true"}
        result = vault.update_secret("azurekv://myvault/key/v1", "value", metadata=metadata)
        
        assert result is True
        mock_client.set_secret.assert_called_once_with("key", "value", tags=metadata)
    
    @patch('aihub.vault.azure_keyvault.keyvault.SecretClient')
    @patch('aihub.vault.azure_keyvault.keyvault.DefaultAzureCredential')
    def test_update_secret_invalid_uri(self, mock_credential, mock_secret_client_class):
        """Test update_secret with invalid URI returns False."""
        mock_client = Mock()
        mock_secret_client_class.return_value = mock_client
        
        vault = AzureKeyVault(vault_url="https://test.vault.azure.net/")
        result = vault.update_secret("invalid", "value")
        
        assert result is False
        mock_client.set_secret.assert_not_called()
    
    @patch('aihub.vault.azure_keyvault.keyvault.SecretClient')
    @patch('aihub.vault.azure_keyvault.keyvault.DefaultAzureCredential')
    def test_delete_secret(self, mock_credential, mock_secret_client_class):
        """Test deleting a secret."""
        mock_client = Mock()
        mock_secret_client_class.return_value = mock_client
        mock_client.begin_delete_secret.return_value = Mock()
        
        vault = AzureKeyVault(vault_url="https://test.vault.azure.net/")
        result = vault.delete_secret("azurekv://myvault/api-key/v1")
        
        assert result is True
        mock_client.begin_delete_secret.assert_called_once_with("api-key")
    
    @patch('aihub.vault.azure_keyvault.keyvault.SecretClient')
    @patch('aihub.vault.azure_keyvault.keyvault.DefaultAzureCredential')
    def test_ping_success(self, mock_credential, mock_secret_client_class):
        """Test ping returns True when vault is accessible."""
        mock_client = Mock()
        mock_secret_client_class.return_value = mock_client
        mock_client.list_properties_of_secrets.return_value = iter([])
        
        vault = AzureKeyVault(vault_url="https://test.vault.azure.net/")
        result = vault.ping()
        
        assert result is True
    
    @patch('aihub.vault.azure_keyvault.keyvault.SecretClient')
    @patch('aihub.vault.azure_keyvault.keyvault.DefaultAzureCredential')
    def test_ping_failure(self, mock_credential, mock_secret_client_class):
        """Test ping returns False when vault is not accessible."""
        mock_client = Mock()
        mock_secret_client_class.return_value = mock_client
        mock_client.list_properties_of_secrets.side_effect = Exception("Connection error")
        
        vault = AzureKeyVault(vault_url="https://test.vault.azure.net/")
        result = vault.ping()
        
        assert result is False
