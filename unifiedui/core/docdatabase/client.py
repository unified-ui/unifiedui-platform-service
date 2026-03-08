'''
from abc import ABC, abstractmethod
from typing import Any, Optional

from unifiedui.core.database.collections.chat_agents import BaseChatAgentsCollectionClient

class BaseDatabaseClient(ABC):
    """Abstract base class for database clients."""

    @property
    @abstractmethod
    def chat_agents(self) -> BaseChatAgentsCollectionClient:
        """Access the chat agents collection client.

        Returns:
            BaseChatAgentsCollectionClient: The chat agents collection client.
        """
        pass
'''
