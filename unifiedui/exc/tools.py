"""Custom exceptions for tools."""
from unifiedui.core.database.enums import ToolTypeEnum


class ToolNotFoundError(Exception):
    """Exception raised when a tool is not found."""
    
    def __init__(self, tool_id: str):
        self.tool_id = tool_id
        super().__init__(f"Tool with ID '{tool_id}' not found")


class ToolConfigValidationError(Exception):
    """Exception raised when tool configuration validation fails."""
    
    def __init__(self, message: str, errors: list = None):
        self.message = message
        self.errors = errors or []
        super().__init__(message)


class UnsupportedToolTypeError(Exception):
    """Exception raised when tool type is not supported."""
    
    def __init__(self, tool_type: str):
        self.tool_type = tool_type
        super().__init__(f"Tool type '{tool_type}' is not supported. Supported types: {ToolTypeEnum.all()}")


class InvalidToolCredentialError(Exception):
    """Exception raised when a referenced credential is invalid."""
    
    def __init__(self, credential_id: str, reason: str = "not found"):
        self.credential_id = credential_id
        self.reason = reason
        super().__init__(f"Credential '{credential_id}' is invalid: {reason}")
