"""Debug backdoor helper for E2E testing and self-debugging.

This module is part of REQ 007 — Debug Backdoor. It allows requests with the
correct shared secret + debug headers to bypass real OAuth/JWT validation by
synthesising a `MockIdentityToken`. The synthesised token then flows through the
normal authentication pipeline unchanged, so RBAC and tenant checks still apply.

Strict guardrails:
- Only active when `settings.enable_debug_back_door=True`
- Required header `X-Debug-Backdoor` must match `settings.debug_back_door_secret`
- App refuses to start in production with the backdoor enabled
- Each backdoor request is logged at WARNING level

NEVER use in production.
"""

from __future__ import annotations

from fastapi import HTTPException, Request, status

from unifiedui.core.config import settings
from unifiedui.identity.mock.token import MockIdentityToken
from unifiedui.logger import get_logger

logger = get_logger(__name__)

DEBUG_HEADER_SECRET = "X-Debug-Backdoor"
DEBUG_HEADER_USER_ID = "X-Debug-User-Id"
DEBUG_HEADER_USER_UPN = "X-Debug-User-Upn"
DEBUG_HEADER_USER_NAME = "X-Debug-User-Name"
DEBUG_HEADER_TENANT_ID = "X-Debug-Tenant-Id"
DEBUG_HEADER_ROLES = "X-Debug-Roles"
DEBUG_HEADER_GROUPS = "X-Debug-Groups"


def is_backdoor_enabled() -> bool:
    """Return True when backdoor is enabled via settings."""
    return bool(settings.enable_debug_back_door)


def has_backdoor_headers(request: Request) -> bool:
    """Return True when the request carries the backdoor secret header.

    Used to short-circuit normal Bearer-token validation only when the caller
    explicitly opts in via header.
    """
    return request.headers.get(DEBUG_HEADER_SECRET) is not None


def build_backdoor_token(request: Request) -> str:
    """Validate backdoor headers and build a synthetic MockIdentityToken JWT.

    Args:
        request: Incoming FastAPI request with debug headers.

    Returns:
        Encoded JWT string ready to be passed to ContextIdentityUser.

    Raises:
        HTTPException: 401 when backdoor disabled, secret mismatched, or
            required identity headers missing.
    """
    if not is_backdoor_enabled():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Debug backdoor is not enabled on this service",
        )

    provided_secret = request.headers.get(DEBUG_HEADER_SECRET)
    expected_secret = settings.debug_back_door_secret
    if not expected_secret or provided_secret != expected_secret:
        logger.warning(
            "Debug backdoor secret mismatch",
            extra={
                "endpoint": str(request.url.path),
                "method": request.method,
                "client_ip": _client_ip(request),
            },
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid debug backdoor secret",
        )

    user_id = request.headers.get(DEBUG_HEADER_USER_ID)
    upn = request.headers.get(DEBUG_HEADER_USER_UPN)
    if not user_id or not upn:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Debug backdoor requires {DEBUG_HEADER_USER_ID} and {DEBUG_HEADER_USER_UPN} headers",
        )

    name = request.headers.get(DEBUG_HEADER_USER_NAME, "Debug User")
    groups_raw = request.headers.get(DEBUG_HEADER_GROUPS, "")
    idp_groups = [g.strip() for g in groups_raw.split(",") if g.strip()]

    log_backdoor_use(request, user_id=user_id, upn=upn)

    token = MockIdentityToken(
        user_id=user_id,
        name=name,
        mail=upn,
        idp_groups=idp_groups,
    )
    return token.get_token()


def log_backdoor_use(request: Request, user_id: str, upn: str) -> None:
    """Emit a WARNING log every time the backdoor authenticates a request."""
    logger.warning(
        "DEBUG BACKDOOR USED — synthetic auth bypass",
        extra={
            "user_id": user_id,
            "upn": upn,
            "endpoint": str(request.url.path),
            "method": request.method,
            "client_ip": _client_ip(request),
            "user_agent": request.headers.get("User-Agent", ""),
        },
    )


def _client_ip(request: Request) -> str:
    """Extract a best-effort client IP from common proxy headers."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return ""
