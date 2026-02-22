"""On-Behalf-Of (OBO) token exchange for Microsoft Entra ID.

Exchanges a user's API-scoped access token for a Microsoft Graph access token
using the OAuth 2.0 On-Behalf-Of flow.
"""

import threading
import time

import requests

from unifiedui.logger import get_logger

logger = get_logger(__name__)


class OBOTokenExchangeClient:
    """Exchanges user tokens for Microsoft Graph tokens via OAuth 2.0 OBO flow."""

    def __init__(self, tenant_id: str, client_id: str, client_secret: str):
        """Initialize the OBO token exchange client.

        Args:
            tenant_id: Azure AD tenant ID.
            client_id: App Registration client ID.
            client_secret: App Registration client secret.
        """
        self._tenant_id = tenant_id
        self._client_id = client_id
        self._client_secret = client_secret
        self._token_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
        self._cache: dict[str, tuple[str, float]] = {}
        self._lock = threading.Lock()

    def exchange_for_graph_token(self, user_token: str) -> str:
        """Exchange a user API token for a Microsoft Graph access token.

        Args:
            user_token: The user's API-scoped access token (aud=api://{client_id}).

        Returns:
            Microsoft Graph access token.

        Raises:
            ValueError: If the token exchange fails.
        """
        cache_key = hash(user_token)

        with self._lock:
            if cache_key in self._cache:
                cached_token, expires_at = self._cache[cache_key]
                if time.time() < expires_at - 60:
                    return cached_token
                del self._cache[cache_key]

        data = {
            "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
            "client_id": self._client_id,
            "client_secret": self._client_secret,
            "assertion": user_token,
            "scope": "https://graph.microsoft.com/.default",
            "requested_token_use": "on_behalf_of",
        }

        try:
            response = requests.post(self._token_url, data=data, timeout=30)
        except requests.RequestException as e:
            raise ValueError(f"OBO token exchange request failed: {e}")

        if response.status_code != 200:
            error_data = (
                response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
            )
            error_desc = error_data.get("error_description", response.text)
            logger.warning(f"OBO token exchange failed: {error_desc}")
            raise ValueError(f"OBO token exchange failed: {error_desc}")

        token_data = response.json()
        graph_token = token_data["access_token"]
        expires_in = token_data.get("expires_in", 3600)

        with self._lock:
            self._cache[cache_key] = (graph_token, time.time() + expires_in)

        return graph_token


_obo_client_instance: OBOTokenExchangeClient | None = None


def get_obo_client() -> OBOTokenExchangeClient:
    """Get or create the singleton OBO token exchange client from settings.

    Returns:
        Configured OBOTokenExchangeClient instance.

    Raises:
        ValueError: If required OBO settings are missing.
    """
    global _obo_client_instance
    if _obo_client_instance is None:
        from unifiedui.core.config import settings

        if not settings.identity_tenant_id:
            raise ValueError("IDENTITY_TENANT_ID is required for OBO token exchange")
        if not settings.identity_client_id:
            raise ValueError("IDENTITY_CLIENT_ID is required for OBO token exchange")
        if not settings.identity_client_secret:
            raise ValueError("IDENTITY_CLIENT_SECRET is required for OBO token exchange")

        _obo_client_instance = OBOTokenExchangeClient(
            tenant_id=settings.identity_tenant_id,
            client_id=settings.identity_client_id,
            client_secret=settings.identity_client_secret,
        )
    return _obo_client_instance


def reset_obo_client() -> None:
    """Reset the singleton OBO client (for testing)."""
    global _obo_client_instance
    _obo_client_instance = None
