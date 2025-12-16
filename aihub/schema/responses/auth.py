from pydantic import BaseModel


class UserIdentityResponse(BaseModel):
    """User identity response model."""
    id: str
    tenant_id: str
    display_name: str
    firstname: str
    lastname: str
