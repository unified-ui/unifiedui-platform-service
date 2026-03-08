"""Tests for tool configuration validators."""

import sys
import types
from unittest.mock import MagicMock, patch

import pytest

from unifiedui.core.database.enums import ToolTypeEnum
from unifiedui.exc.tools import ToolConfigValidationError, UnsupportedToolTypeError

# Ensure openapi_spec_validator is available in sys.modules for tests.
# The pytest binary may use a different Python interpreter where this package
# is not installed. We inject a mock module so the lazy import inside
# OpenAPIDefinitionConfigValidator.validate() succeeds.
if "openapi_spec_validator" not in sys.modules:
    _mock_osv = types.ModuleType("openapi_spec_validator")
    _mock_osv.validate = MagicMock()  # type: ignore[attr-defined]
    sys.modules["openapi_spec_validator"] = _mock_osv

from unifiedui.handlers.validators.tool_validator import (
    MCPServerConfigValidator,
    OpenAPIDefinitionConfigValidator,
    ToolConfigValidatorFactory,
)

MINIMAL_OPENAPI_SPEC: dict = {
    "openapi": "3.0.3",
    "info": {"title": "Test API", "version": "1.0.0"},
    "paths": {
        "/items": {
            "get": {
                "summary": "List items",
                "operationId": "listItems",
                "responses": {"200": {"description": "OK"}},
            }
        }
    },
}

OPENAPI_SPEC_WITH_API_KEY_AUTH: dict = {
    "openapi": "3.0.3",
    "info": {"title": "Secured API", "version": "1.0.0"},
    "paths": {
        "/secure": {
            "get": {
                "summary": "Secured endpoint",
                "operationId": "securedGet",
                "responses": {"200": {"description": "OK"}},
            }
        }
    },
    "components": {"securitySchemes": {"apiKeyAuth": {"type": "apiKey", "in": "header", "name": "X-API-Key"}}},
    "security": [{"apiKeyAuth": []}],
}

OPENAPI_SPEC_WITH_OAUTH_AUTH: dict = {
    "openapi": "3.0.3",
    "info": {"title": "OAuth API", "version": "1.0.0"},
    "paths": {
        "/oauth": {
            "get": {
                "summary": "OAuth endpoint",
                "operationId": "oauthGet",
                "responses": {"200": {"description": "OK"}},
            }
        }
    },
    "components": {
        "securitySchemes": {
            "oauthFlow": {
                "type": "oauth2",
                "flows": {
                    "implicit": {
                        "authorizationUrl": "https://example.com/oauth/authorize",
                        "scopes": {"read": "Read access"},
                    }
                },
            }
        }
    },
    "security": [{"oauthFlow": ["read"]}],
}


def _mock_openapi_validate_noop(spec: dict) -> None:
    """Mock that accepts any spec without error."""


def _mock_openapi_validate_fail(spec: dict) -> None:
    """Mock that always raises a validation error."""
    raise ValueError("Mock OpenAPI validation error: invalid reference")


# ========== MCPServerConfigValidator Tests ==========


