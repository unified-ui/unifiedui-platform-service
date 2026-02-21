"""AI model configuration validators using factory pattern."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field

from unifiedui.core.database.enums import AIModelProviderEnum
from unifiedui.exc.tenant_ai_models import TenantAIModelConfigValidationError, UnsupportedAIModelProviderError
from unifiedui.logger import get_logger

logger = get_logger(__name__)


class AzureOpenAIConfig(BaseModel):
    """Validation model for Azure OpenAI provider config."""

    endpoint: str = Field(..., min_length=1)
    api_version: str = Field(..., min_length=1)
    deployment_name: str = Field(..., min_length=1)


class OpenAIConfig(BaseModel):
    """Validation model for OpenAI provider config."""

    model_name: str = Field(..., min_length=1)
    organization: str = Field(None)
    base_url: str = Field(None)


class AnthropicConfig(BaseModel):
    """Validation model for Anthropic provider config."""

    model_name: str = Field(..., min_length=1)


class GoogleGenAIConfig(BaseModel):
    """Validation model for Google GenAI provider config."""

    model_name: str = Field(..., min_length=1)


class OllamaConfig(BaseModel):
    """Validation model for Ollama provider config."""

    model_name: str = Field(..., min_length=1)
    base_url: str = Field("http://localhost:11434")


class MistralConfig(BaseModel):
    """Validation model for Mistral provider config."""

    model_name: str = Field(..., min_length=1)


class GroqConfig(BaseModel):
    """Validation model for Groq provider config."""

    model_name: str = Field(..., min_length=1)


class BaseAIModelConfigValidator(ABC):
    """Base class for AI model config validators."""

    @abstractmethod
    def validate(self, config: dict[str, Any]) -> dict[str, Any]:
        """Validate the provider-specific config.

        Args:
            config: The configuration dictionary to validate.

        Returns:
            The validated configuration dictionary.
        """

    @abstractmethod
    def get_supported_provider(self) -> AIModelProviderEnum:
        """Return the provider this validator supports.

        Returns:
            The supported AI model provider enum.
        """


class AzureOpenAIConfigValidator(BaseAIModelConfigValidator):
    """Validator for Azure OpenAI configuration."""

    def validate(self, config: dict[str, Any]) -> dict[str, Any]:
        """Validate Azure OpenAI config."""
        try:
            validated = AzureOpenAIConfig(**config)
            return validated.model_dump()
        except Exception as e:
            raise TenantAIModelConfigValidationError(
                f"Azure OpenAI config validation failed: {e!s}. Required fields: endpoint, api_version, deployment_name"
            )

    def get_supported_provider(self) -> AIModelProviderEnum:
        """Return Azure OpenAI provider."""
        return AIModelProviderEnum.AZURE_OPENAI


class OpenAIConfigValidator(BaseAIModelConfigValidator):
    """Validator for OpenAI configuration."""

    def validate(self, config: dict[str, Any]) -> dict[str, Any]:
        """Validate OpenAI config."""
        try:
            validated = OpenAIConfig(**config)
            return validated.model_dump()
        except Exception as e:
            raise TenantAIModelConfigValidationError(
                f"OpenAI config validation failed: {e!s}. Required field: model_name"
            )

    def get_supported_provider(self) -> AIModelProviderEnum:
        """Return OpenAI provider."""
        return AIModelProviderEnum.OPENAI


class AnthropicConfigValidator(BaseAIModelConfigValidator):
    """Validator for Anthropic configuration."""

    def validate(self, config: dict[str, Any]) -> dict[str, Any]:
        """Validate Anthropic config."""
        try:
            validated = AnthropicConfig(**config)
            return validated.model_dump()
        except Exception as e:
            raise TenantAIModelConfigValidationError(
                f"Anthropic config validation failed: {e!s}. Required field: model_name"
            )

    def get_supported_provider(self) -> AIModelProviderEnum:
        """Return Anthropic provider."""
        return AIModelProviderEnum.ANTHROPIC


class GoogleGenAIConfigValidator(BaseAIModelConfigValidator):
    """Validator for Google GenAI configuration."""

    def validate(self, config: dict[str, Any]) -> dict[str, Any]:
        """Validate Google GenAI config."""
        try:
            validated = GoogleGenAIConfig(**config)
            return validated.model_dump()
        except Exception as e:
            raise TenantAIModelConfigValidationError(
                f"Google GenAI config validation failed: {e!s}. Required field: model_name"
            )

    def get_supported_provider(self) -> AIModelProviderEnum:
        """Return Google GenAI provider."""
        return AIModelProviderEnum.GOOGLE_GENAI


class OllamaConfigValidator(BaseAIModelConfigValidator):
    """Validator for Ollama configuration."""

    def validate(self, config: dict[str, Any]) -> dict[str, Any]:
        """Validate Ollama config."""
        try:
            validated = OllamaConfig(**config)
            return validated.model_dump()
        except Exception as e:
            raise TenantAIModelConfigValidationError(
                f"Ollama config validation failed: {e!s}. Required field: model_name"
            )

    def get_supported_provider(self) -> AIModelProviderEnum:
        """Return Ollama provider."""
        return AIModelProviderEnum.OLLAMA


class MistralConfigValidator(BaseAIModelConfigValidator):
    """Validator for Mistral configuration."""

    def validate(self, config: dict[str, Any]) -> dict[str, Any]:
        """Validate Mistral config."""
        try:
            validated = MistralConfig(**config)
            return validated.model_dump()
        except Exception as e:
            raise TenantAIModelConfigValidationError(
                f"Mistral config validation failed: {e!s}. Required field: model_name"
            )

    def get_supported_provider(self) -> AIModelProviderEnum:
        """Return Mistral provider."""
        return AIModelProviderEnum.MISTRAL


class GroqConfigValidator(BaseAIModelConfigValidator):
    """Validator for Groq configuration."""

    def validate(self, config: dict[str, Any]) -> dict[str, Any]:
        """Validate Groq config."""
        try:
            validated = GroqConfig(**config)
            return validated.model_dump()
        except Exception as e:
            raise TenantAIModelConfigValidationError(
                f"Groq config validation failed: {e!s}. Required field: model_name"
            )

    def get_supported_provider(self) -> AIModelProviderEnum:
        """Return Groq provider."""
        return AIModelProviderEnum.GROQ


class AIModelConfigValidatorFactory:
    """Factory for creating AI model config validators."""

    _validators: dict[AIModelProviderEnum, BaseAIModelConfigValidator] = {
        AIModelProviderEnum.AZURE_OPENAI: AzureOpenAIConfigValidator(),
        AIModelProviderEnum.OPENAI: OpenAIConfigValidator(),
        AIModelProviderEnum.ANTHROPIC: AnthropicConfigValidator(),
        AIModelProviderEnum.GOOGLE_GENAI: GoogleGenAIConfigValidator(),
        AIModelProviderEnum.OLLAMA: OllamaConfigValidator(),
        AIModelProviderEnum.MISTRAL: MistralConfigValidator(),
        AIModelProviderEnum.GROQ: GroqConfigValidator(),
    }

    @classmethod
    def get_validator(cls, provider: AIModelProviderEnum) -> BaseAIModelConfigValidator:
        """Get the config validator for a specific provider.

        Args:
            provider: The AI model provider.

        Returns:
            The config validator for the provider.

        Raises:
            UnsupportedAIModelProviderError: If the provider is not supported.
        """
        validator = cls._validators.get(provider)
        if validator is None:
            raise UnsupportedAIModelProviderError(provider)
        return validator

    @classmethod
    def validate_config(cls, provider: AIModelProviderEnum, config: dict[str, Any]) -> dict[str, Any]:
        """Validate config for a given provider.

        Args:
            provider: The AI model provider.
            config: The configuration to validate.

        Returns:
            The validated configuration dictionary.
        """
        validator = cls.get_validator(provider)
        return validator.validate(config)
