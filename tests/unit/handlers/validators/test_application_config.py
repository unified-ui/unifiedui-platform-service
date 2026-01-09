"""Tests for application configuration validators."""
import pytest
from pydantic import ValidationError

from unifiedui.handlers.validators.application_config import (
    ApplicationConfigValidatorFactory,
    N8NConfigValidator,
    N8NApplicationConfig,
    N8NApiVersionEnum,
    N8NWorkflowTypeEnum,
    MicrosoftFoundryConfigValidator,
    MicrosoftFoundryApplicationConfig,
    MicrosoftFoundryAgentTypeEnum,
    MicrosoftFoundryApiVersionEnum,
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
            workflow_endpoint="https://n8n.example.com/workflow/abc123",
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
            workflow_endpoint="https://n8n.example.com/workflow/abc123",
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
            workflow_endpoint="https://n8n.example.com/workflow/abc123",
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
            workflow_endpoint="https://n8n.example.com/workflow/abc123",
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
            workflow_endpoint="https://n8n.example.com/workflow/abc123",
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
            workflow_endpoint="https://n8n.example.com/workflow/abc123",
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
            workflow_endpoint="https://n8n.example.com/workflow/abc123",
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
            workflow_endpoint="https://n8n.example.com/workflow/abc123",
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
            workflow_endpoint="https://n8n.example.com/workflow/abc123",
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
            workflow_endpoint="https://n8n.example.com/workflow/abc123",
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
            workflow_endpoint="https://n8n.example.com/workflow/abc123",
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
            workflow_endpoint="https://n8n.example.com/workflow/abc123",
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
            "workflow_endpoint": "https://n8n.example.com/workflow/abc123",
            "api_api_key_credential_id": "cred-123",
            "chat_auth_credential_id": "cred-456"
        }
        
        result = validator.validate(config)
        
        assert result["api_version"] == "v1"
        assert result["workflow_endpoint"] == "https://n8n.example.com/workflow/abc123"
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
            "workflow_endpoint": "https://n8n.example.com/workflow/abc123",
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
            "workflow_endpoint": "https://n8n.example.com/workflow/abc123",
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
            ApplicationConfigValidatorFactory.get_validator(ApplicationTypeEnum.REST_API)
    
    def test_validate_config_n8n(self):
        """Test validate_config with N8N type."""
        config = {
            "api_version": "v1",
            "workflow_type": "N8N_CHAT_AGENT_WORKFLOW",
            "use_unified_chat_history": True,
            "chat_url": "https://example.com/webhook",
            "workflow_endpoint": "https://n8n.example.com/workflow/abc123",
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
        assert ApplicationConfigValidatorFactory.is_supported(ApplicationTypeEnum.REST_API) is False
    
    def test_get_supported_types(self):
        """Test get_supported_types returns list with N8N and MICROSOFT_FOUNDRY."""
        supported = ApplicationConfigValidatorFactory.get_supported_types()
        assert ApplicationTypeEnum.N8N in supported
        assert ApplicationTypeEnum.MICROSOFT_FOUNDRY in supported
        assert len(supported) >= 2


# ========== Microsoft Foundry Tests ==========

class TestMicrosoftFoundryAgentTypeEnum:
    """Tests for MicrosoftFoundryAgentTypeEnum."""
    
    def test_agent_value(self):
        """Test that AGENT is a valid agent type."""
        assert MicrosoftFoundryAgentTypeEnum.AGENT.value == "AGENT"
    
    def test_multi_agent_value(self):
        """Test that MULTI_AGENT is a valid agent type."""
        assert MicrosoftFoundryAgentTypeEnum.MULTI_AGENT.value == "MULTI_AGENT"
    
    def test_all_returns_list(self):
        """Test that all() returns a list of values."""
        types = MicrosoftFoundryAgentTypeEnum.all()
        assert isinstance(types, list)
        assert "AGENT" in types
        assert "MULTI_AGENT" in types


class TestMicrosoftFoundryApiVersionEnum:
    """Tests for MicrosoftFoundryApiVersionEnum."""
    
    def test_v2025_11_15_preview_value(self):
        """Test that 2025-11-15-preview is a valid API version."""
        assert MicrosoftFoundryApiVersionEnum.V2025_11_15_PREVIEW.value == "2025-11-15-preview"
    
    def test_all_returns_list(self):
        """Test that all() returns a list of values."""
        versions = MicrosoftFoundryApiVersionEnum.all()
        assert isinstance(versions, list)
        assert "2025-11-15-preview" in versions


class TestMicrosoftFoundryApplicationConfig:
    """Tests for MicrosoftFoundryApplicationConfig Pydantic model."""
    
    def test_valid_config_agent(self):
        """Test a valid Microsoft Foundry AGENT configuration."""
        config = MicrosoftFoundryApplicationConfig(
            agent_type=MicrosoftFoundryAgentTypeEnum.AGENT,
            api_version=MicrosoftFoundryApiVersionEnum.V2025_11_15_PREVIEW,
            project_endpoint="https://engo-foundry.services.ai.azure.com/api/projects/proj-default-2",
            agent_name="my-agent"
        )
        
        assert config.agent_type == MicrosoftFoundryAgentTypeEnum.AGENT
        assert config.api_version == MicrosoftFoundryApiVersionEnum.V2025_11_15_PREVIEW
        assert config.project_endpoint == "https://engo-foundry.services.ai.azure.com/api/projects/proj-default-2"
        assert config.agent_name == "my-agent"
    
    def test_valid_config_multi_agent(self):
        """Test a valid Microsoft Foundry MULTI_AGENT configuration."""
        config = MicrosoftFoundryApplicationConfig(
            agent_type=MicrosoftFoundryAgentTypeEnum.MULTI_AGENT,
            api_version=MicrosoftFoundryApiVersionEnum.V2025_11_15_PREVIEW,
            project_endpoint="https://engo-foundry.services.ai.azure.com/api/projects/proj-default-2",
            agent_name="my-workflow"
        )
        
        assert config.agent_type == MicrosoftFoundryAgentTypeEnum.MULTI_AGENT
    
    def test_invalid_agent_type(self):
        """Test that invalid agent type raises ValidationError."""
        with pytest.raises(ValidationError):
            MicrosoftFoundryApplicationConfig(
                agent_type="INVALID_TYPE",
                api_version=MicrosoftFoundryApiVersionEnum.V2025_11_15_PREVIEW,
                project_endpoint="https://engo-foundry.services.ai.azure.com/api/projects/proj-default-2",
                agent_name="my-agent"
            )
    
    def test_invalid_api_version(self):
        """Test that invalid API version raises ValidationError."""
        with pytest.raises(ValidationError):
            MicrosoftFoundryApplicationConfig(
                agent_type=MicrosoftFoundryAgentTypeEnum.AGENT,
                api_version="2024-01-01",
                project_endpoint="https://engo-foundry.services.ai.azure.com/api/projects/proj-default-2",
                agent_name="my-agent"
            )
    
    def test_project_endpoint_must_be_https(self):
        """Test that project_endpoint must start with https://."""
        with pytest.raises(ValidationError) as exc_info:
            MicrosoftFoundryApplicationConfig(
                agent_type=MicrosoftFoundryAgentTypeEnum.AGENT,
                api_version=MicrosoftFoundryApiVersionEnum.V2025_11_15_PREVIEW,
                project_endpoint="http://engo-foundry.services.ai.azure.com/api/projects/proj-default-2",
                agent_name="my-agent"
            )
        assert "must start with https://" in str(exc_info.value)
    
    def test_project_endpoint_must_contain_foundry_pattern(self):
        """Test that project_endpoint must contain Foundry pattern."""
        with pytest.raises(ValidationError) as exc_info:
            MicrosoftFoundryApplicationConfig(
                agent_type=MicrosoftFoundryAgentTypeEnum.AGENT,
                api_version=MicrosoftFoundryApiVersionEnum.V2025_11_15_PREVIEW,
                project_endpoint="https://example.com/api/projects/test",
                agent_name="my-agent"
            )
        assert "services.ai.azure.com/api/projects" in str(exc_info.value)
    
    def test_missing_required_field(self):
        """Test that missing required field raises ValidationError."""
        with pytest.raises(ValidationError):
            MicrosoftFoundryApplicationConfig(
                agent_type=MicrosoftFoundryAgentTypeEnum.AGENT,
                api_version=MicrosoftFoundryApiVersionEnum.V2025_11_15_PREVIEW,
                project_endpoint="https://engo-foundry.services.ai.azure.com/api/projects/proj-default-2"
                # Missing agent_name
            )
    
    def test_empty_agent_name_not_allowed(self):
        """Test that empty agent_name is not allowed."""
        with pytest.raises(ValidationError):
            MicrosoftFoundryApplicationConfig(
                agent_type=MicrosoftFoundryAgentTypeEnum.AGENT,
                api_version=MicrosoftFoundryApiVersionEnum.V2025_11_15_PREVIEW,
                project_endpoint="https://engo-foundry.services.ai.azure.com/api/projects/proj-default-2",
                agent_name=""
            )


class TestMicrosoftFoundryConfigValidator:
    """Tests for MicrosoftFoundryConfigValidator."""
    
    def test_validate_valid_config(self):
        """Test validation of a valid config."""
        validator = MicrosoftFoundryConfigValidator()
        config = {
            "agent_type": "AGENT",
            "api_version": "2025-11-15-preview",
            "project_endpoint": "https://engo-foundry.services.ai.azure.com/api/projects/proj-default-2",
            "agent_name": "my-agent"
        }
        
        result = validator.validate(config)
        
        assert result["agent_type"] == "AGENT"
        assert result["api_version"] == "2025-11-15-preview"
        assert result["project_endpoint"] == "https://engo-foundry.services.ai.azure.com/api/projects/proj-default-2"
        assert result["agent_name"] == "my-agent"
    
    def test_validate_multi_agent_config(self):
        """Test validation of a MULTI_AGENT config."""
        validator = MicrosoftFoundryConfigValidator()
        config = {
            "agent_type": "MULTI_AGENT",
            "api_version": "2025-11-15-preview",
            "project_endpoint": "https://engo-foundry.services.ai.azure.com/api/projects/proj-default-2",
            "agent_name": "my-workflow"
        }
        
        result = validator.validate(config)
        
        assert result["agent_type"] == "MULTI_AGENT"
    
    def test_validate_invalid_config_raises_error(self):
        """Test that invalid config raises ApplicationConfigValidationError."""
        validator = MicrosoftFoundryConfigValidator()
        config = {
            "agent_type": "INVALID",
            "api_version": "2025-11-15-preview",
            "project_endpoint": "https://engo-foundry.services.ai.azure.com/api/projects/proj-default-2",
            "agent_name": "my-agent"
        }
        
        with pytest.raises(ApplicationConfigValidationError):
            validator.validate(config)
    
    def test_get_supported_type(self):
        """Test that get_supported_type returns MICROSOFT_FOUNDRY."""
        validator = MicrosoftFoundryConfigValidator()
        assert validator.get_supported_type() == ApplicationTypeEnum.MICROSOFT_FOUNDRY


class TestApplicationConfigValidatorFactoryMicrosoftFoundry:
    """Tests for ApplicationConfigValidatorFactory with Microsoft Foundry."""
    
    def test_get_validator_microsoft_foundry(self):
        """Test getting Microsoft Foundry validator."""
        validator = ApplicationConfigValidatorFactory.get_validator(ApplicationTypeEnum.MICROSOFT_FOUNDRY)
        assert isinstance(validator, MicrosoftFoundryConfigValidator)
    
    def test_validate_config_microsoft_foundry(self):
        """Test validate_config with Microsoft Foundry type."""
        config = {
            "agent_type": "AGENT",
            "api_version": "2025-11-15-preview",
            "project_endpoint": "https://engo-foundry.services.ai.azure.com/api/projects/proj-default-2",
            "agent_name": "my-agent"
        }
        
        result = ApplicationConfigValidatorFactory.validate_config(
            ApplicationTypeEnum.MICROSOFT_FOUNDRY,
            config
        )
        
        assert result["agent_type"] == "AGENT"
        assert result["api_version"] == "2025-11-15-preview"
    
    def test_is_supported_microsoft_foundry(self):
        """Test is_supported returns True for MICROSOFT_FOUNDRY."""
        assert ApplicationConfigValidatorFactory.is_supported(ApplicationTypeEnum.MICROSOFT_FOUNDRY) is True
