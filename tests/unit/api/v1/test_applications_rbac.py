"""Tests for applications RBAC (Role-Based Access Control)."""
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
        headers=headers
    )
    assert response.status_code == status.HTTP_201_CREATED
    return response.json()["id"]


def create_application(test_client: TestClient, tenant_id: str, headers: dict, app_name: str = "Test App") -> str:
    """Helper function to create an application and return its ID."""
    response = test_client.post(
        ENDPOINT_APPLICATIONS.format(tenant_id=tenant_id),
        json={"name": app_name, "description": f"Application {app_name}", "type": "N8N"},
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


class TestApplicationRBAC:
    """Test suite for application role-based access control."""
    
    def test_creator_becomes_admin(self, test_client: TestClient) -> None:
        """Test that application creator automatically becomes ADMIN."""
        # Create user and tenant
        user_token = test_client.create_test_user("creator-user", "Creator User")
        headers = create_auth_headers(user_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, user_token)
        
        # Create application
        app_id = create_application(test_client, tenant_id, headers, "Creator Test App")
        
        # Verify creator has ADMIN role
        principals_response = test_client.get(
            ENDPOINT_PRINCIPAL_DETAIL.format(
                tenant_id=tenant_id,
                application_id=app_id,
                principal_id="creator-user"
            ),
            headers=headers
        )
        
        assert principals_response.status_code == status.HTTP_200_OK
        data = principals_response.json()
        assert data["principal_id"] == "creator-user"
        assert ROLE_ADMIN in data["roles"]
    
    def test_admin_can_update_application(self, test_client: TestClient) -> None:
        """Test that ADMIN can update application."""
        # Create user and tenant
        user_token = test_client.create_test_user("admin-user", "Admin User")
        headers = create_auth_headers(user_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, user_token)
        
        # Create application
        app_id = create_application(test_client, tenant_id, headers, "Original Name")
        
        # Update application
        update_response = test_client.patch(
            ENDPOINT_APPLICATION_DETAIL.format(tenant_id=tenant_id, application_id=app_id),
            json={"name": "Updated Name"},
            headers=headers
        )
        
        assert update_response.status_code == status.HTTP_200_OK
        assert update_response.json()["name"] == "Updated Name"
    
    def test_admin_can_delete_application(self, test_client: TestClient) -> None:
        """Test that ADMIN can delete application."""
        # Create user and tenant
        user_token = test_client.create_test_user("delete-admin", "Delete Admin")
        headers = create_auth_headers(user_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, user_token)
        
        # Create application
        app_id = create_application(test_client, tenant_id, headers, "To Delete")
        
        # Delete application
        delete_response = test_client.request(
            "DELETE",
            ENDPOINT_APPLICATION_DETAIL.format(tenant_id=tenant_id, application_id=app_id),
            headers=headers
        )
        
        assert delete_response.status_code == status.HTTP_204_NO_CONTENT
    
    def test_admin_can_manage_principals(self, test_client: TestClient) -> None:
        """Test that ADMIN can add/remove principals."""
        # Create admin user and tenant
        admin_token = test_client.create_test_user("principal-admin", "Principal Admin")
        admin_headers = create_auth_headers(admin_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, admin_token)
        
        # Create application
        app_id = create_application(test_client, tenant_id, admin_headers, "Principal Test")
        
        # Add a role to another user
        add_response = test_client.put(
            ENDPOINT_APPLICATION_PRINCIPALS.format(tenant_id=tenant_id, application_id=app_id),
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
            ENDPOINT_APPLICATION_PRINCIPALS.format(tenant_id=tenant_id, application_id=app_id),
            json={
                "principal_id": "other-user",
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_READ
            },
            headers=admin_headers
        )
        
        assert delete_response.status_code == status.HTTP_204_NO_CONTENT
    
    def test_non_member_cannot_access_application(self, test_client: TestClient) -> None:
        """Test that users without access cannot access application."""
        # User A creates tenant and application
        user_a_token = test_client.create_test_user("user-a", "User A")
        headers_a = create_auth_headers(user_a_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, user_a_token)
        app_id = create_application(test_client, tenant_id, headers_a, "Private App")
        
        # User B (not a member of tenant or application)
        user_b_token = test_client.create_test_user("user-b", "User B")
        headers_b = create_auth_headers(user_b_token, use_cache=False)
        
        # User B cannot view application
        get_response = test_client.get(
            ENDPOINT_APPLICATION_DETAIL.format(tenant_id=tenant_id, application_id=app_id),
            headers=headers_b
        )
        assert get_response.status_code == status.HTTP_403_FORBIDDEN
        
        # User B cannot update application
        update_response = test_client.patch(
            ENDPOINT_APPLICATION_DETAIL.format(tenant_id=tenant_id, application_id=app_id),
            json={"name": "Hacked"},
            headers=headers_b
        )
        assert update_response.status_code == status.HTTP_403_FORBIDDEN
        
        # User B cannot delete application
        delete_response = test_client.request(
            "DELETE",
            ENDPOINT_APPLICATION_DETAIL.format(tenant_id=tenant_id, application_id=app_id),
            headers=headers_b
        )
        assert delete_response.status_code == status.HTTP_403_FORBIDDEN
        
        # User B cannot manage principals
        principal_response = test_client.put(
            ENDPOINT_APPLICATION_PRINCIPALS.format(tenant_id=tenant_id, application_id=app_id),
            json={
                "principal_id": "some-user",
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_READ
            },
            headers=headers_b
        )
        assert principal_response.status_code == status.HTTP_403_FORBIDDEN
    
    def test_read_user_can_view_but_not_modify(self, test_client: TestClient) -> None:
        """Test that READ role can view but cannot modify application."""
        # Admin creates tenant and application
        admin_token = test_client.create_test_user("read-admin", "Read Admin")
        admin_headers = create_auth_headers(admin_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, admin_token)
        app_id = create_application(test_client, tenant_id, admin_headers, "Read Test")
        
        # Create reader user
        reader_token = test_client.create_test_user("reader-user", "Reader User")
        reader_headers = create_auth_headers(reader_token, use_cache=False)
        
        # Add reader to tenant first
        add_user_to_tenant(test_client, tenant_id, admin_headers, "reader-user", "READER")
        
        # Admin adds reader with READ role to application
        test_client.put(
            ENDPOINT_APPLICATION_PRINCIPALS.format(tenant_id=tenant_id, application_id=app_id),
            json={
                "principal_id": "reader-user",
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_READ
            },
            headers=admin_headers
        )
        
        # Reader CAN view application
        get_response = test_client.get(
            ENDPOINT_APPLICATION_DETAIL.format(tenant_id=tenant_id, application_id=app_id),
            headers=reader_headers
        )
        assert get_response.status_code == status.HTTP_200_OK
        assert get_response.json()["id"] == app_id
        
        # Reader CAN list principals
        principals_response = test_client.get(
            ENDPOINT_APPLICATION_PRINCIPALS.format(tenant_id=tenant_id, application_id=app_id),
            headers=reader_headers
        )
        assert principals_response.status_code == status.HTTP_200_OK
        
        # Reader CANNOT update application (needs WRITE or ADMIN)
        update_response = test_client.patch(
            ENDPOINT_APPLICATION_DETAIL.format(tenant_id=tenant_id, application_id=app_id),
            json={"name": "Hacked by Reader"},
            headers=reader_headers
        )
        assert update_response.status_code == status.HTTP_403_FORBIDDEN
        
        # Reader CANNOT delete application (needs ADMIN)
        delete_response = test_client.request(
            "DELETE",
            ENDPOINT_APPLICATION_DETAIL.format(tenant_id=tenant_id, application_id=app_id),
            headers=reader_headers
        )
        assert delete_response.status_code == status.HTTP_403_FORBIDDEN
        
        # Reader CANNOT manage principals (needs ADMIN)
        add_principal_response = test_client.put(
            ENDPOINT_APPLICATION_PRINCIPALS.format(tenant_id=tenant_id, application_id=app_id),
            json={
                "principal_id": "another-user",
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_READ
            },
            headers=reader_headers
        )
        assert add_principal_response.status_code == status.HTTP_403_FORBIDDEN
    
    def test_write_user_can_modify_but_not_delete_or_manage_principals(self, test_client: TestClient) -> None:
        """Test that WRITE role can view and modify but cannot delete or manage principals."""
        # Admin creates tenant and application
        admin_token = test_client.create_test_user("write-admin", "Write Admin")
        admin_headers = create_auth_headers(admin_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, admin_token)
        app_id = create_application(test_client, tenant_id, admin_headers, "Write Test")
        
        # Create writer user
        writer_token = test_client.create_test_user("writer-user", "Writer User")
        writer_headers = create_auth_headers(writer_token, use_cache=False)
        
        # Add writer to tenant first
        add_user_to_tenant(test_client, tenant_id, admin_headers, "writer-user", "READER")
        
        # Admin adds writer with WRITE role to application
        test_client.put(
            ENDPOINT_APPLICATION_PRINCIPALS.format(tenant_id=tenant_id, application_id=app_id),
            json={
                "principal_id": "writer-user",
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_WRITE
            },
            headers=admin_headers
        )
        
        # Writer CAN view application
        get_response = test_client.get(
            ENDPOINT_APPLICATION_DETAIL.format(tenant_id=tenant_id, application_id=app_id),
            headers=writer_headers
        )
        assert get_response.status_code == status.HTTP_200_OK
        
        # Writer CAN update application
        update_response = test_client.patch(
            ENDPOINT_APPLICATION_DETAIL.format(tenant_id=tenant_id, application_id=app_id),
            json={"name": "Updated by Writer"},
            headers=writer_headers
        )
        assert update_response.status_code == status.HTTP_200_OK
        assert update_response.json()["name"] == "Updated by Writer"
        
        # Writer CAN list principals
        principals_response = test_client.get(
            ENDPOINT_APPLICATION_PRINCIPALS.format(tenant_id=tenant_id, application_id=app_id),
            headers=writer_headers
        )
        assert principals_response.status_code == status.HTTP_200_OK
        
        # Writer CANNOT delete application (needs ADMIN)
        delete_response = test_client.request(
            "DELETE",
            ENDPOINT_APPLICATION_DETAIL.format(tenant_id=tenant_id, application_id=app_id),
            headers=writer_headers
        )
        assert delete_response.status_code == status.HTTP_403_FORBIDDEN
        
        # Writer CANNOT manage principals (needs ADMIN)
        add_principal_response = test_client.put(
            ENDPOINT_APPLICATION_PRINCIPALS.format(tenant_id=tenant_id, application_id=app_id),
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
        # Admin 1 creates tenant and application
        admin1_token = test_client.create_test_user("admin-1", "Admin One")
        admin1_headers = create_auth_headers(admin1_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, admin1_token)
        app_id = create_application(test_client, tenant_id, admin1_headers, "Multi Admin Test")
        
        # Admin 2 gets ADMIN permission
        admin2_token = test_client.create_test_user("admin-2", "Admin Two")
        admin2_headers = create_auth_headers(admin2_token, use_cache=False)
        
        # Add admin 2 to tenant first
        add_user_to_tenant(test_client, tenant_id, admin1_headers, "admin-2", "READER")
        
        # Admin 1 grants ADMIN to Admin 2
        test_client.put(
            ENDPOINT_APPLICATION_PRINCIPALS.format(tenant_id=tenant_id, application_id=app_id),
            json={
                "principal_id": "admin-2",
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_ADMIN
            },
            headers=admin1_headers
        )
        
        # Admin 2 can update application
        update_response = test_client.patch(
            ENDPOINT_APPLICATION_DETAIL.format(tenant_id=tenant_id, application_id=app_id),
            json={"name": "Updated by Admin 2"},
            headers=admin2_headers
        )
        assert update_response.status_code == status.HTTP_200_OK
        
        # Admin 2 can delete application
        delete_response = test_client.request(
            "DELETE",
            ENDPOINT_APPLICATION_DETAIL.format(tenant_id=tenant_id, application_id=app_id),
            headers=admin2_headers
        )
        assert delete_response.status_code == status.HTTP_204_NO_CONTENT
    
    def test_user_role_replacement(self, test_client: TestClient) -> None:
        """Test that setting a new role replaces the old one (single-role model)."""
        # Admin creates tenant and application
        admin_token = test_client.create_test_user("role-admin", "Role Admin")
        admin_headers = create_auth_headers(admin_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, admin_token)
        app_id = create_application(test_client, tenant_id, admin_headers, "Role Replace Test")
        
        # Grant READ role
        test_client.put(
            ENDPOINT_APPLICATION_PRINCIPALS.format(tenant_id=tenant_id, application_id=app_id),
            json={
                "principal_id": "test-user",
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_READ
            },
            headers=admin_headers
        )
        
        # Upgrade to WRITE role
        test_client.put(
            ENDPOINT_APPLICATION_PRINCIPALS.format(tenant_id=tenant_id, application_id=app_id),
            json={
                "principal_id": "test-user",
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_WRITE
            },
            headers=admin_headers
        )
        
        # Verify user has only WRITE role
        get_response = test_client.get(
            ENDPOINT_PRINCIPAL_DETAIL.format(
                tenant_id=tenant_id,
                application_id=app_id,
                principal_id="test-user"
            ),
            headers=admin_headers
        )
        
        assert get_response.status_code == status.HTTP_200_OK
        data = get_response.json()
        assert ROLE_WRITE in data["roles"]
    
    def test_removing_admin_role(self, test_client: TestClient, fake_redis_client: Any) -> None:
        """Test removing ADMIN role from a user."""
        # Admin creates tenant and application
        admin_token = test_client.create_test_user("remove-admin", "Remove Admin")
        admin_headers = create_auth_headers(admin_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, admin_token)
        app_id = create_application(test_client, tenant_id, admin_headers, "Remove Admin Test")
        
        # Create another user with ADMIN role
        user_token = test_client.create_test_user("temp-admin", "Temp Admin")
        user_headers = create_auth_headers(user_token, use_cache=False)
        
        # Add user to tenant first
        add_user_to_tenant(test_client, tenant_id, admin_headers, "temp-admin", "READER")
        
        # Grant ADMIN role
        test_client.put(
            ENDPOINT_APPLICATION_PRINCIPALS.format(tenant_id=tenant_id, application_id=app_id),
            json={
                "principal_id": "temp-admin",
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_ADMIN
            },
            headers=admin_headers
        )
        
        # User can update (has ADMIN)
        update_response1 = test_client.patch(
            ENDPOINT_APPLICATION_DETAIL.format(tenant_id=tenant_id, application_id=app_id),
            json={"name": "Updated by Temp Admin"},
            headers=user_headers
        )
        assert update_response1.status_code == status.HTTP_200_OK
        
        # Remove ADMIN role
        delete_response = test_client.request(
            "DELETE",
            ENDPOINT_APPLICATION_PRINCIPALS.format(tenant_id=tenant_id, application_id=app_id),
            json={
                "principal_id": "temp-admin",
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_ADMIN
            },
            headers=admin_headers
        )
        assert delete_response.status_code == status.HTTP_204_NO_CONTENT
        
        # User can no longer update (no access)
        update_response2 = test_client.patch(
            ENDPOINT_APPLICATION_DETAIL.format(tenant_id=tenant_id, application_id=app_id),
            json={"name": "Should Fail"},
            headers=user_headers
        )
        assert update_response2.status_code == status.HTTP_403_FORBIDDEN
    
    def test_tenant_global_admin_bypasses_application_permissions(self, test_client: TestClient) -> None:
        """Test that tenant GLOBAL_ADMIN can access all applications without explicit permissions."""
        # Admin creates tenant and application
        admin_token = test_client.create_test_user("tenant-admin", "Tenant Admin")
        admin_headers = create_auth_headers(admin_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, admin_token)
        app_id = create_application(test_client, tenant_id, admin_headers, "Tenant Admin Test")
        
        # Create another user with GLOBAL_ADMIN on tenant
        global_admin_token = test_client.create_test_user("global-admin", "Global Admin")
        global_admin_headers = create_auth_headers(global_admin_token, use_cache=False)
        
        # Add global admin to tenant with GLOBAL_ADMIN role
        add_user_to_tenant(test_client, tenant_id, admin_headers, "global-admin", "GLOBAL_ADMIN")
        
        # Global admin can view application without explicit permission
        get_response = test_client.get(
            ENDPOINT_APPLICATION_DETAIL.format(tenant_id=tenant_id, application_id=app_id),
            headers=global_admin_headers
        )
        assert get_response.status_code == status.HTTP_200_OK
        
        # Global admin can update application
        update_response = test_client.patch(
            ENDPOINT_APPLICATION_DETAIL.format(tenant_id=tenant_id, application_id=app_id),
            json={"name": "Updated by Global Admin"},
            headers=global_admin_headers
        )
        assert update_response.status_code == status.HTTP_200_OK
        
        # Global admin can delete application
        delete_response = test_client.request(
            "DELETE",
            ENDPOINT_APPLICATION_DETAIL.format(tenant_id=tenant_id, application_id=app_id),
            headers=global_admin_headers
        )
        assert delete_response.status_code == status.HTTP_204_NO_CONTENT
    
    def test_tenant_applications_admin_bypasses_application_permissions(self, test_client: TestClient) -> None:
        """Test that tenant APPLICATIONS_ADMIN can access all applications without explicit permissions."""
        # Admin creates tenant and application
        admin_token = test_client.create_test_user("tenant-admin-2", "Tenant Admin 2")
        admin_headers = create_auth_headers(admin_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, admin_token)
        app_id = create_application(test_client, tenant_id, admin_headers, "Apps Admin Test")
        
        # Create another user with APPLICATIONS_ADMIN on tenant
        apps_admin_token = test_client.create_test_user("apps-admin", "Apps Admin")
        apps_admin_headers = create_auth_headers(apps_admin_token, use_cache=False)
        
        # Add apps admin to tenant with APPLICATIONS_ADMIN role
        add_user_to_tenant(test_client, tenant_id, admin_headers, "apps-admin", "APPLICATIONS_ADMIN")
        
        # Apps admin can view application without explicit permission
        get_response = test_client.get(
            ENDPOINT_APPLICATION_DETAIL.format(tenant_id=tenant_id, application_id=app_id),
            headers=apps_admin_headers
        )
        assert get_response.status_code == status.HTTP_200_OK
        
        # Apps admin can update application
        update_response = test_client.patch(
            ENDPOINT_APPLICATION_DETAIL.format(tenant_id=tenant_id, application_id=app_id),
            json={"name": "Updated by Apps Admin"},
            headers=apps_admin_headers
        )
        assert update_response.status_code == status.HTTP_200_OK
        
        # Apps admin can manage principals
        principal_response = test_client.put(
            ENDPOINT_APPLICATION_PRINCIPALS.format(tenant_id=tenant_id, application_id=app_id),
            json={
                "principal_id": "some-user",
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_READ
            },
            headers=apps_admin_headers
        )
        assert principal_response.status_code == status.HTTP_200_OK
