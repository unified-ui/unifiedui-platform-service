"""Tests for credentials RBAC (Role-Based Access Control)."""
from typing import Any
from fastapi import status
from starlette.testclient import TestClient

from unifiedui.core.database.enums import PermissionActionEnum, PrincipalTypeEnum
from tests.conftest import create_auth_headers


# API Endpoints
ENDPOINT_TENANTS = "/api/v1/platform-service/tenants"
ENDPOINT_CREDENTIALS = "/api/v1/platform-service/tenants/{tenant_id}/credentials"
ENDPOINT_CREDENTIAL_DETAIL = "/api/v1/platform-service/tenants/{tenant_id}/credentials/{credential_id}"
ENDPOINT_CREDENTIAL_PRINCIPALS = "/api/v1/platform-service/tenants/{tenant_id}/credentials/{credential_id}/principals"
ENDPOINT_PRINCIPAL_DETAIL = "/api/v1/platform-service/tenants/{tenant_id}/credentials/{credential_id}/principals/{principal_id}"

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
        f"/api/v1/platform-service/tenants/{tenant_id}/principals",
        json={
            "principal_id": user_id,
            "principal_type": PRINCIPAL_TYPE_USER,
            "role": role  # Tenant API expects single role string
        },
        headers=admin_headers
    )
    assert response.status_code == status.HTTP_200_OK


