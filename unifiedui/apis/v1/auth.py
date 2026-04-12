"""Authentication API routes for LDAP login and token refresh."""

from fastapi import APIRouter, status

from unifiedui.handlers.auth import AuthHandler
from unifiedui.schema.requests.auth import LDAPLoginRequest, LDAPRefreshRequest
from unifiedui.schema.responses.auth import LDAPLoginResponse

router = APIRouter()


@router.post(
    "/login/ldap",
    response_model=LDAPLoginResponse,
    status_code=status.HTTP_200_OK,
    summary="LDAP Login",
    description="Authenticate with LDAP username and password. Returns access and refresh tokens.",
)
async def ldap_login(request: LDAPLoginRequest) -> LDAPLoginResponse:
    """Authenticate via LDAP and return access and refresh tokens.

    Args:
        request: LDAP login request with username and password.

    Returns:
        JWT access token and refresh token response.
    """
    handler = AuthHandler()
    return handler.ldap_login(request)


@router.post(
    "/refresh/ldap",
    response_model=LDAPLoginResponse,
    status_code=status.HTTP_200_OK,
    summary="LDAP Token Refresh",
    description="Exchange a valid refresh token for new access and refresh tokens.",
)
async def ldap_refresh(request: LDAPRefreshRequest) -> LDAPLoginResponse:
    """Exchange a refresh token for new access and refresh tokens.

    Args:
        request: Refresh request containing the refresh token.

    Returns:
        New JWT access token and refresh token response.
    """
    handler = AuthHandler()
    return handler.ldap_refresh(request)
