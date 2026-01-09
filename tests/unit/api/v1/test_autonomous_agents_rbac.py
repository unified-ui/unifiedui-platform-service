"""RBAC tests for autonomous agents API endpoints."""
from typing import Any
from fastapi import status
from starlette.testclient import TestClient

from unifiedui.core.database.enums import PermissionActionEnum, PrincipalTypeEnum, TenantRolesEnum
from tests.conftest import create_auth_headers


# API Endpoints
ENDPOINT_AUTONOMOUS_AGENTS = "/api/v1/platform-service/tenants/{tenant_id}/autonomous-agents"
ENDPOINT_AUTONOMOUS_AGENT_DETAIL = "/api/v1/platform-service/tenants/{tenant_id}/autonomous-agents/{autonomous_agent_id}"
ENDPOINT_AUTONOMOUS_AGENT_PRINCIPALS = "/api/v1/platform-service/tenants/{tenant_id}/autonomous-agents/{autonomous_agent_id}/principals"

# Roles
ROLE_READ = PermissionActionEnum.READ.value
ROLE_WRITE = PermissionActionEnum.WRITE.value
ROLE_ADMIN = PermissionActionEnum.ADMIN.value

# Principal Types
PRINCIPAL_TYPE_USER = PrincipalTypeEnum.IDENTITY_USER.value

# Agent Types and Config
AGENT_TYPE_N8N = "N8N"
VALID_N8N_CONFIG = {
    "workflow_endpoint": "http://localhost:5678/workflow/test-workflow-id",
    "api_api_key_credential_id": "test-credential-id"
}


def create_tenant_for_user(test_client: TestClient, user_token: Any, tenant_name: str = "Test Tenant") -> str:
    """Helper function to create a tenant and return its ID."""
    headers = create_auth_headers(user_token, use_cache=False)
    response = test_client.post(
        "/api/v1/platform-service/tenants",
        json={"name": tenant_name, "description": f"Tenant for {user_token.get_id()}"},
        headers=headers
    )
    assert response.status_code == status.HTTP_201_CREATED
    return response.json()["id"]


def add_user_to_tenant(test_client: TestClient, creator_token: Any, tenant_id: str, user_id: str) -> None:
    """Helper function to add a user to a tenant."""
    headers = create_auth_headers(creator_token, use_cache=False)
    response = test_client.put(
        f"/api/v1/platform-service/tenants/{tenant_id}/principals",
        json={
            "principal_id": user_id,
            "principal_type": PRINCIPAL_TYPE_USER,
            "role": TenantRolesEnum.READER.value
        },
        headers=headers
    )
    assert response.status_code == status.HTTP_200_OK


