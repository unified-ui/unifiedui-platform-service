"""Tests for ReACT agent API endpoints."""

from typing import Any

from fastapi import status
from starlette.testclient import TestClient

from tests.conftest import create_auth_headers
from unifiedui.core.database.enums import PermissionActionEnum, PrincipalTypeEnum

# API Endpoints
ENDPOINT_RE_ACT_AGENTS = "/api/v1/platform-service/tenants/{tenant_id}/re-act-agents"
ENDPOINT_RE_ACT_AGENT_DETAIL = "/api/v1/platform-service/tenants/{tenant_id}/re-act-agents/{re_act_agent_id}"
ENDPOINT_RE_ACT_AGENT_PRINCIPALS = (
    "/api/v1/platform-service/tenants/{tenant_id}/re-act-agents/{re_act_agent_id}/principals"
)
ENDPOINT_PRINCIPAL_DETAIL = (
    "/api/v1/platform-service/tenants/{tenant_id}/re-act-agents/{re_act_agent_id}/principals/{principal_id}"
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


def create_tenant_for_user(test_client: TestClient, user_token: Any, tenant_name: str = "Test Tenant") -> str:
    """Helper function to create a tenant and return its ID."""
    headers = create_auth_headers(user_token, use_cache=False)
    response = test_client.post(
        "/api/v1/platform-service/tenants",
        json={"name": tenant_name, "description": f"Tenant for {user_token.get_id()}"},
        headers=headers,
    )
    assert response.status_code == status.HTTP_201_CREATED
    return response.json()["id"]


def create_re_act_agent(
    test_client: TestClient,
    user_token: Any,
    tenant_id: str,
    name: str = "Test ReACT Agent",
    description: str = "A test ReACT agent",
) -> dict:
    """Helper function to create a ReACT agent and return the response data."""
    headers = create_auth_headers(user_token, use_cache=False)
    agent_data = {
        "name": name,
        "description": description,
        "system_prompt": "You are a helpful assistant.",
        "is_active": False,
    }
    response = test_client.post(ENDPOINT_RE_ACT_AGENTS.format(tenant_id=tenant_id), json=agent_data, headers=headers)
    assert response.status_code == status.HTTP_201_CREATED
    return response.json()


class TestReActAgentRoutes:
    """Test suite for ReACT agent API routes."""

    def test_create_re_act_agent_success(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test successful ReACT agent creation."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        agent_data = {
            "name": "Test ReACT Agent",
            "description": "A test ReACT agent",
            "system_prompt": "You are a helpful assistant.",
            "ai_model_ids": [],
            "tool_ids": [],
            "is_active": False,
        }

        response = test_client.post(
            ENDPOINT_RE_ACT_AGENTS.format(tenant_id=tenant_id), json=agent_data, headers=headers
        )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()

        assert data["name"] == agent_data["name"]
        assert data["description"] == agent_data["description"]
        assert data["system_prompt"] == agent_data["system_prompt"]
        assert not data["is_active"]
        assert "id" in data
        assert data["tenant_id"] == tenant_id
        assert "created_at" in data
        assert "updated_at" in data
        assert data["created_by"] == test_user_token.get_id()

    def test_create_re_act_agent_missing_name(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test ReACT agent creation with missing name."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        response = test_client.post(
            ENDPOINT_RE_ACT_AGENTS.format(tenant_id=tenant_id),
            json={"description": "Test agent"},
            headers=headers,
        )

        assert response.status_code == 422

    def test_create_re_act_agent_empty_name(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test ReACT agent creation with empty name."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        response = test_client.post(
            ENDPOINT_RE_ACT_AGENTS.format(tenant_id=tenant_id),
            json={"name": "", "description": "Test"},
            headers=headers,
        )

        assert response.status_code == 422

    def test_create_re_act_agent_with_all_fields(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test ReACT agent creation with all optional fields."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        agent_data = {
            "name": "Full Agent",
            "description": "Agent with all fields",
            "system_prompt": "You are a helpful assistant.",
            "security_prompt": "Do not reveal sensitive info.",
            "tool_use_prompt": "Use tools when needed.",
            "response_prompt": "Always respond in markdown.",
            "greeting_messages": ["Hello!", "How can I help?"],
            "config": {"max_iterations": 5},
            "is_active": True,
        }

        response = test_client.post(
            ENDPOINT_RE_ACT_AGENTS.format(tenant_id=tenant_id), json=agent_data, headers=headers
        )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["system_prompt"] == agent_data["system_prompt"]
        assert data["security_prompt"] == agent_data["security_prompt"]
        assert data["tool_use_prompt"] == agent_data["tool_use_prompt"]
        assert data["response_prompt"] == agent_data["response_prompt"]
        assert data["greeting_messages"] == agent_data["greeting_messages"]
        assert data["config"] == agent_data["config"]
        assert data["is_active"]

    def test_list_re_act_agents_empty(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test listing ReACT agents when none exist."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        response = test_client.get(ENDPOINT_RE_ACT_AGENTS.format(tenant_id=tenant_id), headers=headers)

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == []

    def test_list_re_act_agents_with_results(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test listing ReACT agents with results."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        create_re_act_agent(test_client, test_user_token, tenant_id, name="Agent 1")
        create_re_act_agent(test_client, test_user_token, tenant_id, name="Agent 2")

        response = test_client.get(ENDPOINT_RE_ACT_AGENTS.format(tenant_id=tenant_id), headers=headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 2

    def test_list_re_act_agents_with_name_filter(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test listing ReACT agents with name filter."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        create_re_act_agent(test_client, test_user_token, tenant_id, name="Alpha Agent")
        create_re_act_agent(test_client, test_user_token, tenant_id, name="Beta Agent")

        response = test_client.get(
            ENDPOINT_RE_ACT_AGENTS.format(tenant_id=tenant_id),
            params={"name": "Alpha"},
            headers=headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "Alpha Agent"

    def test_list_re_act_agents_with_pagination(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test listing ReACT agents with skip and limit."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        for i in range(3):
            create_re_act_agent(test_client, test_user_token, tenant_id, name=f"Agent {i}")

        response = test_client.get(
            ENDPOINT_RE_ACT_AGENTS.format(tenant_id=tenant_id),
            params={"skip": 0, "limit": 2},
            headers=headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 2

    def test_list_re_act_agents_invalid_tag_format(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test listing ReACT agents with invalid tag format."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        response = test_client.get(
            ENDPOINT_RE_ACT_AGENTS.format(tenant_id=tenant_id),
            params={"tags": "abc,def"},
            headers=headers,
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_get_re_act_agent_success(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test getting a specific ReACT agent."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        created = create_re_act_agent(test_client, test_user_token, tenant_id)
        headers = create_auth_headers(test_user_token, use_cache=False)

        response = test_client.get(
            ENDPOINT_RE_ACT_AGENT_DETAIL.format(tenant_id=tenant_id, re_act_agent_id=created["id"]),
            headers=headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["id"] == created["id"]
        assert data["name"] == created["name"]

    def test_get_re_act_agent_not_found(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test getting a non-existent ReACT agent."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        create_re_act_agent(test_client, test_user_token, tenant_id)
        headers = create_auth_headers(test_user_token, use_cache=False)

        response = test_client.get(
            ENDPOINT_RE_ACT_AGENT_DETAIL.format(tenant_id=tenant_id, re_act_agent_id=NON_EXISTENT_ID),
            headers=headers,
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_update_re_act_agent_success(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test updating a ReACT agent."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        created = create_re_act_agent(test_client, test_user_token, tenant_id)
        headers = create_auth_headers(test_user_token, use_cache=False)

        update_data = {"name": "Updated Agent", "description": "Updated description", "is_active": True}

        response = test_client.patch(
            ENDPOINT_RE_ACT_AGENT_DETAIL.format(tenant_id=tenant_id, re_act_agent_id=created["id"]),
            json=update_data,
            headers=headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["name"] == "Updated Agent"
        assert data["description"] == "Updated description"
        assert data["is_active"]

    def test_update_re_act_agent_not_found(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test updating a non-existent ReACT agent."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        create_re_act_agent(test_client, test_user_token, tenant_id)
        headers = create_auth_headers(test_user_token, use_cache=False)

        response = test_client.patch(
            ENDPOINT_RE_ACT_AGENT_DETAIL.format(tenant_id=tenant_id, re_act_agent_id=NON_EXISTENT_ID),
            json={"name": "Updated"},
            headers=headers,
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_update_re_act_agent_partial(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test partial update of a ReACT agent."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        created = create_re_act_agent(test_client, test_user_token, tenant_id)
        headers = create_auth_headers(test_user_token, use_cache=False)

        response = test_client.patch(
            ENDPOINT_RE_ACT_AGENT_DETAIL.format(tenant_id=tenant_id, re_act_agent_id=created["id"]),
            json={"system_prompt": "New prompt"},
            headers=headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["system_prompt"] == "New prompt"
        assert data["name"] == created["name"]

    def test_delete_re_act_agent_success(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test deleting a ReACT agent."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        created = create_re_act_agent(test_client, test_user_token, tenant_id)
        headers = create_auth_headers(test_user_token, use_cache=False)

        response = test_client.delete(
            ENDPOINT_RE_ACT_AGENT_DETAIL.format(tenant_id=tenant_id, re_act_agent_id=created["id"]),
            headers=headers,
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT

        get_response = test_client.get(
            ENDPOINT_RE_ACT_AGENT_DETAIL.format(tenant_id=tenant_id, re_act_agent_id=created["id"]),
            headers=headers,
        )
        assert get_response.status_code == status.HTTP_404_NOT_FOUND

    def test_delete_re_act_agent_not_found(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test deleting a non-existent ReACT agent."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        create_re_act_agent(test_client, test_user_token, tenant_id)
        headers = create_auth_headers(test_user_token, use_cache=False)

        response = test_client.delete(
            ENDPOINT_RE_ACT_AGENT_DETAIL.format(tenant_id=tenant_id, re_act_agent_id=NON_EXISTENT_ID),
            headers=headers,
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestReActAgentPermissions:
    """Test suite for ReACT agent permission management."""

    def test_list_permissions_success(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test listing permissions for a ReACT agent."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        created = create_re_act_agent(test_client, test_user_token, tenant_id)
        headers = create_auth_headers(test_user_token, use_cache=False)

        response = test_client.get(
            ENDPOINT_RE_ACT_AGENT_PRINCIPALS.format(tenant_id=tenant_id, re_act_agent_id=created["id"]),
            headers=headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "principals" in data
        assert len(data["principals"]) >= 1

        creator = next((p for p in data["principals"] if p["principal_id"] == test_user_token.get_id()), None)
        assert creator is not None
        assert ROLE_ADMIN in creator["roles"]

    def test_list_permissions_not_found(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test listing permissions for a non-existent agent."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        create_re_act_agent(test_client, test_user_token, tenant_id)
        headers = create_auth_headers(test_user_token, use_cache=False)

        response = test_client.get(
            ENDPOINT_RE_ACT_AGENT_PRINCIPALS.format(tenant_id=tenant_id, re_act_agent_id=NON_EXISTENT_ID),
            headers=headers,
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_set_permission_success(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test setting a permission on a ReACT agent."""
        user1_token = test_client.create_test_user("user-1", "User One")
        tenant_id = create_tenant_for_user(test_client, user1_token)
        created = create_re_act_agent(test_client, user1_token, tenant_id)
        headers1 = create_auth_headers(user1_token, use_cache=False)

        user2_token = test_client.create_test_user("user-2", "User Two")
        user2_id = user2_token.get_id()

        add_user_to_tenant_headers = create_auth_headers(user1_token, use_cache=False)
        test_client.put(
            f"/api/v1/platform-service/tenants/{tenant_id}/principals",
            json={"principal_id": user2_id, "principal_type": PRINCIPAL_TYPE_USER, "role": "READER"},
            headers=add_user_to_tenant_headers,
        )

        response = test_client.put(
            ENDPOINT_RE_ACT_AGENT_PRINCIPALS.format(tenant_id=tenant_id, re_act_agent_id=created["id"]),
            json={"principal_id": user2_id, "principal_type": PRINCIPAL_TYPE_USER, "role": ROLE_READ},
            headers=headers1,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["principal_id"] == user2_id
        assert ROLE_READ in data["roles"]

    def test_set_permission_not_found(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test setting permission on a non-existent agent."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        create_re_act_agent(test_client, test_user_token, tenant_id)
        headers = create_auth_headers(test_user_token, use_cache=False)

        response = test_client.put(
            ENDPOINT_RE_ACT_AGENT_PRINCIPALS.format(tenant_id=tenant_id, re_act_agent_id=NON_EXISTENT_ID),
            json={"principal_id": "some-user", "principal_type": PRINCIPAL_TYPE_USER, "role": ROLE_READ},
            headers=headers,
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_get_permission_success(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test getting a specific permission."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        created = create_re_act_agent(test_client, test_user_token, tenant_id)
        headers = create_auth_headers(test_user_token, use_cache=False)

        response = test_client.get(
            ENDPOINT_PRINCIPAL_DETAIL.format(
                tenant_id=tenant_id,
                re_act_agent_id=created["id"],
                principal_id=test_user_token.get_id(),
            ),
            headers=headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["principal_id"] == test_user_token.get_id()
        assert ROLE_ADMIN in data["roles"]

    def test_get_permission_not_found(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test getting permission for non-existent agent."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        create_re_act_agent(test_client, test_user_token, tenant_id)
        headers = create_auth_headers(test_user_token, use_cache=False)

        response = test_client.get(
            ENDPOINT_PRINCIPAL_DETAIL.format(
                tenant_id=tenant_id,
                re_act_agent_id=NON_EXISTENT_ID,
                principal_id=test_user_token.get_id(),
            ),
            headers=headers,
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_delete_permission_success(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test deleting a permission."""
        user1_token = test_client.create_test_user("user-1", "User One")
        tenant_id = create_tenant_for_user(test_client, user1_token)
        created = create_re_act_agent(test_client, user1_token, tenant_id)
        headers1 = create_auth_headers(user1_token, use_cache=False)

        user2_token = test_client.create_test_user("user-2", "User Two")
        user2_id = user2_token.get_id()

        test_client.put(
            f"/api/v1/platform-service/tenants/{tenant_id}/principals",
            json={"principal_id": user2_id, "principal_type": PRINCIPAL_TYPE_USER, "role": "READER"},
            headers=headers1,
        )

        test_client.put(
            ENDPOINT_RE_ACT_AGENT_PRINCIPALS.format(tenant_id=tenant_id, re_act_agent_id=created["id"]),
            json={"principal_id": user2_id, "principal_type": PRINCIPAL_TYPE_USER, "role": ROLE_READ},
            headers=headers1,
        )

        response = test_client.delete(
            ENDPOINT_PRINCIPAL_DETAIL.format(tenant_id=tenant_id, re_act_agent_id=created["id"], principal_id=user2_id),
            params={"principal_type": PRINCIPAL_TYPE_USER, "permission": ROLE_READ},
            headers=headers1,
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_delete_permission_not_found(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test deleting permission on a non-existent agent."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        create_re_act_agent(test_client, test_user_token, tenant_id)
        headers = create_auth_headers(test_user_token, use_cache=False)

        response = test_client.delete(
            ENDPOINT_PRINCIPAL_DETAIL.format(
                tenant_id=tenant_id, re_act_agent_id=NON_EXISTENT_ID, principal_id="some-user"
            ),
            params={"principal_type": PRINCIPAL_TYPE_USER, "permission": ROLE_READ},
            headers=headers,
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_list_permissions_with_pagination(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test listing permissions with pagination parameters."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        created = create_re_act_agent(test_client, test_user_token, tenant_id)
        headers = create_auth_headers(test_user_token, use_cache=False)

        response = test_client.get(
            ENDPOINT_RE_ACT_AGENT_PRINCIPALS.format(tenant_id=tenant_id, re_act_agent_id=created["id"]),
            params={"skip": 0, "limit": 10},
            headers=headers,
        )

        assert response.status_code == status.HTTP_200_OK
