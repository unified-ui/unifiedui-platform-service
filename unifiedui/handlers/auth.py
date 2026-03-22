"""Handler for authentication operations (LDAP login with JWT issuance)."""

import time

import jwt
import ldap3

from unifiedui.core.config import settings
from unifiedui.exc.auth import InvalidCredentialsError, LDAPConnectionError
from unifiedui.logger import get_logger
from unifiedui.schema.requests.auth import LDAPLoginRequest
from unifiedui.schema.responses.auth import LDAPLoginResponse

logger = get_logger(__name__)

LDAP_TOKEN_EXPIRY_SECONDS = 3600


class AuthHandler:
    """Handler for LDAP authentication and JWT token issuance."""

    def ldap_login(self, request: LDAPLoginRequest) -> LDAPLoginResponse:
        """Authenticate a user against the LDAP directory and issue a JWT.

        Performs an LDAP bind with the provided credentials. On success,
        fetches user attributes and signs a JWT for use as a Bearer token.

        Args:
            request: LDAP login request with username and password.

        Returns:
            Login response with signed JWT access token.

        Raises:
            LDAPConnectionError: If the LDAP server is unreachable.
            InvalidCredentialsError: If username or password is wrong.
            ValueError: If LDAP or JWT settings are not configured.
        """
        if not settings.ldap_server_url:
            raise LDAPConnectionError("LDAP_SERVER_URL is not configured")
        if not settings.ldap_jwt_secret:
            raise LDAPConnectionError("LDAP_JWT_SECRET is not configured")

        server = ldap3.Server(
            settings.ldap_server_url,
            use_ssl=settings.ldap_use_ssl,
            get_info=ldap3.NONE,
        )

        search_base = settings.ldap_base_dn or ""
        search_filter = settings.ldap_user_search_filter or "(objectClass=person)"
        user_filter = f"(&{search_filter}(uid={ldap3.utils.conv.escape_filter_chars(request.username)}))"

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
                logger.warning("LDAP user not found: %s", request.username)
                raise InvalidCredentialsError()

            entry = svc_conn.entries[0]
            user_dn = str(entry.entry_dn)
            user_attrs: dict[str, str] = {
                "uid": str(entry.uid) if hasattr(entry, "uid") else request.username,
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
                password=request.password,
                auto_bind=True,
                raise_exceptions=True,
            )
            user_conn.unbind()
        except (ldap3.core.exceptions.LDAPBindError, ldap3.core.exceptions.LDAPInvalidCredentialsResult):
            logger.warning("LDAP bind failed for user: %s", request.username)
            raise InvalidCredentialsError()
        except ldap3.core.exceptions.LDAPSocketOpenError as e:
            logger.error("LDAP server unreachable: %s", e)
            raise LDAPConnectionError(f"Cannot connect to LDAP server: {settings.ldap_server_url}")

        now = int(time.time())
        claims = {
            "sub": user_attrs.get("entryUUID") or user_attrs.get("uid", request.username),
            "uid": user_attrs.get("uid", request.username),
            "cn": user_attrs.get("cn", ""),
            "sn": user_attrs.get("sn", ""),
            "givenName": user_attrs.get("givenName", ""),
            "mail": user_attrs.get("mail", ""),
            "dn": user_dn,
            "o": settings.ldap_base_dn or "",
            "iss": settings.ldap_server_url,
            "iat": now,
            "exp": now + LDAP_TOKEN_EXPIRY_SECONDS,
        }

        token = jwt.encode(claims, settings.ldap_jwt_secret, algorithm="HS256")

        logger.info("LDAP login successful for user: %s", request.username)

        return LDAPLoginResponse(
            access_token=token,
            expires_in=LDAP_TOKEN_EXPIRY_SECONDS,
        )
