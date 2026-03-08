"""Tests for tools API endpoints."""

from typing import Any

from fastapi import status
from starlette.testclient import TestClient

from tests.conftest import create_auth_headers
from tests.helpers.tenant import create_tenant_for_user
from unifiedui.core.database.enums import PermissionActionEnum, PrincipalTypeEnum

# API Endpoints
ENDPOINT_TOOLS = "/api/v1/platform-service/tenants/{tenant_id}/tools"
ENDPOINT_TOOL_DETAIL = "/api/v1/platform-service/tenants/{tenant_id}/tools/{tool_id}"
ENDPOINT_TOOL_PRINCIPALS = "/api/v1/platform-service/tenants/{tenant_id}/tools/{tool_id}/principals"
ENDPOINT_PRINCIPAL_DETAIL = "/api/v1/platform-service/tenants/{tenant_id}/tools/{tool_id}/principals/{principal_id}"

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


class TestToolRoutes:
    """Test suite for tool API routes."""

    def test_create_tool_success(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test successful tool creation."""
        # Create a tenant first
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        # Create tool
        tool_data = {"name": "Test MCP Server", "description": "A test MCP server tool", "type": "MCP_SERVER"}

        response = test_client.post(ENDPOINT_TOOLS.format(tenant_id=tenant_id), json=tool_data, headers=headers)

        if response.status_code != status.HTTP_201_CREATED:
            print(f"Response status: {response.status_code}")
            print(f"Response body: {response.json()}")
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()

        assert data["name"] == tool_data["name"]
        assert data["description"] == tool_data["description"]
        assert data["type"] == tool_data["type"]
        assert not data["is_active"]
        assert "id" in data
        assert data["tenant_id"] == tenant_id
        assert "created_at" in data
        assert "updated_at" in data
        assert data["created_by"] == test_user_token.get_id()

    def test_create_tool_openapi_definition(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test tool creation with OPENAPI_DEFINITION type."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        tool_data = {
            "name": "Test OpenAPI Tool",
            "description": "An OpenAPI definition tool",
            "type": "OPENAPI_DEFINITION",
        }

        response = test_client.post(ENDPOINT_TOOLS.format(tenant_id=tenant_id), json=tool_data, headers=headers)

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["type"] == "OPENAPI_DEFINITION"

    def test_create_tool_missing_name(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test tool creation with missing name."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        response = test_client.post(
            ENDPOINT_TOOLS.format(tenant_id=tenant_id),
            json={"description": "Test tool", "type": "MCP_SERVER"},
            headers=headers,
        )

        assert response.status_code == 422

    def test_create_tool_invalid_name_type(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test tool creation with invalid name type."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        response = test_client.post(
            ENDPOINT_TOOLS.format(tenant_id=tenant_id), json={"name": 123, "type": "MCP_SERVER"}, headers=headers
        )

        assert response.status_code == 422

    def test_create_tool_empty_name(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test tool creation with empty name."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        response = test_client.post(
            ENDPOINT_TOOLS.format(tenant_id=tenant_id), json={"name": "", "type": "MCP_SERVER"}, headers=headers
        )

        assert response.status_code == 422

    def test_create_tool_missing_type(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test tool creation with missing type."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        response = test_client.post(
            ENDPOINT_TOOLS.format(tenant_id=tenant_id), json={"name": "Test Tool"}, headers=headers
        )

        assert response.status_code == 422

    def test_create_tool_invalid_type(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test tool creation with invalid type."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        response = test_client.post(
            ENDPOINT_TOOLS.format(tenant_id=tenant_id),
            json={"name": "Test Tool", "type": "INVALID_TYPE"},
            headers=headers,
        )

        assert response.status_code == 422

    def test_create_tool_empty_body(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test tool creation with empty JSON body."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        response = test_client.post(ENDPOINT_TOOLS.format(tenant_id=tenant_id), json={}, headers=headers)

        assert response.status_code == 422

    def test_create_tool_without_permission(self, test_client: TestClient) -> None:
        """Test that user without tenant membership cannot create tools."""
        # Create user1 with a tenant
        user1_token = test_client.create_test_user("tool-user-1", "User One")
        tenant_id = create_tenant_for_user(test_client, user1_token)

        # Create user2 (not a member of the tenant)
        user2_token = test_client.create_test_user("tool-user-2", "User Two")
        headers2 = create_auth_headers(user2_token, use_cache=False)

        # Try to create tool as user2 (should fail - no tenant membership)
        response = test_client.post(
            ENDPOINT_TOOLS.format(tenant_id=tenant_id),
            json={"name": "Unauthorized Tool", "type": "MCP_SERVER"},
            headers=headers2,
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_get_tool_success(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test successful tool retrieval."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        # Create a tool
        tool_data = {"name": "Test Tool", "description": "Test description", "type": "MCP_SERVER"}
        create_response = test_client.post(ENDPOINT_TOOLS.format(tenant_id=tenant_id), json=tool_data, headers=headers)
        tool_id = create_response.json()["id"]

        # Retrieve the tool
        response = test_client.get(ENDPOINT_TOOL_DETAIL.format(tenant_id=tenant_id, tool_id=tool_id), headers=headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["id"] == tool_id
        assert data["name"] == tool_data["name"]
        assert data["description"] == tool_data["description"]
        assert data["type"] == tool_data["type"]

    def test_get_tool_not_found(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test tool retrieval with non-existent ID."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        response = test_client.get(
            ENDPOINT_TOOL_DETAIL.format(tenant_id=tenant_id, tool_id=NON_EXISTENT_ID), headers=headers
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_list_tools_empty(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test listing tools when none exist."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        response = test_client.get(ENDPOINT_TOOLS.format(tenant_id=tenant_id), headers=headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert isinstance(data, list)
        assert len(data) == 0

    def test_list_tools_with_data(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test listing tools with existing data."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        # Create multiple tools
        tool1_data = {"name": "Tool 1", "type": "MCP_SERVER"}
        tool2_data = {"name": "Tool 2", "type": "OPENAPI_DEFINITION"}

        test_client.post(ENDPOINT_TOOLS.format(tenant_id=tenant_id), json=tool1_data, headers=headers)
        test_client.post(ENDPOINT_TOOLS.format(tenant_id=tenant_id), json=tool2_data, headers=headers)

        # List tools
        response = test_client.get(ENDPOINT_TOOLS.format(tenant_id=tenant_id), headers=headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert isinstance(data, list)
        assert len(data) == 2

        names = [tool["name"] for tool in data]
        assert "Tool 1" in names
        assert "Tool 2" in names

    def test_list_tools_with_pagination(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test listing tools with pagination parameters."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        # Create multiple tools
        for i in range(5):
            test_client.post(
                ENDPOINT_TOOLS.format(tenant_id=tenant_id),
                json={"name": f"Tool {i}", "type": "MCP_SERVER"},
                headers=headers,
            )

        # Test with limit
        response = test_client.get(f"{ENDPOINT_TOOLS.format(tenant_id=tenant_id)}?limit=3", headers=headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 3

        # Test with skip
        response = test_client.get(f"{ENDPOINT_TOOLS.format(tenant_id=tenant_id)}?skip=2&limit=2", headers=headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 2

    def test_list_tools_with_name_filter(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test listing tools with name filter."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        # Create tools with different names
        test_client.post(
            ENDPOINT_TOOLS.format(tenant_id=tenant_id),
            json={"name": "Production MCP Server", "type": "MCP_SERVER"},
            headers=headers,
        )
        test_client.post(
            ENDPOINT_TOOLS.format(tenant_id=tenant_id),
            json={"name": "Development API Tool", "type": "OPENAPI_DEFINITION"},
            headers=headers,
        )
        test_client.post(
            ENDPOINT_TOOLS.format(tenant_id=tenant_id),
            json={"name": "QA MCP Server", "type": "MCP_SERVER"},
            headers=headers,
        )

        # Filter by name
        response = test_client.get(
            f"{ENDPOINT_TOOLS.format(tenant_id=tenant_id)}?name_filter=Development", headers=headers
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert len(data) >= 1
        assert any(tool["name"] == "Development API Tool" for tool in data)

    def test_list_tools_with_quick_list_view(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test listing tools with quick-list view returns only id and name."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        # Create tools
        test_client.post(
            ENDPOINT_TOOLS.format(tenant_id=tenant_id),
            json={"name": "Tool One", "description": "First tool", "type": "MCP_SERVER"},
            headers=headers,
        )
        test_client.post(
            ENDPOINT_TOOLS.format(tenant_id=tenant_id),
            json={"name": "Tool Two", "description": "Second tool", "type": "OPENAPI_DEFINITION"},
            headers=headers,
        )

        # Get with quick-list view
        response = test_client.get(f"{ENDPOINT_TOOLS.format(tenant_id=tenant_id)}?view=quick-list", headers=headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 2

        # Verify only id and name are returned
        for item in data:
            assert "id" in item
            assert "name" in item
            # These fields should NOT be present in quick-list view
            assert "description" not in item
            assert "type" not in item
            assert "tenant_id" not in item
            assert "created_at" not in item
            assert "updated_at" not in item
            assert "created_by" not in item
            assert "updated_by" not in item
            assert "is_active" not in item

    def test_update_tool_success(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test successful tool update."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        # Create a tool
        create_response = test_client.post(
            ENDPOINT_TOOLS.format(tenant_id=tenant_id),
            json={"name": "Original Name", "description": "Original description", "type": "MCP_SERVER"},
            headers=headers,
        )
        tool_id = create_response.json()["id"]

        # Update the tool
        update_response = test_client.patch(
            ENDPOINT_TOOL_DETAIL.format(tenant_id=tenant_id, tool_id=tool_id),
            json={"name": "Updated Name", "description": "Updated description"},
            headers=headers,
        )

        assert update_response.status_code == status.HTTP_200_OK
        data = update_response.json()

        assert data["name"] == "Updated Name"
        assert data["description"] == "Updated description"
        assert data["id"] == tool_id

    def test_update_tool_not_found(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test tool update with non-existent ID."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        response = test_client.patch(
            ENDPOINT_TOOL_DETAIL.format(tenant_id=tenant_id, tool_id=NON_EXISTENT_ID),
            json={"name": "New Name"},
            headers=headers,
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_update_tool_is_active(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test updating tool is_active status."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        # Create tool (default is_active=False)
        create_response = test_client.post(
            ENDPOINT_TOOLS.format(tenant_id=tenant_id),
            json={"name": "Test Tool", "description": "Test", "type": "MCP_SERVER"},
            headers=headers,
        )
        tool_id = create_response.json()["id"]
        assert not create_response.json()["is_active"]

        # Update is_active to True
        update_response = test_client.patch(
            ENDPOINT_TOOL_DETAIL.format(tenant_id=tenant_id, tool_id=tool_id), json={"is_active": True}, headers=headers
        )

        assert update_response.status_code == status.HTTP_200_OK
        assert update_response.json()["is_active"]

        # Verify via GET
        get_response = test_client.get(
            ENDPOINT_TOOL_DETAIL.format(tenant_id=tenant_id, tool_id=tool_id), headers=headers
        )
        assert get_response.json()["is_active"]

    def test_delete_tool_success(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test successful tool deletion."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        # Create a tool
        create_response = test_client.post(
            ENDPOINT_TOOLS.format(tenant_id=tenant_id),
            json={"name": "Tool to delete", "type": "MCP_SERVER"},
            headers=headers,
        )
        tool_id = create_response.json()["id"]

        # Delete the tool
        delete_response = test_client.delete(
            ENDPOINT_TOOL_DETAIL.format(tenant_id=tenant_id, tool_id=tool_id), headers=headers
        )

        assert delete_response.status_code == status.HTTP_204_NO_CONTENT

        # Verify tool no longer exists
        get_response = test_client.get(
            ENDPOINT_TOOL_DETAIL.format(tenant_id=tenant_id, tool_id=tool_id), headers=headers
        )

        assert get_response.status_code == status.HTTP_404_NOT_FOUND

    def test_delete_tool_not_found(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test tool deletion with non-existent ID."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        response = test_client.delete(
            ENDPOINT_TOOL_DETAIL.format(tenant_id=tenant_id, tool_id=NON_EXISTENT_ID), headers=headers
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestToolPrincipals:
    """Test suite for tool principals (permissions) management."""

    def test_creator_becomes_admin(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test that tool creator automatically becomes ADMIN."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        # Create tool
        create_response = test_client.post(
            ENDPOINT_TOOLS.format(tenant_id=tenant_id),
            json={"name": "Creator Test Tool", "type": "MCP_SERVER"},
            headers=headers,
        )
        tool_id = create_response.json()["id"]

        # Check permissions
        principals_response = test_client.get(
            ENDPOINT_TOOL_PRINCIPALS.format(tenant_id=tenant_id, tool_id=tool_id), headers=headers
        )

        assert principals_response.status_code == status.HTTP_200_OK
        data = principals_response.json()

        # Find creator in principals
        creator_principal = None
        for p in data.get("principals", data):
            if p["principal_id"] == test_user_token.get_id():
                creator_principal = p
                break

        assert creator_principal is not None
        assert ROLE_ADMIN in creator_principal.get("roles", []) or creator_principal.get("role") == ROLE_ADMIN

    def test_list_principals_empty_except_creator(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test listing principals on a tool with only creator."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        # Create tool
        create_response = test_client.post(
            ENDPOINT_TOOLS.format(tenant_id=tenant_id),
            json={"name": "Principals Test Tool", "type": "MCP_SERVER"},
            headers=headers,
        )
        tool_id = create_response.json()["id"]

        # List principals
        response = test_client.get(
            ENDPOINT_TOOL_PRINCIPALS.format(tenant_id=tenant_id, tool_id=tool_id), headers=headers
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Should have at least the creator
        principals = data.get("principals", data)
        assert len(principals) >= 1

    def test_add_principal_success(self, test_client: TestClient) -> None:
        """Test adding a new principal to a tool."""
        # Create owner with tenant and tool
        owner_token = test_client.create_test_user("tool-owner-3", "Tool Owner")
        owner_headers = create_auth_headers(owner_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, owner_token)

        # Create tool
        create_response = test_client.post(
            ENDPOINT_TOOLS.format(tenant_id=tenant_id),
            json={"name": "Principal Test Tool", "type": "MCP_SERVER"},
            headers=owner_headers,
        )
        tool_id = create_response.json()["id"]

        # Create another user and add to tenant
        other_user_token = test_client.create_test_user("tool-reader-3", "Tool Reader")

        # Add other user to tenant first
        test_client.put(
            f"/api/v1/platform-service/tenants/{tenant_id}/principals",
            json={"principal_id": other_user_token.get_id(), "principal_type": PRINCIPAL_TYPE_USER, "role": "READER"},
            headers=owner_headers,
        )

        # Add other user as principal to tool
        add_response = test_client.put(
            ENDPOINT_TOOL_PRINCIPALS.format(tenant_id=tenant_id, tool_id=tool_id),
            json={"principal_id": other_user_token.get_id(), "principal_type": PRINCIPAL_TYPE_USER, "role": ROLE_READ},
            headers=owner_headers,
        )

        assert add_response.status_code == status.HTTP_200_OK

    def test_get_principal_detail(self, test_client: TestClient) -> None:
        """Test getting details of a specific principal."""
        owner_token = test_client.create_test_user("tool-owner-4", "Tool Owner")
        owner_headers = create_auth_headers(owner_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, owner_token)

        # Create tool
        create_response = test_client.post(
            ENDPOINT_TOOLS.format(tenant_id=tenant_id),
            json={"name": "Principal Detail Test", "type": "MCP_SERVER"},
            headers=owner_headers,
        )
        tool_id = create_response.json()["id"]

        # Get principal detail
        response = test_client.get(
            ENDPOINT_PRINCIPAL_DETAIL.format(tenant_id=tenant_id, tool_id=tool_id, principal_id=owner_token.get_id()),
            headers=owner_headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["principal_id"] == owner_token.get_id()

    def test_delete_principal_success(self, test_client: TestClient) -> None:
        """Test removing a principal from a tool."""
        owner_token = test_client.create_test_user("tool-owner-5", "Tool Owner")
        owner_headers = create_auth_headers(owner_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, owner_token)

        # Create tool
        create_response = test_client.post(
            ENDPOINT_TOOLS.format(tenant_id=tenant_id),
            json={"name": "Delete Principal Test", "type": "MCP_SERVER"},
            headers=owner_headers,
        )
        tool_id = create_response.json()["id"]

        # Create and add another user
        other_user_token = test_client.create_test_user("tool-reader-5", "Tool Reader")

        # Add other user to tenant first
        test_client.put(
            f"/api/v1/platform-service/tenants/{tenant_id}/principals",
            json={"principal_id": other_user_token.get_id(), "principal_type": PRINCIPAL_TYPE_USER, "role": "READER"},
            headers=owner_headers,
        )

        # Add as principal to tool
        test_client.put(
            ENDPOINT_TOOL_PRINCIPALS.format(tenant_id=tenant_id, tool_id=tool_id),
            json={"principal_id": other_user_token.get_id(), "principal_type": PRINCIPAL_TYPE_USER, "role": ROLE_READ},
            headers=owner_headers,
        )

        # Delete principal
        delete_response = test_client.delete(
            ENDPOINT_PRINCIPAL_DETAIL.format(
                tenant_id=tenant_id, tool_id=tool_id, principal_id=other_user_token.get_id()
            )
            + f"?principal_type={PRINCIPAL_TYPE_USER}&permission={ROLE_READ}",
            headers=owner_headers,
        )

        assert delete_response.status_code == status.HTTP_204_NO_CONTENT

        # Verify principal is gone
        get_response = test_client.get(
            ENDPOINT_PRINCIPAL_DETAIL.format(
                tenant_id=tenant_id, tool_id=tool_id, principal_id=other_user_token.get_id()
            ),
            headers=owner_headers,
        )

        assert get_response.status_code == status.HTTP_404_NOT_FOUND
