"""Chat agent configuration validators using factory pattern."""

from abc import ABC, abstractmethod
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from unifiedui.core.database.enums import (
    ChatAgentTypeEnum,
    MicrosoftFoundryAuthTypeEnum,
    MicrosoftFoundryCustomRestApiAuthTypeEnum,
    RestApiAuthTypeEnum,
)
from unifiedui.exc.chat_agent_config import ChatAgentConfigValidationError, UnsupportedChatAgentTypeError
from unifiedui.logger import get_logger

logger = get_logger(__name__)


# ========== N8N Config Enums ==========


class N8NApiVersionEnum(StrEnum):
    """Supported N8N API versions."""

    V1 = "v1"

    @classmethod
    def all(cls) -> list[str]:
        return [v.value for v in cls]


class N8NWorkflowTypeEnum(StrEnum):
    """Supported N8N workflow types."""

    N8N_CHAT_AGENT_WORKFLOW = "N8N_CHAT_AGENT_WORKFLOW"

    @classmethod
    def all(cls) -> list[str]:
        return [v.value for v in cls]


# ========== N8N Config Schema ==========


class N8NChatAgentConfig(BaseModel):
    """Pydantic model for N8N chat agent configuration validation."""

    api_version: N8NApiVersionEnum = Field(..., description="API version (currently only 'v1' supported)")
    workflow_type: N8NWorkflowTypeEnum = Field(
        ..., description="Workflow type (currently only 'N8N_CHAT_AGENT_WORKFLOW' supported)"
    )
    use_unified_chat_history: bool = Field(..., description="Whether to use unified chat history")
    chat_history_count: int = Field(
        default=30, ge=1, le=100, description="Number of chat history messages to include (default: 30)"
    )
    chat_url: str = Field(..., min_length=1, description="N8N webhook URL for chat")
    workflow_endpoint: str = Field(
        ..., min_length=1, description="N8N workflow endpoint URL (e.g., https://n8n.example.com/workflow/abc123)"
    )
    api_api_key_credential_id: str = Field(..., min_length=1, description="Credential ID for N8N API key")
    chat_auth_credential_id: str | None = Field(default=None, description="Credential ID for chat authentication")

    @field_validator("chat_url")
    @classmethod
    def validate_chat_url(cls, v: str) -> str:
        """Validate that chat_url is a valid URL format."""
        if not v.startswith(("http://", "https://")):
            raise ValueError("chat_url must start with http:// or https://")
        return v

    @field_validator("workflow_endpoint")
    @classmethod
    def validate_workflow_endpoint(cls, v: str) -> str:
        """Validate that workflow_endpoint is a valid URL format."""
        if not v.startswith(("http://", "https://")):
            raise ValueError("workflow_endpoint must start with http:// or https://")
        if "/workflow/" not in v:
            raise ValueError("workflow_endpoint must contain '/workflow/' in the path")
        return v


# ========== Base Validator Interface ==========


class BaseChatAgentConfigValidator(ABC):
    """Abstract base class for chat agent config validators."""

    @abstractmethod
    def validate(self, config: dict[str, Any]) -> dict[str, Any]:
        """
        Validate the configuration and return the validated config.

        Args:
            config: Configuration dictionary to validate

        Returns:
            Validated configuration dictionary

        Raises:
            ChatAgentConfigValidationError: If validation fails
        """
        pass

    @abstractmethod
    def get_supported_type(self) -> ChatAgentTypeEnum:
        """Get the chat agent type this validator supports."""
        pass


# ========== N8N Validator ==========


class N8NConfigValidator(BaseChatAgentConfigValidator):
    """Validator for N8N chat agent configuration."""

    def validate(self, config: dict[str, Any]) -> dict[str, Any]:
        """
        Validate N8N configuration.

        Args:
            config: Configuration dictionary to validate

        Returns:
            Validated configuration dictionary with defaults applied

        Raises:
            ChatAgentConfigValidationError: If validation fails
        """
        try:
            validated = N8NChatAgentConfig(**config)
            return validated.model_dump()
        except Exception as e:
            logger.error("N8N config validation failed: %s", e)
            raise ChatAgentConfigValidationError(message=f"N8N configuration validation failed: {e!s}", errors=[str(e)])

    def get_supported_type(self) -> ChatAgentTypeEnum:
        return ChatAgentTypeEnum.N8N


