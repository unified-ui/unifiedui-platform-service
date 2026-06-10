"""Custom exceptions for external app configuration validation."""


class ExternalAppConfigValidationError(Exception):
    """Exception raised when external app configuration validation fails."""

    def __init__(self, message: str, errors: list | None = None):
        self.message = message
        self.errors = errors or []
        super().__init__(message)


class UnsupportedExternalAppModeError(Exception):
    """Exception raised when an external app configuration mode is not supported."""

    def __init__(self, mode: str):
        self.mode = mode
        super().__init__(f"External app mode '{mode}' is not supported")
