"""Tests for conversations API endpoints."""

from typing import Any

from fastapi import status
from starlette.testclient import TestClient

from tests.conftest import create_auth_headers
from tests.helpers.tenant import create_tenant_for_user
from unifiedui.core.database.enums import PermissionActionEnum, PrincipalTypeEnum

# API Endpoints
ENDPOINT_CONVERSATIONS = "/api/v1/platform-service/tenants/{tenant_id}/conversations"
ENDPOINT_CONVERSATION_DETAIL = "/api/v1/platform-service/tenants/{tenant_id}/conversations/{conversation_id}"
ENDPOINT_CONVERSATION_PRINCIPALS = (
    "/api/v1/platform-service/tenants/{tenant_id}/conversations/{conversation_id}/principals"
)
ENDPOINT_PRINCIPAL_DETAIL = (
    "/api/v1/platform-service/tenants/{tenant_id}/conversations/{conversation_id}/principals/{principal_id}"
)

# Common Test IDs
NON_EXISTENT_ID = "non-existent-id"

# Roles
ROLE_READ = PermissionActionEnum.READ.value
ROLE_WRITE = PermissionActionEnum.WRITE.value
ROLE_ADMIN = PermissionActionEnum.ADMIN.value

# Principal Types
PRINCIPAL_TYPE_USER = PrincipalTypeEnum.IDENTITY_USER.value
PRINCIPAL_TYPE_GROUP = PrincipalTypeEnum.IDENTITY_GROUP.value
PRINCIPAL_TYPE_CUSTOM_GROUP = PrincipalTypeEnum.CUSTOM_GROUP.value

# Chat agent endpoint for creating chat agents
ENDPOINT_CHAT_AGENTS = "/api/v1/platform-service/tenants/{tenant_id}/chat-agents"


def create_chat_agent_for_user(
    test_client: TestClient, user_token: Any, tenant_id: str, app_name: str = "Test App"
) -> str:
    """Helper function to create a chat agent and return its ID."""
    headers = create_auth_headers(user_token, use_cache=False)
    response = test_client.post(
        ENDPOINT_CHAT_AGENTS.format(tenant_id=tenant_id),
        json={"name": app_name, "description": "Chat agent for testing conversations", "type": "N8N"},
        headers=headers,
    )
    assert response.status_code == status.HTTP_201_CREATED
    return response.json()["id"]


