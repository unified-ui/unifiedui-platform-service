"""Foundry connection-test handler (REQ 008).

Performs a real HTTP probe against a Foundry agent to verify both the project
endpoint reachability and the configured authentication mode. Used by the
test-connection endpoint and (optionally) by the create/update routes.
"""

import json
import time
from typing import Any

import requests

from unifiedui.core.identity.client_credentials import ClientCredentialsTokenClient
from unifiedui.exc.chat_agent_config import InvalidCredentialError
from unifiedui.handlers.credentials import CredentialHandler
from unifiedui.logger import get_logger
from unifiedui.schema.test_connection import TestConnectionRequest, TestConnectionResponse

logger = get_logger(__name__)

FOUNDRY_TIMEOUT_SECONDS = 10
FOUNDRY_TOKEN_SCOPE = "https://ai.azure.com/.default"


class FoundryConnectionTester:
    """Probes a Foundry agent endpoint to verify auth + reachability."""

    def __init__(self, credential_handler: CredentialHandler):
        """Initialize with a credential handler for credential lookup.

        Args:
            credential_handler: Handler used to fetch credentials/secrets.
        """
        self._credentials = credential_handler

    def test(
        self,
        tenant_id: str,
        request: TestConnectionRequest,
        user_token: str | None,
    ) -> TestConnectionResponse:
        """Perform a test connection against a Foundry agent.

        Args:
            tenant_id: Tenant scope used for credential lookup.
            request: Full Foundry config to probe.
            user_token: Bearer token forwarded from the caller (used for
                ENTRA_ID_USER_TOKEN auth mode).

        Returns:
            TestConnectionResponse describing the outcome.
        """
        try:
            headers = self._build_headers(tenant_id, request, user_token)
        except _CredentialResolutionError as exc:
            return TestConnectionResponse(
                success=False,
                latency_ms=0,
                error_code=exc.error_code,
                error_message=exc.message,
            )

        url = f"{request.project_endpoint.rstrip('/')}/agents/{request.agent_name}"
        params = {"api-version": request.api_version}

        started = time.monotonic()
        try:
            response = requests.get(url, headers=headers, params=params, timeout=FOUNDRY_TIMEOUT_SECONDS)
        except requests.Timeout:
            elapsed_ms = int((time.monotonic() - started) * 1000)
            return TestConnectionResponse(
                success=False,
                latency_ms=elapsed_ms,
                error_code="TIMEOUT",
                error_message=f"Foundry endpoint did not respond within {FOUNDRY_TIMEOUT_SECONDS}s",
            )
        except requests.RequestException as exc:
            elapsed_ms = int((time.monotonic() - started) * 1000)
            return TestConnectionResponse(
                success=False,
                latency_ms=elapsed_ms,
                error_code="INVALID_ENDPOINT",
                error_message=f"Failed to reach Foundry endpoint: {exc}",
            )

        elapsed_ms = int((time.monotonic() - started) * 1000)

        if response.status_code == 200:
            metadata = self._extract_metadata(response)
            return TestConnectionResponse(
                success=True,
                latency_ms=elapsed_ms,
                agent_metadata=metadata,
            )
        if response.status_code in (401, 403):
            return TestConnectionResponse(
                success=False,
                latency_ms=elapsed_ms,
                error_code="AUTH_FAILED",
                error_message=self._extract_error_message(response, default="Authentication rejected by Foundry"),
            )
        if response.status_code == 404:
            return TestConnectionResponse(
                success=False,
                latency_ms=elapsed_ms,
                error_code="AGENT_NOT_FOUND",
                error_message=self._extract_error_message(
                    response, default=f"Agent '{request.agent_name}' not found in Foundry project"
                ),
            )

        return TestConnectionResponse(
            success=False,
            latency_ms=elapsed_ms,
            error_code="UNKNOWN",
            error_message=f"Foundry returned HTTP {response.status_code}: {response.text[:300]}",
        )

    def _build_headers(
        self,
        tenant_id: str,
        request: TestConnectionRequest,
        user_token: str | None,
    ) -> dict[str, str]:
        """Build auth headers for the Foundry probe based on auth_type."""
        if request.auth_type == "ENTRA_ID_USER_TOKEN":
            if not user_token:
                raise _CredentialResolutionError(
                    "CREDENTIAL_INVALID",
                    "ENTRA_ID_USER_TOKEN mode requires a forwarded user bearer token",
                )
            return {"Authorization": f"Bearer {user_token}"}

        if request.auth_type == "API_KEY":
            secret = self._fetch_secret(tenant_id, request.credential_id, expected_type="API_KEY")
            if not isinstance(secret, str) or not secret:
                raise _CredentialResolutionError(
                    "CREDENTIAL_INVALID",
                    f"API_KEY credential '{request.credential_id}' has no usable secret",
                )
            return {"api-key": secret}

        if request.auth_type == "ENTRA_ID_APP_REGISTRATION":
            secret = self._fetch_secret(tenant_id, request.credential_id, expected_type="ENTRA_ID_APP_REGISTRATION")
            if isinstance(secret, str):
                try:
                    secret = json.loads(secret)
                except json.JSONDecodeError as exc:
                    raise _CredentialResolutionError(
                        "CREDENTIAL_INVALID",
                        f"App-registration credential '{request.credential_id}' is not valid JSON: {exc}",
                    )
            if not isinstance(secret, dict):
                raise _CredentialResolutionError(
                    "CREDENTIAL_INVALID",
                    "App-registration credential payload must be an object",
                )
            for field in ("tenant_id", "client_id", "client_secret"):
                if not secret.get(field):
                    raise _CredentialResolutionError(
                        "CREDENTIAL_INVALID",
                        f"App-registration credential is missing field '{field}'",
                    )
            cc_client = ClientCredentialsTokenClient(
                tenant_id=secret["tenant_id"],
                client_id=secret["client_id"],
                client_secret=secret["client_secret"],
            )
            try:
                token = cc_client.acquire_token(scope=FOUNDRY_TOKEN_SCOPE)
            except ValueError as exc:
                raise _CredentialResolutionError(
                    "CREDENTIAL_INVALID",
                    f"Failed to acquire client-credentials token: {exc}",
                )
            return {"Authorization": f"Bearer {token}"}

        raise _CredentialResolutionError("CREDENTIAL_INVALID", f"Unsupported auth_type '{request.auth_type}'")

    def _fetch_secret(self, tenant_id: str, credential_id: str | None, expected_type: str) -> str | None:
        """Look up a credential and verify its type, returning its secret."""
        if not credential_id:
            raise _CredentialResolutionError(
                "CREDENTIAL_INVALID",
                f"credential_id is required for auth_type expecting '{expected_type}'",
            )
        try:
            credential = self._credentials.get_credential(tenant_id, credential_id)
        except Exception as exc:
            raise _CredentialResolutionError(
                "CREDENTIAL_INVALID",
                f"Credential '{credential_id}' not found or inaccessible: {exc}",
            )
        if credential.type != expected_type:
            raise _CredentialResolutionError(
                "CREDENTIAL_INVALID",
                (
                    f"Credential type mismatch: expected '{expected_type}', "
                    f"got '{credential.type}' for credential '{credential_id}'"
                ),
            )
        try:
            return self._credentials.get_credential_secret(tenant_id, credential_id)
        except Exception as exc:
            logger.warning("Failed to fetch credential secret for %s: %s", credential_id, exc)
            raise _CredentialResolutionError("CREDENTIAL_INVALID", f"Failed to read credential secret: {exc}") from exc

    @staticmethod
    def _extract_metadata(response: requests.Response) -> dict[str, Any] | None:
        """Extract a small metadata payload from a successful Foundry response."""
        try:
            data = response.json()
        except ValueError:
            return None
        if not isinstance(data, dict):
            return None
        return {
            "id": data.get("id"),
            "name": data.get("name"),
            "model": data.get("model") or data.get("definition", {}).get("model"),
            "status": data.get("status"),
        }

    @staticmethod
    def _extract_error_message(response: requests.Response, default: str) -> str:
        """Extract an error message from a Foundry error response."""
        try:
            data = response.json()
        except ValueError:
            return default
        if isinstance(data, dict):
            error = data.get("error")
            if isinstance(error, dict) and error.get("message"):
                return str(error["message"])
            if data.get("message"):
                return str(data["message"])
        return default


class _CredentialResolutionError(InvalidCredentialError):
    """Internal helper: signals a credential / auth problem during probe building."""

    def __init__(self, error_code: str, message: str):
        self.error_code = error_code
        super().__init__(credential_id="", message=message)
