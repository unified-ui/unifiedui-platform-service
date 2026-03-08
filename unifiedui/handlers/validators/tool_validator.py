"""Tool configuration validators using factory pattern."""

from abc import ABC, abstractmethod
from typing import Any

from unifiedui.core.database.enums import ToolTypeEnum
from unifiedui.exc.tools import ToolConfigValidationError, UnsupportedToolTypeError
from unifiedui.logger import get_logger

logger = get_logger(__name__)


# ========== Base Validator Interface ==========


class BaseToolConfigValidator(ABC):
    """Abstract base class for tool config validators."""

    @abstractmethod
    def validate(self, config: dict[str, Any]) -> dict[str, Any]:
        """Validate the configuration and return the validated config.

        Args:
            config: Configuration dictionary to validate

        Returns:
            Validated configuration dictionary

        Raises:
            ToolConfigValidationError: If validation fails
        """
        pass

    @abstractmethod
    def get_supported_type(self) -> ToolTypeEnum:
        """Get the tool type this validator supports."""
        pass


# ========== MCP Server Validator ==========

MCP_SERVER_REQUIRED_FIELDS = {"server_url", "transport"}
MCP_SERVER_VALID_TRANSPORTS = {"sse", "stdio", "streamable-http"}


class MCPServerConfigValidator(BaseToolConfigValidator):
    """Validator for MCP Server tool configuration."""

    def validate(self, config: dict[str, Any]) -> dict[str, Any]:
        """Validate MCP Server configuration.

        Args:
            config: Configuration dictionary to validate

        Returns:
            Validated configuration dictionary

        Raises:
            ToolConfigValidationError: If validation fails
        """
        errors: list[str] = []

        if not config:
            raise ToolConfigValidationError(message="MCP Server config must not be empty", errors=["Empty config"])

        missing_fields = MCP_SERVER_REQUIRED_FIELDS - set(config.keys())
        if missing_fields:
            errors.append(f"Missing required fields: {', '.join(sorted(missing_fields))}")

        transport = config.get("transport")
        if transport and transport not in MCP_SERVER_VALID_TRANSPORTS:
            errors.append(
                f"Invalid transport '{transport}'. Must be one of: {', '.join(sorted(MCP_SERVER_VALID_TRANSPORTS))}"
            )

        server_url = config.get("server_url")
        if server_url and not isinstance(server_url, str):
            errors.append("server_url must be a string")
        elif server_url and not server_url.startswith(("http://", "https://")):
            errors.append("server_url must start with http:// or https://")

        tools = config.get("tools")
        if tools is not None:
            if not isinstance(tools, list):
                errors.append("tools must be a list of tool definitions")
            else:
                for i, tool in enumerate(tools):
                    if not isinstance(tool, dict):
                        errors.append(f"tools[{i}] must be an object")
                        continue
                    if "name" not in tool:
                        errors.append(f"tools[{i}] missing required field 'name'")
                    if "description" not in tool:
                        errors.append(f"tools[{i}] missing required field 'description'")

        if errors:
            raise ToolConfigValidationError(message="MCP Server configuration validation failed", errors=errors)

        logger.debug("MCP Server config validation passed", extra={"config_keys": list(config.keys())})
        return config

    def get_supported_type(self) -> ToolTypeEnum:
        """Get the tool type this validator supports."""
        return ToolTypeEnum.MCP_SERVER


# ========== OpenAPI Definition Validator ==========

OPENAPI_MIN_VERSION = "3.0.0"


