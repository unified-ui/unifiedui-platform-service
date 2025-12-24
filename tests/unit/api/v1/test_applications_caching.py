"""Tests for applications caching."""
import uuid
from typing import Any
from fastapi import status
from starlette.testclient import TestClient

from aihub.core.database.enums import PermissionActionEnum, PrincipalTypeEnum
from tests.conftest import create_auth_headers


# API Endpoints
ENDPOINT_TENANTS = "/api/v1/tenants"
ENDPOINT_APPLICATIONS = "/api/v1/tenants/{tenant_id}/applications"
ENDPOINT_APPLICATION_DETAIL = "/api/v1/tenants/{tenant_id}/applications/{application_id}"
ENDPOINT_APPLICATION_PRINCIPALS = "/api/v1/tenants/{tenant_id}/applications/{application_id}/principals"
ENDPOINT_PRINCIPAL_DETAIL = "/api/v1/tenants/{tenant_id}/applications/{application_id}/principals/{principal_id}"

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


def create_application(test_client: TestClient, tenant_id: str, headers: dict, app_name: str = "Test App") -> str:
    """Helper function to create an application and return its ID."""
    response = test_client.post(
        ENDPOINT_APPLICATIONS.format(tenant_id=tenant_id),
        json={"name": app_name, "description": f"Application {app_name}"},
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


class TestApplicationCaching:
    """Test suite for application caching behavior with X-Use-Cache enabled."""
    
    def test_creator_permissions_cached(self, test_client: TestClient, fake_redis_client: Any) -> None:
        """Test that creator's ADMIN permission is cached correctly."""
        # Create user and tenant
        user_token = test_client.create_test_user("cache-creator", "Cache Creator")
        headers = create_auth_headers(user_token)
        tenant_id = create_tenant_for_user(test_client, user_token)
        
        # Create application
        app_id = create_application(test_client, tenant_id, headers, "Cached App")
        
        # First access - should cache the permissions
        response1 = test_client.get(
            ENDPOINT_APPLICATION_DETAIL.format(tenant_id=tenant_id, application_id=app_id),
            headers=headers
        )
        assert response1.status_code == status.HTTP_200_OK
        
        # Second access - should use cached permissions
        response2 = test_client.get(
            ENDPOINT_APPLICATION_DETAIL.format(tenant_id=tenant_id, application_id=app_id),
            headers=headers
        )
        assert response2.status_code == status.HTTP_200_OK
        
        # User should still be able to update (has ADMIN)
        update_response = test_client.patch(
            ENDPOINT_APPLICATION_DETAIL.format(tenant_id=tenant_id, application_id=app_id),
            json={"name": "Updated Cached App"},
            headers=headers
        )
        assert update_response.status_code == status.HTTP_200_OK
    
    def test_no_access_cached(self, test_client: TestClient, fake_redis_client: Any) -> None:
        """Test that lack of access is handled correctly with caching."""
        # User A creates tenant and application
        user_a_token = test_client.create_test_user("cache-user-a", "Cache User A")
        headers_a = create_auth_headers(user_a_token)
        tenant_id = create_tenant_for_user(test_client, user_a_token)
        app_id = create_application(test_client, tenant_id, headers_a, "Private Cached App")
        
        # User B (not a member of tenant or application)
        user_b_token = test_client.create_test_user("cache-user-b", "Cache User B")
        headers_b = create_auth_headers(user_b_token)
        
        # First access - no permission (should cache the lack of access)
        response1 = test_client.get(
            ENDPOINT_APPLICATION_DETAIL.format(tenant_id=tenant_id, application_id=app_id),
            headers=headers_b
        )
        assert response1.status_code == status.HTTP_403_FORBIDDEN
        
        # Second access - should still be forbidden
        response2 = test_client.get(
            ENDPOINT_APPLICATION_DETAIL.format(tenant_id=tenant_id, application_id=app_id),
            headers=headers_b
        )
        assert response2.status_code == status.HTTP_403_FORBIDDEN
    
    def test_direct_user_permission_grant_invalidates_cache(self, test_client: TestClient, fake_redis_client: Any) -> None:
        """Test that granting permission to a user invalidates their cache."""
        # Admin creates tenant and application
        admin_token = test_client.create_test_user("cache-admin-1", "Cache Admin 1")
        admin_headers = create_auth_headers(admin_token)
        tenant_id = create_tenant_for_user(test_client, admin_token)
        app_id = create_application(test_client, tenant_id, admin_headers, "Permission Grant Test")
        
        # Regular user has no access initially
        user_token = test_client.create_test_user("cache-regular-1", "Cache Regular 1")
        user_headers = create_auth_headers(user_token)
        
        # Add user to tenant (required for any tenant resource access)
        add_user_to_tenant(test_client, tenant_id, admin_headers, "cache-regular-1", "READER")
        
        # User cannot access application (this caches the lack of permission)
        response_before = test_client.get(
            ENDPOINT_APPLICATION_DETAIL.format(tenant_id=tenant_id, application_id=app_id),
            headers=user_headers
        )
        assert response_before.status_code == status.HTTP_403_FORBIDDEN
        
        # Admin grants WRITE permission to user
        grant_response = test_client.put(
            ENDPOINT_APPLICATION_PRINCIPALS.format(tenant_id=tenant_id, application_id=app_id),
            json={
                "principal_id": "cache-regular-1",
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_WRITE
            },
            headers=admin_headers
        )
        assert grant_response.status_code == status.HTTP_200_OK
        
        # User should NOW have write access (cache must be invalidated)
        response_after = test_client.patch(
            ENDPOINT_APPLICATION_DETAIL.format(tenant_id=tenant_id, application_id=app_id),
            json={"name": "Now It Works"},
            headers=user_headers
        )
        assert response_after.status_code == status.HTTP_200_OK
        
        # Verify the update worked
        assert response_after.json()["name"] == "Now It Works"
        
        # User CANNOT delete (only WRITE, not ADMIN)
        delete_response = test_client.request(
            "DELETE",
            ENDPOINT_APPLICATION_DETAIL.format(tenant_id=tenant_id, application_id=app_id),
            headers=user_headers
        )
        assert delete_response.status_code == status.HTTP_403_FORBIDDEN
    
    def test_direct_user_permission_revoke_invalidates_cache(self, test_client: TestClient, fake_redis_client: Any) -> None:
        """Test that revoking permission from a user invalidates their cache."""
        # Admin creates tenant and application
        admin_token = test_client.create_test_user("cache-admin-2", "Cache Admin 2")
        admin_headers = create_auth_headers(admin_token)
        tenant_id = create_tenant_for_user(test_client, admin_token)
        app_id = create_application(test_client, tenant_id, admin_headers, "Permission Revoke Test")
        
        # Regular user gets ADMIN permission
        user_token = test_client.create_test_user("cache-regular-2", "Cache Regular 2")
        user_headers = create_auth_headers(user_token)
        
        # Add user to tenant first
        add_user_to_tenant(test_client, tenant_id, admin_headers, "cache-regular-2", "READER")
        
        # Grant ADMIN permission
        test_client.put(
            ENDPOINT_APPLICATION_PRINCIPALS.format(tenant_id=tenant_id, application_id=app_id),
            json={
                "principal_id": "cache-regular-2",
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_ADMIN
            },
            headers=admin_headers
        )
        
        # User CAN update application (cache this permission)
        update_response1 = test_client.patch(
            ENDPOINT_APPLICATION_DETAIL.format(tenant_id=tenant_id, application_id=app_id),
            json={"name": "Updated Once"},
            headers=user_headers
        )
        assert update_response1.status_code == status.HTTP_200_OK
        
        # Admin revokes ADMIN permission
        revoke_response = test_client.request(
            "DELETE",
            ENDPOINT_APPLICATION_PRINCIPALS.format(tenant_id=tenant_id, application_id=app_id),
            json={
                "principal_id": "cache-regular-2",
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_ADMIN
            },
            headers=admin_headers
        )
        assert revoke_response.status_code == status.HTTP_204_NO_CONTENT
        
        # User should NOW NOT have write access (cache must be invalidated)
        update_response2 = test_client.patch(
            ENDPOINT_APPLICATION_DETAIL.format(tenant_id=tenant_id, application_id=app_id),
            json={"name": "Should Fail"},
            headers=user_headers
        )
        assert update_response2.status_code == status.HTTP_403_FORBIDDEN
        
        # User cannot view either (no permission at all)
        get_response = test_client.get(
            ENDPOINT_APPLICATION_DETAIL.format(tenant_id=tenant_id, application_id=app_id),
            headers=user_headers
        )
        assert get_response.status_code == status.HTTP_403_FORBIDDEN
    
    def test_multiple_permission_changes_invalidate_cache(self, test_client: TestClient, fake_redis_client: Any) -> None:
        """Test that multiple permission changes properly invalidate cache."""
        # Admin creates tenant and application
        admin_token = test_client.create_test_user("cache-admin-3", "Cache Admin 3")
        admin_headers = create_auth_headers(admin_token)
        tenant_id = create_tenant_for_user(test_client, admin_token)
        app_id = create_application(test_client, tenant_id, admin_headers, "Multiple Changes Test")
        
        # Create user
        user_token = test_client.create_test_user("cache-regular-3", "Cache Regular 3")
        user_headers = create_auth_headers(user_token)
        
        # Add user to tenant first
        add_user_to_tenant(test_client, tenant_id, admin_headers, "cache-regular-3", "READER")
        
        # User cannot access initially
        response1 = test_client.get(
            ENDPOINT_APPLICATION_DETAIL.format(tenant_id=tenant_id, application_id=app_id),
            headers=user_headers
        )
        assert response1.status_code == status.HTTP_403_FORBIDDEN
        
        # Grant READ permission
        test_client.put(
            ENDPOINT_APPLICATION_PRINCIPALS.format(tenant_id=tenant_id, application_id=app_id),
            json={
                "principal_id": "cache-regular-3",
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_READ
            },
            headers=admin_headers
        )
        
        # User can view but cannot modify (READ only)
        get_response = test_client.get(
            ENDPOINT_APPLICATION_DETAIL.format(tenant_id=tenant_id, application_id=app_id),
            headers=user_headers
        )
        assert get_response.status_code == status.HTTP_200_OK
        
        response2 = test_client.patch(
            ENDPOINT_APPLICATION_DETAIL.format(tenant_id=tenant_id, application_id=app_id),
            json={"name": "Should Fail"},
            headers=user_headers
        )
        assert response2.status_code == status.HTTP_403_FORBIDDEN
        
        # Upgrade to WRITE permission (replaces READ due to single-role model)
        test_client.put(
            ENDPOINT_APPLICATION_PRINCIPALS.format(tenant_id=tenant_id, application_id=app_id),
            json={
                "principal_id": "cache-regular-3",
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_WRITE
            },
            headers=admin_headers
        )
        
        # User CAN now modify
        response3 = test_client.patch(
            ENDPOINT_APPLICATION_DETAIL.format(tenant_id=tenant_id, application_id=app_id),
            json={"name": "Now It Works"},
            headers=user_headers
        )
        assert response3.status_code == status.HTTP_200_OK
        
        # Upgrade to ADMIN permission
        test_client.put(
            ENDPOINT_APPLICATION_PRINCIPALS.format(tenant_id=tenant_id, application_id=app_id),
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
            ENDPOINT_APPLICATION_DETAIL.format(tenant_id=tenant_id, application_id=app_id),
            headers=user_headers
        )
        assert delete_response.status_code == status.HTTP_204_NO_CONTENT
    
    def test_applications_list_cached_correctly(self, test_client: TestClient, fake_redis_client: Any) -> None:
        """Test that application list respects permissions and caching."""
        # Admin creates tenant
        admin_token = test_client.create_test_user("list-admin", "List Admin")
        admin_headers = create_auth_headers(admin_token)
        tenant_id = create_tenant_for_user(test_client, admin_token)
        
        # Create multiple applications
        app1_id = create_application(test_client, tenant_id, admin_headers, "App 1")
        app2_id = create_application(test_client, tenant_id, admin_headers, "App 2")
        app3_id = create_application(test_client, tenant_id, admin_headers, "App 3")
        
        # Create regular user
        user_token = test_client.create_test_user("list-user", "List User")
        user_headers = create_auth_headers(user_token)
        
        # Add user to tenant first
        add_user_to_tenant(test_client, tenant_id, admin_headers, "list-user", "READER")
        
        # User sees no applications (no application permission yet)
        response1 = test_client.get(
            ENDPOINT_APPLICATIONS.format(tenant_id=tenant_id),
            headers=user_headers
        )
        assert response1.status_code == status.HTTP_200_OK
        assert len(response1.json()) == 0
        
        # Grant permission to App 1 and App 2
        test_client.put(
            ENDPOINT_APPLICATION_PRINCIPALS.format(tenant_id=tenant_id, application_id=app1_id),
            json={
                "principal_id": "list-user",
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_READ
            },
            headers=admin_headers
        )
        test_client.put(
            ENDPOINT_APPLICATION_PRINCIPALS.format(tenant_id=tenant_id, application_id=app2_id),
            json={
                "principal_id": "list-user",
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_WRITE
            },
            headers=admin_headers
        )
        
        # User now sees only App 1 and App 2
        response2 = test_client.get(
            ENDPOINT_APPLICATIONS.format(tenant_id=tenant_id),
            headers=user_headers
        )
        assert response2.status_code == status.HTTP_200_OK
        data = response2.json()
        assert len(data) == 2
        app_ids = [app["id"] for app in data]
        assert app1_id in app_ids
        assert app2_id in app_ids
        assert app3_id not in app_ids
    
    def test_cache_isolated_between_users(self, test_client: TestClient, fake_redis_client: Any) -> None:
        """Test that cache is properly isolated between different users."""
        # Admin creates tenant and application
        admin_token = test_client.create_test_user("isolation-admin", "Isolation Admin")
        admin_headers = create_auth_headers(admin_token)
        tenant_id = create_tenant_for_user(test_client, admin_token)
        app_id = create_application(test_client, tenant_id, admin_headers, "Isolation Test")
        
        # User A gets READ permission
        user_a_token = test_client.create_test_user("isolation-user-a", "Isolation User A")
        user_a_headers = create_auth_headers(user_a_token)
        add_user_to_tenant(test_client, tenant_id, admin_headers, "isolation-user-a", "READER")
        test_client.put(
            ENDPOINT_APPLICATION_PRINCIPALS.format(tenant_id=tenant_id, application_id=app_id),
            json={
                "principal_id": "isolation-user-a",
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_READ
            },
            headers=admin_headers
        )
        
        # User B gets WRITE permission
        user_b_token = test_client.create_test_user("isolation-user-b", "Isolation User B")
        user_b_headers = create_auth_headers(user_b_token)
        add_user_to_tenant(test_client, tenant_id, admin_headers, "isolation-user-b", "READER")
        test_client.put(
            ENDPOINT_APPLICATION_PRINCIPALS.format(tenant_id=tenant_id, application_id=app_id),
            json={
                "principal_id": "isolation-user-b",
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_WRITE
            },
            headers=admin_headers
        )
        
        # User A can view
        get_a = test_client.get(
            ENDPOINT_APPLICATION_DETAIL.format(tenant_id=tenant_id, application_id=app_id),
            headers=user_a_headers
        )
        assert get_a.status_code == status.HTTP_200_OK
        
        # User A cannot update
        update_a = test_client.patch(
            ENDPOINT_APPLICATION_DETAIL.format(tenant_id=tenant_id, application_id=app_id),
            json={"name": "User A Update"},
            headers=user_a_headers
        )
        assert update_a.status_code == status.HTTP_403_FORBIDDEN
        
        # User B can view and update
        get_b = test_client.get(
            ENDPOINT_APPLICATION_DETAIL.format(tenant_id=tenant_id, application_id=app_id),
            headers=user_b_headers
        )
        assert get_b.status_code == status.HTTP_200_OK
        
        update_b = test_client.patch(
            ENDPOINT_APPLICATION_DETAIL.format(tenant_id=tenant_id, application_id=app_id),
            json={"name": "User B Update"},
            headers=user_b_headers
        )
        assert update_b.status_code == status.HTTP_200_OK
        
        # User A still cannot update (different cache)
        update_a_again = test_client.patch(
            ENDPOINT_APPLICATION_DETAIL.format(tenant_id=tenant_id, application_id=app_id),
            json={"name": "User A Update Again"},
            headers=user_a_headers
        )
        assert update_a_again.status_code == status.HTTP_403_FORBIDDEN
    
    def test_tenant_admin_bypass_cached_correctly(self, test_client: TestClient, fake_redis_client: Any) -> None:
        """Test that tenant admin bypass is cached correctly."""
        # Admin creates tenant and application
        admin_token = test_client.create_test_user("bypass-admin", "Bypass Admin")
        admin_headers = create_auth_headers(admin_token)
        tenant_id = create_tenant_for_user(test_client, admin_token)
        app_id = create_application(test_client, tenant_id, admin_headers, "Bypass Test")
        
        # Create global admin user
        global_admin_token = test_client.create_test_user("bypass-global", "Bypass Global")
        global_admin_headers = create_auth_headers(global_admin_token)
        
        # Add to tenant with GLOBAL_ADMIN role
        add_user_to_tenant(test_client, tenant_id, admin_headers, "bypass-global", "GLOBAL_ADMIN")
        
        # Global admin can access without explicit permission (cached)
        response1 = test_client.get(
            ENDPOINT_APPLICATION_DETAIL.format(tenant_id=tenant_id, application_id=app_id),
            headers=global_admin_headers
        )
        assert response1.status_code == status.HTTP_200_OK
        
        # Global admin can update (cached bypass)
        response2 = test_client.patch(
            ENDPOINT_APPLICATION_DETAIL.format(tenant_id=tenant_id, application_id=app_id),
            json={"name": "Updated by Global Admin"},
            headers=global_admin_headers
        )
        assert response2.status_code == status.HTTP_200_OK


class TestApplicationTagCacheInvalidation:
    """Test suite for cache invalidation when adding/removing tags from applications."""
    
    def test_adding_tags_invalidates_cache(self, test_client: TestClient, fake_redis_client: Any) -> None:
        """Test that adding tags to an application invalidates the application cache."""
        admin_token = test_client.create_test_user("app-tag-cache-1", "App Tag Cache 1")
        admin_headers = create_auth_headers(admin_token)
        tenant_id = create_tenant_for_user(test_client, admin_token)
        app_id = create_application(test_client, tenant_id, admin_headers, "Tagged App")
        
        # First read - cache the application (no tags)
        response1 = test_client.get(
            ENDPOINT_APPLICATION_DETAIL.format(tenant_id=tenant_id, application_id=app_id),
            headers=admin_headers
        )
        assert response1.status_code == status.HTTP_200_OK
        assert response1.json()["tags"] == []
        
        # Add tags to application
        test_client.put(
            f"/api/v1/tenants/{tenant_id}/applications/{app_id}/tags",
            json={"tags": ["production", "critical"]},
            headers=admin_headers
        )
        
        # Read application again - should see the tags (cache invalidated)
        response2 = test_client.get(
            ENDPOINT_APPLICATION_DETAIL.format(tenant_id=tenant_id, application_id=app_id),
            headers=admin_headers
        )
        assert response2.status_code == status.HTTP_200_OK
        assert len(response2.json()["tags"]) == 2
    
    def test_removing_tags_invalidates_cache(self, test_client: TestClient, fake_redis_client: Any) -> None:
        """Test that removing tags from an application invalidates the application cache."""
        admin_token = test_client.create_test_user("app-tag-cache-2", "App Tag Cache 2")
        admin_headers = create_auth_headers(admin_token)
        tenant_id = create_tenant_for_user(test_client, admin_token)
        app_id = create_application(test_client, tenant_id, admin_headers, "Tagged App 2")
        
        # Set initial tags
        test_client.put(
            f"/api/v1/tenants/{tenant_id}/applications/{app_id}/tags",
            json={"tags": ["tag1", "tag2"]},
            headers=admin_headers
        )
        
        # Read and cache
        response1 = test_client.get(
            ENDPOINT_APPLICATION_DETAIL.format(tenant_id=tenant_id, application_id=app_id),
            headers=admin_headers
        )
        assert len(response1.json()["tags"]) == 2
        
        # Remove tags
        test_client.delete(
            f"/api/v1/tenants/{tenant_id}/applications/{app_id}/tags",
            headers=admin_headers
        )
        
        # Read application again - should have no tags (cache invalidated)
        response2 = test_client.get(
            ENDPOINT_APPLICATION_DETAIL.format(tenant_id=tenant_id, application_id=app_id),
            headers=admin_headers
        )
        assert response2.status_code == status.HTTP_200_OK
        assert len(response2.json()["tags"]) == 0
    
    def test_replacing_tags_invalidates_cache(self, test_client: TestClient, fake_redis_client: Any) -> None:
        """Test that replacing tags on an application invalidates the application cache."""
        admin_token = test_client.create_test_user("app-tag-cache-3", "App Tag Cache 3")
        admin_headers = create_auth_headers(admin_token)
        tenant_id = create_tenant_for_user(test_client, admin_token)
        app_id = create_application(test_client, tenant_id, admin_headers, "Tagged App 3")
        
        # Set initial tags
        test_client.put(
            f"/api/v1/tenants/{tenant_id}/applications/{app_id}/tags",
            json={"tags": ["old-tag"]},
            headers=admin_headers
        )
        
        # Read and cache
        response1 = test_client.get(
            ENDPOINT_APPLICATION_DETAIL.format(tenant_id=tenant_id, application_id=app_id),
            headers=admin_headers
        )
        assert len(response1.json()["tags"]) == 1
        assert response1.json()["tags"][0]["name"] == "old-tag"
        
        # Replace with new tags
        test_client.put(
            f"/api/v1/tenants/{tenant_id}/applications/{app_id}/tags",
            json={"tags": ["new-tag-1", "new-tag-2"]},
            headers=admin_headers
        )
        
        # Read application again - should have new tags (cache invalidated)
        response2 = test_client.get(
            ENDPOINT_APPLICATION_DETAIL.format(tenant_id=tenant_id, application_id=app_id),
            headers=admin_headers
        )
        assert response2.status_code == status.HTTP_200_OK
        assert len(response2.json()["tags"]) == 2
        tag_names = [t["name"] for t in response2.json()["tags"]]
        assert "new-tag-1" in tag_names
        assert "new-tag-2" in tag_names

