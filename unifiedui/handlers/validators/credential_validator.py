"""Credential validation logic."""
import json
from typing import Dict, Any
from enum import Enum

from pydantic import BaseModel, Field, field_validator

from unifiedui.logger import get_logger


logger = get_logger(__name__)


class CredentialTypeEnum(str, Enum):
    """Supported credential types."""
    API_KEY = "API_KEY"
    BASIC_AUTH = "BASIC_AUTH"

    @classmethod
    def all(cls) -> list[str]:
        return [v.value for v in cls]


class BasicAuthCredential(BaseModel):
    """Pydantic model for BASIC_AUTH credential validation."""
    
    username: str = Field(..., min_length=1, description="Username for basic auth")
    password: str = Field(..., min_length=1, description="Password for basic auth")


class CredentialValidationError(Exception):
    """Exception raised when credential validation fails."""
    
    def __init__(self, message: str, errors: list = None):
        self.message = message
        self.errors = errors or []
        super().__init__(message)


class UnsupportedCredentialTypeError(Exception):
    """Exception raised when credential type is not supported."""
    
    def __init__(self, credential_type: str):
        self.credential_type = credential_type
        super().__init__(f"Credential type '{credential_type}' is not supported. Supported types: {CredentialTypeEnum.all()}")


def validate_credential_secret(credential_type: str, secret_value: str) -> str:
    """
    Validate the secret value based on credential type.
    
    Args:
        credential_type: The type of credential (API_KEY, BASIC_AUTH)
        secret_value: The secret value to validate
        
    Returns:
        The validated secret value (unchanged for API_KEY, validated for BASIC_AUTH)
        
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
                f"BASIC_AUTH secret_value must be a valid JSON string with 'username' and 'password' fields. Error: {str(e)}"
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
                f"BASIC_AUTH validation failed: {str(e)}. 'username' and 'password' fields must be non-empty strings."
            )
        
        # Return the original string (not re-serialized) as requested
        return secret_value
    
    raise UnsupportedCredentialTypeError(credential_type)
