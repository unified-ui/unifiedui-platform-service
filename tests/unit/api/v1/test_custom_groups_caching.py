"""Tests for custom groups caching."""

from typing import Any

from fastapi import status
from starlette.testclient import TestClient

from tests.conftest import create_auth_headers
from tests.helpers.tenant import add_user_to_tenant, create_tenant_for_user
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

# Roles
ROLE_READ = PermissionActionEnum.READ.value
ROLE_WRITE = PermissionActionEnum.WRITE.value
ROLE_ADMIN = PermissionActionEnum.ADMIN.value

# Principal Types
PRINCIPAL_TYPE_USER = PrincipalTypeEnum.IDENTITY_USER.value
PRINCIPAL_TYPE_GROUP = PrincipalTypeEnum.IDENTITY_GROUP.value


def create_custom_group(test_client: TestClient, tenant_id: str, headers: dict, group_name: str = "Test Group") -> str:
    """Helper function to create a custom group and return its ID."""
    response = test_client.post(
        ENDPOINT_CUSTOM_GROUPS.format(tenant_id=tenant_id),
        json={"name": group_name, "description": f"Group {group_name}"},
        headers=headers,
    )
    assert response.status_code == status.HTTP_201_CREATED
    return response.json()["id"]


class TestCustomGroupCaching:
    """Test suite for custom group caching behavior with X-Use-Cache enabled."""

    def test_creator_permissions_cached(self, test_client: TestClient, fake_redis_client: Any) -> None:
        """Test that creator's ADMIN permission is cached correctly."""
        # Create user and tenant
        user_token = test_client.create_test_user("cache-creator", "Cache Creator")
        headers = create_auth_headers(user_token)
        tenant_id = create_tenant_for_user(test_client, user_token)

        # Create custom group
        group_id = create_custom_group(test_client, tenant_id, headers, "Cached Group")

        # First access - should cache the permissions
        response1 = test_client.get(
            ENDPOINT_CUSTOM_GROUP_DETAIL.format(tenant_id=tenant_id, custom_group_id=group_id), headers=headers
        )
        assert response1.status_code == status.HTTP_200_OK

        # Second access - should use cached permissions
        response2 = test_client.get(
            ENDPOINT_CUSTOM_GROUP_DETAIL.format(tenant_id=tenant_id, custom_group_id=group_id), headers=headers
        )
        assert response2.status_code == status.HTTP_200_OK

        # User should still be able to update (has ADMIN)
        update_response = test_client.patch(
            ENDPOINT_CUSTOM_GROUP_DETAIL.format(tenant_id=tenant_id, custom_group_id=group_id),
            json={"name": "Updated Cached Group"},
            headers=headers,
        )
        assert update_response.status_code == status.HTTP_200_OK

    def test_no_access_cached(self, test_client: TestClient, fake_redis_client: Any) -> None:
        """Test that lack of access is handled correctly with caching."""
        # User A creates tenant and custom group
        user_a_token = test_client.create_test_user("cache-user-a", "Cache User A")
        headers_a = create_auth_headers(user_a_token)
        tenant_id = create_tenant_for_user(test_client, user_a_token)
        group_id = create_custom_group(test_client, tenant_id, headers_a, "Private Cached Group")

        # User B (tenant member but not group member)
        user_b_token = test_client.create_test_user("cache-user-b", "Cache User B")
        headers_b = create_auth_headers(user_b_token)

        # Add User B to tenant
        add_user_to_tenant(test_client, tenant_id, headers_a, "cache-user-b", "READER")

        # User B can view (tenant member can view)
        view_response = test_client.get(
            ENDPOINT_CUSTOM_GROUP_DETAIL.format(tenant_id=tenant_id, custom_group_id=group_id), headers=headers_b
        )
        assert view_response.status_code == status.HTTP_200_OK

        # First access - no permission to modify (should cache the lack of access)
        response1 = test_client.patch(
            ENDPOINT_CUSTOM_GROUP_DETAIL.format(tenant_id=tenant_id, custom_group_id=group_id),
            json={"name": "Should Fail"},
            headers=headers_b,
        )
        assert response1.status_code == status.HTTP_403_FORBIDDEN

        # Second access - should still be forbidden
        response2 = test_client.patch(
            ENDPOINT_CUSTOM_GROUP_DETAIL.format(tenant_id=tenant_id, custom_group_id=group_id),
            json={"name": "Should Fail Again"},
            headers=headers_b,
        )
        assert response2.status_code == status.HTTP_403_FORBIDDEN

    def test_direct_user_permission_grant_invalidates_cache(
        self, test_client: TestClient, fake_redis_client: Any
    ) -> None:
        """Test that granting permission to a user invalidates their cache."""
        # Admin creates tenant and custom group
        admin_token = test_client.create_test_user("cache-admin-1", "Cache Admin 1")
        admin_headers = create_auth_headers(admin_token)
        tenant_id = create_tenant_for_user(test_client, admin_token)
        group_id = create_custom_group(test_client, tenant_id, admin_headers, "Permission Grant Test")

        # Regular user has no access initially
        user_token = test_client.create_test_user("cache-regular-1", "Cache Regular 1")
        user_headers = create_auth_headers(user_token)

        # Add user to tenant first
        add_user_to_tenant(test_client, tenant_id, admin_headers, "cache-regular-1", "READER")

        # User can view but cannot modify (this caches the lack of permission)
        response_before = test_client.patch(
            ENDPOINT_CUSTOM_GROUP_DETAIL.format(tenant_id=tenant_id, custom_group_id=group_id),
            json={"name": "Should Fail"},
            headers=user_headers,
        )
        assert response_before.status_code == status.HTTP_403_FORBIDDEN

        # Admin grants WRITE permission to user
        grant_response = test_client.put(
            ENDPOINT_CUSTOM_GROUP_PRINCIPALS.format(tenant_id=tenant_id, custom_group_id=group_id),
            json={"principal_id": "cache-regular-1", "principal_type": PRINCIPAL_TYPE_USER, "role": ROLE_WRITE},
            headers=admin_headers,
        )
        assert grant_response.status_code == status.HTTP_200_OK

        # User should NOW have write access (cache must be invalidated)
        response_after = test_client.patch(
            ENDPOINT_CUSTOM_GROUP_DETAIL.format(tenant_id=tenant_id, custom_group_id=group_id),
            json={"name": "Now It Works"},
            headers=user_headers,
        )
        assert response_after.status_code == status.HTTP_200_OK

        # Verify the update worked
        assert response_after.json()["name"] == "Now It Works"

        # User CANNOT delete (only WRITE, not ADMIN)
        delete_response = test_client.request(
            "DELETE",
            ENDPOINT_CUSTOM_GROUP_DETAIL.format(tenant_id=tenant_id, custom_group_id=group_id),
            headers=user_headers,
        )
        assert delete_response.status_code == status.HTTP_403_FORBIDDEN

    def test_direct_user_permission_revoke_invalidates_cache(
        self, test_client: TestClient, fake_redis_client: Any
    ) -> None:
        """Test that revoking permission from a user invalidates their cache."""
        # Admin creates tenant and custom group
        admin_token = test_client.create_test_user("cache-admin-2", "Cache Admin 2")
        admin_headers = create_auth_headers(admin_token)
        tenant_id = create_tenant_for_user(test_client, admin_token)
        group_id = create_custom_group(test_client, tenant_id, admin_headers, "Permission Revoke Test")

        # Regular user gets ADMIN permission
        user_token = test_client.create_test_user("cache-regular-2", "Cache Regular 2")
        user_headers = create_auth_headers(user_token)

        # Add user to tenant first
        add_user_to_tenant(test_client, tenant_id, admin_headers, "cache-regular-2", "READER")

        # Grant ADMIN permission
        test_client.put(
            ENDPOINT_CUSTOM_GROUP_PRINCIPALS.format(tenant_id=tenant_id, custom_group_id=group_id),
            json={"principal_id": "cache-regular-2", "principal_type": PRINCIPAL_TYPE_USER, "role": ROLE_ADMIN},
            headers=admin_headers,
        )

        # User CAN update custom group (cache this permission)
        update_response1 = test_client.patch(
            ENDPOINT_CUSTOM_GROUP_DETAIL.format(tenant_id=tenant_id, custom_group_id=group_id),
            json={"name": "Updated Once"},
            headers=user_headers,
        )
        assert update_response1.status_code == status.HTTP_200_OK

        # Admin revokes ADMIN permission
        revoke_response = test_client.request(
            "DELETE",
            ENDPOINT_CUSTOM_GROUP_PRINCIPALS.format(tenant_id=tenant_id, custom_group_id=group_id),
            json={"principal_id": "cache-regular-2", "principal_type": PRINCIPAL_TYPE_USER, "role": ROLE_ADMIN},
            headers=admin_headers,
        )
        assert revoke_response.status_code == status.HTTP_200_OK

        # User should NOW NOT have write access (cache must be invalidated)
        update_response2 = test_client.patch(
            ENDPOINT_CUSTOM_GROUP_DETAIL.format(tenant_id=tenant_id, custom_group_id=group_id),
            json={"name": "Should Fail"},
            headers=user_headers,
        )
        assert update_response2.status_code == status.HTTP_403_FORBIDDEN

        # User can still view (tenant member)
        get_response = test_client.get(
            ENDPOINT_CUSTOM_GROUP_DETAIL.format(tenant_id=tenant_id, custom_group_id=group_id), headers=user_headers
        )
        assert get_response.status_code == status.HTTP_200_OK

    def test_multiple_permission_changes_invalidate_cache(
        self, test_client: TestClient, fake_redis_client: Any
    ) -> None:
        """Test that multiple permission changes properly invalidate cache."""
        # Admin creates tenant and custom group
        admin_token = test_client.create_test_user("cache-admin-3", "Cache Admin 3")
        admin_headers = create_auth_headers(admin_token)
        tenant_id = create_tenant_for_user(test_client, admin_token)
        group_id = create_custom_group(test_client, tenant_id, admin_headers, "Multiple Changes Test")

        # Create user
        user_token = test_client.create_test_user("cache-regular-3", "Cache Regular 3")
        user_headers = create_auth_headers(user_token)

        # Add user to tenant
        add_user_to_tenant(test_client, tenant_id, admin_headers, "cache-regular-3", "READER")

        # User cannot modify initially
        response1 = test_client.patch(
            ENDPOINT_CUSTOM_GROUP_DETAIL.format(tenant_id=tenant_id, custom_group_id=group_id),
            json={"name": "Should Fail 1"},
            headers=user_headers,
        )
        assert response1.status_code == status.HTTP_403_FORBIDDEN

        # Grant READ permission
        test_client.put(
            ENDPOINT_CUSTOM_GROUP_PRINCIPALS.format(tenant_id=tenant_id, custom_group_id=group_id),
            json={"principal_id": "cache-regular-3", "principal_type": PRINCIPAL_TYPE_USER, "role": ROLE_READ},
            headers=admin_headers,
        )

        # User still cannot modify (READ only)
        response2 = test_client.patch(
            ENDPOINT_CUSTOM_GROUP_DETAIL.format(tenant_id=tenant_id, custom_group_id=group_id),
            json={"name": "Should Fail 2"},
            headers=user_headers,
        )
        assert response2.status_code == status.HTTP_403_FORBIDDEN

        # Upgrade to WRITE permission (replaces READ due to single-role model)
        test_client.put(
            ENDPOINT_CUSTOM_GROUP_PRINCIPALS.format(tenant_id=tenant_id, custom_group_id=group_id),
            json={"principal_id": "cache-regular-3", "principal_type": PRINCIPAL_TYPE_USER, "role": ROLE_WRITE},
            headers=admin_headers,
        )

        # User CAN now modify
        response3 = test_client.patch(
            ENDPOINT_CUSTOM_GROUP_DETAIL.format(tenant_id=tenant_id, custom_group_id=group_id),
            json={"name": "Now It Works"},
            headers=user_headers,
        )
        assert response3.status_code == status.HTTP_200_OK

        # Upgrade to ADMIN permission
        test_client.put(
            ENDPOINT_CUSTOM_GROUP_PRINCIPALS.format(tenant_id=tenant_id, custom_group_id=group_id),
            json={"principal_id": "cache-regular-3", "principal_type": PRINCIPAL_TYPE_USER, "role": ROLE_ADMIN},
            headers=admin_headers,
        )

        # User CAN now delete
        delete_response = test_client.request(
            "DELETE",
            ENDPOINT_CUSTOM_GROUP_DETAIL.format(tenant_id=tenant_id, custom_group_id=group_id),
            headers=user_headers,
        )
        assert delete_response.status_code == status.HTTP_204_NO_CONTENT

    def test_custom_groups_list_cached_correctly(self, test_client: TestClient, fake_redis_client: Any) -> None:
        """Test that custom groups list is cached correctly."""
        # Create user and tenant
        user_token = test_client.create_test_user("cache-list-user", "Cache List User")
        headers = create_auth_headers(user_token)
        tenant_id = create_tenant_for_user(test_client, user_token)

        # Create multiple custom groups
        create_custom_group(test_client, tenant_id, headers, "Group 1")
        create_custom_group(test_client, tenant_id, headers, "Group 2")

        # First list - should cache
        response1 = test_client.get(ENDPOINT_CUSTOM_GROUPS.format(tenant_id=tenant_id), headers=headers)
        assert response1.status_code == status.HTTP_200_OK
        data1 = response1.json()
        assert len(data1) == 2

        # Second list - should use cache
        response2 = test_client.get(ENDPOINT_CUSTOM_GROUPS.format(tenant_id=tenant_id), headers=headers)
        assert response2.status_code == status.HTTP_200_OK
        data2 = response2.json()
        assert len(data2) == 2

        # Create another group
        create_custom_group(test_client, tenant_id, headers, "Group 3")

        # List should show new group (cache should be invalidated on create)
        response3 = test_client.get(ENDPOINT_CUSTOM_GROUPS.format(tenant_id=tenant_id), headers=headers)
        assert response3.status_code == status.HTTP_200_OK
        data3 = response3.json()
        assert len(data3) == 3

    def test_cache_isolated_between_users(self, test_client: TestClient, fake_redis_client: Any) -> None:
        """Test that cache is properly isolated between different users."""
        # User A creates tenant and custom group
        user_a_token = test_client.create_test_user("cache-isolation-a", "Cache Isolation A")
        headers_a = create_auth_headers(user_a_token)
        tenant_id = create_tenant_for_user(test_client, user_a_token)
        group_id = create_custom_group(test_client, tenant_id, headers_a, "Isolation Test Group")

        # User B joins tenant
        user_b_token = test_client.create_test_user("cache-isolation-b", "Cache Isolation B")
        headers_b = create_auth_headers(user_b_token)
        add_user_to_tenant(test_client, tenant_id, headers_a, "cache-isolation-b", "READER")

        # User A has ADMIN (can update)
        update_a = test_client.patch(
            ENDPOINT_CUSTOM_GROUP_DETAIL.format(tenant_id=tenant_id, custom_group_id=group_id),
            json={"name": "Updated by A"},
            headers=headers_a,
        )
        assert update_a.status_code == status.HTTP_200_OK

        # User B has no permissions (cannot update)
        update_b = test_client.patch(
            ENDPOINT_CUSTOM_GROUP_DETAIL.format(tenant_id=tenant_id, custom_group_id=group_id),
            json={"name": "Should Fail"},
            headers=headers_b,
        )
        assert update_b.status_code == status.HTTP_403_FORBIDDEN

        # Grant WRITE to User B
        test_client.put(
            ENDPOINT_CUSTOM_GROUP_PRINCIPALS.format(tenant_id=tenant_id, custom_group_id=group_id),
            json={"principal_id": "cache-isolation-b", "principal_type": PRINCIPAL_TYPE_USER, "role": ROLE_WRITE},
            headers=headers_a,
        )

        # User B can now update (their cache invalidated)
        update_b2 = test_client.patch(
            ENDPOINT_CUSTOM_GROUP_DETAIL.format(tenant_id=tenant_id, custom_group_id=group_id),
            json={"name": "Updated by B"},
            headers=headers_b,
        )
        assert update_b2.status_code == status.HTTP_200_OK

        # User A still has ADMIN (their cache not affected by B's permission change)
        delete_a = test_client.request(
            "DELETE",
            ENDPOINT_CUSTOM_GROUP_DETAIL.format(tenant_id=tenant_id, custom_group_id=group_id),
            headers=headers_a,
        )
        assert delete_a.status_code == status.HTTP_204_NO_CONTENT

    def test_tenant_admin_bypass_cached_correctly(self, test_client: TestClient, fake_redis_client: Any) -> None:
        """Test that tenant-level admin permissions are cached correctly."""
        # User A creates tenant (becomes TENANT_GLOBAL_ADMIN)
        user_a_token = test_client.create_test_user("cache-tenant-admin", "Cache Tenant Admin")
        headers_a = create_auth_headers(user_a_token)
        tenant_id = create_tenant_for_user(test_client, user_a_token)

        # User B creates a custom group
        user_b_token = test_client.create_test_user("cache-group-creator", "Cache Group Creator")
        headers_b = create_auth_headers(user_b_token)

        # Add User B to tenant with CUSTOM_GROUP_CREATOR
        add_user_to_tenant(test_client, tenant_id, headers_a, "cache-group-creator", "CUSTOM_GROUP_CREATOR")

        group_id = create_custom_group(test_client, tenant_id, headers_b, "B's Group")

        # User A (TENANT_GLOBAL_ADMIN) can access without explicit permission (cache this)
        response1 = test_client.get(
            ENDPOINT_CUSTOM_GROUP_DETAIL.format(tenant_id=tenant_id, custom_group_id=group_id), headers=headers_a
        )
        assert response1.status_code == status.HTTP_200_OK

        # User A can update (tenant admin bypass)
        update_response = test_client.patch(
            ENDPOINT_CUSTOM_GROUP_DETAIL.format(tenant_id=tenant_id, custom_group_id=group_id),
            json={"name": "Updated by Tenant Admin"},
            headers=headers_a,
        )
        assert update_response.status_code == status.HTTP_200_OK

        # User A can delete
        delete_response = test_client.request(
            "DELETE",
            ENDPOINT_CUSTOM_GROUP_DETAIL.format(tenant_id=tenant_id, custom_group_id=group_id),
            headers=headers_a,
        )
        assert delete_response.status_code == status.HTTP_204_NO_CONTENT