class TestMCPServerConfigValidator:
    """Tests for MCPServerConfigValidator."""

    def setup_method(self) -> None:
        """Set up the validator instance."""
        self.validator = MCPServerConfigValidator()

    def test_get_supported_type(self) -> None:
        """Test that supported type is MCP_SERVER."""
        assert self.validator.get_supported_type() == ToolTypeEnum.MCP_SERVER

    def test_valid_config_sse(self) -> None:
        """Test valid MCP config with SSE transport."""
        config = {
            "server_url": "https://mcp.example.com",
            "transport": "sse",
        }
        result = self.validator.validate(config)

        assert result["server_url"] == "https://mcp.example.com"
        assert result["transport"] == "sse"

    def test_valid_config_stdio(self) -> None:
        """Test valid MCP config with stdio transport."""
        config = {
            "server_url": "https://mcp.example.com",
            "transport": "stdio",
        }
        result = self.validator.validate(config)

        assert result["transport"] == "stdio"

    def test_valid_config_streamable_http(self) -> None:
        """Test valid MCP config with streamable-http transport."""
        config = {
            "server_url": "https://mcp.example.com",
            "transport": "streamable-http",
        }
        result = self.validator.validate(config)

        assert result["transport"] == "streamable-http"

    def test_valid_config_with_tools(self) -> None:
        """Test valid MCP config with tool definitions."""
        config = {
            "server_url": "https://mcp.example.com",
            "transport": "sse",
            "tools": [
                {"name": "search", "description": "Search tool"},
                {"name": "fetch", "description": "Fetch tool"},
            ],
        }
        result = self.validator.validate(config)

        assert len(result["tools"]) == 2

    def test_valid_config_with_http_url(self) -> None:
        """Test valid MCP config with http:// URL."""
        config = {
            "server_url": "http://localhost:8080",
            "transport": "sse",
        }
        result = self.validator.validate(config)

        assert result["server_url"] == "http://localhost:8080"

    def test_empty_config_raises_error(self) -> None:
        """Test that empty config raises ToolConfigValidationError."""
        with pytest.raises(ToolConfigValidationError) as exc_info:
            self.validator.validate({})

        assert "must not be empty" in exc_info.value.message

    def test_none_config_raises_error(self) -> None:
        """Test that None-like empty config raises ToolConfigValidationError."""
        with pytest.raises(ToolConfigValidationError) as exc_info:
            self.validator.validate({})

        assert "must not be empty" in exc_info.value.message

    def test_missing_server_url(self) -> None:
        """Test that missing server_url field raises error."""
        config = {"transport": "sse"}

        with pytest.raises(ToolConfigValidationError) as exc_info:
            self.validator.validate(config)

        assert "server_url" in str(exc_info.value.errors)

    def test_missing_transport(self) -> None:
        """Test that missing transport field raises error."""
        config = {"server_url": "https://mcp.example.com"}

        with pytest.raises(ToolConfigValidationError) as exc_info:
            self.validator.validate(config)

        assert "transport" in str(exc_info.value.errors)

    def test_missing_both_required_fields(self) -> None:
        """Test that missing both required fields raises error with both mentioned."""
        config = {"extra_field": "value"}

        with pytest.raises(ToolConfigValidationError) as exc_info:
            self.validator.validate(config)

        errors_str = str(exc_info.value.errors)
        assert "server_url" in errors_str
        assert "transport" in errors_str

    def test_invalid_transport_value(self) -> None:
        """Test that invalid transport value raises error."""
        config = {
            "server_url": "https://mcp.example.com",
            "transport": "websocket",
        }

        with pytest.raises(ToolConfigValidationError) as exc_info:
            self.validator.validate(config)

        assert "websocket" in str(exc_info.value.errors)
        assert "sse" in str(exc_info.value.errors)

    def test_invalid_server_url_no_scheme(self) -> None:
        """Test that server_url without http/https scheme raises error."""
        config = {
            "server_url": "mcp.example.com",
            "transport": "sse",
        }

        with pytest.raises(ToolConfigValidationError) as exc_info:
            self.validator.validate(config)

        assert "http://" in str(exc_info.value.errors)

    def test_server_url_non_string(self) -> None:
        """Test that non-string server_url raises error."""
        config = {
            "server_url": 12345,
            "transport": "sse",
        }

        with pytest.raises(ToolConfigValidationError) as exc_info:
            self.validator.validate(config)

        assert "must be a string" in str(exc_info.value.errors)

    def test_tools_not_a_list(self) -> None:
        """Test that tools as non-list raises error."""
        config = {
            "server_url": "https://mcp.example.com",
            "transport": "sse",
            "tools": "not-a-list",
        }

        with pytest.raises(ToolConfigValidationError) as exc_info:
            self.validator.validate(config)

        assert "must be a list" in str(exc_info.value.errors)

    def test_tools_item_not_a_dict(self) -> None:
        """Test that non-dict items in tools list raise error."""
        config = {
            "server_url": "https://mcp.example.com",
            "transport": "sse",
            "tools": ["not-a-dict"],
        }

        with pytest.raises(ToolConfigValidationError) as exc_info:
            self.validator.validate(config)

        assert "tools[0] must be an object" in str(exc_info.value.errors)

    def test_tools_item_missing_name(self) -> None:
        """Test that tool item missing 'name' raises error."""
        config = {
            "server_url": "https://mcp.example.com",
            "transport": "sse",
            "tools": [{"description": "A tool without a name"}],
        }

        with pytest.raises(ToolConfigValidationError) as exc_info:
            self.validator.validate(config)

        assert "tools[0] missing required field 'name'" in str(exc_info.value.errors)

    def test_tools_item_missing_description(self) -> None:
        """Test that tool item missing 'description' raises error."""
        config = {
            "server_url": "https://mcp.example.com",
            "transport": "sse",
            "tools": [{"name": "tool_no_desc"}],
        }

        with pytest.raises(ToolConfigValidationError) as exc_info:
            self.validator.validate(config)

        assert "tools[0] missing required field 'description'" in str(exc_info.value.errors)

    def test_tools_none_value_is_valid(self) -> None:
        """Test that tools=None does not trigger tools validation."""
        config = {
            "server_url": "https://mcp.example.com",
            "transport": "sse",
            "tools": None,
        }
        result = self.validator.validate(config)

        assert result["tools"] is None

    def test_extra_fields_are_preserved(self) -> None:
        """Test that extra unrecognized fields are preserved."""
        config = {
            "server_url": "https://mcp.example.com",
            "transport": "sse",
            "custom_field": "custom_value",
        }
        result = self.validator.validate(config)

        assert result["custom_field"] == "custom_value"

    def test_multiple_errors_collected(self) -> None:
        """Test that multiple validation errors are collected and reported."""
        config = {
            "server_url": "no-scheme.example.com",
            "transport": "invalid-transport",
            "tools": "not-a-list",
        }

        with pytest.raises(ToolConfigValidationError) as exc_info:
            self.validator.validate(config)

        assert len(exc_info.value.errors) >= 3