class OpenAPIDefinitionConfigValidator(BaseToolConfigValidator):
    """Validator for OpenAPI Definition tool configuration."""

    def validate(self, config: dict[str, Any]) -> dict[str, Any]:
        """Validate OpenAPI Definition configuration.

        Args:
            config: Configuration dictionary containing the OpenAPI spec under 'spec' key

        Returns:
            Validated configuration dictionary

        Raises:
            ToolConfigValidationError: If validation fails
        """
        errors: list[str] = []

        if not config:
            raise ToolConfigValidationError(
                message="OpenAPI Definition config must not be empty", errors=["Empty config"]
            )

        spec = config.get("spec")
        if not spec and config.get("openapi") and config.get("info"):
            spec = dict(config)
            config.clear()
            config["spec"] = spec

        if not spec:
            raise ToolConfigValidationError(
                message="OpenAPI Definition config must contain a 'spec' field with the OpenAPI specification",
                errors=["Missing 'spec' field"],
            )

        if not isinstance(spec, dict):
            raise ToolConfigValidationError(
                message="The 'spec' field must be a valid OpenAPI specification object",
                errors=["'spec' must be a JSON object"],
            )

        openapi_version = spec.get("openapi", "")
        if not openapi_version:
            errors.append("Missing 'openapi' version field in spec. Only OpenAPI 3.x is supported.")
        elif not str(openapi_version).startswith("3."):
            errors.append(
                f"Unsupported OpenAPI version '{openapi_version}'. Only OpenAPI 3.x (>= {OPENAPI_MIN_VERSION}) is supported."
            )

        if "info" not in spec:
            errors.append("Missing required 'info' field in spec")

        if "paths" not in spec and "webhooks" not in spec:
            errors.append("Spec must contain at least 'paths' or 'webhooks'")

        if errors:
            raise ToolConfigValidationError(message="OpenAPI specification pre-validation failed", errors=errors)

        try:
            from openapi_spec_validator import validate

            validate(spec)
        except ToolConfigValidationError:
            raise
        except Exception as e:
            error_msg = str(e)
            logger.error(
                "OpenAPI spec validation error",
                extra={"error_type": type(e).__name__, "error_msg": error_msg[:500]},
            )
            if len(error_msg) > 500:
                error_msg = error_msg[:500] + "..."
            raise ToolConfigValidationError(message="OpenAPI specification validation failed", errors=[error_msg])

        security_schemes = spec.get("components", {}).get("securitySchemes", {})
        requires_auth = bool(security_schemes) or bool(spec.get("security"))
        config["requires_auth"] = requires_auth

        if requires_auth:
            supported_auth_types = {"apiKey"}
            unsupported = []
            for scheme_name, scheme in security_schemes.items():
                scheme_type = scheme.get("type", "")
                if scheme_type not in supported_auth_types:
                    unsupported.append(f"{scheme_name} ({scheme_type})")

            if unsupported:
                config["unsupported_auth_schemes"] = unsupported
                config["auth_warning"] = (
                    f"Unsupported auth schemes detected: {', '.join(unsupported)}. "
                    "Currently only 'apiKey' authentication is supported."
                )

        logger.debug("OpenAPI Definition config validation passed", extra={"config_keys": list(config.keys())})
        return config

    def get_supported_type(self) -> ToolTypeEnum:
        """Get the tool type this validator supports."""
        return ToolTypeEnum.OPENAPI_DEFINITION


# ========== Factory ==========


class ToolConfigValidatorFactory:
    """Factory for creating tool config validators based on tool type."""

    _validators: dict[ToolTypeEnum, BaseToolConfigValidator] = {
        ToolTypeEnum.MCP_SERVER: MCPServerConfigValidator(),
        ToolTypeEnum.OPENAPI_DEFINITION: OpenAPIDefinitionConfigValidator(),
    }

    @classmethod
    def get_validator(cls, tool_type: str) -> BaseToolConfigValidator:
        """
        Get the appropriate validator for the given tool type.

        Args:
            tool_type: Tool type string (MCP_SERVER, OPENAPI_DEFINITION)

        Returns:
            Appropriate validator instance

        Raises:
            UnsupportedToolTypeError: If tool type is not supported
        """
        try:
            enum_type = ToolTypeEnum(tool_type)
        except ValueError:
            raise UnsupportedToolTypeError(tool_type)

        validator = cls._validators.get(enum_type)
        if not validator:
            raise UnsupportedToolTypeError(tool_type)

        return validator

    @classmethod
    def validate_config(cls, tool_type: str, config: dict[str, Any]) -> dict[str, Any]:
        """
        Validate a tool configuration using the appropriate validator.

        Args:
            tool_type: Tool type string
            config: Configuration dictionary to validate

        Returns:
            Validated configuration dictionary

        Raises:
            UnsupportedToolTypeError: If tool type is not supported
            ToolConfigValidationError: If validation fails
        """
        validator = cls.get_validator(tool_type)
        return validator.validate(config)
