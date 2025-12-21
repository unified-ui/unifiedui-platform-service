"""Caching tests for autonomous agents API endpoints."""
from typing import Any
from fastapi import status
from starlette.testclient import TestClient

from aihub.core.database.enums import PermissionActionEnum, PrincipalTypeEnum, TenantPermissionEnum
from tests.conftest import create_auth_headers


# API Endpoints
ENDPOINT_AUTONOMOUS_AGENTS = "/api/v1/tenants/{tenant_id}/autonomous-agents"
ENDPOINT_AUTONOMOUS_AGENT_DETAIL = "/api/v1/tenants/{tenant_id}/autonomous-agents/{autonomous_agent_id}"
ENDPOINT_AUTONOMOUS_AGENT_PRINCIPALS = "/api/v1/tenants/{tenant_id}/autonomous-agents/{autonomous_agent_id}/principals"

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
            "role": TenantPermissionEnum.READER.value
        },
        headers=headers
    )
    assert response.status_code == status.HTTP_200_OK


class TestAutonomousAgentCaching:
    """Test suite for autonomous agent caching behavior."""
    
    def test_autonomous_agents_list_cached_after_permission_grant(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test that list is properly cached/invalidated when permissions are granted."""
        # Create tenant and agent as user1
        user1_token = test_client.create_test_user("user-1", "User One")
        tenant_id = create_tenant_for_user(test_client, user1_token)
        headers1 = create_auth_headers(user1_token, use_cache=False)
        
        agent_data = {"name": "Test Agent", "description": "Test", "config": {}}
        create_response = test_client.post(
            ENDPOINT_AUTONOMOUS_AGENTS.format(tenant_id=tenant_id),
            json=agent_data,
            headers=headers1
        )
        agent_id = create_response.json()["id"]
        
        # Create user2 and add to tenant
        user2_token = test_client.create_test_user("user-2", "User Two")
        user2_id = user2_token.get_id()
        add_user_to_tenant(test_client, user1_token, tenant_id, user2_id)
        headers2 = create_auth_headers(user2_token, use_cache=True)
        
        # User2 lists agents (should be empty, result cached)
        list1 = test_client.get(
            ENDPOINT_AUTONOMOUS_AGENTS.format(tenant_id=tenant_id),
            headers=headers2
        )
        assert list1.status_code == status.HTTP_200_OK
        assert len(list1.json()) == 0
        
        # Grant user2 READ permission (cache should be invalidated)
        test_client.put(
            ENDPOINT_AUTONOMOUS_AGENT_PRINCIPALS.format(tenant_id=tenant_id, autonomous_agent_id=agent_id),
            json={
                "principal_id": user2_id,
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_READ
            },
            headers=headers1
        )
        
        # User2 lists agents again (should now see the agent due to cache invalidation)
        list2 = test_client.get(
            ENDPOINT_AUTONOMOUS_AGENTS.format(tenant_id=tenant_id),
            headers=headers2
        )
        assert list2.status_code == status.HTTP_200_OK
        assert len(list2.json()) == 1
        assert list2.json()[0]["id"] == agent_id
    
    def test_autonomous_agents_list_cached_after_permission_revoke(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test that list is properly cached/invalidated when permissions are revoked."""
        # Create tenant and agent as user1
        user1_token = test_client.create_test_user("user-1", "User One")
        tenant_id = create_tenant_for_user(test_client, user1_token)
        headers1 = create_auth_headers(user1_token, use_cache=False)
        
        agent_data = {"name": "Test Agent", "description": "Test", "config": {}}
        create_response = test_client.post(
            ENDPOINT_AUTONOMOUS_AGENTS.format(tenant_id=tenant_id),
            json=agent_data,
            headers=headers1
        )
        agent_id = create_response.json()["id"]
        
        # Create user2 and add to tenant
        user2_token = test_client.create_test_user("user-2", "User Two")
        user2_id = user2_token.get_id()
        add_user_to_tenant(test_client, user1_token, tenant_id, user2_id)
        headers2 = create_auth_headers(user2_token, use_cache=True)
        
        # Grant user2 READ permission
        test_client.put(
            ENDPOINT_AUTONOMOUS_AGENT_PRINCIPALS.format(tenant_id=tenant_id, autonomous_agent_id=agent_id),
            json={
                "principal_id": user2_id,
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_READ
            },
            headers=headers1
        )
        
        # User2 lists agents (should see the agent, result cached)
        list1 = test_client.get(
            ENDPOINT_AUTONOMOUS_AGENTS.format(tenant_id=tenant_id),
            headers=headers2
        )
        assert list1.status_code == status.HTTP_200_OK
        assert len(list1.json()) == 1
        
        # Revoke user2's permission (cache should be invalidated)
        test_client.request(
            "DELETE",
            ENDPOINT_AUTONOMOUS_AGENT_PRINCIPALS.format(tenant_id=tenant_id, autonomous_agent_id=agent_id),
            json={
                "principal_id": user2_id,
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_READ
            },
            headers=headers1
        )
        
        # User2 lists agents again (should be empty due to cache invalidation)
        list2 = test_client.get(
            ENDPOINT_AUTONOMOUS_AGENTS.format(tenant_id=tenant_id),
            headers=headers2
        )
        assert list2.status_code == status.HTTP_200_OK
        assert len(list2.json()) == 0
    
    def test_autonomous_agents_list_cached_after_multiple_permission_changes(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test cache invalidation with multiple permission changes."""
        # Create tenant and agents as user1
        user1_token = test_client.create_test_user("user-1", "User One")
        tenant_id = create_tenant_for_user(test_client, user1_token)
        headers1 = create_auth_headers(user1_token, use_cache=False)
        
        # Create two agents
        agent1 = test_client.post(
            ENDPOINT_AUTONOMOUS_AGENTS.format(tenant_id=tenant_id),
            json={"name": "Agent 1", "description": "Test", "config": {}},
            headers=headers1
        ).json()
        
        agent2 = test_client.post(
            ENDPOINT_AUTONOMOUS_AGENTS.format(tenant_id=tenant_id),
            json={"name": "Agent 2", "description": "Test", "config": {}},
            headers=headers1
        ).json()
        
        # Create user2 and add to tenant
        user2_token = test_client.create_test_user("user-2", "User Two")
        user2_id = user2_token.get_id()
        add_user_to_tenant(test_client, user1_token, tenant_id, user2_id)
        headers2 = create_auth_headers(user2_token, use_cache=True)
        
        # Initial list (empty, cached)
        list1 = test_client.get(
            ENDPOINT_AUTONOMOUS_AGENTS.format(tenant_id=tenant_id),
            headers=headers2
        )
        assert len(list1.json()) == 0
        
        # Grant access to agent1 (cache invalidated)
        test_client.put(
            ENDPOINT_AUTONOMOUS_AGENT_PRINCIPALS.format(tenant_id=tenant_id, autonomous_agent_id=agent1["id"]),
            json={
                "principal_id": user2_id,
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_READ
            },
            headers=headers1
        )
        
        # List again (should show agent1)
        list2 = test_client.get(
            ENDPOINT_AUTONOMOUS_AGENTS.format(tenant_id=tenant_id),
            headers=headers2
        )
        assert len(list2.json()) == 1
        assert list2.json()[0]["id"] == agent1["id"]
        
        # Grant access to agent2 (cache invalidated)
        test_client.put(
            ENDPOINT_AUTONOMOUS_AGENT_PRINCIPALS.format(tenant_id=tenant_id, autonomous_agent_id=agent2["id"]),
            json={
                "principal_id": user2_id,
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_WRITE
            },
            headers=headers1
        )
        
        # List again (should show both agents)
        list3 = test_client.get(
            ENDPOINT_AUTONOMOUS_AGENTS.format(tenant_id=tenant_id),
            headers=headers2
        )
        assert len(list3.json()) == 2
        
        # Revoke access to agent1 (cache invalidated)
        test_client.request(
            "DELETE",
            ENDPOINT_AUTONOMOUS_AGENT_PRINCIPALS.format(tenant_id=tenant_id, autonomous_agent_id=agent1["id"]),
            json={
                "principal_id": user2_id,
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_READ
            },
            headers=headers1
        )
        
        # List again (should only show agent2)
        list4 = test_client.get(
            ENDPOINT_AUTONOMOUS_AGENTS.format(tenant_id=tenant_id),
            headers=headers2
        )
        assert len(list4.json()) == 1
        assert list4.json()[0]["id"] == agent2["id"]
    
    def test_autonomous_agent_detail_cached_correctly(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test that get detail endpoint caches correctly."""
        # Create tenant and agent as user1
        user1_token = test_client.create_test_user("user-1", "User One")
        tenant_id = create_tenant_for_user(test_client, user1_token)
        headers1 = create_auth_headers(user1_token, use_cache=False)
        
        agent_data = {"name": "Test Agent", "description": "Original description", "config": {}}
        create_response = test_client.post(
            ENDPOINT_AUTONOMOUS_AGENTS.format(tenant_id=tenant_id),
            json=agent_data,
            headers=headers1
        )
        agent_id = create_response.json()["id"]
        
        # Get agent with cache enabled
        headers_cached = create_auth_headers(user1_token, use_cache=True)
        get1 = test_client.get(
            ENDPOINT_AUTONOMOUS_AGENT_DETAIL.format(tenant_id=tenant_id, autonomous_agent_id=agent_id),
            headers=headers_cached
        )
        assert get1.status_code == status.HTTP_200_OK
        assert get1.json()["description"] == "Original description"
        
        # Update the agent (should invalidate cache)
        test_client.patch(
            ENDPOINT_AUTONOMOUS_AGENT_DETAIL.format(tenant_id=tenant_id, autonomous_agent_id=agent_id),
            json={"description": "Updated description"},
            headers=headers1
        )
        
        # Get agent again with cache (should see updated value due to invalidation)
        get2 = test_client.get(
            ENDPOINT_AUTONOMOUS_AGENT_DETAIL.format(tenant_id=tenant_id, autonomous_agent_id=agent_id),
            headers=headers_cached
        )
        assert get2.status_code == status.HTTP_200_OK
        assert get2.json()["description"] == "Updated description"
    
    def test_cache_isolation_between_users(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test that cache is properly isolated between different users."""
        # Create tenant and agent as user1
        user1_token = test_client.create_test_user("user-1", "User One")
        tenant_id = create_tenant_for_user(test_client, user1_token)
        headers1 = create_auth_headers(user1_token, use_cache=True)
        
        agent_data = {"name": "Test Agent", "description": "Test", "config": {}}
        create_response = test_client.post(
            ENDPOINT_AUTONOMOUS_AGENTS.format(tenant_id=tenant_id),
            json=agent_data,
            headers=headers1
        )
        agent_id = create_response.json()["id"]
        
        # Create user2 and add to tenant
        user2_token = test_client.create_test_user("user-2", "User Two")
        user2_id = user2_token.get_id()
        add_user_to_tenant(test_client, user1_token, tenant_id, user2_id)
        headers2 = create_auth_headers(user2_token, use_cache=True)
        
        # User1 lists agents (should see the agent they created)
        list1 = test_client.get(
            ENDPOINT_AUTONOMOUS_AGENTS.format(tenant_id=tenant_id),
            headers=headers1
        )
        assert len(list1.json()) == 1
        
        # User2 lists agents (should be empty - different cache)
        list2 = test_client.get(
            ENDPOINT_AUTONOMOUS_AGENTS.format(tenant_id=tenant_id),
            headers=headers2
        )
        assert len(list2.json()) == 0
        
        # Grant user2 access
        headers1_no_cache = create_auth_headers(user1_token, use_cache=False)
        test_client.put(
            ENDPOINT_AUTONOMOUS_AGENT_PRINCIPALS.format(tenant_id=tenant_id, autonomous_agent_id=agent_id),
            json={
                "principal_id": user2_id,
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_READ
            },
            headers=headers1_no_cache
        )
        
        # User2 lists again (should now see the agent)
        list3 = test_client.get(
            ENDPOINT_AUTONOMOUS_AGENTS.format(tenant_id=tenant_id),
            headers=headers2
        )
        assert len(list3.json()) == 1
        
        # User1 should still see the agent (unchanged)
        list4 = test_client.get(
            ENDPOINT_AUTONOMOUS_AGENTS.format(tenant_id=tenant_id),
            headers=headers1
        )
        assert len(list4.json()) == 1
    
    def test_autonomous_agent_principals_list_cached_correctly(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test that principals list endpoint caches correctly."""
        # Create tenant and agent as user1
        user1_token = test_client.create_test_user("user-1", "User One")
        tenant_id = create_tenant_for_user(test_client, user1_token)
        headers1_no_cache = create_auth_headers(user1_token, use_cache=False)
        headers1_cached = create_auth_headers(user1_token, use_cache=True)
        
        agent_data = {"name": "Test Agent", "description": "Test", "config": {}}
        create_response = test_client.post(
            ENDPOINT_AUTONOMOUS_AGENTS.format(tenant_id=tenant_id),
            json=agent_data,
            headers=headers1_no_cache
        )
        agent_id = create_response.json()["id"]
        
        # List principals with cache (should show creator only)
        list1 = test_client.get(
            ENDPOINT_AUTONOMOUS_AGENT_PRINCIPALS.format(tenant_id=tenant_id, autonomous_agent_id=agent_id),
            headers=headers1_cached
        )
        initial_count = len(list1.json()["principals"])
        
        # Add a new principal (cache should be invalidated)
        test_client.put(
            ENDPOINT_AUTONOMOUS_AGENT_PRINCIPALS.format(tenant_id=tenant_id, autonomous_agent_id=agent_id),
            json={
                "principal_id": "new-user",
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_READ
            },
            headers=headers1_no_cache
        )
        
        # List principals again (should show the new principal due to cache invalidation)
        list2 = test_client.get(
            ENDPOINT_AUTONOMOUS_AGENT_PRINCIPALS.format(tenant_id=tenant_id, autonomous_agent_id=agent_id),
            headers=headers1_cached
        )
        assert len(list2.json()["principals"]) == initial_count + 1
    
    def test_cache_header_controls_caching_behavior(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test that X-Use-Cache header controls caching behavior."""
        # Create tenant and agent
        user1_token = test_client.create_test_user("user-1", "User One")
        tenant_id = create_tenant_for_user(test_client, user1_token)
        headers_no_cache = create_auth_headers(user1_token, use_cache=False)
        headers_cached = create_auth_headers(user1_token, use_cache=True)
        
        agent_data = {"name": "Original Name", "description": "Test", "config": {}}
        create_response = test_client.post(
            ENDPOINT_AUTONOMOUS_AGENTS.format(tenant_id=tenant_id),
            json=agent_data,
            headers=headers_no_cache
        )
        agent_id = create_response.json()["id"]
        
        # Get with cache enabled
        get1 = test_client.get(
            ENDPOINT_AUTONOMOUS_AGENT_DETAIL.format(tenant_id=tenant_id, autonomous_agent_id=agent_id),
            headers=headers_cached
        )
        assert get1.json()["name"] == "Original Name"
        
        # Update the agent
        test_client.patch(
            ENDPOINT_AUTONOMOUS_AGENT_DETAIL.format(tenant_id=tenant_id, autonomous_agent_id=agent_id),
            json={"name": "Updated Name"},
            headers=headers_no_cache
        )
        
        # Get with cache disabled (should bypass cache and show updated value)
        get2 = test_client.get(
            ENDPOINT_AUTONOMOUS_AGENT_DETAIL.format(tenant_id=tenant_id, autonomous_agent_id=agent_id),
            headers=headers_no_cache
        )
        assert get2.json()["name"] == "Updated Name"
        
        # Get with cache enabled (should also show updated value due to invalidation)
        get3 = test_client.get(
            ENDPOINT_AUTONOMOUS_AGENT_DETAIL.format(tenant_id=tenant_id, autonomous_agent_id=agent_id),
            headers=headers_cached
        )
        assert get3.json()["name"] == "Updated Name"
    
    def test_permission_update_invalidates_cache(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test that updating a permission invalidates the affected user's cache."""
        # Create tenant and agent as user1
        user1_token = test_client.create_test_user("user-1", "User One")
        tenant_id = create_tenant_for_user(test_client, user1_token)
        headers1 = create_auth_headers(user1_token, use_cache=False)
        
        agent_data = {"name": "Test Agent", "description": "Test", "config": {}}
        create_response = test_client.post(
            ENDPOINT_AUTONOMOUS_AGENTS.format(tenant_id=tenant_id),
            json=agent_data,
            headers=headers1
        )
        agent_id = create_response.json()["id"]
        
        # Create user2 and add to tenant
        user2_token = test_client.create_test_user("user-2", "User Two")
        user2_id = user2_token.get_id()
        add_user_to_tenant(test_client, user1_token, tenant_id, user2_id)
        headers2 = create_auth_headers(user2_token, use_cache=True)
        
        # Grant user2 READ permission
        test_client.put(
            ENDPOINT_AUTONOMOUS_AGENT_PRINCIPALS.format(tenant_id=tenant_id, autonomous_agent_id=agent_id),
            json={
                "principal_id": user2_id,
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_READ
            },
            headers=headers1
        )
        
        # User2 lists (should see the agent)
        list1 = test_client.get(
            ENDPOINT_AUTONOMOUS_AGENTS.format(tenant_id=tenant_id),
            headers=headers2
        )
        assert len(list1.json()) == 1
        
        # Update user2's permission to WRITE (cache should be invalidated)
        test_client.put(
            ENDPOINT_AUTONOMOUS_AGENT_PRINCIPALS.format(tenant_id=tenant_id, autonomous_agent_id=agent_id),
            json={
                "principal_id": user2_id,
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_WRITE
            },
            headers=headers1
        )
        
        # User2 should still see the agent (and now with WRITE permission)
        list2 = test_client.get(
            ENDPOINT_AUTONOMOUS_AGENTS.format(tenant_id=tenant_id),
            headers=headers2
        )
        assert len(list2.json()) == 1
        
        # Verify user2 can now update (WRITE permission)
        update_response = test_client.patch(
            ENDPOINT_AUTONOMOUS_AGENT_DETAIL.format(tenant_id=tenant_id, autonomous_agent_id=agent_id),
            json={"name": "Updated by User2"},
            headers=headers2
        )
        assert update_response.status_code == status.HTTP_200_OK
