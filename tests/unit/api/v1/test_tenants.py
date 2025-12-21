"""Tests for tenant API endpoints."""
from typing import Any
from fastapi import status
from starlette.testclient import TestClient

from aihub.core.database.enums import TenantPermissionEnum, PrincipalTypeEnum
from tests.conftest import create_auth_headers


# API Endpoints
ENDPOINT_TENANTS = "/api/v1/tenants"
ENDPOINT_TENANT_DETAIL = "/api/v1/tenants/{tenant_id}"
ENDPOINT_TENANT_PRINCIPALS = "/api/v1/tenants/{tenant_id}/principals"
ENDPOINT_PRINCIPAL_DETAIL = "/api/v1/tenants/{tenant_id}/principals/{principal_id}"

# Common Test IDs
NON_EXISTENT_ID = "non-existent-id"

# Roles
ROLE_GLOBAL_ADMIN = TenantPermissionEnum.GLOBAL_ADMIN.value
ROLE_READER = TenantPermissionEnum.READER.value
ROLE_APPLICATIONS_ADMIN = TenantPermissionEnum.APPLICATIONS_ADMIN.value

# Principal Types
PRINCIPAL_TYPE_USER = PrincipalTypeEnum.IDENTITY_USER.value
PRINCIPAL_TYPE_GROUP = PrincipalTypeEnum.IDENTITY_GROUP.value


