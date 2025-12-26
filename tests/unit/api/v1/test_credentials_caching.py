"""Tests for credentials caching."""
from typing import Any
from fastapi import status
from starlette.testclient import TestClient

from unifiedui.core.database.enums import PermissionActionEnum, PrincipalTypeEnum
from tests.conftest import create_auth_headers


# API Endpoints
ENDPOINT_TENANTS = "/api/v1/tenants"
ENDPOINT_CREDENTIALS = "/api/v1/tenants/{tenant_id}/credentials"
ENDPOINT_CREDENTIAL_DETAIL = "/api/v1/tenants/{tenant_id}/credentials/{credential_id}"
ENDPOINT_CREDENTIAL_PRINCIPALS = "/api/v1/tenants/{tenant_id}/credentials/{credential_id}/principals"
ENDPOINT_PRINCIPAL_DETAIL = "/api/v1/tenants/{tenant_id}/credentials/{credential_id}/principals/{principal_id}"

# Roles
ROLE_READ = PermissionActionEnum.READ.value
ROLE_WRITE = PermissionActionEnum.WRITE.value
ROLE_ADMIN = PermissionActionEnum.ADMIN.value

# Principal Types
PRINCIPAL_TYPE_USER = PrincipalTypeEnum.IDENTITY_USER.value
PRINCIPAL_TYPE_GROUP = PrincipalTypeEnum.IDENTITY_GROUP.value


def create_tenant_for_user(test_client: TestClient, user_token: Any, tenant_name: str = "Test Tenant") -> str:
    """Helper function to create a tenant and return its ID."""
    headers = create_auth_headers(user_token, use_cache=False)
    response = test_client.post(
        ENDPOINT_TENANTS,
        json={"name": tenant_name, "description": f"Tenant for {user_token.get_id()}"},
        headers=headers
    )
    assert response.status_code == status.HTTP_201_CREATED
    return response.json()["id"]


def create_credential(test_client: TestClient, tenant_id: str, headers: dict, cred_name: str = "Test Credential") -> str:
    """Helper function to create a credential and return its ID."""
    response = test_client.post(
        ENDPOINT_CREDENTIALS.format(tenant_id=tenant_id),
        json={
            "name": cred_name,
            "description": f"Credential {cred_name}",
            "credential_type": "API_KEY",
            "secret_value": f"secret-{cred_name}"
        },
        headers=headers
    )
    assert response.status_code == status.HTTP_201_CREATED
    return response.json()["id"]


def add_user_to_tenant(test_client: TestClient, tenant_id: str, admin_headers: dict, user_id: str, role: str = "READER") -> None:
    """Helper function to add a user to a tenant."""
    response = test_client.put(
        f"/api/v1/tenants/{tenant_id}/principals",
        json={
            "principal_id": user_id,
            "principal_type": PRINCIPAL_TYPE_USER,
            "role": role
        },
        headers=admin_headers
    )
    assert response.status_code == status.HTTP_200_OK


