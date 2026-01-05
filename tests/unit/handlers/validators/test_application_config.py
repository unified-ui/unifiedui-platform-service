"""Tests for application configuration validators."""
import pytest
from pydantic import ValidationError

from unifiedui.handlers.validators.application_config import (
    ApplicationConfigValidatorFactory,
    N8NConfigValidator,
    N8NApplicationConfig,
    N8NApiVersionEnum,
    N8NWorkflowTypeEnum,
)
from unifiedui.core.database.enums import ApplicationTypeEnum
from unifiedui.exc.application_config import (
    ApplicationConfigValidationError,
    UnsupportedApplicationTypeError,
)


class TestN8NApiVersionEnum:
    """Tests for N8NApiVersionEnum."""
    
    def test_v1_value(self):
        """Test that v1 is a valid API version."""
        assert N8NApiVersionEnum.V1.value == "v1"
    
    def test_all_returns_list(self):
        """Test that all() returns a list of values."""
        versions = N8NApiVersionEnum.all()
        assert isinstance(versions, list)
        assert "v1" in versions


class TestN8NWorkflowTypeEnum:
    """Tests for N8NWorkflowTypeEnum."""
    
    def test_chat_workflow_value(self):
        """Test that N8N_CHAT_AGENT_WORKFLOW is a valid workflow type."""
        assert N8NWorkflowTypeEnum.N8N_CHAT_AGENT_WORKFLOW.value == "N8N_CHAT_AGENT_WORKFLOW"
    
    def test_all_returns_list(self):
        """Test that all() returns a list of values."""
        types = N8NWorkflowTypeEnum.all()
        assert isinstance(types, list)
        assert "N8N_CHAT_AGENT_WORKFLOW" in types


