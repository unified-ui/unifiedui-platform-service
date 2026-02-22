"""Tests for tools RBAC (Role-Based Access Control)."""

from typing import Any

from fastapi import status
from starlette.testclient import TestClient

from tests.conftest import create_auth_headers
from unifiedui.core.database.enums import PermissionActionEnum, PrincipalTypeEnum

# API Endpoints
ENDPOINT_TENANTS = "/api/v1/platform-service/tenants"
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


def create_tenant_for_user(test_client: TestClient, user_token: Any, tenant_name: str = "Test Tenant") -> str:
    """Helper function to create a tenant and return its ID."""
    headers = create_auth_headers(user_token, use_cache=False)
    response = test_client.post(
        ENDPOINT_TENANTS,
        json={"name": tenant_name, "description": f"Tenant for {user_token.get_id()}"},
        headers=headers,
    )
    assert response.status_code == status.HTTP_201_CREATED
    return response.json()["id"]


def create_tool(test_client: TestClient, tenant_id: str, headers: dict, tool_name: str = "Test Tool") -> str:
    """Helper function to create a tool and return its ID."""
    response = test_client.post(
        ENDPOINT_TOOLS.format(tenant_id=tenant_id),
        json={"name": tool_name, "description": f"Tool {tool_name}", "type": "MCP_SERVER"},
        headers=headers,
    )
    assert response.status_code == status.HTTP_201_CREATED
    return response.json()["id"]


def add_user_to_tenant(
    test_client: TestClient, tenant_id: str, admin_headers: dict, user_id: str, role: str = "READER"
) -> None:
    """Helper function to add a user to a tenant."""
    response = test_client.put(
        f"/api/v1/platform-service/tenants/{tenant_id}/principals",
        json={"principal_id": user_id, "principal_type": PRINCIPAL_TYPE_USER, "role": role},
        headers=admin_headers,
    )
    assert response.status_code == status.HTTP_200_OK


