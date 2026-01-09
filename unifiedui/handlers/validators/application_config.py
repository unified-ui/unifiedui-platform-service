"""Application configuration validators using factory pattern."""
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from enum import Enum
import re

from pydantic import BaseModel, Field, field_validator, model_validator

from unifiedui.core.database.enums import ApplicationTypeEnum
from unifiedui.exc.application_config import (
    ApplicationConfigValidationError, 
    UnsupportedApplicationTypeError
)
from unifiedui.logger import get_logger


logger = get_logger(__name__)


# ========== N8N Config Enums ==========

class N8NApiVersionEnum(str, Enum):
    """Supported N8N API versions."""
    V1 = "v1"

    @classmethod
    def all(cls) -> list[str]:
        return [v.value for v in cls]


class N8NWorkflowTypeEnum(str, Enum):
    """Supported N8N workflow types."""
    N8N_CHAT_AGENT_WORKFLOW = "N8N_CHAT_AGENT_WORKFLOW"

    @classmethod
    def all(cls) -> list[str]:
        return [v.value for v in cls]


# ========== N8N Config Schema ==========

class N8NApplicationConfig(BaseModel):
    """Pydantic model for N8N application configuration validation."""
    
    api_version: N8NApiVersionEnum = Field(
        ...,
        description="API version (currently only 'v1' supported)"
    )
    workflow_type: N8NWorkflowTypeEnum = Field(
        ...,
        description="Workflow type (currently only 'N8N_CHAT_AGENT_WORKFLOW' supported)"
    )
    use_unified_chat_history: bool = Field(
        ...,
        description="Whether to use unified chat history"
    )
    chat_history_count: int = Field(
        default=30,
        ge=1,
        le=100,
        description="Number of chat history messages to include (default: 30)"
    )
    chat_url: str = Field(
        ...,
        min_length=1,
        description="N8N webhook URL for chat"
    )
    workflow_endpoint: str = Field(
        ...,
        min_length=1,
        description="N8N workflow endpoint URL (e.g., https://n8n.example.com/workflow/abc123)"
    )
    api_api_key_credential_id: str = Field(
        ...,
        min_length=1,
        description="Credential ID for N8N API key"
    )
    chat_auth_credential_id: str = Field(
        ...,
        min_length=1,
        description="Credential ID for chat authentication"
    )

    @field_validator('chat_url')
    @classmethod
    def validate_chat_url(cls, v: str) -> str:
        """Validate that chat_url is a valid URL format."""
        if not v.startswith(('http://', 'https://')):
            raise ValueError("chat_url must start with http:// or https://")
        return v

    @field_validator('workflow_endpoint')
    @classmethod
    def validate_workflow_endpoint(cls, v: str) -> str:
        """Validate that workflow_endpoint is a valid URL format."""
        if not v.startswith(('http://', 'https://')):
            raise ValueError("workflow_endpoint must start with http:// or https://")
        if '/workflow/' not in v:
            raise ValueError("workflow_endpoint must contain '/workflow/' in the path")
        return v


# ========== Base Validator Interface ==========

