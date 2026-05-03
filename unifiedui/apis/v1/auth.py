"""Authentication API routes for LDAP login and token refresh."""

from fastapi import APIRouter, HTTPException, status

from unifiedui.core.config import settings
from unifiedui.handlers.auth import AuthHandler
from unifiedui.identity.mock.token import MockIdentityToken
from unifiedui.logger import get_logger
from unifiedui.schema.requests.auth import DebugBackdoorLoginRequest, LDAPLoginRequest, LDAPRefreshRequest
from unifiedui.schema.responses.auth import DebugBackdoorLoginResponse, LDAPLoginResponse

logger = get_logger(__name__)

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


@router.post(
    "/debug-backdoor",
    response_model=DebugBackdoorLoginResponse,
    status_code=status.HTTP_200_OK,
    summary="Debug Backdoor Login (REQ 007)",
    description=(
        "Issue a synthetic mock JWT for E2E testing / self-debugging. "
        "Only available when `ENABLE_DEBUG_BACK_DOOR=true` AND deployment_mode != 'production'."
    ),
)
async def debug_backdoor_login(request: DebugBackdoorLoginRequest) -> DebugBackdoorLoginResponse:
    """Issue a synthetic JWT for the debug backdoor.

    Args:
        request: Backdoor login payload with shared secret and synthetic identity.

    Returns:
        Bearer access token wrapping a `MockIdentityToken`.

    Raises:
        HTTPException: 404 when backdoor disabled, 401 when secret mismatched.
    """
    if not settings.enable_debug_back_door:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Debug backdoor is not enabled")

    if not settings.debug_back_door_secret or request.secret != settings.debug_back_door_secret:
        logger.warning("Debug backdoor login attempt with invalid secret for upn=%s", request.upn)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid debug backdoor secret")

    token = MockIdentityToken(
        user_id=request.user_id,
        name=request.name,
        mail=request.upn,
        idp_groups=request.groups,
    )
    logger.warning(
        "DEBUG BACKDOOR LOGIN issued synthetic JWT",
        extra={"user_id": request.user_id, "upn": request.upn, "groups": request.groups},
    )

    return DebugBackdoorLoginResponse(
        access_token=token.get_token(),
        expires_in=36000,
        user_id=request.user_id,
        upn=request.upn,
    )
