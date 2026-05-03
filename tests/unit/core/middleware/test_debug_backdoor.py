"""Tests for the debug backdoor (REQ 007)."""

from __future__ import annotations

import secrets
from typing import TYPE_CHECKING

import pytest

from unifiedui.core.config import Settings, settings

if TYPE_CHECKING:
    from fastapi.testclient import TestClient
from unifiedui.core.middleware.apis.v1.debug_backdoor import (
    DEBUG_HEADER_SECRET,
    DEBUG_HEADER_TENANT_ID,
    DEBUG_HEADER_USER_ID,
    DEBUG_HEADER_USER_UPN,
)

VALID_SECRET = "x" * 40


@pytest.fixture
def enable_backdoor(monkeypatch: pytest.MonkeyPatch) -> str:
    """Enable backdoor with a known secret for the duration of the test."""
    monkeypatch.setattr(settings, "enable_debug_back_door", True)
    monkeypatch.setattr(settings, "debug_back_door_secret", VALID_SECRET)
    return VALID_SECRET


class TestDebugBackdoorSettings:
    def test_short_secret_rejected(self) -> None:
        with pytest.raises(ValueError, match="debug_back_door_secret"):
            Settings(
                enable_debug_back_door=True,
                debug_back_door_secret="too-short",
                allow_mock_identity_provider=True,
            )

    def test_missing_secret_rejected(self) -> None:
        with pytest.raises(ValueError, match="debug_back_door_secret"):
            Settings(enable_debug_back_door=True, allow_mock_identity_provider=True)

    def test_production_blocks_backdoor(self) -> None:
        with pytest.raises(ValueError, match="enable_debug_back_door"):
            Settings(
                deployment_mode="production",
                identity_verify_signature=True,
                allow_mock_identity_provider=False,
                enable_debug_back_door=True,
                debug_back_door_secret=secrets.token_urlsafe(32),
            )

    def test_backdoor_requires_mock_idp(self) -> None:
        with pytest.raises(ValueError, match="allow_mock_identity_provider"):
            Settings(
                enable_debug_back_door=True,
                debug_back_door_secret=secrets.token_urlsafe(32),
                allow_mock_identity_provider=False,
            )

    def test_disabled_by_default(self) -> None:
        s = Settings()
        assert s.enable_debug_back_door is False
        assert s.debug_back_door_secret is None


class TestHealthcheckExposesBackdoorFlag:
    def test_disabled(self, test_client: TestClient) -> None:
        resp = test_client.get("/api/v1/platform-service/healthcheck")
        assert resp.status_code == 200
        assert resp.json()["debug_backdoor_enabled"] is False

    def test_enabled(self, test_client: TestClient, enable_backdoor: str) -> None:
        resp = test_client.get("/api/v1/platform-service/healthcheck")
        assert resp.status_code == 200
        assert resp.json()["debug_backdoor_enabled"] is True


class TestBackdoorAuthOnProtectedEndpoint:
    """Hits a protected endpoint via backdoor headers — verifies @authenticate path."""

    def _url(self) -> str:
        return "/api/v1/platform-service/identity/me"

    def test_disabled_ignores_headers(self, test_client: TestClient) -> None:
        resp = test_client.get(
            self._url(),
            headers={
                DEBUG_HEADER_SECRET: VALID_SECRET,
                DEBUG_HEADER_USER_ID: "back-user-1",
                DEBUG_HEADER_USER_UPN: "back@example.com",
            },
        )
        assert resp.status_code == 401

    def test_wrong_secret_rejected(self, test_client: TestClient, enable_backdoor: str) -> None:
        resp = test_client.get(
            self._url(),
            headers={
                DEBUG_HEADER_SECRET: "wrong-secret",
                DEBUG_HEADER_USER_ID: "back-user-1",
                DEBUG_HEADER_USER_UPN: "back@example.com",
            },
        )
        assert resp.status_code == 401

    def test_missing_user_id_rejected(self, test_client: TestClient, enable_backdoor: str) -> None:
        resp = test_client.get(
            self._url(),
            headers={
                DEBUG_HEADER_SECRET: VALID_SECRET,
                DEBUG_HEADER_USER_UPN: "back@example.com",
            },
        )
        assert resp.status_code == 401

    def test_valid_backdoor_authenticates(self, test_client: TestClient, enable_backdoor: str) -> None:
        resp = test_client.get(
            self._url(),
            headers={
                DEBUG_HEADER_SECRET: VALID_SECRET,
                DEBUG_HEADER_USER_ID: "back-user-1",
                DEBUG_HEADER_USER_UPN: "back@example.com",
                DEBUG_HEADER_TENANT_ID: "test-tenant-123",
                "X-Use-Cache": "false",
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == "back-user-1"
        assert body["mail"] == "back@example.com"


class TestBackdoorLoginEndpoint:
    def test_disabled_returns_404(self, test_client: TestClient) -> None:
        resp = test_client.post(
            "/api/v1/platform-service/auth/debug-backdoor",
            json={"secret": VALID_SECRET, "user_id": "u1", "upn": "u1@example.com"},
        )
        assert resp.status_code == 404

    def test_wrong_secret_returns_401(self, test_client: TestClient, enable_backdoor: str) -> None:
        resp = test_client.post(
            "/api/v1/platform-service/auth/debug-backdoor",
            json={"secret": "y" * 40, "user_id": "u1", "upn": "u1@example.com"},
        )
        assert resp.status_code == 401

    def test_issues_usable_token(self, test_client: TestClient, enable_backdoor: str) -> None:
        resp = test_client.post(
            "/api/v1/platform-service/auth/debug-backdoor",
            json={"secret": VALID_SECRET, "user_id": "u1", "upn": "u1@example.com", "name": "U One"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["debug"] is True
        assert body["token_type"] == "Bearer"
        token = body["access_token"]
        assert isinstance(token, str) and len(token) > 20

        me_resp = test_client.get(
            "/api/v1/platform-service/identity/me",
            headers={"Authorization": f"Bearer {token}", "X-Use-Cache": "false"},
        )
        assert me_resp.status_code == 200
        assert me_resp.json()["id"] == "u1"
