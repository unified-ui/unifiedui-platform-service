"""Request schemas for authentication endpoints."""

from pydantic import BaseModel, Field


class LDAPLoginRequest(BaseModel):
    """Request body for LDAP login."""

    username: str = Field(..., min_length=1, max_length=256, description="LDAP username (uid)")
    password: str = Field(..., min_length=1, max_length=512, description="LDAP password")


class LDAPRefreshRequest(BaseModel):
    """Request body for LDAP token refresh."""

    refresh_token: str = Field(..., min_length=1, description="LDAP refresh token")


class DebugBackdoorLoginRequest(BaseModel):
    """Request body for debug backdoor login (REQ 007).

    Issues a synthetic mock JWT for the frontend to use as Bearer token.
    Only available when `enable_debug_back_door=True`.
    """

    secret: str = Field(..., min_length=32, description="Shared backdoor secret")
    user_id: str = Field(..., min_length=1, max_length=256)
    upn: str = Field(..., min_length=1, max_length=256, description="User principal name / email")
    name: str = Field("Debug User", min_length=1, max_length=256)
    groups: list[str] = Field(default_factory=list, description="Identity provider group ids")