# ========== Microsoft Foundry Config Enums ==========


class MicrosoftFoundryAgentTypeEnum(StrEnum):
    """Supported Microsoft Foundry agent types."""

    AGENT = "AGENT"
    MULTI_AGENT = "MULTI_AGENT"

    @classmethod
    def all(cls) -> list[str]:
        return [v.value for v in cls]


class MicrosoftFoundryApiVersionEnum(StrEnum):
    """Supported Microsoft Foundry API versions."""

    V2025_11_15_PREVIEW = "2025-11-15-preview"
    V1 = "v1"

    @classmethod
    def all(cls) -> list[str]:
        return [v.value for v in cls]


# ========== Microsoft Foundry Config Schema ==========


class MicrosoftFoundryChatAgentConfig(BaseModel):
    """Pydantic model for Microsoft Foundry chat agent configuration validation."""

    agent_type: MicrosoftFoundryAgentTypeEnum = Field(..., description="Agent type (AGENT or MULTI_AGENT)")
    api_version: MicrosoftFoundryApiVersionEnum = Field(
        ..., description="API version (e.g., 'v1' or '2025-11-15-preview')"
    )
    project_endpoint: str = Field(default="", description="Foundry project endpoint URL")
    agent_name: str = Field(default="", description="Name of the agent in Foundry")
    auth_type: MicrosoftFoundryAuthTypeEnum = Field(
        default=MicrosoftFoundryAuthTypeEnum.ENTRA_ID_USER_TOKEN,
        description="Authentication type (defaults to ENTRA_ID_USER_TOKEN for backward compatibility)",
    )
    credential_id: str | None = Field(
        default=None,
        description="Credential ID (required for ENTRA_ID_APP_REGISTRATION and API_KEY)",
    )
    custom_rest_api_endpoint: str | None = Field(
        default=None,
        description="Custom REST API proxy endpoint URL (required for CUSTOM_REST_API auth_type)",
    )
    custom_rest_api_auth_type: MicrosoftFoundryCustomRestApiAuthTypeEnum | None = Field(
        default=None,
        description="Auth type for the custom REST API proxy (required for CUSTOM_REST_API auth_type)",
    )
    custom_rest_api_api_key_header: str = Field(
        default="X-API-Key",
        description="Custom header name for API key auth to the proxy (default: X-API-Key)",
    )

    @field_validator("project_endpoint")
    @classmethod
    def validate_project_endpoint(cls, v: str) -> str:
        """Validate that project_endpoint is a valid Foundry endpoint URL."""
        if not v:
            return v
        if not v.startswith("https://"):
            raise ValueError("project_endpoint must start with https://")
        if "services.ai.azure.com/api/projects" not in v:
            raise ValueError("project_endpoint must contain 'services.ai.azure.com/api/projects'")
        return v

    @field_validator("custom_rest_api_endpoint")
    @classmethod
    def validate_custom_rest_api_endpoint(cls, v: str | None) -> str | None:
        """Validate that custom_rest_api_endpoint is a valid URL."""
        if not v:
            return v
        if not v.startswith(("https://", "http://localhost", "http://host.docker.internal")):
            raise ValueError(
                "custom_rest_api_endpoint must start with https://, http://localhost, or http://host.docker.internal"
            )
        return v

    @model_validator(mode="after")
    def validate_auth_requirements(self) -> "MicrosoftFoundryChatAgentConfig":
        """Validate fields required by the selected auth_type."""
        if self.auth_type == MicrosoftFoundryAuthTypeEnum.CUSTOM_REST_API:
            if not self.custom_rest_api_endpoint:
                raise ValueError("custom_rest_api_endpoint is required for auth_type 'CUSTOM_REST_API'")
            if not self.custom_rest_api_auth_type:
                raise ValueError("custom_rest_api_auth_type is required for auth_type 'CUSTOM_REST_API'")
            proxy_requires_credential = {
                MicrosoftFoundryCustomRestApiAuthTypeEnum.API_KEY,
                MicrosoftFoundryCustomRestApiAuthTypeEnum.ENTRA_ID_APP_REGISTRATION,
            }
            if self.custom_rest_api_auth_type in proxy_requires_credential and not self.credential_id:
                raise ValueError(
                    f"credential_id is required for custom_rest_api_auth_type '{self.custom_rest_api_auth_type}'"
                )
        else:
            requires_credential = {
                MicrosoftFoundryAuthTypeEnum.ENTRA_ID_APP_REGISTRATION,
                MicrosoftFoundryAuthTypeEnum.API_KEY,
            }
            if not self.project_endpoint:
                raise ValueError("project_endpoint is required for non-CUSTOM_REST_API auth types")
            if not self.agent_name:
                raise ValueError("agent_name is required for non-CUSTOM_REST_API auth types")
            if self.auth_type in requires_credential and not self.credential_id:
                raise ValueError(f"credential_id is required for auth_type '{self.auth_type}'")
        return self


