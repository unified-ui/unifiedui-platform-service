from abc import ABC, abstractmethod


class BaseGroup:
    id: str
    name: str


class BaseIdentityTokenSerializer(ABC):
    def __init__(self, token: str, deserialized_token: dict):
        self.token = token
        self.deserialized_token = deserialized_token

    @abstractmethod
    def get_id(self) -> str:
        pass

    @abstractmethod
    def get_tenant_id(self) -> str:
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
            "tenant_id": self.get_tenant_id(),
            "display_name": self.get_display_name(),
            "firstname": self.get_firstname(),
            "lastname": self.get_lastname(),
            "mail": self.get_mail()
        }