class TestCredentialRBAC:
    """Test suite for credential role-based access control."""
    
    def test_creator_becomes_admin(self, test_client: TestClient) -> None:
        """Test that credential creator automatically becomes ADMIN."""
        # Create user and tenant
        user_token = test_client.create_test_user("creator-user", "Creator User")
        headers = create_auth_headers(user_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, user_token)
        
        # Create credential
        credential_id = create_credential(test_client, tenant_id, headers, "Creator Test Credential")
        
        # Verify creator has ADMIN role
        principals_response = test_client.get(
            ENDPOINT_PRINCIPAL_DETAIL.format(
                tenant_id=tenant_id,
                credential_id=credential_id,
                principal_id="creator-user"
            ),
            headers=headers
        )
        
        assert principals_response.status_code == status.HTTP_200_OK
        data = principals_response.json()
        assert data["principal_id"] == "creator-user"
        assert ROLE_ADMIN in data["roles"]
    
    def test_admin_can_update_credential(self, test_client: TestClient) -> None:
        """Test that ADMIN can update credential."""
        # Create user and tenant
        user_token = test_client.create_test_user("admin-user", "Admin User")
        headers = create_auth_headers(user_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, user_token)
        
        # Create credential
        credential_id = create_credential(test_client, tenant_id, headers, "Original Name")
        
        # Update credential
        update_response = test_client.patch(
            ENDPOINT_CREDENTIAL_DETAIL.format(tenant_id=tenant_id, credential_id=credential_id),
            json={"name": "Updated Name"},
            headers=headers
        )
        
        assert update_response.status_code == status.HTTP_200_OK
        assert update_response.json()["name"] == "Updated Name"
    
    def test_admin_can_delete_credential(self, test_client: TestClient) -> None:
        """Test that ADMIN can delete credential."""
        # Create user and tenant
        user_token = test_client.create_test_user("delete-admin", "Delete Admin")
        headers = create_auth_headers(user_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, user_token)
        
        # Create credential
        credential_id = create_credential(test_client, tenant_id, headers, "To Delete")
        
        # Delete credential
        delete_response = test_client.request(
            "DELETE",
            ENDPOINT_CREDENTIAL_DETAIL.format(tenant_id=tenant_id, credential_id=credential_id),
            headers=headers
        )
        
        assert delete_response.status_code == status.HTTP_204_NO_CONTENT
    
    def test_admin_can_manage_principals(self, test_client: TestClient) -> None:
        """Test that ADMIN can add/remove principals."""
        # Create admin user and tenant
        admin_token = test_client.create_test_user("principal-admin", "Principal Admin")
        admin_headers = create_auth_headers(admin_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, admin_token)
        
        # Create credential
        credential_id = create_credential(test_client, tenant_id, admin_headers, "Principal Test")
        
        # Add a role to another user
        add_response = test_client.put(
            ENDPOINT_CREDENTIAL_PRINCIPALS.format(tenant_id=tenant_id, credential_id=credential_id),
            json={
                "principal_id": "other-user",
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_READ
            },
            headers=admin_headers
        )
        
        assert add_response.status_code == status.HTTP_200_OK
        assert ROLE_READ in add_response.json()["roles"]
        
        # Remove the role
        delete_response = test_client.request(
            "DELETE",
            ENDPOINT_CREDENTIAL_PRINCIPALS.format(tenant_id=tenant_id, credential_id=credential_id),
            json={
                "principal_id": "other-user",
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_READ
            },
            headers=admin_headers
        )
        
        assert delete_response.status_code == status.HTTP_204_NO_CONTENT
    
    def test_non_member_cannot_access_credential(self, test_client: TestClient) -> None:
        """Test that users without access cannot view or modify credential."""
        # User A creates tenant and credential
        user_a_token = test_client.create_test_user("user-a", "User A")
        headers_a = create_auth_headers(user_a_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, user_a_token)
        credential_id = create_credential(test_client, tenant_id, headers_a, "Private Credential")
        
        # User B (not member of tenant)
        user_b_token = test_client.create_test_user("user-b", "User B")
        headers_b = create_auth_headers(user_b_token, use_cache=False)
        
        # User B cannot view credential
        get_response = test_client.get(
            ENDPOINT_CREDENTIAL_DETAIL.format(tenant_id=tenant_id, credential_id=credential_id),
            headers=headers_b
        )
        assert get_response.status_code == status.HTTP_403_FORBIDDEN
        
        # User B cannot update credential
        update_response = test_client.patch(
            ENDPOINT_CREDENTIAL_DETAIL.format(tenant_id=tenant_id, credential_id=credential_id),
            json={"name": "Hacked"},
            headers=headers_b
        )
        assert update_response.status_code == status.HTTP_403_FORBIDDEN
        
        # User B cannot delete credential
        delete_response = test_client.request(
            "DELETE",
            ENDPOINT_CREDENTIAL_DETAIL.format(tenant_id=tenant_id, credential_id=credential_id),
            headers=headers_b
        )
        assert delete_response.status_code == status.HTTP_403_FORBIDDEN
        
        # User B cannot manage principals
        principal_response = test_client.put(
            ENDPOINT_CREDENTIAL_PRINCIPALS.format(tenant_id=tenant_id, credential_id=credential_id),
            json={
                "principal_id": "some-user",
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_READ
            },
            headers=headers_b
        )
        assert principal_response.status_code == status.HTTP_403_FORBIDDEN
    
    def test_read_user_can_view_but_not_modify(self, test_client: TestClient) -> None:
        """Test that READ role can view but cannot modify credential."""
        # Admin creates tenant and credential
        admin_token = test_client.create_test_user("read-admin", "Read Admin")
        admin_headers = create_auth_headers(admin_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, admin_token)
        credential_id = create_credential(test_client, tenant_id, admin_headers, "Read Test")
        
        # Create reader user
        reader_token = test_client.create_test_user("reader-user", "Reader User")
        reader_headers = create_auth_headers(reader_token, use_cache=False)
        
        # Add reader to tenant first
        add_user_to_tenant(test_client, tenant_id, admin_headers, "reader-user", "READER")
        
        # Admin adds reader with READ role to credential
        test_client.put(
            ENDPOINT_CREDENTIAL_PRINCIPALS.format(tenant_id=tenant_id, credential_id=credential_id),
            json={
                "principal_id": "reader-user",
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_READ
            },
            headers=admin_headers
        )
        
        # Reader CAN view credential
        get_response = test_client.get(
            ENDPOINT_CREDENTIAL_DETAIL.format(tenant_id=tenant_id, credential_id=credential_id),
            headers=reader_headers
        )
        assert get_response.status_code == status.HTTP_200_OK
        assert get_response.json()["id"] == credential_id
        
        # Reader CAN list principals
        principals_response = test_client.get(
            ENDPOINT_CREDENTIAL_PRINCIPALS.format(tenant_id=tenant_id, credential_id=credential_id),
            headers=reader_headers
        )
        assert principals_response.status_code == status.HTTP_200_OK
        
        # Reader CANNOT update credential (needs WRITE or ADMIN)
        update_response = test_client.patch(
            ENDPOINT_CREDENTIAL_DETAIL.format(tenant_id=tenant_id, credential_id=credential_id),
            json={"name": "Hacked by Reader"},
            headers=reader_headers
        )
        assert update_response.status_code == status.HTTP_403_FORBIDDEN
        
        # Reader CANNOT delete credential (needs ADMIN)
        delete_response = test_client.request(
            "DELETE",
            ENDPOINT_CREDENTIAL_DETAIL.format(tenant_id=tenant_id, credential_id=credential_id),
            headers=reader_headers
        )
        assert delete_response.status_code == status.HTTP_403_FORBIDDEN
        
        # Reader CANNOT manage principals (needs ADMIN)
        add_principal_response = test_client.put(
            ENDPOINT_CREDENTIAL_PRINCIPALS.format(tenant_id=tenant_id, credential_id=credential_id),
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
        # Admin creates tenant and credential
        admin_token = test_client.create_test_user("write-admin", "Write Admin")
        admin_headers = create_auth_headers(admin_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, admin_token)
        credential_id = create_credential(test_client, tenant_id, admin_headers, "Write Test")
        
        # Create writer user
        writer_token = test_client.create_test_user("writer-user", "Writer User")
        writer_headers = create_auth_headers(writer_token, use_cache=False)
        
        # Add writer to tenant first
        add_user_to_tenant(test_client, tenant_id, admin_headers, "writer-user", "READER")
        
        # Admin adds writer with WRITE role to credential
        test_client.put(
            ENDPOINT_CREDENTIAL_PRINCIPALS.format(tenant_id=tenant_id, credential_id=credential_id),
            json={
                "principal_id": "writer-user",
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_WRITE
            },
            headers=admin_headers
        )
        
        # Writer CAN view credential
        get_response = test_client.get(
            ENDPOINT_CREDENTIAL_DETAIL.format(tenant_id=tenant_id, credential_id=credential_id),
            headers=writer_headers
        )
        assert get_response.status_code == status.HTTP_200_OK
        
        # Writer CAN update credential
        update_response = test_client.patch(
            ENDPOINT_CREDENTIAL_DETAIL.format(tenant_id=tenant_id, credential_id=credential_id),
            json={"name": "Updated by Writer"},
            headers=writer_headers
        )
        assert update_response.status_code == status.HTTP_200_OK
        assert update_response.json()["name"] == "Updated by Writer"
        
        # Writer CANNOT delete credential (needs ADMIN)
        delete_response = test_client.request(
            "DELETE",
            ENDPOINT_CREDENTIAL_DETAIL.format(tenant_id=tenant_id, credential_id=credential_id),
            headers=writer_headers
        )
        assert delete_response.status_code == status.HTTP_403_FORBIDDEN
        
        # Writer CANNOT manage principals (needs ADMIN)
        add_principal_response = test_client.put(
            ENDPOINT_CREDENTIAL_PRINCIPALS.format(tenant_id=tenant_id, credential_id=credential_id),
            json={
                "principal_id": "another-user",
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_READ
            },
            headers=writer_headers
        )
        assert add_principal_response.status_code == status.HTTP_403_FORBIDDEN
        
        # Writer CANNOT remove principals (needs ADMIN)
        remove_principal_response = test_client.request(
            "DELETE",
            ENDPOINT_CREDENTIAL_PRINCIPALS.format(tenant_id=tenant_id, credential_id=credential_id),
            json={
                "principal_id": "writer-user",
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_WRITE
            },
            headers=writer_headers
        )
        assert remove_principal_response.status_code == status.HTTP_403_FORBIDDEN
    
    def test_multiple_admins(self, test_client: TestClient) -> None:
        """Test that multiple users can have ADMIN role."""
        # Admin 1 creates tenant and credential
        admin1_token = test_client.create_test_user("admin-1", "Admin One")
        admin1_headers = create_auth_headers(admin1_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, admin1_token)
        credential_id = create_credential(test_client, tenant_id, admin1_headers, "Multi Admin Test")
        
        # Admin 2
        admin2_token = test_client.create_test_user("admin-2", "Admin Two")
        admin2_headers = create_auth_headers(admin2_token, use_cache=False)
        
        # Add admin2 to tenant
        add_user_to_tenant(test_client, tenant_id, admin1_headers, "admin-2", "READER")
        
        # Admin 1 adds Admin 2 with ADMIN role
        test_client.put(
            ENDPOINT_CREDENTIAL_PRINCIPALS.format(tenant_id=tenant_id, credential_id=credential_id),
            json={
                "principal_id": "admin-2",
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_ADMIN
            },
            headers=admin1_headers
        )
        
        # Admin 2 CAN update credential
        update_response = test_client.patch(
            ENDPOINT_CREDENTIAL_DETAIL.format(tenant_id=tenant_id, credential_id=credential_id),
            json={"name": "Updated by Admin 2"},
            headers=admin2_headers
        )
        assert update_response.status_code == status.HTTP_200_OK
        
        # Admin 2 CAN delete credential
        delete_response = test_client.request(
            "DELETE",
            ENDPOINT_CREDENTIAL_DETAIL.format(tenant_id=tenant_id, credential_id=credential_id),
            headers=admin2_headers
        )
        assert delete_response.status_code == status.HTTP_204_NO_CONTENT
    
    def test_user_role_replacement(self, test_client: TestClient) -> None:
        """Test that setting a new role replaces the old one (single role model)."""
        # Admin creates tenant and credential
        admin_token = test_client.create_test_user("role-admin", "Role Admin")
        admin_headers = create_auth_headers(admin_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, admin_token)
        credential_id = create_credential(test_client, tenant_id, admin_headers, "Role Replacement Test")
        
        # Add user to tenant
        add_user_to_tenant(test_client, tenant_id, admin_headers, "test-user", "READER")
        
        # Grant READ role
        test_client.put(
            ENDPOINT_CREDENTIAL_PRINCIPALS.format(tenant_id=tenant_id, credential_id=credential_id),
            json={
                "principal_id": "test-user",
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_READ
            },
            headers=admin_headers
        )
        
        # Upgrade to WRITE role (should replace READ)
        response = test_client.put(
            ENDPOINT_CREDENTIAL_PRINCIPALS.format(tenant_id=tenant_id, credential_id=credential_id),
            json={
                "principal_id": "test-user",
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_WRITE
            },
            headers=admin_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert ROLE_WRITE in data["roles"]
    
    def test_removing_admin_role(self, test_client: TestClient, fake_redis_client: Any) -> None:
        """Test removing ADMIN role from a user."""
        # Admin creates tenant and credential
        admin_token = test_client.create_test_user("remove-admin", "Remove Admin")
        admin_headers = create_auth_headers(admin_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, admin_token)
        credential_id = create_credential(test_client, tenant_id, admin_headers, "Remove Admin Test")
        
        # Second admin
        admin2_token = test_client.create_test_user("admin-2-remove", "Admin Two Remove")
        admin2_headers = create_auth_headers(admin2_token, use_cache=False)
        
        # Add admin2 to tenant
        add_user_to_tenant(test_client, tenant_id, admin_headers, "admin-2-remove", "READER")
        
        # Grant ADMIN to admin2
        test_client.put(
            ENDPOINT_CREDENTIAL_PRINCIPALS.format(tenant_id=tenant_id, credential_id=credential_id),
            json={
                "principal_id": "admin-2-remove",
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_ADMIN
            },
            headers=admin_headers
        )
        
        # Admin2 can delete
        update_response = test_client.patch(
            ENDPOINT_CREDENTIAL_DETAIL.format(tenant_id=tenant_id, credential_id=credential_id),
            json={"name": "Updated by Admin 2"},
            headers=admin2_headers
        )
        assert update_response.status_code == status.HTTP_200_OK
        
        # Admin1 removes ADMIN role from admin2
        test_client.request(
            "DELETE",
            ENDPOINT_CREDENTIAL_PRINCIPALS.format(tenant_id=tenant_id, credential_id=credential_id),
            json={
                "principal_id": "admin-2-remove",
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_ADMIN
            },
            headers=admin_headers
        )
        
        # Admin2 can no longer modify (no permissions)
        update_response2 = test_client.patch(
            ENDPOINT_CREDENTIAL_DETAIL.format(tenant_id=tenant_id, credential_id=credential_id),
            json={"name": "Should Fail"},
            headers=admin2_headers
        )
        assert update_response2.status_code == status.HTTP_403_FORBIDDEN
    
    def test_tenant_global_admin_bypasses_credential_permissions(self, test_client: TestClient) -> None:
        """Test that tenant GLOBAL_ADMIN can access all credentials without explicit permissions."""
        # User A creates tenant
        user_a_token = test_client.create_test_user("tenant-admin", "Tenant Admin")
        headers_a = create_auth_headers(user_a_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, user_a_token)
        
        # User B creates a credential in the same tenant
        user_b_token = test_client.create_test_user("credential-owner", "Credential Owner")
        headers_b = create_auth_headers(user_b_token, use_cache=False)
        
        # Add user B to tenant as CREDENTIALS_CREATOR
        add_user_to_tenant(test_client, tenant_id, headers_a, "credential-owner", "CREDENTIALS_CREATOR")
        
        # User B creates credential
        credential_id = create_credential(test_client, tenant_id, headers_b, "Private Credential")
        
        # User A (tenant creator = GLOBAL_ADMIN) can access credential
        get_response = test_client.get(
            ENDPOINT_CREDENTIAL_DETAIL.format(tenant_id=tenant_id, credential_id=credential_id),
            headers=headers_a
        )
        assert get_response.status_code == status.HTTP_200_OK
        
        # User A can update credential
        update_response = test_client.patch(
            ENDPOINT_CREDENTIAL_DETAIL.format(tenant_id=tenant_id, credential_id=credential_id),
            json={"name": "Updated by Global Admin"},
            headers=headers_a
        )
        assert update_response.status_code == status.HTTP_200_OK
        
        # User A can delete credential
        delete_response = test_client.request(
            "DELETE",
            ENDPOINT_CREDENTIAL_DETAIL.format(tenant_id=tenant_id, credential_id=credential_id),
            headers=headers_a
        )
        assert delete_response.status_code == status.HTTP_204_NO_CONTENT
    
    def test_tenant_credentials_admin_bypasses_credential_permissions(self, test_client: TestClient) -> None:
        """Test that tenant CREDENTIALS_ADMIN can access all credentials without explicit permissions."""
        # User A creates tenant
        user_a_token = test_client.create_test_user("tenant-creator", "Tenant Creator")
        headers_a = create_auth_headers(user_a_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, user_a_token)
        
        # User B will be CREDENTIALS_ADMIN
        user_b_token = test_client.create_test_user("credentials-admin", "Credentials Admin")
        headers_b = create_auth_headers(user_b_token, use_cache=False)
        
        # Add user B to tenant with CREDENTIALS_ADMIN role
        add_user_to_tenant(test_client, tenant_id, headers_a, "credentials-admin", "CREDENTIALS_ADMIN")
        
        # User A creates credential
        credential_id = create_credential(test_client, tenant_id, headers_a, "Test Credential")
        
        # User B (CREDENTIALS_ADMIN) can access credential
        get_response = test_client.get(
            ENDPOINT_CREDENTIAL_DETAIL.format(tenant_id=tenant_id, credential_id=credential_id),
            headers=headers_b
        )
        assert get_response.status_code == status.HTTP_200_OK
        
        # User B can update credential
        update_response = test_client.patch(
            ENDPOINT_CREDENTIAL_DETAIL.format(tenant_id=tenant_id, credential_id=credential_id),
            json={"name": "Updated by Credentials Admin"},
            headers=headers_b
        )
        assert update_response.status_code == status.HTTP_200_OK
        
        # User B can delete credential
        delete_response = test_client.request(
            "DELETE",
            ENDPOINT_CREDENTIAL_DETAIL.format(tenant_id=tenant_id, credential_id=credential_id),
            headers=headers_b
        )
        assert delete_response.status_code == status.HTTP_204_NO_CONTENT


class TestCredentialSecretRBAC:
    """Test suite for credential secret endpoint RBAC."""
    
    def test_admin_can_get_secret(self, test_client: TestClient) -> None:
        """Test that ADMIN on credential can get secret."""
        user_token = test_client.create_test_user("secret-admin", "Secret Admin")
        headers = create_auth_headers(user_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, user_token)
        
        # Create credential
        credential_id = create_credential(test_client, tenant_id, headers, "Secret Test Cred")
        
        # ADMIN can get secret
        response = test_client.get(
            f"{ENDPOINT_CREDENTIAL_DETAIL.format(tenant_id=tenant_id, credential_id=credential_id)}/secret",
            headers=headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["credential_id"] == credential_id
        assert "secret_value" in data
        assert data["secret_value"] == "secret-Secret Test Cred"
    
    def test_write_user_can_get_secret(self, test_client: TestClient) -> None:
        """Test that user with WRITE permission can get secret."""
        # Create admin user and tenant
        admin_token = test_client.create_test_user("secret-owner", "Secret Owner")
        admin_headers = create_auth_headers(admin_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, admin_token)
        
        # Create credential
        credential_id = create_credential(test_client, tenant_id, admin_headers, "Write Test Cred")
        
        # Create write user and add to tenant
        write_token = test_client.create_test_user("secret-writer", "Secret Writer")
        write_headers = create_auth_headers(write_token, use_cache=False)
        add_user_to_tenant(test_client, tenant_id, admin_headers, "secret-writer", "READER")
        
        # Grant WRITE permission to user
        test_client.put(
            ENDPOINT_CREDENTIAL_PRINCIPALS.format(tenant_id=tenant_id, credential_id=credential_id),
            json={
                "principal_id": "secret-writer",
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_WRITE
            },
            headers=admin_headers
        )
        
        # WRITE user can get secret
        response = test_client.get(
            f"{ENDPOINT_CREDENTIAL_DETAIL.format(tenant_id=tenant_id, credential_id=credential_id)}/secret",
            headers=write_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["secret_value"] == "secret-Write Test Cred"
    
    def test_read_user_cannot_get_secret(self, test_client: TestClient) -> None:
        """Test that user with only READ permission CANNOT get secret."""
        # Create admin user and tenant
        admin_token = test_client.create_test_user("secret-admin-2", "Secret Admin 2")
        admin_headers = create_auth_headers(admin_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, admin_token)
        
        # Create credential
        credential_id = create_credential(test_client, tenant_id, admin_headers, "Read Test Cred")
        
        # Create read user and add to tenant
        read_token = test_client.create_test_user("secret-reader", "Secret Reader")
        read_headers = create_auth_headers(read_token, use_cache=False)
        add_user_to_tenant(test_client, tenant_id, admin_headers, "secret-reader", "READER")
        
        # Grant READ permission to user (not WRITE)
        test_client.put(
            ENDPOINT_CREDENTIAL_PRINCIPALS.format(tenant_id=tenant_id, credential_id=credential_id),
            json={
                "principal_id": "secret-reader",
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_READ
            },
            headers=admin_headers
        )
        
        # READ user can get credential metadata
        get_response = test_client.get(
            ENDPOINT_CREDENTIAL_DETAIL.format(tenant_id=tenant_id, credential_id=credential_id),
            headers=read_headers
        )
        assert get_response.status_code == status.HTTP_200_OK
        
        # READ user CANNOT get secret
        secret_response = test_client.get(
            f"{ENDPOINT_CREDENTIAL_DETAIL.format(tenant_id=tenant_id, credential_id=credential_id)}/secret",
            headers=read_headers
        )
        assert secret_response.status_code == status.HTTP_403_FORBIDDEN
    
    def test_non_member_cannot_get_secret(self, test_client: TestClient) -> None:
        """Test that user without any permission cannot get secret."""
        # Create admin user and tenant
        admin_token = test_client.create_test_user("secret-admin-3", "Secret Admin 3")
        admin_headers = create_auth_headers(admin_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, admin_token)
        
        # Create credential
        credential_id = create_credential(test_client, tenant_id, admin_headers, "Private Cred")
        
        # Create other user (NOT added to tenant)
        other_token = test_client.create_test_user("secret-outsider", "Secret Outsider")
        other_headers = create_auth_headers(other_token, use_cache=False)
        
        # Non-member cannot get secret
        response = test_client.get(
            f"{ENDPOINT_CREDENTIAL_DETAIL.format(tenant_id=tenant_id, credential_id=credential_id)}/secret",
            headers=other_headers
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN
    
    def test_global_admin_can_get_secret(self, test_client: TestClient) -> None:
        """Test that GLOBAL_ADMIN on tenant can get any credential secret."""
        # Create owner and tenant
        owner_token = test_client.create_test_user("tenant-owner", "Tenant Owner")
        owner_headers = create_auth_headers(owner_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, owner_token)
        
        # Create credential
        credential_id = create_credential(test_client, tenant_id, owner_headers, "Global Admin Test")
        
        # Create global admin user
        admin_token = test_client.create_test_user("global-admin-user", "Global Admin User")
        admin_headers = create_auth_headers(admin_token, use_cache=False)
        
        # Add as GLOBAL_ADMIN to tenant
        add_user_to_tenant(test_client, tenant_id, owner_headers, "global-admin-user", "GLOBAL_ADMIN")
        
        # GLOBAL_ADMIN can get secret without specific credential permission
        response = test_client.get(
            f"{ENDPOINT_CREDENTIAL_DETAIL.format(tenant_id=tenant_id, credential_id=credential_id)}/secret",
            headers=admin_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["secret_value"] == "secret-Global Admin Test"
    
    def test_credentials_admin_can_get_secret(self, test_client: TestClient) -> None:
        """Test that CREDENTIALS_ADMIN on tenant can get any credential secret."""
        # Create owner and tenant
        owner_token = test_client.create_test_user("cred-tenant-owner", "Cred Tenant Owner")
        owner_headers = create_auth_headers(owner_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, owner_token)
        
        # Create credential
        credential_id = create_credential(test_client, tenant_id, owner_headers, "Cred Admin Test")
        
        # Create credentials admin user
        cred_admin_token = test_client.create_test_user("cred-admin-user", "Cred Admin User")
        cred_admin_headers = create_auth_headers(cred_admin_token, use_cache=False)
        
        # Add as CREDENTIALS_ADMIN to tenant
        add_user_to_tenant(test_client, tenant_id, owner_headers, "cred-admin-user", "CREDENTIALS_ADMIN")
        
        # CREDENTIALS_ADMIN can get secret without specific credential permission
        response = test_client.get(
            f"{ENDPOINT_CREDENTIAL_DETAIL.format(tenant_id=tenant_id, credential_id=credential_id)}/secret",
            headers=cred_admin_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["secret_value"] == "secret-Cred Admin Test"
    
    def test_get_secret_nonexistent_credential(self, test_client: TestClient) -> None:
        """Test getting secret for non-existent credential returns 404."""
        user_token = test_client.create_test_user("secret-404-user", "Secret 404 User")
        headers = create_auth_headers(user_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, user_token)
        
        response = test_client.get(
            f"{ENDPOINT_CREDENTIAL_DETAIL.format(tenant_id=tenant_id, credential_id='non-existent-id')}/secret",
            headers=headers
        )
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
