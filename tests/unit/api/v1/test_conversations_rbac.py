"""Tests for conversations RBAC (Role-Based Access Control)."""
from typing import Any
from fastapi import status
from starlette.testclient import TestClient

from aihub.core.database.enums import PermissionActionEnum, PrincipalTypeEnum, TenantRolesEnum
from tests.conftest import create_auth_headers


# API Endpoints
ENDPOINT_CONVERSATIONS = "/api/v1/tenants/{tenant_id}/conversations"
ENDPOINT_CONVERSATION_DETAIL = "/api/v1/tenants/{tenant_id}/conversations/{conversation_id}"
ENDPOINT_CONVERSATION_PRINCIPALS = "/api/v1/tenants/{tenant_id}/conversations/{conversation_id}/principals"

# Roles
ROLE_READ = PermissionActionEnum.READ.value
ROLE_WRITE = PermissionActionEnum.WRITE.value
ROLE_ADMIN = PermissionActionEnum.ADMIN.value

# Principal Types
PRINCIPAL_TYPE_USER = PrincipalTypeEnum.IDENTITY_USER.value


def create_tenant_for_user(test_client: TestClient, user_token: Any, tenant_name: str = "Test Tenant") -> str:
    """Helper function to create a tenant and return its ID."""
    headers = create_auth_headers(user_token, use_cache=False)
    response = test_client.post(
        "/api/v1/tenants",
        json={"name": tenant_name, "description": f"Tenant for {user_token.get_id()}"},
        headers=headers
    )
    assert response.status_code == status.HTTP_201_CREATED
    return response.json()["id"]


def add_user_to_tenant(test_client: TestClient, creator_token: Any, tenant_id: str, user_id: str) -> None:
    """Helper function to add a user to a tenant."""
    headers = create_auth_headers(creator_token, use_cache=False)
    response = test_client.put(
        f"/api/v1/tenants/{tenant_id}/principals",
        json={
            "principal_id": user_id,
            "principal_type": PRINCIPAL_TYPE_USER,
            "role": TenantRolesEnum.READER.value
        },
        headers=headers
    )
    assert response.status_code == status.HTTP_200_OK


