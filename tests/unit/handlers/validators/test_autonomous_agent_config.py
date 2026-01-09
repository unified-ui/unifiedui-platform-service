"""Tests for autonomous agent configuration validators."""
import pytest
from pydantic import ValidationError

from unifiedui.handlers.validators.autonomous_agent_config import (
    AutonomousAgentConfigValidatorFactory,
    N8NAutonomousAgentConfigValidator,
    N8NAutonomousAgentConfig,
)
from unifiedui.core.database.enums import AutonomousAgentTypeEnum
from unifiedui.exc.autonomous_agents import (
    AutonomousAgentConfigValidationError,
    UnsupportedAutonomousAgentTypeError,
)


class TestN8NAutonomousAgentConfig:
    """Tests for N8NAutonomousAgentConfig Pydantic model."""
    
    def test_valid_config(self):
        """Test a valid N8N autonomous agent configuration."""
        config = N8NAutonomousAgentConfig(
            api_version="v1",
            workflow_endpoint="http://localhost:5678/workflow/test-workflow-id",
            api_api_key_credential_id="cred-123"
        )
        
        assert config.api_version == "v1"
        assert config.workflow_endpoint == "http://localhost:5678/workflow/test-workflow-id"
        assert config.api_api_key_credential_id == "cred-123"
    
    def test_valid_config_with_https(self):
        """Test that https:// URLs are valid."""
        config = N8NAutonomousAgentConfig(
            api_version="v1",
            workflow_endpoint="https://n8n.example.com/workflow/my-workflow",
            api_api_key_credential_id="cred-456"
        )
        assert config.workflow_endpoint == "https://n8n.example.com/workflow/my-workflow"
    
    def test_api_version_v1_only(self):
        """Test that only 'v1' is a valid API version."""
        # Valid: v1
        config = N8NAutonomousAgentConfig(
            api_version="v1",
            workflow_endpoint="http://localhost:5678/workflow/test",
            api_api_key_credential_id="cred-123"
        )
        assert config.api_version == "v1"
    
    def test_invalid_api_version_v2(self):
        """Test that 'v2' API version is invalid."""
        with pytest.raises(ValidationError) as exc_info:
            N8NAutonomousAgentConfig(
                api_version="v2",
                workflow_endpoint="http://localhost:5678/workflow/test",
                api_api_key_credential_id="cred-123"
            )
        assert "api_version must be one of: v1" in str(exc_info.value)
    
    def test_invalid_api_version_empty(self):
        """Test that empty API version is invalid."""
        with pytest.raises(ValidationError):
            N8NAutonomousAgentConfig(
                api_version="",
                workflow_endpoint="http://localhost:5678/workflow/test",
                api_api_key_credential_id="cred-123"
            )
    
    def test_invalid_api_version_number(self):
        """Test that numeric API version is invalid."""
        with pytest.raises(ValidationError):
            N8NAutonomousAgentConfig(
                api_version="1",
                workflow_endpoint="http://localhost:5678/workflow/test",
                api_api_key_credential_id="cred-123"
            )
    
    def test_missing_api_version(self):
        """Test that missing api_version raises ValidationError."""
        with pytest.raises(ValidationError):
            N8NAutonomousAgentConfig(
                workflow_endpoint="http://localhost:5678/workflow/test",
                api_api_key_credential_id="cred-123"
            )
    
    def test_workflow_endpoint_must_be_http_or_https(self):
        """Test that workflow_endpoint must start with http:// or https://."""
        with pytest.raises(ValidationError) as exc_info:
            N8NAutonomousAgentConfig(
                api_version="v1",
                workflow_endpoint="ftp://example.com/workflow/test",
                api_api_key_credential_id="cred-123"
            )
        assert "must start with http:// or https://" in str(exc_info.value)
    
    def test_workflow_endpoint_must_contain_workflow_path(self):
        """Test that workflow_endpoint must contain /workflow/ path."""
        with pytest.raises(ValidationError) as exc_info:
            N8NAutonomousAgentConfig(
                api_version="v1",
                workflow_endpoint="http://localhost:5678/webhook/test",
                api_api_key_credential_id="cred-123"
            )
        assert "must contain '/workflow/'" in str(exc_info.value)
    
    def test_missing_workflow_endpoint(self):
        """Test that missing workflow_endpoint raises ValidationError."""
        with pytest.raises(ValidationError):
            N8NAutonomousAgentConfig(
                api_version="v1",
                api_api_key_credential_id="cred-123"
            )
    
    def test_empty_workflow_endpoint(self):
        """Test that empty workflow_endpoint is invalid."""
        with pytest.raises(ValidationError):
            N8NAutonomousAgentConfig(
                api_version="v1",
                workflow_endpoint="",
                api_api_key_credential_id="cred-123"
            )
    
    def test_missing_credential_id(self):
        """Test that missing api_api_key_credential_id raises ValidationError."""
        with pytest.raises(ValidationError):
            N8NAutonomousAgentConfig(
                api_version="v1",
                workflow_endpoint="http://localhost:5678/workflow/test"
            )
    
    def test_empty_credential_id(self):
        """Test that empty credential ID is not allowed."""
        with pytest.raises(ValidationError):
            N8NAutonomousAgentConfig(
                api_version="v1",
                workflow_endpoint="http://localhost:5678/workflow/test",
                api_api_key_credential_id=""
            )