class TestN8NApplicationConfig:
    """Tests for N8NApplicationConfig Pydantic model."""
    
    def test_valid_config(self):
        """Test a valid N8N configuration."""
        config = N8NApplicationConfig(
            api_version=N8NApiVersionEnum.V1,
            workflow_type=N8NWorkflowTypeEnum.N8N_CHAT_AGENT_WORKFLOW,
            use_unified_chat_history=True,
            chat_history_count=30,
            chat_url="https://example.com/webhook",
            api_api_key_credential_id="cred-123",
            chat_auth_credential_id="cred-456"
        )
        
        assert config.api_version == N8NApiVersionEnum.V1
        assert config.workflow_type == N8NWorkflowTypeEnum.N8N_CHAT_AGENT_WORKFLOW
        assert config.use_unified_chat_history is True
        assert config.chat_history_count == 30
        assert config.chat_url == "https://example.com/webhook"
        assert config.api_api_key_credential_id == "cred-123"
        assert config.chat_auth_credential_id == "cred-456"
    
    def test_default_chat_history_count(self):
        """Test that chat_history_count defaults to 30."""
        config = N8NApplicationConfig(
            api_version=N8NApiVersionEnum.V1,
            workflow_type=N8NWorkflowTypeEnum.N8N_CHAT_AGENT_WORKFLOW,
            use_unified_chat_history=True,
            chat_url="https://example.com/webhook",
            api_api_key_credential_id="cred-123",
            chat_auth_credential_id="cred-456"
        )
        
        assert config.chat_history_count == 30
    
    def test_invalid_api_version(self):
        """Test that invalid API version raises ValidationError."""
        with pytest.raises(ValidationError):
            N8NApplicationConfig(
                api_version="v2",
                workflow_type=N8NWorkflowTypeEnum.N8N_CHAT_AGENT_WORKFLOW,
                use_unified_chat_history=True,
                chat_url="https://example.com/webhook",
                api_api_key_credential_id="cred-123",
                chat_auth_credential_id="cred-456"
            )
    
    def test_invalid_workflow_type(self):
        """Test that invalid workflow type raises ValidationError."""
        with pytest.raises(ValidationError):
            N8NApplicationConfig(
                api_version=N8NApiVersionEnum.V1,
                workflow_type="INVALID_WORKFLOW",
                use_unified_chat_history=True,
                chat_url="https://example.com/webhook",
                api_api_key_credential_id="cred-123",
                chat_auth_credential_id="cred-456"
            )
    
    def test_chat_url_must_be_http_or_https(self):
        """Test that chat_url must start with http:// or https://."""
        with pytest.raises(ValidationError) as exc_info:
            N8NApplicationConfig(
                api_version=N8NApiVersionEnum.V1,
                workflow_type=N8NWorkflowTypeEnum.N8N_CHAT_AGENT_WORKFLOW,
                use_unified_chat_history=True,
                chat_url="ftp://example.com/webhook",
                api_api_key_credential_id="cred-123",
                chat_auth_credential_id="cred-456"
            )
        assert "must start with http:// or https://" in str(exc_info.value)
    
    def test_http_url_is_valid(self):
        """Test that http:// URLs are valid."""
        config = N8NApplicationConfig(
            api_version=N8NApiVersionEnum.V1,
            workflow_type=N8NWorkflowTypeEnum.N8N_CHAT_AGENT_WORKFLOW,
            use_unified_chat_history=True,
            chat_url="http://localhost:5678/webhook",
            api_api_key_credential_id="cred-123",
            chat_auth_credential_id="cred-456"
        )
        assert config.chat_url == "http://localhost:5678/webhook"
    
    def test_missing_required_field(self):
        """Test that missing required field raises ValidationError."""
        with pytest.raises(ValidationError):
            N8NApplicationConfig(
                api_version=N8NApiVersionEnum.V1,
                workflow_type=N8NWorkflowTypeEnum.N8N_CHAT_AGENT_WORKFLOW,
                use_unified_chat_history=True,
                chat_url="https://example.com/webhook",
                # Missing api_api_key_credential_id and chat_auth_credential_id
            )
    
    def test_empty_credential_id_not_allowed(self):
        """Test that empty credential IDs are not allowed."""
        with pytest.raises(ValidationError):
            N8NApplicationConfig(
                api_version=N8NApiVersionEnum.V1,
                workflow_type=N8NWorkflowTypeEnum.N8N_CHAT_AGENT_WORKFLOW,
                use_unified_chat_history=True,
                chat_url="https://example.com/webhook",
                api_api_key_credential_id="",
                chat_auth_credential_id="cred-456"
            )
    
    def test_chat_history_count_range(self):
        """Test chat_history_count min/max validation."""
        # Valid: 1
        config = N8NApplicationConfig(
            api_version=N8NApiVersionEnum.V1,
            workflow_type=N8NWorkflowTypeEnum.N8N_CHAT_AGENT_WORKFLOW,
            use_unified_chat_history=True,
            chat_history_count=1,
            chat_url="https://example.com/webhook",
            api_api_key_credential_id="cred-123",
            chat_auth_credential_id="cred-456"
        )
        assert config.chat_history_count == 1
        
        # Valid: 100
        config = N8NApplicationConfig(
            api_version=N8NApiVersionEnum.V1,
            workflow_type=N8NWorkflowTypeEnum.N8N_CHAT_AGENT_WORKFLOW,
            use_unified_chat_history=True,
            chat_history_count=100,
            chat_url="https://example.com/webhook",
            api_api_key_credential_id="cred-123",
            chat_auth_credential_id="cred-456"
        )
        assert config.chat_history_count == 100
        
        # Invalid: 0
        with pytest.raises(ValidationError):
            N8NApplicationConfig(
                api_version=N8NApiVersionEnum.V1,
                workflow_type=N8NWorkflowTypeEnum.N8N_CHAT_AGENT_WORKFLOW,
                use_unified_chat_history=True,
                chat_history_count=0,
                chat_url="https://example.com/webhook",
                api_api_key_credential_id="cred-123",
                chat_auth_credential_id="cred-456"
            )
        
        # Invalid: 101
        with pytest.raises(ValidationError):
            N8NApplicationConfig(
                api_version=N8NApiVersionEnum.V1,
                workflow_type=N8NWorkflowTypeEnum.N8N_CHAT_AGENT_WORKFLOW,
                use_unified_chat_history=True,
                chat_history_count=101,
                chat_url="https://example.com/webhook",
                api_api_key_credential_id="cred-123",
                chat_auth_credential_id="cred-456"
            )


