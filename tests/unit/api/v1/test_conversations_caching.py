"""Tests for conversations caching."""
from typing import Any
from fastapi import status
from starlette.testclient import TestClient

from unifiedui.core.database.enums import PermissionActionEnum, PrincipalTypeEnum, TenantRolesEnum
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


class TestConversationCaching:
    """Test suite for conversation caching behavior."""
    
    def test_conversations_list_cached_after_permission_grant(self, test_client: TestClient, fake_redis_client: Any) -> None:
        """Test that conversation list is correctly cached after permission grant."""
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
        headers2 = create_auth_headers(user2_token, use_cache=True)
        
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
        
        # User2 lists conversations (should see the conversation)
        list1 = test_client.get(
            ENDPOINT_CONVERSATIONS.format(tenant_id=tenant_id),
            headers=headers2
        )
        assert len(list1.json()) == 1
        
        # User2 lists again (should use cache)
        list2 = test_client.get(
            ENDPOINT_CONVERSATIONS.format(tenant_id=tenant_id),
            headers=headers2
        )
        assert len(list2.json()) == 1
    
    def test_conversations_list_cached_after_permission_revoke(self, test_client: TestClient, fake_redis_client: Any) -> None:
        """Test that conversation list is correctly updated after permission revoke."""
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
        headers2 = create_auth_headers(user2_token, use_cache=True)
        
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
        
        # User2 lists conversations
        list1 = test_client.get(
            ENDPOINT_CONVERSATIONS.format(tenant_id=tenant_id),
            headers=headers2
        )
        assert len(list1.json()) == 1
        
        # Revoke permission
        test_client.request(
            "DELETE",
            ENDPOINT_CONVERSATION_PRINCIPALS.format(tenant_id=tenant_id, conversation_id=conversation_id),
            json={
                "principal_id": user2_id,
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_READ
            },
            headers=headers1
        )
        
        # User2 lists conversations (should see no conversations - cache invalidated)
        list2 = test_client.get(
            ENDPOINT_CONVERSATIONS.format(tenant_id=tenant_id),
            headers=headers2
        )
        assert len(list2.json()) == 0
    
    def test_conversations_list_cached_after_multiple_permission_changes(self, test_client: TestClient, fake_redis_client: Any) -> None:
        """Test that conversation list is correctly updated after multiple permission changes."""
        # User1 creates tenant and 2 conversations
        user1_token = test_client.create_test_user("user-1", "User One")
        headers1 = create_auth_headers(user1_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, user1_token)
        
        conv1_response = test_client.post(
            ENDPOINT_CONVERSATIONS.format(tenant_id=tenant_id),
            json={"name": "Conversation 1", "description": "Test"},
            headers=headers1
        )
        conv1_id = conv1_response.json()["id"]
        
        conv2_response = test_client.post(
            ENDPOINT_CONVERSATIONS.format(tenant_id=tenant_id),
            json={"name": "Conversation 2", "description": "Test"},
            headers=headers1
        )
        conv2_id = conv2_response.json()["id"]
        
        # Create user2 and add to tenant
        user2_token = test_client.create_test_user("user-2", "User Two")
        user2_id = user2_token.get_id()
        add_user_to_tenant(test_client, user1_token, tenant_id, user2_id)
        headers2 = create_auth_headers(user2_token, use_cache=True)
        
        # Initially user2 has no conversations
        list1 = test_client.get(
            ENDPOINT_CONVERSATIONS.format(tenant_id=tenant_id),
            headers=headers2
        )
        assert len(list1.json()) == 0
        
        # Grant access to conversation 1
        test_client.put(
            ENDPOINT_CONVERSATION_PRINCIPALS.format(tenant_id=tenant_id, conversation_id=conv1_id),
            json={
                "principal_id": user2_id,
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_READ
            },
            headers=headers1
        )
        
        # User2 should see 1 conversation
        list2 = test_client.get(
            ENDPOINT_CONVERSATIONS.format(tenant_id=tenant_id),
            headers=headers2
        )
        assert len(list2.json()) == 1
        
        # Grant access to conversation 2
        test_client.put(
            ENDPOINT_CONVERSATION_PRINCIPALS.format(tenant_id=tenant_id, conversation_id=conv2_id),
            json={
                "principal_id": user2_id,
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_READ
            },
            headers=headers1
        )
        
        # User2 should see 2 conversations
        list3 = test_client.get(
            ENDPOINT_CONVERSATIONS.format(tenant_id=tenant_id),
            headers=headers2
        )
        assert len(list3.json()) == 2
        
        # Revoke access to conversation 1
        test_client.request(
            "DELETE",
            ENDPOINT_CONVERSATION_PRINCIPALS.format(tenant_id=tenant_id, conversation_id=conv1_id),
            json={
                "principal_id": user2_id,
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_READ
            },
            headers=headers1
        )
        
        # User2 should see 1 conversation again
        list4 = test_client.get(
            ENDPOINT_CONVERSATIONS.format(tenant_id=tenant_id),
            headers=headers2
        )
        assert len(list4.json()) == 1
        assert list4.json()[0]["name"] == "Conversation 2"
    
    def test_conversation_detail_cached_correctly(self, test_client: TestClient, fake_redis_client: Any) -> None:
        """Test that conversation detail is correctly cached."""
        # User1 creates tenant and conversation
        user1_token = test_client.create_test_user("user-1", "User One")
        headers1 = create_auth_headers(user1_token, use_cache=True)
        tenant_id = create_tenant_for_user(test_client, user1_token)
        
        conversation_data = {"name": "Test Conversation", "description": "Test"}
        create_response = test_client.post(
            ENDPOINT_CONVERSATIONS.format(tenant_id=tenant_id),
            json=conversation_data,
            headers=headers1
        )
        conversation_id = create_response.json()["id"]
        
        # First GET (cache miss)
        get1 = test_client.get(
            ENDPOINT_CONVERSATION_DETAIL.format(tenant_id=tenant_id, conversation_id=conversation_id),
            headers=headers1
        )
        assert get1.status_code == status.HTTP_200_OK
        
        # Second GET (cache hit)
        get2 = test_client.get(
            ENDPOINT_CONVERSATION_DETAIL.format(tenant_id=tenant_id, conversation_id=conversation_id),
            headers=headers1
        )
        assert get2.status_code == status.HTTP_200_OK
        assert get1.json() == get2.json()
    
    def test_cache_isolation_between_users(self, test_client: TestClient, fake_redis_client: Any) -> None:
        """Test that cache is isolated between different users."""
        # User1 creates tenant and conversation
        user1_token = test_client.create_test_user("user-1", "User One")
        headers1 = create_auth_headers(user1_token, use_cache=True)
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
        headers2 = create_auth_headers(user2_token, use_cache=True)
        
        # User1 sees the conversation
        list1 = test_client.get(
            ENDPOINT_CONVERSATIONS.format(tenant_id=tenant_id),
            headers=headers1
        )
        assert len(list1.json()) == 1
        
        # User2 does not see the conversation (no permission)
        list2 = test_client.get(
            ENDPOINT_CONVERSATIONS.format(tenant_id=tenant_id),
            headers=headers2
        )
        assert len(list2.json()) == 0
        
        # Grant permission to user2
        test_client.put(
            ENDPOINT_CONVERSATION_PRINCIPALS.format(tenant_id=tenant_id, conversation_id=conversation_id),
            json={
                "principal_id": user2_id,
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_READ
            },
            headers=headers1
        )
        
        # User2 now sees the conversation
        list3 = test_client.get(
            ENDPOINT_CONVERSATIONS.format(tenant_id=tenant_id),
            headers=headers2
        )
        assert len(list3.json()) == 1
    
    def test_conversation_principals_list_cached_correctly(self, test_client: TestClient, fake_redis_client: Any) -> None:
        """Test that conversation principals list is correctly cached."""
        # User1 creates tenant and conversation
        user1_token = test_client.create_test_user("user-1", "User One")
        headers1 = create_auth_headers(user1_token, use_cache=True)
        tenant_id = create_tenant_for_user(test_client, user1_token)
        
        conversation_data = {"name": "Test Conversation", "description": "Test"}
        create_response = test_client.post(
            ENDPOINT_CONVERSATIONS.format(tenant_id=tenant_id),
            json=conversation_data,
            headers=headers1
        )
        conversation_id = create_response.json()["id"]
        
        # First GET principals (cache miss)
        get1 = test_client.get(
            ENDPOINT_CONVERSATION_PRINCIPALS.format(tenant_id=tenant_id, conversation_id=conversation_id),
            headers=headers1
        )
        assert get1.status_code == status.HTTP_200_OK
        assert len(get1.json()["principals"]) == 1
        
        # Second GET principals (cache hit)
        get2 = test_client.get(
            ENDPOINT_CONVERSATION_PRINCIPALS.format(tenant_id=tenant_id, conversation_id=conversation_id),
            headers=headers1
        )
        assert get2.status_code == status.HTTP_200_OK
        assert get1.json() == get2.json()
    
    def test_cache_header_controls_caching_behavior(self, test_client: TestClient, fake_redis_client: Any) -> None:
        """Test that X-Use-Cache header correctly controls caching."""
        # User1 creates tenant and conversation
        user1_token = test_client.create_test_user("user-1", "User One")
        tenant_id = create_tenant_for_user(test_client, user1_token)
        
        conversation_data = {"name": "Test Conversation", "description": "Test"}
        create_response = test_client.post(
            ENDPOINT_CONVERSATIONS.format(tenant_id=tenant_id),
            json=conversation_data,
            headers=create_auth_headers(user1_token, use_cache=False)
        )
        conversation_id = create_response.json()["id"]
        
        # Request without cache
        headers_no_cache = create_auth_headers(user1_token, use_cache=False)
        get1 = test_client.get(
            ENDPOINT_CONVERSATION_DETAIL.format(tenant_id=tenant_id, conversation_id=conversation_id),
            headers=headers_no_cache
        )
        assert get1.status_code == status.HTTP_200_OK
        
        # Request with cache
        headers_with_cache = create_auth_headers(user1_token, use_cache=True)
        get2 = test_client.get(
            ENDPOINT_CONVERSATION_DETAIL.format(tenant_id=tenant_id, conversation_id=conversation_id),
            headers=headers_with_cache
        )
        assert get2.status_code == status.HTTP_200_OK
    
    def test_permission_update_invalidates_cache(self, test_client: TestClient, fake_redis_client: Any) -> None:
        """Test that updating permissions invalidates user cache."""
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
        headers2 = create_auth_headers(user2_token, use_cache=True)
        
        # Grant user2 READ permission
        test_client.put(
            ENDPOINT_CONVERSATION_PRINCIPALS.format(tenant_id=tenant_id, conversation_id=conversation_id),
            json={
                "principal_id": user2_id,
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_READ
            },
            headers=headers1
        )
        
        # User2 lists (should see the conversation)
        list1 = test_client.get(
            ENDPOINT_CONVERSATIONS.format(tenant_id=tenant_id),
            headers=headers2
        )
        assert len(list1.json()) == 1
        
        # Update user2's permission to WRITE (cache should be invalidated)
        test_client.put(
            ENDPOINT_CONVERSATION_PRINCIPALS.format(tenant_id=tenant_id, conversation_id=conversation_id),
            json={
                "principal_id": user2_id,
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_WRITE
            },
            headers=headers1
        )
        
        # User2 should still see the conversation (and now with WRITE permission)
        list2 = test_client.get(
            ENDPOINT_CONVERSATIONS.format(tenant_id=tenant_id),
            headers=headers2
        )
        assert len(list2.json()) == 1
        
        # Verify user2 can now update (WRITE permission)
        update_response = test_client.patch(
            ENDPOINT_CONVERSATION_DETAIL.format(tenant_id=tenant_id, conversation_id=conversation_id),
            json={"name": "Updated by User2"},
            headers=headers2
        )
        assert update_response.status_code == status.HTTP_200_OK
