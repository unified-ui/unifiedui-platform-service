"""RBAC tests for ReACT agent API endpoints."""

from typing import Any

from fastapi import status
from starlette.testclient import TestClient

from tests.conftest import create_auth_headers
from unifiedui.core.database.enums import PermissionActionEnum, PrincipalTypeEnum, TenantRolesEnum

# API Endpoints
ENDPOINT_RE_ACT_AGENTS = "/api/v1/platform-service/tenants/{tenant_id}/re-act-agents"
ENDPOINT_RE_ACT_AGENT_DETAIL = "/api/v1/platform-service/tenants/{tenant_id}/re-act-agents/{re_act_agent_id}"
ENDPOINT_RE_ACT_AGENT_PRINCIPALS = (
    "/api/v1/platform-service/tenants/{tenant_id}/re-act-agents/{re_act_agent_id}/principals"
)

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
        "/api/v1/platform-service/tenants",
        json={"name": tenant_name, "description": f"Tenant for {user_token.get_id()}"},
        headers=headers,
    )
    assert response.status_code == status.HTTP_201_CREATED
    return response.json()["id"]


def add_user_to_tenant(test_client: TestClient, creator_token: Any, tenant_id: str, user_id: str) -> None:
    """Helper function to add a user to a tenant."""
    headers = create_auth_headers(creator_token, use_cache=False)
    response = test_client.put(
        f"/api/v1/platform-service/tenants/{tenant_id}/principals",
        json={"principal_id": user_id, "principal_type": PRINCIPAL_TYPE_USER, "role": TenantRolesEnum.READER.value},
        headers=headers,
    )
    assert response.status_code == status.HTTP_200_OK


def add_user_to_tenant_with_role(
    test_client: TestClient, creator_token: Any, tenant_id: str, user_id: str, role: str
) -> None:
    """Helper function to add a user to a tenant with a specific role."""
    headers = create_auth_headers(creator_token, use_cache=False)
    response = test_client.put(
        f"/api/v1/platform-service/tenants/{tenant_id}/principals",
        json={"principal_id": user_id, "principal_type": PRINCIPAL_TYPE_USER, "role": role},
        headers=headers,
    )
    assert response.status_code == status.HTTP_200_OK