# ========== Microsoft Foundry Validator ==========


class MicrosoftFoundryConfigValidator(BaseChatAgentConfigValidator):
    """Validator for Microsoft Foundry chat agent configuration."""

    def validate(self, config: dict[str, Any]) -> dict[str, Any]:
        """
        Validate Microsoft Foundry configuration.

        Args:
            config: Configuration dictionary to validate

        Returns:
            Validated configuration dictionary

        Raises:
            ChatAgentConfigValidationError: If validation fails
        """
        try:
            validated = MicrosoftFoundryChatAgentConfig(**config)
            return validated.model_dump()
        except Exception as e:
            logger.error("Microsoft Foundry config validation failed: %s", e)
            raise ChatAgentConfigValidationError(
                message=f"Microsoft Foundry configuration validation failed: {e!s}", errors=[str(e)]
            )

    def get_supported_type(self) -> ChatAgentTypeEnum:
        return ChatAgentTypeEnum.MICROSOFT_FOUNDRY


# ========== REST API Config Schema ==========


class RestApiChatAgentConfig(BaseModel):
    """Pydantic model for REST API chat agent configuration validation."""

    auth_type: RestApiAuthTypeEnum = Field(..., description="Authentication type for the REST API")
    invoke_endpoint: str = Field(..., min_length=1, description="URL for the agent invoke endpoint")
    credential_id: str | None = Field(
        default=None, description="Credential ID (required for BASIC_AUTH, API_KEY, ENTRA_ID_APP_REGISTRATION)"
    )
    api_key_header_name: str = Field(
        default="X-API-Key", description="Header name for API key auth (default: X-API-Key)"
    )
    use_unified_chat_history: bool = Field(default=True, description="Whether to send chat history from unified-ui")
    chat_history_count: int = Field(
        default=30, ge=1, le=100, description="Number of chat history messages to include (default: 30)"
    )
    create_conversation_endpoint: str | None = Field(
        default=None, description="Optional POST endpoint URL for conversation creation"
    )

    @field_validator("invoke_endpoint")
    @classmethod
    def validate_invoke_endpoint(cls, v: str) -> str:
        """Validate that invoke_endpoint is a valid URL format."""
        if not v.startswith(("http://", "https://")):
            raise ValueError("invoke_endpoint must start with http:// or https://")
        return v

    @field_validator("create_conversation_endpoint")
    @classmethod
    def validate_create_conversation_endpoint(cls, v: str | None) -> str | None:
        """Validate that create_conversation_endpoint is a valid URL format if provided."""
        if v is not None and not v.startswith(("http://", "https://")):
            raise ValueError("create_conversation_endpoint must start with http:// or https://")
        return v

    @model_validator(mode="after")
    def validate_credential_required(self) -> "RestApiChatAgentConfig":
        """Validate that credential_id is provided when auth_type requires it."""
        requires_credential = {
            RestApiAuthTypeEnum.BASIC_AUTH,
            RestApiAuthTypeEnum.API_KEY,
            RestApiAuthTypeEnum.ENTRA_ID_APP_REGISTRATION,
        }
        if self.auth_type in requires_credential and not self.credential_id:
            raise ValueError(f"credential_id is required for auth_type '{self.auth_type}'")
        return self


# ========== REST API Validator ==========


