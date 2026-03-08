"""Tests for autonomous agents API endpoints."""

from typing import Any

from fastapi import status
from starlette.testclient import TestClient

from tests.conftest import create_auth_headers
from tests.helpers.tenant import create_tenant_for_user
from unifiedui.core.database.enums import AutonomousAgentTypeEnum, PermissionActionEnum, PrincipalTypeEnum

# API Endpoints
ENDPOINT_AUTONOMOUS_AGENTS = "/api/v1/platform-service/tenants/{tenant_id}/autonomous-agents"
ENDPOINT_AUTONOMOUS_AGENT_DETAIL = (
    "/api/v1/platform-service/tenants/{tenant_id}/autonomous-agents/{autonomous_agent_id}"
)
ENDPOINT_AUTONOMOUS_AGENT_PRINCIPALS = (
    "/api/v1/platform-service/tenants/{tenant_id}/autonomous-agents/{autonomous_agent_id}/principals"
)
ENDPOINT_PRINCIPAL_DETAIL = (
    "/api/v1/platform-service/tenants/{tenant_id}/autonomous-agents/{autonomous_agent_id}/principals/{principal_id}"
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

# Agent Types
AGENT_TYPE_N8N = AutonomousAgentTypeEnum.N8N.value

# Valid N8N Config for tests
VALID_N8N_CONFIG = {
    "api_version": "v1",
    "workflow_endpoint": "http://localhost:5678/workflow/test-workflow-id",
    "api_api_key_credential_id": "test-credential-id",
}

# Endpoint for config
ENDPOINT_AUTONOMOUS_AGENT_CONFIG = (
    "/api/v1/platform-service/tenants/{tenant_id}/autonomous-agents/{autonomous_agent_id}/config"
)

# API Key header name
API_KEY_HEADER = "X-Unified-UI-Autonomous-Agent-API-Key"


class TestAutonomousAgentRoutes:
    """Test suite for autonomous agent API routes."""

    def test_create_autonomous_agent_success(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test successful autonomous agent creation."""
        # Create a tenant first
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        # Create autonomous agent
        agent_data = {
            "name": "Test Agent",
            "description": "A test autonomous agent",
            "type": AGENT_TYPE_N8N,
            "config": VALID_N8N_CONFIG,
        }

        response = test_client.post(
            ENDPOINT_AUTONOMOUS_AGENTS.format(tenant_id=tenant_id), json=agent_data, headers=headers
        )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()

        assert data["name"] == agent_data["name"]
        assert data["description"] == agent_data["description"]
        assert data["type"] == AGENT_TYPE_N8N
        assert data["config"] == agent_data["config"]
        assert not data["is_active"]
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
            json={"description": "Test agent", "type": AGENT_TYPE_N8N, "config": VALID_N8N_CONFIG},
            headers=headers,
        )

        assert response.status_code == 422

    def test_create_autonomous_agent_invalid_name_type(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test autonomous agent creation with invalid name type."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        response = test_client.post(
            ENDPOINT_AUTONOMOUS_AGENTS.format(tenant_id=tenant_id),
            json={"name": 123, "description": "Test", "type": AGENT_TYPE_N8N, "config": VALID_N8N_CONFIG},
            headers=headers,
        )

        assert response.status_code == 422

    def test_create_autonomous_agent_empty_name(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test autonomous agent creation with empty name."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        response = test_client.post(
            ENDPOINT_AUTONOMOUS_AGENTS.format(tenant_id=tenant_id),
            json={"name": "", "description": "Test", "type": AGENT_TYPE_N8N, "config": VALID_N8N_CONFIG},
            headers=headers,
        )

        assert response.status_code == 422

    def test_create_autonomous_agent_invalid_description_type(
        self, test_client: TestClient, test_user_token: Any
    ) -> None:
        """Test autonomous agent creation with invalid description type."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        response = test_client.post(
            ENDPOINT_AUTONOMOUS_AGENTS.format(tenant_id=tenant_id),
            json={"name": "Test Agent", "description": 123, "type": AGENT_TYPE_N8N, "config": VALID_N8N_CONFIG},
            headers=headers,
        )

        assert response.status_code == 422

    def test_create_autonomous_agent_empty_body(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test autonomous agent creation with empty JSON body."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        response = test_client.post(ENDPOINT_AUTONOMOUS_AGENTS.format(tenant_id=tenant_id), json={}, headers=headers)

        assert response.status_code == 422

    def test_create_autonomous_agent_without_permission(self, test_client: TestClient) -> None:
        """Test that user without AUTONOMOUS_AGENTS_CREATOR permission cannot create agents."""
        # Create user1 with a tenant
        user1_token = test_client.create_test_user("user-1", "User One")
        tenant_id = create_tenant_for_user(test_client, user1_token)
        create_auth_headers(user1_token, use_cache=False)

        # Create user2 (not a member of the tenant)
        user2_token = test_client.create_test_user("user-2", "User Two")
        headers2 = create_auth_headers(user2_token, use_cache=False)

        # Try to create agent as user2 (should fail - no tenant membership)
        response = test_client.post(
            ENDPOINT_AUTONOMOUS_AGENTS.format(tenant_id=tenant_id),
            json={
                "name": "Unauthorized Agent",
                "description": "Should fail",
                "type": AGENT_TYPE_N8N,
                "config": VALID_N8N_CONFIG,
            },
            headers=headers2,
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_get_autonomous_agent_success(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test successful autonomous agent retrieval."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        # Create an autonomous agent
        agent_data = {
            "name": "Test Agent",
            "description": "Test description",
            "type": AGENT_TYPE_N8N,
            "config": VALID_N8N_CONFIG,
        }
        create_response = test_client.post(
            ENDPOINT_AUTONOMOUS_AGENTS.format(tenant_id=tenant_id), json=agent_data, headers=headers
        )
        agent_id = create_response.json()["id"]

        # Retrieve the agent
        response = test_client.get(
            ENDPOINT_AUTONOMOUS_AGENT_DETAIL.format(tenant_id=tenant_id, autonomous_agent_id=agent_id), headers=headers
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["id"] == agent_id
        assert data["name"] == agent_data["name"]
        assert data["description"] == agent_data["description"]
        assert data["type"] == AGENT_TYPE_N8N

    def test_get_autonomous_agent_not_found(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test autonomous agent retrieval with non-existent ID."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        response = test_client.get(
            ENDPOINT_AUTONOMOUS_AGENT_DETAIL.format(tenant_id=tenant_id, autonomous_agent_id=NON_EXISTENT_ID),
            headers=headers,
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_list_autonomous_agents_empty(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test listing autonomous agents when none exist."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        response = test_client.get(ENDPOINT_AUTONOMOUS_AGENTS.format(tenant_id=tenant_id), headers=headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert isinstance(data, list)
        assert len(data) == 0

    def test_list_autonomous_agents_with_data(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test listing autonomous agents with existing data."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        # Create multiple autonomous agents
        agent1_data = {
            "name": "Agent 1",
            "description": "First agent",
            "type": AGENT_TYPE_N8N,
            "config": VALID_N8N_CONFIG,
        }
        agent2_data = {
            "name": "Agent 2",
            "description": "Second agent",
            "type": AGENT_TYPE_N8N,
            "config": VALID_N8N_CONFIG,
        }

        test_client.post(ENDPOINT_AUTONOMOUS_AGENTS.format(tenant_id=tenant_id), json=agent1_data, headers=headers)
        test_client.post(ENDPOINT_AUTONOMOUS_AGENTS.format(tenant_id=tenant_id), json=agent2_data, headers=headers)

        # List agents
        response = test_client.get(ENDPOINT_AUTONOMOUS_AGENTS.format(tenant_id=tenant_id), headers=headers)

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
                json={
                    "name": f"Agent {i}",
                    "description": f"Agent number {i}",
                    "type": AGENT_TYPE_N8N,
                    "config": VALID_N8N_CONFIG,
                },
                headers=headers,
            )

        # Test with limit
        response = test_client.get(f"{ENDPOINT_AUTONOMOUS_AGENTS.format(tenant_id=tenant_id)}?limit=3", headers=headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 3

        # Test with skip
        response = test_client.get(
            f"{ENDPOINT_AUTONOMOUS_AGENTS.format(tenant_id=tenant_id)}?skip=2&limit=2", headers=headers
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
            json={
                "name": "Production Agent",
                "description": "Prod",
                "type": AGENT_TYPE_N8N,
                "config": VALID_N8N_CONFIG,
            },
            headers=headers,
        )
        test_client.post(
            ENDPOINT_AUTONOMOUS_AGENTS.format(tenant_id=tenant_id),
            json={
                "name": "Development Agent",
                "description": "Dev",
                "type": AGENT_TYPE_N8N,
                "config": VALID_N8N_CONFIG,
            },
            headers=headers,
        )
        test_client.post(
            ENDPOINT_AUTONOMOUS_AGENTS.format(tenant_id=tenant_id),
            json={"name": "Testing Bot", "description": "Test", "type": AGENT_TYPE_N8N, "config": VALID_N8N_CONFIG},
            headers=headers,
        )

        # Filter by "Agent"
        response = test_client.get(
            f"{ENDPOINT_AUTONOMOUS_AGENTS.format(tenant_id=tenant_id)}?name=Agent", headers=headers
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 2

        names = [agent["name"] for agent in data]
        assert "Production Agent" in names
        assert "Development Agent" in names
        assert "Testing Bot" not in names

    def test_list_autonomous_agents_with_quick_list_view(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test listing autonomous agents with quick-list view returns only id and name."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        # Create agents
        test_client.post(
            ENDPOINT_AUTONOMOUS_AGENTS.format(tenant_id=tenant_id),
            json={
                "name": "Agent One",
                "description": "First agent",
                "type": AGENT_TYPE_N8N,
                "config": VALID_N8N_CONFIG,
            },
            headers=headers,
        )
        test_client.post(
            ENDPOINT_AUTONOMOUS_AGENTS.format(tenant_id=tenant_id),
            json={
                "name": "Agent Two",
                "description": "Second agent",
                "type": AGENT_TYPE_N8N,
                "config": VALID_N8N_CONFIG,
            },
            headers=headers,
        )

        # Get with quick-list view
        response = test_client.get(
            f"{ENDPOINT_AUTONOMOUS_AGENTS.format(tenant_id=tenant_id)}?view=quick-list", headers=headers
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 2

        # Verify only id and name are returned
        for item in data:
            assert "id" in item
            assert "name" in item
            # These fields should NOT be present in quick-list view
            assert "description" not in item
            assert "config" not in item
            assert "tenant_id" not in item
            assert "created_at" not in item
            assert "updated_at" not in item
            assert "created_by" not in item
            assert "updated_by" not in item
            assert "is_active" not in item

    def test_update_autonomous_agent_success(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test successful autonomous agent update."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        # Create an autonomous agent
        agent_data = {
            "name": "Original Name",
            "description": "Original description",
            "type": AGENT_TYPE_N8N,
            "config": VALID_N8N_CONFIG,
        }
        create_response = test_client.post(
            ENDPOINT_AUTONOMOUS_AGENTS.format(tenant_id=tenant_id), json=agent_data, headers=headers
        )
        agent_id = create_response.json()["id"]

        # Update the agent
        update_data = {"name": "Updated Name", "description": "Updated description"}
        update_response = test_client.patch(
            ENDPOINT_AUTONOMOUS_AGENT_DETAIL.format(tenant_id=tenant_id, autonomous_agent_id=agent_id),
            json=update_data,
            headers=headers,
        )

        assert update_response.status_code == status.HTTP_200_OK
        data = update_response.json()

        assert data["name"] == "Updated Name"
        assert data["description"] == "Updated description"
        assert data["config"] == VALID_N8N_CONFIG  # Config should remain unchanged

    def test_update_autonomous_agent_not_found(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test autonomous agent update with non-existent ID."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        response = test_client.patch(
            ENDPOINT_AUTONOMOUS_AGENT_DETAIL.format(tenant_id=tenant_id, autonomous_agent_id=NON_EXISTENT_ID),
            json={"name": "Updated"},
            headers=headers,
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_update_autonomous_agent_partial(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test partial autonomous agent update."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        # Create an autonomous agent
        agent_data = {
            "name": "Original Name",
            "description": "Original description",
            "type": AGENT_TYPE_N8N,
            "config": VALID_N8N_CONFIG,
        }
        test_client.post(ENDPOINT_AUTONOMOUS_AGENTS.format(tenant_id=tenant_id), json=agent_data, headers=headers)

    def test_update_autonomous_agent_is_active(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test updating autonomous agent is_active status."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        # Create an autonomous agent (default is_active=False)
        agent_data = {"name": "Test Agent", "description": "Test", "type": AGENT_TYPE_N8N, "config": VALID_N8N_CONFIG}
        create_response = test_client.post(
            ENDPOINT_AUTONOMOUS_AGENTS.format(tenant_id=tenant_id), json=agent_data, headers=headers
        )
        agent_id = create_response.json()["id"]
        assert not create_response.json()["is_active"]

        # Update to active
        update_response = test_client.patch(
            ENDPOINT_AUTONOMOUS_AGENT_DETAIL.format(tenant_id=tenant_id, autonomous_agent_id=agent_id),
            json={"is_active": True},
            headers=headers,
        )

        assert update_response.status_code == status.HTTP_200_OK
        assert update_response.json()["is_active"]

        # Update back to inactive
        update_response2 = test_client.patch(
            ENDPOINT_AUTONOMOUS_AGENT_DETAIL.format(tenant_id=tenant_id, autonomous_agent_id=agent_id),
            json={"is_active": False},
            headers=headers,
        )

        assert update_response2.status_code == status.HTTP_200_OK
        assert not update_response2.json()["is_active"]
        agent_id = create_response.json()["id"]

        # Update only the name
        update_response = test_client.patch(
            ENDPOINT_AUTONOMOUS_AGENT_DETAIL.format(tenant_id=tenant_id, autonomous_agent_id=agent_id),
            json={"name": "Only Name Updated"},
            headers=headers,
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
        agent_data = {
            "name": "To Delete",
            "description": "Will be deleted",
            "type": AGENT_TYPE_N8N,
            "config": VALID_N8N_CONFIG,
        }
        create_response = test_client.post(
            ENDPOINT_AUTONOMOUS_AGENTS.format(tenant_id=tenant_id), json=agent_data, headers=headers
        )
        agent_id = create_response.json()["id"]

        # Delete the agent
        delete_response = test_client.request(
            "DELETE",
            ENDPOINT_AUTONOMOUS_AGENT_DETAIL.format(tenant_id=tenant_id, autonomous_agent_id=agent_id),
            headers=headers,
        )

        assert delete_response.status_code == status.HTTP_204_NO_CONTENT

        # Verify it's deleted
        get_response = test_client.get(
            ENDPOINT_AUTONOMOUS_AGENT_DETAIL.format(tenant_id=tenant_id, autonomous_agent_id=agent_id), headers=headers
        )

        assert get_response.status_code == status.HTTP_404_NOT_FOUND

    def test_delete_autonomous_agent_not_found(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test autonomous agent deletion with non-existent ID."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        response = test_client.request(
            "DELETE",
            ENDPOINT_AUTONOMOUS_AGENT_DETAIL.format(tenant_id=tenant_id, autonomous_agent_id=NON_EXISTENT_ID),
            headers=headers,
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestAutonomousAgentPrincipalRoutes:
    """Test suite for autonomous agent principal/permission management routes."""

    def test_list_autonomous_agent_principals_creator_only(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test that only creator has permissions initially."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        # Create an autonomous agent
        agent_data = {"name": "Test Agent", "description": "Test", "type": AGENT_TYPE_N8N, "config": VALID_N8N_CONFIG}
        create_response = test_client.post(
            ENDPOINT_AUTONOMOUS_AGENTS.format(tenant_id=tenant_id), json=agent_data, headers=headers
        )
        agent_id = create_response.json()["id"]

        # List principals
        response = test_client.get(
            ENDPOINT_AUTONOMOUS_AGENT_PRINCIPALS.format(tenant_id=tenant_id, autonomous_agent_id=agent_id),
            headers=headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert "resource_id" in data
        assert "resource_type" in data
        assert data["resource_type"] == "autonomous_agent"
        assert "principals" in data
        assert len(data["principals"]) >= 1  # At least the creator

        # Check creator has ADMIN permission
        creator_principal = next((p for p in data["principals"] if p["principal_id"] == test_user_token.get_id()), None)
        assert creator_principal is not None
        assert ROLE_ADMIN in creator_principal["roles"]

    def test_get_principal_permissions(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test getting permissions for a specific principal."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        # Create an autonomous agent
        agent_data = {"name": "Test Agent", "description": "Test", "type": AGENT_TYPE_N8N, "config": VALID_N8N_CONFIG}
        create_response = test_client.post(
            ENDPOINT_AUTONOMOUS_AGENTS.format(tenant_id=tenant_id), json=agent_data, headers=headers
        )
        agent_id = create_response.json()["id"]

        # Get creator's permissions
        response = test_client.get(
            ENDPOINT_PRINCIPAL_DETAIL.format(
                tenant_id=tenant_id, autonomous_agent_id=agent_id, principal_id=test_user_token.get_id()
            ),
            headers=headers,
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
        agent_data = {"name": "Test Agent", "description": "Test", "type": AGENT_TYPE_N8N, "config": VALID_N8N_CONFIG}
        create_response = test_client.post(
            ENDPOINT_AUTONOMOUS_AGENTS.format(tenant_id=tenant_id), json=agent_data, headers=headers
        )
        agent_id = create_response.json()["id"]

        # Add permission for another user
        permission_data = {"principal_id": "other-user", "principal_type": PRINCIPAL_TYPE_USER, "role": ROLE_READ}

        response = test_client.put(
            ENDPOINT_AUTONOMOUS_AGENT_PRINCIPALS.format(tenant_id=tenant_id, autonomous_agent_id=agent_id),
            json=permission_data,
            headers=headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["principal_id"] == "other-user"
        assert ROLE_READ in data["roles"]

    def test_set_principal_permission_update_existing(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test updating an existing principal's permission."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        # Create an autonomous agent
        agent_data = {"name": "Test Agent", "description": "Test", "type": AGENT_TYPE_N8N, "config": VALID_N8N_CONFIG}
        create_response = test_client.post(
            ENDPOINT_AUTONOMOUS_AGENTS.format(tenant_id=tenant_id), json=agent_data, headers=headers
        )
        agent_id = create_response.json()["id"]

        # Add READ permission
        test_client.put(
            ENDPOINT_AUTONOMOUS_AGENT_PRINCIPALS.format(tenant_id=tenant_id, autonomous_agent_id=agent_id),
            json={"principal_id": "other-user", "principal_type": PRINCIPAL_TYPE_USER, "role": ROLE_READ},
            headers=headers,
        )

        # Update to WRITE permission
        update_response = test_client.put(
            ENDPOINT_AUTONOMOUS_AGENT_PRINCIPALS.format(tenant_id=tenant_id, autonomous_agent_id=agent_id),
            json={"principal_id": "other-user", "principal_type": PRINCIPAL_TYPE_USER, "role": ROLE_WRITE},
            headers=headers,
        )

        assert update_response.status_code == status.HTTP_200_OK
        data = update_response.json()

        assert data["principal_id"] == "other-user"
        assert ROLE_WRITE in data["roles"]

    def test_set_principal_permission_missing_principal_id(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test setting permission with missing principal_id."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        # Create an autonomous agent
        agent_data = {"name": "Test Agent", "description": "Test", "type": AGENT_TYPE_N8N, "config": VALID_N8N_CONFIG}
        create_response = test_client.post(
            ENDPOINT_AUTONOMOUS_AGENTS.format(tenant_id=tenant_id), json=agent_data, headers=headers
        )
        agent_id = create_response.json()["id"]

        response = test_client.put(
            ENDPOINT_AUTONOMOUS_AGENT_PRINCIPALS.format(tenant_id=tenant_id, autonomous_agent_id=agent_id),
            json={"principal_type": PRINCIPAL_TYPE_USER, "role": ROLE_READ},
            headers=headers,
        )

        assert response.status_code == 422

    def test_set_principal_permission_missing_role(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test setting permission with missing role."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        # Create an autonomous agent
        agent_data = {"name": "Test Agent", "description": "Test", "type": AGENT_TYPE_N8N, "config": VALID_N8N_CONFIG}
        create_response = test_client.post(
            ENDPOINT_AUTONOMOUS_AGENTS.format(tenant_id=tenant_id), json=agent_data, headers=headers
        )
        agent_id = create_response.json()["id"]

        response = test_client.put(
            ENDPOINT_AUTONOMOUS_AGENT_PRINCIPALS.format(tenant_id=tenant_id, autonomous_agent_id=agent_id),
            json={"principal_id": "user-123", "principal_type": PRINCIPAL_TYPE_USER},
            headers=headers,
        )

        assert response.status_code == 422

    def test_set_principal_permission_invalid_role(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test setting permission with invalid role."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        # Create an autonomous agent
        agent_data = {"name": "Test Agent", "description": "Test", "type": AGENT_TYPE_N8N, "config": VALID_N8N_CONFIG}
        create_response = test_client.post(
            ENDPOINT_AUTONOMOUS_AGENTS.format(tenant_id=tenant_id), json=agent_data, headers=headers
        )
        agent_id = create_response.json()["id"]

        response = test_client.put(
            ENDPOINT_AUTONOMOUS_AGENT_PRINCIPALS.format(tenant_id=tenant_id, autonomous_agent_id=agent_id),
            json={"principal_id": "user-123", "principal_type": PRINCIPAL_TYPE_USER, "role": "INVALID_ROLE"},
            headers=headers,
        )

        assert response.status_code == 422

    def test_set_principal_permission_invalid_principal_type(
        self, test_client: TestClient, test_user_token: Any
    ) -> None:
        """Test setting permission with invalid principal type."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        # Create an autonomous agent
        agent_data = {"name": "Test Agent", "description": "Test", "type": AGENT_TYPE_N8N, "config": VALID_N8N_CONFIG}
        create_response = test_client.post(
            ENDPOINT_AUTONOMOUS_AGENTS.format(tenant_id=tenant_id), json=agent_data, headers=headers
        )
        agent_id = create_response.json()["id"]

        response = test_client.put(
            ENDPOINT_AUTONOMOUS_AGENT_PRINCIPALS.format(tenant_id=tenant_id, autonomous_agent_id=agent_id),
            json={"principal_id": "user-123", "principal_type": "INVALID_TYPE", "role": ROLE_READ},
            headers=headers,
        )

        assert response.status_code == 422

    def test_delete_principal_permission(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test deleting a principal's permission."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        # Create an autonomous agent
        agent_data = {"name": "Test Agent", "description": "Test", "type": AGENT_TYPE_N8N, "config": VALID_N8N_CONFIG}
        create_response = test_client.post(
            ENDPOINT_AUTONOMOUS_AGENTS.format(tenant_id=tenant_id), json=agent_data, headers=headers
        )
        agent_id = create_response.json()["id"]

        # Add permission
        test_client.put(
            ENDPOINT_AUTONOMOUS_AGENT_PRINCIPALS.format(tenant_id=tenant_id, autonomous_agent_id=agent_id),
            json={"principal_id": "user-to-remove", "principal_type": PRINCIPAL_TYPE_USER, "role": ROLE_READ},
            headers=headers,
        )

        # Delete permission
        delete_response = test_client.request(
            "DELETE",
            ENDPOINT_AUTONOMOUS_AGENT_PRINCIPALS.format(tenant_id=tenant_id, autonomous_agent_id=agent_id),
            json={"principal_id": "user-to-remove", "principal_type": PRINCIPAL_TYPE_USER, "role": ROLE_READ},
            headers=headers,
        )

        assert delete_response.status_code == status.HTTP_204_NO_CONTENT

    def test_delete_principal_permission_not_found(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test deleting a non-existent principal permission."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        # Create an autonomous agent
        agent_data = {"name": "Test Agent", "description": "Test", "type": AGENT_TYPE_N8N, "config": VALID_N8N_CONFIG}
        create_response = test_client.post(
            ENDPOINT_AUTONOMOUS_AGENTS.format(tenant_id=tenant_id), json=agent_data, headers=headers
        )
        agent_id = create_response.json()["id"]

        # Try to delete non-existent permission
        response = test_client.request(
            "DELETE",
            ENDPOINT_AUTONOMOUS_AGENT_PRINCIPALS.format(tenant_id=tenant_id, autonomous_agent_id=agent_id),
            json={"principal_id": "non-existent-user", "principal_type": PRINCIPAL_TYPE_USER, "role": ROLE_READ},
            headers=headers,
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestAutonomousAgentKeyRoutes:
    """Test suite for autonomous agent API key management routes."""

    def test_get_primary_key_success(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test successful retrieval of primary API key."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        # Create an autonomous agent
        agent_data = {
            "name": "Test Agent",
            "description": "Test",
            "type": AGENT_TYPE_N8N,
            "config": VALID_N8N_CONFIG,
            "allow_api_keys": True,
        }
        create_response = test_client.post(
            ENDPOINT_AUTONOMOUS_AGENTS.format(tenant_id=tenant_id), json=agent_data, headers=headers
        )
        agent_id = create_response.json()["id"]

        # Get primary key
        response = test_client.get(
            f"{ENDPOINT_AUTONOMOUS_AGENT_DETAIL.format(tenant_id=tenant_id, autonomous_agent_id=agent_id)}/keys/1",
            headers=headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "key" in data
        assert data["key_number"] == 1
        assert len(data["key"]) > 20  # Key should be a reasonable length

    def test_get_secondary_key_success(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test successful retrieval of secondary API key."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        # Create an autonomous agent
        agent_data = {
            "name": "Test Agent",
            "description": "Test",
            "type": AGENT_TYPE_N8N,
            "config": VALID_N8N_CONFIG,
            "allow_api_keys": True,
        }
        create_response = test_client.post(
            ENDPOINT_AUTONOMOUS_AGENTS.format(tenant_id=tenant_id), json=agent_data, headers=headers
        )
        agent_id = create_response.json()["id"]

        # Get secondary key
        response = test_client.get(
            f"{ENDPOINT_AUTONOMOUS_AGENT_DETAIL.format(tenant_id=tenant_id, autonomous_agent_id=agent_id)}/keys/2",
            headers=headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "key" in data
        assert data["key_number"] == 2

    def test_get_key_invalid_number(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test retrieval of key with invalid key number."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        # Create an autonomous agent
        agent_data = {"name": "Test Agent", "description": "Test", "type": AGENT_TYPE_N8N, "config": VALID_N8N_CONFIG}
        create_response = test_client.post(
            ENDPOINT_AUTONOMOUS_AGENTS.format(tenant_id=tenant_id), json=agent_data, headers=headers
        )
        agent_id = create_response.json()["id"]

        # Try to get key 3 (invalid)
        response = test_client.get(
            f"{ENDPOINT_AUTONOMOUS_AGENT_DETAIL.format(tenant_id=tenant_id, autonomous_agent_id=agent_id)}/keys/3",
            headers=headers,
        )

        # Invalid key_number is a bad request, not not-found
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_rotate_primary_key_success(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test successful rotation of primary API key."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        # Create an autonomous agent
        agent_data = {
            "name": "Test Agent",
            "description": "Test",
            "type": AGENT_TYPE_N8N,
            "config": VALID_N8N_CONFIG,
            "allow_api_keys": True,
        }
        create_response = test_client.post(
            ENDPOINT_AUTONOMOUS_AGENTS.format(tenant_id=tenant_id), json=agent_data, headers=headers
        )
        agent_id = create_response.json()["id"]

        # Get original primary key
        original_key_response = test_client.get(
            f"{ENDPOINT_AUTONOMOUS_AGENT_DETAIL.format(tenant_id=tenant_id, autonomous_agent_id=agent_id)}/keys/1",
            headers=headers,
        )
        original_key = original_key_response.json()["key"]

        # Rotate primary key
        rotate_response = test_client.put(
            f"{ENDPOINT_AUTONOMOUS_AGENT_DETAIL.format(tenant_id=tenant_id, autonomous_agent_id=agent_id)}/keys/1/rotate",
            headers=headers,
        )

        assert rotate_response.status_code == status.HTTP_200_OK
        rotated_data = rotate_response.json()
        assert "key" in rotated_data
        assert rotated_data["key_number"] == 1
        assert rotated_data["key"] != original_key  # New key should be different

    def test_rotate_secondary_key_success(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test successful rotation of secondary API key."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        # Create an autonomous agent
        agent_data = {
            "name": "Test Agent",
            "description": "Test",
            "type": AGENT_TYPE_N8N,
            "config": VALID_N8N_CONFIG,
            "allow_api_keys": True,
        }
        create_response = test_client.post(
            ENDPOINT_AUTONOMOUS_AGENTS.format(tenant_id=tenant_id), json=agent_data, headers=headers
        )
        agent_id = create_response.json()["id"]

        # Get original secondary key
        original_key_response = test_client.get(
            f"{ENDPOINT_AUTONOMOUS_AGENT_DETAIL.format(tenant_id=tenant_id, autonomous_agent_id=agent_id)}/keys/2",
            headers=headers,
        )
        original_key = original_key_response.json()["key"]

        # Rotate secondary key
        rotate_response = test_client.put(
            f"{ENDPOINT_AUTONOMOUS_AGENT_DETAIL.format(tenant_id=tenant_id, autonomous_agent_id=agent_id)}/keys/2/rotate",
            headers=headers,
        )

        assert rotate_response.status_code == status.HTTP_200_OK
        rotated_data = rotate_response.json()
        assert "key" in rotated_data
        assert rotated_data["key_number"] == 2
        assert rotated_data["key"] != original_key

    def test_rotate_key_invalid_number(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test rotation of key with invalid key number."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        # Create an autonomous agent
        agent_data = {"name": "Test Agent", "description": "Test", "type": AGENT_TYPE_N8N, "config": VALID_N8N_CONFIG}
        create_response = test_client.post(
            ENDPOINT_AUTONOMOUS_AGENTS.format(tenant_id=tenant_id), json=agent_data, headers=headers
        )
        agent_id = create_response.json()["id"]

        # Try to rotate key 3 (invalid)
        response = test_client.put(
            f"{ENDPOINT_AUTONOMOUS_AGENT_DETAIL.format(tenant_id=tenant_id, autonomous_agent_id=agent_id)}/keys/3/rotate",
            headers=headers,
        )

        # Invalid key_number is a bad request, not not-found
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_keys_are_different(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test that primary and secondary keys are different upon creation."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        # Create an autonomous agent
        agent_data = {
            "name": "Test Agent",
            "description": "Test",
            "type": AGENT_TYPE_N8N,
            "config": VALID_N8N_CONFIG,
            "allow_api_keys": True,
        }
        create_response = test_client.post(
            ENDPOINT_AUTONOMOUS_AGENTS.format(tenant_id=tenant_id), json=agent_data, headers=headers
        )
        agent_id = create_response.json()["id"]

        # Get both keys
        key1_response = test_client.get(
            f"{ENDPOINT_AUTONOMOUS_AGENT_DETAIL.format(tenant_id=tenant_id, autonomous_agent_id=agent_id)}/keys/1",
            headers=headers,
        )
        key2_response = test_client.get(
            f"{ENDPOINT_AUTONOMOUS_AGENT_DETAIL.format(tenant_id=tenant_id, autonomous_agent_id=agent_id)}/keys/2",
            headers=headers,
        )

        key1 = key1_response.json()["key"]
        key2 = key2_response.json()["key"]

        assert key1 != key2  # Primary and secondary keys should be different

    def test_get_key_agent_not_found(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test getting key for non-existent agent."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        response = test_client.get(
            f"{ENDPOINT_AUTONOMOUS_AGENT_DETAIL.format(tenant_id=tenant_id, autonomous_agent_id=NON_EXISTENT_ID)}/keys/1",
            headers=headers,
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestAutonomousAgentConfigValidation:
    """Test suite for autonomous agent configuration validation."""

    def test_create_agent_invalid_workflow_endpoint_missing_workflow(
        self, test_client: TestClient, test_user_token: Any
    ) -> None:
        """Test creation fails when workflow_endpoint doesn't contain /workflow/."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        invalid_config = {
            "workflow_endpoint": "http://localhost:5678/api/test",  # Missing /workflow/
            "api_api_key_credential_id": "test-cred-id",
        }

        response = test_client.post(
            ENDPOINT_AUTONOMOUS_AGENTS.format(tenant_id=tenant_id),
            json={"name": "Test Agent", "description": "Test", "type": AGENT_TYPE_N8N, "config": invalid_config},
            headers=headers,
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_agent_invalid_workflow_endpoint_not_url(
        self, test_client: TestClient, test_user_token: Any
    ) -> None:
        """Test creation fails when workflow_endpoint is not a valid URL."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        invalid_config = {
            "workflow_endpoint": "not-a-valid-url/workflow/test",
            "api_api_key_credential_id": "test-cred-id",
        }

        response = test_client.post(
            ENDPOINT_AUTONOMOUS_AGENTS.format(tenant_id=tenant_id),
            json={"name": "Test Agent", "description": "Test", "type": AGENT_TYPE_N8N, "config": invalid_config},
            headers=headers,
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_agent_missing_api_key_credential_id(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test creation fails when api_api_key_credential_id is missing."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        invalid_config = {
            "workflow_endpoint": "http://localhost:5678/workflow/test"
            # Missing api_api_key_credential_id
        }

        response = test_client.post(
            ENDPOINT_AUTONOMOUS_AGENTS.format(tenant_id=tenant_id),
            json={"name": "Test Agent", "description": "Test", "type": AGENT_TYPE_N8N, "config": invalid_config},
            headers=headers,
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_update_agent_config_validation(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test that config is validated on update."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        # Create agent with valid config
        agent_data = {"name": "Test Agent", "description": "Test", "type": AGENT_TYPE_N8N, "config": VALID_N8N_CONFIG}
        create_response = test_client.post(
            ENDPOINT_AUTONOMOUS_AGENTS.format(tenant_id=tenant_id), json=agent_data, headers=headers
        )
        agent_id = create_response.json()["id"]

        # Try to update with invalid config
        invalid_config = {"workflow_endpoint": "invalid-url", "api_api_key_credential_id": "test-cred-id"}

        update_response = test_client.patch(
            ENDPOINT_AUTONOMOUS_AGENT_DETAIL.format(tenant_id=tenant_id, autonomous_agent_id=agent_id),
            json={"config": invalid_config},
            headers=headers,
        )

        assert update_response.status_code == status.HTTP_400_BAD_REQUEST

    def test_agent_response_includes_type(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test that agent response includes type field."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        agent_data = {"name": "Test Agent", "description": "Test", "type": AGENT_TYPE_N8N, "config": VALID_N8N_CONFIG}
        create_response = test_client.post(
            ENDPOINT_AUTONOMOUS_AGENTS.format(tenant_id=tenant_id), json=agent_data, headers=headers
        )

        assert create_response.status_code == status.HTTP_201_CREATED
        data = create_response.json()
        assert "type" in data
        assert data["type"] == AGENT_TYPE_N8N

    def test_create_agent_with_api_version(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test that api_version is required in N8N config."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        # Config with api_version
        config_with_version = {
            "api_version": "v1",
            "workflow_endpoint": "http://localhost:5678/workflow/test-workflow-id",
            "api_api_key_credential_id": "test-credential-id",
        }

        agent_data = {
            "name": "Test Agent",
            "description": "Test",
            "type": AGENT_TYPE_N8N,
            "config": config_with_version,
        }
        response = test_client.post(
            ENDPOINT_AUTONOMOUS_AGENTS.format(tenant_id=tenant_id), json=agent_data, headers=headers
        )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["config"]["api_version"] == "v1"

    def test_create_agent_missing_api_version_fails(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test that missing api_version in N8N config raises error."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        # Config without api_version
        config_without_version = {
            "workflow_endpoint": "http://localhost:5678/workflow/test-workflow-id",
            "api_api_key_credential_id": "test-credential-id",
        }

        agent_data = {
            "name": "Test Agent",
            "description": "Test",
            "type": AGENT_TYPE_N8N,
            "config": config_without_version,
        }
        response = test_client.post(
            ENDPOINT_AUTONOMOUS_AGENTS.format(tenant_id=tenant_id), json=agent_data, headers=headers
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_agent_invalid_api_version_fails(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test that invalid api_version (v2) in N8N config raises error."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        # Config with invalid api_version
        config_invalid_version = {
            "api_version": "v2",  # Invalid - only v1 allowed
            "workflow_endpoint": "http://localhost:5678/workflow/test-workflow-id",
            "api_api_key_credential_id": "test-credential-id",
        }

        agent_data = {
            "name": "Test Agent",
            "description": "Test",
            "type": AGENT_TYPE_N8N,
            "config": config_invalid_version,
        }
        response = test_client.post(
            ENDPOINT_AUTONOMOUS_AGENTS.format(tenant_id=tenant_id), json=agent_data, headers=headers
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST


class TestAutonomousAgentConfigEndpoint:
    """Test suite for the /autonomous-agents/{id}/config endpoint with API key auth."""

    def test_config_endpoint_requires_api_key_header(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test that config endpoint requires X-Unified-UI-Autonomous-Agent-API-Key header."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        # Create an agent
        agent_data = {"name": "Test Agent", "type": AGENT_TYPE_N8N, "config": VALID_N8N_CONFIG}
        create_response = test_client.post(
            ENDPOINT_AUTONOMOUS_AGENTS.format(tenant_id=tenant_id), json=agent_data, headers=headers
        )
        agent_id = create_response.json()["id"]

        # Try to access config without API key header
        response = test_client.get(
            ENDPOINT_AUTONOMOUS_AGENT_CONFIG.format(tenant_id=tenant_id, autonomous_agent_id=agent_id)
            # No headers - should fail
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_config_endpoint_rejects_bearer_token(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test that config endpoint does not accept Bearer token (only API key)."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        # Create an agent
        agent_data = {"name": "Test Agent", "type": AGENT_TYPE_N8N, "config": VALID_N8N_CONFIG}
        create_response = test_client.post(
            ENDPOINT_AUTONOMOUS_AGENTS.format(tenant_id=tenant_id), json=agent_data, headers=headers
        )
        agent_id = create_response.json()["id"]

        # Try to access config with Bearer token only (no API key)
        response = test_client.get(
            ENDPOINT_AUTONOMOUS_AGENT_CONFIG.format(tenant_id=tenant_id, autonomous_agent_id=agent_id),
            headers=headers,  # Bearer token only
        )

        # Should fail because API key header is required
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_config_endpoint_rejects_invalid_api_key(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test that config endpoint rejects invalid API key."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        # Create an agent with keys
        agent_data = {"name": "Test Agent", "type": AGENT_TYPE_N8N, "config": VALID_N8N_CONFIG, "allow_api_keys": True}
        create_response = test_client.post(
            ENDPOINT_AUTONOMOUS_AGENTS.format(tenant_id=tenant_id), json=agent_data, headers=headers
        )
        agent_id = create_response.json()["id"]

        # Rotate keys for the agent (PUT /keys/1/rotate generates a new key)
        keys_response = test_client.put(
            f"{ENDPOINT_AUTONOMOUS_AGENT_DETAIL.format(tenant_id=tenant_id, autonomous_agent_id=agent_id)}/keys/1/rotate",
            headers=headers,
        )
        assert keys_response.status_code == status.HTTP_200_OK

        # Activate the agent (required for config access)
        test_client.patch(
            ENDPOINT_AUTONOMOUS_AGENT_DETAIL.format(tenant_id=tenant_id, autonomous_agent_id=agent_id),
            json={"is_active": True},
            headers=headers,
        )

        # Try with invalid API key
        response = test_client.get(
            ENDPOINT_AUTONOMOUS_AGENT_CONFIG.format(tenant_id=tenant_id, autonomous_agent_id=agent_id),
            headers={API_KEY_HEADER: "invalid-api-key"},
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_config_endpoint_rejects_inactive_agent(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test that config endpoint rejects access if agent is not active."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        # Create an inactive agent with keys
        agent_data = {"name": "Test Agent", "type": AGENT_TYPE_N8N, "config": VALID_N8N_CONFIG, "allow_api_keys": True}
        create_response = test_client.post(
            ENDPOINT_AUTONOMOUS_AGENTS.format(tenant_id=tenant_id), json=agent_data, headers=headers
        )
        agent_id = create_response.json()["id"]

        # Rotate keys (PUT /keys/1/rotate generates a new key)
        keys_response = test_client.put(
            f"{ENDPOINT_AUTONOMOUS_AGENT_DETAIL.format(tenant_id=tenant_id, autonomous_agent_id=agent_id)}/keys/1/rotate",
            headers=headers,
        )
        assert keys_response.status_code == status.HTTP_200_OK
        api_key = keys_response.json()["key"]

        # Agent is NOT activated (is_active=False)
        # Try to access config
        response = test_client.get(
            ENDPOINT_AUTONOMOUS_AGENT_CONFIG.format(tenant_id=tenant_id, autonomous_agent_id=agent_id),
            headers={API_KEY_HEADER: api_key},
        )

        # Should fail because agent is not active
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_config_endpoint_not_found_agent(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test that config endpoint returns 404 for non-existent agent."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)

        response = test_client.get(
            ENDPOINT_AUTONOMOUS_AGENT_CONFIG.format(tenant_id=tenant_id, autonomous_agent_id="non-existent-id"),
            headers={API_KEY_HEADER: "some-api-key"},
        )

        assert response.status_code in [status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND]
