"""Tests for custom groups RBAC (Role-Based Access Control)."""

from typing import Any

from fastapi import status
from starlette.testclient import TestClient
from tests.conftest import create_auth_headers

from unifiedui.core.database.enums import PermissionActionEnum, PrincipalTypeEnum

# API Endpoints
ENDPOINT_TENANTS = "/api/v1/platform-service/tenants"
ENDPOINT_CUSTOM_GROUPS = "/api/v1/platform-service/tenants/{tenant_id}/custom-groups"
ENDPOINT_CUSTOM_GROUP_DETAIL = "/api/v1/platform-service/tenants/{tenant_id}/custom-groups/{custom_group_id}"
ENDPOINT_CUSTOM_GROUP_PRINCIPALS = (
    "/api/v1/platform-service/tenants/{tenant_id}/custom-groups/{custom_group_id}/principals"
)
ENDPOINT_PRINCIPAL_DETAIL = (
    "/api/v1/platform-service/tenants/{tenant_id}/custom-groups/{custom_group_id}/principals/{principal_id}"
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
        ENDPOINT_TENANTS,
        json={"name": tenant_name, "description": f"Tenant for {user_token.get_id()}"},
        headers=headers,
    )
    assert response.status_code == status.HTTP_201_CREATED
    return response.json()["id"]


