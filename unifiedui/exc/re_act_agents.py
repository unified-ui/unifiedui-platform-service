"""Custom exceptions for ReACT agent versions."""


class ReActAgentVersionNotFoundError(Exception):
    """Exception raised when a ReACT agent version is not found."""

    def __init__(self, chat_agent_id: str, version: int):
        """Initialize ReActAgentVersionNotFoundError.

        Args:
            chat_agent_id: ID of the chat agent
            version: Version number that was not found
        """
        self.chat_agent_id = chat_agent_id
        self.version = version
        super().__init__(f"Version {version} of ReACT Agent '{chat_agent_id}' not found")
