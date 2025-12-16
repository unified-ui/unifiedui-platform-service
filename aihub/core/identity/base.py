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