class TestCredentialCaching:
    """Test suite for credential caching behavior with X-Use-Cache enabled."""
    
    def test_creator_permissions_cached(self, test_client: TestClient, fake_redis_client: Any) -> None:
        """Test that creator's ADMIN permission is cached correctly."""
        # Create user and tenant
        user_token = test_client.create_test_user("cache-creator", "Cache Creator")
        headers = create_auth_headers(user_token)
        tenant_id = create_tenant_for_user(test_client, user_token)
        
        # Create credential
        credential_id = create_credential(test_client, tenant_id, headers, "Cached Credential")
        
        # First access - should cache the permissions
        response1 = test_client.get(
            ENDPOINT_CREDENTIAL_DETAIL.format(tenant_id=tenant_id, credential_id=credential_id),
            headers=headers
        )
        assert response1.status_code == status.HTTP_200_OK
        
        # Second access - should use cached permissions
        response2 = test_client.get(
            ENDPOINT_CREDENTIAL_DETAIL.format(tenant_id=tenant_id, credential_id=credential_id),
            headers=headers
        )
        assert response2.status_code == status.HTTP_200_OK
        
        # User should still be able to update (has ADMIN)
        update_response = test_client.patch(
            ENDPOINT_CREDENTIAL_DETAIL.format(tenant_id=tenant_id, credential_id=credential_id),
            json={"name": "Updated Cached Credential"},
            headers=headers
        )
        assert update_response.status_code == status.HTTP_200_OK
    
    def test_no_access_cached(self, test_client: TestClient, fake_redis_client: Any) -> None:
        """Test that lack of access is handled correctly with caching."""
        # User A creates tenant and credential
        user_a_token = test_client.create_test_user("cache-user-a", "Cache User A")
        headers_a = create_auth_headers(user_a_token)
        tenant_id = create_tenant_for_user(test_client, user_a_token)
        credential_id = create_credential(test_client, tenant_id, headers_a, "Private Cached Credential")
        
        # User B (not tenant member)
        user_b_token = test_client.create_test_user("cache-user-b", "Cache User B")
        headers_b = create_auth_headers(user_b_token)
        
        # First access - no permission (should cache the lack of access)
        response1 = test_client.get(
            ENDPOINT_CREDENTIAL_DETAIL.format(tenant_id=tenant_id, credential_id=credential_id),
            headers=headers_b
        )
        assert response1.status_code == status.HTTP_403_FORBIDDEN
        
        # Second access - should still be forbidden
        response2 = test_client.get(
            ENDPOINT_CREDENTIAL_DETAIL.format(tenant_id=tenant_id, credential_id=credential_id),
            headers=headers_b
        )
        assert response2.status_code == status.HTTP_403_FORBIDDEN
    
    def test_direct_user_permission_grant_invalidates_cache(self, test_client: TestClient, fake_redis_client: Any) -> None:
        """Test that granting permission to a user invalidates their cache."""
        # Admin creates tenant and credential
        admin_token = test_client.create_test_user("cache-admin-1", "Cache Admin 1")
        admin_headers = create_auth_headers(admin_token)
        tenant_id = create_tenant_for_user(test_client, admin_token)
        credential_id = create_credential(test_client, tenant_id, admin_headers, "Permission Grant Test")
        
        # Regular user has no access initially
        user_token = test_client.create_test_user("cache-regular-1", "Cache Regular 1")
        user_headers = create_auth_headers(user_token)
        
        # Add user to tenant first
        add_user_to_tenant(test_client, tenant_id, admin_headers, "cache-regular-1", "READER")
        
        # User cannot access (this caches the lack of permission)
        response_before = test_client.get(
            ENDPOINT_CREDENTIAL_DETAIL.format(tenant_id=tenant_id, credential_id=credential_id),
            headers=user_headers
        )
        assert response_before.status_code == status.HTTP_403_FORBIDDEN
        
        # Admin grants WRITE permission to user
        grant_response = test_client.put(
            ENDPOINT_CREDENTIAL_PRINCIPALS.format(tenant_id=tenant_id, credential_id=credential_id),
            json={
                "principal_id": "cache-regular-1",
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_WRITE
            },
            headers=admin_headers
        )
        assert grant_response.status_code == status.HTTP_200_OK
        
        # User should NOW have access (cache must be invalidated)
        response_after = test_client.get(
            ENDPOINT_CREDENTIAL_DETAIL.format(tenant_id=tenant_id, credential_id=credential_id),
            headers=user_headers
        )
        assert response_after.status_code == status.HTTP_200_OK
        
        # User can now update
        update_response = test_client.patch(
            ENDPOINT_CREDENTIAL_DETAIL.format(tenant_id=tenant_id, credential_id=credential_id),
            json={"name": "Now It Works"},
            headers=user_headers
        )
        assert update_response.status_code == status.HTTP_200_OK
        assert update_response.json()["name"] == "Now It Works"
        
        # User CANNOT delete (only WRITE, not ADMIN)
        delete_response = test_client.request(
            "DELETE",
            ENDPOINT_CREDENTIAL_DETAIL.format(tenant_id=tenant_id, credential_id=credential_id),
            headers=user_headers
        )
        assert delete_response.status_code == status.HTTP_403_FORBIDDEN
    
    def test_direct_user_permission_revoke_invalidates_cache(self, test_client: TestClient, fake_redis_client: Any) -> None:
        """Test that revoking permission from a user invalidates their cache."""
        # Admin creates tenant and credential
        admin_token = test_client.create_test_user("cache-admin-2", "Cache Admin 2")
        admin_headers = create_auth_headers(admin_token)
        tenant_id = create_tenant_for_user(test_client, admin_token)
        credential_id = create_credential(test_client, tenant_id, admin_headers, "Permission Revoke Test")
        
        # Regular user gets ADMIN permission
        user_token = test_client.create_test_user("cache-regular-2", "Cache Regular 2")
        user_headers = create_auth_headers(user_token)
        
        # Add user to tenant first
        add_user_to_tenant(test_client, tenant_id, admin_headers, "cache-regular-2", "READER")
        
        # Grant ADMIN permission
        test_client.put(
            ENDPOINT_CREDENTIAL_PRINCIPALS.format(tenant_id=tenant_id, credential_id=credential_id),
            json={
                "principal_id": "cache-regular-2",
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_ADMIN
            },
            headers=admin_headers
        )
        
        # User CAN update credential (cache this permission)
        update_response1 = test_client.patch(
            ENDPOINT_CREDENTIAL_DETAIL.format(tenant_id=tenant_id, credential_id=credential_id),
            json={"name": "Updated Once"},
            headers=user_headers
        )
        assert update_response1.status_code == status.HTTP_200_OK
        
        # Admin revokes ADMIN permission
        revoke_response = test_client.request(
            "DELETE",
            ENDPOINT_CREDENTIAL_PRINCIPALS.format(tenant_id=tenant_id, credential_id=credential_id),
            json={
                "principal_id": "cache-regular-2",
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_ADMIN
            },
            headers=admin_headers
        )
        assert revoke_response.status_code == status.HTTP_204_NO_CONTENT
        
        # User should NOW NOT have access (cache must be invalidated)
        update_response2 = test_client.patch(
            ENDPOINT_CREDENTIAL_DETAIL.format(tenant_id=tenant_id, credential_id=credential_id),
            json={"name": "Should Fail"},
            headers=user_headers
        )
        assert update_response2.status_code == status.HTTP_403_FORBIDDEN
        
        # User can also not view
        get_response = test_client.get(
            ENDPOINT_CREDENTIAL_DETAIL.format(tenant_id=tenant_id, credential_id=credential_id),
            headers=user_headers
        )
        assert get_response.status_code == status.HTTP_403_FORBIDDEN
    
    def test_multiple_permission_changes_invalidate_cache(self, test_client: TestClient, fake_redis_client: Any) -> None:
        """Test that multiple permission changes properly invalidate cache."""
        # Admin creates tenant and credential
        admin_token = test_client.create_test_user("cache-admin-3", "Cache Admin 3")
        admin_headers = create_auth_headers(admin_token)
        tenant_id = create_tenant_for_user(test_client, admin_token)
        credential_id = create_credential(test_client, tenant_id, admin_headers, "Multiple Changes Test")
        
        # Create user
        user_token = test_client.create_test_user("cache-regular-3", "Cache Regular 3")
        user_headers = create_auth_headers(user_token)
        
        # Add user to tenant
        add_user_to_tenant(test_client, tenant_id, admin_headers, "cache-regular-3", "READER")
        
        # User cannot access initially
        response1 = test_client.get(
            ENDPOINT_CREDENTIAL_DETAIL.format(tenant_id=tenant_id, credential_id=credential_id),
            headers=user_headers
        )
        assert response1.status_code == status.HTTP_403_FORBIDDEN
        
        # Grant READ permission
        test_client.put(
            ENDPOINT_CREDENTIAL_PRINCIPALS.format(tenant_id=tenant_id, credential_id=credential_id),
            json={
                "principal_id": "cache-regular-3",
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_READ
            },
            headers=admin_headers
        )
        
        # User can now view
        response2 = test_client.get(
            ENDPOINT_CREDENTIAL_DETAIL.format(tenant_id=tenant_id, credential_id=credential_id),
            headers=user_headers
        )
        assert response2.status_code == status.HTTP_200_OK
        
        # User still cannot modify (READ only)
        response3 = test_client.patch(
            ENDPOINT_CREDENTIAL_DETAIL.format(tenant_id=tenant_id, credential_id=credential_id),
            json={"name": "Should Fail"},
            headers=user_headers
        )
        assert response3.status_code == status.HTTP_403_FORBIDDEN
        
        # Upgrade to WRITE permission (replaces READ due to single-role model)
        test_client.put(
            ENDPOINT_CREDENTIAL_PRINCIPALS.format(tenant_id=tenant_id, credential_id=credential_id),
            json={
                "principal_id": "cache-regular-3",
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_WRITE
            },
            headers=admin_headers
        )
        
        # User CAN now modify
        response4 = test_client.patch(
            ENDPOINT_CREDENTIAL_DETAIL.format(tenant_id=tenant_id, credential_id=credential_id),
            json={"name": "Now It Works"},
            headers=user_headers
        )
        assert response4.status_code == status.HTTP_200_OK
        
        # Upgrade to ADMIN permission
        test_client.put(
            ENDPOINT_CREDENTIAL_PRINCIPALS.format(tenant_id=tenant_id, credential_id=credential_id),
            json={
                "principal_id": "cache-regular-3",
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_ADMIN
            },
            headers=admin_headers
        )
        
        # User CAN now delete
        delete_response = test_client.request(
            "DELETE",
            ENDPOINT_CREDENTIAL_DETAIL.format(tenant_id=tenant_id, credential_id=credential_id),
            headers=user_headers
        )
        assert delete_response.status_code == status.HTTP_204_NO_CONTENT
    
    def test_credentials_list_cached_correctly(self, test_client: TestClient, fake_redis_client: Any) -> None:
        """Test that credentials list is cached correctly per user."""
        # Admin creates tenant
        admin_token = test_client.create_test_user("cache-list-admin", "Cache List Admin")
        admin_headers = create_auth_headers(admin_token)
        tenant_id = create_tenant_for_user(test_client, admin_token)
        
        # Create multiple credentials
        cred1_id = create_credential(test_client, tenant_id, admin_headers, "Credential 1")
        cred2_id = create_credential(test_client, tenant_id, admin_headers, "Credential 2")
        
        # Regular user
        user_token = test_client.create_test_user("cache-list-user", "Cache List User")
        user_headers = create_auth_headers(user_token)
        
        # Add user to tenant
        add_user_to_tenant(test_client, tenant_id, admin_headers, "cache-list-user", "READER")
        
        # Grant permission to only first credential
        test_client.put(
            ENDPOINT_CREDENTIAL_PRINCIPALS.format(tenant_id=tenant_id, credential_id=cred1_id),
            json={
                "principal_id": "cache-list-user",
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_READ
            },
            headers=admin_headers
        )
        
        # User lists credentials - should see only cred1
        list_response1 = test_client.get(
            ENDPOINT_CREDENTIALS.format(tenant_id=tenant_id),
            headers=user_headers
        )
        assert list_response1.status_code == status.HTTP_200_OK
        data1 = list_response1.json()
        assert len(data1) == 1
        assert data1[0]["id"] == cred1_id
        
        # Grant permission to second credential
        test_client.put(
            ENDPOINT_CREDENTIAL_PRINCIPALS.format(tenant_id=tenant_id, credential_id=cred2_id),
            json={
                "principal_id": "cache-list-user",
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_READ
            },
            headers=admin_headers
        )
        
        # User lists again - should now see both (cache invalidated)
        list_response2 = test_client.get(
            ENDPOINT_CREDENTIALS.format(tenant_id=tenant_id),
            headers=user_headers
        )
        assert list_response2.status_code == status.HTTP_200_OK
        data2 = list_response2.json()
        assert len(data2) == 2
    
    def test_cache_isolated_between_users(self, test_client: TestClient, fake_redis_client: Any) -> None:
        """Test that cache is properly isolated between different users."""
        # Admin creates tenant
        admin_token = test_client.create_test_user("cache-iso-admin", "Cache Iso Admin")
        admin_headers = create_auth_headers(admin_token)
        tenant_id = create_tenant_for_user(test_client, admin_token)
        
        # Create credential
        credential_id = create_credential(test_client, tenant_id, admin_headers, "Shared Credential")
        
        # User A
        user_a_token = test_client.create_test_user("cache-iso-a", "Cache Iso A")
        headers_a = create_auth_headers(user_a_token)
        
        # User B
        user_b_token = test_client.create_test_user("cache-iso-b", "Cache Iso B")
        headers_b = create_auth_headers(user_b_token)
        
        # Add both users to tenant
        add_user_to_tenant(test_client, tenant_id, admin_headers, "cache-iso-a", "READER")
        add_user_to_tenant(test_client, tenant_id, admin_headers, "cache-iso-b", "READER")
        
        # Grant READ to user A only
        test_client.put(
            ENDPOINT_CREDENTIAL_PRINCIPALS.format(tenant_id=tenant_id, credential_id=credential_id),
            json={
                "principal_id": "cache-iso-a",
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_READ
            },
            headers=admin_headers
        )
        
        # User A can access
        response_a = test_client.get(
            ENDPOINT_CREDENTIAL_DETAIL.format(tenant_id=tenant_id, credential_id=credential_id),
            headers=headers_a
        )
        assert response_a.status_code == status.HTTP_200_OK
        
        # User B cannot access (different cache)
        response_b = test_client.get(
            ENDPOINT_CREDENTIAL_DETAIL.format(tenant_id=tenant_id, credential_id=credential_id),
            headers=headers_b
        )
        assert response_b.status_code == status.HTTP_403_FORBIDDEN
        
        # Grant WRITE to user B
        test_client.put(
            ENDPOINT_CREDENTIAL_PRINCIPALS.format(tenant_id=tenant_id, credential_id=credential_id),
            json={
                "principal_id": "cache-iso-b",
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_WRITE
            },
            headers=admin_headers
        )
        
        # User B can now access
        response_b2 = test_client.get(
            ENDPOINT_CREDENTIAL_DETAIL.format(tenant_id=tenant_id, credential_id=credential_id),
            headers=headers_b
        )
        assert response_b2.status_code == status.HTTP_200_OK
        
        # User B can update (WRITE)
        update_response_b = test_client.patch(
            ENDPOINT_CREDENTIAL_DETAIL.format(tenant_id=tenant_id, credential_id=credential_id),
            json={"name": "Updated by B"},
            headers=headers_b
        )
        assert update_response_b.status_code == status.HTTP_200_OK
        
        # User A cannot update (only READ)
        update_response_a = test_client.patch(
            ENDPOINT_CREDENTIAL_DETAIL.format(tenant_id=tenant_id, credential_id=credential_id),
            json={"name": "Should Fail"},
            headers=headers_a
        )
        assert update_response_a.status_code == status.HTTP_403_FORBIDDEN
    
    def test_tenant_admin_bypass_cached_correctly(self, test_client: TestClient, fake_redis_client: Any) -> None:
        """Test that tenant admin bypass is cached correctly."""
        # User A creates tenant (becomes GLOBAL_ADMIN)
        user_a_token = test_client.create_test_user("cache-tenant-admin", "Cache Tenant Admin")
        headers_a = create_auth_headers(user_a_token)
        tenant_id = create_tenant_for_user(test_client, user_a_token)
        
        # User B creates credential
        user_b_token = test_client.create_test_user("cache-cred-owner", "Cache Cred Owner")
        headers_b = create_auth_headers(user_b_token)
        
        # Add user B to tenant
        add_user_to_tenant(test_client, tenant_id, headers_a, "cache-cred-owner", "CREDENTIALS_CREATOR")
        
        # User B creates credential
        credential_id = create_credential(test_client, tenant_id, headers_b, "B's Credential")
        
        # User A (GLOBAL_ADMIN) can access without explicit permission (cache this)
        response1 = test_client.get(
            ENDPOINT_CREDENTIAL_DETAIL.format(tenant_id=tenant_id, credential_id=credential_id),
            headers=headers_a
        )
        assert response1.status_code == status.HTTP_200_OK
        
        # User A can update (cached admin bypass)
        update_response = test_client.patch(
            ENDPOINT_CREDENTIAL_DETAIL.format(tenant_id=tenant_id, credential_id=credential_id),
            json={"name": "Updated by Global Admin"},
            headers=headers_a
        )
        assert update_response.status_code == status.HTTP_200_OK
        
        # User A can delete (cached admin bypass)
        delete_response = test_client.request(
            "DELETE",
            ENDPOINT_CREDENTIAL_DETAIL.format(tenant_id=tenant_id, credential_id=credential_id),
            headers=headers_a
        )
        assert delete_response.status_code == status.HTTP_204_NO_CONTENT


