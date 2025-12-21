import jwt
import time
from datetime import datetime, timedelta
from aihub.core.identity.providers import BaseIdentityToken
from aihub.core.identity.enums import IdenityProviderEnum


class MockIdentityToken(BaseIdentityToken):
    """Mock identity token for testing."""
    
    def __init__(self, user_id: str, name: str = "Test User", mail: str = None, idp_groups: list[str] = None):
        # Create a mock JWT token
        now = int(time.time())
        exp_time = now + 36000
        
        payload = {
            "iss": "https://mock.identity.provider/test",
            "oid": user_id,
            "tid": "test-tenant-123",
            "name": name,
            "given_name": name.split()[0] if " " in name else name,
            "family_name": name.split()[1] if " " in name and len(name.split()) > 1 else "",
            "mail": mail or f"{user_id}@test.com",
            "groups": idp_groups or [],  # Add groups to token payload
            "iat": now,
            "exp": exp_time
        }
        
        # Create JWT token (unsigned for testing)
        token = jwt.encode(payload, "test-secret", algorithm="HS256")
        
        self._identity_provider = IdenityProviderEnum.MOCK.value
        super().__init__(token, payload)
    
    def get_token(self) -> str:
        return self.token
    
    def get_deserialized_token(self) -> dict:
        return self.deserialized_token
    
    def get_id(self) -> str:
        return self.deserialized_token.get("oid")
    
    def get_identity_tenant_id(self) -> str:
        return self.deserialized_token.get("tid", "")
    
    def get_display_name(self) -> str:
        return self.deserialized_token.get("name", "")
    
    def get_firstname(self) -> str:
        return self.deserialized_token.get("given_name", "")
    
    def get_lastname(self) -> str:
        return self.deserialized_token.get("family_name", "")
    
    def get_mail(self) -> str:
        return self.deserialized_token.get("mail", "")
    
    def get_identity_provider(self) -> str:
        return self._identity_provider
    
    def get_groups(self) -> list[str]:
        """Get user's group memberships."""
        return self.deserialized_token.get("groups", [])
