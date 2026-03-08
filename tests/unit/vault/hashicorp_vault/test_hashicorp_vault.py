"""Unit tests for unifiedui/vault/hashicorp_vault/vault.py - HashiCorpVault."""

import os
from unittest.mock import Mock, patch

import pytest

from unifiedui.core.vault.vault import BaseVault
from unifiedui.vault.hashicorp_vault.vault import HashiCorpVault


class TestHashiCorpVault:
    """Test suite for HashiCorpVault implementation."""

    @patch("unifiedui.vault.hashicorp_vault.vault.hvac.Client")
    def test_initialization_with_params(self, mock_client_class):
        """Test initialization with explicit parameters."""
        mock_client = Mock()
        mock_client.is_authenticated.return_value = True
        mock_client_class.return_value = mock_client

        vault = HashiCorpVault(url="http://vault.example.com:8200", token="test-token-123", mount_point="custom")

        assert vault.url == "http://vault.example.com:8200"
        assert vault.token == "test-token-123"
        assert vault.mount_point == "custom"
        mock_client_class.assert_called_once_with(url="http://vault.example.com:8200", token="test-token-123")

    @patch.dict(os.environ, {"VAULT_ADDR": "http://env-vault:8200", "VAULT_TOKEN": "env-token"})
    @patch("unifiedui.vault.hashicorp_vault.vault.hvac.Client")
    def test_initialization_from_env(self, mock_client_class):
        """Test initialization from environment variables."""
        mock_client = Mock()
        mock_client.is_authenticated.return_value = True
        mock_client_class.return_value = mock_client

        vault = HashiCorpVault()

        assert vault.url == "http://env-vault:8200"
        assert vault.token == "env-token"

    @patch("unifiedui.vault.hashicorp_vault.vault.hvac.Client")
    def test_initialization_without_token_raises_error(self, mock_client_class):
        """Test initialization without token raises ValueError."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="VAULT_TOKEN must be provided"):
                HashiCorpVault(url="http://localhost:8200")

    @patch("unifiedui.vault.hashicorp_vault.vault.hvac.Client")
    def test_initialization_authentication_fails(self, mock_client_class):
        """Test initialization fails when authentication fails."""
        mock_client = Mock()
        mock_client.is_authenticated.return_value = False
        mock_client_class.return_value = mock_client

        with pytest.raises(ValueError, match="Failed to authenticate"):
            HashiCorpVault(url="http://localhost:8200", token="invalid-token")

    @patch("unifiedui.vault.hashicorp_vault.vault.hvac.Client")
    def test_is_base_vault_implementation(self, mock_client_class):
        """Test that HashiCorpVault implements BaseVault."""
        mock_client = Mock()
        mock_client.is_authenticated.return_value = True
        mock_client_class.return_value = mock_client

        vault = HashiCorpVault(url="http://localhost:8200", token="token")
        assert isinstance(vault, BaseVault)

    @patch("unifiedui.vault.hashicorp_vault.vault.hvac.Client")
    def test_store_secret(self, mock_client_class):
        """Test storing a secret."""
        mock_client = Mock()
        mock_client.is_authenticated.return_value = True
        mock_client_class.return_value = mock_client

        vault = HashiCorpVault(url="http://localhost:8200", token="token")
        uri = vault.store_secret("my/api/key", "secret-value-123")

        assert uri == "vault://localhost:8200/secret/my/api/key"
        mock_client.secrets.kv.v2.create_or_update_secret.assert_called_once_with(
            path="my/api/key", secret={"value": "secret-value-123"}, mount_point="secret"
        )

    @patch("unifiedui.vault.hashicorp_vault.vault.hvac.Client")
    def test_store_secret_with_metadata(self, mock_client_class):
        """Test storing a secret with metadata."""
        mock_client = Mock()
        mock_client.is_authenticated.return_value = True
        mock_client_class.return_value = mock_client

        vault = HashiCorpVault(url="http://localhost:8200", token="token")
        metadata = {"env": "PRODUCTION", "owner": "admin"}
        vault.store_secret("db/password", "secret123", metadata=metadata)

        mock_client.secrets.kv.v2.create_or_update_secret.assert_called_once_with(
            path="db/password", secret={"value": "secret123", "metadata": metadata}, mount_point="secret"
        )

    @patch("unifiedui.vault.hashicorp_vault.vault.hvac.Client")
    def test_store_secret_custom_mount_point(self, mock_client_class):
        """Test storing secret with custom mount point."""
        mock_client = Mock()
        mock_client.is_authenticated.return_value = True
        mock_client_class.return_value = mock_client

        vault = HashiCorpVault(url="http://localhost:8200", token="token", mount_point="kv")
        uri = vault.store_secret("key", "value")

        assert "kv/key" in uri
        mock_client.secrets.kv.v2.create_or_update_secret.assert_called_once_with(
            path="key", secret={"value": "value"}, mount_point="kv"
        )

    @patch("unifiedui.vault.hashicorp_vault.vault.hvac.Client")
    def test_store_secret_handles_error(self, mock_client_class):
        """Test store_secret raises exception when storage fails."""
        mock_client = Mock()
        mock_client.is_authenticated.return_value = True
        mock_client.secrets.kv.v2.create_or_update_secret.side_effect = Exception("Storage failed")
        mock_client_class.return_value = mock_client

        vault = HashiCorpVault(url="http://localhost:8200", token="token")

        with pytest.raises(Exception, match="Storage failed"):
            vault.store_secret("key", "value")

    @patch("unifiedui.vault.hashicorp_vault.vault.hvac.Client")
    def test_get_secret(self, mock_client_class):
        """Test retrieving a secret."""
        mock_client = Mock()
        mock_client.is_authenticated.return_value = True
        mock_client.secrets.kv.v2.read_secret_version.return_value = {"data": {"data": {"value": "secret-value-123"}}}
        mock_client_class.return_value = mock_client

        vault = HashiCorpVault(url="http://localhost:8200", token="token")
        value = vault.get_secret("vault://localhost:8200/secret/my/api/key")

        assert value == "secret-value-123"
        mock_client.secrets.kv.v2.read_secret_version.assert_called_once_with(path="my/api/key", mount_point="secret")

    @patch("unifiedui.vault.hashicorp_vault.vault.hvac.Client")
    def test_get_secret_invalid_uri(self, mock_client_class):
        """Test get_secret with invalid URI returns None."""
        mock_client = Mock()
        mock_client.is_authenticated.return_value = True
        mock_client_class.return_value = mock_client

        vault = HashiCorpVault(url="http://localhost:8200", token="token")
        value = vault.get_secret("invalid-uri")

        assert value is None
        mock_client.secrets.kv.v2.read_secret_version.assert_not_called()

    @patch("unifiedui.vault.hashicorp_vault.vault.hvac.Client")
    def test_get_secret_handles_error(self, mock_client_class):
        """Test get_secret handles errors gracefully."""
        mock_client = Mock()
        mock_client.is_authenticated.return_value = True
        mock_client.secrets.kv.v2.read_secret_version.side_effect = Exception("Not found")
        mock_client_class.return_value = mock_client

        vault = HashiCorpVault(url="http://localhost:8200", token="token")
        value = vault.get_secret("vault://localhost:8200/secret/missing")

        assert value is None

    @patch("unifiedui.vault.hashicorp_vault.vault.hvac.Client")
    def test_update_secret(self, mock_client_class):
        """Test updating a secret."""
        mock_client = Mock()
        mock_client.is_authenticated.return_value = True
        mock_client_class.return_value = mock_client

        vault = HashiCorpVault(url="http://localhost:8200", token="token")
        result = vault.update_secret("vault://localhost:8200/secret/key", "new-value")

        assert result is True
        mock_client.secrets.kv.v2.create_or_update_secret.assert_called_once_with(
            path="key", secret={"value": "new-value"}, mount_point="secret"
        )

    @patch("unifiedui.vault.hashicorp_vault.vault.hvac.Client")
    def test_update_secret_with_metadata(self, mock_client_class):
        """Test updating secret with metadata."""
        mock_client = Mock()
        mock_client.is_authenticated.return_value = True
        mock_client_class.return_value = mock_client

        vault = HashiCorpVault(url="http://localhost:8200", token="token")
        metadata = {"updated": "true"}
        result = vault.update_secret("vault://localhost:8200/secret/key", "value", metadata)

        assert result is True
        mock_client.secrets.kv.v2.create_or_update_secret.assert_called_once_with(
            path="key", secret={"value": "value", "metadata": metadata}, mount_point="secret"
        )

    @patch("unifiedui.vault.hashicorp_vault.vault.hvac.Client")
    def test_update_secret_invalid_uri(self, mock_client_class):
        """Test update_secret with invalid URI returns False."""
        mock_client = Mock()
        mock_client.is_authenticated.return_value = True
        mock_client_class.return_value = mock_client

        vault = HashiCorpVault(url="http://localhost:8200", token="token")
        result = vault.update_secret("invalid-uri", "new-value")

        assert result is False
        mock_client.secrets.kv.v2.create_or_update_secret.assert_not_called()

    @patch("unifiedui.vault.hashicorp_vault.vault.hvac.Client")
    def test_update_secret_handles_error(self, mock_client_class):
        """Test update_secret handles errors gracefully."""
        mock_client = Mock()
        mock_client.is_authenticated.return_value = True
        mock_client.secrets.kv.v2.create_or_update_secret.side_effect = Exception("Update failed")
        mock_client_class.return_value = mock_client

        vault = HashiCorpVault(url="http://localhost:8200", token="token")
        result = vault.update_secret("vault://localhost:8200/secret/key", "new-value")

        assert result is False

    @patch("unifiedui.vault.hashicorp_vault.vault.hvac.Client")
    def test_delete_secret(self, mock_client_class):
        """Test deleting a secret."""
        mock_client = Mock()
        mock_client.is_authenticated.return_value = True
        mock_client_class.return_value = mock_client

        vault = HashiCorpVault(url="http://localhost:8200", token="token")
        result = vault.delete_secret("vault://localhost:8200/secret/key")

        assert result is True
        mock_client.secrets.kv.v2.delete_latest_version_of_secret.assert_called_once_with(
            path="key", mount_point="secret"
        )

    @patch("unifiedui.vault.hashicorp_vault.vault.hvac.Client")
    def test_delete_secret_invalid_uri(self, mock_client_class):
        """Test delete_secret with invalid URI returns False."""
        mock_client = Mock()
        mock_client.is_authenticated.return_value = True
        mock_client_class.return_value = mock_client

        vault = HashiCorpVault(url="http://localhost:8200", token="token")
        result = vault.delete_secret("invalid-uri")

        assert result is False
        mock_client.secrets.kv.v2.delete_latest_version_of_secret.assert_not_called()

    @patch("unifiedui.vault.hashicorp_vault.vault.hvac.Client")
    def test_delete_secret_handles_error(self, mock_client_class):
        """Test delete_secret handles errors gracefully."""
        mock_client = Mock()
        mock_client.is_authenticated.return_value = True
        mock_client.secrets.kv.v2.delete_latest_version_of_secret.side_effect = Exception("Delete failed")
        mock_client_class.return_value = mock_client

        vault = HashiCorpVault(url="http://localhost:8200", token="token")
        result = vault.delete_secret("vault://localhost:8200/secret/key")

        assert result is False

    @patch("unifiedui.vault.hashicorp_vault.vault.hvac.Client")
    def test_ping_success(self, mock_client_class):
        """Test ping returns True when vault is accessible."""
        mock_client = Mock()
        mock_client.is_authenticated.return_value = True
        mock_client.sys.read_health_status.return_value = {"initialized": True}
        mock_client_class.return_value = mock_client

        vault = HashiCorpVault(url="http://localhost:8200", token="token")
        result = vault.ping()

        assert result is True

    @patch("unifiedui.vault.hashicorp_vault.vault.hvac.Client")
    def test_ping_failure(self, mock_client_class):
        """Test ping returns False when vault is not accessible."""
        mock_client = Mock()
        mock_client.is_authenticated.side_effect = [True, Exception("Connection error")]
        mock_client_class.return_value = mock_client

        vault = HashiCorpVault(url="http://localhost:8200", token="token")
        result = vault.ping()

        assert result is False

    @patch("unifiedui.vault.hashicorp_vault.vault.hvac.Client")
    def test_close(self, mock_client_class):
        """Test close method."""
        mock_client = Mock()
        mock_client.is_authenticated.return_value = True
        mock_client_class.return_value = mock_client

        vault = HashiCorpVault(url="http://localhost:8200", token="token")
        vault.close()

        # HashiCorp Vault client doesn't have explicit close, just verify no errors
        assert True
