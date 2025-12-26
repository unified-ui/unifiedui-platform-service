"""Custom exception for conversations."""


class ConversationNotFoundError(Exception):
    """Exception raised when a conversation is not found."""
    
    def __init__(self, conversation_id: str):
        self.conversation_id = conversation_id
        super().__init__(f"Conversation with ID '{conversation_id}' not found")
