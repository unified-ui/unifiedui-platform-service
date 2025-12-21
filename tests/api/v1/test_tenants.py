"""Tests for tenant API endpoints."""
import pytest
import logging
from fastapi import status

# Configure logging for tests
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class TestTenantRoutes:
    """Test suite for tenant API routes."""
    
    def test_create_tenant_success(self, test_client, auth_headers, sample_tenant_data, test_user_token):
        """Test successful tenant creation."""
        logger.info("=" * 80)
        logger.info("TEST: test_create_tenant_success")
        logger.info(f"Auth Headers: {auth_headers}")
        logger.info(f"Sample Tenant Data: {sample_tenant_data}")
        
        response = test_client.post(
            "/api/v1/tenants",
            json=sample_tenant_data,
            headers=auth_headers
        )
        
        logger.info(f"Response Status: {response.status_code}")
        logger.info(f"Response Headers: {dict(response.headers)}")
        logger.info(f"Response Body: {response.text}")
        
        if response.status_code != status.HTTP_201_CREATED:
            logger.error(f"Test failed! Expected 201, got {response.status_code}")
            try:
                logger.error(f"Response JSON: {response.json()}")
            except:
                logger.error(f"Response text: {response.text}")
        
        logger.info("=" * 80)
        
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        
        assert data["name"] == sample_tenant_data["name"]
        assert data["description"] == sample_tenant_data["description"]
        assert "id" in data
        assert "created_at" in data
        assert "updated_at" in data
        assert data["created_by"] == test_user_token.get_id()

    def test_create_tenant_missing_name(self, test_client, auth_headers):
        """Test tenant creation with missing name."""
        response = test_client.post(
            "/api/v1/tenants",
            json={"description": "Test tenant"},
            headers=auth_headers
        )
        
        assert response.status_code == 422
    
    def test_create_tenant_multiple_users(self, test_client, sample_tenant_data):
        """Test that different users can create their own tenants."""
        # Create first user and tenant
        user1_token = test_client.create_test_user("user-1", "User One")
        headers1 = {"Authorization": f"Bearer {user1_token.get_token()}", "X-Use-Cache": "false"}
        
        response1 = test_client.post(
            "/api/v1/tenants",
            json={"name": "Tenant 1", "description": "First tenant"},
            headers=headers1
        )
        
        assert response1.status_code == status.HTTP_201_CREATED
        assert response1.json()["created_by"] == "user-1"
        
        # Create second user and tenant
        user2_token = test_client.create_test_user("user-2", "User Two")
        headers2 = {"Authorization": f"Bearer {user2_token.get_token()}", "X-Use-Cache": "false"}
        
        response2 = test_client.post(
            "/api/v1/tenants",
            json={"name": "Tenant 2", "description": "Second tenant"},
            headers=headers2
        )
        
        assert response2.status_code == status.HTTP_201_CREATED
        assert response2.json()["created_by"] == "user-2"
    
    def test_get_tenant_success(self, test_client, auth_headers, sample_tenant_data):
        """Test successful tenant retrieval."""
        # First create a tenant
        create_response = test_client.post(
            "/api/v1/tenants",
            json=sample_tenant_data,
            headers=auth_headers
        )
        tenant_id = create_response.json()["id"]
        
        # Then retrieve it
        response = test_client.get(
            f"/api/v1/tenants/{tenant_id}",
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["id"] == tenant_id
        assert data["name"] == sample_tenant_data["name"]
        assert data["description"] == sample_tenant_data["description"]
    
    def test_get_tenant_not_found(self, test_client, auth_headers):
        """Test tenant retrieval with non-existent ID."""
        response = test_client.get(
            "/api/v1/tenants/non-existent-id",
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_403_FORBIDDEN  # 403 instead of 404 for security
    
    def test_list_tenants_empty(self, test_client, auth_headers):
        """Test listing tenants when none exist."""
        response = test_client.get(
            "/api/v1/tenants",
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert isinstance(data, list)
        assert len(data) == 0
    
    def test_list_tenants_with_data(self, test_client, auth_headers, sample_tenant_data, test_user_token):
        """Test listing tenants with existing data."""
        # Create multiple tenants
        tenant_data_1 = sample_tenant_data.copy()
        tenant_data_2 = {"name": "Second Tenant", "description": "Another test tenant"}
        
        test_client.post("/api/v1/tenants", json=tenant_data_1, headers=auth_headers)
        test_client.post("/api/v1/tenants", json=tenant_data_2, headers=auth_headers)
        
        # List tenants
        response = test_client.get(
            "/api/v1/tenants",
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert isinstance(data, list)
        assert len(data) == 2
        
        names = [tenant["name"] for tenant in data]
        assert "Test Tenant" in names
        assert "Second Tenant" in names
    
    def test_list_tenants_with_pagination(self, test_client, auth_headers, sample_tenant_data, test_user_token):
        """Test listing tenants with pagination parameters."""
        # Create multiple tenants
        for i in range(5):
            tenant_data = {"name": f"Tenant {i}", "description": f"Test tenant {i}"}
            test_client.post("/api/v1/tenants", json=tenant_data, headers=auth_headers)
        
        # Test with limit
        response = test_client.get(
            "/api/v1/tenants?limit=3",
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 3
        
        # Test with skip
        response = test_client.get(
            "/api/v1/tenants?skip=2&limit=2",
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 2
    
    def test_list_tenants_with_name_filter(self, test_client, auth_headers, test_user_token):
        """Test listing tenants with name filter."""
        # Create tenants with different names
        test_client.post("/api/v1/tenants", json={"name": "Production", "description": "Prod"}, headers=auth_headers)
        test_client.post("/api/v1/tenants", json={"name": "Development", "description": "Dev"}, headers=auth_headers)
        test_client.post("/api/v1/tenants", json={"name": "Staging", "description": "Stage"}, headers=auth_headers)
        
        # Filter by name
        response = test_client.get(
            "/api/v1/tenants?name=Development",
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert len(data) >= 1
        assert any(tenant["name"] == "Development" for tenant in data)
    
    def test_update_tenant_success(self, test_client, auth_headers, sample_tenant_data, sample_update_tenant_data, test_user_token):
        """Test successful tenant update."""
        # Create a tenant
        create_response = test_client.post(
            "/api/v1/tenants",
            json=sample_tenant_data,
            headers=auth_headers
        )
        tenant_id = create_response.json()["id"]
        
        # Update the tenant
        response = test_client.patch(
            f"/api/v1/tenants/{tenant_id}",
            json=sample_update_tenant_data,
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["id"] == tenant_id
        assert data["name"] == sample_update_tenant_data["name"]
        assert data["description"] == sample_update_tenant_data["description"]
        assert data["updated_by"] == test_user_token.get_id()
    
    def test_update_tenant_not_found(self, test_client, auth_headers, sample_update_tenant_data, test_user_token):
        """Test updating a non-existent tenant."""
        response = test_client.patch(
            "/api/v1/tenants/non-existent-id",
            json=sample_update_tenant_data,
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_403_FORBIDDEN  # 403 instead of 404 for security
    
    def test_update_tenant_partial(self, test_client, auth_headers, sample_tenant_data, test_user_token):
        """Test partial tenant update."""
        # Create a tenant
        create_response = test_client.post(
            "/api/v1/tenants",
            json=sample_tenant_data,
            headers=auth_headers
        )
        tenant_id = create_response.json()["id"]
        
        # Update only name
        response = test_client.patch(
            f"/api/v1/tenants/{tenant_id}",
            json={"name": "Partially Updated"},
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["name"] == "Partially Updated"
        assert data["description"] == sample_tenant_data["description"]
    
    def test_delete_tenant_success(self, test_client, auth_headers, sample_tenant_data, test_user_token):
        """Test successful tenant deletion."""
        # Create a tenant
        create_response = test_client.post(
            "/api/v1/tenants",
            json=sample_tenant_data,
            headers=auth_headers
        )
        tenant_id = create_response.json()["id"]
        
        # Delete the tenant
        response = test_client.request("DELETE", 
            f"/api/v1/tenants/{tenant_id}",
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_204_NO_CONTENT
        
        # Verify tenant is deleted - returns 403 because user no longer has access
        get_response = test_client.get(
            f"/api/v1/tenants/{tenant_id}",
            headers=auth_headers
        )
        assert get_response.status_code == status.HTTP_403_FORBIDDEN
    
    def test_delete_tenant_not_found(self, test_client, auth_headers, test_user_token):
        """Test deleting a non-existent tenant."""
        response = test_client.request("DELETE", 
            "/api/v1/tenants/non-existent-id",
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_403_FORBIDDEN  # 403 instead of 404 for security


class TestTenantPrincipalRoutes:
    """Test suite for tenant principal/role management routes."""
    
    def test_list_tenant_principals_empty(self, test_client, auth_headers, sample_tenant_data, test_user_token):
        """Test listing principals for a tenant with only the creator."""
        # Create a tenant
        create_response = test_client.post(
            "/api/v1/tenants",
            json=sample_tenant_data,
            headers=auth_headers
        )
        tenant_id = create_response.json()["id"]
        
        # List principals
        response = test_client.get(
            f"/api/v1/tenants/{tenant_id}/principals",
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
        assert "GLOBAL_ADMIN" in creator_principal["roles"]
    
    def test_get_principal_permissions(self, test_client, auth_headers, sample_tenant_data, test_user_token):
        """Test getting permissions for a specific principal."""
        # Create a tenant
        create_response = test_client.post(
            "/api/v1/tenants",
            json=sample_tenant_data,
            headers=auth_headers
        )
        tenant_id = create_response.json()["id"]
        
        # Get creator's permissions
        response = test_client.get(
            f"/api/v1/tenants/{tenant_id}/principals/test-user-123",
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["principal_id"] == test_user_token.get_id()
        assert data["principal_type"] == "IDENTITY_USER"
        assert "GLOBAL_ADMIN" in data["roles"]
    
    def test_set_principal_permission_new_user(self, test_client, auth_headers, sample_tenant_data):
        """Test adding a role for a new principal."""
        # Create a tenant
        create_response = test_client.post(
            "/api/v1/tenants",
            json=sample_tenant_data,
            headers=auth_headers
        )
        tenant_id = create_response.json()["id"]
        
        # Add a new user with READER role
        role_data = {
            "principal_id": "user-456",
            "principal_type": "IDENTITY_USER",
            "role": "READER"
        }
        
        response = test_client.put(
            f"/api/v1/tenants/{tenant_id}/principals",
            json=role_data,
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["principal_id"] == "user-456"
        assert data["principal_type"] == "IDENTITY_USER"
        assert "READER" in data["roles"]
    
    def test_set_principal_permission_add_role(self, test_client, auth_headers, sample_tenant_data):
        """Test adding an additional role to an existing principal."""
        # Create a tenant
        create_response = test_client.post(
            "/api/v1/tenants",
            json=sample_tenant_data,
            headers=auth_headers
        )
        tenant_id = create_response.json()["id"]
        
        # Add first role
        role_data_1 = {
            "principal_id": "user-789",
            "principal_type": "IDENTITY_USER",
            "role": "READER"
        }
        test_client.put(
            f"/api/v1/tenants/{tenant_id}/principals",
            json=role_data_1,
            headers=auth_headers
        )
        
        # Add second role
        role_data_2 = {
            "principal_id": "user-789",
            "principal_type": "IDENTITY_USER",
            "role": "APPLICATIONS_ADMIN"
        }
        
        response = test_client.put(
            f"/api/v1/tenants/{tenant_id}/principals",
            json=role_data_2,
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["principal_id"] == "user-789"
        assert len(data["roles"]) == 2
        assert "READER" in data["roles"]
        assert "APPLICATIONS_ADMIN" in data["roles"]
    
    def test_set_principal_permission_duplicate_role(self, test_client, auth_headers, sample_tenant_data):
        """Test adding the same role twice (should be idempotent)."""
        # Create a tenant
        create_response = test_client.post(
            "/api/v1/tenants",
            json=sample_tenant_data,
            headers=auth_headers
        )
        tenant_id = create_response.json()["id"]
        
        # Add role first time
        role_data = {
            "principal_id": "user-999",
            "principal_type": "IDENTITY_USER",
            "role": "READER"
        }
        test_client.put(
            f"/api/v1/tenants/{tenant_id}/principals",
            json=role_data,
            headers=auth_headers
        )
        
        # Add same role again
        response = test_client.put(
            f"/api/v1/tenants/{tenant_id}/principals",
            json=role_data,
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        # Should still have only one READER role
        assert data["roles"].count("READER") == 1
    
    def test_set_principal_permission_with_different_users(self, test_client, sample_tenant_data):
        """Test adding roles with multiple different users."""
        # Create admin user and tenant
        admin_token = test_client.create_test_user("admin-user", "Admin User")
        admin_headers = {"Authorization": f"Bearer {admin_token.get_token()}", "X-Use-Cache": "false"}
        
        create_response = test_client.post(
            "/api/v1/tenants",
            json=sample_tenant_data,
            headers=admin_headers
        )
        tenant_id = create_response.json()["id"]
        
        # Create additional test users
        user1_token = test_client.create_test_user("user-001", "User One")
        user2_token = test_client.create_test_user("user-002", "User Two")
        
        # Admin adds user1 with READER role
        response1 = test_client.put(
            f"/api/v1/tenants/{tenant_id}/principals",
            json={"principal_id": "user-001", "principal_type": "IDENTITY_USER", "role": "READER"},
            headers=admin_headers
        )
        assert response1.status_code == status.HTTP_200_OK
        assert "READER" in response1.json()["roles"]
        
        # Admin adds user2 with APPLICATIONS_ADMIN role
        response2 = test_client.put(
            f"/api/v1/tenants/{tenant_id}/principals",
            json={"principal_id": "user-002", "principal_type": "IDENTITY_USER", "role": "APPLICATIONS_ADMIN"},
            headers=admin_headers
        )
        assert response2.status_code == status.HTTP_200_OK
        assert "APPLICATIONS_ADMIN" in response2.json()["roles"]
        
        # List all principals
        list_response = test_client.get(
            f"/api/v1/tenants/{tenant_id}/principals",
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
    
    def test_delete_principal_permission(self, test_client, auth_headers, sample_tenant_data):
        """Test removing a role from a principal."""
        # Create a tenant
        create_response = test_client.post(
            "/api/v1/tenants",
            json=sample_tenant_data,
            headers=auth_headers
        )
        tenant_id = create_response.json()["id"]
        
        # Add two roles to a user
        user_id = "user-delete-test"
        test_client.put(
            f"/api/v1/tenants/{tenant_id}/principals",
            json={"principal_id": user_id, "principal_type": "IDENTITY_USER", "role": "READER"},
            headers=auth_headers
        )
        test_client.put(
            f"/api/v1/tenants/{tenant_id}/principals",
            json={"principal_id": user_id, "principal_type": "IDENTITY_USER", "role": "APPLICATIONS_ADMIN"},
            headers=auth_headers
        )
        
        # Delete one role
        delete_data = {
            "principal_id": user_id,
            "principal_type": "IDENTITY_USER",
            "role": "READER"
        }
        
        response = test_client.request("DELETE", 
            f"/api/v1/tenants/{tenant_id}/principals",
            json=delete_data,
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["principal_id"] == user_id
        assert "READER" not in data["roles"]
        assert "APPLICATIONS_ADMIN" in data["roles"]
    
    def test_delete_principal_permission_not_found(self, test_client, auth_headers, sample_tenant_data, test_user_token):
        """Test removing a non-existent role."""
        # Create a tenant
        create_response = test_client.post(
            "/api/v1/tenants",
            json=sample_tenant_data,
            headers=auth_headers
        )
        tenant_id = create_response.json()["id"]
        
        # Try to delete role that doesn't exist
        delete_data = {
            "principal_id": "non-existent-user",
            "principal_type": "IDENTITY_USER",
            "role": "READER"
        }
        
        response = test_client.request("DELETE", 
            f"/api/v1/tenants/{tenant_id}/principals",
            json=delete_data,
            headers=auth_headers
        )
        
        # Should return 404 or handle gracefully
        assert response.status_code in [status.HTTP_404_NOT_FOUND, status.HTTP_200_OK]
    
    def test_multi_user_access_control(self, test_client, test_user_token):
        """Test that users can only see/manage tenants they have access to."""
        # Create two separate users
        user1_token = test_client.create_test_user("isolated-user-1", "Isolated User One")
        user2_token = test_client.create_test_user("isolated-user-2", "Isolated User Two")
        
        headers1 = {"Authorization": f"Bearer {user1_token.get_token()}", "X-Use-Cache": "false"}
        headers2 = {"Authorization": f"Bearer {user2_token.get_token()}", "X-Use-Cache": "false"}
        
        # User 1 creates a tenant
        tenant1_response = test_client.post(
            "/api/v1/tenants",
            json={"name": "User 1 Tenant", "description": "Private to user 1"},
            headers=headers1
        )
        assert tenant1_response.status_code == status.HTTP_201_CREATED
        tenant1_id = tenant1_response.json()["id"]
        
        # User 2 creates a tenant
        tenant2_response = test_client.post(
            "/api/v1/tenants",
            json={"name": "User 2 Tenant", "description": "Private to user 2"},
            headers=headers2
        )
        assert tenant2_response.status_code == status.HTTP_201_CREATED
        tenant2_id = tenant2_response.json()["id"]
        
        # Each user should be admin of their own tenant
        principals1 = test_client.get(
            f"/api/v1/tenants/{tenant1_id}/principals/isolated-user-1",
            headers=headers1
        )
        assert principals1.status_code == status.HTTP_200_OK
        assert "GLOBAL_ADMIN" in principals1.json()["roles"]
        
        principals2 = test_client.get(
            f"/api/v1/tenants/{tenant2_id}/principals/isolated-user-2",
            headers=headers2
        )
        assert principals2.status_code == status.HTTP_200_OK
        assert "GLOBAL_ADMIN" in principals2.json()["roles"]

    """Test suite for tenant API routes."""
    
    def test_create_tenant_success(self, test_client, auth_headers, sample_tenant_data, test_user_token):
        """Test successful tenant creation."""
        response = test_client.post(
            "/api/v1/tenants",
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
    
    def test_create_tenant_missing_name(self, test_client, auth_headers):
        """Test tenant creation with missing name."""
        response = test_client.post(
            "/api/v1/tenants",
            json={"description": "Test tenant"},
            headers=auth_headers
        )
        
        assert response.status_code == 422
    
    def test_get_tenant_success(self, test_client, auth_headers, sample_tenant_data):
        """Test successful tenant retrieval."""
        # First create a tenant
        create_response = test_client.post(
            "/api/v1/tenants",
            json=sample_tenant_data,
            headers=auth_headers
        )
        tenant_id = create_response.json()["id"]
        
        # Then retrieve it
        response = test_client.get(
            f"/api/v1/tenants/{tenant_id}",
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["id"] == tenant_id
        assert data["name"] == sample_tenant_data["name"]
        assert data["description"] == sample_tenant_data["description"]
    
    def test_get_tenant_not_found(self, test_client, auth_headers):
        """Test tenant retrieval with non-existent ID."""
        response = test_client.get(
            "/api/v1/tenants/non-existent-id",
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_403_FORBIDDEN  # 403 instead of 404 for security
    
    def test_list_tenants_empty(self, test_client, auth_headers):
        """Test listing tenants when none exist."""
        response = test_client.get(
            "/api/v1/tenants",
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert isinstance(data, list)
        assert len(data) == 0
    
    def test_list_tenants_with_data(self, test_client, auth_headers, sample_tenant_data, test_user_token):
        """Test listing tenants with existing data."""
        # Create multiple tenants
        tenant_data_1 = sample_tenant_data.copy()
        tenant_data_2 = {"name": "Second Tenant", "description": "Another test tenant"}
        
        test_client.post("/api/v1/tenants", json=tenant_data_1, headers=auth_headers)
        test_client.post("/api/v1/tenants", json=tenant_data_2, headers=auth_headers)
        
        # List tenants
        response = test_client.get(
            "/api/v1/tenants",
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert isinstance(data, list)
        assert len(data) == 2
        
        names = [tenant["name"] for tenant in data]
        assert "Test Tenant" in names
        assert "Second Tenant" in names
    
    def test_list_tenants_with_pagination(self, test_client, auth_headers, sample_tenant_data, test_user_token):
        """Test listing tenants with pagination parameters."""
        # Create multiple tenants
        for i in range(5):
            tenant_data = {"name": f"Tenant {i}", "description": f"Test tenant {i}"}
            test_client.post("/api/v1/tenants", json=tenant_data, headers=auth_headers)
        
        # Test with limit
        response = test_client.get(
            "/api/v1/tenants?limit=3",
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 3
        
        # Test with skip
        response = test_client.get(
            "/api/v1/tenants?skip=2&limit=2",
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 2
    
    def test_list_tenants_with_name_filter(self, test_client, auth_headers, test_user_token):
        """Test listing tenants with name filter."""
        # Create tenants with different names
        test_client.post("/api/v1/tenants", json={"name": "Production", "description": "Prod"}, headers=auth_headers)
        test_client.post("/api/v1/tenants", json={"name": "Development", "description": "Dev"}, headers=auth_headers)
        test_client.post("/api/v1/tenants", json={"name": "Staging", "description": "Stage"}, headers=auth_headers)
        
        # Filter by name
        response = test_client.get(
            "/api/v1/tenants?name=Development",
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert len(data) >= 1
        assert any(tenant["name"] == "Development" for tenant in data)
    
    def test_update_tenant_success(self, test_client, auth_headers, sample_tenant_data, sample_update_tenant_data, test_user_token):
        """Test successful tenant update."""
        # Create a tenant
        create_response = test_client.post(
            "/api/v1/tenants",
            json=sample_tenant_data,
            headers=auth_headers
        )
        tenant_id = create_response.json()["id"]
        
        # Update the tenant
        response = test_client.patch(
            f"/api/v1/tenants/{tenant_id}",
            json=sample_update_tenant_data,
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["id"] == tenant_id
        assert data["name"] == sample_update_tenant_data["name"]
        assert data["description"] == sample_update_tenant_data["description"]
        assert data["updated_by"] == test_user_token.get_id()
    
    def test_update_tenant_not_found(self, test_client, auth_headers, sample_update_tenant_data, test_user_token):
        """Test updating a non-existent tenant."""
        response = test_client.patch(
            "/api/v1/tenants/non-existent-id",
            json=sample_update_tenant_data,
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_403_FORBIDDEN  # 403 instead of 404 for security
    
    def test_update_tenant_partial(self, test_client, auth_headers, sample_tenant_data, test_user_token):
        """Test partial tenant update."""
        # Create a tenant
        create_response = test_client.post(
            "/api/v1/tenants",
            json=sample_tenant_data,
            headers=auth_headers
        )
        tenant_id = create_response.json()["id"]
        
        # Update only name
        response = test_client.patch(
            f"/api/v1/tenants/{tenant_id}",
            json={"name": "Partially Updated"},
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["name"] == "Partially Updated"
        assert data["description"] == sample_tenant_data["description"]
    
    def test_delete_tenant_success(self, test_client, auth_headers, sample_tenant_data, test_user_token):
        """Test successful tenant deletion."""
        # Create a tenant
        create_response = test_client.post(
            "/api/v1/tenants",
            json=sample_tenant_data,
            headers=auth_headers
        )
        tenant_id = create_response.json()["id"]
        
        # Delete the tenant
        response = test_client.request("DELETE", 
            f"/api/v1/tenants/{tenant_id}",
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_204_NO_CONTENT
        
        # Verify tenant is deleted - returns 403 because user no longer has access
        get_response = test_client.get(
            f"/api/v1/tenants/{tenant_id}",
            headers=auth_headers
        )
        assert get_response.status_code == status.HTTP_403_FORBIDDEN
    
    def test_delete_tenant_not_found(self, test_client, auth_headers, test_user_token):
        """Test deleting a non-existent tenant."""
        response = test_client.request("DELETE", 
            "/api/v1/tenants/non-existent-id",
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_403_FORBIDDEN  # 403 instead of 404 for security


    def test_list_tenant_principals_empty(self, test_client, auth_headers, sample_tenant_data, test_user_token):
        """Test listing principals for a tenant with only the creator."""
        # Create a tenant
        create_response = test_client.post(
            "/api/v1/tenants",
            json=sample_tenant_data,
            headers=auth_headers
        )
        tenant_id = create_response.json()["id"]
        
        # List principals
        response = test_client.get(
            f"/api/v1/tenants/{tenant_id}/principals",
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
        assert "GLOBAL_ADMIN" in creator_principal["roles"]
    
    def test_get_principal_permissions(self, test_client, auth_headers, sample_tenant_data, test_user_token):
        """Test getting permissions for a specific principal."""
        # Create a tenant
        create_response = test_client.post(
            "/api/v1/tenants",
            json=sample_tenant_data,
            headers=auth_headers
        )
        tenant_id = create_response.json()["id"]
        
        # Get creator's permissions
        response = test_client.get(
            f"/api/v1/tenants/{tenant_id}/principals/test-user-123",
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["principal_id"] == test_user_token.get_id()
        assert data["principal_type"] == "IDENTITY_USER"
        assert "GLOBAL_ADMIN" in data["roles"]
    
    def test_set_principal_permission_new_user(self, test_client, auth_headers, sample_tenant_data):
        """Test adding a role for a new principal."""
        # Create a tenant
        create_response = test_client.post(
            "/api/v1/tenants",
            json=sample_tenant_data,
            headers=auth_headers
        )
        tenant_id = create_response.json()["id"]
        
        # Add a new user with READER role
        role_data = {
            "principal_id": "user-456",
            "principal_type": "IDENTITY_USER",
            "role": "READER"
        }
        
        response = test_client.put(
            f"/api/v1/tenants/{tenant_id}/principals",
            json=role_data,
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["principal_id"] == "user-456"
        assert data["principal_type"] == "IDENTITY_USER"
        assert "READER" in data["roles"]
    
    def test_set_principal_permission_add_role(self, test_client, auth_headers, sample_tenant_data):
        """Test adding an additional role to an existing principal."""
        # Create a tenant
        create_response = test_client.post(
            "/api/v1/tenants",
            json=sample_tenant_data,
            headers=auth_headers
        )
        tenant_id = create_response.json()["id"]
        
        # Add first role
        role_data_1 = {
            "principal_id": "user-789",
            "principal_type": "IDENTITY_USER",
            "role": "READER"
        }
        test_client.put(
            f"/api/v1/tenants/{tenant_id}/principals",
            json=role_data_1,
            headers=auth_headers
        )
        
        # Add second role
        role_data_2 = {
            "principal_id": "user-789",
            "principal_type": "IDENTITY_USER",
            "role": "APPLICATIONS_ADMIN"
        }
        
        response = test_client.put(
            f"/api/v1/tenants/{tenant_id}/principals",
            json=role_data_2,
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["principal_id"] == "user-789"
        assert len(data["roles"]) == 2
        assert "READER" in data["roles"]
        assert "APPLICATIONS_ADMIN" in data["roles"]
    
    def test_set_principal_permission_duplicate_role(self, test_client, auth_headers, sample_tenant_data):
        """Test adding the same role twice (should be idempotent)."""
        # Create a tenant
        create_response = test_client.post(
            "/api/v1/tenants",
            json=sample_tenant_data,
            headers=auth_headers
        )
        tenant_id = create_response.json()["id"]
        
        # Add role first time
        role_data = {
            "principal_id": "user-999",
            "principal_type": "IDENTITY_USER",
            "role": "READER"
        }
        test_client.put(
            f"/api/v1/tenants/{tenant_id}/principals",
            json=role_data,
            headers=auth_headers
        )
        
        # Add same role again
        response = test_client.put(
            f"/api/v1/tenants/{tenant_id}/principals",
            json=role_data,
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        # Should still have only one READER role
        assert data["roles"].count("READER") == 1
    
    def test_set_principal_permission_invalid_role(self, test_client, auth_headers, sample_tenant_data):
        """Test that invalid role values return 422 with proper error message."""
        # Create a tenant
        create_response = test_client.post(
            "/api/v1/tenants",
            json=sample_tenant_data,
            headers=auth_headers
        )
        tenant_id = create_response.json()["id"]
        
        # Try to add an invalid role
        role_data = {
            "principal_id": "user-invalid-role",
            "principal_type": "IDENTITY_USER",
            "role": "INVALID_ROLE_XYZ"
        }
        
        response = test_client.put(
            f"/api/v1/tenants/{tenant_id}/principals",
            json=role_data,
            headers=auth_headers
        )
        
        # Should return 422 Unprocessable Entity, not 500
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        data = response.json()
        
        # Check that error message mentions valid values
        assert "detail" in data
        error_msg = str(data["detail"])
        assert "READER" in error_msg or "GLOBAL_ADMIN" in error_msg
    
    def test_set_principal_permission_invalid_principal_type(self, test_client, auth_headers, sample_tenant_data):
        """Test that invalid principal_type values return 422 with proper error message."""
        # Create a tenant
        create_response = test_client.post(
            "/api/v1/tenants",
            json=sample_tenant_data,
            headers=auth_headers
        )
        tenant_id = create_response.json()["id"]
        
        # Try to add with invalid principal_type
        role_data = {
            "principal_id": "user-invalid-type",
            "principal_type": "INVALID_TYPE_XYZ",
            "role": "READER"
        }
        
        response = test_client.put(
            f"/api/v1/tenants/{tenant_id}/principals",
            json=role_data,
            headers=auth_headers
        )
        
        # Should return 422 Unprocessable Entity, not 500
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        data = response.json()
        
        # Check that error message mentions valid values
        assert "detail" in data
        error_msg = str(data["detail"])
        assert "IDENTITY_USER" in error_msg or "IDENTITY_GROUP" in error_msg
    
    def test_delete_principal_permission_invalid_role(self, test_client, auth_headers, sample_tenant_data):
        """Test that deleting with invalid role returns 422."""
        # Create a tenant
        create_response = test_client.post(
            "/api/v1/tenants",
            json=sample_tenant_data,
            headers=auth_headers
        )
        tenant_id = create_response.json()["id"]
        
        # Try to delete with invalid role
        delete_data = {
            "principal_id": "user-delete-invalid",
            "principal_type": "IDENTITY_USER",
            "role": "INVALID_ROLE"
        }
        
        response = test_client.request("DELETE", 
            f"/api/v1/tenants/{tenant_id}/principals",
            json=delete_data,
            headers=auth_headers
        )
        
        # Should return 422 Unprocessable Entity
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    
    def test_delete_principal_permission_invalid_principal_type(self, test_client, auth_headers, sample_tenant_data):
        """Test that deleting with invalid principal_type returns 422."""
        # Create a tenant
        create_response = test_client.post(
            "/api/v1/tenants",
            json=sample_tenant_data,
            headers=auth_headers
        )
        tenant_id = create_response.json()["id"]
        
        # Try to delete with invalid principal_type
        delete_data = {
            "principal_id": "user-delete-invalid-type",
            "principal_type": "INVALID_TYPE",
            "role": "READER"
        }
        
        response = test_client.request("DELETE", 
            f"/api/v1/tenants/{tenant_id}/principals",
            json=delete_data,
            headers=auth_headers
        )
        
        # Should return 422 Unprocessable Entity
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    
    def test_delete_principal_permission(self, test_client, auth_headers, sample_tenant_data):
        """Test removing a role from a principal."""
        # Create a tenant
        create_response = test_client.post(
            "/api/v1/tenants",
            json=sample_tenant_data,
            headers=auth_headers
        )
        tenant_id = create_response.json()["id"]
        
        # Add two roles to a user
        user_id = "user-delete-test"
        test_client.put(
            f"/api/v1/tenants/{tenant_id}/principals",
            json={"principal_id": user_id, "principal_type": "IDENTITY_USER", "role": "READER"},
            headers=auth_headers
        )
        test_client.put(
            f"/api/v1/tenants/{tenant_id}/principals",
            json={"principal_id": user_id, "principal_type": "IDENTITY_USER", "role": "APPLICATIONS_ADMIN"},
            headers=auth_headers
        )
        
        # Delete one role
        delete_data = {
            "principal_id": user_id,
            "principal_type": "IDENTITY_USER",
            "role": "READER"
        }
        
        response = test_client.request("DELETE", 
            f"/api/v1/tenants/{tenant_id}/principals",
            json=delete_data,
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["principal_id"] == user_id
        assert "READER" not in data["roles"]
        assert "APPLICATIONS_ADMIN" in data["roles"]
    
    def test_delete_principal_permission_not_found(self, test_client, auth_headers, sample_tenant_data):
        """Test removing a non-existent role."""
        # Create a tenant
        create_response = test_client.post(
            "/api/v1/tenants",
            json=sample_tenant_data,
            headers=auth_headers
        )
        tenant_id = create_response.json()["id"]
        
        # Try to delete role that doesn't exist
        delete_data = {
            "principal_id": "non-existent-user",
            "principal_type": "IDENTITY_USER",
            "role": "READER"
        }
        
        response = test_client.request("DELETE", 
            f"/api/v1/tenants/{tenant_id}/principals",
            json=delete_data,
            headers=auth_headers
        )
        
        # Should return 404 or handle gracefully
        assert response.status_code in [status.HTTP_404_NOT_FOUND, status.HTTP_200_OK]