def create_custom_group(test_client: TestClient, tenant_id: str, headers: dict, group_name: str = "Test Group") -> str:
    """Helper function to create a custom group and return its ID."""
    response = test_client.post(
        ENDPOINT_CUSTOM_GROUPS.format(tenant_id=tenant_id),
        json={"name": group_name, "description": f"Group {group_name}"},
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


class TestCustomGroupRBAC:
    """Test suite for custom group role-based access control."""

    def test_creator_becomes_admin(self, test_client: TestClient) -> None:
        """Test that custom group creator automatically becomes ADMIN."""
        # Create user and tenant
        user_token = test_client.create_test_user("creator-user", "Creator User")
        headers = create_auth_headers(user_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, user_token)

        # Create custom group
        group_id = create_custom_group(test_client, tenant_id, headers, "Creator Test Group")

        # Verify creator has ADMIN role
        principals_response = test_client.get(
            ENDPOINT_PRINCIPAL_DETAIL.format(
                tenant_id=tenant_id, custom_group_id=group_id, principal_id="creator-user"
            ),
            headers=headers,
        )

        assert principals_response.status_code == status.HTTP_200_OK
        data = principals_response.json()
        assert data["principal_id"] == "creator-user"
        assert ROLE_ADMIN in data["roles"]

    def test_admin_can_update_custom_group(self, test_client: TestClient) -> None:
        """Test that ADMIN can update custom group."""
        # Create user and tenant
        user_token = test_client.create_test_user("admin-user", "Admin User")
        headers = create_auth_headers(user_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, user_token)

        # Create custom group
        group_id = create_custom_group(test_client, tenant_id, headers, "Original Name")

        # Update custom group
        update_response = test_client.patch(
            ENDPOINT_CUSTOM_GROUP_DETAIL.format(tenant_id=tenant_id, custom_group_id=group_id),
            json={"name": "Updated Name"},
            headers=headers,
        )

        assert update_response.status_code == status.HTTP_200_OK
        assert update_response.json()["name"] == "Updated Name"

    def test_admin_can_delete_custom_group(self, test_client: TestClient) -> None:
        """Test that ADMIN can delete custom group."""
        # Create user and tenant
        user_token = test_client.create_test_user("delete-admin", "Delete Admin")
        headers = create_auth_headers(user_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, user_token)

        # Create custom group
        group_id = create_custom_group(test_client, tenant_id, headers, "To Delete")

        # Delete custom group
        delete_response = test_client.request(
            "DELETE",
            ENDPOINT_CUSTOM_GROUP_DETAIL.format(tenant_id=tenant_id, custom_group_id=group_id),
            headers=headers,
        )

        assert delete_response.status_code == status.HTTP_204_NO_CONTENT

    def test_admin_can_manage_principals(self, test_client: TestClient) -> None:
        """Test that ADMIN can add/remove principals."""
        # Create admin user and tenant
        admin_token = test_client.create_test_user("principal-admin", "Principal Admin")
        admin_headers = create_auth_headers(admin_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, admin_token)

        # Create custom group
        group_id = create_custom_group(test_client, tenant_id, admin_headers, "Principal Test")

        # Add a role to another user
        add_response = test_client.put(
            ENDPOINT_CUSTOM_GROUP_PRINCIPALS.format(tenant_id=tenant_id, custom_group_id=group_id),
            json={"principal_id": "other-user", "principal_type": PRINCIPAL_TYPE_USER, "role": ROLE_READ},
            headers=admin_headers,
        )

        assert add_response.status_code == status.HTTP_200_OK
        assert ROLE_READ in add_response.json()["roles"]

        # Remove the role
        delete_response = test_client.request(
            "DELETE",
            ENDPOINT_CUSTOM_GROUP_PRINCIPALS.format(tenant_id=tenant_id, custom_group_id=group_id),
            json={"principal_id": "other-user", "principal_type": PRINCIPAL_TYPE_USER, "role": ROLE_READ},
            headers=admin_headers,
        )

        assert delete_response.status_code == status.HTTP_200_OK

    def test_non_member_cannot_access_custom_group(self, test_client: TestClient) -> None:
        """Test that users without access cannot modify custom group (but can view if tenant member)."""
        # User A creates tenant and custom group
        user_a_token = test_client.create_test_user("user-a", "User A")
        headers_a = create_auth_headers(user_a_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, user_a_token)
        group_id = create_custom_group(test_client, tenant_id, headers_a, "Private Group")

        # User B (member of same tenant but not of the custom group)
        user_b_token = test_client.create_test_user("user-b", "User B")
        headers_b = create_auth_headers(user_b_token, use_cache=False)

        # Add User B to tenant with READER role
        add_user_to_tenant(test_client, tenant_id, headers_a, "user-b", "READER")

        # User B CAN view custom group (any tenant member can view)
        get_response = test_client.get(
            ENDPOINT_CUSTOM_GROUP_DETAIL.format(tenant_id=tenant_id, custom_group_id=group_id), headers=headers_b
        )
        assert get_response.status_code == status.HTTP_200_OK

        # User B cannot update custom group
        update_response = test_client.patch(
            ENDPOINT_CUSTOM_GROUP_DETAIL.format(tenant_id=tenant_id, custom_group_id=group_id),
            json={"name": "Hacked"},
            headers=headers_b,
        )
        assert update_response.status_code == status.HTTP_403_FORBIDDEN

        # User B cannot delete custom group
        delete_response = test_client.request(
            "DELETE",
            ENDPOINT_CUSTOM_GROUP_DETAIL.format(tenant_id=tenant_id, custom_group_id=group_id),
            headers=headers_b,
        )
        assert delete_response.status_code == status.HTTP_403_FORBIDDEN

        # User B cannot manage principals
        principal_response = test_client.put(
            ENDPOINT_CUSTOM_GROUP_PRINCIPALS.format(tenant_id=tenant_id, custom_group_id=group_id),
            json={"principal_id": "some-user", "principal_type": PRINCIPAL_TYPE_USER, "role": ROLE_READ},
            headers=headers_b,
        )
        assert principal_response.status_code == status.HTTP_403_FORBIDDEN

    def test_read_user_can_view_but_not_modify(self, test_client: TestClient) -> None:
        """Test that READ role can view but cannot modify custom group."""
        # Admin creates tenant and custom group
        admin_token = test_client.create_test_user("read-admin", "Read Admin")
        admin_headers = create_auth_headers(admin_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, admin_token)
        group_id = create_custom_group(test_client, tenant_id, admin_headers, "Read Test")

        # Create reader user
        reader_token = test_client.create_test_user("reader-user", "Reader User")
        reader_headers = create_auth_headers(reader_token, use_cache=False)

        # Add reader to tenant first
        add_user_to_tenant(test_client, tenant_id, admin_headers, "reader-user", "READER")

        # Admin adds reader with READ role to custom group
        test_client.put(
            ENDPOINT_CUSTOM_GROUP_PRINCIPALS.format(tenant_id=tenant_id, custom_group_id=group_id),
            json={"principal_id": "reader-user", "principal_type": PRINCIPAL_TYPE_USER, "role": ROLE_READ},
            headers=admin_headers,
        )

        # Reader CAN view custom group
        get_response = test_client.get(
            ENDPOINT_CUSTOM_GROUP_DETAIL.format(tenant_id=tenant_id, custom_group_id=group_id), headers=reader_headers
        )
        assert get_response.status_code == status.HTTP_200_OK
        assert get_response.json()["id"] == group_id

        # Reader CAN list principals
        principals_response = test_client.get(
            ENDPOINT_CUSTOM_GROUP_PRINCIPALS.format(tenant_id=tenant_id, custom_group_id=group_id),
            headers=reader_headers,
        )
        assert principals_response.status_code == status.HTTP_200_OK

        # Reader CANNOT update custom group (needs WRITE or ADMIN)
        update_response = test_client.patch(
            ENDPOINT_CUSTOM_GROUP_DETAIL.format(tenant_id=tenant_id, custom_group_id=group_id),
            json={"name": "Hacked by Reader"},
            headers=reader_headers,
        )
        assert update_response.status_code == status.HTTP_403_FORBIDDEN

        # Reader CANNOT delete custom group (needs ADMIN)
        delete_response = test_client.request(
            "DELETE",
            ENDPOINT_CUSTOM_GROUP_DETAIL.format(tenant_id=tenant_id, custom_group_id=group_id),
            headers=reader_headers,
        )
        assert delete_response.status_code == status.HTTP_403_FORBIDDEN

        # Reader CANNOT manage principals (needs ADMIN)
        add_principal_response = test_client.put(
            ENDPOINT_CUSTOM_GROUP_PRINCIPALS.format(tenant_id=tenant_id, custom_group_id=group_id),
            json={"principal_id": "another-user", "principal_type": PRINCIPAL_TYPE_USER, "role": ROLE_READ},
            headers=reader_headers,
        )
        assert add_principal_response.status_code == status.HTTP_403_FORBIDDEN

    def test_write_user_can_modify_but_not_delete_or_manage_principals(self, test_client: TestClient) -> None:
        """Test that WRITE role can view and modify but cannot delete or manage principals."""
        # Admin creates tenant and custom group
        admin_token = test_client.create_test_user("write-admin", "Write Admin")
        admin_headers = create_auth_headers(admin_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, admin_token)
        group_id = create_custom_group(test_client, tenant_id, admin_headers, "Write Test")

        # Create writer user
        writer_token = test_client.create_test_user("writer-user", "Writer User")
        writer_headers = create_auth_headers(writer_token, use_cache=False)

        # Add writer to tenant first
        add_user_to_tenant(test_client, tenant_id, admin_headers, "writer-user", "READER")

        # Admin adds writer with WRITE role to custom group
        test_client.put(
            ENDPOINT_CUSTOM_GROUP_PRINCIPALS.format(tenant_id=tenant_id, custom_group_id=group_id),
            json={"principal_id": "writer-user", "principal_type": PRINCIPAL_TYPE_USER, "role": ROLE_WRITE},
            headers=admin_headers,
        )

        # Writer CAN view custom group
        get_response = test_client.get(
            ENDPOINT_CUSTOM_GROUP_DETAIL.format(tenant_id=tenant_id, custom_group_id=group_id), headers=writer_headers
        )
        assert get_response.status_code == status.HTTP_200_OK

        # Writer CAN update custom group
        update_response = test_client.patch(
            ENDPOINT_CUSTOM_GROUP_DETAIL.format(tenant_id=tenant_id, custom_group_id=group_id),
            json={"name": "Updated by Writer"},
            headers=writer_headers,
        )
        assert update_response.status_code == status.HTTP_200_OK
        assert update_response.json()["name"] == "Updated by Writer"

        # Writer CAN list principals
        principals_response = test_client.get(
            ENDPOINT_CUSTOM_GROUP_PRINCIPALS.format(tenant_id=tenant_id, custom_group_id=group_id),
            headers=writer_headers,
        )
        assert principals_response.status_code == status.HTTP_200_OK

        # Writer CANNOT delete custom group (needs ADMIN)
        delete_response = test_client.request(
            "DELETE",
            ENDPOINT_CUSTOM_GROUP_DETAIL.format(tenant_id=tenant_id, custom_group_id=group_id),
            headers=writer_headers,
        )
        assert delete_response.status_code == status.HTTP_403_FORBIDDEN

        # Writer CANNOT manage principals (needs ADMIN)
        add_principal_response = test_client.put(
            ENDPOINT_CUSTOM_GROUP_PRINCIPALS.format(tenant_id=tenant_id, custom_group_id=group_id),
            json={"principal_id": "another-user", "principal_type": PRINCIPAL_TYPE_USER, "role": ROLE_READ},
            headers=writer_headers,
        )
        assert add_principal_response.status_code == status.HTTP_403_FORBIDDEN

    def test_multiple_admins(self, test_client: TestClient) -> None:
        """Test that multiple users can be ADMIN and all have full access."""
        # First admin creates tenant and custom group
        admin1_token = test_client.create_test_user("admin-1", "Admin 1")
        admin1_headers = create_auth_headers(admin1_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, admin1_token)
        group_id = create_custom_group(test_client, tenant_id, admin1_headers, "Multi Admin Group")

        # Create second admin user
        admin2_token = test_client.create_test_user("admin-2", "Admin 2")
        admin2_headers = create_auth_headers(admin2_token, use_cache=False)

        # Add admin2 to tenant first
        add_user_to_tenant(test_client, tenant_id, admin1_headers, "admin-2", "READER")

        # First admin adds second admin with ADMIN role to custom group
        add_response = test_client.put(
            ENDPOINT_CUSTOM_GROUP_PRINCIPALS.format(tenant_id=tenant_id, custom_group_id=group_id),
            json={"principal_id": "admin-2", "principal_type": PRINCIPAL_TYPE_USER, "role": ROLE_ADMIN},
            headers=admin1_headers,
        )
        assert add_response.status_code == status.HTTP_200_OK
        assert ROLE_ADMIN in add_response.json()["roles"]

        # Second admin CAN update custom group
        update_response = test_client.patch(
            ENDPOINT_CUSTOM_GROUP_DETAIL.format(tenant_id=tenant_id, custom_group_id=group_id),
            json={"name": "Updated by Admin 2"},
            headers=admin2_headers,
        )
        assert update_response.status_code == status.HTTP_200_OK
        assert update_response.json()["name"] == "Updated by Admin 2"

        # Second admin CAN manage principals
        add_user_response = test_client.put(
            ENDPOINT_CUSTOM_GROUP_PRINCIPALS.format(tenant_id=tenant_id, custom_group_id=group_id),
            json={"principal_id": "new-user", "principal_type": PRINCIPAL_TYPE_USER, "role": ROLE_READ},
            headers=admin2_headers,
        )
        assert add_user_response.status_code == status.HTTP_200_OK

        # Second admin CAN delete custom group
        delete_response = test_client.request(
            "DELETE",
            ENDPOINT_CUSTOM_GROUP_DETAIL.format(tenant_id=tenant_id, custom_group_id=group_id),
            headers=admin2_headers,
        )
        assert delete_response.status_code == status.HTTP_204_NO_CONTENT

    def test_user_role_replacement(self, test_client: TestClient) -> None:
        """Test that setting a new role for a user replaces the old role (not adds)."""
        # Admin creates tenant and custom group
        admin_token = test_client.create_test_user("role-admin", "Role Admin")
        admin_headers = create_auth_headers(admin_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, admin_token)
        group_id = create_custom_group(test_client, tenant_id, admin_headers, "Role Test")

        # Create test user
        test_client.create_test_user("test-user", "Test User")

        # Admin gives user READ role
        test_client.put(
            ENDPOINT_CUSTOM_GROUP_PRINCIPALS.format(tenant_id=tenant_id, custom_group_id=group_id),
            json={"principal_id": "test-user", "principal_type": PRINCIPAL_TYPE_USER, "role": ROLE_READ},
            headers=admin_headers,
        )

        # Admin changes user to WRITE role
        update_response = test_client.put(
            ENDPOINT_CUSTOM_GROUP_PRINCIPALS.format(tenant_id=tenant_id, custom_group_id=group_id),
            json={"principal_id": "test-user", "principal_type": PRINCIPAL_TYPE_USER, "role": ROLE_WRITE},
            headers=admin_headers,
        )

        # User should have only WRITE role (READ was replaced)
        assert update_response.status_code == status.HTTP_200_OK
        roles = update_response.json()["roles"]
        assert len(roles) == 1
        assert ROLE_WRITE in roles
        assert ROLE_READ not in roles

    def test_removing_admin_role(self, test_client: TestClient, fake_redis_client: Any) -> None:
        """Test that ADMIN role can be removed (user loses admin access)."""
        # Admin creates tenant and custom group
        admin_token = test_client.create_test_user("demote-admin", "Demote Admin")
        admin_headers = create_auth_headers(admin_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, admin_token)
        group_id = create_custom_group(test_client, tenant_id, admin_headers, "Demote Test")

        # Create second admin
        admin2_token = test_client.create_test_user("admin-to-demote", "Admin To Demote")
        admin2_headers = create_auth_headers(admin2_token, use_cache=False)

        # Add admin2 to tenant first
        add_user_to_tenant(test_client, tenant_id, admin_headers, "admin-to-demote", "READER")

        # Give second user ADMIN role on custom group
        test_client.put(
            ENDPOINT_CUSTOM_GROUP_PRINCIPALS.format(tenant_id=tenant_id, custom_group_id=group_id),
            json={"principal_id": "admin-to-demote", "principal_type": PRINCIPAL_TYPE_USER, "role": ROLE_ADMIN},
            headers=admin_headers,
        )

        # Verify second admin CAN update custom group
        update_response = test_client.patch(
            ENDPOINT_CUSTOM_GROUP_DETAIL.format(tenant_id=tenant_id, custom_group_id=group_id),
            json={"name": "Updated"},
            headers=admin2_headers,
        )
        assert update_response.status_code == status.HTTP_200_OK

        # First admin removes ADMIN role from second admin
        remove_response = test_client.request(
            "DELETE",
            ENDPOINT_CUSTOM_GROUP_PRINCIPALS.format(tenant_id=tenant_id, custom_group_id=group_id),
            json={"principal_id": "admin-to-demote", "principal_type": PRINCIPAL_TYPE_USER, "role": ROLE_ADMIN},
            headers=admin_headers,
        )
        assert remove_response.status_code == status.HTTP_200_OK
        assert len(remove_response.json()["roles"]) == 0

        # Clear cache
        fake_redis_client.client.flushall()

        # Second user now has NO roles, so should get 403 when trying to access
        update_response2 = test_client.patch(
            ENDPOINT_CUSTOM_GROUP_DETAIL.format(tenant_id=tenant_id, custom_group_id=group_id),
            json={"name": "Should Fail"},
            headers=admin2_headers,
        )
        assert update_response2.status_code == status.HTTP_403_FORBIDDEN

    def test_tenant_global_admin_bypasses_custom_group_permissions(self, test_client: TestClient) -> None:
        """Test that tenant GLOBAL_ADMIN can access all custom groups regardless of group membership."""
        # User A creates tenant and custom group
        user_a_token = test_client.create_test_user("tenant-admin", "Tenant Admin")
        headers_a = create_auth_headers(user_a_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, user_a_token)

        # User B creates a custom group (User B is tenant member with CUSTOM_GROUP_CREATOR permission)
        user_b_token = test_client.create_test_user("group-creator", "Group Creator")
        headers_b = create_auth_headers(user_b_token, use_cache=False)

        # User A (tenant admin) grants User B CUSTOM_GROUP_CREATOR permission
        test_client.put(
            f"/api/v1/platform-service/tenants/{tenant_id}/principals",
            json={
                "principal_id": "group-creator",
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": "CUSTOM_GROUP_CREATOR",
            },
            headers=headers_a,
        )

        # User B creates a private custom group
        group_id = create_custom_group(test_client, tenant_id, headers_b, "Private Group")

        # User A (tenant GLOBAL_ADMIN) CAN access the group even though not explicitly a member
        get_response = test_client.get(
            ENDPOINT_CUSTOM_GROUP_DETAIL.format(tenant_id=tenant_id, custom_group_id=group_id), headers=headers_a
        )
        assert get_response.status_code == status.HTTP_200_OK

        # User A (tenant GLOBAL_ADMIN) CAN update the group
        update_response = test_client.patch(
            ENDPOINT_CUSTOM_GROUP_DETAIL.format(tenant_id=tenant_id, custom_group_id=group_id),
            json={"name": "Updated by Tenant Admin"},
            headers=headers_a,
        )
        assert update_response.status_code == status.HTTP_200_OK

        # User A (tenant GLOBAL_ADMIN) CAN manage principals
        add_response = test_client.put(
            ENDPOINT_CUSTOM_GROUP_PRINCIPALS.format(tenant_id=tenant_id, custom_group_id=group_id),
            json={"principal_id": "new-user", "principal_type": PRINCIPAL_TYPE_USER, "role": ROLE_READ},
            headers=headers_a,
        )
        assert add_response.status_code == status.HTTP_200_OK

        # User A (tenant GLOBAL_ADMIN) CAN delete the group
        delete_response = test_client.request(
            "DELETE",
            ENDPOINT_CUSTOM_GROUP_DETAIL.format(tenant_id=tenant_id, custom_group_id=group_id),
            headers=headers_a,
        )
        assert delete_response.status_code == status.HTTP_204_NO_CONTENT

    def test_tenant_custom_groups_admin_bypasses_custom_group_permissions(self, test_client: TestClient) -> None:
        """Test that tenant CUSTOM_GROUPS_ADMIN can access all custom groups."""
        # User A creates tenant
        user_a_token = test_client.create_test_user("tenant-admin-2", "Tenant Admin 2")
        headers_a = create_auth_headers(user_a_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, user_a_token)

        # User A creates a custom group
        group_id = create_custom_group(test_client, tenant_id, headers_a, "Test Group")

        # User B gets CUSTOM_GROUPS_ADMIN role on tenant
        user_b_token = test_client.create_test_user("groups-admin", "Groups Admin")
        headers_b = create_auth_headers(user_b_token, use_cache=False)

        test_client.put(
            f"/api/v1/platform-service/tenants/{tenant_id}/principals",
            json={"principal_id": "groups-admin", "principal_type": PRINCIPAL_TYPE_USER, "role": "CUSTOM_GROUPS_ADMIN"},
            headers=headers_a,
        )

        # User B (CUSTOM_GROUPS_ADMIN) CAN access the group
        get_response = test_client.get(
            ENDPOINT_CUSTOM_GROUP_DETAIL.format(tenant_id=tenant_id, custom_group_id=group_id), headers=headers_b
        )
        assert get_response.status_code == status.HTTP_200_OK

        # User B CAN update the group
        update_response = test_client.patch(
            ENDPOINT_CUSTOM_GROUP_DETAIL.format(tenant_id=tenant_id, custom_group_id=group_id),
            json={"name": "Updated by Groups Admin"},
            headers=headers_b,
        )
        assert update_response.status_code == status.HTTP_200_OK

        # User B CAN delete the group
        delete_response = test_client.request(
            "DELETE",
            ENDPOINT_CUSTOM_GROUP_DETAIL.format(tenant_id=tenant_id, custom_group_id=group_id),
            headers=headers_b,
        )
        assert delete_response.status_code == status.HTTP_204_NO_CONTENT
