"""Custom exceptions for tenant AI models."""


class TenantAIModelNotFoundError(Exception):
    """Exception raised when a tenant AI model is not found."""

    def __init__(self, model_id: str):
        """Initialize the exception.

        Args:
            model_id: The ID of the AI model that was not found.
        """
        self.model_id = model_id
        super().__init__(f"Tenant AI model with ID '{model_id}' not found")


class TenantAIModelConfigValidationError(Exception):
    """Exception raised when AI model config validation fails."""

    def __init__(self, message: str):
        """Initialize the exception.

        Args:
            message: Description of the validation error.
        """
        self.message = message
        super().__init__(message)


class UnsupportedAIModelProviderError(Exception):
    """Exception raised when an unsupported AI model provider is used."""

    def __init__(self, provider: str):
        """Initialize the exception.

        Args:
            provider: The unsupported provider name.
        """
        self.provider = provider
        super().__init__(f"AI model provider '{provider}' is not supported")


class InvalidAIModelCredentialError(Exception):
    """Exception raised when the credential for an AI model is invalid."""

    def __init__(self, credential_id: str):
        """Initialize the exception.

        Args:
            credential_id: The ID of the invalid credential.
        """
        self.credential_id = credential_id
        super().__init__(f"Credential with ID '{credential_id}' not found or invalid for AI model")
