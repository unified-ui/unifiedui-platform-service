"""Custom exceptions for chat agent configuration validation."""


class ChatAgentConfigValidationError(Exception):
    """Exception raised when chat agent configuration validation fails."""

    def __init__(self, message: str, errors: list | None = None):
        self.message = message
        self.errors = errors or []
        super().__init__(message)


class UnsupportedChatAgentTypeError(Exception):
    """Exception raised when chat agent type is not supported for config validation."""

    def __init__(self, chat_agent_type: str):
        self.chat_agent_type = chat_agent_type
        super().__init__(f"Chat agent type '{chat_agent_type}' is not supported for config validation")


class InvalidCredentialError(Exception):
    """Exception raised when a credential is invalid or cannot be fetched."""

    def __init__(self, credential_id: str, message: str | None = None):
        self.credential_id = credential_id
        self.message = message or f"Invalid or inaccessible credential with ID '{credential_id}'"
        super().__init__(self.message)


class InvalidAIModelReferenceError(Exception):
    """Exception raised when a referenced AI model does not exist or is inactive."""

    def __init__(self, ai_model_id: str, message: str | None = None):
        self.ai_model_id = ai_model_id
        self.message = message or f"AI model with ID '{ai_model_id}' not found or inactive"
        super().__init__(self.message)
