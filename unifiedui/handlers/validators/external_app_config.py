"""External app configuration validators using factory pattern."""

import re
from abc import ABC, abstractmethod
from enum import StrEnum
from typing import Any

import nh3
from pydantic import BaseModel, Field, field_validator

from unifiedui.exc.external_app_config import (
    ExternalAppConfigValidationError,
    UnsupportedExternalAppModeError,
)
from unifiedui.logger import get_logger

logger = get_logger(__name__)


MAX_PARAMS = 20
MAX_PARAM_KEY_LENGTH = 64
MAX_PARAM_VALUE_LENGTH = 2000
MAX_IFRAME_HTML_LENGTH = 8000
PARAM_KEY_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")
DEFAULT_SANDBOX = "allow-same-origin allow-scripts allow-popups allow-forms allow-downloads"


class ExternalAppModeEnum(StrEnum):
    """Supported external app configuration modes."""

    URL = "url"
    IFRAME = "iframe"

    @classmethod
    def all(cls) -> list[str]:
        return [v.value for v in cls]


class UrlModeConfig(BaseModel):
    """Configuration model for URL-mode external apps."""

    mode: ExternalAppModeEnum = Field(..., description="Configuration mode (must be 'url')")
    url: str = Field(..., min_length=1, max_length=2000, description="Base URL for the iframe")
    params: dict[str, str] = Field(default_factory=dict, description="Query parameters to append to the URL")

    @field_validator("mode")
    @classmethod
    def validate_mode(cls, v: ExternalAppModeEnum) -> ExternalAppModeEnum:
        """Ensure mode equals 'url' for this config."""
        if v != ExternalAppModeEnum.URL:
            raise ValueError("mode must be 'url' for UrlModeConfig")
        return v

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        """Validate URL scheme."""
        if not v.startswith(("http://", "https://")):
            raise ValueError("url must start with http:// or https://")
        return v

    @field_validator("params")
    @classmethod
    def validate_params(cls, v: dict[str, str]) -> dict[str, str]:
        """Validate parameter key format, value length and count."""
        if len(v) > MAX_PARAMS:
            raise ValueError(f"params must contain at most {MAX_PARAMS} entries")
        for key, value in v.items():
            if not key or len(key) > MAX_PARAM_KEY_LENGTH:
                raise ValueError(f"param key must be 1..{MAX_PARAM_KEY_LENGTH} characters: '{key}'")
            if not PARAM_KEY_PATTERN.match(key):
                raise ValueError(f"param key '{key}' contains invalid characters (allowed: a-z, A-Z, 0-9, _, -)")
            if not isinstance(value, str):
                raise ValueError(f"param value for '{key}' must be a string")
            if len(value) > MAX_PARAM_VALUE_LENGTH:
                raise ValueError(f"param value for '{key}' exceeds max length {MAX_PARAM_VALUE_LENGTH}")
        return v


class IframeModeConfig(BaseModel):
    """Configuration model for raw iframe-HTML mode external apps."""

    mode: ExternalAppModeEnum = Field(..., description="Configuration mode (must be 'iframe')")
    iframe_html: str = Field(..., min_length=1, max_length=MAX_IFRAME_HTML_LENGTH, description="Raw <iframe> HTML")

    @field_validator("mode")
    @classmethod
    def validate_mode(cls, v: ExternalAppModeEnum) -> ExternalAppModeEnum:
        """Ensure mode equals 'iframe' for this config."""
        if v != ExternalAppModeEnum.IFRAME:
            raise ValueError("mode must be 'iframe' for IframeModeConfig")
        return v


class BaseExternalAppConfigValidator(ABC):
    """Abstract base class for external app config validators."""

    @abstractmethod
    def validate(self, config: dict[str, Any]) -> dict[str, Any]:
        """Validate the configuration and return the sanitized config.

        Args:
            config: Configuration dictionary to validate

        Returns:
            Validated and sanitized configuration dictionary

        Raises:
            ExternalAppConfigValidationError: If validation fails
        """

    @abstractmethod
    def get_supported_mode(self) -> ExternalAppModeEnum:
        """Get the configuration mode this validator supports."""


