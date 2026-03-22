"""Handler for authentication operations (LDAP login with JWT issuance)."""

import time

import jwt
import ldap3
from jwt.exceptions import InvalidTokenError

from unifiedui.core.config import settings
from unifiedui.exc.auth import InvalidCredentialsError, InvalidRefreshTokenError, LDAPConnectionError
from unifiedui.logger import get_logger
from unifiedui.schema.requests.auth import LDAPLoginRequest, LDAPRefreshRequest
from unifiedui.schema.responses.auth import LDAPLoginResponse

logger = get_logger(__name__)


class AuthHandler:
    """Handler for LDAP authentication and JWT token issuance."""

    def ldap_login(self, request: LDAPLoginRequest) -> LDAPLoginResponse:
        """Authenticate a user against the LDAP directory and issue token pair.

        Performs an LDAP bind with the provided credentials. On success,
        fetches user attributes and issues an access token + refresh token.

        Args:
            request: LDAP login request with username and password.

        Returns:
            Login response with access token and refresh token.

        Raises:
            LDAPConnectionError: If the LDAP server is unreachable.
            InvalidCredentialsError: If username or password is wrong.
        """
        self._validate_ldap_config()
        user_attrs, user_dn = self._authenticate_ldap_user(request.username, request.password)

        access_token, refresh_token = self._create_token_pair(user_attrs, user_dn)

        logger.info("LDAP login successful for user: %s", request.username)

        return LDAPLoginResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=settings.ldap_access_token_expiry_seconds,
        )

    def ldap_refresh(self, request: LDAPRefreshRequest) -> LDAPLoginResponse:
        """Exchange a valid refresh token for a new access/refresh token pair.

        Args:
            request: Refresh request containing the refresh token.

        Returns:
            New login response with fresh access token and refresh token.

        Raises:
            InvalidRefreshTokenError: If the refresh token is invalid or expired.
        """
        self._validate_ldap_config()

        if not settings.ldap_jwt_refresh_secret:
            raise LDAPConnectionError("LDAP_JWT_REFRESH_SECRET is not configured")

        try:
            claims: dict = jwt.decode(
                request.refresh_token,
                settings.ldap_jwt_refresh_secret,
                algorithms=["HS256"],
            )
        except InvalidTokenError:
            raise InvalidRefreshTokenError()

        if claims.get("token_type") != "refresh":
            raise InvalidRefreshTokenError()

        user_attrs = {
            "uid": claims.get("uid", ""),
            "cn": claims.get("cn", ""),
            "sn": claims.get("sn", ""),
            "givenName": claims.get("givenName", ""),
            "mail": claims.get("mail", ""),
            "entryUUID": claims.get("sub", ""),
        }
        user_dn = claims.get("dn", "")

        access_token, refresh_token = self._create_token_pair(user_attrs, user_dn)

        logger.info("LDAP token refresh successful for user: %s", claims.get("uid", "unknown"))

        return LDAPLoginResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=settings.ldap_access_token_expiry_seconds,
        )

    def _validate_ldap_config(self) -> None:
        """Validate that required LDAP configuration is present.

        Raises:
            LDAPConnectionError: If required settings are missing.
        """
        if not settings.ldap_server_url:
            raise LDAPConnectionError("LDAP_SERVER_URL is not configured")
        if not settings.ldap_jwt_secret:
            raise LDAPConnectionError("LDAP_JWT_SECRET is not configured")

    def _authenticate_ldap_user(self, username: str, password: str) -> tuple[dict[str, str], str]:
        """Authenticate user against LDAP and return attributes and DN.

        Args:
            username: LDAP uid of the user.
            password: User's password.

        Returns:
            Tuple of (user_attrs dict, user_dn string).

        Raises:
            LDAPConnectionError: If the LDAP server is unreachable.
            InvalidCredentialsError: If credentials are invalid.
        """
        server = ldap3.Server(
            settings.ldap_server_url,
            use_ssl=settings.ldap_use_ssl,
            get_info=ldap3.NONE,
        )

        search_base = settings.ldap_base_dn or ""
        search_filter = settings.ldap_user_search_filter or "(objectClass=person)"
        user_filter = f"(&{search_filter}(uid={ldap3.utils.conv.escape_filter_chars(username)}))"

        try:
            svc_conn = ldap3.Connection(
                server,
                user=settings.ldap_bind_dn,
                password=settings.ldap_bind_password,
                auto_bind=True,
                raise_exceptions=True,
            )
        except ldap3.core.exceptions.LDAPSocketOpenError as e:
            logger.error("LDAP server unreachable: %s", e)
            raise LDAPConnectionError(f"Cannot connect to LDAP server: {settings.ldap_server_url}")
        except ldap3.core.exceptions.LDAPBindError as e:
            logger.error("LDAP service account bind failed: %s", e)
            raise LDAPConnectionError("LDAP service account authentication failed")

        try:
            svc_conn.search(
                search_base=search_base,
                search_filter=user_filter,
                search_scope=ldap3.SUBTREE,
                attributes=["uid", "cn", "sn", "givenName", "mail", "entryUUID"],
            )
        except ldap3.core.exceptions.LDAPOperationResult as e:
            logger.error("LDAP search failed (base=%s): %s", search_base, e)
            svc_conn.unbind()
            raise LDAPConnectionError(f"LDAP search failed — check LDAP_BIND_DN and LDAP_BASE_DN: {e.description}")

        try:
            if not svc_conn.entries:
                logger.warning("LDAP user not found: %s", username)
                raise InvalidCredentialsError()

            entry = svc_conn.entries[0]
            user_dn = str(entry.entry_dn)
            user_attrs: dict[str, str] = {
                "uid": str(entry.uid) if hasattr(entry, "uid") else username,
                "cn": str(entry.cn) if hasattr(entry, "cn") else "",
                "sn": str(entry.sn) if hasattr(entry, "sn") else "",
                "givenName": str(entry.givenName) if hasattr(entry, "givenName") else "",
                "mail": str(entry.mail) if hasattr(entry, "mail") else "",
                "entryUUID": str(entry.entryUUID) if hasattr(entry, "entryUUID") else "",
            }
        finally:
            svc_conn.unbind()

        try:
            user_conn = ldap3.Connection(
                server,
                user=user_dn,
                password=password,
                auto_bind=True,
                raise_exceptions=True,
            )
            user_conn.unbind()
        except (ldap3.core.exceptions.LDAPBindError, ldap3.core.exceptions.LDAPInvalidCredentialsResult):
            logger.warning("LDAP bind failed for user: %s", username)
            raise InvalidCredentialsError()
        except ldap3.core.exceptions.LDAPSocketOpenError as e:
            logger.error("LDAP server unreachable: %s", e)
            raise LDAPConnectionError(f"Cannot connect to LDAP server: {settings.ldap_server_url}")

        return user_attrs, user_dn

    def _create_token_pair(self, user_attrs: dict[str, str], user_dn: str) -> tuple[str, str]:
        """Create an access token and refresh token pair.

        Args:
            user_attrs: LDAP user attributes.
            user_dn: LDAP distinguished name.

        Returns:
            Tuple of (access_token, refresh_token).
        """
        jwt_secret = settings.ldap_jwt_secret
        if not jwt_secret:
            raise LDAPConnectionError("LDAP_JWT_SECRET is not configured")

        now = int(time.time())
        base_claims = {
            "sub": user_attrs.get("entryUUID") or user_attrs.get("uid", ""),
            "uid": user_attrs.get("uid", ""),
            "cn": user_attrs.get("cn", ""),
            "sn": user_attrs.get("sn", ""),
            "givenName": user_attrs.get("givenName", ""),
            "mail": user_attrs.get("mail", ""),
            "dn": user_dn,
            "o": settings.ldap_base_dn or "",
            "iss": settings.ldap_server_url,
        }

        access_claims = {
            **base_claims,
            "token_type": "access",
            "iat": now,
            "exp": now + settings.ldap_access_token_expiry_seconds,
        }
        access_token = jwt.encode(access_claims, jwt_secret, algorithm="HS256")

        refresh_secret = settings.ldap_jwt_refresh_secret or jwt_secret
        refresh_claims = {
            **base_claims,
            "token_type": "refresh",
            "iat": now,
            "exp": now + settings.ldap_refresh_token_expiry_seconds,
        }
        refresh_token = jwt.encode(refresh_claims, refresh_secret, algorithm="HS256")

        return access_token, refresh_token