class RestApiConfigValidator(BaseChatAgentConfigValidator):
    """Validator for REST API chat agent configuration."""

    def validate(self, config: dict[str, Any]) -> dict[str, Any]:
        """
        Validate REST API configuration.

        Args:
            config: Configuration dictionary to validate

        Returns:
            Validated configuration dictionary with defaults applied

        Raises:
            ChatAgentConfigValidationError: If validation fails
        """
        try:
            validated = RestApiChatAgentConfig(**config)
            return validated.model_dump()
        except Exception as e:
            logger.error("REST API config validation failed: %s", e)
            raise ChatAgentConfigValidationError(
                message=f"REST API configuration validation failed: {e!s}", errors=[str(e)]
            )

    def get_supported_type(self) -> ChatAgentTypeEnum:
        return ChatAgentTypeEnum.REST_API


# ========== LLM Config Schema ==========


class LLMChatAgentConfig(BaseModel):
    """Pydantic model for LLM chat agent configuration validation."""

    ai_model_id: str = Field(..., min_length=1, max_length=36, description="Reference to a TenantAIModel ID")
    system_prompt: str | None = Field(default=None, max_length=10000, description="Optional system prompt for the LLM")


# ========== LLM Validator ==========


class LLMConfigValidator(BaseChatAgentConfigValidator):
    """Validator for LLM chat agent configuration."""

    def validate(self, config: dict[str, Any]) -> dict[str, Any]:
        """Validate LLM configuration.

        Args:
            config: Configuration dictionary to validate

        Returns:
            Validated configuration dictionary with defaults applied

        Raises:
            ChatAgentConfigValidationError: If validation fails
        """
        try:
            validated = LLMChatAgentConfig(**config)
            return validated.model_dump()
        except Exception as e:
            logger.error("LLM config validation failed: %s", e)
            raise ChatAgentConfigValidationError(message=f"LLM configuration validation failed: {e!s}", errors=[str(e)])

    def get_supported_type(self) -> ChatAgentTypeEnum:
        return ChatAgentTypeEnum.LLM


# ========== Config Validator Factory ==========


class ChatAgentConfigValidatorFactory:
    """Factory for creating chat agent config validators based on type."""

    _validators: dict[ChatAgentTypeEnum, BaseChatAgentConfigValidator] = {
        ChatAgentTypeEnum.N8N: N8NConfigValidator(),
        ChatAgentTypeEnum.MICROSOFT_FOUNDRY: MicrosoftFoundryConfigValidator(),
        ChatAgentTypeEnum.REST_API: RestApiConfigValidator(),
        ChatAgentTypeEnum.LLM: LLMConfigValidator(),
    }

    @classmethod
    def get_validator(cls, chat_agent_type: ChatAgentTypeEnum) -> BaseChatAgentConfigValidator:
        """
        Get the validator for the specified chat agent type.

        Args:
            chat_agent_type: The type of chat agent

        Returns:
            The appropriate config validator

        Raises:
            UnsupportedChatAgentTypeError: If the chat agent type is not supported
        """
        validator = cls._validators.get(chat_agent_type)
        if validator is None:
            raise UnsupportedChatAgentTypeError(chat_agent_type.value)
        return validator

    @classmethod
    def validate_config(cls, chat_agent_type: ChatAgentTypeEnum, config: dict[str, Any] | None) -> dict[str, Any]:
        """
        Validate configuration for the specified chat agent type.

        Args:
            chat_agent_type: The type of chat agent
            config: Configuration dictionary to validate (can be None or empty)

        Returns:
            Validated configuration dictionary

        Raises:
            UnsupportedChatAgentTypeError: If the chat agent type is not supported
            ChatAgentConfigValidationError: If validation fails
        """
        if not config:
            return {}

        validator = cls.get_validator(chat_agent_type)
        return validator.validate(config)

    @classmethod
    def is_supported(cls, chat_agent_type: ChatAgentTypeEnum) -> bool:
        """Check if a chat agent type has a validator."""
        return chat_agent_type in cls._validators

    @classmethod
    def get_supported_types(cls) -> list[ChatAgentTypeEnum]:
        """Get list of supported chat agent types."""
        return list(cls._validators.keys())
