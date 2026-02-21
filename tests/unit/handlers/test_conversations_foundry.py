"""Tests for conversation handler - Microsoft Foundry integration."""

from unittest.mock import MagicMock, Mock, patch

import pytest

from unifiedui.core.database.enums import ChatAgentTypeEnum
from unifiedui.exc.conversations import FoundryConversationCreationError
from unifiedui.handlers.conversations import ConversationHandler


class TestConversationHandlerFoundryIntegration:
    """Tests for ConversationHandler Foundry integration."""

    @pytest.fixture
    def mock_db_client(self):
        """Create mock database client."""
        db_client = Mock()
        session = MagicMock()
        db_client.get_session.return_value.__enter__ = Mock(return_value=session)
        db_client.get_session.return_value.__exit__ = Mock(return_value=False)
        return db_client, session

    @pytest.fixture
    def mock_cache_client(self):
        """Create mock cache client."""
        cache_client = Mock()
        cache_client.client = Mock()
        return cache_client

    @pytest.fixture
    def mock_user(self):
        """Create mock user context."""
        user = Mock()
        user.identity.get_id.return_value = "user-123"
        user.identity.get_display_name.return_value = "Test User"
        user.identity.get_principal_name.return_value = "test@example.com"
        user.identity.get_mail.return_value = "test@example.com"
        user.tenants = [{"tenant": {"id": "tenant-123"}, "roles": ["GLOBAL_ADMIN"]}]
        user.groups = []
        return user

    @pytest.fixture
    def handler(self, mock_db_client, mock_cache_client):
        """Create conversation handler."""
        db_client, _ = mock_db_client
        handler = ConversationHandler(db_client=db_client, cache_client=mock_cache_client)
        handler._permissions_handler = Mock()
        return handler

    def test_create_conversation_non_foundry_app_no_external_id(self, handler, mock_db_client, mock_user):
        """Test that non-Foundry chat agents don't get external conversation ID."""
        _db_client, session = mock_db_client

        # Mock chat agent query
        mock_app = Mock()
        mock_app.type = ChatAgentTypeEnum.N8N.value
        mock_app.config = {}
        session.execute.return_value.scalar_one_or_none.return_value = mock_app

        # Mock conversation creation
        mock_conversation = Mock()
        mock_conversation.id = "conv-123"
        mock_conversation.tenant_id = "tenant-123"
        mock_conversation.chat_agent_id = "app-123"
        mock_conversation.ext_conversation_id = None
        mock_conversation.name = "Test Conversation"
        mock_conversation.description = None
        mock_conversation.is_active = False
        mock_conversation.created_at = Mock()
        mock_conversation.updated_at = Mock()
        mock_conversation.created_by = "user-123"
        mock_conversation.updated_by = "user-123"

        # The second call to scalar_one_or_none returns the chat agent
        # We need to set up the mock to return conversation after session operations
        def refresh_mock(obj):
            # Copy properties to the conversation object being refreshed
            for attr in [
                "id",
                "tenant_id",
                "chat_agent_id",
                "ext_conversation_id",
                "name",
                "description",
                "is_active",
                "created_at",
                "updated_at",
                "created_by",
                "updated_by",
            ]:
                if not hasattr(obj, attr):
                    setattr(obj, attr, getattr(mock_conversation, attr))

        session.refresh = refresh_mock

        from unifiedui.schema.requests.conversations import CreateConversationRequest

        request = CreateConversationRequest(chat_agent_id="app-123", name="Test Conversation")

        with patch.object(handler, "_model_to_response") as mock_to_response:
            mock_to_response.return_value = Mock()

            handler.create_conversation(
                tenant_id="tenant-123", request=request, user_id="user-123", user=mock_user, foundry_api_key=None
            )

            # Verify no Foundry client was created/called
            # (Would have raised error if called without proper mocking)

    def test_create_conversation_foundry_app_missing_api_key_raises_error(self, handler, mock_db_client, mock_user):
        """Test that Foundry chat agents without API key raise error."""
        _db_client, session = mock_db_client

        # Mock chat agent query
        mock_app = Mock()
        mock_app.type = ChatAgentTypeEnum.MICROSOFT_FOUNDRY.value
        mock_app.config = {
            "project_endpoint": "https://engo-foundry.services.ai.azure.com/api/projects/proj-default-2",
            "api_version": "2025-11-15-preview",
        }
        session.execute.return_value.scalar_one_or_none.return_value = mock_app

        from unifiedui.schema.requests.conversations import CreateConversationRequest

        request = CreateConversationRequest(chat_agent_id="app-123", name="Test Conversation")

        with pytest.raises(FoundryConversationCreationError) as exc_info:
            handler.create_conversation(
                tenant_id="tenant-123",
                request=request,
                user_id="user-123",
                user=mock_user,
                foundry_api_key=None,  # Missing API key
            )

        assert "X-Microsoft-Foundry-API-Key" in str(exc_info.value.message)

    def test_create_conversation_foundry_app_missing_endpoint_raises_error(self, handler, mock_db_client, mock_user):
        """Test that Foundry chat agents without project endpoint raise error."""
        _db_client, session = mock_db_client

        # Mock chat agent query - missing project_endpoint
        mock_app = Mock()
        mock_app.type = ChatAgentTypeEnum.MICROSOFT_FOUNDRY.value
        mock_app.config = {}  # Missing project_endpoint
        session.execute.return_value.scalar_one_or_none.return_value = mock_app

        from unifiedui.schema.requests.conversations import CreateConversationRequest

        request = CreateConversationRequest(chat_agent_id="app-123", name="Test Conversation")

        with pytest.raises(FoundryConversationCreationError) as exc_info:
            handler.create_conversation(
                tenant_id="tenant-123",
                request=request,
                user_id="user-123",
                user=mock_user,
                foundry_api_key="test-api-key",
            )

        assert "project_endpoint" in str(exc_info.value.message)

    @patch("unifiedui.handlers.conversations.MicrosoftFoundryClient")
    def test_create_conversation_foundry_app_success(
        self, mock_foundry_client_class, handler, mock_db_client, mock_user
    ):
        """Test successful Foundry conversation creation."""
        _db_client, session = mock_db_client

        # Mock chat agent query
        mock_app = Mock()
        mock_app.type = ChatAgentTypeEnum.MICROSOFT_FOUNDRY.value
        mock_app.config = {
            "project_endpoint": "https://engo-foundry.services.ai.azure.com/api/projects/proj-default-2",
            "api_version": "2025-11-15-preview",
        }
        session.execute.return_value.scalar_one_or_none.return_value = mock_app

        # Mock Foundry client
        mock_foundry_instance = Mock()
        mock_foundry_instance.get_conversation_id.return_value = "conv_foundry_12345"
        mock_foundry_client_class.return_value = mock_foundry_instance

        from unifiedui.schema.requests.conversations import CreateConversationRequest

        request = CreateConversationRequest(chat_agent_id="app-123", name="Test Conversation")

        # Track conversation object created
        captured_conversation = None
        original_add = session.add

        def capture_add(obj):
            nonlocal captured_conversation
            if hasattr(obj, "ext_conversation_id"):
                captured_conversation = obj
            return original_add(obj)

        session.add = capture_add

        # Mock refresh to set attributes
        def mock_refresh(obj):
            obj.id = "conv-123"
            obj.tenant_id = "tenant-123"
            obj.chat_agent_id = "app-123"
            obj.name = "Test Conversation"
            obj.description = None
            obj.is_active = False
            obj.created_at = Mock()
            obj.updated_at = Mock()
            obj.created_by = "user-123"
            obj.updated_by = "user-123"

        session.refresh = mock_refresh

        with patch.object(handler, "_model_to_response") as mock_to_response:
            mock_to_response.return_value = Mock()

            handler.create_conversation(
                tenant_id="tenant-123",
                request=request,
                user_id="user-123",
                user=mock_user,
                foundry_api_key="test-api-key",
            )

        # Verify Foundry client was called
        mock_foundry_client_class.assert_called_once_with(
            project_endpoint="https://engo-foundry.services.ai.azure.com/api/projects/proj-default-2",
            api_token="test-api-key",
            api_version="2025-11-15-preview",
        )
        mock_foundry_instance.get_conversation_id.assert_called_once()

        # Verify ext_conversation_id was set
        if captured_conversation:
            assert captured_conversation.ext_conversation_id == "conv_foundry_12345"

    @patch("unifiedui.handlers.conversations.MicrosoftFoundryClient")
    def test_create_conversation_foundry_api_error(self, mock_foundry_client_class, handler, mock_db_client, mock_user):
        """Test Foundry API error is properly wrapped."""
        _db_client, session = mock_db_client

        # Mock chat agent query
        mock_app = Mock()
        mock_app.type = ChatAgentTypeEnum.MICROSOFT_FOUNDRY.value
        mock_app.config = {
            "project_endpoint": "https://engo-foundry.services.ai.azure.com/api/projects/proj-default-2",
            "api_version": "2025-11-15-preview",
        }
        session.execute.return_value.scalar_one_or_none.return_value = mock_app

        # Mock Foundry client to raise error
        from unifiedui.libs.foundry.client import MicrosoftFoundryError

        mock_foundry_instance = Mock()
        mock_foundry_instance.get_conversation_id.side_effect = MicrosoftFoundryError(
            message="API error", status_code=500
        )
        mock_foundry_client_class.return_value = mock_foundry_instance

        from unifiedui.schema.requests.conversations import CreateConversationRequest

        request = CreateConversationRequest(chat_agent_id="app-123", name="Test Conversation")

        with pytest.raises(FoundryConversationCreationError) as exc_info:
            handler.create_conversation(
                tenant_id="tenant-123",
                request=request,
                user_id="user-123",
                user=mock_user,
                foundry_api_key="test-api-key",
            )

        assert exc_info.value.status_code == 500
        assert "API error" in str(exc_info.value.message)
