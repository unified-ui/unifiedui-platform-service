"""Custom exceptions for permission operations."""


class PermissionError(Exception):
    """Base exception for permission-related errors."""

    pass


class PermissionDeniedError(PermissionError):
    """Exception raised when user doesn't have required permission."""

    def __init__(self, resource_type: str, resource_id: str, action: str):
        self.resource_type = resource_type
        self.resource_id = resource_id
        self.action = action
        super().__init__(f"Permission denied: Missing '{action}' permission on {resource_type}/{resource_id}")
