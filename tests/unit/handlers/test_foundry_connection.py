"""Unit tests for the Foundry connection tester (REQ 008)."""

import json
from unittest.mock import MagicMock, patch

import pytest
import requests

from unifiedui.handlers.foundry_connection import FoundryConnectionTester
from unifiedui.schema.test_connection import TestConnectionRequest


def _make_request(auth_type: str, credential_id: str | None = None) -> TestConnectionRequest:
    return TestConnectionRequest(
        agent_type="AGENT",
        api_version="v1",
        project_endpoint="https://x.services.ai.azure.com/api/projects/p",
        agent_name="BasicAgent",
        auth_type=auth_type,
        credential_id=credential_id,
    )


def _ok_response() -> MagicMock:
    response = MagicMock(spec=requests.Response)
    response.status_code = 200
    response.json.return_value = {
        "id": "BasicAgent",
        "name": "BasicAgent",
        "definition": {"model": "gpt-4.1"},
        "status": "active",
    }
    return response


def _error_response(status_code: int, message: str = "denied") -> MagicMock:
    response = MagicMock(spec=requests.Response)
    response.status_code = status_code
    response.text = message
    response.json.return_value = {"error": {"message": message}}
    return response


@pytest.fixture
def credential_handler() -> MagicMock:
    return MagicMock()


@pytest.fixture
def tester(credential_handler: MagicMock) -> FoundryConnectionTester:
    return FoundryConnectionTester(credential_handler)


