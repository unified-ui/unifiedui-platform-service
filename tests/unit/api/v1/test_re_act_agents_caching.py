"""Caching tests for ReACT agent API endpoints."""

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


class TestReActAgentCaching:
    """Test suite for ReACT agent caching behavior."""

    def test_list_cached_after_permission_grant(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test that list is properly cached/invalidated when permissions are granted."""
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
        headers2 = create_auth_headers(user2_token, use_cache=True)

        list1 = test_client.get(ENDPOINT_RE_ACT_AGENTS.format(tenant_id=tenant_id), headers=headers2)
        assert list1.status_code == status.HTTP_200_OK
        assert len(list1.json()) == 0

        test_client.put(
            ENDPOINT_RE_ACT_AGENT_PRINCIPALS.format(tenant_id=tenant_id, re_act_agent_id=agent_id),
            json={"principal_id": user2_id, "principal_type": PRINCIPAL_TYPE_USER, "role": ROLE_READ},
            headers=headers1,
        )

        list2 = test_client.get(ENDPOINT_RE_ACT_AGENTS.format(tenant_id=tenant_id), headers=headers2)
        assert list2.status_code == status.HTTP_200_OK
        assert len(list2.json()) == 1
        assert list2.json()[0]["id"] == agent_id

    def test_list_cached_after_permission_revoke(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test that list is properly cached/invalidated when permissions are revoked."""
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
        headers2 = create_auth_headers(user2_token, use_cache=True)

        test_client.put(
            ENDPOINT_RE_ACT_AGENT_PRINCIPALS.format(tenant_id=tenant_id, re_act_agent_id=agent_id),
            json={"principal_id": user2_id, "principal_type": PRINCIPAL_TYPE_USER, "role": ROLE_READ},
            headers=headers1,
        )

        list1 = test_client.get(ENDPOINT_RE_ACT_AGENTS.format(tenant_id=tenant_id), headers=headers2)
        assert list1.status_code == status.HTTP_200_OK
        assert len(list1.json()) == 1

        principal_detail_url = (
            f"/api/v1/platform-service/tenants/{tenant_id}/re-act-agents/{agent_id}/principals/{user2_id}"
        )
        test_client.delete(
            principal_detail_url,
            params={"principal_type": PRINCIPAL_TYPE_USER, "permission": ROLE_READ},
            headers=headers1,
        )

        list2 = test_client.get(ENDPOINT_RE_ACT_AGENTS.format(tenant_id=tenant_id), headers=headers2)
        assert list2.status_code == status.HTTP_200_OK
        assert len(list2.json()) == 0

    def test_detail_cached_after_update(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test that detail view is refreshed after update."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers_cache = create_auth_headers(test_user_token, use_cache=True)
        headers_no_cache = create_auth_headers(test_user_token, use_cache=False)

        agent_data = {"name": "Original Name", "description": "Test"}
        create_response = test_client.post(
            ENDPOINT_RE_ACT_AGENTS.format(tenant_id=tenant_id), json=agent_data, headers=headers_no_cache
        )
        agent_id = create_response.json()["id"]

        get1 = test_client.get(
            ENDPOINT_RE_ACT_AGENT_DETAIL.format(tenant_id=tenant_id, re_act_agent_id=agent_id),
            headers=headers_cache,
        )
        assert get1.status_code == status.HTTP_200_OK
        assert get1.json()["name"] == "Original Name"

        test_client.patch(
            ENDPOINT_RE_ACT_AGENT_DETAIL.format(tenant_id=tenant_id, re_act_agent_id=agent_id),
            json={"name": "Updated Name"},
            headers=headers_no_cache,
        )

        get2 = test_client.get(
            ENDPOINT_RE_ACT_AGENT_DETAIL.format(tenant_id=tenant_id, re_act_agent_id=agent_id),
            headers=headers_cache,
        )
        assert get2.status_code == status.HTTP_200_OK
        assert get2.json()["name"] == "Updated Name"

    def test_list_cached_after_create(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test that list cache is invalidated after creating a new agent."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers_cache = create_auth_headers(test_user_token, use_cache=True)
        headers_no_cache = create_auth_headers(test_user_token, use_cache=False)

        list1 = test_client.get(ENDPOINT_RE_ACT_AGENTS.format(tenant_id=tenant_id), headers=headers_cache)
        assert list1.status_code == status.HTTP_200_OK
        assert len(list1.json()) == 0

        test_client.post(
            ENDPOINT_RE_ACT_AGENTS.format(tenant_id=tenant_id),
            json={"name": "New Agent", "description": "Test"},
            headers=headers_no_cache,
        )

        list2 = test_client.get(ENDPOINT_RE_ACT_AGENTS.format(tenant_id=tenant_id), headers=headers_cache)
        assert list2.status_code == status.HTTP_200_OK
        assert len(list2.json()) == 1

    def test_list_cached_after_delete(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test that list cache is invalidated after deleting an agent."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers_cache = create_auth_headers(test_user_token, use_cache=True)
        headers_no_cache = create_auth_headers(test_user_token, use_cache=False)

        create_response = test_client.post(
            ENDPOINT_RE_ACT_AGENTS.format(tenant_id=tenant_id),
            json={"name": "Agent To Delete", "description": "Test"},
            headers=headers_no_cache,
        )
        agent_id = create_response.json()["id"]

        list1 = test_client.get(ENDPOINT_RE_ACT_AGENTS.format(tenant_id=tenant_id), headers=headers_cache)
        assert list1.status_code == status.HTTP_200_OK
        assert len(list1.json()) == 1

        test_client.delete(
            ENDPOINT_RE_ACT_AGENT_DETAIL.format(tenant_id=tenant_id, re_act_agent_id=agent_id),
            headers=headers_no_cache,
        )

        list2 = test_client.get(ENDPOINT_RE_ACT_AGENTS.format(tenant_id=tenant_id), headers=headers_cache)
        assert list2.status_code == status.HTTP_200_OK
        assert len(list2.json()) == 0

    def test_detail_cache_removed_after_delete(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test that detail cache is removed after agent deletion."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers_cache = create_auth_headers(test_user_token, use_cache=True)
        headers_no_cache = create_auth_headers(test_user_token, use_cache=False)

        create_response = test_client.post(
            ENDPOINT_RE_ACT_AGENTS.format(tenant_id=tenant_id),
            json={"name": "Agent To Delete", "description": "Test"},
            headers=headers_no_cache,
        )
        agent_id = create_response.json()["id"]

        get1 = test_client.get(
            ENDPOINT_RE_ACT_AGENT_DETAIL.format(tenant_id=tenant_id, re_act_agent_id=agent_id),
            headers=headers_cache,
        )
        assert get1.status_code == status.HTTP_200_OK

        test_client.delete(
            ENDPOINT_RE_ACT_AGENT_DETAIL.format(tenant_id=tenant_id, re_act_agent_id=agent_id),
            headers=headers_no_cache,
        )

        get2 = test_client.get(
            ENDPOINT_RE_ACT_AGENT_DETAIL.format(tenant_id=tenant_id, re_act_agent_id=agent_id),
            headers=headers_cache,
        )
        assert get2.status_code == status.HTTP_404_NOT_FOUND
