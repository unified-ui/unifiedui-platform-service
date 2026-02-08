"""Unit tests for unifiedui/handlers/dependencies/vault.py - Vault dependency."""
import pytest
from unittest.mock import patch, Mock

from unifiedui.handlers.dependencies.vault import get_vault_client


class TestGetVaultClient:
    """Test suite for get_vault_client dependency."""

    def teardown_method(self):
        """Reset global vault client and clear cache."""
        import unifiedui.handlers.dependencies.vault
        unifiedui.handlers.dependencies.vault._vault_client = None
        # Clear lru_cache
        get_vault_client.cache_clear()

    @patch('unifiedui.handlers.dependencies.vault.settings')
    def test_get_vault_client_no_vault_configured(self, mock_settings):
        """Test when no vault is configured."""
        mock_settings.vault_type = None
        
        result = get_vault_client()
        
        assert result is None

    @patch('unifiedui.handlers.dependencies.vault.settings')
    @patch('unifiedui.handlers.dependencies.vault.AzureKeyVaultClient')
    @patch('unifiedui.handlers.dependencies.vault.get_cache_client')
    def test_get_vault_client_azure_keyvault(self, mock_cache, mock_vault_class, mock_settings):
        """Test Azure KeyVault client initialization."""
        mock_settings.vault_type = "AZURE_KEYVAULT"
        mock_settings.secrets_azure_keyvault_url = "https://my-vault.vault.azure.net/"
        mock_settings.secrets_hashicorp_vault_addr = None
        mock_settings.secrets_hashicorp_vault_token = None
        mock_settings.cache_enabled = True
        mock_settings.secrets_encryption_key = "encryption-key"
        mock_cache_client = Mock()
        mock_cache.return_value = mock_cache_client
        mock_vault_instance = Mock()
        mock_vault_class.return_value = mock_vault_instance
        
        result = get_vault_client()
        
        assert result is mock_vault_instance
        mock_vault_class.assert_called_once_with(
            vault_url="https://my-vault.vault.azure.net/",
            cache_client=mock_cache_client
        )

    @patch('unifiedui.handlers.dependencies.vault.settings')
    @patch('unifiedui.handlers.dependencies.vault.AzureKeyVaultClient')
    def test_get_vault_client_azure_keyvault_no_cache(self, mock_vault_class, mock_settings):
        """Test Azure KeyVault without caching."""
        mock_settings.vault_type = "azure_keyvault"  # Test case-insensitive
        mock_settings.secrets_azure_keyvault_url = "https://test-vault.vault.azure.net/"
        mock_settings.secrets_hashicorp_vault_addr = None
        mock_settings.secrets_hashicorp_vault_token = None
        mock_settings.cache_enabled = False
        mock_vault_instance = Mock()
        mock_vault_class.return_value = mock_vault_instance
        
        result = get_vault_client()
        
        assert result is mock_vault_instance
        mock_vault_class.assert_called_once_with(
            vault_url="https://test-vault.vault.azure.net/",
            cache_client=None
        )

    @patch('unifiedui.handlers.dependencies.vault.settings')
    def test_get_vault_client_azure_keyvault_missing_url(self, mock_settings):
        """Test Azure KeyVault without URL raises error."""
        mock_settings.vault_type = "AZURE_KEYVAULT"
        mock_settings.secrets_azure_keyvault_url = None
        mock_settings.secrets_hashicorp_vault_addr = None
        mock_settings.secrets_hashicorp_vault_token = None
        mock_settings.cache_enabled = False
        
        with pytest.raises(RuntimeError) as exc_info:
            get_vault_client()
        
        assert "Azure KeyVault URL must be set" in str(exc_info.value)

    @patch('unifiedui.handlers.dependencies.vault.settings')
    @patch('unifiedui.handlers.dependencies.vault.HashiCorpVaultClient')
    @patch('unifiedui.handlers.dependencies.vault.get_cache_client')
    def test_get_vault_client_hashicorp(self, mock_cache, mock_vault_class, mock_settings):
        """Test HashiCorp Vault client initialization."""
        mock_settings.vault_type = "HASHICORP_VAULT"
        mock_settings.secrets_hashicorp_vault_addr = "http://vault.example.com:8200"
        mock_settings.secrets_hashicorp_vault_token = "test-token"
        mock_settings.secrets_azure_keyvault_url = None
        mock_settings.cache_enabled = True
        mock_settings.secrets_encryption_key = "key"
        mock_cache_client = Mock()
        mock_cache.return_value = mock_cache_client
        mock_vault_instance = Mock()
        mock_vault_class.return_value = mock_vault_instance
        
        result = get_vault_client()
        
        assert result is mock_vault_instance
        mock_vault_class.assert_called_once_with(
            url="http://vault.example.com:8200",
            token="test-token",
            cache_client=mock_cache_client
        )

    @patch('unifiedui.handlers.dependencies.vault.settings')
    def test_get_vault_client_hashicorp_missing_addr(self, mock_settings):
        """Test HashiCorp Vault without address raises error."""
        mock_settings.vault_type = "hashicorp_vault"  # Test case-insensitive
        mock_settings.secrets_hashicorp_vault_addr = None
        mock_settings.secrets_hashicorp_vault_token = None
        mock_settings.secrets_azure_keyvault_url = None
        mock_settings.cache_enabled = False
        
        with pytest.raises(RuntimeError) as exc_info:
            get_vault_client()
        
        assert "HashiCorp Vault address must be set" in str(exc_info.value)

    @patch('unifiedui.handlers.dependencies.vault.settings')
    def test_get_vault_client_unsupported_type(self, mock_settings):
        """Test unsupported vault type raises error."""
        mock_settings.vault_type = "UNKNOWN_VAULT"
        mock_settings.secrets_hashicorp_vault_addr = None
        mock_settings.secrets_hashicorp_vault_token = None
        mock_settings.secrets_azure_keyvault_url = None
        mock_settings.cache_enabled = False
        
        with pytest.raises(RuntimeError) as exc_info:
            get_vault_client()
        
        assert "Unsupported vault type" in str(exc_info.value)
        assert "UNKNOWN_VAULT" in str(exc_info.value)

    @patch('unifiedui.handlers.dependencies.vault.settings')
    @patch('unifiedui.handlers.dependencies.vault.AzureKeyVaultClient')
    def test_get_vault_client_cached(self, mock_vault_class, mock_settings):
        """Test that vault client is cached (lru_cache)."""
        mock_settings.vault_type = "AZURE_KEYVAULT"
        mock_settings.secrets_azure_keyvault_url = "https://vault.vault.azure.net/"
        mock_settings.secrets_hashicorp_vault_addr = None
        mock_settings.secrets_hashicorp_vault_token = None
        mock_settings.cache_enabled = False
        mock_vault_instance = Mock()
        mock_vault_class.return_value = mock_vault_instance
        
        result1 = get_vault_client()
        result2 = get_vault_client()
        
        # Due to lru_cache, should return same instance
        assert result1 is result2
        # Vault class should only be called once
        assert mock_vault_class.call_count == 1

    @patch('unifiedui.handlers.dependencies.vault.settings')
    @patch('unifiedui.handlers.dependencies.vault.AzureKeyVaultClient')
    def test_get_vault_client_test_vault_client_set(self, mock_vault_class, mock_settings):
        """Test that test vault client is returned when set."""
        import unifiedui.handlers.dependencies.vault
        test_client = Mock()
        unifiedui.handlers.dependencies.vault._vault_client = test_client
        
        result = get_vault_client()
        
        assert result is test_client
        # Settings should not be accessed when test client is set
        mock_vault_class.assert_not_called()
