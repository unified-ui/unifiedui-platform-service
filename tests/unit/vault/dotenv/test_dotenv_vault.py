"""Unit tests for DotEnv vault implementation."""

import os
from unittest.mock import patch

from unifiedui.vault.dotenv.client import DotEnvVaultClient
from unifiedui.vault.dotenv.vault import DotEnvVault


class TestDotEnvVault:
    """Test suite for DotEnvVault."""

    def test_store_secret_returns_uri(self):
        """Test that store_secret returns a dotenv:// URI."""
        vault = DotEnvVault()

        uri = vault.store_secret("my_key", "my_secret")

        assert uri == "dotenv://my_key"

    def test_get_secret_from_memory(self):
        """Test that get_secret retrieves from in-memory store."""
        vault = DotEnvVault()
        vault.store_secret("test_key", "test_value")

        result = vault.get_secret("dotenv://test_key")

        assert result == "test_value"

    def test_get_secret_from_environment(self):
        """Test that get_secret reads from environment variables."""
        vault = DotEnvVault()

        with patch.dict(os.environ, {"ENV_KEY": "env_value"}):
            result = vault.get_secret("dotenv://ENV_KEY")

        assert result == "env_value"

    def test_get_secret_env_takes_priority(self):
        """Test that environment variables take priority over memory."""
        vault = DotEnvVault()
        vault.store_secret("MY_KEY", "memory_value")

        with patch.dict(os.environ, {"MY_KEY": "env_value"}):
            result = vault.get_secret("dotenv://MY_KEY")

        assert result == "env_value"

    def test_get_secret_not_found(self):
        """Test that get_secret returns None for missing keys."""
        vault = DotEnvVault()

        result = vault.get_secret("dotenv://nonexistent_key")

        assert result is None

    def test_update_secret(self):
        """Test that update_secret updates in-memory store."""
        vault = DotEnvVault()
        vault.store_secret("update_key", "initial_value")

        success = vault.update_secret("dotenv://update_key", "updated_value")
        result = vault.get_secret("dotenv://update_key")

        assert success is True
        assert result == "updated_value"

    def test_delete_secret(self):
        """Test that delete_secret removes from in-memory store."""
        vault = DotEnvVault()
        vault.store_secret("delete_key", "value")

        success = vault.delete_secret("dotenv://delete_key")
        result = vault.get_secret("dotenv://delete_key")

        assert success is True
        assert result is None

    def test_delete_secret_not_found(self):
        """Test that delete_secret returns False for missing keys."""
        vault = DotEnvVault()

        success = vault.delete_secret("dotenv://nonexistent")

        assert success is False

    def test_ping_always_true(self):
        """Test that ping always returns True."""
        vault = DotEnvVault()

        assert vault.ping() is True

    def test_close_no_error(self):
        """Test that close doesn't raise any errors."""
        vault = DotEnvVault()

        vault.close()  # Should not raise


class TestDotEnvVaultClient:
    """Test suite for DotEnvVaultClient."""

    def test_get_vault_returns_dotenv_vault(self):
        """Test that get_vault returns DotEnvVault instance."""
        client = DotEnvVaultClient()

        vault = client.get_vault()

        assert isinstance(vault, DotEnvVault)

    def test_client_store_and_get_secret(self):
        """Test that client can store and retrieve secrets."""
        client = DotEnvVaultClient()

        uri = client.store_secret("client_test", "client_value")
        result = client.get_secret(uri)

        assert result == "client_value"

    def test_client_with_cache(self):
        """Test that client works with cache client."""
        mock_cache = type(
            "MockCache",
            (),
            {
                "get": lambda self, key: None,
                "set": lambda self, key, value, ttl=None: None,
                "delete": lambda self, key: None,
            },
        )()

        client = DotEnvVaultClient(cache_client=mock_cache)

        uri = client.store_secret("cache_test", "cache_value")
        result = client.get_secret(uri)

        assert result == "cache_value"

    def test_client_ping(self):
        """Test that client ping returns True."""
        client = DotEnvVaultClient()

        assert client.ping() is True

    def test_client_close(self):
        """Test that client close doesn't raise."""
        client = DotEnvVaultClient()

        client.close()  # Should not raise