class TestToolRBAC:
    """Test suite for tool role-based access control."""

    def test_creator_becomes_admin(self, test_client: TestClient) -> None:
        """Test that tool creator automatically becomes ADMIN."""
        # Create user and tenant
        user_token = test_client.create_test_user("rbac-creator-user", "Creator User")
        headers = create_auth_headers(user_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, user_token)

        # Create tool
        tool_id = create_tool(test_client, tenant_id, headers, "Creator Test Tool")

        # Verify creator has ADMIN role
        principals_response = test_client.get(
            ENDPOINT_PRINCIPAL_DETAIL.format(tenant_id=tenant_id, tool_id=tool_id, principal_id="rbac-creator-user"),
            headers=headers,
        )

        assert principals_response.status_code == status.HTTP_200_OK
        data = principals_response.json()
        assert data["principal_id"] == "rbac-creator-user"
        assert ROLE_ADMIN in data["roles"]

    def test_read_role_can_view_tool(self, test_client: TestClient) -> None:
        """Test that user with READ role can view tool."""
        # Create owner with tenant and tool
        owner_token = test_client.create_test_user("rbac-owner-1", "Tool Owner")
        owner_headers = create_auth_headers(owner_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, owner_token)
        tool_id = create_tool(test_client, tenant_id, owner_headers, "RBAC Test Tool")

        # Create reader user and add to tenant
        reader_token = test_client.create_test_user("rbac-reader-1", "Tool Reader")
        reader_headers = create_auth_headers(reader_token, use_cache=False)
        add_user_to_tenant(test_client, tenant_id, owner_headers, reader_token.get_id())

        # Add reader to tool with READ role
        test_client.put(
            ENDPOINT_TOOL_PRINCIPALS.format(tenant_id=tenant_id, tool_id=tool_id),
            json={"principal_id": reader_token.get_id(), "principal_type": PRINCIPAL_TYPE_USER, "role": ROLE_READ},
            headers=owner_headers,
        )

        # Reader should be able to view tool
        response = test_client.get(
            ENDPOINT_TOOL_DETAIL.format(tenant_id=tenant_id, tool_id=tool_id), headers=reader_headers
        )

        assert response.status_code == status.HTTP_200_OK

    def test_read_role_cannot_update_tool(self, test_client: TestClient) -> None:
        """Test that user with READ role cannot update tool."""
        # Create owner with tenant and tool
        owner_token = test_client.create_test_user("rbac-owner-2", "Tool Owner")
        owner_headers = create_auth_headers(owner_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, owner_token)
        tool_id = create_tool(test_client, tenant_id, owner_headers, "RBAC Test Tool 2")

        # Create reader user and add to tenant
        reader_token = test_client.create_test_user("rbac-reader-2", "Tool Reader")
        reader_headers = create_auth_headers(reader_token, use_cache=False)
        add_user_to_tenant(test_client, tenant_id, owner_headers, reader_token.get_id())

        # Add reader to tool with READ role
        test_client.put(
            ENDPOINT_TOOL_PRINCIPALS.format(tenant_id=tenant_id, tool_id=tool_id),
            json={"principal_id": reader_token.get_id(), "principal_type": PRINCIPAL_TYPE_USER, "role": ROLE_READ},
            headers=owner_headers,
        )

        # Reader should NOT be able to update tool
        response = test_client.patch(
            ENDPOINT_TOOL_DETAIL.format(tenant_id=tenant_id, tool_id=tool_id),
            json={"name": "Unauthorized Update"},
            headers=reader_headers,
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_write_role_can_update_tool(self, test_client: TestClient) -> None:
        """Test that user with WRITE role can update tool."""
        # Create owner with tenant and tool
        owner_token = test_client.create_test_user("rbac-owner-3", "Tool Owner")
        owner_headers = create_auth_headers(owner_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, owner_token)
        tool_id = create_tool(test_client, tenant_id, owner_headers, "RBAC Test Tool 3")

        # Create writer user and add to tenant
        writer_token = test_client.create_test_user("rbac-writer-3", "Tool Writer")
        writer_headers = create_auth_headers(writer_token, use_cache=False)
        add_user_to_tenant(test_client, tenant_id, owner_headers, writer_token.get_id())

        # Add writer to tool with WRITE role
        test_client.put(
            ENDPOINT_TOOL_PRINCIPALS.format(tenant_id=tenant_id, tool_id=tool_id),
            json={"principal_id": writer_token.get_id(), "principal_type": PRINCIPAL_TYPE_USER, "role": ROLE_WRITE},
            headers=owner_headers,
        )

        # Writer should be able to update tool
        response = test_client.patch(
            ENDPOINT_TOOL_DETAIL.format(tenant_id=tenant_id, tool_id=tool_id),
            json={"name": "Writer Updated Name"},
            headers=writer_headers,
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["name"] == "Writer Updated Name"

    def test_write_role_cannot_delete_tool(self, test_client: TestClient) -> None:
        """Test that user with WRITE role cannot delete tool."""
        # Create owner with tenant and tool
        owner_token = test_client.create_test_user("rbac-owner-4", "Tool Owner")
        owner_headers = create_auth_headers(owner_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, owner_token)
        tool_id = create_tool(test_client, tenant_id, owner_headers, "RBAC Test Tool 4")

        # Create writer user and add to tenant
        writer_token = test_client.create_test_user("rbac-writer-4", "Tool Writer")
        writer_headers = create_auth_headers(writer_token, use_cache=False)
        add_user_to_tenant(test_client, tenant_id, owner_headers, writer_token.get_id())

        # Add writer to tool with WRITE role
        test_client.put(
            ENDPOINT_TOOL_PRINCIPALS.format(tenant_id=tenant_id, tool_id=tool_id),
            json={"principal_id": writer_token.get_id(), "principal_type": PRINCIPAL_TYPE_USER, "role": ROLE_WRITE},
            headers=owner_headers,
        )

        # Writer should NOT be able to delete tool
        response = test_client.delete(
            ENDPOINT_TOOL_DETAIL.format(tenant_id=tenant_id, tool_id=tool_id), headers=writer_headers
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_admin_role_can_delete_tool(self, test_client: TestClient) -> None:
        """Test that user with ADMIN role can delete tool."""
        # Create owner with tenant and tool
        owner_token = test_client.create_test_user("rbac-owner-5", "Tool Owner")
        owner_headers = create_auth_headers(owner_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, owner_token)
        tool_id = create_tool(test_client, tenant_id, owner_headers, "RBAC Test Tool 5")

        # Create admin user and add to tenant
        admin_token = test_client.create_test_user("rbac-admin-5", "Tool Admin")
        admin_headers = create_auth_headers(admin_token, use_cache=False)
        add_user_to_tenant(test_client, tenant_id, owner_headers, admin_token.get_id())

        # Add admin to tool with ADMIN role
        test_client.put(
            ENDPOINT_TOOL_PRINCIPALS.format(tenant_id=tenant_id, tool_id=tool_id),
            json={"principal_id": admin_token.get_id(), "principal_type": PRINCIPAL_TYPE_USER, "role": ROLE_ADMIN},
            headers=owner_headers,
        )

        # Admin should be able to delete tool
        response = test_client.delete(
            ENDPOINT_TOOL_DETAIL.format(tenant_id=tenant_id, tool_id=tool_id), headers=admin_headers
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_admin_role_can_manage_principals(self, test_client: TestClient) -> None:
        """Test that user with ADMIN role can manage principals."""
        # Create owner with tenant and tool
        owner_token = test_client.create_test_user("rbac-owner-6", "Tool Owner")
        owner_headers = create_auth_headers(owner_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, owner_token)
        tool_id = create_tool(test_client, tenant_id, owner_headers, "RBAC Test Tool 6")

        # Create admin user and add to tenant
        admin_token = test_client.create_test_user("rbac-admin-6", "Tool Admin")
        admin_headers = create_auth_headers(admin_token, use_cache=False)
        add_user_to_tenant(test_client, tenant_id, owner_headers, admin_token.get_id())

        # Add admin to tool with ADMIN role
        test_client.put(
            ENDPOINT_TOOL_PRINCIPALS.format(tenant_id=tenant_id, tool_id=tool_id),
            json={"principal_id": admin_token.get_id(), "principal_type": PRINCIPAL_TYPE_USER, "role": ROLE_ADMIN},
            headers=owner_headers,
        )

        # Create a third user to add
        other_user_token = test_client.create_test_user("rbac-other-6", "Other User")
        add_user_to_tenant(test_client, tenant_id, owner_headers, other_user_token.get_id())

        # Admin should be able to add principals
        response = test_client.put(
            ENDPOINT_TOOL_PRINCIPALS.format(tenant_id=tenant_id, tool_id=tool_id),
            json={"principal_id": other_user_token.get_id(), "principal_type": PRINCIPAL_TYPE_USER, "role": ROLE_READ},
            headers=admin_headers,
        )

        assert response.status_code == status.HTTP_200_OK

    def test_write_role_cannot_manage_principals(self, test_client: TestClient) -> None:
        """Test that user with WRITE role cannot manage principals."""
        # Create owner with tenant and tool
        owner_token = test_client.create_test_user("rbac-owner-7", "Tool Owner")
        owner_headers = create_auth_headers(owner_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, owner_token)
        tool_id = create_tool(test_client, tenant_id, owner_headers, "RBAC Test Tool 7")

        # Create writer user and add to tenant
        writer_token = test_client.create_test_user("rbac-writer-7", "Tool Writer")
        writer_headers = create_auth_headers(writer_token, use_cache=False)
        add_user_to_tenant(test_client, tenant_id, owner_headers, writer_token.get_id())

        # Add writer to tool with WRITE role
        test_client.put(
            ENDPOINT_TOOL_PRINCIPALS.format(tenant_id=tenant_id, tool_id=tool_id),
            json={"principal_id": writer_token.get_id(), "principal_type": PRINCIPAL_TYPE_USER, "role": ROLE_WRITE},
            headers=owner_headers,
        )

        # Create a third user to add
        other_user_token = test_client.create_test_user("rbac-other-7", "Other User")
        add_user_to_tenant(test_client, tenant_id, owner_headers, other_user_token.get_id())

        # Writer should NOT be able to add principals
        response = test_client.put(
            ENDPOINT_TOOL_PRINCIPALS.format(tenant_id=tenant_id, tool_id=tool_id),
            json={"principal_id": other_user_token.get_id(), "principal_type": PRINCIPAL_TYPE_USER, "role": ROLE_READ},
            headers=writer_headers,
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_no_permission_cannot_access_tool(self, test_client: TestClient) -> None:
        """Test that user without permission cannot access tool."""
        # Create owner with tenant and tool
        owner_token = test_client.create_test_user("rbac-owner-8", "Tool Owner")
        owner_headers = create_auth_headers(owner_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, owner_token)
        tool_id = create_tool(test_client, tenant_id, owner_headers, "RBAC Test Tool 8")

        # Create other user and add to tenant (but NOT to tool)
        other_user_token = test_client.create_test_user("rbac-other-8", "Other User")
        other_user_headers = create_auth_headers(other_user_token, use_cache=False)
        add_user_to_tenant(test_client, tenant_id, owner_headers, other_user_token.get_id())

        # Other user should NOT be able to access tool
        response = test_client.get(
            ENDPOINT_TOOL_DETAIL.format(tenant_id=tenant_id, tool_id=tool_id), headers=other_user_headers
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_tenant_global_admin_can_access_all_tools(self, test_client: TestClient) -> None:
        """Test that tenant GLOBAL_ADMIN can access all tools."""
        # Create owner with tenant
        owner_token = test_client.create_test_user("rbac-owner-9", "Tool Owner")
        owner_headers = create_auth_headers(owner_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, owner_token)

        # Create tool
        tool_id = create_tool(test_client, tenant_id, owner_headers, "RBAC Test Tool 9")

        # Create admin user and add to tenant as GLOBAL_ADMIN
        global_admin_token = test_client.create_test_user("rbac-globaladmin-9", "Global Admin")
        global_admin_headers = create_auth_headers(global_admin_token, use_cache=False)
        test_client.put(
            f"/api/v1/platform-service/tenants/{tenant_id}/principals",
            json={
                "principal_id": global_admin_token.get_id(),
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": "GLOBAL_ADMIN",
            },
            headers=owner_headers,
        )

        # Global admin should be able to access tool even without explicit permission
        response = test_client.get(
            ENDPOINT_TOOL_DETAIL.format(tenant_id=tenant_id, tool_id=tool_id), headers=global_admin_headers
        )

        assert response.status_code == status.HTTP_200_OK

    def test_tenant_react_agent_admin_can_access_all_tools(self, test_client: TestClient) -> None:
        """Test that tenant REACT_AGENT_ADMIN can access all tools."""
        # Create owner with tenant
        owner_token = test_client.create_test_user("rbac-owner-10", "Tool Owner")
        owner_headers = create_auth_headers(owner_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, owner_token)

        # Create tool
        tool_id = create_tool(test_client, tenant_id, owner_headers, "RBAC Test Tool 10")

        # Create admin user and add to tenant as REACT_AGENT_ADMIN
        react_admin_token = test_client.create_test_user("rbac-reactadmin-10", "React Agent Admin")
        react_admin_headers = create_auth_headers(react_admin_token, use_cache=False)
        test_client.put(
            f"/api/v1/platform-service/tenants/{tenant_id}/principals",
            json={
                "principal_id": react_admin_token.get_id(),
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": "REACT_AGENT_ADMIN",
            },
            headers=owner_headers,
        )

        # React agent admin should be able to access tool
        response = test_client.get(
            ENDPOINT_TOOL_DETAIL.format(tenant_id=tenant_id, tool_id=tool_id), headers=react_admin_headers
        )

        assert response.status_code == status.HTTP_200_OK

    def test_list_tools_only_returns_accessible_tools(self, test_client: TestClient) -> None:
        """Test that list tools only returns tools user has access to."""
        # Create owner with tenant
        owner_token = test_client.create_test_user("rbac-owner-11", "Tool Owner")
        owner_headers = create_auth_headers(owner_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, owner_token)

        # Create multiple tools
        tool_ids = []
        for i in range(3):
            tool_id = create_tool(test_client, tenant_id, owner_headers, f"RBAC Test Tool 11-{i}")
            tool_ids.append(tool_id)

        # Create other user and add to tenant
        other_user_token = test_client.create_test_user("rbac-other-11", "Other User")
        other_user_headers = create_auth_headers(other_user_token, use_cache=False)
        add_user_to_tenant(test_client, tenant_id, owner_headers, other_user_token.get_id())

        # Give other user access to only one tool
        test_client.put(
            ENDPOINT_TOOL_PRINCIPALS.format(tenant_id=tenant_id, tool_id=tool_ids[0]),
            json={"principal_id": other_user_token.get_id(), "principal_type": PRINCIPAL_TYPE_USER, "role": ROLE_READ},
            headers=owner_headers,
        )

        # Other user should only see the one tool they have access to
        response = test_client.get(ENDPOINT_TOOLS.format(tenant_id=tenant_id), headers=other_user_headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 1
        assert data[0]["id"] == tool_ids[0]
