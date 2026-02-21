"""Tests for AgentServiceClient."""

from typing import Any
from unittest.mock import MagicMock, patch

from unifiedui.services.agent_service_client import AgentServiceClient


class TestAgentServiceClient:
    """Test suite for AgentServiceClient."""

    def _create_client(self, app_vault: Any = None) -> AgentServiceClient:
        """Create an AgentServiceClient with test defaults."""
        return AgentServiceClient(base_url="http://agent-service:8085", app_vault=app_vault, timeout=5)

    def test_delete_conversation_data_success(self) -> None:
        """Test successful cascade delete of conversation data."""
        client = self._create_client()

        mock_response = MagicMock()
        mock_response.status_code = 204

        with patch("unifiedui.services.agent_service_client.httpx.Client") as mock_httpx:
            mock_httpx_instance = MagicMock()
            mock_httpx_instance.delete.return_value = mock_response
            mock_httpx.return_value.__enter__ = MagicMock(return_value=mock_httpx_instance)
            mock_httpx.return_value.__exit__ = MagicMock(return_value=False)

            result = client.delete_conversation_data("tenant-1", "conv-1")

        assert result is True
        mock_httpx_instance.delete.assert_called_once()
        call_args = mock_httpx_instance.delete.call_args
        assert "/conversations/conv-1/data" in call_args[0][0]

    def test_delete_conversation_data_failure_status(self) -> None:
        """Test cascade delete returns False on non-2xx status."""
        client = self._create_client()

        mock_response = MagicMock()
        mock_response.status_code = 500

        with patch("unifiedui.services.agent_service_client.httpx.Client") as mock_httpx:
            mock_httpx_instance = MagicMock()
            mock_httpx_instance.delete.return_value = mock_response
            mock_httpx.return_value.__enter__ = MagicMock(return_value=mock_httpx_instance)
            mock_httpx.return_value.__exit__ = MagicMock(return_value=False)

            result = client.delete_conversation_data("tenant-1", "conv-1")

        assert result is False

    def test_delete_conversation_data_connection_error(self) -> None:
        """Test cascade delete returns False on connection error (best-effort)."""
        client = self._create_client()

        with patch("unifiedui.services.agent_service_client.httpx.Client") as mock_httpx:
            mock_httpx_instance = MagicMock()
            mock_httpx_instance.delete.side_effect = ConnectionError("connection refused")
            mock_httpx.return_value.__enter__ = MagicMock(return_value=mock_httpx_instance)
            mock_httpx.return_value.__exit__ = MagicMock(return_value=False)

            result = client.delete_conversation_data("tenant-1", "conv-1")

        assert result is False

    def test_delete_autonomous_agent_data_success(self) -> None:
        """Test successful cascade delete of autonomous agent data."""
        client = self._create_client()

        mock_response = MagicMock()
        mock_response.status_code = 204

        with patch("unifiedui.services.agent_service_client.httpx.Client") as mock_httpx:
            mock_httpx_instance = MagicMock()
            mock_httpx_instance.delete.return_value = mock_response
            mock_httpx.return_value.__enter__ = MagicMock(return_value=mock_httpx_instance)
            mock_httpx.return_value.__exit__ = MagicMock(return_value=False)

            result = client.delete_autonomous_agent_data("tenant-1", "agent-1")

        assert result is True
        mock_httpx_instance.delete.assert_called_once()
        call_args = mock_httpx_instance.delete.call_args
        assert "/autonomous-agents/agent-1/data" in call_args[0][0]

    def test_delete_autonomous_agent_data_failure(self) -> None:
        """Test cascade delete of agent data returns False on error."""
        client = self._create_client()

        with patch("unifiedui.services.agent_service_client.httpx.Client") as mock_httpx:
            mock_httpx_instance = MagicMock()
            mock_httpx_instance.delete.side_effect = Exception("timeout")
            mock_httpx.return_value.__enter__ = MagicMock(return_value=mock_httpx_instance)
            mock_httpx.return_value.__exit__ = MagicMock(return_value=False)

            result = client.delete_autonomous_agent_data("tenant-1", "agent-1")

        assert result is False

    def test_service_key_from_vault(self) -> None:
        """Test that service key is retrieved from app vault."""
        mock_vault = MagicMock()
        mock_vault.build_secret_uri.return_value = "dotenv://PLATFORM_TO_AGENT_SERVICE_KEY"
        mock_vault.get_secret.return_value = "vault-service-key"

        client = self._create_client(app_vault=mock_vault)

        mock_response = MagicMock()
        mock_response.status_code = 204

        with patch("unifiedui.services.agent_service_client.httpx.Client") as mock_httpx:
            mock_httpx_instance = MagicMock()
            mock_httpx_instance.delete.return_value = mock_response
            mock_httpx.return_value.__enter__ = MagicMock(return_value=mock_httpx_instance)
            mock_httpx.return_value.__exit__ = MagicMock(return_value=False)

            client.delete_conversation_data("tenant-1", "conv-1")

        call_args = mock_httpx_instance.delete.call_args
        headers = call_args[1]["headers"] if "headers" in call_args[1] else call_args.kwargs.get("headers", {})
        assert headers.get("X-Service-Key") == "vault-service-key"

    def test_service_key_missing_when_no_vault(self) -> None:
        """Test that no X-Service-Key header is set when vault is not available."""
        client = self._create_client(app_vault=None)

        mock_response = MagicMock()
        mock_response.status_code = 204

        with patch("unifiedui.services.agent_service_client.httpx.Client") as mock_httpx:
            mock_httpx_instance = MagicMock()
            mock_httpx_instance.delete.return_value = mock_response
            mock_httpx.return_value.__enter__ = MagicMock(return_value=mock_httpx_instance)
            mock_httpx.return_value.__exit__ = MagicMock(return_value=False)

            result = client.delete_conversation_data("tenant-1", "conv-1")

        assert result is True
        call_args = mock_httpx_instance.delete.call_args
        headers = call_args[1]["headers"] if "headers" in call_args[1] else call_args.kwargs.get("headers", {})
        assert "X-Service-Key" not in headers

    def test_vault_exception_does_not_propagate(self) -> None:
        """Test that vault errors are handled gracefully (no X-Service-Key sent)."""
        mock_vault = MagicMock()
        mock_vault.build_secret_uri.return_value = "dotenv://PLATFORM_TO_AGENT_SERVICE_KEY"
        mock_vault.get_secret.side_effect = Exception("vault unavailable")

        client = self._create_client(app_vault=mock_vault)

        mock_response = MagicMock()
        mock_response.status_code = 204

        with patch("unifiedui.services.agent_service_client.httpx.Client") as mock_httpx:
            mock_httpx_instance = MagicMock()
            mock_httpx_instance.delete.return_value = mock_response
            mock_httpx.return_value.__enter__ = MagicMock(return_value=mock_httpx_instance)
            mock_httpx.return_value.__exit__ = MagicMock(return_value=False)

            result = client.delete_conversation_data("tenant-1", "conv-1")

        assert result is True