class UrlModeValidator(BaseExternalAppConfigValidator):
    """Validator for URL-mode external app configuration."""

    def validate(self, config: dict[str, Any]) -> dict[str, Any]:
        """Validate URL-mode configuration."""
        try:
            validated = UrlModeConfig(**config)
            return validated.model_dump(mode="json")
        except Exception as e:
            logger.error("External app URL config validation failed: %s", e)
            raise ExternalAppConfigValidationError(
                message=f"URL configuration validation failed: {e!s}", errors=[str(e)]
            ) from e

    def get_supported_mode(self) -> ExternalAppModeEnum:
        return ExternalAppModeEnum.URL


class IframeModeValidator(BaseExternalAppConfigValidator):
    """Validator for iframe-HTML mode external app configuration."""

    _ALLOWED_TAGS = {"iframe"}
    _ALLOWED_ATTRS = {
        "iframe": {
            "src",
            "width",
            "height",
            "title",
            "sandbox",
            "allow",
            "allowfullscreen",
            "referrerpolicy",
            "loading",
            "style",
            "name",
        }
    }
    _URL_ATTRS = {"iframe": {"src"}}

    def validate(self, config: dict[str, Any]) -> dict[str, Any]:
        """Validate and sanitize iframe HTML configuration."""
        try:
            parsed = IframeModeConfig(**config)
        except Exception as e:
            logger.error("External app iframe config schema validation failed: %s", e)
            raise ExternalAppConfigValidationError(
                message=f"iframe configuration validation failed: {e!s}", errors=[str(e)]
            ) from e

        sanitized_html = nh3.clean(
            parsed.iframe_html,
            tags=self._ALLOWED_TAGS,
            attributes=self._ALLOWED_ATTRS,
            url_schemes={"http", "https"},
        )

        if "<iframe" not in sanitized_html.lower():
            raise ExternalAppConfigValidationError(
                message="iframe_html must contain a valid <iframe> element",
                errors=["No <iframe> tag found after sanitization"],
            )

        sanitized_html = self._ensure_sandbox(sanitized_html)

        return {"mode": ExternalAppModeEnum.IFRAME.value, "iframe_html": sanitized_html}

    def get_supported_mode(self) -> ExternalAppModeEnum:
        return ExternalAppModeEnum.IFRAME

    @staticmethod
    def _ensure_sandbox(html: str) -> str:
        """Inject a default sandbox attribute when missing."""
        if re.search(r"<iframe[^>]*\ssandbox\s*=", html, flags=re.IGNORECASE):
            return html
        return re.sub(
            r"<iframe\b",
            f'<iframe sandbox="{DEFAULT_SANDBOX}"',
            html,
            count=1,
            flags=re.IGNORECASE,
        )


class ExternalAppConfigValidatorFactory:
    """Factory for creating external app config validators based on mode."""

    _validators: dict[ExternalAppModeEnum, BaseExternalAppConfigValidator] = {
        ExternalAppModeEnum.URL: UrlModeValidator(),
        ExternalAppModeEnum.IFRAME: IframeModeValidator(),
    }

    @classmethod
    def get_validator(cls, mode: ExternalAppModeEnum) -> BaseExternalAppConfigValidator:
        """Get the validator for the specified mode."""
        validator = cls._validators.get(mode)
        if validator is None:
            raise UnsupportedExternalAppModeError(mode.value)
        return validator

    @classmethod
    def validate_config(cls, config: dict[str, Any] | None) -> dict[str, Any]:
        """Validate external app configuration based on its declared mode.

        Args:
            config: Configuration dictionary to validate

        Returns:
            Validated and sanitized configuration dictionary

        Raises:
            ExternalAppConfigValidationError: If the config is missing or invalid
            UnsupportedExternalAppModeError: If the mode is not supported
        """
        if not config:
            raise ExternalAppConfigValidationError(
                message="config is required",
                errors=["config must be a non-empty object with a 'mode' field"],
            )

        raw_mode = config.get("mode")
        if not isinstance(raw_mode, str):
            raise ExternalAppConfigValidationError(
                message="config.mode is required",
                errors=["config.mode must be a string ('url' or 'iframe')"],
            )

        try:
            mode = ExternalAppModeEnum(raw_mode)
        except ValueError as e:
            raise UnsupportedExternalAppModeError(raw_mode) from e

        validator = cls.get_validator(mode)
        return validator.validate(config)

    @classmethod
    def get_supported_modes(cls) -> list[ExternalAppModeEnum]:
        """Get the list of supported external app modes."""
        return list(cls._validators.keys())
