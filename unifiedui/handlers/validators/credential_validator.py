"""Credential validation logic."""

import json
from enum import StrEnum

from pydantic import BaseModel, Field

from unifiedui.logger import get_logger

logger = get_logger(__name__)


class CredentialTypeEnum(StrEnum):
    """Supported credential types."""

    API_KEY = "API_KEY"
    BASIC_AUTH = "BASIC_AUTH"
    OPENAPI_CONNECTION = "OPENAPI_CONNECTION"
    AI_MODEL_PROVIDER = "AI_MODEL_PROVIDER"
    ENTRA_ID_APP_REGISTRATION = "ENTRA_ID_APP_REGISTRATION"

    @classmethod
    def all(cls) -> list[str]:
        return [v.value for v in cls]


class BasicAuthCredential(BaseModel):
    """Pydantic model for BASIC_AUTH credential validation."""

    username: str = Field(..., min_length=1, description="Username for basic auth")
    password: str = Field(..., min_length=1, description="Password for basic auth")


class OpenAPIConnectionCredential(BaseModel):
    """Pydantic model for OPENAPI_CONNECTION credential validation."""

    key: str = Field(..., min_length=1, description="API header key (e.g., 'x-api-key')")
    value: str = Field(..., min_length=1, description="API key value")
    password: str = Field(..., min_length=1, description="Password for basic auth")


class AIModelProviderCredential(BaseModel):
    """Pydantic model for AI_MODEL_PROVIDER credential validation."""

    api_key: str = Field(..., min_length=1, description="API key for the AI model provider")


class EntraIdAppRegistrationCredential(BaseModel):
    """Pydantic model for ENTRA_ID_APP_REGISTRATION credential validation."""

    tenant_id: str = Field(..., min_length=1, description="Azure Entra ID tenant ID")
    client_id: str = Field(..., min_length=1, description="Azure Entra ID client/application ID")
    client_secret: str = Field(..., min_length=1, description="Azure Entra ID client secret")


class CredentialValidationError(Exception):
    """Exception raised when credential validation fails."""

    def __init__(self, message: str, errors: list | None = None):
        self.message = message
        self.errors = errors or []
        super().__init__(message)


class UnsupportedCredentialTypeError(Exception):
    """Exception raised when credential type is not supported."""

    def __init__(self, credential_type: str):
        self.credential_type = credential_type
        super().__init__(
            f"Credential type '{credential_type}' is not supported. Supported types: {CredentialTypeEnum.all()}"
        )


def validate_credential_secret(credential_type: str, secret_value: str) -> str:
    """
    Validate the secret value based on credential type.

    Args:
        credential_type: The type of credential (API_KEY, BASIC_AUTH, OPENAPI_CONNECTION)
        secret_value: The secret value to validate

    Returns:
        The validated secret value (unchanged for API_KEY, validated for BASIC_AUTH/OPENAPI_CONNECTION)

    Raises:
        UnsupportedCredentialTypeError: If credential type is not supported
        CredentialValidationError: If validation fails
    """
    # Normalize credential type to uppercase
    cred_type = credential_type.upper()

    if cred_type not in CredentialTypeEnum.all():
        raise UnsupportedCredentialTypeError(credential_type)

    if cred_type == CredentialTypeEnum.API_KEY.value:
        # API_KEY just needs to be a non-empty string
        if not secret_value or not secret_value.strip():
            raise CredentialValidationError("API_KEY secret value cannot be empty")
        return secret_value

    elif cred_type == CredentialTypeEnum.BASIC_AUTH.value:
        # BASIC_AUTH must be a valid JSON string with username and password
        try:
            parsed = json.loads(secret_value)
        except json.JSONDecodeError as e:
            raise CredentialValidationError(
                f"BASIC_AUTH secret_value must be a valid JSON string with 'username' and 'password' fields. Error: {e!s}"
            )

        if not isinstance(parsed, dict):
            raise CredentialValidationError(
                "BASIC_AUTH secret_value must be a JSON object with 'username' and 'password' fields"
            )

        # Validate using Pydantic
        try:
            BasicAuthCredential(**parsed)
        except Exception as e:
            raise CredentialValidationError(
                f"BASIC_AUTH validation failed: {e!s}. 'username' and 'password' fields must be non-empty strings."
            )

        # Return the original string (not re-serialized) as requested
        return secret_value

    elif cred_type == CredentialTypeEnum.OPENAPI_CONNECTION.value:
        # OPENAPI_CONNECTION must be a valid JSON string with key and value
        try:
            parsed = json.loads(secret_value)
        except json.JSONDecodeError as e:
            raise CredentialValidationError(
                f"OPENAPI_CONNECTION secret_value must be a valid JSON string with 'key' and 'value' fields. Error: {e!s}"
            )

        if not isinstance(parsed, dict):
            raise CredentialValidationError(
                "OPENAPI_CONNECTION secret_value must be a JSON object with 'key' and 'value' fields"
            )

        # Validate using Pydantic
        try:
            OpenAPIConnectionCredential(**parsed)
        except Exception as e:
            raise CredentialValidationError(
                f"OPENAPI_CONNECTION validation failed: {e!s}. 'key' and 'value' fields must be non-empty strings."
            )

        # Return the original string (not re-serialized) as requested
        return secret_value

    elif cred_type == CredentialTypeEnum.AI_MODEL_PROVIDER.value:
        try:
            parsed = json.loads(secret_value)
        except json.JSONDecodeError as e:
            raise CredentialValidationError(
                f"AI_MODEL_PROVIDER secret_value must be a valid JSON string with 'api_key' field. Error: {e!s}"
            )

        if not isinstance(parsed, dict):
            raise CredentialValidationError("AI_MODEL_PROVIDER secret_value must be a JSON object with 'api_key' field")

        try:
            AIModelProviderCredential(**parsed)
        except Exception as e:
            raise CredentialValidationError(
                f"AI_MODEL_PROVIDER validation failed: {e!s}. 'api_key' field must be a non-empty string."
            )

        return secret_value

    elif cred_type == CredentialTypeEnum.ENTRA_ID_APP_REGISTRATION.value:
        try:
            parsed = json.loads(secret_value)
        except json.JSONDecodeError as e:
            raise CredentialValidationError(
                "ENTRA_ID_APP_REGISTRATION secret_value must be a valid JSON string with "
                f"'tenant_id', 'client_id', and 'client_secret' fields. Error: {e!s}"
            )

        if not isinstance(parsed, dict):
            raise CredentialValidationError(
                "ENTRA_ID_APP_REGISTRATION secret_value must be a JSON object with "
                "'tenant_id', 'client_id', and 'client_secret' fields"
            )

        try:
            EntraIdAppRegistrationCredential(**parsed)
        except Exception as e:
            raise CredentialValidationError(
                f"ENTRA_ID_APP_REGISTRATION validation failed: {e!s}. "
                "'tenant_id', 'client_id', and 'client_secret' fields must be non-empty strings."
            )

        return secret_value

    raise UnsupportedCredentialTypeError(credential_type)
