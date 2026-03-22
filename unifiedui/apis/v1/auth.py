"""Authentication API routes for LDAP login."""

from fastapi import APIRouter, status

from unifiedui.handlers.auth import AuthHandler
from unifiedui.schema.requests.auth import LDAPLoginRequest
from unifiedui.schema.responses.auth import LDAPLoginResponse

router = APIRouter()


@router.post(
    "/login/ldap",
    response_model=LDAPLoginResponse,
    status_code=status.HTTP_200_OK,
    summary="LDAP Login",
    description="Authenticate with LDAP username and password. Returns a signed JWT.",
)
async def ldap_login(request: LDAPLoginRequest) -> LDAPLoginResponse:
    """Authenticate via LDAP and return a signed JWT.

    Args:
        request: LDAP login request with username and password.

    Returns:
        JWT access token response.
    """
    handler = AuthHandler()
    return handler.ldap_login(request)
