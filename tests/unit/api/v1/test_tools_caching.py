"""Tests for tools caching behavior."""

from typing import Any

from fastapi import status
from starlette.testclient import TestClient

from tests.conftest import create_auth_headers
from tests.helpers.tenant import add_user_to_tenant, create_tenant_for_user
from unifiedui.core.database.enums import PermissionActionEnum, PrincipalTypeEnum

# API Endpoints
ENDPOINT_TENANTS = "/api/v1/platform-service/tenants"
ENDPOINT_TOOLS = "/api/v1/platform-service/tenants/{tenant_id}/tools"
ENDPOINT_TOOL_DETAIL = "/api/v1/platform-service/tenants/{tenant_id}/tools/{tool_id}"
ENDPOINT_TOOL_PRINCIPALS = "/api/v1/platform-service/tenants/{tenant_id}/tools/{tool_id}/principals"

# Roles
ROLE_READ = PermissionActionEnum.READ.value
ROLE_WRITE = PermissionActionEnum.WRITE.value
ROLE_ADMIN = PermissionActionEnum.ADMIN.value

# Principal Types
PRINCIPAL_TYPE_USER = PrincipalTypeEnum.IDENTITY_USER.value


def create_tool(test_client: TestClient, tenant_id: str, headers: dict, tool_name: str = "Test Tool") -> str:
    """Helper function to create a tool and return its ID."""
    response = test_client.post(
        ENDPOINT_TOOLS.format(tenant_id=tenant_id),
        json={"name": tool_name, "description": f"Tool {tool_name}", "type": "MCP_SERVER"},
        headers=headers,
    )
    assert response.status_code == status.HTTP_201_CREATED
    return response.json()["id"]