# ========== OpenAPIDefinitionConfigValidator Tests ==========


class TestOpenAPIDefinitionConfigValidator:
    """Tests for OpenAPIDefinitionConfigValidator."""

    def setup_method(self) -> None:
        """Set up the validator instance."""
        self.validator = OpenAPIDefinitionConfigValidator()

    def test_get_supported_type(self) -> None:
        """Test that supported type is OPENAPI_DEFINITION."""
        assert self.validator.get_supported_type() == ToolTypeEnum.OPENAPI_DEFINITION

    @patch("openapi_spec_validator.validate", side_effect=_mock_openapi_validate_noop)
    def test_valid_spec_wrapped(self, _mock_validate: object) -> None:
        """Test valid OpenAPI spec wrapped in spec field."""
        config = {"spec": dict(MINIMAL_OPENAPI_SPEC)}
        result = self.validator.validate(config)

        assert "spec" in result
        assert result["requires_auth"] is False

    @patch("openapi_spec_validator.validate", side_effect=_mock_openapi_validate_noop)
    def test_valid_spec_raw_auto_wraps(self, _mock_validate: object) -> None:
        """Test that raw OpenAPI spec without spec wrapper is auto-wrapped."""
        config = dict(MINIMAL_OPENAPI_SPEC)
        result = self.validator.validate(config)

        assert "spec" in result
        assert result["spec"]["openapi"] == "3.0.3"
        assert result["requires_auth"] is False

    def test_empty_config_raises_error(self) -> None:
        """Test that empty config raises ToolConfigValidationError."""
        with pytest.raises(ToolConfigValidationError) as exc_info:
            self.validator.validate({})

        assert "must not be empty" in exc_info.value.message

    def test_missing_spec_field(self) -> None:
        """Test that config without spec and without openapi/info raises error."""
        config = {"not_spec": "something"}

        with pytest.raises(ToolConfigValidationError) as exc_info:
            self.validator.validate(config)

        assert "spec" in exc_info.value.message.lower()

    def test_spec_not_a_dict(self) -> None:
        """Test that spec as non-dict raises error."""
        config = {"spec": "not-a-dict"}

        with pytest.raises(ToolConfigValidationError) as exc_info:
            self.validator.validate(config)

        assert "JSON object" in str(exc_info.value.errors)

    def test_spec_as_list_raises_error(self) -> None:
        """Test that spec as list raises error."""
        config = {"spec": [{"openapi": "3.0.3"}]}

        with pytest.raises(ToolConfigValidationError) as exc_info:
            self.validator.validate(config)

        assert "JSON object" in str(exc_info.value.errors)

    def test_missing_openapi_version(self) -> None:
        """Test that spec without openapi version field raises error."""
        config = {
            "spec": {
                "info": {"title": "No Version", "version": "1.0.0"},
                "paths": {},
            }
        }

        with pytest.raises(ToolConfigValidationError) as exc_info:
            self.validator.validate(config)

        assert "openapi" in str(exc_info.value.errors).lower()

    def test_unsupported_openapi_version_2(self) -> None:
        """Test that OpenAPI 2.x (Swagger) is rejected."""
        config = {
            "spec": {
                "openapi": "2.0",
                "info": {"title": "Swagger API", "version": "1.0.0"},
                "paths": {},
            }
        }

        with pytest.raises(ToolConfigValidationError) as exc_info:
            self.validator.validate(config)

        assert "Unsupported OpenAPI version" in str(exc_info.value.errors)
        assert "2.0" in str(exc_info.value.errors)

    def test_missing_info_field(self) -> None:
        """Test that spec without info field raises error."""
        config = {
            "spec": {
                "openapi": "3.0.3",
                "paths": {},
            }
        }

        with pytest.raises(ToolConfigValidationError) as exc_info:
            self.validator.validate(config)

        assert "info" in str(exc_info.value.errors)

    def test_missing_paths_and_webhooks(self) -> None:
        """Test that spec without paths or webhooks raises error."""
        config = {
            "spec": {
                "openapi": "3.0.3",
                "info": {"title": "No Paths", "version": "1.0.0"},
            }
        }

        with pytest.raises(ToolConfigValidationError) as exc_info:
            self.validator.validate(config)

        assert "paths" in str(exc_info.value.errors).lower()

    @patch("openapi_spec_validator.validate", side_effect=_mock_openapi_validate_noop)
    def test_spec_with_webhooks_instead_of_paths(self, _mock_validate: object) -> None:
        """Test that spec with webhooks (no paths) passes pre-validation."""
        config = {
            "spec": {
                "openapi": "3.1.0",
                "info": {"title": "Webhook API", "version": "1.0.0"},
                "webhooks": {
                    "newItem": {
                        "post": {
                            "summary": "New item webhook",
                            "operationId": "newItemWebhook",
                            "responses": {"200": {"description": "OK"}},
                        }
                    }
                },
            }
        }
        result = self.validator.validate(config)

        assert result["requires_auth"] is False

    def test_multiple_pre_validation_errors(self) -> None:
        """Test that multiple pre-validation errors are collected."""
        config = {
            "spec": {
                "openapi": "2.0",
            }
        }

        with pytest.raises(ToolConfigValidationError) as exc_info:
            self.validator.validate(config)

        assert len(exc_info.value.errors) >= 2

    @patch("openapi_spec_validator.validate", side_effect=_mock_openapi_validate_fail)
    def test_invalid_spec_fails_openapi_validation(self, _mock_validate: object) -> None:
        """Test that openapi_spec_validator errors are caught and re-raised."""
        config = {"spec": dict(MINIMAL_OPENAPI_SPEC)}

        with pytest.raises(ToolConfigValidationError) as exc_info:
            self.validator.validate(config)

        assert "validation failed" in exc_info.value.message.lower()
        assert len(exc_info.value.errors) >= 1

    @patch("openapi_spec_validator.validate", side_effect=_mock_openapi_validate_noop)
    def test_auth_detection_api_key(self, _mock_validate: object) -> None:
        """Test that apiKey security scheme is detected."""
        config = {"spec": dict(OPENAPI_SPEC_WITH_API_KEY_AUTH)}
        result = self.validator.validate(config)

        assert result["requires_auth"] is True

    @patch("openapi_spec_validator.validate", side_effect=_mock_openapi_validate_noop)
    def test_auth_detection_unsupported_oauth(self, _mock_validate: object) -> None:
        """Test that unsupported OAuth scheme is detected with warning."""
        config = {"spec": dict(OPENAPI_SPEC_WITH_OAUTH_AUTH)}
        result = self.validator.validate(config)

        assert result["requires_auth"] is True
        assert "unsupported_auth_schemes" in result
        assert any("oauth2" in s for s in result["unsupported_auth_schemes"])
        assert "auth_warning" in result

    @patch("openapi_spec_validator.validate", side_effect=_mock_openapi_validate_noop)
    def test_auth_detection_no_security(self, _mock_validate: object) -> None:
        """Test that spec without security schemes sets requires_auth=False."""
        config = {"spec": dict(MINIMAL_OPENAPI_SPEC)}
        result = self.validator.validate(config)

        assert result["requires_auth"] is False
        assert "unsupported_auth_schemes" not in result
        assert "auth_warning" not in result

    @patch("openapi_spec_validator.validate", side_effect=_mock_openapi_validate_noop)
    def test_auth_detection_api_key_no_warning(self, _mock_validate: object) -> None:
        """Test that supported apiKey auth does not produce warnings."""
        config = {"spec": dict(OPENAPI_SPEC_WITH_API_KEY_AUTH)}
        result = self.validator.validate(config)

        assert result["requires_auth"] is True
        assert "unsupported_auth_schemes" not in result
        assert "auth_warning" not in result

    @patch("openapi_spec_validator.validate", side_effect=_mock_openapi_validate_noop)
    def test_openapi_version_3_1_supported(self, _mock_validate: object) -> None:
        """Test that OpenAPI 3.1.x is supported."""
        spec = dict(MINIMAL_OPENAPI_SPEC)
        spec["openapi"] = "3.1.0"
        config = {"spec": spec}

        result = self.validator.validate(config)

        assert "spec" in result

    @patch("openapi_spec_validator.validate", side_effect=_mock_openapi_validate_noop)
    def test_raw_spec_with_openapi_and_info_auto_wraps(self, _mock_validate: object) -> None:
        """Test auto-wrap for raw spec that has openapi and info fields."""
        config = {
            "openapi": "3.0.3",
            "info": {"title": "Raw Spec", "version": "1.0.0"},
            "paths": {
                "/test": {
                    "get": {
                        "summary": "Test",
                        "operationId": "test",
                        "responses": {"200": {"description": "OK"}},
                    }
                }
            },
        }

        result = self.validator.validate(config)

        assert "spec" in result
        assert result["spec"]["openapi"] == "3.0.3"
        assert result["spec"]["info"]["title"] == "Raw Spec"

    def test_raw_spec_only_openapi_no_info_not_wrapped(self) -> None:
        """Test that config with openapi but no info is not auto-wrapped."""
        config = {"openapi": "3.0.3", "paths": {}}

        with pytest.raises(ToolConfigValidationError) as exc_info:
            self.validator.validate(config)

        assert "spec" in exc_info.value.message.lower()

    def test_error_message_truncation(self) -> None:
        """Test that very long validation errors are truncated to 500 chars."""
        long_error_msg = "x" * 1000
        with patch(
            "openapi_spec_validator.validate",
            side_effect=ValueError(long_error_msg),
        ):
            config = {"spec": dict(MINIMAL_OPENAPI_SPEC)}

            with pytest.raises(ToolConfigValidationError) as exc_info:
                self.validator.validate(config)

            assert exc_info.value.errors[0].endswith("...")
            assert len(exc_info.value.errors[0]) <= 504


