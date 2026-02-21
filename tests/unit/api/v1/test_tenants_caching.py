"""Tests for tenants caching."""

import uuid
from typing import Any

from fastapi import status
from starlette.testclient import TestClient
from tests.conftest import create_auth_headers

from unifiedui.core.database.enums import PrincipalTypeEnum, TenantRolesEnum

# API Endpoints
ENDPOINT_TENANTS = "/api/v1/platform-service/tenants"
ENDPOINT_TENANT_DETAIL = "/api/v1/platform-service/tenants/{tenant_id}"
ENDPOINT_TENANT_PRINCIPALS = "/api/v1/platform-service/tenants/{tenant_id}/principals"
ENDPOINT_PRINCIPAL_DETAIL = "/api/v1/platform-service/tenants/{tenant_id}/principals/{principal_id}"

# Common Test IDs
NON_EXISTENT_ID = "non-existent-id"

# Roles
ROLE_GLOBAL_ADMIN = TenantRolesEnum.GLOBAL_ADMIN.value
ROLE_READER = TenantRolesEnum.READER.value
ROLE_CHAT_AGENTS_ADMIN = TenantRolesEnum.CHAT_AGENTS_ADMIN.value

# Principal Types
PRINCIPAL_TYPE_USER = PrincipalTypeEnum.IDENTITY_USER.value
PRINCIPAL_TYPE_GROUP = PrincipalTypeEnum.IDENTITY_GROUP.value