class TestConversationRBAC:
    """Test suite for conversation role-based access control."""
    
    def test_creator_has_admin_permissions(self, test_client: TestClient) -> None:
        """Test that conversation creator automatically gets ADMIN role."""
        # Create user and tenant
        user1_token = test_client.create_test_user("user-1", "User One")
        headers1 = create_auth_headers(user1_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, user1_token)
        
        # Create conversation
        conversation_data = {"name": "Test Conversation", "description": "Test"}
        create_response = test_client.post(
            ENDPOINT_CONVERSATIONS.format(tenant_id=tenant_id),
            json=conversation_data,
            headers=headers1
        )
        conversation_id = create_response.json()["id"]
        
        # Creator can view
        get_response = test_client.get(
            ENDPOINT_CONVERSATION_DETAIL.format(tenant_id=tenant_id, conversation_id=conversation_id),
            headers=headers1
        )
        assert get_response.status_code == status.HTTP_200_OK
        
        # Creator can update
        update_response = test_client.patch(
            ENDPOINT_CONVERSATION_DETAIL.format(tenant_id=tenant_id, conversation_id=conversation_id),
            json={"name": "Updated"},
            headers=headers1
        )
        assert update_response.status_code == status.HTTP_200_OK
        
        # Creator can delete
        delete_response = test_client.request(
            "DELETE",
            ENDPOINT_CONVERSATION_DETAIL.format(tenant_id=tenant_id, conversation_id=conversation_id),
            headers=headers1
        )
        assert delete_response.status_code == status.HTTP_204_NO_CONTENT
    
    def test_read_permission_allows_get(self, test_client: TestClient) -> None:
        """Test that READ permission allows GET but not modify."""
        # User1 creates tenant and conversation
        user1_token = test_client.create_test_user("user-1", "User One")
        headers1 = create_auth_headers(user1_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, user1_token)
        
        conversation_data = {"name": "Test Conversation", "description": "Test"}
        create_response = test_client.post(
            ENDPOINT_CONVERSATIONS.format(tenant_id=tenant_id),
            json=conversation_data,
            headers=headers1
        )
        conversation_id = create_response.json()["id"]
        
        # Create user2 and add to tenant
        user2_token = test_client.create_test_user("user-2", "User Two")
        user2_id = user2_token.get_id()
        add_user_to_tenant(test_client, user1_token, tenant_id, user2_id)
        headers2 = create_auth_headers(user2_token, use_cache=False)
        
        # Grant READ permission to user2
        test_client.put(
            ENDPOINT_CONVERSATION_PRINCIPALS.format(tenant_id=tenant_id, conversation_id=conversation_id),
            json={
                "principal_id": user2_id,
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_READ
            },
            headers=headers1
        )
        
        # User2 CAN view conversation
        get_response = test_client.get(
            ENDPOINT_CONVERSATION_DETAIL.format(tenant_id=tenant_id, conversation_id=conversation_id),
            headers=headers2
        )
        assert get_response.status_code == status.HTTP_200_OK
    
    def test_read_permission_denies_update(self, test_client: TestClient) -> None:
        """Test that READ permission denies UPDATE."""
        # User1 creates tenant and conversation
        user1_token = test_client.create_test_user("user-1", "User One")
        headers1 = create_auth_headers(user1_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, user1_token)
        
        conversation_data = {"name": "Test Conversation", "description": "Test"}
        create_response = test_client.post(
            ENDPOINT_CONVERSATIONS.format(tenant_id=tenant_id),
            json=conversation_data,
            headers=headers1
        )
        conversation_id = create_response.json()["id"]
        
        # Create user2 and add to tenant
        user2_token = test_client.create_test_user("user-2", "User Two")
        user2_id = user2_token.get_id()
        add_user_to_tenant(test_client, user1_token, tenant_id, user2_id)
        headers2 = create_auth_headers(user2_token, use_cache=False)
        
        # Grant READ permission to user2
        test_client.put(
            ENDPOINT_CONVERSATION_PRINCIPALS.format(tenant_id=tenant_id, conversation_id=conversation_id),
            json={
                "principal_id": user2_id,
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_READ
            },
            headers=headers1
        )
        
        # User2 CANNOT update conversation
        update_response = test_client.patch(
            ENDPOINT_CONVERSATION_DETAIL.format(tenant_id=tenant_id, conversation_id=conversation_id),
            json={"name": "Hacked"},
            headers=headers2
        )
        assert update_response.status_code == status.HTTP_403_FORBIDDEN
    
    def test_read_permission_denies_delete(self, test_client: TestClient) -> None:
        """Test that READ permission denies DELETE."""
        # User1 creates tenant and conversation
        user1_token = test_client.create_test_user("user-1", "User One")
        headers1 = create_auth_headers(user1_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, user1_token)
        
        conversation_data = {"name": "Test Conversation", "description": "Test"}
        create_response = test_client.post(
            ENDPOINT_CONVERSATIONS.format(tenant_id=tenant_id),
            json=conversation_data,
            headers=headers1
        )
        conversation_id = create_response.json()["id"]
        
        # Create user2 and add to tenant
        user2_token = test_client.create_test_user("user-2", "User Two")
        user2_id = user2_token.get_id()
        add_user_to_tenant(test_client, user1_token, tenant_id, user2_id)
        headers2 = create_auth_headers(user2_token, use_cache=False)
        
        # Grant READ permission to user2
        test_client.put(
            ENDPOINT_CONVERSATION_PRINCIPALS.format(tenant_id=tenant_id, conversation_id=conversation_id),
            json={
                "principal_id": user2_id,
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_READ
            },
            headers=headers1
        )
        
        # User2 CANNOT delete conversation
        delete_response = test_client.request(
            "DELETE",
            ENDPOINT_CONVERSATION_DETAIL.format(tenant_id=tenant_id, conversation_id=conversation_id),
            headers=headers2
        )
        assert delete_response.status_code == status.HTTP_403_FORBIDDEN
    
    def test_read_permission_denies_permission_management(self, test_client: TestClient) -> None:
        """Test that READ permission denies permission management."""
        # User1 creates tenant and conversation
        user1_token = test_client.create_test_user("user-1", "User One")
        headers1 = create_auth_headers(user1_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, user1_token)
        
        conversation_data = {"name": "Test Conversation", "description": "Test"}
        create_response = test_client.post(
            ENDPOINT_CONVERSATIONS.format(tenant_id=tenant_id),
            json=conversation_data,
            headers=headers1
        )
        conversation_id = create_response.json()["id"]
        
        # Create user2 and add to tenant
        user2_token = test_client.create_test_user("user-2", "User Two")
        user2_id = user2_token.get_id()
        add_user_to_tenant(test_client, user1_token, tenant_id, user2_id)
        headers2 = create_auth_headers(user2_token, use_cache=False)
        
        # Grant READ permission to user2
        test_client.put(
            ENDPOINT_CONVERSATION_PRINCIPALS.format(tenant_id=tenant_id, conversation_id=conversation_id),
            json={
                "principal_id": user2_id,
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_READ
            },
            headers=headers1
        )
        
        # User2 CANNOT manage permissions
        permission_response = test_client.put(
            ENDPOINT_CONVERSATION_PRINCIPALS.format(tenant_id=tenant_id, conversation_id=conversation_id),
            json={
                "principal_id": "user-3",
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_READ
            },
            headers=headers2
        )
        assert permission_response.status_code == status.HTTP_403_FORBIDDEN
    
    def test_write_permission_allows_update(self, test_client: TestClient) -> None:
        """Test that WRITE permission allows UPDATE."""
        # User1 creates tenant and conversation
        user1_token = test_client.create_test_user("user-1", "User One")
        headers1 = create_auth_headers(user1_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, user1_token)
        
        conversation_data = {"name": "Test Conversation", "description": "Test"}
        create_response = test_client.post(
            ENDPOINT_CONVERSATIONS.format(tenant_id=tenant_id),
            json=conversation_data,
            headers=headers1
        )
        conversation_id = create_response.json()["id"]
        
        # Create user2 and add to tenant
        user2_token = test_client.create_test_user("user-2", "User Two")
        user2_id = user2_token.get_id()
        add_user_to_tenant(test_client, user1_token, tenant_id, user2_id)
        headers2 = create_auth_headers(user2_token, use_cache=False)
        
        # Grant WRITE permission to user2
        test_client.put(
            ENDPOINT_CONVERSATION_PRINCIPALS.format(tenant_id=tenant_id, conversation_id=conversation_id),
            json={
                "principal_id": user2_id,
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_WRITE
            },
            headers=headers1
        )
        
        # User2 CAN update conversation
        update_response = test_client.patch(
            ENDPOINT_CONVERSATION_DETAIL.format(tenant_id=tenant_id, conversation_id=conversation_id),
            json={"name": "Updated by User2"},
            headers=headers2
        )
        assert update_response.status_code == status.HTTP_200_OK
    
    def test_write_permission_denies_delete(self, test_client: TestClient) -> None:
        """Test that WRITE permission denies DELETE."""
        # User1 creates tenant and conversation
        user1_token = test_client.create_test_user("user-1", "User One")
        headers1 = create_auth_headers(user1_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, user1_token)
        
        conversation_data = {"name": "Test Conversation", "description": "Test"}
        create_response = test_client.post(
            ENDPOINT_CONVERSATIONS.format(tenant_id=tenant_id),
            json=conversation_data,
            headers=headers1
        )
        conversation_id = create_response.json()["id"]
        
        # Create user2 and add to tenant
        user2_token = test_client.create_test_user("user-2", "User Two")
        user2_id = user2_token.get_id()
        add_user_to_tenant(test_client, user1_token, tenant_id, user2_id)
        headers2 = create_auth_headers(user2_token, use_cache=False)
        
        # Grant WRITE permission to user2
        test_client.put(
            ENDPOINT_CONVERSATION_PRINCIPALS.format(tenant_id=tenant_id, conversation_id=conversation_id),
            json={
                "principal_id": user2_id,
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_WRITE
            },
            headers=headers1
        )
        
        # User2 should NOT be able to delete the conversation
        delete_response = test_client.request(
            "DELETE",
            ENDPOINT_CONVERSATION_DETAIL.format(tenant_id=tenant_id, conversation_id=conversation_id),
            headers=headers2
        )
        
        assert delete_response.status_code == status.HTTP_403_FORBIDDEN
    
    def test_write_permission_denies_permission_management(self, test_client: TestClient) -> None:
        """Test that WRITE permission denies permission management."""
        # User1 creates tenant and conversation
        user1_token = test_client.create_test_user("user-1", "User One")
        headers1 = create_auth_headers(user1_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, user1_token)
        
        conversation_data = {"name": "Test Conversation", "description": "Test"}
        create_response = test_client.post(
            ENDPOINT_CONVERSATIONS.format(tenant_id=tenant_id),
            json=conversation_data,
            headers=headers1
        )
        conversation_id = create_response.json()["id"]
        
        # Create user2 and add to tenant
        user2_token = test_client.create_test_user("user-2", "User Two")
        user2_id = user2_token.get_id()
        add_user_to_tenant(test_client, user1_token, tenant_id, user2_id)
        headers2 = create_auth_headers(user2_token, use_cache=False)
        
        # Grant WRITE permission to user2
        test_client.put(
            ENDPOINT_CONVERSATION_PRINCIPALS.format(tenant_id=tenant_id, conversation_id=conversation_id),
            json={
                "principal_id": user2_id,
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_WRITE
            },
            headers=headers1
        )
        
        # User2 CANNOT manage permissions
        permission_response = test_client.put(
            ENDPOINT_CONVERSATION_PRINCIPALS.format(tenant_id=tenant_id, conversation_id=conversation_id),
            json={
                "principal_id": "user-3",
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_READ
            },
            headers=headers2
        )
        assert permission_response.status_code == status.HTTP_403_FORBIDDEN
    
    def test_admin_permission_allows_all_operations(self, test_client: TestClient) -> None:
        """Test that ADMIN permission allows all operations."""
        # User1 creates tenant and conversation
        user1_token = test_client.create_test_user("user-1", "User One")
        headers1 = create_auth_headers(user1_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, user1_token)
        
        conversation_data = {"name": "Test Conversation", "description": "Test"}
        create_response = test_client.post(
            ENDPOINT_CONVERSATIONS.format(tenant_id=tenant_id),
            json=conversation_data,
            headers=headers1
        )
        conversation_id = create_response.json()["id"]
        
        # Create user2 and add to tenant
        user2_token = test_client.create_test_user("user-2", "User Two")
        user2_id = user2_token.get_id()
        add_user_to_tenant(test_client, user1_token, tenant_id, user2_id)
        headers2 = create_auth_headers(user2_token, use_cache=False)
        
        # Grant ADMIN permission to user2
        test_client.put(
            ENDPOINT_CONVERSATION_PRINCIPALS.format(tenant_id=tenant_id, conversation_id=conversation_id),
            json={
                "principal_id": user2_id,
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_ADMIN
            },
            headers=headers1
        )
        
        # User2 CAN view
        get_response = test_client.get(
            ENDPOINT_CONVERSATION_DETAIL.format(tenant_id=tenant_id, conversation_id=conversation_id),
            headers=headers2
        )
        assert get_response.status_code == status.HTTP_200_OK
        
        # User2 CAN update
        update_response = test_client.patch(
            ENDPOINT_CONVERSATION_DETAIL.format(tenant_id=tenant_id, conversation_id=conversation_id),
            json={"name": "Updated by User2"},
            headers=headers2
        )
        assert update_response.status_code == status.HTTP_200_OK
        
        # User2 CAN manage permissions
        permission_response = test_client.put(
            ENDPOINT_CONVERSATION_PRINCIPALS.format(tenant_id=tenant_id, conversation_id=conversation_id),
            json={
                "principal_id": "user-3",
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_READ
            },
            headers=headers2
        )
        assert permission_response.status_code == status.HTTP_200_OK
        
        # User2 CAN delete
        delete_response = test_client.request(
            "DELETE",
            ENDPOINT_CONVERSATION_DETAIL.format(tenant_id=tenant_id, conversation_id=conversation_id),
            headers=headers2
        )
        assert delete_response.status_code == status.HTTP_204_NO_CONTENT
    
    def test_user_without_permission_cannot_access_conversation(self, test_client: TestClient) -> None:
        """Test that users without permission cannot access conversation."""
        # User1 creates tenant and conversation
        user1_token = test_client.create_test_user("user-1", "User One")
        headers1 = create_auth_headers(user1_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, user1_token)
        
        conversation_data = {"name": "Private Conversation", "description": "Test"}
        create_response = test_client.post(
            ENDPOINT_CONVERSATIONS.format(tenant_id=tenant_id),
            json=conversation_data,
            headers=headers1
        )
        conversation_id = create_response.json()["id"]
        
        # Create user2 and add to tenant (but no conversation permissions)
        user2_token = test_client.create_test_user("user-2", "User Two")
        user2_id = user2_token.get_id()
        add_user_to_tenant(test_client, user1_token, tenant_id, user2_id)
        headers2 = create_auth_headers(user2_token, use_cache=False)
        
        # User2 CANNOT view conversation
        get_response = test_client.get(
            ENDPOINT_CONVERSATION_DETAIL.format(tenant_id=tenant_id, conversation_id=conversation_id),
            headers=headers2
        )
        assert get_response.status_code == status.HTTP_403_FORBIDDEN
    
    def test_list_shows_only_accessible_conversations(self, test_client: TestClient) -> None:
        """Test that list only shows conversations user has access to."""
        # User1 creates tenant
        user1_token = test_client.create_test_user("user-1", "User One")
        headers1 = create_auth_headers(user1_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, user1_token)
        
        # Create 3 conversations
        conv1_response = test_client.post(
            ENDPOINT_CONVERSATIONS.format(tenant_id=tenant_id),
            json={"name": "Conversation 1", "description": "Test"},
            headers=headers1
        )
        conv1_id = conv1_response.json()["id"]
        
        test_client.post(
            ENDPOINT_CONVERSATIONS.format(tenant_id=tenant_id),
            json={"name": "Conversation 2", "description": "Test"},
            headers=headers1
        )
        
        conv3_response = test_client.post(
            ENDPOINT_CONVERSATIONS.format(tenant_id=tenant_id),
            json={"name": "Conversation 3", "description": "Test"},
            headers=headers1
        )
        conv3_id = conv3_response.json()["id"]
        
        # Create user2 and add to tenant
        user2_token = test_client.create_test_user("user-2", "User Two")
        user2_id = user2_token.get_id()
        add_user_to_tenant(test_client, user1_token, tenant_id, user2_id)
        headers2 = create_auth_headers(user2_token, use_cache=False)
        
        # Grant user2 access to only conversation 1 and 3
        test_client.put(
            ENDPOINT_CONVERSATION_PRINCIPALS.format(tenant_id=tenant_id, conversation_id=conv1_id),
            json={
                "principal_id": user2_id,
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_READ
            },
            headers=headers1
        )
        test_client.put(
            ENDPOINT_CONVERSATION_PRINCIPALS.format(tenant_id=tenant_id, conversation_id=conv3_id),
            json={
                "principal_id": user2_id,
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_READ
            },
            headers=headers1
        )
        
        # User2 should see only 2 conversations
        list_response = test_client.get(
            ENDPOINT_CONVERSATIONS.format(tenant_id=tenant_id),
            headers=headers2
        )
        
        assert list_response.status_code == status.HTTP_200_OK
        conversations = list_response.json()
        assert len(conversations) == 2
        
        conversation_names = [c["name"] for c in conversations]
        assert "Conversation 1" in conversation_names
        assert "Conversation 3" in conversation_names
        assert "Conversation 2" not in conversation_names
