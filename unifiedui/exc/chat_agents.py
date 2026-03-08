"""Custom exception for chat agents."""


class ChatAgentNotFoundError(Exception):
    """Exception raised when a chat agent is not found."""

    def __init__(self, chat_agent_id: str):
        self.chat_agent_id = chat_agent_id
        super().__init__(f"Chat agent with ID '{chat_agent_id}' not found")