class TestN8NConfigValidator:
    """Tests for N8NConfigValidator."""
    
    def test_validate_valid_config(self):
        """Test validation of a valid config."""
        validator = N8NConfigValidator()
        config = {
            "api_version": "v1",
            "workflow_type": "N8N_CHAT_AGENT_WORKFLOW",
            "use_unified_chat_history": True,
            "chat_history_count": 25,
            "chat_url": "https://example.com/webhook",
            "api_api_key_credential_id": "cred-123",
            "chat_auth_credential_id": "cred-456"
        }
        
        result = validator.validate(config)
        
        assert result["api_version"] == "v1"
        assert result["workflow_type"] == "N8N_CHAT_AGENT_WORKFLOW"
        assert result["use_unified_chat_history"] is True
        assert result["chat_history_count"] == 25
        assert result["chat_url"] == "https://example.com/webhook"
        assert result["api_api_key_credential_id"] == "cred-123"
        assert result["chat_auth_credential_id"] == "cred-456"
    
    def test_validate_applies_defaults(self):
        """Test that validation applies default values."""
        validator = N8NConfigValidator()
        config = {
            "api_version": "v1",
            "workflow_type": "N8N_CHAT_AGENT_WORKFLOW",
            "use_unified_chat_history": False,
            "chat_url": "https://example.com/webhook",
            "api_api_key_credential_id": "cred-123",
            "chat_auth_credential_id": "cred-456"
        }
        
        result = validator.validate(config)
        
        assert result["chat_history_count"] == 30  # Default value
    
    def test_validate_invalid_config_raises_error(self):
        """Test that invalid config raises ApplicationConfigValidationError."""
        validator = N8NConfigValidator()
        config = {
            "api_version": "v2",  # Invalid
            "workflow_type": "N8N_CHAT_AGENT_WORKFLOW",
            "use_unified_chat_history": True,
            "chat_url": "https://example.com/webhook",
            "api_api_key_credential_id": "cred-123",
            "chat_auth_credential_id": "cred-456"
        }
        
        with pytest.raises(ApplicationConfigValidationError):
            validator.validate(config)
    
    def test_get_supported_type(self):
        """Test that get_supported_type returns N8N."""
        validator = N8NConfigValidator()
        assert validator.get_supported_type() == ApplicationTypeEnum.N8N


class TestApplicationConfigValidatorFactory:
    """Tests for ApplicationConfigValidatorFactory."""
    
    def test_get_validator_n8n(self):
        """Test getting N8N validator."""
        validator = ApplicationConfigValidatorFactory.get_validator(ApplicationTypeEnum.N8N)
        assert isinstance(validator, N8NConfigValidator)
    
    def test_get_validator_unsupported_type(self):
        """Test getting validator for unsupported type raises error."""
        with pytest.raises(UnsupportedApplicationTypeError):
            ApplicationConfigValidatorFactory.get_validator(ApplicationTypeEnum.MICROSOFT_FOUNDRY)
    
    def test_validate_config_n8n(self):
        """Test validate_config with N8N type."""
        config = {
            "api_version": "v1",
            "workflow_type": "N8N_CHAT_AGENT_WORKFLOW",
            "use_unified_chat_history": True,
            "chat_url": "https://example.com/webhook",
            "api_api_key_credential_id": "cred-123",
            "chat_auth_credential_id": "cred-456"
        }
        
        result = ApplicationConfigValidatorFactory.validate_config(
            ApplicationTypeEnum.N8N,
            config
        )
        
        assert result["api_version"] == "v1"
    
    def test_validate_config_empty_returns_empty(self):
        """Test that empty config returns empty dict."""
        result = ApplicationConfigValidatorFactory.validate_config(
            ApplicationTypeEnum.N8N,
            None
        )
        assert result == {}
        
        result = ApplicationConfigValidatorFactory.validate_config(
            ApplicationTypeEnum.N8N,
            {}
        )
        assert result == {}
    
    def test_validate_config_unsupported_type(self):
        """Test validate_config with unsupported type raises error."""
        config = {"key": "value"}
        
        with pytest.raises(UnsupportedApplicationTypeError):
            ApplicationConfigValidatorFactory.validate_config(
                ApplicationTypeEnum.REST_API,
                config
            )
    
    def test_is_supported_n8n(self):
        """Test is_supported returns True for N8N."""
        assert ApplicationConfigValidatorFactory.is_supported(ApplicationTypeEnum.N8N) is True
    
    def test_is_supported_unsupported_type(self):
        """Test is_supported returns False for unsupported types."""
        assert ApplicationConfigValidatorFactory.is_supported(ApplicationTypeEnum.MICROSOFT_FOUNDRY) is False
        assert ApplicationConfigValidatorFactory.is_supported(ApplicationTypeEnum.REST_API) is False
    
    def test_get_supported_types(self):
        """Test get_supported_types returns list with N8N."""
        supported = ApplicationConfigValidatorFactory.get_supported_types()
        assert ApplicationTypeEnum.N8N in supported
        assert len(supported) >= 1