class TestConversationRoutes:
    """Test suite for conversation API routes."""

    def test_create_conversation_success(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test successful conversation creation."""
        # Create a tenant first
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        # Create chat agent for conversation
        chat_agent_id = create_chat_agent_for_user(test_client, test_user_token, tenant_id)

        # Create conversation
        conversation_data = {
            "chat_agent_id": chat_agent_id,
            "name": "Test Conversation",
            "description": "A test conversation",
        }

        response = test_client.post(
            ENDPOINT_CONVERSATIONS.format(tenant_id=tenant_id), json=conversation_data, headers=headers
        )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()

        assert data["name"] == conversation_data["name"]
        assert data["description"] == conversation_data["description"]
        assert data["chat_agent_id"] == chat_agent_id
        assert not data["is_active"]
        assert "id" in data
        assert data["tenant_id"] == tenant_id
        assert "created_at" in data
        assert "updated_at" in data
        assert data["created_by"] == test_user_token.get_id()

    def test_create_conversation_missing_name(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test conversation creation with missing name."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        chat_agent_id = create_chat_agent_for_user(test_client, test_user_token, tenant_id)

        response = test_client.post(
            ENDPOINT_CONVERSATIONS.format(tenant_id=tenant_id),
            json={"chat_agent_id": chat_agent_id, "description": "Test conversation"},
            headers=headers,
        )

        assert response.status_code == 422

    def test_create_conversation_invalid_name_type(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test conversation creation with invalid name type."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        chat_agent_id = create_chat_agent_for_user(test_client, test_user_token, tenant_id)

        response = test_client.post(
            ENDPOINT_CONVERSATIONS.format(tenant_id=tenant_id),
            json={"chat_agent_id": chat_agent_id, "name": 123, "description": "Test"},
            headers=headers,
        )

        assert response.status_code == 422

    def test_create_conversation_empty_name(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test conversation creation with empty name."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        chat_agent_id = create_chat_agent_for_user(test_client, test_user_token, tenant_id)

        response = test_client.post(
            ENDPOINT_CONVERSATIONS.format(tenant_id=tenant_id),
            json={"chat_agent_id": chat_agent_id, "name": "", "description": "Test"},
            headers=headers,
        )

        assert response.status_code == 422

    def test_create_conversation_invalid_description_type(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test conversation creation with invalid description type."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        chat_agent_id = create_chat_agent_for_user(test_client, test_user_token, tenant_id)

        response = test_client.post(
            ENDPOINT_CONVERSATIONS.format(tenant_id=tenant_id),
            json={"chat_agent_id": chat_agent_id, "name": "Test Conversation", "description": 123},
            headers=headers,
        )

        assert response.status_code == 422

    def test_create_conversation_empty_body(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test conversation creation with empty JSON body."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        response = test_client.post(ENDPOINT_CONVERSATIONS.format(tenant_id=tenant_id), json={}, headers=headers)

        assert response.status_code == 422

    def test_create_conversation_without_permission(self, test_client: TestClient) -> None:
        """Test that user without CONVERSATION_CREATOR permission cannot create conversations."""
        # Create user1 with a tenant
        user1_token = test_client.create_test_user("user-1", "User One")
        tenant_id = create_tenant_for_user(test_client, user1_token)
        chat_agent_id = create_chat_agent_for_user(test_client, user1_token, tenant_id)

        # Create user2 (not a member of the tenant)
        user2_token = test_client.create_test_user("user-2", "User Two")
        headers2 = create_auth_headers(user2_token, use_cache=False)

        # Try to create conversation as user2 (should fail - no tenant membership)
        response = test_client.post(
            ENDPOINT_CONVERSATIONS.format(tenant_id=tenant_id),
            json={"chat_agent_id": chat_agent_id, "name": "Unauthorized Conversation", "description": "Should fail"},
            headers=headers2,
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_get_conversation_success(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test successful conversation retrieval."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        chat_agent_id = create_chat_agent_for_user(test_client, test_user_token, tenant_id)

        # Create a conversation
        conversation_data = {
            "chat_agent_id": chat_agent_id,
            "name": "Test Conversation",
            "description": "Test description",
        }
        create_response = test_client.post(
            ENDPOINT_CONVERSATIONS.format(tenant_id=tenant_id), json=conversation_data, headers=headers
        )
        conversation_id = create_response.json()["id"]

        # Retrieve the conversation
        response = test_client.get(
            ENDPOINT_CONVERSATION_DETAIL.format(tenant_id=tenant_id, conversation_id=conversation_id), headers=headers
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["id"] == conversation_id
        assert data["name"] == conversation_data["name"]
        assert data["description"] == conversation_data["description"]

    def test_get_conversation_not_found(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test conversation retrieval with non-existent ID."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        response = test_client.get(
            ENDPOINT_CONVERSATION_DETAIL.format(tenant_id=tenant_id, conversation_id=NON_EXISTENT_ID), headers=headers
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_list_conversations_empty(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test listing conversations when none exist."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        response = test_client.get(ENDPOINT_CONVERSATIONS.format(tenant_id=tenant_id), headers=headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert isinstance(data, list)
        assert len(data) == 0

    def test_list_conversations_with_data(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test listing conversations with existing data."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        chat_agent_id = create_chat_agent_for_user(test_client, test_user_token, tenant_id)

        # Create multiple conversations
        conversation1_data = {
            "chat_agent_id": chat_agent_id,
            "name": "Conversation 1",
            "description": "First conversation",
        }
        conversation2_data = {
            "chat_agent_id": chat_agent_id,
            "name": "Conversation 2",
            "description": "Second conversation",
        }

        test_client.post(ENDPOINT_CONVERSATIONS.format(tenant_id=tenant_id), json=conversation1_data, headers=headers)
        test_client.post(ENDPOINT_CONVERSATIONS.format(tenant_id=tenant_id), json=conversation2_data, headers=headers)

        # List conversations
        response = test_client.get(ENDPOINT_CONVERSATIONS.format(tenant_id=tenant_id), headers=headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert isinstance(data, list)
        assert len(data) == 2

        names = [conversation["name"] for conversation in data]
        assert "Conversation 1" in names
        assert "Conversation 2" in names

    def test_list_conversations_with_pagination(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test listing conversations with pagination parameters."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        chat_agent_id = create_chat_agent_for_user(test_client, test_user_token, tenant_id)

        # Create multiple conversations
        for i in range(5):
            test_client.post(
                ENDPOINT_CONVERSATIONS.format(tenant_id=tenant_id),
                json={"chat_agent_id": chat_agent_id, "name": f"Conversation {i}", "description": f"Description {i}"},
                headers=headers,
            )

        # Test with limit
        response = test_client.get(f"{ENDPOINT_CONVERSATIONS.format(tenant_id=tenant_id)}?limit=3", headers=headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 3

        # Test with skip
        response = test_client.get(
            f"{ENDPOINT_CONVERSATIONS.format(tenant_id=tenant_id)}?skip=2&limit=2", headers=headers
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 2

    def test_list_conversations_with_name_filter(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test listing conversations with name filter."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        chat_agent_id = create_chat_agent_for_user(test_client, test_user_token, tenant_id)

        # Create conversations with different names
        test_client.post(
            ENDPOINT_CONVERSATIONS.format(tenant_id=tenant_id),
            json={"chat_agent_id": chat_agent_id, "name": "Production Chat", "description": "Prod"},
            headers=headers,
        )
        test_client.post(
            ENDPOINT_CONVERSATIONS.format(tenant_id=tenant_id),
            json={"chat_agent_id": chat_agent_id, "name": "Development Chat", "description": "Dev"},
            headers=headers,
        )

        # Filter by name
        response = test_client.get(
            f"{ENDPOINT_CONVERSATIONS.format(tenant_id=tenant_id)}?name=Production", headers=headers
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert len(data) == 1
        assert data[0]["name"] == "Production Chat"

    def test_update_conversation_success(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test successful conversation update."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        chat_agent_id = create_chat_agent_for_user(test_client, test_user_token, tenant_id)

        # Create conversation
        create_response = test_client.post(
            ENDPOINT_CONVERSATIONS.format(tenant_id=tenant_id),
            json={"chat_agent_id": chat_agent_id, "name": "Original", "description": "Original Description"},
            headers=headers,
        )
        conversation_id = create_response.json()["id"]

        # Update conversation
        update_response = test_client.patch(
            ENDPOINT_CONVERSATION_DETAIL.format(tenant_id=tenant_id, conversation_id=conversation_id),
            json={"name": "Updated", "description": "Updated Description"},
            headers=headers,
        )

        assert update_response.status_code == status.HTTP_200_OK
        data = update_response.json()

        assert data["name"] == "Updated"
        assert data["description"] == "Updated Description"

    def test_update_conversation_not_found(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test conversation update with non-existent ID."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        response = test_client.patch(
            ENDPOINT_CONVERSATION_DETAIL.format(tenant_id=tenant_id, conversation_id=NON_EXISTENT_ID),
            json={"name": "Updated"},
            headers=headers,
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_update_conversation_partial(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test partial conversation update (only name)."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        create_auth_headers(test_user_token, use_cache=False)
        create_chat_agent_for_user(test_client, test_user_token, tenant_id)

        # Create conversation

    def test_update_conversation_is_active(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test updating conversation is_active status."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        chat_agent_id = create_chat_agent_for_user(test_client, test_user_token, tenant_id)

        # Create conversation (default is_active=False)
        create_response = test_client.post(
            ENDPOINT_CONVERSATIONS.format(tenant_id=tenant_id),
            json={"chat_agent_id": chat_agent_id, "name": "Test Conversation", "description": "Test"},
            headers=headers,
        )
        conversation_id = create_response.json()["id"]
        assert not create_response.json()["is_active"]

        # Update to active
        update_response = test_client.patch(
            ENDPOINT_CONVERSATION_DETAIL.format(tenant_id=tenant_id, conversation_id=conversation_id),
            json={"is_active": True},
            headers=headers,
        )

        assert update_response.status_code == status.HTTP_200_OK
        assert update_response.json()["is_active"]

        # Update back to inactive
        update_response2 = test_client.patch(
            ENDPOINT_CONVERSATION_DETAIL.format(tenant_id=tenant_id, conversation_id=conversation_id),
            json={"is_active": False},
            headers=headers,
        )

        assert update_response2.status_code == status.HTTP_200_OK
        assert not update_response2.json()["is_active"]
        create_response = test_client.post(
            ENDPOINT_CONVERSATIONS.format(tenant_id=tenant_id),
            json={"chat_agent_id": chat_agent_id, "name": "Original", "description": "Keep this"},
            headers=headers,
        )
        conversation_id = create_response.json()["id"]

        # Update only name
        update_response = test_client.patch(
            ENDPOINT_CONVERSATION_DETAIL.format(tenant_id=tenant_id, conversation_id=conversation_id),
            json={"name": "Updated Name Only"},
            headers=headers,
        )

        assert update_response.status_code == status.HTTP_200_OK
        data = update_response.json()

        assert data["name"] == "Updated Name Only"
        assert data["description"] == "Keep this"

    def test_delete_conversation_success(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test successful conversation deletion."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        chat_agent_id = create_chat_agent_for_user(test_client, test_user_token, tenant_id)

        # Create conversation
        create_response = test_client.post(
            ENDPOINT_CONVERSATIONS.format(tenant_id=tenant_id),
            json={"chat_agent_id": chat_agent_id, "name": "To Delete", "description": "Will be deleted"},
            headers=headers,
        )
        conversation_id = create_response.json()["id"]

        # Delete conversation
        delete_response = test_client.request(
            "DELETE",
            ENDPOINT_CONVERSATION_DETAIL.format(tenant_id=tenant_id, conversation_id=conversation_id),
            headers=headers,
        )

        assert delete_response.status_code == status.HTTP_204_NO_CONTENT

        # Verify conversation is deleted
        get_response = test_client.get(
            ENDPOINT_CONVERSATION_DETAIL.format(tenant_id=tenant_id, conversation_id=conversation_id), headers=headers
        )
        assert get_response.status_code == status.HTTP_404_NOT_FOUND

    def test_delete_conversation_not_found(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test conversation deletion with non-existent ID."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        response = test_client.request(
            "DELETE",
            ENDPOINT_CONVERSATION_DETAIL.format(tenant_id=tenant_id, conversation_id=NON_EXISTENT_ID),
            headers=headers,
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestConversationPrincipalRoutes:
    """Test suite for conversation principal/permission management routes."""

    def test_list_conversation_principals_creator_only(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test that only creator is listed initially."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        chat_agent_id = create_chat_agent_for_user(test_client, test_user_token, tenant_id)

        # Create conversation
        create_response = test_client.post(
            ENDPOINT_CONVERSATIONS.format(tenant_id=tenant_id),
            json={"chat_agent_id": chat_agent_id, "name": "Test Conversation", "description": "Test"},
            headers=headers,
        )
        conversation_id = create_response.json()["id"]

        # List principals
        response = test_client.get(
            ENDPOINT_CONVERSATION_PRINCIPALS.format(tenant_id=tenant_id, conversation_id=conversation_id),
            headers=headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert "resource_id" in data
        assert "resource_type" in data
        assert data["resource_type"] == "conversation"
        assert "principals" in data
        assert len(data["principals"]) == 1
        assert data["principals"][0]["principal_id"] == test_user_token.get_id()
        assert ROLE_ADMIN in data["principals"][0]["roles"]

    def test_get_principal_permissions(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test getting specific principal permissions."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        chat_agent_id = create_chat_agent_for_user(test_client, test_user_token, tenant_id)

        # Create conversation
        create_response = test_client.post(
            ENDPOINT_CONVERSATIONS.format(tenant_id=tenant_id),
            json={"chat_agent_id": chat_agent_id, "name": "Test Conversation", "description": "Test"},
            headers=headers,
        )
        conversation_id = create_response.json()["id"]

        # Get creator's permissions
        response = test_client.get(
            ENDPOINT_PRINCIPAL_DETAIL.format(
                tenant_id=tenant_id, conversation_id=conversation_id, principal_id=test_user_token.get_id()
            ),
            headers=headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["principal_id"] == test_user_token.get_id()
        assert ROLE_ADMIN in data["roles"]

    def test_set_principal_permission_new_user(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test setting permission for a new principal."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        chat_agent_id = create_chat_agent_for_user(test_client, test_user_token, tenant_id)

        # Create conversation
        create_response = test_client.post(
            ENDPOINT_CONVERSATIONS.format(tenant_id=tenant_id),
            json={"chat_agent_id": chat_agent_id, "name": "Test Conversation", "description": "Test"},
            headers=headers,
        )
        conversation_id = create_response.json()["id"]

        # Add READ permission for another user
        response = test_client.put(
            ENDPOINT_CONVERSATION_PRINCIPALS.format(tenant_id=tenant_id, conversation_id=conversation_id),
            json={"principal_id": "other-user", "principal_type": PRINCIPAL_TYPE_USER, "role": ROLE_READ},
            headers=headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["principal_id"] == "other-user"
        assert ROLE_READ in data["roles"]

    def test_set_principal_permission_update_existing(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test updating permission for an existing principal."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        chat_agent_id = create_chat_agent_for_user(test_client, test_user_token, tenant_id)

        # Create conversation
        create_response = test_client.post(
            ENDPOINT_CONVERSATIONS.format(tenant_id=tenant_id),
            json={"chat_agent_id": chat_agent_id, "name": "Test Conversation", "description": "Test"},
            headers=headers,
        )
        conversation_id = create_response.json()["id"]

        # Add READ permission
        test_client.put(
            ENDPOINT_CONVERSATION_PRINCIPALS.format(tenant_id=tenant_id, conversation_id=conversation_id),
            json={"principal_id": "other-user", "principal_type": PRINCIPAL_TYPE_USER, "role": ROLE_READ},
            headers=headers,
        )

        # Update to WRITE permission
        update_response = test_client.put(
            ENDPOINT_CONVERSATION_PRINCIPALS.format(tenant_id=tenant_id, conversation_id=conversation_id),
            json={"principal_id": "other-user", "principal_type": PRINCIPAL_TYPE_USER, "role": ROLE_WRITE},
            headers=headers,
        )

        assert update_response.status_code == status.HTTP_200_OK
        data = update_response.json()

        assert data["principal_id"] == "other-user"
        assert ROLE_WRITE in data["roles"]

        # Verify only one role exists
        principals_response = test_client.get(
            ENDPOINT_CONVERSATION_PRINCIPALS.format(tenant_id=tenant_id, conversation_id=conversation_id),
            headers=headers,
        )
        principals = principals_response.json()["principals"]
        other_user_principal = next(p for p in principals if p["principal_id"] == "other-user")
        assert len(other_user_principal["roles"]) == 1
        assert ROLE_WRITE in other_user_principal["roles"]

    def test_set_principal_permission_missing_principal_id(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test setting permission with missing principal_id."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        chat_agent_id = create_chat_agent_for_user(test_client, test_user_token, tenant_id)

        # Create conversation
        create_response = test_client.post(
            ENDPOINT_CONVERSATIONS.format(tenant_id=tenant_id),
            json={"chat_agent_id": chat_agent_id, "name": "Test Conversation", "description": "Test"},
            headers=headers,
        )
        conversation_id = create_response.json()["id"]

        # Try to set permission without principal_id
        response = test_client.put(
            ENDPOINT_CONVERSATION_PRINCIPALS.format(tenant_id=tenant_id, conversation_id=conversation_id),
            json={"principal_type": PRINCIPAL_TYPE_USER, "role": ROLE_READ},
            headers=headers,
        )

        assert response.status_code == 422

    def test_set_principal_permission_missing_role(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test setting permission with missing role."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        chat_agent_id = create_chat_agent_for_user(test_client, test_user_token, tenant_id)

        # Create conversation
        create_response = test_client.post(
            ENDPOINT_CONVERSATIONS.format(tenant_id=tenant_id),
            json={"chat_agent_id": chat_agent_id, "name": "Test Conversation", "description": "Test"},
            headers=headers,
        )
        conversation_id = create_response.json()["id"]

        # Try to set permission without role
        response = test_client.put(
            ENDPOINT_CONVERSATION_PRINCIPALS.format(tenant_id=tenant_id, conversation_id=conversation_id),
            json={"principal_id": "other-user", "principal_type": PRINCIPAL_TYPE_USER},
            headers=headers,
        )

        assert response.status_code == 422

    def test_set_principal_permission_invalid_role(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test setting permission with invalid role."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        chat_agent_id = create_chat_agent_for_user(test_client, test_user_token, tenant_id)

        # Create conversation
        create_response = test_client.post(
            ENDPOINT_CONVERSATIONS.format(tenant_id=tenant_id),
            json={"chat_agent_id": chat_agent_id, "name": "Test Conversation", "description": "Test"},
            headers=headers,
        )
        conversation_id = create_response.json()["id"]

        # Try to set permission with invalid role
        response = test_client.put(
            ENDPOINT_CONVERSATION_PRINCIPALS.format(tenant_id=tenant_id, conversation_id=conversation_id),
            json={"principal_id": "other-user", "principal_type": PRINCIPAL_TYPE_USER, "role": "INVALID_ROLE"},
            headers=headers,
        )

        assert response.status_code == 422

    def test_set_principal_permission_invalid_principal_type(
        self, test_client: TestClient, test_user_token: Any
    ) -> None:
        """Test setting permission with invalid principal_type."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        chat_agent_id = create_chat_agent_for_user(test_client, test_user_token, tenant_id)

        # Create conversation
        create_response = test_client.post(
            ENDPOINT_CONVERSATIONS.format(tenant_id=tenant_id),
            json={"chat_agent_id": chat_agent_id, "name": "Test Conversation", "description": "Test"},
            headers=headers,
        )
        conversation_id = create_response.json()["id"]

        # Try to set permission with invalid principal_type
        response = test_client.put(
            ENDPOINT_CONVERSATION_PRINCIPALS.format(tenant_id=tenant_id, conversation_id=conversation_id),
            json={"principal_id": "other-user", "principal_type": "INVALID_TYPE", "role": ROLE_READ},
            headers=headers,
        )

        assert response.status_code == 422

    def test_delete_principal_permission(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test deleting a principal permission."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        chat_agent_id = create_chat_agent_for_user(test_client, test_user_token, tenant_id)

        # Create conversation
        create_response = test_client.post(
            ENDPOINT_CONVERSATIONS.format(tenant_id=tenant_id),
            json={"chat_agent_id": chat_agent_id, "name": "Test Conversation", "description": "Test"},
            headers=headers,
        )
        conversation_id = create_response.json()["id"]

        # Add READ permission
        test_client.put(
            ENDPOINT_CONVERSATION_PRINCIPALS.format(tenant_id=tenant_id, conversation_id=conversation_id),
            json={"principal_id": "other-user", "principal_type": PRINCIPAL_TYPE_USER, "role": ROLE_READ},
            headers=headers,
        )

        # Delete the permission
        delete_response = test_client.request(
            "DELETE",
            ENDPOINT_CONVERSATION_PRINCIPALS.format(tenant_id=tenant_id, conversation_id=conversation_id),
            json={"principal_id": "other-user", "principal_type": PRINCIPAL_TYPE_USER, "role": ROLE_READ},
            headers=headers,
        )

        assert delete_response.status_code == status.HTTP_204_NO_CONTENT

        # Verify permission is deleted
        principals_response = test_client.get(
            ENDPOINT_CONVERSATION_PRINCIPALS.format(tenant_id=tenant_id, conversation_id=conversation_id),
            headers=headers,
        )
        principals = principals_response.json()["principals"]
        other_user_principals = [p for p in principals if p["principal_id"] == "other-user"]
        assert len(other_user_principals) == 0

    def test_delete_principal_permission_not_found(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test deleting a non-existent permission."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        chat_agent_id = create_chat_agent_for_user(test_client, test_user_token, tenant_id)

        # Create conversation
        create_response = test_client.post(
            ENDPOINT_CONVERSATIONS.format(tenant_id=tenant_id),
            json={"chat_agent_id": chat_agent_id, "name": "Test Conversation", "description": "Test"},
            headers=headers,
        )
        conversation_id = create_response.json()["id"]

        # Try to delete non-existent permission
        response = test_client.request(
            "DELETE",
            ENDPOINT_CONVERSATION_PRINCIPALS.format(tenant_id=tenant_id, conversation_id=conversation_id),
            json={"principal_id": "non-existent-user", "principal_type": PRINCIPAL_TYPE_USER, "role": ROLE_READ},
            headers=headers,
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