class TestTenantCaching:
    """Test suite for tenant caching behavior with X-Use-Cache enabled."""

    def test_creator_permissions_cached(self, test_client: TestClient, fake_redis_client: Any) -> None:
        """Test that creator's GLOBAL_ADMIN permission is cached correctly."""
        # Create user and tenant
        user_token = test_client.create_test_user("cache-creator", "Cache Creator")
        headers = create_auth_headers(user_token)

        create_response = test_client.post(
            ENDPOINT_TENANTS, json={"name": "Cached Tenant", "description": "Test caching"}, headers=headers
        )
        assert create_response.status_code == status.HTTP_201_CREATED
        tenant_id = create_response.json()["id"]

        # First access - should cache the permissions
        response1 = test_client.get(ENDPOINT_TENANT_DETAIL.format(tenant_id=tenant_id), headers=headers)
        assert response1.status_code == status.HTTP_200_OK

        # Second access - should use cached permissions
        response2 = test_client.get(ENDPOINT_TENANT_DETAIL.format(tenant_id=tenant_id), headers=headers)
        assert response2.status_code == status.HTTP_200_OK

        # User should still be able to update (has GLOBAL_ADMIN)
        update_response = test_client.patch(
            ENDPOINT_TENANT_DETAIL.format(tenant_id=tenant_id), json={"name": "Updated Cached Tenant"}, headers=headers
        )
        assert update_response.status_code == status.HTTP_200_OK

    def test_no_access_cached(self, test_client: TestClient, fake_redis_client: Any) -> None:
        """Test that lack of access is handled correctly with caching."""
        # User A creates tenant
        user_a_token = test_client.create_test_user("cache-user-a", "Cache User A")
        headers_a = create_auth_headers(user_a_token)

        create_response = test_client.post(
            ENDPOINT_TENANTS, json={"name": "Private Cached Tenant", "description": "Test"}, headers=headers_a
        )
        tenant_id = create_response.json()["id"]

        # User B tries to access
        user_b_token = test_client.create_test_user("cache-user-b", "Cache User B")
        headers_b = create_auth_headers(user_b_token)

        # First access - no permission (should cache the lack of access)
        response1 = test_client.get(ENDPOINT_TENANT_DETAIL.format(tenant_id=tenant_id), headers=headers_b)
        assert response1.status_code == status.HTTP_403_FORBIDDEN

        # Second access - should still be forbidden
        response2 = test_client.get(ENDPOINT_TENANT_DETAIL.format(tenant_id=tenant_id), headers=headers_b)
        assert response2.status_code == status.HTTP_403_FORBIDDEN

    def test_direct_user_permission_grant_invalidates_cache(
        self, test_client: TestClient, fake_redis_client: Any
    ) -> None:
        """Test that granting permission to a user invalidates their cache."""
        # Admin creates tenant
        admin_token = test_client.create_test_user("cache-admin-1", "Cache Admin 1")
        admin_headers = create_auth_headers(admin_token)

        create_response = test_client.post(
            ENDPOINT_TENANTS, json={"name": "Permission Grant Test", "description": "Test"}, headers=admin_headers
        )
        tenant_id = create_response.json()["id"]

        # Regular user has no access initially
        user_token = test_client.create_test_user("cache-regular-1", "Cache Regular 1")
        user_headers = create_auth_headers(user_token)

        # User cannot access (this caches the lack of permission)
        response_before = test_client.get(ENDPOINT_TENANT_DETAIL.format(tenant_id=tenant_id), headers=user_headers)
        assert response_before.status_code == status.HTTP_403_FORBIDDEN

        # Admin grants READER permission to user
        grant_response = test_client.put(
            ENDPOINT_TENANT_PRINCIPALS.format(tenant_id=tenant_id),
            json={"principal_id": "cache-regular-1", "principal_type": PRINCIPAL_TYPE_USER, "role": ROLE_READER},
            headers=admin_headers,
        )
        assert grant_response.status_code == status.HTTP_200_OK

        # User should NOW have access (cache must be invalidated)
        response_after = test_client.get(ENDPOINT_TENANT_DETAIL.format(tenant_id=tenant_id), headers=user_headers)
        assert response_after.status_code == status.HTTP_200_OK

        # User CAN read
        assert response_after.json()["id"] == tenant_id

        # User CANNOT update (only READER)
        update_response = test_client.patch(
            ENDPOINT_TENANT_DETAIL.format(tenant_id=tenant_id), json={"name": "Should Fail"}, headers=user_headers
        )
        assert update_response.status_code == status.HTTP_403_FORBIDDEN

    def test_direct_user_permission_revoke_invalidates_cache(
        self, test_client: TestClient, fake_redis_client: Any
    ) -> None:
        """Test that revoking permission from a user invalidates their cache."""
        # Admin creates tenant
        admin_token = test_client.create_test_user("cache-admin-2", "Cache Admin 2")
        admin_headers = create_auth_headers(admin_token)

        create_response = test_client.post(
            ENDPOINT_TENANTS, json={"name": "Permission Revoke Test", "description": "Test"}, headers=admin_headers
        )
        tenant_id = create_response.json()["id"]

        # Regular user gets GLOBAL_ADMIN
        user_token = test_client.create_test_user("cache-regular-2", "Cache Regular 2")
        user_headers = create_auth_headers(user_token)

        test_client.put(
            ENDPOINT_TENANT_PRINCIPALS.format(tenant_id=tenant_id),
            json={"principal_id": "cache-regular-2", "principal_type": PRINCIPAL_TYPE_USER, "role": ROLE_GLOBAL_ADMIN},
            headers=admin_headers,
        )

        # User CAN update tenant (cache this permission)
        update_response1 = test_client.patch(
            ENDPOINT_TENANT_DETAIL.format(tenant_id=tenant_id), json={"name": "Updated Once"}, headers=user_headers
        )
        assert update_response1.status_code == status.HTTP_200_OK

        # Admin revokes GLOBAL_ADMIN permission
        revoke_response = test_client.request(
            "DELETE",
            ENDPOINT_TENANT_PRINCIPALS.format(tenant_id=tenant_id),
            json={"principal_id": "cache-regular-2", "principal_type": PRINCIPAL_TYPE_USER, "role": ROLE_GLOBAL_ADMIN},
            headers=admin_headers,
        )
        assert revoke_response.status_code == status.HTTP_200_OK

        # User should NOW NOT have access (cache must be invalidated)
        update_response2 = test_client.patch(
            ENDPOINT_TENANT_DETAIL.format(tenant_id=tenant_id), json={"name": "Should Fail"}, headers=user_headers
        )
        assert update_response2.status_code == status.HTTP_403_FORBIDDEN

        # Also cannot read anymore
        get_response = test_client.get(ENDPOINT_TENANT_DETAIL.format(tenant_id=tenant_id), headers=user_headers)
        assert get_response.status_code == status.HTTP_403_FORBIDDEN

    def test_custom_group_permission_grant_invalidates_member_cache(
        self, test_client: TestClient, fake_redis_client: Any
    ) -> None:
        """Test that granting permission to a custom group invalidates member caches."""
        from unifiedui.core.database.enums import PrincipalTypeEnum
        from unifiedui.core.database.models import CustomGroupMember, Principal

        # Admin creates tenant
        admin_token = test_client.create_test_user("cache-admin-3", "Cache Admin 3")
        admin_headers = create_auth_headers(admin_token)

        create_response = test_client.post(
            ENDPOINT_TENANTS, json={"name": "Custom Group Grant Test", "description": "Test"}, headers=admin_headers
        )
        tenant_id = create_response.json()["id"]

        # Create custom group with user as member
        custom_group_id = str(uuid.uuid4())
        user_token = test_client.create_test_user("cache-cg-user-1", "Cache CG User 1")
        user_id = user_token.get_id()
        user_headers = create_auth_headers(user_token)

        with test_client.db_client.get_session() as session:
            # Create custom group as Principal
            custom_group = Principal(
                tenant_id=tenant_id,
                principal_id=custom_group_id,
                principal_type=PrincipalTypeEnum.CUSTOM_GROUP.value,
                display_name="Test Custom Group",
                principal_name="Test Custom Group",
                description="Test",
            )
            session.add(custom_group)

            # Also need the user as a Principal
            user_principal = Principal(
                tenant_id=tenant_id,
                principal_id=user_id,
                principal_type=PrincipalTypeEnum.IDENTITY_USER.value,
                display_name="Cache CG User 1",
                principal_name="cache-cg-user-1@test.com",
            )
            session.add(user_principal)
            session.flush()

            group_member = CustomGroupMember(
                id=str(uuid.uuid4()),
                custom_group_id=custom_group_id,
                principal_id=user_id,
                tenant_id=tenant_id,
                role="READ",
            )
            session.add(group_member)
            session.commit()

        # User has no access initially (caches this)
        response_before = test_client.get(ENDPOINT_TENANT_DETAIL.format(tenant_id=tenant_id), headers=user_headers)
        assert response_before.status_code == status.HTTP_403_FORBIDDEN

        # Admin grants READER permission to custom group
        grant_response = test_client.put(
            ENDPOINT_TENANT_PRINCIPALS.format(tenant_id=tenant_id),
            json={"principal_id": custom_group_id, "principal_type": "CUSTOM_GROUP", "role": ROLE_READER},
            headers=admin_headers,
        )
        assert grant_response.status_code == status.HTTP_200_OK

        # User should NOW have access via custom group (cache must be invalidated)
        response_after = test_client.get(ENDPOINT_TENANT_DETAIL.format(tenant_id=tenant_id), headers=user_headers)
        assert response_after.status_code == status.HTTP_200_OK

    def test_identity_group_permission_grant_invalidates_member_cache(
        self, test_client: TestClient, fake_redis_client: Any
    ) -> None:
        """Test that granting permission to an identity group invalidates member caches."""
        # Admin creates tenant
        admin_token = test_client.create_test_user("cache-admin-4", "Cache Admin 4")
        admin_headers = create_auth_headers(admin_token)

        create_response = test_client.post(
            ENDPOINT_TENANTS, json={"name": "Identity Group Grant Test", "description": "Test"}, headers=admin_headers
        )
        tenant_id = create_response.json()["id"]

        # Create user with identity group
        identity_group_id = "ig-cache-test-001"
        user_token = test_client.create_test_user("cache-ig-user-1", "Cache IG User 1", idp_groups=[identity_group_id])
        user_headers = create_auth_headers(user_token)

        # User has no access initially (caches this)
        response_before = test_client.get(ENDPOINT_TENANT_DETAIL.format(tenant_id=tenant_id), headers=user_headers)
        assert response_before.status_code == status.HTTP_403_FORBIDDEN

        # Admin grants CHAT_AGENTS_ADMIN permission to identity group
        grant_response = test_client.put(
            ENDPOINT_TENANT_PRINCIPALS.format(tenant_id=tenant_id),
            json={
                "principal_id": identity_group_id,
                "principal_type": PRINCIPAL_TYPE_GROUP,
                "role": ROLE_CHAT_AGENTS_ADMIN,
            },
            headers=admin_headers,
        )
        assert grant_response.status_code == status.HTTP_200_OK

        # User should NOW have access via identity group (cache must be invalidated)
        response_after = test_client.get(ENDPOINT_TENANT_DETAIL.format(tenant_id=tenant_id), headers=user_headers)
        assert response_after.status_code == status.HTTP_200_OK

    def test_multiple_permission_changes_invalidate_cache(
        self, test_client: TestClient, fake_redis_client: Any
    ) -> None:
        """Test multiple permission changes all invalidate cache correctly."""
        # Admin creates tenant
        admin_token = test_client.create_test_user("cache-admin-5", "Cache Admin 5")
        admin_headers = create_auth_headers(admin_token)

        create_response = test_client.post(
            ENDPOINT_TENANTS, json={"name": "Multiple Changes Test", "description": "Test"}, headers=admin_headers
        )
        tenant_id = create_response.json()["id"]

        # Regular user
        user_token = test_client.create_test_user("cache-regular-3", "Cache Regular 3")
        user_headers = create_auth_headers(user_token)

        # 1. User has no access
        assert (
            test_client.get(ENDPOINT_TENANT_DETAIL.format(tenant_id=tenant_id), headers=user_headers).status_code
            == status.HTTP_403_FORBIDDEN
        )

        # 2. Grant READER
        test_client.put(
            ENDPOINT_TENANT_PRINCIPALS.format(tenant_id=tenant_id),
            json={"principal_id": "cache-regular-3", "principal_type": PRINCIPAL_TYPE_USER, "role": ROLE_READER},
            headers=admin_headers,
        )
        # User can now read
        assert (
            test_client.get(ENDPOINT_TENANT_DETAIL.format(tenant_id=tenant_id), headers=user_headers).status_code
            == status.HTTP_200_OK
        )
        # But cannot update
        assert (
            test_client.patch(
                ENDPOINT_TENANT_DETAIL.format(tenant_id=tenant_id), json={"name": "Fail"}, headers=user_headers
            ).status_code
            == status.HTTP_403_FORBIDDEN
        )

        # 3. Add GLOBAL_ADMIN
        test_client.put(
            ENDPOINT_TENANT_PRINCIPALS.format(tenant_id=tenant_id),
            json={"principal_id": "cache-regular-3", "principal_type": PRINCIPAL_TYPE_USER, "role": ROLE_GLOBAL_ADMIN},
            headers=admin_headers,
        )
        # User can now update
        assert (
            test_client.patch(
                ENDPOINT_TENANT_DETAIL.format(tenant_id=tenant_id), json={"name": "Success"}, headers=user_headers
            ).status_code
            == status.HTTP_200_OK
        )

        # 4. Remove GLOBAL_ADMIN
        test_client.request(
            "DELETE",
            ENDPOINT_TENANT_PRINCIPALS.format(tenant_id=tenant_id),
            json={"principal_id": "cache-regular-3", "principal_type": PRINCIPAL_TYPE_USER, "role": ROLE_GLOBAL_ADMIN},
            headers=admin_headers,
        )
        # User can read (still has READER)
        assert (
            test_client.get(ENDPOINT_TENANT_DETAIL.format(tenant_id=tenant_id), headers=user_headers).status_code
            == status.HTTP_200_OK
        )
        # But cannot update anymore
        assert (
            test_client.patch(
                ENDPOINT_TENANT_DETAIL.format(tenant_id=tenant_id), json={"name": "Fail2"}, headers=user_headers
            ).status_code
            == status.HTTP_403_FORBIDDEN
        )

        # 5. Remove READER
        test_client.request(
            "DELETE",
            ENDPOINT_TENANT_PRINCIPALS.format(tenant_id=tenant_id),
            json={"principal_id": "cache-regular-3", "principal_type": PRINCIPAL_TYPE_USER, "role": ROLE_READER},
            headers=admin_headers,
        )
        # User cannot access at all
        assert (
            test_client.get(ENDPOINT_TENANT_DETAIL.format(tenant_id=tenant_id), headers=user_headers).status_code
            == status.HTTP_403_FORBIDDEN
        )

    def test_user_tenants_list_cached_correctly(self, test_client: TestClient, fake_redis_client: Any) -> None:
        """Test that user's tenant list is cached and invalidated correctly."""
        # User creates first tenant
        user_token = test_client.create_test_user("cache-list-user", "Cache List User")
        user_headers = create_auth_headers(user_token)

        # Create first tenant
        tenant1_response = test_client.post(
            ENDPOINT_TENANTS, json={"name": "Tenant 1", "description": "First"}, headers=user_headers
        )
        tenant1_response.json()["id"]

        # List tenants (should cache with 1 tenant)
        list1 = test_client.get(ENDPOINT_TENANTS, headers=user_headers)
        assert list1.status_code == status.HTTP_200_OK
        assert len(list1.json()) == 1

        # Create second tenant
        test_client.post(ENDPOINT_TENANTS, json={"name": "Tenant 2", "description": "Second"}, headers=user_headers)

        # List should now show 2 tenants (cache invalidated)
        list2 = test_client.get(ENDPOINT_TENANTS, headers=user_headers)
        assert list2.status_code == status.HTTP_200_OK
        assert len(list2.json()) == 2

    def test_cache_isolated_between_users(self, test_client: TestClient, fake_redis_client: Any) -> None:
        """Test that cache is properly isolated between different users."""
        # User A creates tenant
        user_a_token = test_client.create_test_user("cache-iso-a", "Cache Iso A")
        headers_a = create_auth_headers(user_a_token)

        tenant_response = test_client.post(
            ENDPOINT_TENANTS, json={"name": "Isolated Tenant", "description": "Test"}, headers=headers_a
        )
        tenant_id = tenant_response.json()["id"]

        # User A can access (caches permission)
        response_a = test_client.get(ENDPOINT_TENANT_DETAIL.format(tenant_id=tenant_id), headers=headers_a)
        assert response_a.status_code == status.HTTP_200_OK

        # User B cannot access (should not use User A's cache)
        user_b_token = test_client.create_test_user("cache-iso-b", "Cache Iso B")
        headers_b = create_auth_headers(user_b_token)

        response_b = test_client.get(ENDPOINT_TENANT_DETAIL.format(tenant_id=tenant_id), headers=headers_b)
        assert response_b.status_code == status.HTTP_403_FORBIDDEN

        # User A should still have access
        response_a2 = test_client.get(ENDPOINT_TENANT_DETAIL.format(tenant_id=tenant_id), headers=headers_a)
        assert response_a2.status_code == status.HTTP_200_OK
