from abc import ABC, abstractmethod

from aihub.core.caching.collections.applications import BaseApplicationsCollectionCache
from aihub.core.caching.collections.autonomous_agents import BaseAutonomousAgentsCollectionCache
from aihub.core.caching.collections.conversations import BaseConversationsCollectionClient
from aihub.core.caching.collections.custom_groups import BaseCustomGroupsCollectionClient


class CollectionsCacheClient(ABC):
    """Abstract base class for collections cache clients."""

    @abstractmethod
    def applications(self) -> BaseApplicationsCollectionCache:
        """Retrieve a collection by its ID."""
        pass

    @abstractmethod
    def autonomous_agents(self) -> BaseAutonomousAgentsCollectionCache:
        """Retrieve a collection by its ID."""
        pass

    @abstractmethod
    def conversations(self) -> BaseConversationsCollectionClient:
        """Retrieve a collection by its ID."""
        pass

    @abstractmethod
    def custom_groups(self) -> BaseCustomGroupsCollectionClient:
        """Retrieve a collection by its ID."""
        pass
