"""Custom exception for conversations."""


class ConversationNotFoundError(Exception):
    """Exception raised when a conversation is not found."""

    def __init__(self, conversation_id: str):
        self.conversation_id = conversation_id
        super().__init__(f"Conversation with ID '{conversation_id}' not found")


class FoundryConversationCreationError(Exception):
    """Exception raised when creating a conversation in Microsoft Foundry fails."""

    def __init__(self, message: str, status_code: int | None = None):
        self.message = message
        self.status_code = status_code
        super().__init__(message)
