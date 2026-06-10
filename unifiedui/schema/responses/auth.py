"""Response schemas for authentication endpoints."""

from pydantic import BaseModel


class LDAPLoginResponse(BaseModel):
    """Response body for successful LDAP login."""

    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int


class DebugBackdoorLoginResponse(BaseModel):
    """Response body for the debug backdoor login (REQ 007)."""

    access_token: str
    token_type: str = "Bearer"
    expires_in: int
    user_id: str
    upn: str
    debug: bool = True