class TestCredentialTagCacheInvalidation:
    """Test suite for cache invalidation when adding/removing tags from credentials."""
    
    def test_adding_tags_invalidates_cache(self, test_client: TestClient, fake_redis_client: Any) -> None:
        """Test that adding tags to a credential invalidates the credential cache."""
        admin_token = test_client.create_test_user("cred-tag-cache-1", "Cred Tag Cache 1")
        admin_headers = create_auth_headers(admin_token)
        tenant_id = create_tenant_for_user(test_client, admin_token)
        credential_id = create_credential(test_client, tenant_id, admin_headers, "Tagged Credential")
        
        # First read - cache the credential (no tags)
        response1 = test_client.get(
            ENDPOINT_CREDENTIAL_DETAIL.format(tenant_id=tenant_id, credential_id=credential_id),
            headers=admin_headers
        )
        assert response1.status_code == status.HTTP_200_OK
        assert response1.json()["tags"] == []
        
        # Add tags to credential
        test_client.put(
            f"/api/v1/tenants/{tenant_id}/credentials/{credential_id}/tags",
            json={"tags": ["production", "api-key"]},
            headers=admin_headers
        )
        
        # Read credential again - should see the tags (cache invalidated)
        response2 = test_client.get(
            ENDPOINT_CREDENTIAL_DETAIL.format(tenant_id=tenant_id, credential_id=credential_id),
            headers=admin_headers
        )
        assert response2.status_code == status.HTTP_200_OK
        assert len(response2.json()["tags"]) == 2
    
    def test_removing_tags_invalidates_cache(self, test_client: TestClient, fake_redis_client: Any) -> None:
        """Test that removing tags from a credential invalidates the credential cache."""
        admin_token = test_client.create_test_user("cred-tag-cache-2", "Cred Tag Cache 2")
        admin_headers = create_auth_headers(admin_token)
        tenant_id = create_tenant_for_user(test_client, admin_token)
        credential_id = create_credential(test_client, tenant_id, admin_headers, "Tagged Credential 2")
        
        # Set initial tags
        test_client.put(
            f"/api/v1/tenants/{tenant_id}/credentials/{credential_id}/tags",
            json={"tags": ["tag1", "tag2"]},
            headers=admin_headers
        )
        
        # Read and cache
        response1 = test_client.get(
            ENDPOINT_CREDENTIAL_DETAIL.format(tenant_id=tenant_id, credential_id=credential_id),
            headers=admin_headers
        )
        assert len(response1.json()["tags"]) == 2
        
        # Remove tags
        test_client.delete(
            f"/api/v1/tenants/{tenant_id}/credentials/{credential_id}/tags",
            headers=admin_headers
        )
        
        # Read credential again - should have no tags (cache invalidated)
        response2 = test_client.get(
            ENDPOINT_CREDENTIAL_DETAIL.format(tenant_id=tenant_id, credential_id=credential_id),
            headers=admin_headers
        )
        assert response2.status_code == status.HTTP_200_OK
        assert len(response2.json()["tags"]) == 0
    
    def test_replacing_tags_invalidates_cache(self, test_client: TestClient, fake_redis_client: Any) -> None:
        """Test that replacing tags on a credential invalidates the credential cache."""
        admin_token = test_client.create_test_user("cred-tag-cache-3", "Cred Tag Cache 3")
        admin_headers = create_auth_headers(admin_token)
        tenant_id = create_tenant_for_user(test_client, admin_token)
        credential_id = create_credential(test_client, tenant_id, admin_headers, "Tagged Credential 3")
        
        # Set initial tags
        test_client.put(
            f"/api/v1/tenants/{tenant_id}/credentials/{credential_id}/tags",
            json={"tags": ["old-tag"]},
            headers=admin_headers
        )
        
        # Read and cache
        response1 = test_client.get(
            ENDPOINT_CREDENTIAL_DETAIL.format(tenant_id=tenant_id, credential_id=credential_id),
            headers=admin_headers
        )
        assert len(response1.json()["tags"]) == 1
        assert response1.json()["tags"][0]["name"] == "old-tag"
        
        # Replace with new tags
        test_client.put(
            f"/api/v1/tenants/{tenant_id}/credentials/{credential_id}/tags",
            json={"tags": ["new-tag-1", "new-tag-2"]},
            headers=admin_headers
        )
        
        # Read credential again - should have new tags (cache invalidated)
        response2 = test_client.get(
            ENDPOINT_CREDENTIAL_DETAIL.format(tenant_id=tenant_id, credential_id=credential_id),
            headers=admin_headers
        )
        assert response2.status_code == status.HTTP_200_OK
        assert len(response2.json()["tags"]) == 2
        tag_names = [t["name"] for t in response2.json()["tags"]]
        assert "new-tag-1" in tag_names
        assert "new-tag-2" in tag_names
