"""Workflow configuration validators using factory pattern."""

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field, field_validator

from unifiedui.core.database.enums import WorkflowTypeEnum
from unifiedui.exc.workflows import UnsupportedWorkflowTypeError, WorkflowConfigValidationError
from unifiedui.logger import get_logger

logger = get_logger(__name__)


# ========== N8N Config Schema ==========


class N8NWorkflowConfig(BaseModel):
    """Pydantic model for N8N workflow configuration validation."""

    api_version: str = Field(..., description="API version for the workflow (currently only 'v1' is supported)")
    workflow_endpoint: str = Field(
        ...,
        min_length=1,
        description="N8N workflow endpoint URL (e.g., 'http://localhost:5678/workflow/01V4K8pjRhOVncdg')",
    )
    api_api_key_credential_id: str = Field(..., min_length=1, description="Credential ID for N8N API key")
    webhook_url: str | None = Field(
        None,
        description="Optional webhook URL for triggering the workflow (e.g., 'http://localhost:5678/webhook/my-hook')",
    )
    default_body: dict[str, Any] | None = Field(
        None,
        description="Optional default JSON body pre-filled when starting the workflow via webhook",
    )
    default_query_params: dict[str, str] | None = Field(
        None,
        description="Optional default query parameters pre-filled when starting the workflow via webhook",
    )

    @field_validator("api_version")
    @classmethod
    def validate_api_version(cls, v: str) -> str:
        """Validate that api_version is a supported version."""
        allowed_versions = ["v1"]
        if v not in allowed_versions:
            raise ValueError(f"api_version must be one of: {', '.join(allowed_versions)}")
        return v

    @field_validator("workflow_endpoint")
    @classmethod
    def validate_workflow_endpoint(cls, v: str) -> str:
        """Validate that workflow_endpoint is a valid URL format and contains workflow path."""
        if not v.startswith(("http://", "https://")):
            raise ValueError("workflow_endpoint must start with http:// or https://")
        if "/workflow/" not in v:
            raise ValueError("workflow_endpoint must contain '/workflow/' path with workflow ID")
        return v

    @field_validator("webhook_url")
    @classmethod
    def validate_webhook_url(cls, v: str | None) -> str | None:
        """Validate that webhook_url is a valid URL if provided."""
        if v is None or v == "":
            return None
        if not v.startswith(("http://", "https://")):
            raise ValueError("webhook_url must start with http:// or https://")
        return v

    @field_validator("default_body")
    @classmethod
    def validate_default_body(cls, v: dict[str, Any] | None) -> dict[str, Any] | None:
        """Validate that default_body is a valid JSON object if provided."""
        if v is None:
            return None
        if not isinstance(v, dict):
            raise ValueError("default_body must be a JSON object")
        return v

    @field_validator("default_query_params")
    @classmethod
    def validate_default_query_params(cls, v: dict[str, str] | None) -> dict[str, str] | None:
        """Validate that default_query_params contains only string values."""
        if v is None:
            return None
        if not isinstance(v, dict):
            raise ValueError("default_query_params must be a JSON object with string values")
        for key, val in v.items():
            if not isinstance(key, str) or not isinstance(val, str):
                raise ValueError("default_query_params keys and values must be strings")
        return v


# ========== Base Validator Interface ==========


class BaseWorkflowConfigValidator(ABC):
    """Abstract base class for workflow config validators."""

    @abstractmethod
    def validate(self, config: dict[str, Any]) -> dict[str, Any]:
        """
        Validate the configuration and return the validated config.

        Args:
            config: Configuration dictionary to validate

        Returns:
            Validated configuration dictionary

        Raises:
            WorkflowConfigValidationError: If validation fails
        """
        pass

    @abstractmethod
    def get_supported_type(self) -> WorkflowTypeEnum:
        """Get the workflow type this validator supports."""
        pass


# ========== N8N Validator ==========


class N8NWorkflowConfigValidator(BaseWorkflowConfigValidator):
    """Validator for N8N workflow configuration."""

    def validate(self, config: dict[str, Any]) -> dict[str, Any]:
        """
        Validate N8N configuration.

        Args:
            config: Configuration dictionary to validate

        Returns:
            Validated configuration dictionary with defaults applied

        Raises:
            WorkflowConfigValidationError: If validation fails
        """
        try:
            validated = N8NWorkflowConfig(**config)
            return validated.model_dump(exclude_none=True)
        except Exception as e:
            logger.error("N8N workflow config validation failed: %s", e)
            raise WorkflowConfigValidationError(message=f"N8N configuration validation failed: {e!s}", errors=[str(e)])

    def get_supported_type(self) -> WorkflowTypeEnum:
        return WorkflowTypeEnum.N8N


# ========== Config Validator Factory ==========


class WorkflowConfigValidatorFactory:
    """Factory for creating workflow config validators based on type."""

    _validators: dict[WorkflowTypeEnum, BaseWorkflowConfigValidator] = {
        WorkflowTypeEnum.N8N: N8NWorkflowConfigValidator(),
    }

    @classmethod
    def get_validator(cls, agent_type: WorkflowTypeEnum) -> BaseWorkflowConfigValidator:
        """
        Get the validator for the specified workflow type.

        Args:
            agent_type: The type of workflow

        Returns:
            The appropriate config validator

        Raises:
            UnsupportedWorkflowTypeError: If the agent type is not supported
        """
        validator = cls._validators.get(agent_type)
        if validator is None:
            raise UnsupportedWorkflowTypeError(agent_type.value)
        return validator

    @classmethod
    def validate_config(cls, agent_type: WorkflowTypeEnum, config: dict[str, Any] | None) -> dict[str, Any]:
        """
        Validate configuration for the specified workflow type.

        Args:
            agent_type: The type of workflow
            config: Configuration dictionary to validate (can be None or empty)

        Returns:
            Validated configuration dictionary

        Raises:
            UnsupportedWorkflowTypeError: If the agent type is not supported
            WorkflowConfigValidationError: If validation fails
        """
        # Config is REQUIRED for workflows - validate even if empty
        if not config:
            raise WorkflowConfigValidationError(
                message="Configuration is required for workflows", errors=["config cannot be empty"]
            )

        validator = cls.get_validator(agent_type)
        return validator.validate(config)

    @classmethod
    def is_supported(cls, agent_type: WorkflowTypeEnum) -> bool:
        """Check if a workflow type has a validator."""
        return agent_type in cls._validators

    @classmethod
    def get_supported_types(cls) -> list[WorkflowTypeEnum]:
        """Get list of supported workflow types."""
        return list(cls._validators.keys())