# ========== ToolConfigValidatorFactory Tests ==========


class TestToolConfigValidatorFactory:
    """Tests for ToolConfigValidatorFactory."""

    def test_get_validator_mcp_server(self) -> None:
        """Test getting MCP_SERVER validator."""
        validator = ToolConfigValidatorFactory.get_validator("MCP_SERVER")

        assert isinstance(validator, MCPServerConfigValidator)
        assert validator.get_supported_type() == ToolTypeEnum.MCP_SERVER

    def test_get_validator_openapi_definition(self) -> None:
        """Test getting OPENAPI_DEFINITION validator."""
        validator = ToolConfigValidatorFactory.get_validator("OPENAPI_DEFINITION")

        assert isinstance(validator, OpenAPIDefinitionConfigValidator)
        assert validator.get_supported_type() == ToolTypeEnum.OPENAPI_DEFINITION

    def test_get_validator_unsupported_type(self) -> None:
        """Test that unsupported tool type raises UnsupportedToolTypeError."""
        with pytest.raises(UnsupportedToolTypeError) as exc_info:
            ToolConfigValidatorFactory.get_validator("UNKNOWN_TYPE")

        assert "UNKNOWN_TYPE" in str(exc_info.value)

    def test_get_validator_empty_string(self) -> None:
        """Test that empty string type raises UnsupportedToolTypeError."""
        with pytest.raises(UnsupportedToolTypeError):
            ToolConfigValidatorFactory.get_validator("")

    def test_validate_config_mcp_server(self) -> None:
        """Test validate_config convenience method for MCP_SERVER."""
        config = {
            "server_url": "https://mcp.example.com",
            "transport": "sse",
        }
        result = ToolConfigValidatorFactory.validate_config("MCP_SERVER", config)

        assert result["server_url"] == "https://mcp.example.com"

    @patch("openapi_spec_validator.validate", side_effect=_mock_openapi_validate_noop)
    def test_validate_config_openapi_definition(self, _mock_validate: object) -> None:
        """Test validate_config convenience method for OPENAPI_DEFINITION."""
        config = {"spec": dict(MINIMAL_OPENAPI_SPEC)}
        result = ToolConfigValidatorFactory.validate_config("OPENAPI_DEFINITION", config)

        assert result["requires_auth"] is False

    def test_validate_config_unsupported_type(self) -> None:
        """Test validate_config raises UnsupportedToolTypeError for unknown type."""
        with pytest.raises(UnsupportedToolTypeError):
            ToolConfigValidatorFactory.validate_config("INVALID", {})

    def test_validate_config_propagates_validation_error(self) -> None:
        """Test validate_config propagates ToolConfigValidationError."""
        with pytest.raises(ToolConfigValidationError):
            ToolConfigValidatorFactory.validate_config("MCP_SERVER", {})

    def test_validate_config_lowercase_type_raises(self) -> None:
        """Test that lowercase tool type raises UnsupportedToolTypeError."""
        with pytest.raises(UnsupportedToolTypeError):
            ToolConfigValidatorFactory.get_validator("mcp_server")
