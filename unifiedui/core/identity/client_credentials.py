"""Client Credentials flow for Microsoft Entra ID.

Acquires an application-level access token using the OAuth 2.0
client credentials grant.
"""

import threading
import time

import requests

from unifiedui.logger import get_logger

logger = get_logger(__name__)


class ClientCredentialsTokenClient:
    """Acquires app-level tokens via OAuth 2.0 client credentials grant."""

    def __init__(self, tenant_id: str, client_id: str, client_secret: str):
        """Initialize the client credentials token client.

        Args:
            tenant_id: Azure AD tenant ID of the app registration.
            client_id: App Registration client ID.
            client_secret: App Registration client secret.
        """
        self._tenant_id = tenant_id
        self._client_id = client_id
        self._client_secret = client_secret
        self._token_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
        self._cache: dict[str, tuple[str, float]] = {}
        self._lock = threading.Lock()

    def acquire_token(self, scope: str = "https://graph.microsoft.com/.default") -> str:
        """Acquire an access token using client credentials flow.

        Args:
            scope: The scope to request. Defaults to Microsoft Graph.

        Returns:
            Access token string.

        Raises:
            ValueError: If the token acquisition fails.
        """
        cache_key = f"{self._client_id}:{scope}"

        with self._lock:
            if cache_key in self._cache:
                cached_token, expires_at = self._cache[cache_key]
                if time.time() < expires_at:
                    return cached_token
                del self._cache[cache_key]

        data = {
            "grant_type": "client_credentials",
            "client_id": self._client_id,
            "client_secret": self._client_secret,
            "scope": scope,
        }

        try:
            response = requests.post(self._token_url, data=data, timeout=30)
        except requests.RequestException as e:
            raise ValueError(f"Client credentials token request failed: {e}")

        if response.status_code != 200:
            error_data = (
                response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
            )
            error_desc = error_data.get("error_description", response.text)
            logger.warning("Client credentials token acquisition failed: %s", error_desc)
            raise ValueError(f"Client credentials token acquisition failed: {error_desc}")

        token_data = response.json()
        access_token = token_data["access_token"]
        expires_in = token_data.get("expires_in", 3600)

        with self._lock:
            self._cache[cache_key] = (access_token, time.time() + expires_in - 60)

        return access_token
