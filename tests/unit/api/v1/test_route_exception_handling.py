"""Tests for route-level generic exception handling (500 error paths).

These tests verify that all API route handlers properly catch unexpected exceptions
and return 500 Internal Server Error responses. This is done by overriding handler
dependencies with mocks that raise RuntimeError, simulating unexpected failures.
"""

from typing import Any
from unittest.mock import patch

from fastapi import status
from starlette.testclient import TestClient

from tests.conftest import create_auth_headers
from unifiedui.handlers.dependencies.autonomous_agents import get_autonomous_agent_handler
from unifiedui.handlers.dependencies.chat_agents import get_chat_agent_handler
from unifiedui.handlers.dependencies.chat_widgets import get_chat_widget_handler
from unifiedui.handlers.dependencies.conversations import get_conversation_handler
from unifiedui.handlers.dependencies.credentials import get_credential_handler
from unifiedui.handlers.dependencies.tags import get_tag_handler
from unifiedui.handlers.dependencies.tenant_ai_models import get_tenant_ai_model_handler
from unifiedui.handlers.dependencies.tools import get_tool_handler

FAKE_ID = "00000000-0000-0000-0000-000000000099"
TEST_SERVICE_KEY = "test-service-key-for-exception-tests"


class FailingHandler:
    """Handler stub that raises RuntimeError on any method call."""

    def __getattr__(self, name: str) -> Any:
        """Raise RuntimeError for any attribute access."""

        def _fail(*args: Any, **kwargs: Any) -> None:
            raise RuntimeError("Unexpected error")

        return _fail


def create_tenant_for_user(test_client: TestClient, user_token: Any, tenant_name: str = "Test Tenant") -> str:
    """Create a tenant and return its ID."""
    headers = create_auth_headers(user_token, use_cache=False)
    response = test_client.post(
        "/api/v1/platform-service/tenants",
        json={"name": tenant_name, "description": "Test"},
        headers=headers,
    )
    assert response.status_code == status.HTTP_201_CREATED
    return response.json()["id"]


def make_failing_handler() -> FailingHandler:
    """Create a handler where all method calls raise RuntimeError."""
    return FailingHandler()


