"""Unit tests for unifiedui/vault/azure_keyvault/client.py - AzureKeyVaultClient."""

from unittest.mock import Mock, patch

from unifiedui.core.vault.client import BaseVaultClient
from unifiedui.vault.azure_keyvault.client import AzureKeyVaultClient


class TestAzureKeyVaultClient:
    """Test suite for AzureKeyVaultClient."""

    @patch("unifiedui.vault.azure_keyvault.client.AzureKeyVault")
    def test_initialization(self, mock_vault_class):
        """Test client initialization."""
        mock_vault = Mock()
        mock_vault_class.return_value = mock_vault

        client = AzureKeyVaultClient(vault_url="https://test.vault.azure.net/")

        mock_vault_class.assert_called_once_with(vault_url="https://test.vault.azure.net/")
        assert client._vault is mock_vault

    @patch("unifiedui.vault.azure_keyvault.client.AzureKeyVault")
    def test_is_base_vault_client(self, mock_vault_class):
        """Test that AzureKeyVaultClient extends BaseVaultClient."""
        client = AzureKeyVaultClient(vault_url="https://test.vault.azure.net/")
        assert isinstance(client, BaseVaultClient)

    @patch("unifiedui.vault.azure_keyvault.client.AzureKeyVault")
    def test_get_vault(self, mock_vault_class):
        """Test get_vault returns the vault instance."""
        mock_vault = Mock()
        mock_vault_class.return_value = mock_vault

        client = AzureKeyVaultClient(vault_url="https://test.vault.azure.net/")
        vault = client.get_vault()

        assert vault is mock_vault

    @patch("unifiedui.vault.azure_keyvault.client.AzureKeyVault")
    def test_with_cache_client(self, mock_vault_class):
        """Test initialization with cache client."""
        mock_vault = Mock()
        mock_vault_class.return_value = mock_vault
        mock_cache = Mock()

        client = AzureKeyVaultClient(vault_url="https://test.vault.azure.net/", cache_client=mock_cache)

        assert client.cache_client is mock_cache