class TestTenantRoutes:
    """Test suite for tenant API routes."""
    
    def test_create_tenant_success(
        self, 
        test_client: TestClient, 
        auth_headers: dict[str, str], 
        sample_tenant_data: dict[str, Any], 
        test_user_token: Any
    ) -> None:
        """Test successful tenant creation."""
        response = test_client.post(
            ENDPOINT_TENANTS,
            json=sample_tenant_data,
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        
        # Field names
        field_name = "name"
        field_description = "description"
        field_id = "id"
        field_created_at = "created_at"
        field_updated_at = "updated_at"
        field_created_by = "created_by"
        
        assert data[field_name] == sample_tenant_data[field_name]
        assert data[field_description] == sample_tenant_data[field_description]
        assert field_id in data
        assert field_created_at in data
        assert field_updated_at in data
        assert data[field_created_by] == test_user_token.get_id()

    def test_create_tenant_missing_name(self, test_client: TestClient, auth_headers: dict[str, str]) -> None:
        """Test tenant creation with missing name."""
        tenant_description = "Test tenant"
        response = test_client.post(
            ENDPOINT_TENANTS,
            json={"description": tenant_description},
            headers=auth_headers
        )
        
        assert response.status_code == 422
    
    def test_create_tenant_invalid_name_type(self, test_client: TestClient, auth_headers: dict[str, str]) -> None:
        """Test tenant creation with invalid name type."""
        response = test_client.post(
            ENDPOINT_TENANTS,
            json={"name": 123, "description": "Test"},
            headers=auth_headers
        )
        
        assert response.status_code == 422
    
    def test_create_tenant_empty_name(self, test_client: TestClient, auth_headers: dict[str, str]) -> None:
        """Test tenant creation with empty name."""
        response = test_client.post(
            ENDPOINT_TENANTS,
            json={"name": "", "description": "Test"},
            headers=auth_headers
        )
        
        assert response.status_code == 422
    
    def test_create_tenant_invalid_description_type(self, test_client: TestClient, auth_headers: dict[str, str]) -> None:
        """Test tenant creation with invalid description type."""
        response = test_client.post(
            ENDPOINT_TENANTS,
            json={"name": "Test Tenant", "description": 123},
            headers=auth_headers
        )
        
        assert response.status_code == 422
    
    def test_create_tenant_empty_body(self, test_client: TestClient, auth_headers: dict[str, str]) -> None:
        """Test tenant creation with empty JSON body."""
        response = test_client.post(
            ENDPOINT_TENANTS,
            json={},
            headers=auth_headers
        )
        
        assert response.status_code == 422
    
    def test_create_tenant_multiple_users(self, test_client: TestClient, sample_tenant_data: dict[str, Any]) -> None:
        """Test that different users can create their own tenants."""
        # Create first user and tenant
        user1_id = "user-1"
        user1_name = "User One"
        tenant1_name = "Tenant 1"
        tenant1_desc = "First tenant"
        
        user1_token = test_client.create_test_user(user1_id, user1_name)
        headers1 = create_auth_headers(user1_token, use_cache=False)
        
        response1 = test_client.post(
            ENDPOINT_TENANTS,
            json={"name": tenant1_name, "description": tenant1_desc},
            headers=headers1
        )
        
        assert response1.status_code == status.HTTP_201_CREATED
        assert response1.json()["created_by"] == user1_id
        
        # Create second user and tenant
        user2_id = "user-2"
        user2_name = "User Two"
        tenant2_name = "Tenant 2"
        tenant2_desc = "Second tenant"
        
        user2_token = test_client.create_test_user(user2_id, user2_name)
        headers2 = create_auth_headers(user2_token, use_cache=False)
        
        response2 = test_client.post(
            ENDPOINT_TENANTS,
            json={"name": tenant2_name, "description": tenant2_desc},
            headers=headers2
        )
        
        assert response2.status_code == status.HTTP_201_CREATED
        assert response2.json()["created_by"] == user2_id
    
    def test_get_tenant_success(self, test_client: TestClient, auth_headers: dict[str, str], sample_tenant_data: dict[str, Any]) -> None:
        """Test successful tenant retrieval."""
        # First create a tenant
        create_response = test_client.post(
            ENDPOINT_TENANTS,
            json=sample_tenant_data,
            headers=auth_headers
        )
        tenant_id = create_response.json()["id"]
        
        # Then retrieve it
        response = test_client.get(
            ENDPOINT_TENANT_DETAIL.format(tenant_id=tenant_id),
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["id"] == tenant_id
        assert data["name"] == sample_tenant_data["name"]
        assert data["description"] == sample_tenant_data["description"]
    
    def test_get_tenant_not_found(self, test_client: TestClient, auth_headers: dict[str, str]) -> None:
        """Test tenant retrieval with non-existent ID."""
        response = test_client.get(
            ENDPOINT_TENANT_DETAIL.format(tenant_id=NON_EXISTENT_ID),
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_403_FORBIDDEN  # 403 instead of 404 for security
    
    def test_list_tenants_empty(self, test_client: TestClient, auth_headers: dict[str, str]) -> None:
        """Test listing tenants when none exist."""
        response = test_client.get(
            ENDPOINT_TENANTS,
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert isinstance(data, list)
        assert len(data) == 0
    
    def test_list_tenants_with_data(self, test_client: TestClient, auth_headers: dict[str, str], sample_tenant_data: dict[str, Any], test_user_token: Any) -> None:
        """Test listing tenants with existing data."""
        # Create multiple tenants
        tenant_data_1 = sample_tenant_data.copy()
        tenant_data_2 = {"name": "Second Tenant", "description": "Another test tenant"}
        
        test_client.post(ENDPOINT_TENANTS, json=tenant_data_1, headers=auth_headers)
        test_client.post(ENDPOINT_TENANTS, json=tenant_data_2, headers=auth_headers)
        
        # List tenants
        response = test_client.get(
            ENDPOINT_TENANTS,
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert isinstance(data, list)
        assert len(data) == 2
        
        names = [tenant["name"] for tenant in data]
        assert "Test Tenant" in names
        assert "Second Tenant" in names
    
    def test_list_tenants_with_pagination(self, test_client: TestClient, auth_headers: dict[str, str], sample_tenant_data: dict[str, Any], test_user_token: Any) -> None:
        """Test listing tenants with pagination parameters."""
        # Create multiple tenants
        for i in range(5):
            tenant_data = {"name": f"Tenant {i}", "description": f"Test tenant {i}"}
            test_client.post(ENDPOINT_TENANTS, json=tenant_data, headers=auth_headers)
        
        # Test with limit
        response = test_client.get(
            f"{ENDPOINT_TENANTS}?limit=3",
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 3
        
        # Test with skip
        response = test_client.get(
            f"{ENDPOINT_TENANTS}?skip=2&limit=2",
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 2
    
    def test_list_tenants_with_name_filter(self, test_client: TestClient, auth_headers: dict[str, str], test_user_token: Any) -> None:
        """Test listing tenants with name filter."""
        # Create tenants with different names
        test_client.post(ENDPOINT_TENANTS, json={"name": "Production", "description": "Prod"}, headers=auth_headers)
        test_client.post(ENDPOINT_TENANTS, json={"name": "Development", "description": "Dev"}, headers=auth_headers)
        test_client.post(ENDPOINT_TENANTS, json={"name": "Staging", "description": "Stage"}, headers=auth_headers)
        
        # Filter by name
        response = test_client.get(
            f"{ENDPOINT_TENANTS}?name=Development",
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert len(data) >= 1
        assert any(tenant["name"] == "Development" for tenant in data)
    
    def test_update_tenant_success(self, test_client: TestClient, auth_headers: dict[str, str], sample_tenant_data: dict[str, Any], sample_update_tenant_data: dict[str, Any], test_user_token: Any) -> None:
        """Test successful tenant update."""
        # Create a tenant
        create_response = test_client.post(
            ENDPOINT_TENANTS,
            json=sample_tenant_data,
            headers=auth_headers
        )
        tenant_id = create_response.json()["id"]
        
        # Update the tenant
        response = test_client.patch(
            ENDPOINT_TENANT_DETAIL.format(tenant_id=tenant_id),
            json=sample_update_tenant_data,
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["id"] == tenant_id
        assert data["name"] == sample_update_tenant_data["name"]
        assert data["description"] == sample_update_tenant_data["description"]
        assert data["updated_by"] == test_user_token.get_id()
    
    def test_update_tenant_not_found(self, test_client: TestClient, auth_headers: dict[str, str], sample_update_tenant_data: dict[str, Any], test_user_token: Any) -> None:
        """Test updating a non-existent tenant."""
        response = test_client.patch(
            ENDPOINT_TENANT_DETAIL.format(tenant_id=NON_EXISTENT_ID),
            json=sample_update_tenant_data,
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_403_FORBIDDEN  # 403 instead of 404 for security
    
    def test_update_tenant_partial(self, test_client: TestClient, auth_headers: dict[str, str], sample_tenant_data: dict[str, Any], test_user_token: Any) -> None:
        """Test partial tenant update."""
        # Create a tenant
        create_response = test_client.post(
            ENDPOINT_TENANTS,
            json=sample_tenant_data,
            headers=auth_headers
        )
        tenant_id = create_response.json()["id"]
        
        # Update only name
        response = test_client.patch(
            ENDPOINT_TENANT_DETAIL.format(tenant_id=tenant_id),
            json={"name": "Partially Updated"},
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["name"] == "Partially Updated"
        assert data["description"] == sample_tenant_data["description"]
    
    def test_delete_tenant_success(self, test_client: TestClient, auth_headers: dict[str, str], sample_tenant_data: dict[str, Any], test_user_token: Any) -> None:
        """Test successful tenant deletion."""
        # Create a tenant
        create_response = test_client.post(
            ENDPOINT_TENANTS,
            json=sample_tenant_data,
            headers=auth_headers
        )
        tenant_id = create_response.json()["id"]
        
        # Delete the tenant
        response = test_client.request("DELETE", 
            ENDPOINT_TENANT_DETAIL.format(tenant_id=tenant_id),
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_204_NO_CONTENT
        
        # Verify tenant is deleted - returns 403 because user no longer has access
        get_response = test_client.get(
            ENDPOINT_TENANT_DETAIL.format(tenant_id=tenant_id),
            headers=auth_headers
        )
        assert get_response.status_code == status.HTTP_403_FORBIDDEN
    
    def test_delete_tenant_not_found(self, test_client: TestClient, auth_headers: dict[str, str], test_user_token: Any) -> None:
        """Test deleting a non-existent tenant."""
        response = test_client.request("DELETE", 
            ENDPOINT_TENANT_DETAIL.format(tenant_id=NON_EXISTENT_ID),
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_403_FORBIDDEN  # 403 instead of 404 for security


class TestTenantPrincipalRoutes:
    """Test suite for tenant principal/role management routes."""
    
    def test_list_tenant_principals_empty(self, test_client: TestClient, auth_headers: dict[str, str], sample_tenant_data: dict[str, Any], test_user_token: Any) -> None:
        """Test listing principals for a tenant with only the creator."""
        # Create a tenant
        create_response = test_client.post(
            ENDPOINT_TENANTS,
            json=sample_tenant_data,
            headers=auth_headers
        )
        tenant_id = create_response.json()["id"]
        
        # List principals
        response = test_client.get(
            ENDPOINT_TENANT_PRINCIPALS.format(tenant_id=tenant_id),
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert "tenant_id" in data
        assert "principals" in data
        assert len(data["principals"]) >= 1  # At least the creator
        
        # Check creator has GLOBAL_ADMIN role
        creator_principal = next(
            (p for p in data["principals"] if p["principal_id"] == test_user_token.get_id()),
            None
        )
        assert creator_principal is not None
        assert ROLE_GLOBAL_ADMIN in creator_principal["roles"]
    
    def test_get_principal_permissions(self, test_client: TestClient, auth_headers: dict[str, str], sample_tenant_data: dict[str, Any], test_user_token: Any) -> None:
        """Test getting permissions for a specific principal."""
        # Create a tenant
        create_response = test_client.post(
            ENDPOINT_TENANTS,
            json=sample_tenant_data,
            headers=auth_headers
        )
        tenant_id = create_response.json()["id"]
        
        # Get creator's permissions
        response = test_client.get(
            ENDPOINT_PRINCIPAL_DETAIL.format(tenant_id=tenant_id, principal_id="test-user-123"),
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["principal_id"] == test_user_token.get_id()
        assert data["principal_type"] == PRINCIPAL_TYPE_USER
        assert ROLE_GLOBAL_ADMIN in data["roles"]
    
    def test_set_principal_permission_new_user(self, test_client: TestClient, auth_headers: dict[str, str], sample_tenant_data: dict[str, Any]) -> None:
        """Test adding a role for a new principal."""
        # Create a tenant
        create_response = test_client.post(
            ENDPOINT_TENANTS,
            json=sample_tenant_data,
            headers=auth_headers
        )
        tenant_id = create_response.json()["id"]
        
        # Add a new user with READER role
        role_data = {
            "principal_id": "user-456",
            "principal_type": PRINCIPAL_TYPE_USER,
            "role": ROLE_READER
        }
        
        response = test_client.put(
            ENDPOINT_TENANT_PRINCIPALS.format(tenant_id=tenant_id),
            json=role_data,
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["principal_id"] == "user-456"
        assert data["principal_type"] == PRINCIPAL_TYPE_USER
        assert ROLE_READER in data["roles"]
    
    def test_set_principal_permission_add_role(self, test_client: TestClient, auth_headers: dict[str, str], sample_tenant_data: dict[str, Any]) -> None:
        """Test adding an additional role to an existing principal."""
        # Create a tenant
        create_response = test_client.post(
            ENDPOINT_TENANTS,
            json=sample_tenant_data,
            headers=auth_headers
        )
        tenant_id = create_response.json()["id"]
        
        # Add first role
        role_data_1 = {
            "principal_id": "user-789",
            "principal_type": PRINCIPAL_TYPE_USER,
            "role": ROLE_READER
        }
        test_client.put(
            ENDPOINT_TENANT_PRINCIPALS.format(tenant_id=tenant_id),
            json=role_data_1,
            headers=auth_headers
        )
        
        # Add second role
        role_data_2 = {
            "principal_id": "user-789",
            "principal_type": PRINCIPAL_TYPE_USER,
            "role": ROLE_APPLICATIONS_ADMIN
        }
        
        response = test_client.put(
            ENDPOINT_TENANT_PRINCIPALS.format(tenant_id=tenant_id),
            json=role_data_2,
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["principal_id"] == "user-789"
        assert len(data["roles"]) == 2
        assert ROLE_READER in data["roles"]
        assert ROLE_APPLICATIONS_ADMIN in data["roles"]
    
    def test_set_principal_permission_duplicate_role(self, test_client: TestClient, auth_headers: dict[str, str], sample_tenant_data: dict[str, Any]) -> None:
        """Test adding the same role twice (should be idempotent)."""
        # Create a tenant
        create_response = test_client.post(
            ENDPOINT_TENANTS,
            json=sample_tenant_data,
            headers=auth_headers
        )
        tenant_id = create_response.json()["id"]
        
        # Add role first time
        role_data = {
            "principal_id": "user-999",
            "principal_type": PRINCIPAL_TYPE_USER,
            "role": ROLE_READER
        }
        test_client.put(
            ENDPOINT_TENANT_PRINCIPALS.format(tenant_id=tenant_id),
            json=role_data,
            headers=auth_headers
        )
        
        # Add same role again
        response = test_client.put(
            ENDPOINT_TENANT_PRINCIPALS.format(tenant_id=tenant_id),
            json=role_data,
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        # Should still have only one READER role
        assert data["roles"].count(ROLE_READER) == 1
    
    def test_set_principal_permission_with_different_users(self, test_client: TestClient, sample_tenant_data: dict[str, Any]) -> None:
        """Test adding roles with multiple different users."""
        # Create admin user and tenant
        admin_token = test_client.create_test_user("admin-user", "Admin User")
        admin_headers = create_auth_headers(admin_token, use_cache=False)
        
        create_response = test_client.post(
            ENDPOINT_TENANTS,
            json=sample_tenant_data,
            headers=admin_headers
        )
        tenant_id = create_response.json()["id"]
        
        # Create additional test users
        user1_token = test_client.create_test_user("user-001", "User One")
        user2_token = test_client.create_test_user("user-002", "User Two")
        
        # Admin adds user1 with READER role
        response1 = test_client.put(
            ENDPOINT_TENANT_PRINCIPALS.format(tenant_id=tenant_id),
            json={"principal_id": "user-001", "principal_type": PRINCIPAL_TYPE_USER, "role": ROLE_READER},
            headers=admin_headers
        )
        assert response1.status_code == status.HTTP_200_OK
        assert ROLE_READER in response1.json()["roles"]
        
        # Admin adds user2 with APPLICATIONS_ADMIN role
        response2 = test_client.put(
            ENDPOINT_TENANT_PRINCIPALS.format(tenant_id=tenant_id),
            json={"principal_id": "user-002", "principal_type": PRINCIPAL_TYPE_USER, "role": ROLE_APPLICATIONS_ADMIN},
            headers=admin_headers
        )
        assert response2.status_code == status.HTTP_200_OK
        assert ROLE_APPLICATIONS_ADMIN in response2.json()["roles"]
        
        # List all principals
        list_response = test_client.get(
            ENDPOINT_TENANT_PRINCIPALS.format(tenant_id=tenant_id),
            headers=admin_headers
        )
        assert list_response.status_code == status.HTTP_200_OK
        principals = list_response.json()["principals"]
        
        # Should have admin + 2 users
        assert len(principals) >= 3
        principal_ids = [p["principal_id"] for p in principals]
        assert "admin-user" in principal_ids
        assert "user-001" in principal_ids
        assert "user-002" in principal_ids
    
    def test_set_principal_permission_missing_principal_id(self, test_client: TestClient, auth_headers: dict[str, str], sample_tenant_data: dict[str, Any]) -> None:
        """Test setting principal permission with missing principal_id."""
        # Create tenant
        create_response = test_client.post(
            ENDPOINT_TENANTS,
            json=sample_tenant_data,
            headers=auth_headers
        )
        tenant_id = create_response.json()["id"]
        
        # Try to add permission without principal_id
        response = test_client.put(
            ENDPOINT_TENANT_PRINCIPALS.format(tenant_id=tenant_id),
            json={
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_READER
            },
            headers=auth_headers
        )
        
        assert response.status_code == 422
    
    def test_set_principal_permission_missing_role(self, test_client: TestClient, auth_headers: dict[str, str], sample_tenant_data: dict[str, Any]) -> None:
        """Test setting principal permission with missing role."""
        # Create tenant
        create_response = test_client.post(
            ENDPOINT_TENANTS,
            json=sample_tenant_data,
            headers=auth_headers
        )
        tenant_id = create_response.json()["id"]
        
        # Try to add permission without role
        response = test_client.put(
            ENDPOINT_TENANT_PRINCIPALS.format(tenant_id=tenant_id),
            json={
                "principal_id": "test-user",
                "principal_type": PRINCIPAL_TYPE_USER
            },
            headers=auth_headers
        )
        
        assert response.status_code == 422
    
    def test_set_principal_permission_missing_principal_type(self, test_client: TestClient, auth_headers: dict[str, str], sample_tenant_data: dict[str, Any]) -> None:
        """Test setting principal permission with missing principal_type."""
        # Create tenant
        create_response = test_client.post(
            ENDPOINT_TENANTS,
            json=sample_tenant_data,
            headers=auth_headers
        )
        tenant_id = create_response.json()["id"]
        
        # Try to add permission without principal_type
        response = test_client.put(
            ENDPOINT_TENANT_PRINCIPALS.format(tenant_id=tenant_id),
            json={
                "principal_id": "test-user",
                "role": ROLE_READER
            },
            headers=auth_headers
        )
        
        assert response.status_code == 422
    
    def test_set_principal_permission_empty_body(self, test_client: TestClient, auth_headers: dict[str, str], sample_tenant_data: dict[str, Any]) -> None:
        """Test setting principal permission with empty body."""
        # Create tenant
        create_response = test_client.post(
            ENDPOINT_TENANTS,
            json=sample_tenant_data,
            headers=auth_headers
        )
        tenant_id = create_response.json()["id"]
        
        # Try to add permission with empty body
        response = test_client.put(
            ENDPOINT_TENANT_PRINCIPALS.format(tenant_id=tenant_id),
            json={},
            headers=auth_headers
        )
        
        assert response.status_code == 422
    
    def test_delete_principal_permission(self, test_client: TestClient, auth_headers: dict[str, str], sample_tenant_data: dict[str, Any]) -> None:
        """Test removing a role from a principal."""
        # Create a tenant
        create_response = test_client.post(
            ENDPOINT_TENANTS,
            json=sample_tenant_data,
            headers=auth_headers
        )
        tenant_id = create_response.json()["id"]
        
        # Add two roles to a user
        user_id = "user-delete-test"
        test_client.put(
            ENDPOINT_TENANT_PRINCIPALS.format(tenant_id=tenant_id),
            json={"principal_id": user_id, "principal_type": PRINCIPAL_TYPE_USER, "role": ROLE_READER},
            headers=auth_headers
        )
        test_client.put(
            ENDPOINT_TENANT_PRINCIPALS.format(tenant_id=tenant_id),
            json={"principal_id": user_id, "principal_type": PRINCIPAL_TYPE_USER, "role": ROLE_APPLICATIONS_ADMIN},
            headers=auth_headers
        )
        
        # Delete one role
        delete_data = {
            "principal_id": user_id,
            "principal_type": PRINCIPAL_TYPE_USER,
            "role": ROLE_READER
        }
        
        response = test_client.request("DELETE", 
            ENDPOINT_TENANT_PRINCIPALS.format(tenant_id=tenant_id),
            json=delete_data,
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["principal_id"] == user_id
        assert ROLE_READER not in data["roles"]
        assert ROLE_APPLICATIONS_ADMIN in data["roles"]
    
    def test_delete_principal_permission_not_found(self, test_client: TestClient, auth_headers: dict[str, str], sample_tenant_data: dict[str, Any], test_user_token: Any) -> None:
        """Test removing a non-existent role."""
        # Create a tenant
        create_response = test_client.post(
            ENDPOINT_TENANTS,
            json=sample_tenant_data,
            headers=auth_headers
        )
        tenant_id = create_response.json()["id"]
        
        # Try to delete role that doesn't exist
        delete_data = {
            "principal_id": "non-existent-user",
            "principal_type": PRINCIPAL_TYPE_USER,
            "role": ROLE_READER
        }
        
        response = test_client.request("DELETE", 
            ENDPOINT_TENANT_PRINCIPALS.format(tenant_id=tenant_id),
            json=delete_data,
            headers=auth_headers
        )
        
        # Should return 404 or handle gracefully
        assert response.status_code in [status.HTTP_404_NOT_FOUND, status.HTTP_200_OK]
    
    def test_delete_principal_permission_missing_principal_id(self, test_client: TestClient, auth_headers: dict[str, str], sample_tenant_data: dict[str, Any]) -> None:
        """Test deleting principal permission with missing principal_id."""
        # Create tenant
        create_response = test_client.post(
            ENDPOINT_TENANTS,
            json=sample_tenant_data,
            headers=auth_headers
        )
        tenant_id = create_response.json()["id"]
        
        # Try to delete permission without principal_id
        response = test_client.request(
            "DELETE",
            ENDPOINT_TENANT_PRINCIPALS.format(tenant_id=tenant_id),
            json={
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_READER
            },
            headers=auth_headers
        )
        
        assert response.status_code == 422
    
    def test_delete_principal_permission_missing_role(self, test_client: TestClient, auth_headers: dict[str, str], sample_tenant_data: dict[str, Any]) -> None:
        """Test deleting principal permission with missing role."""
        # Create tenant
        create_response = test_client.post(
            ENDPOINT_TENANTS,
            json=sample_tenant_data,
            headers=auth_headers
        )
        tenant_id = create_response.json()["id"]
        
        # Try to delete permission without role
        response = test_client.request(
            "DELETE",
            ENDPOINT_TENANT_PRINCIPALS.format(tenant_id=tenant_id),
            json={
                "principal_id": "test-user",
                "principal_type": PRINCIPAL_TYPE_USER
            },
            headers=auth_headers
        )
        
        assert response.status_code == 422
    
    def test_delete_principal_permission_missing_principal_type(self, test_client: TestClient, auth_headers: dict[str, str], sample_tenant_data: dict[str, Any]) -> None:
        """Test deleting principal permission with missing principal_type."""
        # Create tenant
        create_response = test_client.post(
            ENDPOINT_TENANTS,
            json=sample_tenant_data,
            headers=auth_headers
        )
        tenant_id = create_response.json()["id"]
        
        # Try to delete permission without principal_type
        response = test_client.request(
            "DELETE",
            ENDPOINT_TENANT_PRINCIPALS.format(tenant_id=tenant_id),
            json={
                "principal_id": "test-user",
                "role": ROLE_READER
            },
            headers=auth_headers
        )
        
        assert response.status_code == 422
    
    def test_delete_principal_permission_empty_body(self, test_client: TestClient, auth_headers: dict[str, str], sample_tenant_data: dict[str, Any]) -> None:
        """Test deleting principal permission with empty body."""
        # Create tenant
        create_response = test_client.post(
            ENDPOINT_TENANTS,
            json=sample_tenant_data,
            headers=auth_headers
        )
        tenant_id = create_response.json()["id"]
        
        # Try to delete permission with empty body
        response = test_client.request(
            "DELETE",
            ENDPOINT_TENANT_PRINCIPALS.format(tenant_id=tenant_id),
            json={},
            headers=auth_headers
        )
        
        assert response.status_code == 422

    def test_multi_user_access_control(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test that users can only see/manage tenants they have access to."""
        # Create two separate users
        user1_token = test_client.create_test_user("isolated-user-1", "Isolated User One")
        user2_token = test_client.create_test_user("isolated-user-2", "Isolated User Two")
        
        headers1 = create_auth_headers(user1_token, use_cache=False)
        headers2 = create_auth_headers(user2_token, use_cache=False)
        
        # User 1 creates a tenant
        tenant1_response = test_client.post(
            ENDPOINT_TENANTS,
            json={"name": "User 1 Tenant", "description": "Private to user 1"},
            headers=headers1
        )
        assert tenant1_response.status_code == status.HTTP_201_CREATED
        tenant1_id = tenant1_response.json()["id"]
        
        # User 2 creates a tenant
        tenant2_response = test_client.post(
            ENDPOINT_TENANTS,
            json={"name": "User 2 Tenant", "description": "Private to user 2"},
            headers=headers2
        )
        assert tenant2_response.status_code == status.HTTP_201_CREATED
        tenant2_id = tenant2_response.json()["id"]
        
        # Each user should be admin of their own tenant
        principals1 = test_client.get(
            ENDPOINT_PRINCIPAL_DETAIL.format(tenant_id=tenant1_id, principal_id="isolated-user-1"),
            headers=headers1
        )
        assert principals1.status_code == status.HTTP_200_OK
        assert ROLE_GLOBAL_ADMIN in principals1.json()["roles"]
        
        principals2 = test_client.get(
            ENDPOINT_PRINCIPAL_DETAIL.format(tenant_id=tenant2_id, principal_id="isolated-user-2"),
            headers=headers2
        )
        assert principals2.status_code == status.HTTP_200_OK
        assert ROLE_GLOBAL_ADMIN in principals2.json()["roles"]

    """Test suite for tenant API routes."""
    
    def test_create_tenant_success(self, test_client: TestClient, auth_headers: dict[str, str], sample_tenant_data: dict[str, Any], test_user_token: Any) -> None:
        """Test successful tenant creation."""
        response = test_client.post(
            ENDPOINT_TENANTS,
            json=sample_tenant_data,
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        
        assert data["name"] == sample_tenant_data["name"]
        assert data["description"] == sample_tenant_data["description"]
        assert "id" in data
        assert "created_at" in data
        assert "updated_at" in data
        assert data["created_by"] == test_user_token.get_id()
    
    def test_create_tenant_missing_name(self, test_client: TestClient, auth_headers: dict[str, str]) -> None:
        """Test tenant creation with missing name."""
        response = test_client.post(
            ENDPOINT_TENANTS,
            json={"description": "Test tenant"},
            headers=auth_headers
        )
        
        assert response.status_code == 422
    
    def test_get_tenant_success(self, test_client: TestClient, auth_headers: dict[str, str], sample_tenant_data: dict[str, Any]) -> None:
        """Test successful tenant retrieval."""
        # First create a tenant
        create_response = test_client.post(
            ENDPOINT_TENANTS,
            json=sample_tenant_data,
            headers=auth_headers
        )
        tenant_id = create_response.json()["id"]
        
        # Then retrieve it
        response = test_client.get(
            ENDPOINT_TENANT_DETAIL.format(tenant_id=tenant_id),
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["id"] == tenant_id
        assert data["name"] == sample_tenant_data["name"]
        assert data["description"] == sample_tenant_data["description"]
    
    def test_get_tenant_not_found(self, test_client: TestClient, auth_headers: dict[str, str]) -> None:
        """Test tenant retrieval with non-existent ID."""
        response = test_client.get(
            ENDPOINT_TENANT_DETAIL.format(tenant_id=NON_EXISTENT_ID),
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_403_FORBIDDEN  # 403 instead of 404 for security
    
    def test_list_tenants_empty(self, test_client: TestClient, auth_headers: dict[str, str]) -> None:
        """Test listing tenants when none exist."""
        response = test_client.get(
            ENDPOINT_TENANTS,
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert isinstance(data, list)
        assert len(data) == 0
    
    def test_list_tenants_with_data(self, test_client: TestClient, auth_headers: dict[str, str], sample_tenant_data: dict[str, Any], test_user_token: Any) -> None:
        """Test listing tenants with existing data."""
        # Create multiple tenants
        tenant_data_1 = sample_tenant_data.copy()
        tenant_data_2 = {"name": "Second Tenant", "description": "Another test tenant"}
        
        test_client.post(ENDPOINT_TENANTS, json=tenant_data_1, headers=auth_headers)
        test_client.post(ENDPOINT_TENANTS, json=tenant_data_2, headers=auth_headers)
        
        # List tenants
        response = test_client.get(
            ENDPOINT_TENANTS,
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert isinstance(data, list)
        assert len(data) == 2
        
        names = [tenant["name"] for tenant in data]
        assert "Test Tenant" in names
        assert "Second Tenant" in names
    
    def test_list_tenants_with_pagination(self, test_client: TestClient, auth_headers: dict[str, str], sample_tenant_data: dict[str, Any], test_user_token: Any) -> None:
        """Test listing tenants with pagination parameters."""
        # Create multiple tenants
        for i in range(5):
            tenant_data = {"name": f"Tenant {i}", "description": f"Test tenant {i}"}
            test_client.post(ENDPOINT_TENANTS, json=tenant_data, headers=auth_headers)
        
        # Test with limit
        response = test_client.get(
            f"{ENDPOINT_TENANTS}?limit=3",
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 3
        
        # Test with skip
        response = test_client.get(
            f"{ENDPOINT_TENANTS}?skip=2&limit=2",
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 2
    
    def test_list_tenants_with_name_filter(self, test_client: TestClient, auth_headers: dict[str, str], test_user_token: Any) -> None:
        """Test listing tenants with name filter."""
        # Create tenants with different names
        test_client.post(ENDPOINT_TENANTS, json={"name": "Production", "description": "Prod"}, headers=auth_headers)
        test_client.post(ENDPOINT_TENANTS, json={"name": "Development", "description": "Dev"}, headers=auth_headers)
        test_client.post(ENDPOINT_TENANTS, json={"name": "Staging", "description": "Stage"}, headers=auth_headers)
        
        # Filter by name
        response = test_client.get(
            f"{ENDPOINT_TENANTS}?name=Development",
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert len(data) >= 1
        assert any(tenant["name"] == "Development" for tenant in data)
    
    def test_update_tenant_success(self, test_client: TestClient, auth_headers: dict[str, str], sample_tenant_data: dict[str, Any], sample_update_tenant_data: dict[str, Any], test_user_token: Any) -> None:
        """Test successful tenant update."""
        # Create a tenant
        create_response = test_client.post(
            ENDPOINT_TENANTS,
            json=sample_tenant_data,
            headers=auth_headers
        )
        tenant_id = create_response.json()["id"]
        
        # Update the tenant
        response = test_client.patch(
            ENDPOINT_TENANT_DETAIL.format(tenant_id=tenant_id),
            json=sample_update_tenant_data,
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["id"] == tenant_id
        assert data["name"] == sample_update_tenant_data["name"]
        assert data["description"] == sample_update_tenant_data["description"]
        assert data["updated_by"] == test_user_token.get_id()
    
    def test_update_tenant_not_found(self, test_client: TestClient, auth_headers: dict[str, str], sample_update_tenant_data: dict[str, Any], test_user_token: Any) -> None:
        """Test updating a non-existent tenant."""
        response = test_client.patch(
            ENDPOINT_TENANT_DETAIL.format(tenant_id=NON_EXISTENT_ID),
            json=sample_update_tenant_data,
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_403_FORBIDDEN  # 403 instead of 404 for security
    
    def test_update_tenant_partial(self, test_client: TestClient, auth_headers: dict[str, str], sample_tenant_data: dict[str, Any], test_user_token: Any) -> None:
        """Test partial tenant update."""
        # Create a tenant
        create_response = test_client.post(
            ENDPOINT_TENANTS,
            json=sample_tenant_data,
            headers=auth_headers
        )
        tenant_id = create_response.json()["id"]
        
        # Update only name
        response = test_client.patch(
            ENDPOINT_TENANT_DETAIL.format(tenant_id=tenant_id),
            json={"name": "Partially Updated"},
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["name"] == "Partially Updated"
        assert data["description"] == sample_tenant_data["description"]
    
    def test_delete_tenant_success(self, test_client: TestClient, auth_headers: dict[str, str], sample_tenant_data: dict[str, Any], test_user_token: Any) -> None:
        """Test successful tenant deletion."""
        # Create a tenant
        create_response = test_client.post(
            ENDPOINT_TENANTS,
            json=sample_tenant_data,
            headers=auth_headers
        )
        tenant_id = create_response.json()["id"]
        
        # Delete the tenant
        response = test_client.request("DELETE", 
            ENDPOINT_TENANT_DETAIL.format(tenant_id=tenant_id),
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_204_NO_CONTENT
        
        # Verify tenant is deleted - returns 403 because user no longer has access
        get_response = test_client.get(
            ENDPOINT_TENANT_DETAIL.format(tenant_id=tenant_id),
            headers=auth_headers
        )
        assert get_response.status_code == status.HTTP_403_FORBIDDEN
    
    def test_delete_tenant_not_found(self, test_client: TestClient, auth_headers: dict[str, str], test_user_token: Any) -> None:
        """Test deleting a non-existent tenant."""
        response = test_client.request("DELETE", 
            ENDPOINT_TENANT_DETAIL.format(tenant_id=NON_EXISTENT_ID),
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_403_FORBIDDEN  # 403 instead of 404 for security


    def test_list_tenant_principals_empty(self, test_client: TestClient, auth_headers: dict[str, str], sample_tenant_data: dict[str, Any], test_user_token: Any) -> None:
        """Test listing principals for a tenant with only the creator."""
        # Create a tenant
        create_response = test_client.post(
            ENDPOINT_TENANTS,
            json=sample_tenant_data,
            headers=auth_headers
        )
        tenant_id = create_response.json()["id"]
        
        # List principals
        response = test_client.get(
            ENDPOINT_TENANT_PRINCIPALS.format(tenant_id=tenant_id),
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert "tenant_id" in data
        assert "principals" in data
        assert len(data["principals"]) >= 1  # At least the creator
        
        # Check creator has GLOBAL_ADMIN role
        creator_principal = next(
            (p for p in data["principals"] if p["principal_id"] == test_user_token.get_id()),
            None
        )
        assert creator_principal is not None
        assert ROLE_GLOBAL_ADMIN in creator_principal["roles"]
    
    def test_get_principal_permissions(self, test_client: TestClient, auth_headers: dict[str, str], sample_tenant_data: dict[str, Any], test_user_token: Any) -> None:
        """Test getting permissions for a specific principal."""
        # Create a tenant
        create_response = test_client.post(
            ENDPOINT_TENANTS,
            json=sample_tenant_data,
            headers=auth_headers
        )
        tenant_id = create_response.json()["id"]
        
        # Get creator's permissions
        response = test_client.get(
            ENDPOINT_PRINCIPAL_DETAIL.format(tenant_id=tenant_id, principal_id="test-user-123"),
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["principal_id"] == test_user_token.get_id()
        assert data["principal_type"] == PRINCIPAL_TYPE_USER
        assert ROLE_GLOBAL_ADMIN in data["roles"]
    
    def test_set_principal_permission_new_user(self, test_client: TestClient, auth_headers: dict[str, str], sample_tenant_data: dict[str, Any]) -> None:
        """Test adding a role for a new principal."""
        # Create a tenant
        create_response = test_client.post(
            ENDPOINT_TENANTS,
            json=sample_tenant_data,
            headers=auth_headers
        )
        tenant_id = create_response.json()["id"]
        
        # Add a new user with READER role
        role_data = {
            "principal_id": "user-456",
            "principal_type": PRINCIPAL_TYPE_USER,
            "role": ROLE_READER
        }
        
        response = test_client.put(
            ENDPOINT_TENANT_PRINCIPALS.format(tenant_id=tenant_id),
            json=role_data,
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["principal_id"] == "user-456"
        assert data["principal_type"] == PRINCIPAL_TYPE_USER
        assert ROLE_READER in data["roles"]
    
    def test_set_principal_permission_add_role(self, test_client: TestClient, auth_headers: dict[str, str], sample_tenant_data: dict[str, Any]) -> None:
        """Test adding an additional role to an existing principal."""
        # Create a tenant
        create_response = test_client.post(
            ENDPOINT_TENANTS,
            json=sample_tenant_data,
            headers=auth_headers
        )
        tenant_id = create_response.json()["id"]
        
        # Add first role
        role_data_1 = {
            "principal_id": "user-789",
            "principal_type": PRINCIPAL_TYPE_USER,
            "role": ROLE_READER
        }
        test_client.put(
            ENDPOINT_TENANT_PRINCIPALS.format(tenant_id=tenant_id),
            json=role_data_1,
            headers=auth_headers
        )
        
        # Add second role
        role_data_2 = {
            "principal_id": "user-789",
            "principal_type": PRINCIPAL_TYPE_USER,
            "role": ROLE_APPLICATIONS_ADMIN
        }
        
        response = test_client.put(
            ENDPOINT_TENANT_PRINCIPALS.format(tenant_id=tenant_id),
            json=role_data_2,
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["principal_id"] == "user-789"
        assert len(data["roles"]) == 2
        assert ROLE_READER in data["roles"]
        assert ROLE_APPLICATIONS_ADMIN in data["roles"]
    
    def test_set_principal_permission_duplicate_role(self, test_client: TestClient, auth_headers: dict[str, str], sample_tenant_data: dict[str, Any]) -> None:
        """Test adding the same role twice (should be idempotent)."""
        # Create a tenant
        create_response = test_client.post(
            ENDPOINT_TENANTS,
            json=sample_tenant_data,
            headers=auth_headers
        )
        tenant_id = create_response.json()["id"]
        
        # Add role first time
        role_data = {
            "principal_id": "user-999",
            "principal_type": PRINCIPAL_TYPE_USER,
            "role": ROLE_READER
        }
        test_client.put(
            ENDPOINT_TENANT_PRINCIPALS.format(tenant_id=tenant_id),
            json=role_data,
            headers=auth_headers
        )
        
        # Add same role again
        response = test_client.put(
            ENDPOINT_TENANT_PRINCIPALS.format(tenant_id=tenant_id),
            json=role_data,
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        # Should still have only one READER role
        assert data["roles"].count(ROLE_READER) == 1
    
    def test_set_principal_permission_invalid_role(self, test_client: TestClient, auth_headers: dict[str, str], sample_tenant_data: dict[str, Any]) -> None:
        """Test that invalid role values return 422 with proper error message."""
        # Create a tenant
        create_response = test_client.post(
            ENDPOINT_TENANTS,
            json=sample_tenant_data,
            headers=auth_headers
        )
        tenant_id = create_response.json()["id"]
        
        # Try to add an invalid role
        role_data = {
            "principal_id": "user-invalid-role",
            "principal_type": PRINCIPAL_TYPE_USER,
            "role": "INVALID_ROLE_XYZ"
        }
        
        response = test_client.put(
            ENDPOINT_TENANT_PRINCIPALS.format(tenant_id=tenant_id),
            json=role_data,
            headers=auth_headers
        )
        
        # Should return 422 Unprocessable Entity, not 500
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        data = response.json()
        
        # Check that error message mentions valid values
        assert "detail" in data
        error_msg = str(data["detail"])
        assert ROLE_READER in error_msg or ROLE_GLOBAL_ADMIN in error_msg
    
    def test_set_principal_permission_invalid_principal_type(self, test_client: TestClient, auth_headers: dict[str, str], sample_tenant_data: dict[str, Any]) -> None:
        """Test that invalid principal_type values return 422 with proper error message."""
        # Create a tenant
        create_response = test_client.post(
            ENDPOINT_TENANTS,
            json=sample_tenant_data,
            headers=auth_headers
        )
        tenant_id = create_response.json()["id"]
        
        # Try to add with invalid principal_type
        role_data = {
            "principal_id": "user-invalid-type",
            "principal_type": "INVALID_TYPE_XYZ",
            "role": ROLE_READER
        }
        
        response = test_client.put(
            ENDPOINT_TENANT_PRINCIPALS.format(tenant_id=tenant_id),
            json=role_data,
            headers=auth_headers
        )
        
        # Should return 422 Unprocessable Entity, not 500
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        data = response.json()
        
        # Check that error message mentions valid values
        assert "detail" in data
        error_msg = str(data["detail"])
        assert PRINCIPAL_TYPE_USER in error_msg or PRINCIPAL_TYPE_GROUP in error_msg
    
    def test_delete_principal_permission_invalid_role(self, test_client: TestClient, auth_headers: dict[str, str], sample_tenant_data: dict[str, Any]) -> None:
        """Test that deleting with invalid role returns 422."""
        # Create a tenant
        create_response = test_client.post(
            ENDPOINT_TENANTS,
            json=sample_tenant_data,
            headers=auth_headers
        )
        tenant_id = create_response.json()["id"]
        
        # Try to delete with invalid role
        delete_data = {
            "principal_id": "user-delete-invalid",
            "principal_type": PRINCIPAL_TYPE_USER,
            "role": "INVALID_ROLE"
        }
        
        response = test_client.request("DELETE", 
            ENDPOINT_TENANT_PRINCIPALS.format(tenant_id=tenant_id),
            json=delete_data,
            headers=auth_headers
        )
        
        # Should return 422 Unprocessable Entity
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    
    def test_delete_principal_permission_invalid_principal_type(self, test_client: TestClient, auth_headers: dict[str, str], sample_tenant_data: dict[str, Any]) -> None:
        """Test that deleting with invalid principal_type returns 422."""
        # Create a tenant
        create_response = test_client.post(
            ENDPOINT_TENANTS,
            json=sample_tenant_data,
            headers=auth_headers
        )
        tenant_id = create_response.json()["id"]
        
        # Try to delete with invalid principal_type
        delete_data = {
            "principal_id": "user-delete-invalid-type",
            "principal_type": "INVALID_TYPE",
            "role": ROLE_READER
        }
        
        response = test_client.request("DELETE", 
            ENDPOINT_TENANT_PRINCIPALS.format(tenant_id=tenant_id),
            json=delete_data,
            headers=auth_headers
        )
        
        # Should return 422 Unprocessable Entity
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    
    def test_delete_principal_permission(self, test_client: TestClient, auth_headers: dict[str, str], sample_tenant_data: dict[str, Any]) -> None:
        """Test removing a role from a principal."""
        # Create a tenant
        create_response = test_client.post(
            ENDPOINT_TENANTS,
            json=sample_tenant_data,
            headers=auth_headers
        )
        tenant_id = create_response.json()["id"]
        
        # Add two roles to a user
        user_id = "user-delete-test"
        test_client.put(
            ENDPOINT_TENANT_PRINCIPALS.format(tenant_id=tenant_id),
            json={"principal_id": user_id, "principal_type": PRINCIPAL_TYPE_USER, "role": ROLE_READER},
            headers=auth_headers
        )
        test_client.put(
            ENDPOINT_TENANT_PRINCIPALS.format(tenant_id=tenant_id),
            json={"principal_id": user_id, "principal_type": PRINCIPAL_TYPE_USER, "role": ROLE_APPLICATIONS_ADMIN},
            headers=auth_headers
        )
        
        # Delete one role
        delete_data = {
            "principal_id": user_id,
            "principal_type": PRINCIPAL_TYPE_USER,
            "role": ROLE_READER
        }
        
        response = test_client.request("DELETE", 
            ENDPOINT_TENANT_PRINCIPALS.format(tenant_id=tenant_id),
            json=delete_data,
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["principal_id"] == user_id
        assert ROLE_READER not in data["roles"]
        assert ROLE_APPLICATIONS_ADMIN in data["roles"]
    
    def test_delete_principal_permission_not_found(self, test_client: TestClient, auth_headers: dict[str, str], sample_tenant_data: dict[str, Any]) -> None:
        """Test removing a non-existent role."""
        # Create a tenant
        create_response = test_client.post(
            ENDPOINT_TENANTS,
            json=sample_tenant_data,
            headers=auth_headers
        )
        tenant_id = create_response.json()["id"]
        
        # Try to delete role that doesn't exist
        delete_data = {
            "principal_id": "non-existent-user",
            "principal_type": PRINCIPAL_TYPE_USER,
            "role": ROLE_READER
        }
        
        response = test_client.request("DELETE", 
            ENDPOINT_TENANT_PRINCIPALS.format(tenant_id=tenant_id),
            json=delete_data,
            headers=auth_headers
        )
        
        # Should return 404 or handle gracefully
        assert response.status_code in [status.HTTP_404_NOT_FOUND, status.HTTP_200_OK]