class TestToolCaching:
    """Test suite for tool caching behavior."""

    def test_get_tool_cached_response(self, test_client: TestClient, fake_redis_client: Any) -> None:
        """Test that get tool response is cached."""
        # Create user and tenant
        user_token = test_client.create_test_user("cache-user-1", "Cache User 1")
        headers_no_cache = create_auth_headers(user_token, use_cache=False)
        headers_cache = create_auth_headers(user_token, use_cache=True)
        tenant_id = create_tenant_for_user(test_client, user_token)

        # Create tool (no cache)
        tool_id = create_tool(test_client, tenant_id, headers_no_cache, "Cached Tool 1")

        # First call should populate cache
        response1 = test_client.get(
            ENDPOINT_TOOL_DETAIL.format(tenant_id=tenant_id, tool_id=tool_id), headers=headers_cache
        )
        assert response1.status_code == status.HTTP_200_OK

        # Second call should use cache
        response2 = test_client.get(
            ENDPOINT_TOOL_DETAIL.format(tenant_id=tenant_id, tool_id=tool_id), headers=headers_cache
        )
        assert response2.status_code == status.HTTP_200_OK
        assert response1.json() == response2.json()

    def test_list_tools_cached_response(self, test_client: TestClient, fake_redis_client: Any) -> None:
        """Test that list tools response is cached."""
        # Create user and tenant
        user_token = test_client.create_test_user("cache-user-2", "Cache User 2")
        headers_no_cache = create_auth_headers(user_token, use_cache=False)
        headers_cache = create_auth_headers(user_token, use_cache=True)
        tenant_id = create_tenant_for_user(test_client, user_token)

        # Create tools (no cache)
        for i in range(3):
            create_tool(test_client, tenant_id, headers_no_cache, f"Cached Tool 2-{i}")

        # First call should populate cache
        response1 = test_client.get(ENDPOINT_TOOLS.format(tenant_id=tenant_id), headers=headers_cache)
        assert response1.status_code == status.HTTP_200_OK

        # Second call should use cache
        response2 = test_client.get(ENDPOINT_TOOLS.format(tenant_id=tenant_id), headers=headers_cache)
        assert response2.status_code == status.HTTP_200_OK
        assert len(response1.json()) == len(response2.json())

    def test_cache_invalidated_on_update(self, test_client: TestClient, fake_redis_client: Any) -> None:
        """Test that cache is invalidated when tool is updated."""
        # Create user and tenant
        user_token = test_client.create_test_user("cache-user-3", "Cache User 3")
        headers_no_cache = create_auth_headers(user_token, use_cache=False)
        headers_cache = create_auth_headers(user_token, use_cache=True)
        tenant_id = create_tenant_for_user(test_client, user_token)

        # Create tool (no cache)
        tool_id = create_tool(test_client, tenant_id, headers_no_cache, "Cache Test Tool 3")

        # Get tool to populate cache
        response1 = test_client.get(
            ENDPOINT_TOOL_DETAIL.format(tenant_id=tenant_id, tool_id=tool_id), headers=headers_cache
        )
        assert response1.status_code == status.HTTP_200_OK
        original_name = response1.json()["name"]

        # Update tool (no cache)
        new_name = "Updated Cache Test Tool 3"
        test_client.patch(
            ENDPOINT_TOOL_DETAIL.format(tenant_id=tenant_id, tool_id=tool_id),
            json={"name": new_name},
            headers=headers_no_cache,
        )

        # Get tool again (cache should be invalidated)
        response2 = test_client.get(
            ENDPOINT_TOOL_DETAIL.format(tenant_id=tenant_id, tool_id=tool_id), headers=headers_cache
        )
        assert response2.status_code == status.HTTP_200_OK
        assert response2.json()["name"] == new_name
        assert response2.json()["name"] != original_name

    def test_cache_invalidated_on_delete(self, test_client: TestClient, fake_redis_client: Any) -> None:
        """Test that cache is invalidated when tool is deleted."""
        # Create user and tenant
        user_token = test_client.create_test_user("cache-user-4", "Cache User 4")
        headers_no_cache = create_auth_headers(user_token, use_cache=False)
        headers_cache = create_auth_headers(user_token, use_cache=True)
        tenant_id = create_tenant_for_user(test_client, user_token)

        # Create tools (no cache)
        tool_id = create_tool(test_client, tenant_id, headers_no_cache, "Cache Test Tool 4")

        # List tools to populate cache
        response1 = test_client.get(ENDPOINT_TOOLS.format(tenant_id=tenant_id), headers=headers_cache)
        assert response1.status_code == status.HTTP_200_OK
        initial_count = len(response1.json())

        # Delete tool (no cache)
        test_client.delete(ENDPOINT_TOOL_DETAIL.format(tenant_id=tenant_id, tool_id=tool_id), headers=headers_no_cache)

        # List tools again (cache should be invalidated)
        response2 = test_client.get(ENDPOINT_TOOLS.format(tenant_id=tenant_id), headers=headers_cache)
        assert response2.status_code == status.HTTP_200_OK
        assert len(response2.json()) == initial_count - 1

    def test_cache_invalidated_on_principal_change(self, test_client: TestClient, fake_redis_client: Any) -> None:
        """Test that cache is invalidated when principals are changed."""
        # Create owner with tenant and tool
        owner_token = test_client.create_test_user("cache-owner-5", "Cache Owner 5")
        owner_headers_no_cache = create_auth_headers(owner_token, use_cache=False)
        create_auth_headers(owner_token, use_cache=True)
        tenant_id = create_tenant_for_user(test_client, owner_token)
        tool_id = create_tool(test_client, tenant_id, owner_headers_no_cache, "Cache Test Tool 5")

        # Create other user
        other_user_token = test_client.create_test_user("cache-other-5", "Cache Other 5")
        other_user_headers = create_auth_headers(other_user_token, use_cache=True)
        add_user_to_tenant(test_client, tenant_id, owner_headers_no_cache, other_user_token.get_id())

        # Other user cannot access tool initially
        response1 = test_client.get(
            ENDPOINT_TOOL_DETAIL.format(tenant_id=tenant_id, tool_id=tool_id), headers=other_user_headers
        )
        assert response1.status_code == status.HTTP_403_FORBIDDEN

        # Add other user to tool
        test_client.put(
            ENDPOINT_TOOL_PRINCIPALS.format(tenant_id=tenant_id, tool_id=tool_id),
            json={"principal_id": other_user_token.get_id(), "principal_type": PRINCIPAL_TYPE_USER, "role": ROLE_READ},
            headers=owner_headers_no_cache,
        )

        # Other user should now be able to access tool
        response2 = test_client.get(
            ENDPOINT_TOOL_DETAIL.format(tenant_id=tenant_id, tool_id=tool_id), headers=other_user_headers
        )
        assert response2.status_code == status.HTTP_200_OK

    def test_no_cache_header_bypasses_cache(self, test_client: TestClient, fake_redis_client: Any) -> None:
        """Test that X-Use-Cache: false header bypasses cache."""
        # Create user and tenant
        user_token = test_client.create_test_user("cache-user-6", "Cache User 6")
        headers_no_cache = create_auth_headers(user_token, use_cache=False)
        headers_cache = create_auth_headers(user_token, use_cache=True)
        tenant_id = create_tenant_for_user(test_client, user_token)

        # Create tool
        tool_id = create_tool(test_client, tenant_id, headers_no_cache, "Cache Test Tool 6")

        # Get with cache
        response1 = test_client.get(
            ENDPOINT_TOOL_DETAIL.format(tenant_id=tenant_id, tool_id=tool_id), headers=headers_cache
        )
        assert response1.status_code == status.HTTP_200_OK

        # Direct database update bypassing API (simulated by updating without cache)
        new_name = "Directly Updated Tool 6"
        test_client.patch(
            ENDPOINT_TOOL_DETAIL.format(tenant_id=tenant_id, tool_id=tool_id),
            json={"name": new_name},
            headers=headers_no_cache,
        )

        # Get without cache should get updated value
        response2 = test_client.get(
            ENDPOINT_TOOL_DETAIL.format(tenant_id=tenant_id, tool_id=tool_id), headers=headers_no_cache
        )
        assert response2.status_code == status.HTTP_200_OK
        assert response2.json()["name"] == new_name

    def test_cache_key_includes_query_params(self, test_client: TestClient, fake_redis_client: Any) -> None:
        """Test that cache key includes query parameters for different results."""
        # Create user and tenant
        user_token = test_client.create_test_user("cache-user-7", "Cache User 7")
        headers_no_cache = create_auth_headers(user_token, use_cache=False)
        headers_cache = create_auth_headers(user_token, use_cache=True)
        tenant_id = create_tenant_for_user(test_client, user_token)

        # Create tools with different names
        for name in ["Alpha Tool", "Beta Tool", "Gamma Tool"]:
            create_tool(test_client, tenant_id, headers_no_cache, name)

        # List all tools
        response_all = test_client.get(ENDPOINT_TOOLS.format(tenant_id=tenant_id), headers=headers_cache)
        assert response_all.status_code == status.HTTP_200_OK
        all_count = len(response_all.json())

        # List filtered tools
        response_filtered = test_client.get(
            ENDPOINT_TOOLS.format(tenant_id=tenant_id) + "?name=Alpha", headers=headers_cache
        )
        assert response_filtered.status_code == status.HTTP_200_OK
        filtered_count = len(response_filtered.json())

        # Counts should be different
        assert all_count > filtered_count
        assert filtered_count >= 1

    def test_create_tool_does_not_cache(self, test_client: TestClient, fake_redis_client: Any) -> None:
        """Test that create tool operation doesn't use cache."""
        # Create user and tenant
        user_token = test_client.create_test_user("cache-user-8", "Cache User 8")
        headers_no_cache = create_auth_headers(user_token, use_cache=False)
        headers_cache = create_auth_headers(user_token, use_cache=True)
        tenant_id = create_tenant_for_user(test_client, user_token)

        # Create tool with cache header (should still work)
        response = test_client.post(
            ENDPOINT_TOOLS.format(tenant_id=tenant_id),
            json={"name": "Cache Create Test Tool 8", "type": "MCP_SERVER"},
            headers=headers_cache,
        )
        assert response.status_code == status.HTTP_201_CREATED

        # Verify tool was created
        tool_id = response.json()["id"]
        get_response = test_client.get(
            ENDPOINT_TOOL_DETAIL.format(tenant_id=tenant_id, tool_id=tool_id), headers=headers_no_cache
        )
        assert get_response.status_code == status.HTTP_200_OK

    def test_cache_per_user_isolation(self, test_client: TestClient, fake_redis_client: Any) -> None:
        """Test that cache is isolated per user for permission-based results."""
        # Create owner with tenant and tools
        owner_token = test_client.create_test_user("cache-owner-9", "Cache Owner 9")
        owner_headers_no_cache = create_auth_headers(owner_token, use_cache=False)
        owner_headers_cache = create_auth_headers(owner_token, use_cache=True)
        tenant_id = create_tenant_for_user(test_client, owner_token)

        # Create 3 tools
        tool_ids = []
        for i in range(3):
            tool_id = create_tool(test_client, tenant_id, owner_headers_no_cache, f"Cache Test Tool 9-{i}")
            tool_ids.append(tool_id)

        # Create another user with access to only 1 tool
        other_user_token = test_client.create_test_user("cache-other-9", "Cache Other 9")
        other_user_headers_cache = create_auth_headers(other_user_token, use_cache=True)
        add_user_to_tenant(test_client, tenant_id, owner_headers_no_cache, other_user_token.get_id())

        # Add other user to one tool only
        test_client.put(
            ENDPOINT_TOOL_PRINCIPALS.format(tenant_id=tenant_id, tool_id=tool_ids[0]),
            json={"principal_id": other_user_token.get_id(), "principal_type": PRINCIPAL_TYPE_USER, "role": ROLE_READ},
            headers=owner_headers_no_cache,
        )

        # Owner should see all 3 tools
        owner_response = test_client.get(ENDPOINT_TOOLS.format(tenant_id=tenant_id), headers=owner_headers_cache)
        assert owner_response.status_code == status.HTTP_200_OK
        assert len(owner_response.json()) == 3

        # Other user should see only 1 tool
        other_response = test_client.get(ENDPOINT_TOOLS.format(tenant_id=tenant_id), headers=other_user_headers_cache)
        assert other_response.status_code == status.HTTP_200_OK
        assert len(other_response.json()) == 1