class TestReActAgentRBAC:
    """Test suite for ReACT agent role-based access control."""

    def test_creator_has_admin_permissions(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test that the creator automatically gets ADMIN permissions."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        agent_data = {"name": "Test Agent", "description": "Test"}
        create_response = test_client.post(
            ENDPOINT_RE_ACT_AGENTS.format(tenant_id=tenant_id), json=agent_data, headers=headers
        )
        agent_id = create_response.json()["id"]

        principals_response = test_client.get(
            ENDPOINT_RE_ACT_AGENT_PRINCIPALS.format(tenant_id=tenant_id, re_act_agent_id=agent_id),
            headers=headers,
        )

        assert principals_response.status_code == status.HTTP_200_OK
        data = principals_response.json()

        creator_principal = next((p for p in data["principals"] if p["principal_id"] == test_user_token.get_id()), None)
        assert creator_principal is not None
        assert ROLE_ADMIN in creator_principal["roles"]

    def test_read_permission_allows_get(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test that READ permission allows getting a ReACT agent."""
        user1_token = test_client.create_test_user("user-1", "User One")
        tenant_id = create_tenant_for_user(test_client, user1_token)
        headers1 = create_auth_headers(user1_token, use_cache=False)

        agent_data = {"name": "Test Agent", "description": "Test"}
        create_response = test_client.post(
            ENDPOINT_RE_ACT_AGENTS.format(tenant_id=tenant_id), json=agent_data, headers=headers1
        )
        agent_id = create_response.json()["id"]

        user2_token = test_client.create_test_user("user-2", "User Two")
        user2_id = user2_token.get_id()
        add_user_to_tenant(test_client, user1_token, tenant_id, user2_id)
        headers2 = create_auth_headers(user2_token, use_cache=False)

        test_client.put(
            ENDPOINT_RE_ACT_AGENT_PRINCIPALS.format(tenant_id=tenant_id, re_act_agent_id=agent_id),
            json={"principal_id": user2_id, "principal_type": PRINCIPAL_TYPE_USER, "role": ROLE_READ},
            headers=headers1,
        )

        get_response = test_client.get(
            ENDPOINT_RE_ACT_AGENT_DETAIL.format(tenant_id=tenant_id, re_act_agent_id=agent_id),
            headers=headers2,
        )

        assert get_response.status_code == status.HTTP_200_OK

    def test_write_permission_allows_update(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test that WRITE permission allows updating a ReACT agent."""
        user1_token = test_client.create_test_user("user-1", "User One")
        tenant_id = create_tenant_for_user(test_client, user1_token)
        headers1 = create_auth_headers(user1_token, use_cache=False)

        agent_data = {"name": "Test Agent", "description": "Test"}
        create_response = test_client.post(
            ENDPOINT_RE_ACT_AGENTS.format(tenant_id=tenant_id), json=agent_data, headers=headers1
        )
        agent_id = create_response.json()["id"]

        user2_token = test_client.create_test_user("user-2", "User Two")
        user2_id = user2_token.get_id()
        add_user_to_tenant(test_client, user1_token, tenant_id, user2_id)
        headers2 = create_auth_headers(user2_token, use_cache=False)

        test_client.put(
            ENDPOINT_RE_ACT_AGENT_PRINCIPALS.format(tenant_id=tenant_id, re_act_agent_id=agent_id),
            json={"principal_id": user2_id, "principal_type": PRINCIPAL_TYPE_USER, "role": ROLE_WRITE},
            headers=headers1,
        )

        update_response = test_client.patch(
            ENDPOINT_RE_ACT_AGENT_DETAIL.format(tenant_id=tenant_id, re_act_agent_id=agent_id),
            json={"name": "Updated"},
            headers=headers2,
        )

        assert update_response.status_code == status.HTTP_200_OK

    def test_read_permission_denies_update(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test that READ permission denies updating a ReACT agent."""
        user1_token = test_client.create_test_user("user-1", "User One")
        tenant_id = create_tenant_for_user(test_client, user1_token)
        headers1 = create_auth_headers(user1_token, use_cache=False)

        agent_data = {"name": "Test Agent", "description": "Test"}
        create_response = test_client.post(
            ENDPOINT_RE_ACT_AGENTS.format(tenant_id=tenant_id), json=agent_data, headers=headers1
        )
        agent_id = create_response.json()["id"]

        user2_token = test_client.create_test_user("user-2", "User Two")
        user2_id = user2_token.get_id()
        add_user_to_tenant(test_client, user1_token, tenant_id, user2_id)
        headers2 = create_auth_headers(user2_token, use_cache=False)

        test_client.put(
            ENDPOINT_RE_ACT_AGENT_PRINCIPALS.format(tenant_id=tenant_id, re_act_agent_id=agent_id),
            json={"principal_id": user2_id, "principal_type": PRINCIPAL_TYPE_USER, "role": ROLE_READ},
            headers=headers1,
        )

        update_response = test_client.patch(
            ENDPOINT_RE_ACT_AGENT_DETAIL.format(tenant_id=tenant_id, re_act_agent_id=agent_id),
            json={"name": "Updated"},
            headers=headers2,
        )

        assert update_response.status_code == status.HTTP_403_FORBIDDEN

    def test_non_member_denied_access(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test that a non-member cannot access ReACT agents."""
        user1_token = test_client.create_test_user("user-1", "User One")
        tenant_id = create_tenant_for_user(test_client, user1_token)
        headers1 = create_auth_headers(user1_token, use_cache=False)

        agent_data = {"name": "Test Agent", "description": "Test"}
        create_response = test_client.post(
            ENDPOINT_RE_ACT_AGENTS.format(tenant_id=tenant_id), json=agent_data, headers=headers1
        )
        agent_id = create_response.json()["id"]

        user2_token = test_client.create_test_user("user-2", "User Two")
        headers2 = create_auth_headers(user2_token, use_cache=False)

        get_response = test_client.get(
            ENDPOINT_RE_ACT_AGENT_DETAIL.format(tenant_id=tenant_id, re_act_agent_id=agent_id),
            headers=headers2,
        )

        assert get_response.status_code == status.HTTP_403_FORBIDDEN

    def test_global_admin_bypasses_resource_permissions(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test that TENANT_GLOBAL_ADMIN tenant role bypasses resource-level permissions."""
        user1_token = test_client.create_test_user("user-1", "User One")
        tenant_id = create_tenant_for_user(test_client, user1_token)
        headers1 = create_auth_headers(user1_token, use_cache=False)

        agent_data = {"name": "Test Agent", "description": "Test"}
        create_response = test_client.post(
            ENDPOINT_RE_ACT_AGENTS.format(tenant_id=tenant_id), json=agent_data, headers=headers1
        )
        agent_id = create_response.json()["id"]

        admin_token = test_client.create_test_user("admin-user", "Admin User")
        admin_id = admin_token.get_id()
        add_user_to_tenant_with_role(
            test_client, user1_token, tenant_id, admin_id, TenantRolesEnum.TENANT_GLOBAL_ADMIN.value
        )
        admin_headers = create_auth_headers(admin_token, use_cache=False)

        get_response = test_client.get(
            ENDPOINT_RE_ACT_AGENT_DETAIL.format(tenant_id=tenant_id, re_act_agent_id=agent_id),
            headers=admin_headers,
        )

        assert get_response.status_code == status.HTTP_200_OK

    def test_react_agent_admin_bypasses_resource_permissions(
        self, test_client: TestClient, test_user_token: Any
    ) -> None:
        """Test that REACT_AGENT_ADMIN tenant role bypasses resource-level permissions."""
        user1_token = test_client.create_test_user("user-1", "User One")
        tenant_id = create_tenant_for_user(test_client, user1_token)
        headers1 = create_auth_headers(user1_token, use_cache=False)

        agent_data = {"name": "Test Agent", "description": "Test"}
        create_response = test_client.post(
            ENDPOINT_RE_ACT_AGENTS.format(tenant_id=tenant_id), json=agent_data, headers=headers1
        )
        agent_id = create_response.json()["id"]

        ra_admin_token = test_client.create_test_user("ra-admin", "RA Admin")
        ra_admin_id = ra_admin_token.get_id()
        add_user_to_tenant_with_role(
            test_client, user1_token, tenant_id, ra_admin_id, TenantRolesEnum.REACT_AGENT_ADMIN.value
        )
        ra_admin_headers = create_auth_headers(ra_admin_token, use_cache=False)

        get_response = test_client.get(
            ENDPOINT_RE_ACT_AGENT_DETAIL.format(tenant_id=tenant_id, re_act_agent_id=agent_id),
            headers=ra_admin_headers,
        )

        assert get_response.status_code == status.HTTP_200_OK

    def test_reader_can_list_own_agents(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test that a reader can list agents they have permission on."""
        user1_token = test_client.create_test_user("user-1", "User One")
        tenant_id = create_tenant_for_user(test_client, user1_token)
        headers1 = create_auth_headers(user1_token, use_cache=False)

        agent_data = {"name": "Test Agent", "description": "Test"}
        create_response = test_client.post(
            ENDPOINT_RE_ACT_AGENTS.format(tenant_id=tenant_id), json=agent_data, headers=headers1
        )
        agent_id = create_response.json()["id"]

        user2_token = test_client.create_test_user("user-2", "User Two")
        user2_id = user2_token.get_id()
        add_user_to_tenant(test_client, user1_token, tenant_id, user2_id)
        headers2 = create_auth_headers(user2_token, use_cache=False)

        list_response = test_client.get(ENDPOINT_RE_ACT_AGENTS.format(tenant_id=tenant_id), headers=headers2)
        assert list_response.status_code == status.HTTP_200_OK
        assert len(list_response.json()) == 0

        test_client.put(
            ENDPOINT_RE_ACT_AGENT_PRINCIPALS.format(tenant_id=tenant_id, re_act_agent_id=agent_id),
            json={"principal_id": user2_id, "principal_type": PRINCIPAL_TYPE_USER, "role": ROLE_READ},
            headers=headers1,
        )

        list_response2 = test_client.get(ENDPOINT_RE_ACT_AGENTS.format(tenant_id=tenant_id), headers=headers2)
        assert list_response2.status_code == status.HTTP_200_OK
        assert len(list_response2.json()) == 1

    def test_read_permission_denies_delete(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test that READ permission denies deleting a ReACT agent."""
        user1_token = test_client.create_test_user("user-1", "User One")
        tenant_id = create_tenant_for_user(test_client, user1_token)
        headers1 = create_auth_headers(user1_token, use_cache=False)

        agent_data = {"name": "Test Agent", "description": "Test"}
        create_response = test_client.post(
            ENDPOINT_RE_ACT_AGENTS.format(tenant_id=tenant_id), json=agent_data, headers=headers1
        )
        agent_id = create_response.json()["id"]

        user2_token = test_client.create_test_user("user-2", "User Two")
        user2_id = user2_token.get_id()
        add_user_to_tenant(test_client, user1_token, tenant_id, user2_id)
        headers2 = create_auth_headers(user2_token, use_cache=False)

        test_client.put(
            ENDPOINT_RE_ACT_AGENT_PRINCIPALS.format(tenant_id=tenant_id, re_act_agent_id=agent_id),
            json={"principal_id": user2_id, "principal_type": PRINCIPAL_TYPE_USER, "role": ROLE_READ},
            headers=headers1,
        )

        delete_response = test_client.delete(
            ENDPOINT_RE_ACT_AGENT_DETAIL.format(tenant_id=tenant_id, re_act_agent_id=agent_id),
            headers=headers2,
        )

        assert delete_response.status_code == status.HTTP_403_FORBIDDEN

    def test_write_permission_denies_delete(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test that WRITE permission denies deleting a ReACT agent."""
        user1_token = test_client.create_test_user("user-1", "User One")
        tenant_id = create_tenant_for_user(test_client, user1_token)
        headers1 = create_auth_headers(user1_token, use_cache=False)

        agent_data = {"name": "Test Agent", "description": "Test"}
        create_response = test_client.post(
            ENDPOINT_RE_ACT_AGENTS.format(tenant_id=tenant_id), json=agent_data, headers=headers1
        )
        agent_id = create_response.json()["id"]

        user2_token = test_client.create_test_user("user-2", "User Two")
        user2_id = user2_token.get_id()
        add_user_to_tenant(test_client, user1_token, tenant_id, user2_id)
        headers2 = create_auth_headers(user2_token, use_cache=False)

        test_client.put(
            ENDPOINT_RE_ACT_AGENT_PRINCIPALS.format(tenant_id=tenant_id, re_act_agent_id=agent_id),
            json={"principal_id": user2_id, "principal_type": PRINCIPAL_TYPE_USER, "role": ROLE_WRITE},
            headers=headers1,
        )

        delete_response = test_client.delete(
            ENDPOINT_RE_ACT_AGENT_DETAIL.format(tenant_id=tenant_id, re_act_agent_id=agent_id),
            headers=headers2,
        )

        assert delete_response.status_code == status.HTTP_403_FORBIDDEN

    def test_admin_permission_allows_delete(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test that ADMIN permission allows deleting a ReACT agent."""
        user1_token = test_client.create_test_user("user-1", "User One")
        tenant_id = create_tenant_for_user(test_client, user1_token)
        headers1 = create_auth_headers(user1_token, use_cache=False)

        agent_data = {"name": "Test Agent", "description": "Test"}
        create_response = test_client.post(
            ENDPOINT_RE_ACT_AGENTS.format(tenant_id=tenant_id), json=agent_data, headers=headers1
        )
        agent_id = create_response.json()["id"]

        user2_token = test_client.create_test_user("user-2", "User Two")
        user2_id = user2_token.get_id()
        add_user_to_tenant(test_client, user1_token, tenant_id, user2_id)
        headers2 = create_auth_headers(user2_token, use_cache=False)

        test_client.put(
            ENDPOINT_RE_ACT_AGENT_PRINCIPALS.format(tenant_id=tenant_id, re_act_agent_id=agent_id),
            json={"principal_id": user2_id, "principal_type": PRINCIPAL_TYPE_USER, "role": ROLE_ADMIN},
            headers=headers1,
        )

        delete_response = test_client.delete(
            ENDPOINT_RE_ACT_AGENT_DETAIL.format(tenant_id=tenant_id, re_act_agent_id=agent_id),
            headers=headers2,
        )

        assert delete_response.status_code == status.HTTP_204_NO_CONTENT

    def test_react_agent_creator_can_create(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test that REACT_AGENT_CREATOR tenant role can create agents."""
        user1_token = test_client.create_test_user("user-1", "User One")
        tenant_id = create_tenant_for_user(test_client, user1_token)

        creator_token = test_client.create_test_user("creator-user", "Creator User")
        creator_id = creator_token.get_id()
        add_user_to_tenant_with_role(
            test_client, user1_token, tenant_id, creator_id, TenantRolesEnum.REACT_AGENT_CREATOR.value
        )
        creator_headers = create_auth_headers(creator_token, use_cache=False)

        agent_data = {"name": "Created by Creator", "description": "Test"}
        response = test_client.post(
            ENDPOINT_RE_ACT_AGENTS.format(tenant_id=tenant_id), json=agent_data, headers=creator_headers
        )

        assert response.status_code == status.HTTP_201_CREATED

    def test_reader_cannot_create(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test that READER tenant role cannot create agents."""
        user1_token = test_client.create_test_user("user-1", "User One")
        tenant_id = create_tenant_for_user(test_client, user1_token)

        reader_token = test_client.create_test_user("reader-user", "Reader User")
        reader_id = reader_token.get_id()
        add_user_to_tenant(test_client, user1_token, tenant_id, reader_id)
        reader_headers = create_auth_headers(reader_token, use_cache=False)

        agent_data = {"name": "Created by Reader", "description": "Test"}
        response = test_client.post(
            ENDPOINT_RE_ACT_AGENTS.format(tenant_id=tenant_id), json=agent_data, headers=reader_headers
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN
