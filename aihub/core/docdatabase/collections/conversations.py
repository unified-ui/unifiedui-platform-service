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
    def create(self, conversation: ConversationModel) -> ConversationModel:
        """Create a new conversation in the collection.

        Args:
            conversation (ConversationModel): The conversation data to create.
        Returns:
            ConversationModel: The created conversation.
        """
        pass

    @abstractmethod
    def update(
            self,
            conversation_id: str,
            conversation: ConversationModel
    ) -> ConversationModel:
        """Update an existing conversation in the collection (PATCH).

        Args:
            conversation_id (str): The ID of the conversation to update.
            conversation (ConversationModel): The new conversation data.

        Returns:
            ConversationModel: The updated conversation.
        """
        pass

    @abstractmethod
    def delete(self, conversation_id: str) -> None:
        """Delete a conversation from the collection.

        Args:
            conversation_id (str): The ID of the conversation to delete.
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
    def update_message(
            self,
            conversation_id: str,
            message: ConverstionMessageModel
    ) -> ConverstionMessageModel:
        """Update a specific message in a conversation.

        Note: Regular users may only modify their own user messages.
        System-level accounts with elevated permissions can modify assistant messages.

        Args:
            conversation_id (str): The ID of the conversation.
            message_id (str): The ID of the message to update.
            message_data (ConverstionMessageModel): The updated message data.

        Returns:
            ConverstionMessageModel: The updated message.
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