class BaseApplicationConfigValidator(ABC):
    """Abstract base class for application config validators."""
    
    @abstractmethod
    def validate(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate the configuration and return the validated config.
        
        Args:
            config: Configuration dictionary to validate
            
        Returns:
            Validated configuration dictionary
            
        Raises:
            ApplicationConfigValidationError: If validation fails
        """
        pass
    
    @abstractmethod
    def get_supported_type(self) -> ApplicationTypeEnum:
        """Get the application type this validator supports."""
        pass


# ========== N8N Validator ==========

class N8NConfigValidator(BaseApplicationConfigValidator):
    """Validator for N8N application configuration."""
    
    def validate(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate N8N configuration.
        
        Args:
            config: Configuration dictionary to validate
            
        Returns:
            Validated configuration dictionary with defaults applied
            
        Raises:
            ApplicationConfigValidationError: If validation fails
        """
        try:
            validated = N8NApplicationConfig(**config)
            return validated.model_dump()
        except Exception as e:
            logger.error(f"N8N config validation failed: {e}")
            raise ApplicationConfigValidationError(
                message=f"N8N configuration validation failed: {str(e)}",
                errors=[str(e)]
            )
    
    def get_supported_type(self) -> ApplicationTypeEnum:
        return ApplicationTypeEnum.N8N


# ========== Microsoft Foundry Config Enums ==========

class MicrosoftFoundryAgentTypeEnum(str, Enum):
    """Supported Microsoft Foundry agent types."""
    AGENT = "AGENT"
    MULTI_AGENT = "MULTI_AGENT"

    @classmethod
    def all(cls) -> list[str]:
        return [v.value for v in cls]


class MicrosoftFoundryApiVersionEnum(str, Enum):
    """Supported Microsoft Foundry API versions."""
    V2025_11_15_PREVIEW = "2025-11-15-preview"

    @classmethod
    def all(cls) -> list[str]:
        return [v.value for v in cls]


# ========== Microsoft Foundry Config Schema ==========

class MicrosoftFoundryApplicationConfig(BaseModel):
    """Pydantic model for Microsoft Foundry application configuration validation."""
    
    agent_type: MicrosoftFoundryAgentTypeEnum = Field(
        ...,
        description="Agent type (AGENT or MULTI_AGENT)"
    )
    api_version: MicrosoftFoundryApiVersionEnum = Field(
        ...,
        description="API version (currently only '2025-11-15-preview' supported)"
    )
    project_endpoint: str = Field(
        ...,
        min_length=1,
        description="Foundry project endpoint URL"
    )
    agent_name: str = Field(
        ...,
        min_length=1,
        description="Name of the agent in Foundry"
    )

    @field_validator('project_endpoint')
    @classmethod
    def validate_project_endpoint(cls, v: str) -> str:
        """Validate that project_endpoint is a valid Foundry endpoint URL."""
        if not v.startswith('https://'):
            raise ValueError("project_endpoint must start with https://")
        if 'services.ai.azure.com/api/projects' not in v:
            raise ValueError("project_endpoint must contain 'services.ai.azure.com/api/projects'")
        return v


# ========== Microsoft Foundry Validator ==========

class MicrosoftFoundryConfigValidator(BaseApplicationConfigValidator):
    """Validator for Microsoft Foundry application configuration."""
    
    def validate(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate Microsoft Foundry configuration.
        
        Args:
            config: Configuration dictionary to validate
            
        Returns:
            Validated configuration dictionary
            
        Raises:
            ApplicationConfigValidationError: If validation fails
        """
        try:
            validated = MicrosoftFoundryApplicationConfig(**config)
            return validated.model_dump()
        except Exception as e:
            logger.error(f"Microsoft Foundry config validation failed: {e}")
            raise ApplicationConfigValidationError(
                message=f"Microsoft Foundry configuration validation failed: {str(e)}",
                errors=[str(e)]
            )
    
    def get_supported_type(self) -> ApplicationTypeEnum:
        return ApplicationTypeEnum.MICROSOFT_FOUNDRY


# ========== Config Validator Factory ==========

class ApplicationConfigValidatorFactory:
    """Factory for creating application config validators based on type."""
    
    _validators: Dict[ApplicationTypeEnum, BaseApplicationConfigValidator] = {
        ApplicationTypeEnum.N8N: N8NConfigValidator(),
        ApplicationTypeEnum.MICROSOFT_FOUNDRY: MicrosoftFoundryConfigValidator(),
    }
    
    @classmethod
    def get_validator(cls, application_type: ApplicationTypeEnum) -> BaseApplicationConfigValidator:
        """
        Get the validator for the specified application type.
        
        Args:
            application_type: The type of application
            
        Returns:
            The appropriate config validator
            
        Raises:
            UnsupportedApplicationTypeError: If the application type is not supported
        """
        validator = cls._validators.get(application_type)
        if validator is None:
            raise UnsupportedApplicationTypeError(application_type.value)
        return validator
    
    @classmethod
    def validate_config(
        cls, 
        application_type: ApplicationTypeEnum, 
        config: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Validate configuration for the specified application type.
        
        Args:
            application_type: The type of application
            config: Configuration dictionary to validate (can be None or empty)
            
        Returns:
            Validated configuration dictionary
            
        Raises:
            UnsupportedApplicationTypeError: If the application type is not supported
            ApplicationConfigValidationError: If validation fails
        """
        # If config is None or empty, just return empty dict
        # Validation only required when config is provided
        if not config:
            return {}
        
        validator = cls.get_validator(application_type)
        return validator.validate(config)
    
    @classmethod
    def is_supported(cls, application_type: ApplicationTypeEnum) -> bool:
        """Check if an application type has a validator."""
        return application_type in cls._validators
    
    @classmethod
    def get_supported_types(cls) -> List[ApplicationTypeEnum]:
        """Get list of supported application types."""
        return list(cls._validators.keys())
