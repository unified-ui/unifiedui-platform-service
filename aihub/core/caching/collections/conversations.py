from abc import ABC, abstractmethod
from aihub.core.database.models.conversations import (
    ConversationModel, ConverstionMessageModel
)


class BaseConversationsCollectionClient(ABC):
    """Abstract base class for conversation collection clients in the database."""

    @abstractmethod
    def get(self, conversation_id: str) -> ConversationModel:
        """Retrieve a conversation by its ID.

        Args:
            conversation_id (str): The ID of the conversation to retrieve.

        Returns:
            ConversationModel: The conversation data.
        """
        pass

    @abstractmethod
    def get_list(self) -> list[ConversationModel]:
        """List all conversations in the collection.

        Returns:
            list[ConversationModel]: A list of all conversations.
        """
        pass

    @abstractmethod
    def get_messages(self, conversation_id: str) -> list[ConverstionMessageModel]:
        """Retrieve all messages in a conversation.

        Args:
            conversation_id (str): The ID of the conversation.

        Returns:
            list[ConverstionMessageModel]: A list of messages in the conversation.
        """
        pass

    @abstractmethod
    def get_permissions(self, conversation_id: str) -> dict:
        """Retrieve permissions for a specific conversation.
        TODO: Define permission model.

        Args:
            conversation_id (str): The ID of the conversation.

        Returns:
            dict: The permissions associated with the conversation.
        """
        pass
