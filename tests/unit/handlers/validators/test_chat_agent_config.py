"""Tests for chat agent configuration validators."""

import pytest
from pydantic import ValidationError

from unifiedui.core.database.enums import ChatAgentTypeEnum
from unifiedui.exc.chat_agent_config import (
    ChatAgentConfigValidationError,
    UnsupportedChatAgentTypeError,
)
from unifiedui.handlers.validators.chat_agent_config import (
    ChatAgentConfigValidatorFactory,
    MicrosoftFoundryAgentTypeEnum,
    MicrosoftFoundryApiVersionEnum,
    MicrosoftFoundryChatAgentConfig,
    MicrosoftFoundryConfigValidator,
    N8NApiVersionEnum,
    N8NChatAgentConfig,
    N8NConfigValidator,
    N8NWorkflowTypeEnum,
    RestApiChatAgentConfig,
    RestApiConfigValidator,
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


class TestN8NChatAgentConfig:
    """Tests for N8NChatAgentConfig Pydantic model."""

    def test_valid_config(self):
        """Test a valid N8N configuration."""
        config = N8NChatAgentConfig(
            api_version=N8NApiVersionEnum.V1,
            workflow_type=N8NWorkflowTypeEnum.N8N_CHAT_AGENT_WORKFLOW,
            use_unified_chat_history=True,
            chat_history_count=30,
            chat_url="https://example.com/webhook",
            workflow_endpoint="https://n8n.example.com/workflow/abc123",
            api_api_key_credential_id="cred-123",
            chat_auth_credential_id="cred-456",
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
        config = N8NChatAgentConfig(
            api_version=N8NApiVersionEnum.V1,
            workflow_type=N8NWorkflowTypeEnum.N8N_CHAT_AGENT_WORKFLOW,
            use_unified_chat_history=True,
            chat_url="https://example.com/webhook",
            workflow_endpoint="https://n8n.example.com/workflow/abc123",
            api_api_key_credential_id="cred-123",
            chat_auth_credential_id="cred-456",
        )

        assert config.chat_history_count == 30

    def test_invalid_api_version(self):
        """Test that invalid API version raises ValidationError."""
        with pytest.raises(ValidationError):
            N8NChatAgentConfig(
                api_version="v2",
                workflow_type=N8NWorkflowTypeEnum.N8N_CHAT_AGENT_WORKFLOW,
                use_unified_chat_history=True,
                chat_url="https://example.com/webhook",
                workflow_endpoint="https://n8n.example.com/workflow/abc123",
                api_api_key_credential_id="cred-123",
                chat_auth_credential_id="cred-456",
            )

    def test_invalid_workflow_type(self):
        """Test that invalid workflow type raises ValidationError."""
        with pytest.raises(ValidationError):
            N8NChatAgentConfig(
                api_version=N8NApiVersionEnum.V1,
                workflow_type="INVALID_WORKFLOW",
                use_unified_chat_history=True,
                chat_url="https://example.com/webhook",
                workflow_endpoint="https://n8n.example.com/workflow/abc123",
                api_api_key_credential_id="cred-123",
                chat_auth_credential_id="cred-456",
            )

    def test_chat_url_must_be_http_or_https(self):
        """Test that chat_url must start with http:// or https://."""
        with pytest.raises(ValidationError) as exc_info:
            N8NChatAgentConfig(
                api_version=N8NApiVersionEnum.V1,
                workflow_type=N8NWorkflowTypeEnum.N8N_CHAT_AGENT_WORKFLOW,
                use_unified_chat_history=True,
                chat_url="ftp://example.com/webhook",
                workflow_endpoint="https://n8n.example.com/workflow/abc123",
                api_api_key_credential_id="cred-123",
                chat_auth_credential_id="cred-456",
            )
        assert "must start with http:// or https://" in str(exc_info.value)

    def test_http_url_is_valid(self):
        """Test that http:// URLs are valid."""
        config = N8NChatAgentConfig(
            api_version=N8NApiVersionEnum.V1,
            workflow_type=N8NWorkflowTypeEnum.N8N_CHAT_AGENT_WORKFLOW,
            use_unified_chat_history=True,
            chat_url="http://localhost:5678/webhook",
            workflow_endpoint="https://n8n.example.com/workflow/abc123",
            api_api_key_credential_id="cred-123",
            chat_auth_credential_id="cred-456",
        )
        assert config.chat_url == "http://localhost:5678/webhook"

    def test_missing_required_field(self):
        """Test that missing required field raises ValidationError."""
        with pytest.raises(ValidationError):
            N8NChatAgentConfig(
                api_version=N8NApiVersionEnum.V1,
                workflow_type=N8NWorkflowTypeEnum.N8N_CHAT_AGENT_WORKFLOW,
                use_unified_chat_history=True,
                chat_url="https://example.com/webhook",
                workflow_endpoint="https://n8n.example.com/workflow/abc123",
                # Missing api_api_key_credential_id
            )

    def test_empty_credential_id_not_allowed(self):
        """Test that empty credential IDs are not allowed."""
        with pytest.raises(ValidationError):
            N8NChatAgentConfig(
                api_version=N8NApiVersionEnum.V1,
                workflow_type=N8NWorkflowTypeEnum.N8N_CHAT_AGENT_WORKFLOW,
                use_unified_chat_history=True,
                chat_url="https://example.com/webhook",
                workflow_endpoint="https://n8n.example.com/workflow/abc123",
                api_api_key_credential_id="",
                chat_auth_credential_id="cred-456",
            )

    def test_chat_history_count_range(self):
        """Test chat_history_count min/max validation."""
        # Valid: 1
        config = N8NChatAgentConfig(
            api_version=N8NApiVersionEnum.V1,
            workflow_type=N8NWorkflowTypeEnum.N8N_CHAT_AGENT_WORKFLOW,
            use_unified_chat_history=True,
            chat_history_count=1,
            chat_url="https://example.com/webhook",
            workflow_endpoint="https://n8n.example.com/workflow/abc123",
            api_api_key_credential_id="cred-123",
            chat_auth_credential_id="cred-456",
        )
        assert config.chat_history_count == 1

        # Valid: 100
        config = N8NChatAgentConfig(
            api_version=N8NApiVersionEnum.V1,
            workflow_type=N8NWorkflowTypeEnum.N8N_CHAT_AGENT_WORKFLOW,
            use_unified_chat_history=True,
            chat_history_count=100,
            chat_url="https://example.com/webhook",
            workflow_endpoint="https://n8n.example.com/workflow/abc123",
            api_api_key_credential_id="cred-123",
            chat_auth_credential_id="cred-456",
        )
        assert config.chat_history_count == 100

        # Invalid: 0
        with pytest.raises(ValidationError):
            N8NChatAgentConfig(
                api_version=N8NApiVersionEnum.V1,
                workflow_type=N8NWorkflowTypeEnum.N8N_CHAT_AGENT_WORKFLOW,
                use_unified_chat_history=True,
                chat_history_count=0,
                chat_url="https://example.com/webhook",
                workflow_endpoint="https://n8n.example.com/workflow/abc123",
                api_api_key_credential_id="cred-123",
                chat_auth_credential_id="cred-456",
            )

        # Invalid: 101
        with pytest.raises(ValidationError):
            N8NChatAgentConfig(
                api_version=N8NApiVersionEnum.V1,
                workflow_type=N8NWorkflowTypeEnum.N8N_CHAT_AGENT_WORKFLOW,
                use_unified_chat_history=True,
                chat_history_count=101,
                chat_url="https://example.com/webhook",
                workflow_endpoint="https://n8n.example.com/workflow/abc123",
                api_api_key_credential_id="cred-123",
                chat_auth_credential_id="cred-456",
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
            "chat_auth_credential_id": "cred-456",
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
            "chat_auth_credential_id": "cred-456",
        }

        result = validator.validate(config)

        assert result["chat_history_count"] == 30  # Default value

    def test_validate_invalid_config_raises_error(self):
        """Test that invalid config raises ChatAgentConfigValidationError."""
        validator = N8NConfigValidator()
        config = {
            "api_version": "v2",  # Invalid
            "workflow_type": "N8N_CHAT_AGENT_WORKFLOW",
            "use_unified_chat_history": True,
            "chat_url": "https://example.com/webhook",
            "workflow_endpoint": "https://n8n.example.com/workflow/abc123",
            "api_api_key_credential_id": "cred-123",
            "chat_auth_credential_id": "cred-456",
        }

        with pytest.raises(ChatAgentConfigValidationError):
            validator.validate(config)

    def test_get_supported_type(self):
        """Test that get_supported_type returns N8N."""
        validator = N8NConfigValidator()
        assert validator.get_supported_type() == ChatAgentTypeEnum.N8N


class TestChatAgentConfigValidatorFactory:
    """Tests for ChatAgentConfigValidatorFactory."""

    def test_get_validator_n8n(self):
        """Test getting N8N validator."""
        validator = ChatAgentConfigValidatorFactory.get_validator(ChatAgentTypeEnum.N8N)
        assert isinstance(validator, N8NConfigValidator)

    def test_get_validator_unsupported_type(self):
        """Test getting validator for unsupported type raises error."""
        with pytest.raises(UnsupportedChatAgentTypeError):
            ChatAgentConfigValidatorFactory.get_validator(ChatAgentTypeEnum.REACT_AGENT)

    def test_validate_config_n8n(self):
        """Test validate_config with N8N type."""
        config = {
            "api_version": "v1",
            "workflow_type": "N8N_CHAT_AGENT_WORKFLOW",
            "use_unified_chat_history": True,
            "chat_url": "https://example.com/webhook",
            "workflow_endpoint": "https://n8n.example.com/workflow/abc123",
            "api_api_key_credential_id": "cred-123",
            "chat_auth_credential_id": "cred-456",
        }

        result = ChatAgentConfigValidatorFactory.validate_config(ChatAgentTypeEnum.N8N, config)

        assert result["api_version"] == "v1"

    def test_validate_config_empty_returns_empty(self):
        """Test that empty config returns empty dict."""
        result = ChatAgentConfigValidatorFactory.validate_config(ChatAgentTypeEnum.N8N, None)
        assert result == {}

        result = ChatAgentConfigValidatorFactory.validate_config(ChatAgentTypeEnum.N8N, {})
        assert result == {}

    def test_validate_config_unsupported_type(self):
        """Test validate_config with unsupported type raises error."""
        config = {"key": "value"}

        with pytest.raises(UnsupportedChatAgentTypeError):
            ChatAgentConfigValidatorFactory.validate_config(ChatAgentTypeEnum.REACT_AGENT, config)

    def test_is_supported_n8n(self):
        """Test is_supported returns True for N8N."""
        assert ChatAgentConfigValidatorFactory.is_supported(ChatAgentTypeEnum.N8N) is True

    def test_is_supported_unsupported_type(self):
        """Test is_supported returns False for unsupported types."""
        assert ChatAgentConfigValidatorFactory.is_supported(ChatAgentTypeEnum.REACT_AGENT) is False

    def test_get_supported_types(self):
        """Test get_supported_types returns list with N8N and MICROSOFT_FOUNDRY."""
        supported = ChatAgentConfigValidatorFactory.get_supported_types()
        assert ChatAgentTypeEnum.N8N in supported
        assert ChatAgentTypeEnum.MICROSOFT_FOUNDRY in supported
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


class TestMicrosoftFoundryChatAgentConfig:
    """Tests for MicrosoftFoundryChatAgentConfig Pydantic model."""

    def test_valid_config_agent(self):
        """Test a valid Microsoft Foundry AGENT configuration."""
        config = MicrosoftFoundryChatAgentConfig(
            agent_type=MicrosoftFoundryAgentTypeEnum.AGENT,
            api_version=MicrosoftFoundryApiVersionEnum.V2025_11_15_PREVIEW,
            project_endpoint="https://engo-foundry.services.ai.azure.com/api/projects/proj-default-2",
            agent_name="my-agent",
        )

        assert config.agent_type == MicrosoftFoundryAgentTypeEnum.AGENT
        assert config.api_version == MicrosoftFoundryApiVersionEnum.V2025_11_15_PREVIEW
        assert config.project_endpoint == "https://engo-foundry.services.ai.azure.com/api/projects/proj-default-2"
        assert config.agent_name == "my-agent"

    def test_valid_config_multi_agent(self):
        """Test a valid Microsoft Foundry MULTI_AGENT configuration."""
        config = MicrosoftFoundryChatAgentConfig(
            agent_type=MicrosoftFoundryAgentTypeEnum.MULTI_AGENT,
            api_version=MicrosoftFoundryApiVersionEnum.V2025_11_15_PREVIEW,
            project_endpoint="https://engo-foundry.services.ai.azure.com/api/projects/proj-default-2",
            agent_name="my-workflow",
        )

        assert config.agent_type == MicrosoftFoundryAgentTypeEnum.MULTI_AGENT

    def test_invalid_agent_type(self):
        """Test that invalid agent type raises ValidationError."""
        with pytest.raises(ValidationError):
            MicrosoftFoundryChatAgentConfig(
                agent_type="INVALID_TYPE",
                api_version=MicrosoftFoundryApiVersionEnum.V2025_11_15_PREVIEW,
                project_endpoint="https://engo-foundry.services.ai.azure.com/api/projects/proj-default-2",
                agent_name="my-agent",
            )

    def test_invalid_api_version(self):
        """Test that invalid API version raises ValidationError."""
        with pytest.raises(ValidationError):
            MicrosoftFoundryChatAgentConfig(
                agent_type=MicrosoftFoundryAgentTypeEnum.AGENT,
                api_version="2024-01-01",
                project_endpoint="https://engo-foundry.services.ai.azure.com/api/projects/proj-default-2",
                agent_name="my-agent",
            )

    def test_project_endpoint_must_be_https(self):
        """Test that project_endpoint must start with https://."""
        with pytest.raises(ValidationError) as exc_info:
            MicrosoftFoundryChatAgentConfig(
                agent_type=MicrosoftFoundryAgentTypeEnum.AGENT,
                api_version=MicrosoftFoundryApiVersionEnum.V2025_11_15_PREVIEW,
                project_endpoint="http://engo-foundry.services.ai.azure.com/api/projects/proj-default-2",
                agent_name="my-agent",
            )
        assert "must start with https://" in str(exc_info.value)

    def test_project_endpoint_must_contain_foundry_pattern(self):
        """Test that project_endpoint must contain Foundry pattern."""
        with pytest.raises(ValidationError) as exc_info:
            MicrosoftFoundryChatAgentConfig(
                agent_type=MicrosoftFoundryAgentTypeEnum.AGENT,
                api_version=MicrosoftFoundryApiVersionEnum.V2025_11_15_PREVIEW,
                project_endpoint="https://example.com/api/projects/test",
                agent_name="my-agent",
            )
        assert "services.ai.azure.com/api/projects" in str(exc_info.value)

    def test_missing_required_field(self):
        """Test that missing required field raises ValidationError."""
        with pytest.raises(ValidationError):
            MicrosoftFoundryChatAgentConfig(
                agent_type=MicrosoftFoundryAgentTypeEnum.AGENT,
                api_version=MicrosoftFoundryApiVersionEnum.V2025_11_15_PREVIEW,
                project_endpoint="https://engo-foundry.services.ai.azure.com/api/projects/proj-default-2",
                # Missing agent_name
            )

    def test_empty_agent_name_not_allowed(self):
        """Test that empty agent_name is not allowed."""
        with pytest.raises(ValidationError):
            MicrosoftFoundryChatAgentConfig(
                agent_type=MicrosoftFoundryAgentTypeEnum.AGENT,
                api_version=MicrosoftFoundryApiVersionEnum.V2025_11_15_PREVIEW,
                project_endpoint="https://engo-foundry.services.ai.azure.com/api/projects/proj-default-2",
                agent_name="",
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
            "agent_name": "my-agent",
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
            "agent_name": "my-workflow",
        }

        result = validator.validate(config)

        assert result["agent_type"] == "MULTI_AGENT"

    def test_validate_invalid_config_raises_error(self):
        """Test that invalid config raises ChatAgentConfigValidationError."""
        validator = MicrosoftFoundryConfigValidator()
        config = {
            "agent_type": "INVALID",
            "api_version": "2025-11-15-preview",
            "project_endpoint": "https://engo-foundry.services.ai.azure.com/api/projects/proj-default-2",
            "agent_name": "my-agent",
        }

        with pytest.raises(ChatAgentConfigValidationError):
            validator.validate(config)

    def test_get_supported_type(self):
        """Test that get_supported_type returns MICROSOFT_FOUNDRY."""
        validator = MicrosoftFoundryConfigValidator()
        assert validator.get_supported_type() == ChatAgentTypeEnum.MICROSOFT_FOUNDRY


class TestChatAgentConfigValidatorFactoryMicrosoftFoundry:
    """Tests for ChatAgentConfigValidatorFactory with Microsoft Foundry."""

    def test_get_validator_microsoft_foundry(self):
        """Test getting Microsoft Foundry validator."""
        validator = ChatAgentConfigValidatorFactory.get_validator(ChatAgentTypeEnum.MICROSOFT_FOUNDRY)
        assert isinstance(validator, MicrosoftFoundryConfigValidator)

    def test_validate_config_microsoft_foundry(self):
        """Test validate_config with Microsoft Foundry type."""
        config = {
            "agent_type": "AGENT",
            "api_version": "2025-11-15-preview",
            "project_endpoint": "https://engo-foundry.services.ai.azure.com/api/projects/proj-default-2",
            "agent_name": "my-agent",
        }

        result = ChatAgentConfigValidatorFactory.validate_config(ChatAgentTypeEnum.MICROSOFT_FOUNDRY, config)

        assert result["agent_type"] == "AGENT"
        assert result["api_version"] == "2025-11-15-preview"

    def test_is_supported_microsoft_foundry(self):
        """Test is_supported returns True for MICROSOFT_FOUNDRY."""
        assert ChatAgentConfigValidatorFactory.is_supported(ChatAgentTypeEnum.MICROSOFT_FOUNDRY) is True


# ========== REST API Tests ==========


class TestRestApiChatAgentConfig:
    """Tests for RestApiChatAgentConfig Pydantic model."""

    def test_valid_config_anonymous(self):
        """Test a valid anonymous REST API configuration."""
        config = RestApiChatAgentConfig(
            auth_type="ANONYMOUS",
            invoke_endpoint="https://api.example.com/agent/invoke",
        )

        assert config.auth_type == "ANONYMOUS"
        assert config.invoke_endpoint == "https://api.example.com/agent/invoke"
        assert config.credential_id is None
        assert config.use_unified_chat_history is True
        assert config.chat_history_count == 30
        assert config.create_conversation_endpoint is None

    def test_valid_config_api_key_with_credential(self):
        """Test a valid API key REST API configuration."""
        config = RestApiChatAgentConfig(
            auth_type="API_KEY",
            invoke_endpoint="https://api.example.com/agent/invoke",
            credential_id="cred-123",
        )

        assert config.auth_type == "API_KEY"
        assert config.credential_id == "cred-123"

    def test_valid_config_with_conversation_endpoint(self):
        """Test config with conversation creation endpoint."""
        config = RestApiChatAgentConfig(
            auth_type="ANONYMOUS",
            invoke_endpoint="https://api.example.com/agent/invoke",
            create_conversation_endpoint="https://api.example.com/conversations",
        )

        assert config.create_conversation_endpoint == "https://api.example.com/conversations"

    def test_valid_config_chat_history_disabled(self):
        """Test config with chat history disabled."""
        config = RestApiChatAgentConfig(
            auth_type="ANONYMOUS",
            invoke_endpoint="https://api.example.com/agent/invoke",
            use_unified_chat_history=False,
        )

        assert config.use_unified_chat_history is False

    def test_credential_required_for_basic_auth(self):
        """Test that credential_id is required for BASIC_AUTH."""
        with pytest.raises(ValidationError) as exc_info:
            RestApiChatAgentConfig(
                auth_type="BASIC_AUTH",
                invoke_endpoint="https://api.example.com/agent/invoke",
            )
        assert "credential_id is required" in str(exc_info.value)

    def test_credential_required_for_api_key(self):
        """Test that credential_id is required for API_KEY."""
        with pytest.raises(ValidationError) as exc_info:
            RestApiChatAgentConfig(
                auth_type="API_KEY",
                invoke_endpoint="https://api.example.com/agent/invoke",
            )
        assert "credential_id is required" in str(exc_info.value)

    def test_credential_required_for_entra_id_app_registration(self):
        """Test that credential_id is required for ENTRA_ID_APP_REGISTRATION."""
        with pytest.raises(ValidationError) as exc_info:
            RestApiChatAgentConfig(
                auth_type="ENTRA_ID_APP_REGISTRATION",
                invoke_endpoint="https://api.example.com/agent/invoke",
            )
        assert "credential_id is required" in str(exc_info.value)

    def test_credential_not_required_for_anonymous(self):
        """Test that credential_id is optional for ANONYMOUS."""
        config = RestApiChatAgentConfig(
            auth_type="ANONYMOUS",
            invoke_endpoint="https://api.example.com/agent/invoke",
        )
        assert config.credential_id is None

    def test_credential_not_required_for_entra_id_user_token(self):
        """Test that credential_id is optional for ENTRA_ID_USER_TOKEN."""
        config = RestApiChatAgentConfig(
            auth_type="ENTRA_ID_USER_TOKEN",
            invoke_endpoint="https://api.example.com/agent/invoke",
        )
        assert config.credential_id is None

    def test_invoke_endpoint_must_be_url(self):
        """Test that invoke_endpoint must start with http:// or https://."""
        with pytest.raises(ValidationError) as exc_info:
            RestApiChatAgentConfig(
                auth_type="ANONYMOUS",
                invoke_endpoint="ftp://example.com/invoke",
            )
        assert "invoke_endpoint must start with http:// or https://" in str(exc_info.value)

    def test_create_conversation_endpoint_must_be_url(self):
        """Test that create_conversation_endpoint must be a valid URL."""
        with pytest.raises(ValidationError) as exc_info:
            RestApiChatAgentConfig(
                auth_type="ANONYMOUS",
                invoke_endpoint="https://api.example.com/invoke",
                create_conversation_endpoint="not-a-url",
            )
        assert "create_conversation_endpoint must start with http:// or https://" in str(exc_info.value)

    def test_invalid_auth_type(self):
        """Test that invalid auth_type raises ValidationError."""
        with pytest.raises(ValidationError):
            RestApiChatAgentConfig(
                auth_type="INVALID",
                invoke_endpoint="https://api.example.com/invoke",
            )

    def test_chat_history_count_range(self):
        """Test chat_history_count must be between 1 and 100."""
        with pytest.raises(ValidationError):
            RestApiChatAgentConfig(
                auth_type="ANONYMOUS",
                invoke_endpoint="https://api.example.com/invoke",
                chat_history_count=0,
            )

        with pytest.raises(ValidationError):
            RestApiChatAgentConfig(
                auth_type="ANONYMOUS",
                invoke_endpoint="https://api.example.com/invoke",
                chat_history_count=101,
            )

    def test_model_dump(self):
        """Test serialization via model_dump."""
        config = RestApiChatAgentConfig(
            auth_type="API_KEY",
            invoke_endpoint="https://api.example.com/invoke",
            credential_id="cred-1",
            use_unified_chat_history=False,
            chat_history_count=10,
            create_conversation_endpoint="https://api.example.com/conversations",
        )
        data = config.model_dump()

        assert data["auth_type"] == "API_KEY"
        assert data["invoke_endpoint"] == "https://api.example.com/invoke"
        assert data["credential_id"] == "cred-1"
        assert data["use_unified_chat_history"] is False
        assert data["chat_history_count"] == 10
        assert data["create_conversation_endpoint"] == "https://api.example.com/conversations"


class TestRestApiConfigValidator:
    """Tests for RestApiConfigValidator."""

    def test_validate_valid_config(self):
        """Test validation of a valid config."""
        validator = RestApiConfigValidator()
        config = {
            "auth_type": "ANONYMOUS",
            "invoke_endpoint": "https://api.example.com/agent/invoke",
        }

        result = validator.validate(config)

        assert result["auth_type"] == "ANONYMOUS"
        assert result["invoke_endpoint"] == "https://api.example.com/agent/invoke"
        assert result["use_unified_chat_history"] is True
        assert result["chat_history_count"] == 30

    def test_validate_invalid_config_raises_error(self):
        """Test that invalid config raises ChatAgentConfigValidationError."""
        validator = RestApiConfigValidator()
        config = {"auth_type": "INVALID"}

        with pytest.raises(ChatAgentConfigValidationError):
            validator.validate(config)

    def test_get_supported_type(self):
        """Test that get_supported_type returns REST_API."""
        validator = RestApiConfigValidator()
        assert validator.get_supported_type() == ChatAgentTypeEnum.REST_API


class TestChatAgentConfigValidatorFactoryRestApi:
    """Tests for ChatAgentConfigValidatorFactory with REST API."""

    def test_get_validator_rest_api(self):
        """Test getting REST API validator."""
        validator = ChatAgentConfigValidatorFactory.get_validator(ChatAgentTypeEnum.REST_API)
        assert isinstance(validator, RestApiConfigValidator)

    def test_validate_config_rest_api(self):
        """Test validate_config with REST API type."""
        config = {
            "auth_type": "API_KEY",
            "invoke_endpoint": "https://api.example.com/invoke",
            "credential_id": "cred-123",
        }

        result = ChatAgentConfigValidatorFactory.validate_config(ChatAgentTypeEnum.REST_API, config)

        assert result["auth_type"] == "API_KEY"
        assert result["invoke_endpoint"] == "https://api.example.com/invoke"

    def test_is_supported_rest_api(self):
        """Test is_supported returns True for REST_API."""
        assert ChatAgentConfigValidatorFactory.is_supported(ChatAgentTypeEnum.REST_API) is True
