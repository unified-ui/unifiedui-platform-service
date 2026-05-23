"""Custom exceptions for permission operations."""


class PermissionError(Exception):
    """Base exception for permission-related errors."""

    pass


class PermissionDeniedError(PermissionError):
    """Exception raised when user doesn't have required permission."""

    def __init__(
        self,
        resource_type: str,
        resource_id: str,
        action: str,
        required_roles: list[str] | None = None,
        user_roles: list[str] | None = None,
    ):
        self.resource_type = resource_type
        self.resource_id = resource_id
        self.action = action
        self.required_roles = required_roles or []
        self.user_roles = user_roles or []
        super().__init__(f"Permission denied: Missing '{action}' permission on {resource_type}/{resource_id}")
