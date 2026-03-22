"""Request schemas for authentication endpoints."""

from pydantic import BaseModel, Field


class LDAPLoginRequest(BaseModel):
    """Request body for LDAP login."""

    username: str = Field(..., min_length=1, max_length=256, description="LDAP username (uid)")
    password: str = Field(..., min_length=1, max_length=512, description="LDAP password")