class TestAutonomousAgentRBAC:
    """Test suite for autonomous agent role-based access control."""
    
    def test_creator_has_admin_permissions(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test that the creator automatically gets ADMIN permissions."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        # Create autonomous agent
        agent_data = {"name": "Test Agent", "description": "Test", "type": AGENT_TYPE_N8N, "config": VALID_N8N_CONFIG}
        create_response = test_client.post(
            ENDPOINT_AUTONOMOUS_AGENTS.format(tenant_id=tenant_id),
            json=agent_data,
            headers=headers
        )
        agent_id = create_response.json()["id"]
        
        # Check principals
        principals_response = test_client.get(
            ENDPOINT_AUTONOMOUS_AGENT_PRINCIPALS.format(tenant_id=tenant_id, autonomous_agent_id=agent_id),
            headers=headers
        )
        
        assert principals_response.status_code == status.HTTP_200_OK
        data = principals_response.json()
        
        creator_principal = next(
            (p for p in data["principals"] if p["principal_id"] == test_user_token.get_id()),
            None
        )
        
        assert creator_principal is not None
        assert ROLE_ADMIN in creator_principal["roles"]
    
    def test_read_permission_allows_get(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test that READ permission allows getting an autonomous agent."""
        # Create tenant and agent as user1
        user1_token = test_client.create_test_user("user-1", "User One")
        tenant_id = create_tenant_for_user(test_client, user1_token)
        headers1 = create_auth_headers(user1_token, use_cache=False)
        
        agent_data = {"name": "Test Agent", "description": "Test", "type": AGENT_TYPE_N8N, "config": VALID_N8N_CONFIG}
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
        headers2 = create_auth_headers(user2_token, use_cache=False)
        
        # Grant READ permission to user2
        test_client.put(
            ENDPOINT_AUTONOMOUS_AGENT_PRINCIPALS.format(tenant_id=tenant_id, autonomous_agent_id=agent_id),
            json={
                "principal_id": user2_id,
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_READ
            },
            headers=headers1
        )
        
        # User2 should be able to get the agent
        get_response = test_client.get(
            ENDPOINT_AUTONOMOUS_AGENT_DETAIL.format(tenant_id=tenant_id, autonomous_agent_id=agent_id),
            headers=headers2
        )
        
        assert get_response.status_code == status.HTTP_200_OK
    
    def test_read_permission_denies_update(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test that READ permission denies updating an autonomous agent."""
        # Create tenant and agent as user1
        user1_token = test_client.create_test_user("user-1", "User One")
        tenant_id = create_tenant_for_user(test_client, user1_token)
        headers1 = create_auth_headers(user1_token, use_cache=False)
        
        agent_data = {"name": "Test Agent", "description": "Test", "type": AGENT_TYPE_N8N, "config": VALID_N8N_CONFIG}
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
        headers2 = create_auth_headers(user2_token, use_cache=False)
        
        # Grant READ permission to user2
        test_client.put(
            ENDPOINT_AUTONOMOUS_AGENT_PRINCIPALS.format(tenant_id=tenant_id, autonomous_agent_id=agent_id),
            json={
                "principal_id": user2_id,
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_READ
            },
            headers=headers1
        )
        
        # User2 should NOT be able to update the agent
        update_response = test_client.patch(
            ENDPOINT_AUTONOMOUS_AGENT_DETAIL.format(tenant_id=tenant_id, autonomous_agent_id=agent_id),
            json={"name": "Updated Name"},
            headers=headers2
        )
        
        assert update_response.status_code == status.HTTP_403_FORBIDDEN
    
    def test_read_permission_denies_delete(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test that READ permission denies deleting an autonomous agent."""
        # Create tenant and agent as user1
        user1_token = test_client.create_test_user("user-1", "User One")
        tenant_id = create_tenant_for_user(test_client, user1_token)
        headers1 = create_auth_headers(user1_token, use_cache=False)
        
        agent_data = {"name": "Test Agent", "description": "Test", "type": AGENT_TYPE_N8N, "config": VALID_N8N_CONFIG}
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
        headers2 = create_auth_headers(user2_token, use_cache=False)
        
        # Grant READ permission to user2
        test_client.put(
            ENDPOINT_AUTONOMOUS_AGENT_PRINCIPALS.format(tenant_id=tenant_id, autonomous_agent_id=agent_id),
            json={
                "principal_id": user2_id,
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_READ
            },
            headers=headers1
        )
        
        # User2 should NOT be able to delete the agent
        delete_response = test_client.request(
            "DELETE",
            ENDPOINT_AUTONOMOUS_AGENT_DETAIL.format(tenant_id=tenant_id, autonomous_agent_id=agent_id),
            headers=headers2
        )
        
        assert delete_response.status_code == status.HTTP_403_FORBIDDEN
    
    def test_read_permission_denies_permission_management(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test that READ permission denies managing permissions."""
        # Create tenant and agent as user1
        user1_token = test_client.create_test_user("user-1", "User One")
        tenant_id = create_tenant_for_user(test_client, user1_token)
        headers1 = create_auth_headers(user1_token, use_cache=False)
        
        agent_data = {"name": "Test Agent", "description": "Test", "type": AGENT_TYPE_N8N, "config": VALID_N8N_CONFIG}
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
        headers2 = create_auth_headers(user2_token, use_cache=False)
        
        # Grant READ permission to user2
        test_client.put(
            ENDPOINT_AUTONOMOUS_AGENT_PRINCIPALS.format(tenant_id=tenant_id, autonomous_agent_id=agent_id),
            json={
                "principal_id": user2_id,
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_READ
            },
            headers=headers1
        )
        
        # User2 should NOT be able to grant permissions
        grant_response = test_client.put(
            ENDPOINT_AUTONOMOUS_AGENT_PRINCIPALS.format(tenant_id=tenant_id, autonomous_agent_id=agent_id),
            json={
                "principal_id": "other-user",
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_READ
            },
            headers=headers2
        )
        
        assert grant_response.status_code == status.HTTP_403_FORBIDDEN
    
    def test_write_permission_allows_update(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test that WRITE permission allows updating an autonomous agent."""
        # Create tenant and agent as user1
        user1_token = test_client.create_test_user("user-1", "User One")
        tenant_id = create_tenant_for_user(test_client, user1_token)
        headers1 = create_auth_headers(user1_token, use_cache=False)
        
        agent_data = {"name": "Test Agent", "description": "Test", "type": AGENT_TYPE_N8N, "config": VALID_N8N_CONFIG}
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
        headers2 = create_auth_headers(user2_token, use_cache=False)
        
        # Grant WRITE permission to user2
        test_client.put(
            ENDPOINT_AUTONOMOUS_AGENT_PRINCIPALS.format(tenant_id=tenant_id, autonomous_agent_id=agent_id),
            json={
                "principal_id": user2_id,
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_WRITE
            },
            headers=headers1
        )
        
        # User2 should be able to update the agent
        update_response = test_client.patch(
            ENDPOINT_AUTONOMOUS_AGENT_DETAIL.format(tenant_id=tenant_id, autonomous_agent_id=agent_id),
            json={"name": "Updated by User2"},
            headers=headers2
        )
        
        assert update_response.status_code == status.HTTP_200_OK
        assert update_response.json()["name"] == "Updated by User2"
    
    def test_write_permission_denies_delete(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test that WRITE permission denies deleting an autonomous agent."""
        # Create tenant and agent as user1
        user1_token = test_client.create_test_user("user-1", "User One")
        tenant_id = create_tenant_for_user(test_client, user1_token)
        headers1 = create_auth_headers(user1_token, use_cache=False)
        
        agent_data = {"name": "Test Agent", "description": "Test", "type": AGENT_TYPE_N8N, "config": VALID_N8N_CONFIG}
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
        headers2 = create_auth_headers(user2_token, use_cache=False)
        
        # Grant WRITE permission to user2
        test_client.put(
            ENDPOINT_AUTONOMOUS_AGENT_PRINCIPALS.format(tenant_id=tenant_id, autonomous_agent_id=agent_id),
            json={
                "principal_id": user2_id,
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_WRITE
            },
            headers=headers1
        )
        
        # User2 should NOT be able to delete the agent
        delete_response = test_client.request(
            "DELETE",
            ENDPOINT_AUTONOMOUS_AGENT_DETAIL.format(tenant_id=tenant_id, autonomous_agent_id=agent_id),
            headers=headers2
        )
        
        assert delete_response.status_code == status.HTTP_403_FORBIDDEN
    
    def test_write_permission_denies_permission_management(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test that WRITE permission denies managing permissions."""
        # Create tenant and agent as user1
        user1_token = test_client.create_test_user("user-1", "User One")
        tenant_id = create_tenant_for_user(test_client, user1_token)
        headers1 = create_auth_headers(user1_token, use_cache=False)
        
        agent_data = {"name": "Test Agent", "description": "Test", "type": AGENT_TYPE_N8N, "config": VALID_N8N_CONFIG}
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
        headers2 = create_auth_headers(user2_token, use_cache=False)
        
        # Grant WRITE permission to user2
        test_client.put(
            ENDPOINT_AUTONOMOUS_AGENT_PRINCIPALS.format(tenant_id=tenant_id, autonomous_agent_id=agent_id),
            json={
                "principal_id": user2_id,
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_WRITE
            },
            headers=headers1
        )
        
        # User2 should NOT be able to grant permissions
        grant_response = test_client.put(
            ENDPOINT_AUTONOMOUS_AGENT_PRINCIPALS.format(tenant_id=tenant_id, autonomous_agent_id=agent_id),
            json={
                "principal_id": "other-user",
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_READ
            },
            headers=headers2
        )
        
        assert grant_response.status_code == status.HTTP_403_FORBIDDEN
    
    def test_admin_permission_allows_all_operations(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test that ADMIN permission allows all operations."""
        # Create tenant and agent as user1
        user1_token = test_client.create_test_user("user-1", "User One")
        tenant_id = create_tenant_for_user(test_client, user1_token)
        headers1 = create_auth_headers(user1_token, use_cache=False)
        
        agent_data = {"name": "Test Agent", "description": "Test", "type": AGENT_TYPE_N8N, "config": VALID_N8N_CONFIG}
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
        headers2 = create_auth_headers(user2_token, use_cache=False)
        
        # Grant ADMIN permission to user2
        test_client.put(
            ENDPOINT_AUTONOMOUS_AGENT_PRINCIPALS.format(tenant_id=tenant_id, autonomous_agent_id=agent_id),
            json={
                "principal_id": user2_id,
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_ADMIN
            },
            headers=headers1
        )
        
        # User2 can read
        get_response = test_client.get(
            ENDPOINT_AUTONOMOUS_AGENT_DETAIL.format(tenant_id=tenant_id, autonomous_agent_id=agent_id),
            headers=headers2
        )
        assert get_response.status_code == status.HTTP_200_OK
        
        # User2 can update
        update_response = test_client.patch(
            ENDPOINT_AUTONOMOUS_AGENT_DETAIL.format(tenant_id=tenant_id, autonomous_agent_id=agent_id),
            json={"name": "Updated by Admin"},
            headers=headers2
        )
        assert update_response.status_code == status.HTTP_200_OK
        
        # User2 can manage permissions
        grant_response = test_client.put(
            ENDPOINT_AUTONOMOUS_AGENT_PRINCIPALS.format(tenant_id=tenant_id, autonomous_agent_id=agent_id),
            json={
                "principal_id": "other-user",
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_READ
            },
            headers=headers2
        )
        assert grant_response.status_code == status.HTTP_200_OK
        
        # User2 can delete (tested last as it destroys the resource)
        delete_response = test_client.request(
            "DELETE",
            ENDPOINT_AUTONOMOUS_AGENT_DETAIL.format(tenant_id=tenant_id, autonomous_agent_id=agent_id),
            headers=headers2
        )
        assert delete_response.status_code == status.HTTP_204_NO_CONTENT
    
    def test_user_without_permission_cannot_access_agent(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test that a user without any permission cannot access an autonomous agent."""
        # Create tenant and agent as user1
        user1_token = test_client.create_test_user("user-1", "User One")
        tenant_id = create_tenant_for_user(test_client, user1_token)
        headers1 = create_auth_headers(user1_token, use_cache=False)
        
        agent_data = {"name": "Test Agent", "description": "Test", "type": AGENT_TYPE_N8N, "config": VALID_N8N_CONFIG}
        create_response = test_client.post(
            ENDPOINT_AUTONOMOUS_AGENTS.format(tenant_id=tenant_id),
            json=agent_data,
            headers=headers1
        )
        agent_id = create_response.json()["id"]
        
        # Create user2 and add to tenant (but no agent permissions)
        user2_token = test_client.create_test_user("user-2", "User Two")
        user2_id = user2_token.get_id()
        add_user_to_tenant(test_client, user1_token, tenant_id, user2_id)
        headers2 = create_auth_headers(user2_token, use_cache=False)
        
        # User2 should NOT be able to get the agent
        get_response = test_client.get(
            ENDPOINT_AUTONOMOUS_AGENT_DETAIL.format(tenant_id=tenant_id, autonomous_agent_id=agent_id),
            headers=headers2
        )
        
        assert get_response.status_code == status.HTTP_403_FORBIDDEN
    
    def test_list_shows_only_accessible_agents(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test that list endpoint only shows agents the user has access to."""
        # Create tenant as user1
        user1_token = test_client.create_test_user("user-1", "User One")
        tenant_id = create_tenant_for_user(test_client, user1_token)
        headers1 = create_auth_headers(user1_token, use_cache=False)
        
        # Create 3 agents
        agent1 = test_client.post(
            ENDPOINT_AUTONOMOUS_AGENTS.format(tenant_id=tenant_id),
            json={"name": "Agent 1", "description": "Test", "type": AGENT_TYPE_N8N, "config": VALID_N8N_CONFIG},
            headers=headers1
        ).json()
        
        agent2 = test_client.post(
            ENDPOINT_AUTONOMOUS_AGENTS.format(tenant_id=tenant_id),
            json={"name": "Agent 2", "description": "Test", "type": AGENT_TYPE_N8N, "config": VALID_N8N_CONFIG},
            headers=headers1
        ).json()
        
        agent3 = test_client.post(
            ENDPOINT_AUTONOMOUS_AGENTS.format(tenant_id=tenant_id),
            json={"name": "Agent 3", "description": "Test", "type": AGENT_TYPE_N8N, "config": VALID_N8N_CONFIG},
            headers=headers1
        ).json()
        
        # Create user2 and add to tenant
        user2_token = test_client.create_test_user("user-2", "User Two")
        user2_id = user2_token.get_id()
        add_user_to_tenant(test_client, user1_token, tenant_id, user2_id)
        headers2 = create_auth_headers(user2_token, use_cache=False)
        
        # Grant user2 access to only agent1 and agent2
        test_client.put(
            ENDPOINT_AUTONOMOUS_AGENT_PRINCIPALS.format(tenant_id=tenant_id, autonomous_agent_id=agent1["id"]),
            json={
                "principal_id": user2_id,
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_READ
            },
            headers=headers1
        )
        
        test_client.put(
            ENDPOINT_AUTONOMOUS_AGENT_PRINCIPALS.format(tenant_id=tenant_id, autonomous_agent_id=agent2["id"]),
            json={
                "principal_id": user2_id,
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_WRITE
            },
            headers=headers1
        )
        
        # User2 should only see agent1 and agent2
        list_response = test_client.get(
            ENDPOINT_AUTONOMOUS_AGENTS.format(tenant_id=tenant_id),
            headers=headers2
        )
        
        assert list_response.status_code == status.HTTP_200_OK
        data = list_response.json()
        
        assert len(data) == 2
        agent_ids = [agent["id"] for agent in data]
        assert agent1["id"] in agent_ids
        assert agent2["id"] in agent_ids
        assert agent3["id"] not in agent_ids
