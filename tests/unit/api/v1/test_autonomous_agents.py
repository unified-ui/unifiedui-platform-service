"""Tests for autonomous agents API endpoints."""
from typing import Any
from fastapi import status
from starlette.testclient import TestClient

from aihub.core.database.enums import PermissionActionEnum, PrincipalTypeEnum
from tests.conftest import create_auth_headers


# API Endpoints
ENDPOINT_AUTONOMOUS_AGENTS = "/api/v1/tenants/{tenant_id}/autonomous-agents"
ENDPOINT_AUTONOMOUS_AGENT_DETAIL = "/api/v1/tenants/{tenant_id}/autonomous-agents/{autonomous_agent_id}"
ENDPOINT_AUTONOMOUS_AGENT_PRINCIPALS = "/api/v1/tenants/{tenant_id}/autonomous-agents/{autonomous_agent_id}/principals"
ENDPOINT_PRINCIPAL_DETAIL = "/api/v1/tenants/{tenant_id}/autonomous-agents/{autonomous_agent_id}/principals/{principal_id}"

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


class TestAutonomousAgentRoutes:
    """Test suite for autonomous agent API routes."""
    
    def test_create_autonomous_agent_success(
        self, 
        test_client: TestClient, 
        test_user_token: Any
    ) -> None:
        """Test successful autonomous agent creation."""
        # Create a tenant first
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        # Create autonomous agent
        agent_data = {
            "name": "Test Agent",
            "description": "A test autonomous agent",
            "config": {"model": "gpt-4", "temperature": 0.7}
        }
        
        response = test_client.post(
            ENDPOINT_AUTONOMOUS_AGENTS.format(tenant_id=tenant_id),
            json=agent_data,
            headers=headers
        )
        
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        
        assert data["name"] == agent_data["name"]
        assert data["description"] == agent_data["description"]
        assert data["config"] == agent_data["config"]
        assert "id" in data
        assert data["tenant_id"] == tenant_id
        assert "created_at" in data
        assert "updated_at" in data
        assert data["created_by"] == test_user_token.get_id()
    
    def test_create_autonomous_agent_missing_name(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test autonomous agent creation with missing name."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        response = test_client.post(
            ENDPOINT_AUTONOMOUS_AGENTS.format(tenant_id=tenant_id),
            json={"description": "Test agent"},
            headers=headers
        )
        
        assert response.status_code == 422
    
    def test_create_autonomous_agent_invalid_name_type(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test autonomous agent creation with invalid name type."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        response = test_client.post(
            ENDPOINT_AUTONOMOUS_AGENTS.format(tenant_id=tenant_id),
            json={"name": 123, "description": "Test"},
            headers=headers
        )
        
        assert response.status_code == 422
    
    def test_create_autonomous_agent_empty_name(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test autonomous agent creation with empty name."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        response = test_client.post(
            ENDPOINT_AUTONOMOUS_AGENTS.format(tenant_id=tenant_id),
            json={"name": "", "description": "Test"},
            headers=headers
        )
        
        assert response.status_code == 422
    
    def test_create_autonomous_agent_invalid_description_type(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test autonomous agent creation with invalid description type."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        response = test_client.post(
            ENDPOINT_AUTONOMOUS_AGENTS.format(tenant_id=tenant_id),
            json={"name": "Test Agent", "description": 123},
            headers=headers
        )
        
        assert response.status_code == 422
    
    def test_create_autonomous_agent_empty_body(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test autonomous agent creation with empty JSON body."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        response = test_client.post(
            ENDPOINT_AUTONOMOUS_AGENTS.format(tenant_id=tenant_id),
            json={},
            headers=headers
        )
        
        assert response.status_code == 422
    
    def test_create_autonomous_agent_without_permission(self, test_client: TestClient) -> None:
        """Test that user without AUTONOMOUS_AGENTS_CREATOR permission cannot create agents."""
        # Create user1 with a tenant
        user1_token = test_client.create_test_user("user-1", "User One")
        tenant_id = create_tenant_for_user(test_client, user1_token)
        headers1 = create_auth_headers(user1_token, use_cache=False)
        
        # Create user2 (not a member of the tenant)
        user2_token = test_client.create_test_user("user-2", "User Two")
        headers2 = create_auth_headers(user2_token, use_cache=False)
        
        # Try to create agent as user2 (should fail - no tenant membership)
        response = test_client.post(
            ENDPOINT_AUTONOMOUS_AGENTS.format(tenant_id=tenant_id),
            json={"name": "Unauthorized Agent", "description": "Should fail"},
            headers=headers2
        )
        
        assert response.status_code == status.HTTP_403_FORBIDDEN
    
    def test_get_autonomous_agent_success(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test successful autonomous agent retrieval."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        # Create an autonomous agent
        agent_data = {"name": "Test Agent", "description": "Test description", "config": {}}
        create_response = test_client.post(
            ENDPOINT_AUTONOMOUS_AGENTS.format(tenant_id=tenant_id),
            json=agent_data,
            headers=headers
        )
        agent_id = create_response.json()["id"]
        
        # Retrieve the agent
        response = test_client.get(
            ENDPOINT_AUTONOMOUS_AGENT_DETAIL.format(tenant_id=tenant_id, autonomous_agent_id=agent_id),
            headers=headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["id"] == agent_id
        assert data["name"] == agent_data["name"]
        assert data["description"] == agent_data["description"]
    
    def test_get_autonomous_agent_not_found(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test autonomous agent retrieval with non-existent ID."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        response = test_client.get(
            ENDPOINT_AUTONOMOUS_AGENT_DETAIL.format(tenant_id=tenant_id, autonomous_agent_id=NON_EXISTENT_ID),
            headers=headers
        )
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
    
    def test_list_autonomous_agents_empty(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test listing autonomous agents when none exist."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        response = test_client.get(
            ENDPOINT_AUTONOMOUS_AGENTS.format(tenant_id=tenant_id),
            headers=headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert isinstance(data, list)
        assert len(data) == 0
    
    def test_list_autonomous_agents_with_data(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test listing autonomous agents with existing data."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        # Create multiple autonomous agents
        agent1_data = {"name": "Agent 1", "description": "First agent", "config": {}}
        agent2_data = {"name": "Agent 2", "description": "Second agent", "config": {}}
        
        test_client.post(
            ENDPOINT_AUTONOMOUS_AGENTS.format(tenant_id=tenant_id),
            json=agent1_data,
            headers=headers
        )
        test_client.post(
            ENDPOINT_AUTONOMOUS_AGENTS.format(tenant_id=tenant_id),
            json=agent2_data,
            headers=headers
        )
        
        # List agents
        response = test_client.get(
            ENDPOINT_AUTONOMOUS_AGENTS.format(tenant_id=tenant_id),
            headers=headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert isinstance(data, list)
        assert len(data) == 2
        
        names = [agent["name"] for agent in data]
        assert "Agent 1" in names
        assert "Agent 2" in names
    
    def test_list_autonomous_agents_with_pagination(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test listing autonomous agents with pagination parameters."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        # Create multiple autonomous agents
        for i in range(5):
            test_client.post(
                ENDPOINT_AUTONOMOUS_AGENTS.format(tenant_id=tenant_id),
                json={"name": f"Agent {i}", "description": f"Agent number {i}", "config": {}},
                headers=headers
            )
        
        # Test with limit
        response = test_client.get(
            f"{ENDPOINT_AUTONOMOUS_AGENTS.format(tenant_id=tenant_id)}?limit=3",
            headers=headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 3
        
        # Test with skip
        response = test_client.get(
            f"{ENDPOINT_AUTONOMOUS_AGENTS.format(tenant_id=tenant_id)}?skip=2&limit=2",
            headers=headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 2
    
    def test_list_autonomous_agents_with_name_filter(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test listing autonomous agents with name filter."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        # Create agents with different names
        test_client.post(
            ENDPOINT_AUTONOMOUS_AGENTS.format(tenant_id=tenant_id),
            json={"name": "Production Agent", "description": "Prod", "config": {}},
            headers=headers
        )
        test_client.post(
            ENDPOINT_AUTONOMOUS_AGENTS.format(tenant_id=tenant_id),
            json={"name": "Development Agent", "description": "Dev", "config": {}},
            headers=headers
        )
        test_client.post(
            ENDPOINT_AUTONOMOUS_AGENTS.format(tenant_id=tenant_id),
            json={"name": "Testing Bot", "description": "Test", "config": {}},
            headers=headers
        )
        
        # Filter by "Agent"
        response = test_client.get(
            f"{ENDPOINT_AUTONOMOUS_AGENTS.format(tenant_id=tenant_id)}?name_filter=Agent",
            headers=headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 2
        
        names = [agent["name"] for agent in data]
        assert "Production Agent" in names
        assert "Development Agent" in names
        assert "Testing Bot" not in names
    
    def test_update_autonomous_agent_success(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test successful autonomous agent update."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        # Create an autonomous agent
        agent_data = {"name": "Original Name", "description": "Original description", "config": {"key": "value"}}
        create_response = test_client.post(
            ENDPOINT_AUTONOMOUS_AGENTS.format(tenant_id=tenant_id),
            json=agent_data,
            headers=headers
        )
        agent_id = create_response.json()["id"]
        
        # Update the agent
        update_data = {"name": "Updated Name", "description": "Updated description"}
        update_response = test_client.patch(
            ENDPOINT_AUTONOMOUS_AGENT_DETAIL.format(tenant_id=tenant_id, autonomous_agent_id=agent_id),
            json=update_data,
            headers=headers
        )
        
        assert update_response.status_code == status.HTTP_200_OK
        data = update_response.json()
        
        assert data["name"] == "Updated Name"
        assert data["description"] == "Updated description"
        assert data["config"] == {"key": "value"}  # Config should remain unchanged
    
    def test_update_autonomous_agent_not_found(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test autonomous agent update with non-existent ID."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        response = test_client.patch(
            ENDPOINT_AUTONOMOUS_AGENT_DETAIL.format(tenant_id=tenant_id, autonomous_agent_id=NON_EXISTENT_ID),
            json={"name": "Updated"},
            headers=headers
        )
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
    
    def test_update_autonomous_agent_partial(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test partial autonomous agent update."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        # Create an autonomous agent
        agent_data = {"name": "Original Name", "description": "Original description", "config": {}}
        create_response = test_client.post(
            ENDPOINT_AUTONOMOUS_AGENTS.format(tenant_id=tenant_id),
            json=agent_data,
            headers=headers
        )
        agent_id = create_response.json()["id"]
        
        # Update only the name
        update_response = test_client.patch(
            ENDPOINT_AUTONOMOUS_AGENT_DETAIL.format(tenant_id=tenant_id, autonomous_agent_id=agent_id),
            json={"name": "Only Name Updated"},
            headers=headers
        )
        
        assert update_response.status_code == status.HTTP_200_OK
        data = update_response.json()
        
        assert data["name"] == "Only Name Updated"
        assert data["description"] == agent_data["description"]  # Should remain unchanged
    
    def test_delete_autonomous_agent_success(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test successful autonomous agent deletion."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        # Create an autonomous agent
        agent_data = {"name": "To Delete", "description": "Will be deleted", "config": {}}
        create_response = test_client.post(
            ENDPOINT_AUTONOMOUS_AGENTS.format(tenant_id=tenant_id),
            json=agent_data,
            headers=headers
        )
        agent_id = create_response.json()["id"]
        
        # Delete the agent
        delete_response = test_client.request(
            "DELETE",
            ENDPOINT_AUTONOMOUS_AGENT_DETAIL.format(tenant_id=tenant_id, autonomous_agent_id=agent_id),
            headers=headers
        )
        
        assert delete_response.status_code == status.HTTP_204_NO_CONTENT
        
        # Verify it's deleted
        get_response = test_client.get(
            ENDPOINT_AUTONOMOUS_AGENT_DETAIL.format(tenant_id=tenant_id, autonomous_agent_id=agent_id),
            headers=headers
        )
        
        assert get_response.status_code == status.HTTP_404_NOT_FOUND
    
    def test_delete_autonomous_agent_not_found(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test autonomous agent deletion with non-existent ID."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        response = test_client.request(
            "DELETE",
            ENDPOINT_AUTONOMOUS_AGENT_DETAIL.format(tenant_id=tenant_id, autonomous_agent_id=NON_EXISTENT_ID),
            headers=headers
        )
        
        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestAutonomousAgentPrincipalRoutes:
    """Test suite for autonomous agent principal/permission management routes."""
    
    def test_list_autonomous_agent_principals_creator_only(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test that only creator has permissions initially."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        # Create an autonomous agent
        agent_data = {"name": "Test Agent", "description": "Test", "config": {}}
        create_response = test_client.post(
            ENDPOINT_AUTONOMOUS_AGENTS.format(tenant_id=tenant_id),
            json=agent_data,
            headers=headers
        )
        agent_id = create_response.json()["id"]
        
        # List principals
        response = test_client.get(
            ENDPOINT_AUTONOMOUS_AGENT_PRINCIPALS.format(tenant_id=tenant_id, autonomous_agent_id=agent_id),
            headers=headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert "autonomous_agent_id" in data
        assert "principals" in data
        assert len(data["principals"]) >= 1  # At least the creator
        
        # Check creator has ADMIN permission
        creator_principal = next(
            (p for p in data["principals"] if p["principal_id"] == test_user_token.get_id()),
            None
        )
        assert creator_principal is not None
        assert ROLE_ADMIN in creator_principal["roles"]
    
    def test_get_principal_permissions(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test getting permissions for a specific principal."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        # Create an autonomous agent
        agent_data = {"name": "Test Agent", "description": "Test", "config": {}}
        create_response = test_client.post(
            ENDPOINT_AUTONOMOUS_AGENTS.format(tenant_id=tenant_id),
            json=agent_data,
            headers=headers
        )
        agent_id = create_response.json()["id"]
        
        # Get creator's permissions
        response = test_client.get(
            ENDPOINT_PRINCIPAL_DETAIL.format(
                tenant_id=tenant_id,
                autonomous_agent_id=agent_id,
                principal_id=test_user_token.get_id()
            ),
            headers=headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["principal_id"] == test_user_token.get_id()
        assert data["principal_type"] == PRINCIPAL_TYPE_USER
        assert ROLE_ADMIN in data["roles"]
    
    def test_set_principal_permission_new_user(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test adding a new principal with permission."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        # Create an autonomous agent
        agent_data = {"name": "Test Agent", "description": "Test", "config": {}}
        create_response = test_client.post(
            ENDPOINT_AUTONOMOUS_AGENTS.format(tenant_id=tenant_id),
            json=agent_data,
            headers=headers
        )
        agent_id = create_response.json()["id"]
        
        # Add permission for another user
        permission_data = {
            "principal_id": "other-user",
            "principal_type": PRINCIPAL_TYPE_USER,
            "role": ROLE_READ
        }
        
        response = test_client.put(
            ENDPOINT_AUTONOMOUS_AGENT_PRINCIPALS.format(tenant_id=tenant_id, autonomous_agent_id=agent_id),
            json=permission_data,
            headers=headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["principal_id"] == "other-user"
        assert data["role"] == ROLE_READ
    
    def test_set_principal_permission_update_existing(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test updating an existing principal's permission."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        # Create an autonomous agent
        agent_data = {"name": "Test Agent", "description": "Test", "config": {}}
        create_response = test_client.post(
            ENDPOINT_AUTONOMOUS_AGENTS.format(tenant_id=tenant_id),
            json=agent_data,
            headers=headers
        )
        agent_id = create_response.json()["id"]
        
        # Add READ permission
        test_client.put(
            ENDPOINT_AUTONOMOUS_AGENT_PRINCIPALS.format(tenant_id=tenant_id, autonomous_agent_id=agent_id),
            json={
                "principal_id": "other-user",
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_READ
            },
            headers=headers
        )
        
        # Update to WRITE permission
        update_response = test_client.put(
            ENDPOINT_AUTONOMOUS_AGENT_PRINCIPALS.format(tenant_id=tenant_id, autonomous_agent_id=agent_id),
            json={
                "principal_id": "other-user",
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_WRITE
            },
            headers=headers
        )
        
        assert update_response.status_code == status.HTTP_200_OK
        data = update_response.json()
        
        assert data["principal_id"] == "other-user"
        assert data["role"] == ROLE_WRITE
    
    def test_set_principal_permission_missing_principal_id(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test setting permission with missing principal_id."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        # Create an autonomous agent
        agent_data = {"name": "Test Agent", "description": "Test", "config": {}}
        create_response = test_client.post(
            ENDPOINT_AUTONOMOUS_AGENTS.format(tenant_id=tenant_id),
            json=agent_data,
            headers=headers
        )
        agent_id = create_response.json()["id"]
        
        response = test_client.put(
            ENDPOINT_AUTONOMOUS_AGENT_PRINCIPALS.format(tenant_id=tenant_id, autonomous_agent_id=agent_id),
            json={
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_READ
            },
            headers=headers
        )
        
        assert response.status_code == 422
    
    def test_set_principal_permission_missing_role(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test setting permission with missing role."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        # Create an autonomous agent
        agent_data = {"name": "Test Agent", "description": "Test", "config": {}}
        create_response = test_client.post(
            ENDPOINT_AUTONOMOUS_AGENTS.format(tenant_id=tenant_id),
            json=agent_data,
            headers=headers
        )
        agent_id = create_response.json()["id"]
        
        response = test_client.put(
            ENDPOINT_AUTONOMOUS_AGENT_PRINCIPALS.format(tenant_id=tenant_id, autonomous_agent_id=agent_id),
            json={
                "principal_id": "user-123",
                "principal_type": PRINCIPAL_TYPE_USER
            },
            headers=headers
        )
        
        assert response.status_code == 422
    
    def test_set_principal_permission_invalid_role(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test setting permission with invalid role."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        # Create an autonomous agent
        agent_data = {"name": "Test Agent", "description": "Test", "config": {}}
        create_response = test_client.post(
            ENDPOINT_AUTONOMOUS_AGENTS.format(tenant_id=tenant_id),
            json=agent_data,
            headers=headers
        )
        agent_id = create_response.json()["id"]
        
        response = test_client.put(
            ENDPOINT_AUTONOMOUS_AGENT_PRINCIPALS.format(tenant_id=tenant_id, autonomous_agent_id=agent_id),
            json={
                "principal_id": "user-123",
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": "INVALID_ROLE"
            },
            headers=headers
        )
        
        assert response.status_code == 422
    
    def test_set_principal_permission_invalid_principal_type(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test setting permission with invalid principal type."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        # Create an autonomous agent
        agent_data = {"name": "Test Agent", "description": "Test", "config": {}}
        create_response = test_client.post(
            ENDPOINT_AUTONOMOUS_AGENTS.format(tenant_id=tenant_id),
            json=agent_data,
            headers=headers
        )
        agent_id = create_response.json()["id"]
        
        response = test_client.put(
            ENDPOINT_AUTONOMOUS_AGENT_PRINCIPALS.format(tenant_id=tenant_id, autonomous_agent_id=agent_id),
            json={
                "principal_id": "user-123",
                "principal_type": "INVALID_TYPE",
                "role": ROLE_READ
            },
            headers=headers
        )
        
        assert response.status_code == 422
    
    def test_delete_principal_permission(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test deleting a principal's permission."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        # Create an autonomous agent
        agent_data = {"name": "Test Agent", "description": "Test", "config": {}}
        create_response = test_client.post(
            ENDPOINT_AUTONOMOUS_AGENTS.format(tenant_id=tenant_id),
            json=agent_data,
            headers=headers
        )
        agent_id = create_response.json()["id"]
        
        # Add permission
        test_client.put(
            ENDPOINT_AUTONOMOUS_AGENT_PRINCIPALS.format(tenant_id=tenant_id, autonomous_agent_id=agent_id),
            json={
                "principal_id": "user-to-remove",
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_READ
            },
            headers=headers
        )
        
        # Delete permission
        delete_response = test_client.request(
            "DELETE",
            ENDPOINT_AUTONOMOUS_AGENT_PRINCIPALS.format(tenant_id=tenant_id, autonomous_agent_id=agent_id),
            json={
                "principal_id": "user-to-remove",
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_READ
            },
            headers=headers
        )
        
        assert delete_response.status_code == status.HTTP_204_NO_CONTENT
    
    def test_delete_principal_permission_not_found(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test deleting a non-existent principal permission."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        # Create an autonomous agent
        agent_data = {"name": "Test Agent", "description": "Test", "config": {}}
        create_response = test_client.post(
            ENDPOINT_AUTONOMOUS_AGENTS.format(tenant_id=tenant_id),
            json=agent_data,
            headers=headers
        )
        agent_id = create_response.json()["id"]
        
        # Try to delete non-existent permission
        response = test_client.request(
            "DELETE",
            ENDPOINT_AUTONOMOUS_AGENT_PRINCIPALS.format(tenant_id=tenant_id, autonomous_agent_id=agent_id),
            json={
                "principal_id": "non-existent-user",
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_READ
            },
            headers=headers
        )
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
