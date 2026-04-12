"""Tests for credential test connection handler."""

from unittest.mock import MagicMock, patch

import pytest

from unifiedui.handlers.credentials import CredentialHandler
from unifiedui.handlers.validators.credential_validator import CredentialValidationError
from unifiedui.schema.requests.credentials import TestCredentialConnectionRequest

PATCH_TARGET = "unifiedui.core.identity.client_credentials.ClientCredentialsTokenClient"


class TestCredentialTestConnection:
    """Tests for CredentialHandler.test_credential_connection."""

    def test_success_with_default_scope(self) -> None:
        """Test successful token acquisition with default scope."""
        request = TestCredentialConnectionRequest(
            credential_type="ENTRA_ID_APP_REGISTRATION",
            tenant_id="test-tenant-id",
            client_id="test-client-id",
            client_secret="test-client-secret",
        )

        with patch(PATCH_TARGET) as mock_client_cls:
            mock_client = MagicMock()
            mock_client.acquire_token.return_value = "test-token"
            mock_client_cls.return_value = mock_client

            result = CredentialHandler.test_credential_connection(request=request)

            assert result.success is True
            assert result.message == "Token acquired successfully"
            assert result.response_time_ms >= 0
            mock_client_cls.assert_called_once_with(
                tenant_id="test-tenant-id",
                client_id="test-client-id",
                client_secret="test-client-secret",
            )
            mock_client.acquire_token.assert_called_once_with(scope="https://graph.microsoft.com/.default")

    def test_success_with_custom_scopes(self) -> None:
        """Test successful token acquisition with custom scopes."""
        request = TestCredentialConnectionRequest(
            credential_type="ENTRA_ID_APP_REGISTRATION",
            tenant_id="test-tenant-id",
            client_id="test-client-id",
            client_secret="test-client-secret",
            scopes=["https://my-api.example.com/.default"],
        )

        with patch(PATCH_TARGET) as mock_client_cls:
            mock_client = MagicMock()
            mock_client.acquire_token.return_value = "test-token"
            mock_client_cls.return_value = mock_client

            result = CredentialHandler.test_credential_connection(request=request)

            assert result.success is True
            mock_client.acquire_token.assert_called_once_with(scope="https://my-api.example.com/.default")

    def test_success_uses_first_scope(self) -> None:
        """Test that only the first scope is used when multiple are provided."""
        request = TestCredentialConnectionRequest(
            credential_type="ENTRA_ID_APP_REGISTRATION",
            tenant_id="test-tenant-id",
            client_id="test-client-id",
            client_secret="test-client-secret",
            scopes=["https://first.example.com/.default", "https://second.example.com/.default"],
        )

        with patch(PATCH_TARGET) as mock_client_cls:
            mock_client = MagicMock()
            mock_client.acquire_token.return_value = "test-token"
            mock_client_cls.return_value = mock_client

            result = CredentialHandler.test_credential_connection(request=request)

            assert result.success is True
            mock_client.acquire_token.assert_called_once_with(scope="https://first.example.com/.default")

    def test_failure_invalid_credentials(self) -> None:
        """Test failed token acquisition returns failure response."""
        request = TestCredentialConnectionRequest(
            credential_type="ENTRA_ID_APP_REGISTRATION",
            tenant_id="test-tenant-id",
            client_id="invalid-client-id",
            client_secret="invalid-secret",
        )

        with patch(PATCH_TARGET) as mock_client_cls:
            mock_client = MagicMock()
            mock_client.acquire_token.side_effect = ValueError(
                "Client credentials token acquisition failed: invalid_client"
            )
            mock_client_cls.return_value = mock_client

            result = CredentialHandler.test_credential_connection(request=request)

            assert result.success is False
            assert "invalid_client" in result.message
            assert result.response_time_ms >= 0

    def test_unsupported_credential_type(self) -> None:
        """Test that unsupported credential type raises CredentialValidationError."""
        request = TestCredentialConnectionRequest(
            credential_type="API_KEY",
            tenant_id="test-tenant-id",
            client_id="test-client-id",
            client_secret="test-client-secret",
        )

        with pytest.raises(CredentialValidationError) as exc_info:
            CredentialHandler.test_credential_connection(request=request)

        assert "only supported for ENTRA_ID_APP_REGISTRATION" in exc_info.value.message

    def test_empty_scopes_uses_default(self) -> None:
        """Test that empty scopes list uses default scope."""
        request = TestCredentialConnectionRequest(
            credential_type="ENTRA_ID_APP_REGISTRATION",
            tenant_id="test-tenant-id",
            client_id="test-client-id",
            client_secret="test-client-secret",
            scopes=[],
        )

        with patch(PATCH_TARGET) as mock_client_cls:
            mock_client = MagicMock()
            mock_client.acquire_token.return_value = "test-token"
            mock_client_cls.return_value = mock_client

            result = CredentialHandler.test_credential_connection(request=request)

            assert result.success is True
            mock_client.acquire_token.assert_called_once_with(scope="https://graph.microsoft.com/.default")