class TestToolRouteExceptionHandling:
    """Test generic exception handling in tool routes."""

    def test_list_tools_500(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test list tools returns 500 on unexpected error."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        mock_handler = make_failing_handler()
        test_client.app.dependency_overrides[get_tool_handler] = lambda: mock_handler

        response = test_client.get(f"/api/v1/platform-service/tenants/{tenant_id}/tools", headers=headers)
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

        del test_client.app.dependency_overrides[get_tool_handler]

    def test_create_tool_500(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test create tool returns 500 on unexpected error."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        mock_handler = make_failing_handler()
        test_client.app.dependency_overrides[get_tool_handler] = lambda: mock_handler

        response = test_client.post(
            f"/api/v1/platform-service/tenants/{tenant_id}/tools",
            json={"name": "Fail Tool", "type": "MCP_SERVER"},
            headers=headers,
        )
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

        del test_client.app.dependency_overrides[get_tool_handler]

    def test_get_tool_500(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test get tool returns 500 on unexpected error."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        mock_handler = make_failing_handler()
        test_client.app.dependency_overrides[get_tool_handler] = lambda: mock_handler

        response = test_client.get(f"/api/v1/platform-service/tenants/{tenant_id}/tools/{FAKE_ID}", headers=headers)
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

        del test_client.app.dependency_overrides[get_tool_handler]

    def test_update_tool_500(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test update tool returns 500 on unexpected error."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        mock_handler = make_failing_handler()
        test_client.app.dependency_overrides[get_tool_handler] = lambda: mock_handler

        response = test_client.patch(
            f"/api/v1/platform-service/tenants/{tenant_id}/tools/{FAKE_ID}",
            json={"name": "Updated"},
            headers=headers,
        )
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

        del test_client.app.dependency_overrides[get_tool_handler]

    def test_delete_tool_500(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test delete tool returns 500 on unexpected error."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        mock_handler = make_failing_handler()
        test_client.app.dependency_overrides[get_tool_handler] = lambda: mock_handler

        response = test_client.delete(f"/api/v1/platform-service/tenants/{tenant_id}/tools/{FAKE_ID}", headers=headers)
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

        del test_client.app.dependency_overrides[get_tool_handler]

    def test_list_tool_principals_500(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test list tool principals returns 500 on unexpected error."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        mock_handler = make_failing_handler()
        test_client.app.dependency_overrides[get_tool_handler] = lambda: mock_handler

        response = test_client.get(
            f"/api/v1/platform-service/tenants/{tenant_id}/tools/{FAKE_ID}/principals", headers=headers
        )
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

        del test_client.app.dependency_overrides[get_tool_handler]

    def test_set_tool_permission_500(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test set tool permission returns 500 on unexpected error."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        mock_handler = make_failing_handler()
        test_client.app.dependency_overrides[get_tool_handler] = lambda: mock_handler

        response = test_client.put(
            f"/api/v1/platform-service/tenants/{tenant_id}/tools/{FAKE_ID}/principals",
            json={"principal_id": "user-1", "principal_type": "IDENTITY_USER", "role": "READ"},
            headers=headers,
        )
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

        del test_client.app.dependency_overrides[get_tool_handler]

    def test_get_tool_principal_500(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test get tool principal returns 500 on unexpected error."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        mock_handler = make_failing_handler()
        test_client.app.dependency_overrides[get_tool_handler] = lambda: mock_handler

        response = test_client.get(
            f"/api/v1/platform-service/tenants/{tenant_id}/tools/{FAKE_ID}/principals/{FAKE_ID}",
            headers=headers,
        )
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

        del test_client.app.dependency_overrides[get_tool_handler]

    def test_delete_tool_principal_500(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test delete tool principal returns 500 on unexpected error."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        mock_handler = make_failing_handler()
        test_client.app.dependency_overrides[get_tool_handler] = lambda: mock_handler

        response = test_client.delete(
            f"/api/v1/platform-service/tenants/{tenant_id}/tools/{FAKE_ID}/principals/{FAKE_ID}"
            "?principal_type=IDENTITY_USER&permission=READ",
            headers=headers,
        )
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

        del test_client.app.dependency_overrides[get_tool_handler]

    def test_list_tools_invalid_tags_format(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test list tools with invalid tag IDs format returns 400."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        response = test_client.get(f"/api/v1/platform-service/tenants/{tenant_id}/tools?tags=abc,xyz", headers=headers)
        assert response.status_code == status.HTTP_400_BAD_REQUEST


class TestCredentialRouteExceptionHandling:
    """Test generic exception handling in credential routes."""

    def test_list_credentials_500(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test list credentials returns 500 on unexpected error."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        mock_handler = make_failing_handler()
        test_client.app.dependency_overrides[get_credential_handler] = lambda: mock_handler

        response = test_client.get(f"/api/v1/platform-service/tenants/{tenant_id}/credentials", headers=headers)
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

        del test_client.app.dependency_overrides[get_credential_handler]

    def test_create_credential_500(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test create credential returns 500 on unexpected error."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        mock_handler = make_failing_handler()
        test_client.app.dependency_overrides[get_credential_handler] = lambda: mock_handler

        response = test_client.post(
            f"/api/v1/platform-service/tenants/{tenant_id}/credentials",
            json={"name": "Fail Cred", "credential_type": "API_KEY", "secret_value": "secret123"},
            headers=headers,
        )
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

        del test_client.app.dependency_overrides[get_credential_handler]

    def test_get_credential_500(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test get credential returns 500 on unexpected error."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        mock_handler = make_failing_handler()
        test_client.app.dependency_overrides[get_credential_handler] = lambda: mock_handler

        response = test_client.get(
            f"/api/v1/platform-service/tenants/{tenant_id}/credentials/{FAKE_ID}", headers=headers
        )
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

        del test_client.app.dependency_overrides[get_credential_handler]

    def test_get_credential_secret_500(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test get credential secret returns 500 on unexpected error."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        mock_handler = make_failing_handler()
        test_client.app.dependency_overrides[get_credential_handler] = lambda: mock_handler

        response = test_client.get(
            f"/api/v1/platform-service/tenants/{tenant_id}/credentials/{FAKE_ID}/secret", headers=headers
        )
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

        del test_client.app.dependency_overrides[get_credential_handler]

    def test_update_credential_500(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test update credential returns 500 on unexpected error."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        mock_handler = make_failing_handler()
        test_client.app.dependency_overrides[get_credential_handler] = lambda: mock_handler

        response = test_client.patch(
            f"/api/v1/platform-service/tenants/{tenant_id}/credentials/{FAKE_ID}",
            json={"name": "Updated"},
            headers=headers,
        )
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

        del test_client.app.dependency_overrides[get_credential_handler]

    def test_delete_credential_500(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test delete credential returns 500 on unexpected error."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        mock_handler = make_failing_handler()
        test_client.app.dependency_overrides[get_credential_handler] = lambda: mock_handler

        response = test_client.delete(
            f"/api/v1/platform-service/tenants/{tenant_id}/credentials/{FAKE_ID}", headers=headers
        )
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

        del test_client.app.dependency_overrides[get_credential_handler]

    def test_list_credential_principals_500(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test list credential principals returns 500 on unexpected error."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        mock_handler = make_failing_handler()
        test_client.app.dependency_overrides[get_credential_handler] = lambda: mock_handler

        response = test_client.get(
            f"/api/v1/platform-service/tenants/{tenant_id}/credentials/{FAKE_ID}/principals",
            headers=headers,
        )
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

        del test_client.app.dependency_overrides[get_credential_handler]

    def test_set_credential_permission_500(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test set credential permission returns 500 on unexpected error."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        mock_handler = make_failing_handler()
        test_client.app.dependency_overrides[get_credential_handler] = lambda: mock_handler

        response = test_client.put(
            f"/api/v1/platform-service/tenants/{tenant_id}/credentials/{FAKE_ID}/principals",
            json={"principal_id": "user-1", "principal_type": "IDENTITY_USER", "role": "READ"},
            headers=headers,
        )
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

        del test_client.app.dependency_overrides[get_credential_handler]

    def test_delete_credential_principal_500(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test delete credential principal returns 500 on unexpected error."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        mock_handler = make_failing_handler()
        test_client.app.dependency_overrides[get_credential_handler] = lambda: mock_handler

        response = test_client.request(
            "DELETE",
            f"/api/v1/platform-service/tenants/{tenant_id}/credentials/{FAKE_ID}/principals",
            json={"principal_id": FAKE_ID, "principal_type": "IDENTITY_USER", "role": "READ"},
            headers=headers,
        )
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

        del test_client.app.dependency_overrides[get_credential_handler]

    def test_list_credentials_invalid_tags_format(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test list credentials with invalid tag IDs returns 400."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        response = test_client.get(
            f"/api/v1/platform-service/tenants/{tenant_id}/credentials?tags=abc", headers=headers
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST


class TestChatWidgetRouteExceptionHandling:
    """Test generic exception handling in chat widget routes."""

    def test_list_chat_widgets_500(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test list chat widgets returns 500 on unexpected error."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        mock_handler = make_failing_handler()
        test_client.app.dependency_overrides[get_chat_widget_handler] = lambda: mock_handler

        response = test_client.get(f"/api/v1/platform-service/tenants/{tenant_id}/chat-widgets", headers=headers)
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

        del test_client.app.dependency_overrides[get_chat_widget_handler]

    def test_create_chat_widget_500(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test create chat widget returns 500 on unexpected error."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        mock_handler = make_failing_handler()
        test_client.app.dependency_overrides[get_chat_widget_handler] = lambda: mock_handler

        response = test_client.post(
            f"/api/v1/platform-service/tenants/{tenant_id}/chat-widgets",
            json={"name": "Widget", "config": {"chat_endpoint": "http://localhost:5678/webhook/chat"}},
            headers=headers,
        )
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

        del test_client.app.dependency_overrides[get_chat_widget_handler]

    def test_get_chat_widget_500(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test get chat widget returns 500 on unexpected error."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        mock_handler = make_failing_handler()
        test_client.app.dependency_overrides[get_chat_widget_handler] = lambda: mock_handler

        response = test_client.get(
            f"/api/v1/platform-service/tenants/{tenant_id}/chat-widgets/{FAKE_ID}", headers=headers
        )
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

        del test_client.app.dependency_overrides[get_chat_widget_handler]

    def test_update_chat_widget_500(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test update chat widget returns 500 on unexpected error."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        mock_handler = make_failing_handler()
        test_client.app.dependency_overrides[get_chat_widget_handler] = lambda: mock_handler

        response = test_client.patch(
            f"/api/v1/platform-service/tenants/{tenant_id}/chat-widgets/{FAKE_ID}",
            json={"name": "Updated"},
            headers=headers,
        )
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

        del test_client.app.dependency_overrides[get_chat_widget_handler]

    def test_delete_chat_widget_500(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test delete chat widget returns 500 on unexpected error."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        mock_handler = make_failing_handler()
        test_client.app.dependency_overrides[get_chat_widget_handler] = lambda: mock_handler

        response = test_client.delete(
            f"/api/v1/platform-service/tenants/{tenant_id}/chat-widgets/{FAKE_ID}", headers=headers
        )
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

        del test_client.app.dependency_overrides[get_chat_widget_handler]

    def test_list_chat_widget_principals_500(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test list chat widget principals returns 500 on unexpected error."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        mock_handler = make_failing_handler()
        test_client.app.dependency_overrides[get_chat_widget_handler] = lambda: mock_handler

        response = test_client.get(
            f"/api/v1/platform-service/tenants/{tenant_id}/chat-widgets/{FAKE_ID}/principals",
            headers=headers,
        )
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

        del test_client.app.dependency_overrides[get_chat_widget_handler]

    def test_set_chat_widget_permission_500(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test set chat widget permission returns 500 on unexpected error."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        mock_handler = make_failing_handler()
        test_client.app.dependency_overrides[get_chat_widget_handler] = lambda: mock_handler

        response = test_client.put(
            f"/api/v1/platform-service/tenants/{tenant_id}/chat-widgets/{FAKE_ID}/principals",
            json={"principal_id": "user-1", "principal_type": "IDENTITY_USER", "role": "READ"},
            headers=headers,
        )
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

        del test_client.app.dependency_overrides[get_chat_widget_handler]

    def test_delete_chat_widget_principal_500(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test delete chat widget principal returns 500 on unexpected error."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        mock_handler = make_failing_handler()
        test_client.app.dependency_overrides[get_chat_widget_handler] = lambda: mock_handler

        response = test_client.request(
            "DELETE",
            f"/api/v1/platform-service/tenants/{tenant_id}/chat-widgets/{FAKE_ID}/principals",
            json={"principal_id": FAKE_ID, "principal_type": "IDENTITY_USER", "role": "READ"},
            headers=headers,
        )
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

        del test_client.app.dependency_overrides[get_chat_widget_handler]

    def test_list_chat_widgets_invalid_tags_format(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test list chat widgets with invalid tag IDs returns 400."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        response = test_client.get(
            f"/api/v1/platform-service/tenants/{tenant_id}/chat-widgets?tags=abc", headers=headers
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST


class TestConversationRouteExceptionHandling:
    """Test generic exception handling in conversation routes."""

    def test_list_conversations_500(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test list conversations returns 500 on unexpected error."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        mock_handler = make_failing_handler()
        test_client.app.dependency_overrides[get_conversation_handler] = lambda: mock_handler

        response = test_client.get(f"/api/v1/platform-service/tenants/{tenant_id}/conversations", headers=headers)
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

        del test_client.app.dependency_overrides[get_conversation_handler]

    def test_create_conversation_500(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test create conversation returns 500 on unexpected error."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        mock_handler = make_failing_handler()
        test_client.app.dependency_overrides[get_conversation_handler] = lambda: mock_handler

        response = test_client.post(
            f"/api/v1/platform-service/tenants/{tenant_id}/conversations",
            json={"name": "Test Conv", "chat_agent_id": FAKE_ID},
            headers=headers,
        )
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

        del test_client.app.dependency_overrides[get_conversation_handler]

    def test_get_conversation_500(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test get conversation returns 500 on unexpected error."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        mock_handler = make_failing_handler()
        test_client.app.dependency_overrides[get_conversation_handler] = lambda: mock_handler

        response = test_client.get(
            f"/api/v1/platform-service/tenants/{tenant_id}/conversations/{FAKE_ID}", headers=headers
        )
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

        del test_client.app.dependency_overrides[get_conversation_handler]

    def test_update_conversation_500(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test update conversation returns 500 on unexpected error."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        mock_handler = make_failing_handler()
        test_client.app.dependency_overrides[get_conversation_handler] = lambda: mock_handler

        response = test_client.patch(
            f"/api/v1/platform-service/tenants/{tenant_id}/conversations/{FAKE_ID}",
            json={"name": "Updated"},
            headers=headers,
        )
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

        del test_client.app.dependency_overrides[get_conversation_handler]

    def test_delete_conversation_500(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test delete conversation returns 500 on unexpected error."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        mock_handler = make_failing_handler()
        test_client.app.dependency_overrides[get_conversation_handler] = lambda: mock_handler

        response = test_client.delete(
            f"/api/v1/platform-service/tenants/{tenant_id}/conversations/{FAKE_ID}", headers=headers
        )
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

        del test_client.app.dependency_overrides[get_conversation_handler]

    def test_list_conversation_principals_500(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test list conversation principals returns 500 on unexpected error."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        mock_handler = make_failing_handler()
        test_client.app.dependency_overrides[get_conversation_handler] = lambda: mock_handler

        response = test_client.get(
            f"/api/v1/platform-service/tenants/{tenant_id}/conversations/{FAKE_ID}/principals",
            headers=headers,
        )
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

        del test_client.app.dependency_overrides[get_conversation_handler]

    def test_set_conversation_permission_500(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test set conversation permission returns 500 on unexpected error."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        mock_handler = make_failing_handler()
        test_client.app.dependency_overrides[get_conversation_handler] = lambda: mock_handler

        response = test_client.put(
            f"/api/v1/platform-service/tenants/{tenant_id}/conversations/{FAKE_ID}/principals",
            json={"principal_id": "user-1", "principal_type": "IDENTITY_USER", "role": "READ"},
            headers=headers,
        )
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

        del test_client.app.dependency_overrides[get_conversation_handler]

    def test_delete_conversation_principal_500(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test delete conversation principal returns 500 on unexpected error."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        mock_handler = make_failing_handler()
        test_client.app.dependency_overrides[get_conversation_handler] = lambda: mock_handler

        response = test_client.request(
            "DELETE",
            f"/api/v1/platform-service/tenants/{tenant_id}/conversations/{FAKE_ID}/principals",
            json={"principal_id": FAKE_ID, "principal_type": "IDENTITY_USER", "role": "READ"},
            headers=headers,
        )
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

        del test_client.app.dependency_overrides[get_conversation_handler]


class TestChatAgentRouteExceptionHandling:
    """Test generic exception handling in chat agent routes."""

    def test_list_chat_agents_500(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test list chat agents returns 500 on unexpected error."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        mock_handler = make_failing_handler()
        test_client.app.dependency_overrides[get_chat_agent_handler] = lambda: mock_handler

        response = test_client.get(f"/api/v1/platform-service/tenants/{tenant_id}/chat-agents", headers=headers)
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

        del test_client.app.dependency_overrides[get_chat_agent_handler]

    def test_create_chat_agent_500(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test create chat agent returns 500 on unexpected error."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        mock_handler = make_failing_handler()
        test_client.app.dependency_overrides[get_chat_agent_handler] = lambda: mock_handler

        response = test_client.post(
            f"/api/v1/platform-service/tenants/{tenant_id}/chat-agents",
            json={"name": "Agent", "type": "N8N", "config": {"chat_endpoint": "http://localhost:5678/webhook/chat"}},
            headers=headers,
        )
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

        del test_client.app.dependency_overrides[get_chat_agent_handler]

    def test_get_chat_agent_500(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test get chat agent returns 500 on unexpected error."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        mock_handler = make_failing_handler()
        test_client.app.dependency_overrides[get_chat_agent_handler] = lambda: mock_handler

        response = test_client.get(
            f"/api/v1/platform-service/tenants/{tenant_id}/chat-agents/{FAKE_ID}", headers=headers
        )
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

        del test_client.app.dependency_overrides[get_chat_agent_handler]

    def test_update_chat_agent_500(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test update chat agent returns 500 on unexpected error."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        mock_handler = make_failing_handler()
        test_client.app.dependency_overrides[get_chat_agent_handler] = lambda: mock_handler

        response = test_client.patch(
            f"/api/v1/platform-service/tenants/{tenant_id}/chat-agents/{FAKE_ID}",
            json={"name": "Updated"},
            headers=headers,
        )
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

        del test_client.app.dependency_overrides[get_chat_agent_handler]

    def test_delete_chat_agent_500(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test delete chat agent returns 500 on unexpected error."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        mock_handler = make_failing_handler()
        test_client.app.dependency_overrides[get_chat_agent_handler] = lambda: mock_handler

        response = test_client.delete(
            f"/api/v1/platform-service/tenants/{tenant_id}/chat-agents/{FAKE_ID}", headers=headers
        )
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

        del test_client.app.dependency_overrides[get_chat_agent_handler]

    def test_get_chat_agent_config_500(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test get chat agent config returns 500 on unexpected error."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        mock_handler = make_failing_handler()
        test_client.app.dependency_overrides[get_chat_agent_handler] = lambda: mock_handler

        with patch(
            "unifiedui.core.middleware.apis.v1.auth._resolve_service_key",
            return_value=TEST_SERVICE_KEY,
        ):
            response = test_client.get(
                f"/api/v1/platform-service/tenants/{tenant_id}/chat-agents/{FAKE_ID}/config",
                headers={**headers, "X-Service-Key": TEST_SERVICE_KEY},
            )
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

        del test_client.app.dependency_overrides[get_chat_agent_handler]

    def test_list_chat_agent_principals_500(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test list chat agent principals returns 500 on unexpected error."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        mock_handler = make_failing_handler()
        test_client.app.dependency_overrides[get_chat_agent_handler] = lambda: mock_handler

        response = test_client.get(
            f"/api/v1/platform-service/tenants/{tenant_id}/chat-agents/{FAKE_ID}/principals",
            headers=headers,
        )
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

        del test_client.app.dependency_overrides[get_chat_agent_handler]

    def test_set_chat_agent_permission_500(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test set chat agent permission returns 500 on unexpected error."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        mock_handler = make_failing_handler()
        test_client.app.dependency_overrides[get_chat_agent_handler] = lambda: mock_handler

        response = test_client.put(
            f"/api/v1/platform-service/tenants/{tenant_id}/chat-agents/{FAKE_ID}/principals",
            json={"principal_id": "user-1", "principal_type": "IDENTITY_USER", "role": "READ"},
            headers=headers,
        )
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

        del test_client.app.dependency_overrides[get_chat_agent_handler]

    def test_delete_chat_agent_principal_500(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test delete chat agent principal returns 500 on unexpected error."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        mock_handler = make_failing_handler()
        test_client.app.dependency_overrides[get_chat_agent_handler] = lambda: mock_handler

        response = test_client.request(
            "DELETE",
            f"/api/v1/platform-service/tenants/{tenant_id}/chat-agents/{FAKE_ID}/principals",
            json={"principal_id": FAKE_ID, "principal_type": "IDENTITY_USER", "role": "READ"},
            headers=headers,
        )
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

        del test_client.app.dependency_overrides[get_chat_agent_handler]

    def test_list_chat_agents_invalid_tags_format(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test list chat agents with invalid tag IDs returns 400."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        response = test_client.get(
            f"/api/v1/platform-service/tenants/{tenant_id}/chat-agents?tags=abc", headers=headers
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST


class TestAutonomousAgentRouteExceptionHandling:
    """Test generic exception handling in autonomous agent routes."""

    def test_list_autonomous_agents_500(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test list autonomous agents returns 500 on unexpected error."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        mock_handler = make_failing_handler()
        test_client.app.dependency_overrides[get_autonomous_agent_handler] = lambda: mock_handler

        response = test_client.get(f"/api/v1/platform-service/tenants/{tenant_id}/autonomous-agents", headers=headers)
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

        del test_client.app.dependency_overrides[get_autonomous_agent_handler]

    def test_create_autonomous_agent_500(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test create autonomous agent returns 500 on unexpected error."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        mock_handler = make_failing_handler()
        test_client.app.dependency_overrides[get_autonomous_agent_handler] = lambda: mock_handler

        response = test_client.post(
            f"/api/v1/platform-service/tenants/{tenant_id}/autonomous-agents",
            json={
                "name": "Agent",
                "type": "N8N",
                "config": {
                    "api_version": "v1",
                    "workflow_endpoint": "http://localhost:5678/workflow/test",
                    "api_api_key_credential_id": "cred-1",
                },
            },
            headers=headers,
        )
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

        del test_client.app.dependency_overrides[get_autonomous_agent_handler]

    def test_get_autonomous_agent_500(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test get autonomous agent returns 500 on unexpected error."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        mock_handler = make_failing_handler()
        test_client.app.dependency_overrides[get_autonomous_agent_handler] = lambda: mock_handler

        response = test_client.get(
            f"/api/v1/platform-service/tenants/{tenant_id}/autonomous-agents/{FAKE_ID}",
            headers=headers,
        )
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

        del test_client.app.dependency_overrides[get_autonomous_agent_handler]

    def test_update_autonomous_agent_500(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test update autonomous agent returns 500 on unexpected error."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        mock_handler = make_failing_handler()
        test_client.app.dependency_overrides[get_autonomous_agent_handler] = lambda: mock_handler

        response = test_client.patch(
            f"/api/v1/platform-service/tenants/{tenant_id}/autonomous-agents/{FAKE_ID}",
            json={"name": "Updated"},
            headers=headers,
        )
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

        del test_client.app.dependency_overrides[get_autonomous_agent_handler]

    def test_delete_autonomous_agent_500(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test delete autonomous agent returns 500 on unexpected error."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        mock_handler = make_failing_handler()
        test_client.app.dependency_overrides[get_autonomous_agent_handler] = lambda: mock_handler

        response = test_client.delete(
            f"/api/v1/platform-service/tenants/{tenant_id}/autonomous-agents/{FAKE_ID}",
            headers=headers,
        )
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

        del test_client.app.dependency_overrides[get_autonomous_agent_handler]

    def test_list_autonomous_agent_principals_500(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test list autonomous agent principals returns 500 on unexpected error."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        mock_handler = make_failing_handler()
        test_client.app.dependency_overrides[get_autonomous_agent_handler] = lambda: mock_handler

        response = test_client.get(
            f"/api/v1/platform-service/tenants/{tenant_id}/autonomous-agents/{FAKE_ID}/principals",
            headers=headers,
        )
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

        del test_client.app.dependency_overrides[get_autonomous_agent_handler]

    def test_set_autonomous_agent_permission_500(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test set autonomous agent permission returns 500 on unexpected error."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        mock_handler = make_failing_handler()
        test_client.app.dependency_overrides[get_autonomous_agent_handler] = lambda: mock_handler

        response = test_client.put(
            f"/api/v1/platform-service/tenants/{tenant_id}/autonomous-agents/{FAKE_ID}/principals",
            json={"principal_id": "user-1", "principal_type": "IDENTITY_USER", "role": "READ"},
            headers=headers,
        )
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

        del test_client.app.dependency_overrides[get_autonomous_agent_handler]

    def test_delete_autonomous_agent_principal_500(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test delete autonomous agent principal returns 500 on unexpected error."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        mock_handler = make_failing_handler()
        test_client.app.dependency_overrides[get_autonomous_agent_handler] = lambda: mock_handler

        response = test_client.request(
            "DELETE",
            f"/api/v1/platform-service/tenants/{tenant_id}/autonomous-agents/{FAKE_ID}/principals",
            json={"principal_id": FAKE_ID, "principal_type": "IDENTITY_USER", "role": "READ"},
            headers=headers,
        )
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

        del test_client.app.dependency_overrides[get_autonomous_agent_handler]

    def test_list_autonomous_agents_invalid_tags_format(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test list autonomous agents with invalid tag IDs returns 400."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        response = test_client.get(
            f"/api/v1/platform-service/tenants/{tenant_id}/autonomous-agents?tags=abc", headers=headers
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST


class TestTagRouteExceptionHandling:
    """Test generic exception handling in tag routes."""

    def test_list_tags_500(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test list tags returns 500 on unexpected error."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        mock_handler = make_failing_handler()
        test_client.app.dependency_overrides[get_tag_handler] = lambda: mock_handler

        response = test_client.get(f"/api/v1/platform-service/tenants/{tenant_id}/tags", headers=headers)
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

        del test_client.app.dependency_overrides[get_tag_handler]

    def test_create_tag_500(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test create tag returns 500 on unexpected error."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        mock_handler = make_failing_handler()
        test_client.app.dependency_overrides[get_tag_handler] = lambda: mock_handler

        response = test_client.post(
            f"/api/v1/platform-service/tenants/{tenant_id}/tags",
            json={"name": "test-tag"},
            headers=headers,
        )
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

        del test_client.app.dependency_overrides[get_tag_handler]

    def test_delete_tag_500(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test delete tag returns 500 on unexpected error."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        mock_handler = make_failing_handler()
        test_client.app.dependency_overrides[get_tag_handler] = lambda: mock_handler

        response = test_client.delete(f"/api/v1/platform-service/tenants/{tenant_id}/tags/999", headers=headers)
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

        del test_client.app.dependency_overrides[get_tag_handler]

    def test_get_resource_tags_500(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test get chat agent tags returns 500 on unexpected error."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        mock_handler = make_failing_handler()
        test_client.app.dependency_overrides[get_tag_handler] = lambda: mock_handler

        response = test_client.get(
            f"/api/v1/platform-service/tenants/{tenant_id}/chat-agents/{FAKE_ID}/tags",
            headers=headers,
        )
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

        del test_client.app.dependency_overrides[get_tag_handler]

    def test_set_resource_tags_500(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test set chat agent tags returns 500 on unexpected error."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        mock_handler = make_failing_handler()
        test_client.app.dependency_overrides[get_tag_handler] = lambda: mock_handler

        response = test_client.put(
            f"/api/v1/platform-service/tenants/{tenant_id}/chat-agents/{FAKE_ID}/tags",
            json={"tags": ["tag1"]},
            headers=headers,
        )
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

        del test_client.app.dependency_overrides[get_tag_handler]

    def test_delete_resource_tags_500(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test delete chat agent tags returns 500 on unexpected error."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        mock_handler = make_failing_handler()
        test_client.app.dependency_overrides[get_tag_handler] = lambda: mock_handler

        response = test_client.delete(
            f"/api/v1/platform-service/tenants/{tenant_id}/chat-agents/{FAKE_ID}/tags",
            headers=headers,
        )
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

        del test_client.app.dependency_overrides[get_tag_handler]

    def test_list_resource_type_tags_500(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test list chat agent type tags returns 500 on unexpected error."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        mock_handler = make_failing_handler()
        test_client.app.dependency_overrides[get_tag_handler] = lambda: mock_handler

        response = test_client.get(
            f"/api/v1/platform-service/tenants/{tenant_id}/chat-agents/tags",
            headers=headers,
        )
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

        del test_client.app.dependency_overrides[get_tag_handler]

    def test_get_autonomous_agent_tags_500(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test get autonomous agent tags returns 500 on unexpected error."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        mock_handler = make_failing_handler()
        test_client.app.dependency_overrides[get_tag_handler] = lambda: mock_handler

        response = test_client.get(
            f"/api/v1/platform-service/tenants/{tenant_id}/autonomous-agents/{FAKE_ID}/tags",
            headers=headers,
        )
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

        del test_client.app.dependency_overrides[get_tag_handler]

    def test_set_autonomous_agent_tags_500(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test set autonomous agent tags returns 500 on unexpected error."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        mock_handler = make_failing_handler()
        test_client.app.dependency_overrides[get_tag_handler] = lambda: mock_handler

        response = test_client.put(
            f"/api/v1/platform-service/tenants/{tenant_id}/autonomous-agents/{FAKE_ID}/tags",
            json={"tags": ["tag1"]},
            headers=headers,
        )
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

        del test_client.app.dependency_overrides[get_tag_handler]

    def test_delete_autonomous_agent_tags_500(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test delete autonomous agent tags returns 500 on unexpected error."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        mock_handler = make_failing_handler()
        test_client.app.dependency_overrides[get_tag_handler] = lambda: mock_handler

        response = test_client.delete(
            f"/api/v1/platform-service/tenants/{tenant_id}/autonomous-agents/{FAKE_ID}/tags",
            headers=headers,
        )
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

        del test_client.app.dependency_overrides[get_tag_handler]

    def test_list_autonomous_agent_type_tags_500(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test list autonomous agent type tags returns 500 on unexpected error."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        mock_handler = make_failing_handler()
        test_client.app.dependency_overrides[get_tag_handler] = lambda: mock_handler

        response = test_client.get(
            f"/api/v1/platform-service/tenants/{tenant_id}/autonomous-agents/tags",
            headers=headers,
        )
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

        del test_client.app.dependency_overrides[get_tag_handler]

    def test_get_chat_widget_tags_500(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test get chat widget tags returns 500 on unexpected error."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        mock_handler = make_failing_handler()
        test_client.app.dependency_overrides[get_tag_handler] = lambda: mock_handler

        response = test_client.get(
            f"/api/v1/platform-service/tenants/{tenant_id}/chat-widgets/{FAKE_ID}/tags",
            headers=headers,
        )
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

        del test_client.app.dependency_overrides[get_tag_handler]

    def test_set_chat_widget_tags_500(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test set chat widget tags returns 500 on unexpected error."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        mock_handler = make_failing_handler()
        test_client.app.dependency_overrides[get_tag_handler] = lambda: mock_handler

        response = test_client.put(
            f"/api/v1/platform-service/tenants/{tenant_id}/chat-widgets/{FAKE_ID}/tags",
            json={"tags": ["tag1"]},
            headers=headers,
        )
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

        del test_client.app.dependency_overrides[get_tag_handler]

    def test_delete_chat_widget_tags_500(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test delete chat widget tags returns 500 on unexpected error."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        mock_handler = make_failing_handler()
        test_client.app.dependency_overrides[get_tag_handler] = lambda: mock_handler

        response = test_client.delete(
            f"/api/v1/platform-service/tenants/{tenant_id}/chat-widgets/{FAKE_ID}/tags",
            headers=headers,
        )
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

        del test_client.app.dependency_overrides[get_tag_handler]

    def test_list_chat_widget_type_tags_500(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test list chat widget type tags returns 500 on unexpected error."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        mock_handler = make_failing_handler()
        test_client.app.dependency_overrides[get_tag_handler] = lambda: mock_handler

        response = test_client.get(
            f"/api/v1/platform-service/tenants/{tenant_id}/chat-widgets/tags",
            headers=headers,
        )
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

        del test_client.app.dependency_overrides[get_tag_handler]

    def test_get_credential_tags_500(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test get credential tags returns 500 on unexpected error."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        mock_handler = make_failing_handler()
        test_client.app.dependency_overrides[get_tag_handler] = lambda: mock_handler

        response = test_client.get(
            f"/api/v1/platform-service/tenants/{tenant_id}/credentials/{FAKE_ID}/tags",
            headers=headers,
        )
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

        del test_client.app.dependency_overrides[get_tag_handler]

    def test_set_credential_tags_500(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test set credential tags returns 500 on unexpected error."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        mock_handler = make_failing_handler()
        test_client.app.dependency_overrides[get_tag_handler] = lambda: mock_handler

        response = test_client.put(
            f"/api/v1/platform-service/tenants/{tenant_id}/credentials/{FAKE_ID}/tags",
            json={"tags": ["tag1"]},
            headers=headers,
        )
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

        del test_client.app.dependency_overrides[get_tag_handler]

    def test_delete_credential_tags_500(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test delete credential tags returns 500 on unexpected error."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        mock_handler = make_failing_handler()
        test_client.app.dependency_overrides[get_tag_handler] = lambda: mock_handler

        response = test_client.delete(
            f"/api/v1/platform-service/tenants/{tenant_id}/credentials/{FAKE_ID}/tags",
            headers=headers,
        )
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

        del test_client.app.dependency_overrides[get_tag_handler]

    def test_list_credential_type_tags_500(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test list credential type tags returns 500 on unexpected error."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        mock_handler = make_failing_handler()
        test_client.app.dependency_overrides[get_tag_handler] = lambda: mock_handler

        response = test_client.get(
            f"/api/v1/platform-service/tenants/{tenant_id}/credentials/tags",
            headers=headers,
        )
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

        del test_client.app.dependency_overrides[get_tag_handler]

    def test_get_tool_tags_500(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test get tool tags returns 500 on unexpected error."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        mock_handler = make_failing_handler()
        test_client.app.dependency_overrides[get_tag_handler] = lambda: mock_handler

        response = test_client.get(
            f"/api/v1/platform-service/tenants/{tenant_id}/tools/{FAKE_ID}/tags",
            headers=headers,
        )
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

        del test_client.app.dependency_overrides[get_tag_handler]

    def test_set_tool_tags_500(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test set tool tags returns 500 on unexpected error."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        mock_handler = make_failing_handler()
        test_client.app.dependency_overrides[get_tag_handler] = lambda: mock_handler

        response = test_client.put(
            f"/api/v1/platform-service/tenants/{tenant_id}/tools/{FAKE_ID}/tags",
            json={"tags": ["tag1"]},
            headers=headers,
        )
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

        del test_client.app.dependency_overrides[get_tag_handler]

    def test_delete_tool_tags_500(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test delete tool tags returns 500 on unexpected error."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        mock_handler = make_failing_handler()
        test_client.app.dependency_overrides[get_tag_handler] = lambda: mock_handler

        response = test_client.delete(
            f"/api/v1/platform-service/tenants/{tenant_id}/tools/{FAKE_ID}/tags",
            headers=headers,
        )
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

        del test_client.app.dependency_overrides[get_tag_handler]

    def test_list_tool_type_tags_500(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test list tool type tags returns 500 on unexpected error."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        mock_handler = make_failing_handler()
        test_client.app.dependency_overrides[get_tag_handler] = lambda: mock_handler

        response = test_client.get(
            f"/api/v1/platform-service/tenants/{tenant_id}/tools/tags",
            headers=headers,
        )
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

        del test_client.app.dependency_overrides[get_tag_handler]


class TestTenantAIModelRouteExceptionHandling:
    """Test generic exception handling in tenant AI model routes."""

    def test_list_tenant_ai_models_500(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test list AI models returns 500 on unexpected error."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        mock_handler = make_failing_handler()
        test_client.app.dependency_overrides[get_tenant_ai_model_handler] = lambda: mock_handler

        response = test_client.get(f"/api/v1/platform-service/tenants/{tenant_id}/ai-models", headers=headers)
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

        del test_client.app.dependency_overrides[get_tenant_ai_model_handler]

    def test_create_tenant_ai_model_500(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test create AI model returns 500 on unexpected error."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        mock_handler = make_failing_handler()
        test_client.app.dependency_overrides[get_tenant_ai_model_handler] = lambda: mock_handler

        response = test_client.post(
            f"/api/v1/platform-service/tenants/{tenant_id}/ai-models",
            json={"name": "GPT-4", "type": "LLM_MODEL", "provider": "OPENAI"},
            headers=headers,
        )
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

        del test_client.app.dependency_overrides[get_tenant_ai_model_handler]

    def test_get_tenant_ai_model_500(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test get AI model returns 500 on unexpected error."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        mock_handler = make_failing_handler()
        test_client.app.dependency_overrides[get_tenant_ai_model_handler] = lambda: mock_handler

        response = test_client.get(f"/api/v1/platform-service/tenants/{tenant_id}/ai-models/{FAKE_ID}", headers=headers)
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

        del test_client.app.dependency_overrides[get_tenant_ai_model_handler]

    def test_update_tenant_ai_model_500(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test update AI model returns 500 on unexpected error."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        mock_handler = make_failing_handler()
        test_client.app.dependency_overrides[get_tenant_ai_model_handler] = lambda: mock_handler

        response = test_client.patch(
            f"/api/v1/platform-service/tenants/{tenant_id}/ai-models/{FAKE_ID}",
            json={"name": "Updated"},
            headers=headers,
        )
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

        del test_client.app.dependency_overrides[get_tenant_ai_model_handler]

    def test_delete_tenant_ai_model_500(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test delete AI model returns 500 on unexpected error."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        mock_handler = make_failing_handler()
        test_client.app.dependency_overrides[get_tenant_ai_model_handler] = lambda: mock_handler

        response = test_client.delete(
            f"/api/v1/platform-service/tenants/{tenant_id}/ai-models/{FAKE_ID}", headers=headers
        )
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

        del test_client.app.dependency_overrides[get_tenant_ai_model_handler]