class TestFoundryConnectionTester:
    """Unit tests for FoundryConnectionTester covering all auth modes."""

    def test_user_token_success(self, tester: FoundryConnectionTester) -> None:
        with patch("unifiedui.handlers.foundry_connection.requests.get", return_value=_ok_response()) as mocked:
            result = tester.test("tenant-1", _make_request("ENTRA_ID_USER_TOKEN"), user_token="abc")
        assert result.success is True
        assert result.error_code is None
        assert result.agent_metadata == {
            "id": "BasicAgent",
            "name": "BasicAgent",
            "model": "gpt-4.1",
            "status": "active",
        }
        called_kwargs = mocked.call_args.kwargs
        assert called_kwargs["headers"] == {"Authorization": "Bearer abc"}
        assert called_kwargs["params"] == {"api-version": "v1"}

    def test_user_token_missing_token(self, tester: FoundryConnectionTester) -> None:
        result = tester.test("tenant-1", _make_request("ENTRA_ID_USER_TOKEN"), user_token=None)
        assert result.success is False
        assert result.error_code == "CREDENTIAL_INVALID"
        assert result.latency_ms == 0

    def test_api_key_success(self, tester: FoundryConnectionTester, credential_handler: MagicMock) -> None:
        credential_handler.get_credential.return_value = MagicMock(type="API_KEY")
        credential_handler.get_credential_secret.return_value = "secret-key"
        with patch("unifiedui.handlers.foundry_connection.requests.get", return_value=_ok_response()) as mocked:
            result = tester.test("t", _make_request("API_KEY", credential_id="c-1"), user_token=None)
        assert result.success is True
        assert mocked.call_args.kwargs["headers"] == {"api-key": "secret-key"}

    def test_api_key_credential_type_mismatch(
        self, tester: FoundryConnectionTester, credential_handler: MagicMock
    ) -> None:
        credential_handler.get_credential.return_value = MagicMock(type="BASIC_AUTH")
        result = tester.test("t", _make_request("API_KEY", credential_id="c-2"), user_token=None)
        assert result.success is False
        assert result.error_code == "CREDENTIAL_INVALID"
        assert "type mismatch" in (result.error_message or "")

    def test_api_key_missing_credential_id(self, tester: FoundryConnectionTester) -> None:
        result = tester.test("t", _make_request("API_KEY"), user_token=None)
        assert result.success is False
        assert result.error_code == "CREDENTIAL_INVALID"

    def test_app_registration_success(self, tester: FoundryConnectionTester, credential_handler: MagicMock) -> None:
        credential_handler.get_credential.return_value = MagicMock(type="ENTRA_ID_APP_REGISTRATION")
        credential_handler.get_credential_secret.return_value = json.dumps(
            {"tenant_id": "t", "client_id": "c", "client_secret": "s"}
        )
        with (
            patch("unifiedui.handlers.foundry_connection.ClientCredentialsTokenClient") as cc_cls,
            patch("unifiedui.handlers.foundry_connection.requests.get", return_value=_ok_response()) as mocked,
        ):
            cc_cls.return_value.acquire_token.return_value = "synthetic-token"
            result = tester.test(
                "t",
                _make_request("ENTRA_ID_APP_REGISTRATION", credential_id="c-3"),
                user_token=None,
            )
        assert result.success is True
        assert mocked.call_args.kwargs["headers"] == {"Authorization": "Bearer synthetic-token"}
        cc_cls.assert_called_once_with(tenant_id="t", client_id="c", client_secret="s")

    def test_app_registration_invalid_payload(
        self, tester: FoundryConnectionTester, credential_handler: MagicMock
    ) -> None:
        credential_handler.get_credential.return_value = MagicMock(type="ENTRA_ID_APP_REGISTRATION")
        credential_handler.get_credential_secret.return_value = "not-json"
        result = tester.test(
            "t",
            _make_request("ENTRA_ID_APP_REGISTRATION", credential_id="c-4"),
            user_token=None,
        )
        assert result.success is False
        assert result.error_code == "CREDENTIAL_INVALID"

    def test_app_registration_token_acquisition_failure(
        self, tester: FoundryConnectionTester, credential_handler: MagicMock
    ) -> None:
        credential_handler.get_credential.return_value = MagicMock(type="ENTRA_ID_APP_REGISTRATION")
        credential_handler.get_credential_secret.return_value = json.dumps(
            {"tenant_id": "t", "client_id": "c", "client_secret": "s"}
        )
        with patch("unifiedui.handlers.foundry_connection.ClientCredentialsTokenClient") as cc_cls:
            cc_cls.return_value.acquire_token.side_effect = ValueError("token rejected")
            result = tester.test(
                "t",
                _make_request("ENTRA_ID_APP_REGISTRATION", credential_id="c-5"),
                user_token=None,
            )
        assert result.success is False
        assert result.error_code == "CREDENTIAL_INVALID"
        assert "token rejected" in (result.error_message or "")

    def test_auth_failed_401(self, tester: FoundryConnectionTester) -> None:
        with patch(
            "unifiedui.handlers.foundry_connection.requests.get",
            return_value=_error_response(401, "auth rejected"),
        ):
            result = tester.test("t", _make_request("ENTRA_ID_USER_TOKEN"), user_token="x")
        assert result.success is False
        assert result.error_code == "AUTH_FAILED"

    def test_agent_not_found_404(self, tester: FoundryConnectionTester) -> None:
        with patch(
            "unifiedui.handlers.foundry_connection.requests.get",
            return_value=_error_response(404, "no such agent"),
        ):
            result = tester.test("t", _make_request("ENTRA_ID_USER_TOKEN"), user_token="x")
        assert result.success is False
        assert result.error_code == "AGENT_NOT_FOUND"

    def test_timeout(self, tester: FoundryConnectionTester) -> None:
        with patch(
            "unifiedui.handlers.foundry_connection.requests.get",
            side_effect=requests.Timeout("slow"),
        ):
            result = tester.test("t", _make_request("ENTRA_ID_USER_TOKEN"), user_token="x")
        assert result.success is False
        assert result.error_code == "TIMEOUT"

    def test_invalid_endpoint(self, tester: FoundryConnectionTester) -> None:
        with patch(
            "unifiedui.handlers.foundry_connection.requests.get",
            side_effect=requests.ConnectionError("boom"),
        ):
            result = tester.test("t", _make_request("ENTRA_ID_USER_TOKEN"), user_token="x")
        assert result.success is False
        assert result.error_code == "INVALID_ENDPOINT"
