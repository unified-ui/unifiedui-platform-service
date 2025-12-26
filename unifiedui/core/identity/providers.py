from abc import ABC, abstractmethod
from enum import Enum

from unifiedui.utils.api_query import APIFilterQuery
from unifiedui.schema.responses.identity import IdentityGroupResponse, IdentityUserResponse


class BaseIdentityToken(ABC):
    def __init__(self, token: str, deserialized_token: dict):
        self.token = token
        self.deserialized_token = deserialized_token

    @abstractmethod
    def get_id(self) -> str:
        pass

    @abstractmethod
    def get_identity_tenant_id(self) -> str:
        pass

    @abstractmethod
    def get_display_name(self) -> str:
        pass

    @abstractmethod
    def get_firstname(self) -> str:
        pass

    @abstractmethod
    def get_lastname(self) -> str:
        pass

    @abstractmethod
    def get_mail(self) -> str:
        pass

    @abstractmethod
    def get_identity_provider(self) -> str:
        pass

    def to_dict(self) -> dict:
        return {
            "identity_provider": self.get_identity_provider(),
            "id": self.get_id(),
            "tenant_id": self.get_identity_tenant_id(),
            "display_name": self.get_display_name(),
            "firstname": self.get_firstname(),
            "lastname": self.get_lastname(),
            "mail": self.get_mail()
        }


class BaseIdentityProvider(ABC):
    """Base class for identity provider implementations."""
    def __init__(self, identity_token: BaseIdentityToken):
        self.identity_token = identity_token

    @abstractmethod
    def get_current_user_security_groups(
        self,
        query: APIFilterQuery | None = None
    ) -> list[IdentityGroupResponse]:
        """Get security groups for the current user."""
        pass

    @abstractmethod
    def get_security_groups(
        self,
        query: APIFilterQuery | None = None
    ) -> tuple[list[IdentityGroupResponse], str | None]:
        """
        Get all security groups from the directory.
        
        Args:
            identity_token: User's identity token
            query: Query parameters (search, top, next_link)
            
        Returns:
            Tuple of (list of security groups, next_link)
        """
        pass

    @abstractmethod
    def get_users(
        self,
        query: APIFilterQuery | None = None
    ) -> tuple[list[IdentityUserResponse], str | None]:
        """
        Get users from the directory.
        
        Args:
            identity_token: User's identity token
            query: Query parameters (search, top, next_link)
            
        Returns:
            Tuple of (list of users, next_link)
        """
        pass

    @abstractmethod
    def get_user_by_id(self, user_id: str) -> IdentityUserResponse:
        """Get a specific user by ID."""
        pass

    @abstractmethod
    def get_group_by_id(self, group_id: str) -> IdentityGroupResponse:
        """Get a specific group by ID."""
        pass

    @abstractmethod
    def get_principal_name(self, principal_id: str, principal_type: str) -> str:
        """
        Get the principal name for a user or group.
        
        For users, this typically returns the userPrincipalName or mail.
        For groups, this returns the display name.
        
        Args:
            principal_id: The ID of the principal
            principal_type: The type of principal (IDENTITY_USER or IDENTITY_GROUP)
            
        Returns:
            The principal name string
        """
        pass
