"""Tests for tenant API routes."""
import pytest
from unittest.mock import MagicMock, patch
from fastapi import status

from aihub.core.database.models.tenants import TenantModel
from aihub.schema.responses.tenants import TenantResponse
from aihub.exc.tenants import TenantNotFoundError


class TestTenantRoutes:
    """Test suite for tenant API endpoints."""
    
    def test_list_tenants_success(self, test_client, auth_headers, mock_identity_user):
        """Test successful tenant listing."""
        # Mock tenants
        mock_tenant = TenantModel(
            id="tenant-123",
            name="Test Tenant",
            description="Test Description",
            meta={},
            created_by="user-123",
            updated_by="user-123"
        )
        
        test_client.mock_db.tenants.get_list.return_value = [mock_tenant]
        
        # Mock user tenants for permission check
        tenant_response = TenantResponse(
            id="tenant-123",
            name="Test Tenant",
            description="Test Description",
            meta={},
            created_at="2024-01-01T00:00:00",
            updated_at="2024-01-01T00:00:00",
            created_by="user-123",
            updated_by="user-123"
        )
        mock_identity_user.tenants = [tenant_response]
        
        with patch("aihub.core.middleware.apis.v1.auth.IdentityUser", return_value=mock_identity_user):
            response = test_client.get("/api/v1/tenants", headers=auth_headers)
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, list)
    
    def test_list_tenants_with_pagination(self, test_client, auth_headers, mock_identity_user):
        """Test tenant listing with pagination parameters."""
        test_client.mock_db.tenants.get_list.return_value = []
        mock_identity_user.tenants = []
        
        with patch("aihub.core.middleware.apis.v1.auth.IdentityUser", return_value=mock_identity_user):
            response = test_client.get(
                "/api/v1/tenants?skip=10&limit=50",
                headers=auth_headers
            )
        
        assert response.status_code == status.HTTP_200_OK
        test_client.mock_db.tenants.get_list.assert_called_once()
    
    def test_list_tenants_with_name_filter(self, test_client, auth_headers, mock_identity_user):
        """Test tenant listing with name filter."""
        test_client.mock_db.tenants.get_list.return_value = []
        mock_identity_user.tenants = []
        
        with patch("aihub.core.middleware.apis.v1.auth.IdentityUser", return_value=mock_identity_user):
            response = test_client.get(
                "/api/v1/tenants?name=test",
                headers=auth_headers
            )
        
        assert response.status_code == status.HTTP_200_OK
    
    def test_list_tenants_unauthorized(self, test_client):
        """Test tenant listing without authentication."""
        response = test_client.get("/api/v1/tenants")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    def test_get_tenant_success(self, test_client, auth_headers, mock_identity_user):
        """Test successful tenant retrieval."""
        tenant_id = "tenant-123"
        
        mock_tenant = TenantModel(
            id=tenant_id,
            name="Test Tenant",
            description="Test Description",
            meta={},
            created_by="user-123",
            updated_by="user-123"
        )
        
        test_client.mock_db.tenants.get.return_value = mock_tenant
        
        # Mock user has access
        tenant_response = TenantResponse(
            id=tenant_id,
            name="Test Tenant",
            description="Test Description",
            meta={},
            created_at="2024-01-01T00:00:00",
            updated_at="2024-01-01T00:00:00",
            created_by="user-123",
            updated_by="user-123"
        )
        mock_identity_user.tenants = [tenant_response]
        
        with patch("aihub.core.middleware.apis.v1.auth.IdentityUser", return_value=mock_identity_user):
            response = test_client.get(f"/api/v1/tenants/{tenant_id}", headers=auth_headers)
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["id"] == tenant_id
        assert data["name"] == "Test Tenant"
    
    def test_get_tenant_not_found(self, test_client, auth_headers, mock_identity_user):
        """Test tenant retrieval when tenant doesn't exist."""
        tenant_id = "nonexistent"
        
        tenant_response = TenantResponse(
            id=tenant_id,
            name="Test",
            description="Test",
            meta={},
            created_at="2024-01-01T00:00:00",
            updated_at="2024-01-01T00:00:00",
            created_by="user-123",
            updated_by="user-123"
        )
        mock_identity_user.tenants = [tenant_response]
        
        test_client.mock_db.tenants.get.return_value = None
        
        with patch("aihub.core.middleware.apis.v1.auth.IdentityUser", return_value=mock_identity_user):
            response = test_client.get(f"/api/v1/tenants/{tenant_id}", headers=auth_headers)
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
    
    def test_get_tenant_permission_denied(self, test_client, auth_headers, mock_identity_user):
        """Test tenant retrieval without permission."""
        tenant_id = "tenant-123"
        
        # User doesn't have access to this tenant
        mock_identity_user.tenants = []
        
        with patch("aihub.core.middleware.apis.v1.auth.IdentityUser", return_value=mock_identity_user):
            response = test_client.get(f"/api/v1/tenants/{tenant_id}", headers=auth_headers)
        
        assert response.status_code == status.HTTP_403_FORBIDDEN
    
    def test_create_tenant_success(self, test_client, auth_headers, sample_tenant_data, mock_identity_user):
        """Test successful tenant creation."""
        created_tenant = TenantModel(
            id="new-tenant-123",
            name=sample_tenant_data["name"],
            description=sample_tenant_data["description"],
            meta=sample_tenant_data["meta"],
            created_by="test-user-123",
            updated_by="test-user-123"
        )
        
        test_client.mock_db.tenants.create.return_value = created_tenant
        test_client.mock_db.permissions.create_many.return_value = []
        
        with patch("aihub.core.middleware.apis.v1.auth.IdentityUser", return_value=mock_identity_user):
            response = test_client.post(
                "/api/v1/tenants",
                json=sample_tenant_data,
                headers=auth_headers
            )
        
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["name"] == sample_tenant_data["name"]
        test_client.mock_db.tenants.create.assert_called_once()
    
    def test_create_tenant_invalid_data(self, test_client, auth_headers, mock_identity_user):
        """Test tenant creation with invalid data."""
        invalid_data = {"description": "Missing name field"}
        
        with patch("aihub.core.middleware.apis.v1.auth.IdentityUser", return_value=mock_identity_user):
            response = test_client.post(
                "/api/v1/tenants",
                json=invalid_data,
                headers=auth_headers
            )
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    
    def test_update_tenant_success(self, test_client, auth_headers, mock_identity_user):
        """Test successful tenant update."""
        tenant_id = "tenant-123"
        update_data = {"name": "Updated Tenant"}
        
        updated_tenant = TenantModel(
            id=tenant_id,
            name="Updated Tenant",
            description="Description",
            meta={},
            created_by="user-123",
            updated_by="test-user-123"
        )
        
        test_client.mock_db.tenants.update.return_value = updated_tenant
        test_client.mock_db.permissions.check_permission.return_value = True
        
        with patch("aihub.core.middleware.apis.v1.auth.IdentityUser", return_value=mock_identity_user):
            response = test_client.patch(
                f"/api/v1/tenants/{tenant_id}",
                json=update_data,
                headers=auth_headers
            )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["name"] == "Updated Tenant"
    
    def test_update_tenant_permission_denied(self, test_client, auth_headers, mock_identity_user):
        """Test tenant update without write permission."""
        tenant_id = "tenant-123"
        update_data = {"name": "Updated Tenant"}
        
        test_client.mock_db.permissions.check_permission.return_value = False
        
        with patch("aihub.core.middleware.apis.v1.auth.IdentityUser", return_value=mock_identity_user):
            response = test_client.patch(
                f"/api/v1/tenants/{tenant_id}",
                json=update_data,
                headers=auth_headers
            )
        
        assert response.status_code == status.HTTP_403_FORBIDDEN
    
    def test_delete_tenant_success(self, test_client, auth_headers, mock_identity_user):
        """Test successful tenant deletion."""
        tenant_id = "tenant-123"
        
        test_client.mock_db.tenants.delete.return_value = True
        test_client.mock_db.permissions.check_permission.return_value = True
        
        with patch("aihub.core.middleware.apis.v1.auth.IdentityUser", return_value=mock_identity_user):
            response = test_client.delete(
                f"/api/v1/tenants/{tenant_id}",
                headers=auth_headers
            )
        
        assert response.status_code == status.HTTP_204_NO_CONTENT
        test_client.mock_db.tenants.delete.assert_called_once_with(tenant_id)
    
    def test_delete_tenant_permission_denied(self, test_client, auth_headers, mock_identity_user):
        """Test tenant deletion without admin permission."""
        tenant_id = "tenant-123"
        
        test_client.mock_db.permissions.check_permission.return_value = False
        
        with patch("aihub.core.middleware.apis.v1.auth.IdentityUser", return_value=mock_identity_user):
            response = test_client.delete(
                f"/api/v1/tenants/{tenant_id}",
                headers=auth_headers
            )
        
        assert response.status_code == status.HTTP_403_FORBIDDEN
