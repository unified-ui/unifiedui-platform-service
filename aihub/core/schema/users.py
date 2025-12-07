from pydantic import BaseModel

class IdentityProviderUserModel(BaseModel):
    provider: str
    provider_user_id: str
