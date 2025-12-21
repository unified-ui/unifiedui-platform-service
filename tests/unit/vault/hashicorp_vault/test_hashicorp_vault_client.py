"""Unit tests for aihub/vault/hashicorp_vault/client.py - HashiCorpVaultClient."""
import pytest
from unittest.mock import Mock, patch

from aihub.vault.hashicorp_vault.client import HashiCorpVaultClient
from aihub.core.vault.client import BaseVaultClient


class TestHashiCorpVaultClient:
    """Test suite for HashiCorpVaultClient."""
    
    @patch('aihub.vault.hashicorp_vault.client.HashiCorpVault')
    def test_initialization(self, mock_vault_class):
        """Test client initialization."""
        mock_vault = Mock()
        mock_vault_class.return_value = mock_vault
        
        client = HashiCorpVaultClient(
            url="http://localhost:8200",
            token="test-token",
            mount_point="kv"
        )
        
        mock_vault_class.assert_called_once_with(
            url="http://localhost:8200",
            token="test-token",
            mount_point="kv"
        )
        assert client._vault is mock_vault
    
    @patch('aihub.vault.hashicorp_vault.client.HashiCorpVault')
    def test_initialization_with_defaults(self, mock_vault_class):
        """Test initialization with default mount point."""
        mock_vault = Mock()
        mock_vault_class.return_value = mock_vault
        
        client = HashiCorpVaultClient(url="http://localhost:8200", token="token")
        
        # Default mount_point is "secret"
        call_kwargs = mock_vault_class.call_args[1]
        assert call_kwargs['mount_point'] == "secret"
    
    @patch('aihub.vault.hashicorp_vault.client.HashiCorpVault')
    def test_is_base_vault_client(self, mock_vault_class):
        """Test that HashiCorpVaultClient extends BaseVaultClient."""
        client = HashiCorpVaultClient(url="http://localhost:8200", token="token")
        assert isinstance(client, BaseVaultClient)
    
    @patch('aihub.vault.hashicorp_vault.client.HashiCorpVault')
    def test_get_vault(self, mock_vault_class):
        """Test get_vault returns the vault instance."""
        mock_vault = Mock()
        mock_vault_class.return_value = mock_vault
        
        client = HashiCorpVaultClient(url="http://localhost:8200", token="token")
        vault = client.get_vault()
        
        assert vault is mock_vault
    
    @patch('aihub.vault.hashicorp_vault.client.HashiCorpVault')
    def test_with_cache_client(self, mock_vault_class):
        """Test initialization with cache client."""
        mock_vault = Mock()
        mock_vault_class.return_value = mock_vault
        mock_cache = Mock()
        
        client = HashiCorpVaultClient(
            url="http://localhost:8200",
            token="token",
            cache_client=mock_cache
        )
        
        assert client.cache_client is mock_cache