class TestN8NAutonomousAgentConfigValidator:
    """Tests for N8NAutonomousAgentConfigValidator."""
    
    def test_validate_valid_config(self):
        """Test validation of a valid config."""
        validator = N8NAutonomousAgentConfigValidator()
        config = {
            "api_version": "v1",
            "workflow_endpoint": "http://localhost:5678/workflow/my-workflow",
            "api_api_key_credential_id": "cred-123"
        }
        
        result = validator.validate(config)
        
        assert result["api_version"] == "v1"
        assert result["workflow_endpoint"] == "http://localhost:5678/workflow/my-workflow"
        assert result["api_api_key_credential_id"] == "cred-123"
    
    def test_validate_invalid_api_version_raises_error(self):
        """Test that invalid API version raises AutonomousAgentConfigValidationError."""
        validator = N8NAutonomousAgentConfigValidator()
        config = {
            "api_version": "v2",
            "workflow_endpoint": "http://localhost:5678/workflow/test",
            "api_api_key_credential_id": "cred-123"
        }
        
        with pytest.raises(AutonomousAgentConfigValidationError) as exc_info:
            validator.validate(config)
        assert "validation failed" in str(exc_info.value).lower()
    
    def test_validate_missing_required_field(self):
        """Test that missing required field raises error."""
        validator = N8NAutonomousAgentConfigValidator()
        config = {
            "api_version": "v1",
            # Missing workflow_endpoint and api_api_key_credential_id
        }
        
        with pytest.raises(AutonomousAgentConfigValidationError):
            validator.validate(config)
    
    def test_validate_invalid_url_format(self):
        """Test that invalid URL format raises error."""
        validator = N8NAutonomousAgentConfigValidator()
        config = {
            "api_version": "v1",
            "workflow_endpoint": "not-a-url",
            "api_api_key_credential_id": "cred-123"
        }
        
        with pytest.raises(AutonomousAgentConfigValidationError):
            validator.validate(config)
    
    def test_get_supported_type(self):
        """Test that validator returns correct supported type."""
        validator = N8NAutonomousAgentConfigValidator()
        assert validator.get_supported_type() == AutonomousAgentTypeEnum.N8N


class TestAutonomousAgentConfigValidatorFactory:
    """Tests for AutonomousAgentConfigValidatorFactory."""
    
    def test_get_validator_for_n8n(self):
        """Test getting validator for N8N type."""
        validator = AutonomousAgentConfigValidatorFactory.get_validator(
            AutonomousAgentTypeEnum.N8N
        )
        
        assert isinstance(validator, N8NAutonomousAgentConfigValidator)
    
    def test_validate_config_valid(self):
        """Test validating valid config through factory."""
        config = {
            "api_version": "v1",
            "workflow_endpoint": "http://localhost:5678/workflow/test",
            "api_api_key_credential_id": "cred-123"
        }
        
        result = AutonomousAgentConfigValidatorFactory.validate_config(
            AutonomousAgentTypeEnum.N8N,
            config
        )
        
        assert result["api_version"] == "v1"
    
    def test_validate_config_empty_raises_error(self):
        """Test that empty config raises error."""
        with pytest.raises(AutonomousAgentConfigValidationError) as exc_info:
            AutonomousAgentConfigValidatorFactory.validate_config(
                AutonomousAgentTypeEnum.N8N,
                {}
            )
        assert "required" in str(exc_info.value).lower()
    
    def test_validate_config_none_raises_error(self):
        """Test that None config raises error."""
        with pytest.raises(AutonomousAgentConfigValidationError):
            AutonomousAgentConfigValidatorFactory.validate_config(
                AutonomousAgentTypeEnum.N8N,
                None
            )
    
    def test_is_supported_n8n(self):
        """Test that N8N is supported."""
        assert AutonomousAgentConfigValidatorFactory.is_supported(AutonomousAgentTypeEnum.N8N)
    
    def test_get_supported_types(self):
        """Test getting list of supported types."""
        types = AutonomousAgentConfigValidatorFactory.get_supported_types()
        
        assert isinstance(types, list)
        assert AutonomousAgentTypeEnum.N8N in types


class TestN8NAutonomousAgentConfigApiVersion:
    """Dedicated tests for api_version field validation."""
    
    def test_api_version_required(self):
        """Test that api_version is a required field."""
        with pytest.raises(ValidationError) as exc_info:
            N8NAutonomousAgentConfig(
                workflow_endpoint="http://localhost:5678/workflow/test",
                api_api_key_credential_id="cred-123"
            )
        # Should mention api_version is required
        assert "api_version" in str(exc_info.value)
    
    def test_api_version_allowed_values(self):
        """Test allowed values for api_version (currently only v1)."""
        # v1 is valid
        config = N8NAutonomousAgentConfig(
            api_version="v1",
            workflow_endpoint="http://localhost:5678/workflow/test",
            api_api_key_credential_id="cred-123"
        )
        assert config.api_version == "v1"
        
        # Other versions should fail
        invalid_versions = ["v0", "v2", "v3", "1.0", "2.0", "latest", "beta"]
        for version in invalid_versions:
            with pytest.raises(ValidationError):
                N8NAutonomousAgentConfig(
                    api_version=version,
                    workflow_endpoint="http://localhost:5678/workflow/test",
                    api_api_key_credential_id="cred-123"
                )
    
    def test_api_version_case_sensitive(self):
        """Test that api_version is case sensitive (V1 should fail)."""
        with pytest.raises(ValidationError):
            N8NAutonomousAgentConfig(
                api_version="V1",  # Uppercase should fail
                workflow_endpoint="http://localhost:5678/workflow/test",
                api_api_key_credential_id="cred-123"
            )
