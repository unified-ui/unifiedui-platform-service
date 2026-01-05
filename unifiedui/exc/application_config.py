"""Custom exceptions for application configuration validation."""


class ApplicationConfigValidationError(Exception):
    """Exception raised when application configuration validation fails."""
    
    def __init__(self, message: str, errors: list = None):
        self.message = message
        self.errors = errors or []
        super().__init__(message)


class UnsupportedApplicationTypeError(Exception):
    """Exception raised when application type is not supported for config validation."""
    
    def __init__(self, application_type: str):
        self.application_type = application_type
        super().__init__(f"Application type '{application_type}' is not supported for config validation")


class InvalidCredentialError(Exception):
    """Exception raised when a credential is invalid or cannot be fetched."""
    
    def __init__(self, credential_id: str, message: str = None):
        self.credential_id = credential_id
        self.message = message or f"Invalid or inaccessible credential with ID '{credential_id}'"
        super().__init__(self.message)
