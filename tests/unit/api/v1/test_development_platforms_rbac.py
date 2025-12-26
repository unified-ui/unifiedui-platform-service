"""Tests for development platforms RBAC (Role-Based Access Control)."""
from typing import Any
from fastapi import status
from starlette.testclient import TestClient

from unifiedui.core.database.enums import PermissionActionEnum, PrincipalTypeEnum
from tests.conftest import create_auth_headers


# API Endpoints
ENDPOINT_TENANTS = "/api/v1/tenants"
ENDPOINT_DEVELOPMENT_PLATFORMS = "/api/v1/tenants/{tenant_id}/development-platforms"
ENDPOINT_DEVELOPMENT_PLATFORM_DETAIL = "/api/v1/tenants/{tenant_id}/development-platforms/{development_platform_id}"
ENDPOINT_DEVELOPMENT_PLATFORM_PRINCIPALS = "/api/v1/tenants/{tenant_id}/development-platforms/{development_platform_id}/principals"
ENDPOINT_PRINCIPAL_DETAIL = "/api/v1/tenants/{tenant_id}/development-platforms/{development_platform_id}/principals/{principal_id}"

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
        headers=headers
    )
    assert response.status_code == status.HTTP_201_CREATED
    return response.json()["id"]


def create_development_platform(test_client: TestClient, tenant_id: str, headers: dict, name: str = "Test Platform") -> str:
    """Helper function to create a development platform and return its ID."""
    response = test_client.post(
        ENDPOINT_DEVELOPMENT_PLATFORMS.format(tenant_id=tenant_id),
        json={
            "name": name,
            "description": f"Dev Platform {name}",
            "type": "IDE",
            "iframe_url": "https://example.com/ide"
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


class TestDevelopmentPlatformRBAC:
    """Test suite for development platform role-based access control."""
    
    def test_creator_becomes_admin(self, test_client: TestClient) -> None:
        """Test that development platform creator automatically becomes ADMIN."""
        user_token = test_client.create_test_user("dp-creator", "DP Creator")
        headers = create_auth_headers(user_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, user_token)
        
        platform_id = create_development_platform(test_client, tenant_id, headers, "Creator Test")
        
        # Verify creator has ADMIN role
        principals_response = test_client.get(
            ENDPOINT_PRINCIPAL_DETAIL.format(
                tenant_id=tenant_id,
                development_platform_id=platform_id,
                principal_id="dp-creator"
            ),
            headers=headers
        )
        
        assert principals_response.status_code == status.HTTP_200_OK
        data = principals_response.json()
        assert ROLE_ADMIN in data["roles"]
    
    def test_admin_can_update_development_platform(self, test_client: TestClient) -> None:
        """Test that ADMIN can update development platform."""
        user_token = test_client.create_test_user("dp-admin", "DP Admin")
        headers = create_auth_headers(user_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, user_token)
        
        platform_id = create_development_platform(test_client, tenant_id, headers, "Original Name")
        
        update_response = test_client.patch(
            ENDPOINT_DEVELOPMENT_PLATFORM_DETAIL.format(tenant_id=tenant_id, development_platform_id=platform_id),
            json={"name": "Updated Name"},
            headers=headers
        )
        
        assert update_response.status_code == status.HTTP_200_OK
        assert update_response.json()["name"] == "Updated Name"
    
    def test_admin_can_delete_development_platform(self, test_client: TestClient) -> None:
        """Test that ADMIN can delete development platform."""
        user_token = test_client.create_test_user("dp-delete-admin", "DP Delete Admin")
        headers = create_auth_headers(user_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, user_token)
        
        platform_id = create_development_platform(test_client, tenant_id, headers, "To Delete")
        
        delete_response = test_client.request(
            "DELETE",
            ENDPOINT_DEVELOPMENT_PLATFORM_DETAIL.format(tenant_id=tenant_id, development_platform_id=platform_id),
            headers=headers
        )
        
        assert delete_response.status_code == status.HTTP_204_NO_CONTENT
    
    def test_admin_can_manage_principals(self, test_client: TestClient) -> None:
        """Test that ADMIN can add/remove principals."""
        admin_token = test_client.create_test_user("dp-principal-admin", "DP Principal Admin")
        admin_headers = create_auth_headers(admin_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, admin_token)
        
        platform_id = create_development_platform(test_client, tenant_id, admin_headers, "Principal Test")
        
        # Add a role to another user
        add_response = test_client.put(
            ENDPOINT_DEVELOPMENT_PLATFORM_PRINCIPALS.format(tenant_id=tenant_id, development_platform_id=platform_id),
            json={
                "principal_id": "other-user",
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_READ
            },
            headers=admin_headers
        )
        
        assert add_response.status_code == status.HTTP_200_OK
        assert add_response.json()["role"] == ROLE_READ
        
        # Remove the role
        delete_response = test_client.request(
            "DELETE",
            ENDPOINT_DEVELOPMENT_PLATFORM_PRINCIPALS.format(tenant_id=tenant_id, development_platform_id=platform_id),
            json={
                "principal_id": "other-user",
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_READ
            },
            headers=admin_headers
        )
        
        assert delete_response.status_code == status.HTTP_204_NO_CONTENT
    
    def test_non_member_cannot_access_development_platform(self, test_client: TestClient) -> None:
        """Test that users without access cannot access development platform."""
        user_a_token = test_client.create_test_user("dp-user-a", "DP User A")
        headers_a = create_auth_headers(user_a_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, user_a_token)
        platform_id = create_development_platform(test_client, tenant_id, headers_a, "Private Platform")
        
        user_b_token = test_client.create_test_user("dp-user-b", "DP User B")
        headers_b = create_auth_headers(user_b_token, use_cache=False)
        
        # User B cannot view
        get_response = test_client.get(
            ENDPOINT_DEVELOPMENT_PLATFORM_DETAIL.format(tenant_id=tenant_id, development_platform_id=platform_id),
            headers=headers_b
        )
        assert get_response.status_code == status.HTTP_403_FORBIDDEN
        
        # User B cannot update
        update_response = test_client.patch(
            ENDPOINT_DEVELOPMENT_PLATFORM_DETAIL.format(tenant_id=tenant_id, development_platform_id=platform_id),
            json={"name": "Hacked"},
            headers=headers_b
        )
        assert update_response.status_code == status.HTTP_403_FORBIDDEN
        
        # User B cannot delete
        delete_response = test_client.request(
            "DELETE",
            ENDPOINT_DEVELOPMENT_PLATFORM_DETAIL.format(tenant_id=tenant_id, development_platform_id=platform_id),
            headers=headers_b
        )
        assert delete_response.status_code == status.HTTP_403_FORBIDDEN
    
    def test_read_user_can_view_but_not_modify(self, test_client: TestClient) -> None:
        """Test that READ role can view but cannot modify development platform."""
        admin_token = test_client.create_test_user("dp-read-admin", "DP Read Admin")
        admin_headers = create_auth_headers(admin_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, admin_token)
        platform_id = create_development_platform(test_client, tenant_id, admin_headers, "Read Test")
        
        reader_token = test_client.create_test_user("dp-reader", "DP Reader")
        reader_headers = create_auth_headers(reader_token, use_cache=False)
        
        add_user_to_tenant(test_client, tenant_id, admin_headers, "dp-reader", "READER")
        
        test_client.put(
            ENDPOINT_DEVELOPMENT_PLATFORM_PRINCIPALS.format(tenant_id=tenant_id, development_platform_id=platform_id),
            json={
                "principal_id": "dp-reader",
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_READ
            },
            headers=admin_headers
        )
        
        # Reader CAN view
        get_response = test_client.get(
            ENDPOINT_DEVELOPMENT_PLATFORM_DETAIL.format(tenant_id=tenant_id, development_platform_id=platform_id),
            headers=reader_headers
        )
        assert get_response.status_code == status.HTTP_200_OK
        
        # Reader CAN list principals
        principals_response = test_client.get(
            ENDPOINT_DEVELOPMENT_PLATFORM_PRINCIPALS.format(tenant_id=tenant_id, development_platform_id=platform_id),
            headers=reader_headers
        )
        assert principals_response.status_code == status.HTTP_200_OK
        
        # Reader CANNOT update
        update_response = test_client.patch(
            ENDPOINT_DEVELOPMENT_PLATFORM_DETAIL.format(tenant_id=tenant_id, development_platform_id=platform_id),
            json={"name": "Hacked by Reader"},
            headers=reader_headers
        )
        assert update_response.status_code == status.HTTP_403_FORBIDDEN
        
        # Reader CANNOT delete
        delete_response = test_client.request(
            "DELETE",
            ENDPOINT_DEVELOPMENT_PLATFORM_DETAIL.format(tenant_id=tenant_id, development_platform_id=platform_id),
            headers=reader_headers
        )
        assert delete_response.status_code == status.HTTP_403_FORBIDDEN
    
    def test_write_user_can_modify_but_not_delete_or_manage_principals(self, test_client: TestClient) -> None:
        """Test that WRITE role can modify but cannot delete or manage principals."""
        admin_token = test_client.create_test_user("dp-write-admin", "DP Write Admin")
        admin_headers = create_auth_headers(admin_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, admin_token)
        platform_id = create_development_platform(test_client, tenant_id, admin_headers, "Write Test")
        
        writer_token = test_client.create_test_user("dp-writer", "DP Writer")
        writer_headers = create_auth_headers(writer_token, use_cache=False)
        
        add_user_to_tenant(test_client, tenant_id, admin_headers, "dp-writer", "READER")
        
        test_client.put(
            ENDPOINT_DEVELOPMENT_PLATFORM_PRINCIPALS.format(tenant_id=tenant_id, development_platform_id=platform_id),
            json={
                "principal_id": "dp-writer",
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_WRITE
            },
            headers=admin_headers
        )
        
        # Writer CAN view
        get_response = test_client.get(
            ENDPOINT_DEVELOPMENT_PLATFORM_DETAIL.format(tenant_id=tenant_id, development_platform_id=platform_id),
            headers=writer_headers
        )
        assert get_response.status_code == status.HTTP_200_OK
        
        # Writer CAN update
        update_response = test_client.patch(
            ENDPOINT_DEVELOPMENT_PLATFORM_DETAIL.format(tenant_id=tenant_id, development_platform_id=platform_id),
            json={"name": "Updated by Writer"},
            headers=writer_headers
        )
        assert update_response.status_code == status.HTTP_200_OK
        
        # Writer CANNOT delete
        delete_response = test_client.request(
            "DELETE",
            ENDPOINT_DEVELOPMENT_PLATFORM_DETAIL.format(tenant_id=tenant_id, development_platform_id=platform_id),
            headers=writer_headers
        )
        assert delete_response.status_code == status.HTTP_403_FORBIDDEN
        
        # Writer CANNOT manage principals
        add_principal_response = test_client.put(
            ENDPOINT_DEVELOPMENT_PLATFORM_PRINCIPALS.format(tenant_id=tenant_id, development_platform_id=platform_id),
            json={
                "principal_id": "another-user",
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_READ
            },
            headers=writer_headers
        )
        assert add_principal_response.status_code == status.HTTP_403_FORBIDDEN
    
    def test_multiple_admins(self, test_client: TestClient) -> None:
        """Test that multiple users can have ADMIN role."""
        admin1_token = test_client.create_test_user("dp-admin-1", "DP Admin 1")
        admin1_headers = create_auth_headers(admin1_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, admin1_token)
        platform_id = create_development_platform(test_client, tenant_id, admin1_headers, "Multi Admin Test")
        
        admin2_token = test_client.create_test_user("dp-admin-2", "DP Admin 2")
        admin2_headers = create_auth_headers(admin2_token, use_cache=False)
        
        add_user_to_tenant(test_client, tenant_id, admin1_headers, "dp-admin-2", "READER")
        
        test_client.put(
            ENDPOINT_DEVELOPMENT_PLATFORM_PRINCIPALS.format(tenant_id=tenant_id, development_platform_id=platform_id),
            json={
                "principal_id": "dp-admin-2",
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_ADMIN
            },
            headers=admin1_headers
        )
        
        # Admin 2 can update
        update_response = test_client.patch(
            ENDPOINT_DEVELOPMENT_PLATFORM_DETAIL.format(tenant_id=tenant_id, development_platform_id=platform_id),
            json={"name": "Updated by Admin 2"},
            headers=admin2_headers
        )
        assert update_response.status_code == status.HTTP_200_OK
        
        # Admin 2 can delete
        delete_response = test_client.request(
            "DELETE",
            ENDPOINT_DEVELOPMENT_PLATFORM_DETAIL.format(tenant_id=tenant_id, development_platform_id=platform_id),
            headers=admin2_headers
        )
        assert delete_response.status_code == status.HTTP_204_NO_CONTENT
    
    def test_tenant_global_admin_bypasses_development_platform_permissions(self, test_client: TestClient) -> None:
        """Test that tenant GLOBAL_ADMIN can access all development platforms."""
        admin_token = test_client.create_test_user("dp-tenant-admin", "DP Tenant Admin")
        admin_headers = create_auth_headers(admin_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, admin_token)
        platform_id = create_development_platform(test_client, tenant_id, admin_headers, "Global Admin Test")
        
        global_admin_token = test_client.create_test_user("dp-global-admin", "DP Global Admin")
        global_admin_headers = create_auth_headers(global_admin_token, use_cache=False)
        
        add_user_to_tenant(test_client, tenant_id, admin_headers, "dp-global-admin", "GLOBAL_ADMIN")
        
        # Global admin can view
        get_response = test_client.get(
            ENDPOINT_DEVELOPMENT_PLATFORM_DETAIL.format(tenant_id=tenant_id, development_platform_id=platform_id),
            headers=global_admin_headers
        )
        assert get_response.status_code == status.HTTP_200_OK
        
        # Global admin can update
        update_response = test_client.patch(
            ENDPOINT_DEVELOPMENT_PLATFORM_DETAIL.format(tenant_id=tenant_id, development_platform_id=platform_id),
            json={"name": "Updated by Global Admin"},
            headers=global_admin_headers
        )
        assert update_response.status_code == status.HTTP_200_OK
        
        # Global admin can delete
        delete_response = test_client.request(
            "DELETE",
            ENDPOINT_DEVELOPMENT_PLATFORM_DETAIL.format(tenant_id=tenant_id, development_platform_id=platform_id),
            headers=global_admin_headers
        )
        assert delete_response.status_code == status.HTTP_204_NO_CONTENT
    
    def test_tenant_development_platforms_admin_bypasses_permissions(self, test_client: TestClient) -> None:
        """Test that tenant DEVELOPMENT_PLATFORMS_ADMIN can access all development platforms."""
        admin_token = test_client.create_test_user("dp-tenant-admin-2", "DP Tenant Admin 2")
        admin_headers = create_auth_headers(admin_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, admin_token)
        platform_id = create_development_platform(test_client, tenant_id, admin_headers, "DP Admin Test")
        
        dp_admin_token = test_client.create_test_user("dp-platforms-admin", "DP Platforms Admin")
        dp_admin_headers = create_auth_headers(dp_admin_token, use_cache=False)
        
        add_user_to_tenant(test_client, tenant_id, admin_headers, "dp-platforms-admin", "DEVELOPMENT_PLATFORMS_ADMIN")
        
        # Dev platforms admin can view
        get_response = test_client.get(
            ENDPOINT_DEVELOPMENT_PLATFORM_DETAIL.format(tenant_id=tenant_id, development_platform_id=platform_id),
            headers=dp_admin_headers
        )
        assert get_response.status_code == status.HTTP_200_OK
        
        # Dev platforms admin can update
        update_response = test_client.patch(
            ENDPOINT_DEVELOPMENT_PLATFORM_DETAIL.format(tenant_id=tenant_id, development_platform_id=platform_id),
            json={"name": "Updated by DP Admin"},
            headers=dp_admin_headers
        )
        assert update_response.status_code == status.HTTP_200_OK
    
    def test_user_role_replacement(self, test_client: TestClient) -> None:
        """Test that setting a new role replaces the old one."""
        admin_token = test_client.create_test_user("dp-role-admin", "DP Role Admin")
        admin_headers = create_auth_headers(admin_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, admin_token)
        platform_id = create_development_platform(test_client, tenant_id, admin_headers, "Role Replace Test")
        
        # Grant READ role
        test_client.put(
            ENDPOINT_DEVELOPMENT_PLATFORM_PRINCIPALS.format(tenant_id=tenant_id, development_platform_id=platform_id),
            json={
                "principal_id": "test-user",
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_READ
            },
            headers=admin_headers
        )
        
        # Upgrade to WRITE role
        test_client.put(
            ENDPOINT_DEVELOPMENT_PLATFORM_PRINCIPALS.format(tenant_id=tenant_id, development_platform_id=platform_id),
            json={
                "principal_id": "test-user",
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_WRITE
            },
            headers=admin_headers
        )
        
        # Verify user has WRITE role
        get_response = test_client.get(
            ENDPOINT_PRINCIPAL_DETAIL.format(
                tenant_id=tenant_id,
                development_platform_id=platform_id,
                principal_id="test-user"
            ),
            headers=admin_headers
        )
        
        assert get_response.status_code == status.HTTP_200_OK
        assert ROLE_WRITE in get_response.json()["roles"]
    
    def test_removing_admin_role(self, test_client: TestClient, fake_redis_client: Any) -> None:
        """Test removing ADMIN role from a user."""
        admin_token = test_client.create_test_user("dp-remove-admin", "DP Remove Admin")
        admin_headers = create_auth_headers(admin_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, admin_token)
        platform_id = create_development_platform(test_client, tenant_id, admin_headers, "Remove Admin Test")
        
        user_token = test_client.create_test_user("dp-temp-admin", "DP Temp Admin")
        user_headers = create_auth_headers(user_token, use_cache=False)
        
        add_user_to_tenant(test_client, tenant_id, admin_headers, "dp-temp-admin", "READER")
        
        # Grant ADMIN role
        test_client.put(
            ENDPOINT_DEVELOPMENT_PLATFORM_PRINCIPALS.format(tenant_id=tenant_id, development_platform_id=platform_id),
            json={
                "principal_id": "dp-temp-admin",
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_ADMIN
            },
            headers=admin_headers
        )
        
        # User can update (has ADMIN)
        update_response1 = test_client.patch(
            ENDPOINT_DEVELOPMENT_PLATFORM_DETAIL.format(tenant_id=tenant_id, development_platform_id=platform_id),
            json={"name": "Updated by Temp Admin"},
            headers=user_headers
        )
        assert update_response1.status_code == status.HTTP_200_OK
        
        # Remove ADMIN role
        delete_response = test_client.request(
            "DELETE",
            ENDPOINT_DEVELOPMENT_PLATFORM_PRINCIPALS.format(tenant_id=tenant_id, development_platform_id=platform_id),
            json={
                "principal_id": "dp-temp-admin",
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_ADMIN
            },
            headers=admin_headers
        )
        assert delete_response.status_code == status.HTTP_204_NO_CONTENT
        
        # User can no longer update
        update_response2 = test_client.patch(
            ENDPOINT_DEVELOPMENT_PLATFORM_DETAIL.format(tenant_id=tenant_id, development_platform_id=platform_id),
            json={"name": "Should Fail"},
            headers=user_headers
        )
        assert update_response2.status_code == status.HTTP_403_FORBIDDEN
