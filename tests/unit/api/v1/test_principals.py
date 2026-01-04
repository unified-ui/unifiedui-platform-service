"""Tests for principals API endpoints."""
from typing import Any
from fastapi import status
from starlette.testclient import TestClient

from tests.fixtures.auth import create_auth_headers


# Endpoints
ENDPOINT_TENANTS = "/api/v1/platform-service/tenants"
ENDPOINT_TENANT_PRINCIPALS = "/api/v1/platform-service/tenants/{tenant_id}/principals"
ENDPOINT_PRINCIPAL_DETAIL = "/api/v1/platform-service/tenants/{tenant_id}/principals/{principal_id}"
ENDPOINT_PRINCIPAL_REFRESH = "/api/v1/platform-service/tenants/{tenant_id}/principals/{principal_id}/refresh"
ENDPOINT_PRINCIPAL_STATUS = "/api/v1/platform-service/tenants/{tenant_id}/principals/{principal_id}/status"

# Constants
ROLE_GLOBAL_ADMIN = "GLOBAL_ADMIN"
ROLE_READER = "READER"
PRINCIPAL_TYPE_USER = "IDENTITY_USER"
PRINCIPAL_TYPE_GROUP = "IDENTITY_GROUP"
NON_EXISTENT_ID = "non-existent-id"


class TestPrincipalStatusRoutes:
    """Test suite for principal status update endpoint."""
    
    def test_update_principal_status_deactivate(
        self,
        test_client: TestClient,
        auth_headers: dict[str, str],
        sample_tenant_data: dict[str, Any],
        test_user_token: Any
    ) -> None:
        """Test deactivating a principal."""
        # Create a tenant (this also creates the principal)
        create_response = test_client.post(
            ENDPOINT_TENANTS,
            json=sample_tenant_data,
            headers=auth_headers
        )
        assert create_response.status_code == status.HTTP_201_CREATED
        tenant_id = create_response.json()["id"]
        
        # Update principal status to inactive
        response = test_client.patch(
            ENDPOINT_PRINCIPAL_STATUS.format(
                tenant_id=tenant_id,
                principal_id=test_user_token.get_id()
            ),
            json={"is_active": False},
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["principal_id"] == test_user_token.get_id()
        assert data["is_active"] is False

    def test_update_principal_status_activate(
        self,
        test_client: TestClient,
        auth_headers: dict[str, str],
        sample_tenant_data: dict[str, Any],
        test_user_token: Any
    ) -> None:
        """Test activating a previously deactivated principal."""
        # Create a tenant
        create_response = test_client.post(
            ENDPOINT_TENANTS,
            json=sample_tenant_data,
            headers=auth_headers
        )
        assert create_response.status_code == status.HTTP_201_CREATED
        tenant_id = create_response.json()["id"]
        
        # First deactivate
        test_client.patch(
            ENDPOINT_PRINCIPAL_STATUS.format(
                tenant_id=tenant_id,
                principal_id=test_user_token.get_id()
            ),
            json={"is_active": False},
            headers=auth_headers
        )
        
        # Then reactivate
        response = test_client.patch(
            ENDPOINT_PRINCIPAL_STATUS.format(
                tenant_id=tenant_id,
                principal_id=test_user_token.get_id()
            ),
            json={"is_active": True},
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["is_active"] is True

    def test_update_principal_status_missing_body(
        self,
        test_client: TestClient,
        auth_headers: dict[str, str],
        sample_tenant_data: dict[str, Any],
        test_user_token: Any
    ) -> None:
        """Test that missing request body returns validation error."""
        # Create a tenant
        create_response = test_client.post(
            ENDPOINT_TENANTS,
            json=sample_tenant_data,
            headers=auth_headers
        )
        tenant_id = create_response.json()["id"]
        
        # Try to update without body
        response = test_client.patch(
            ENDPOINT_PRINCIPAL_STATUS.format(
                tenant_id=tenant_id,
                principal_id=test_user_token.get_id()
            ),
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


class TestPrincipalRefreshRoutes:
    """Test suite for principal refresh endpoint."""
    
    def test_refresh_principal_success(
        self,
        test_client: TestClient,
        auth_headers: dict[str, str],
        sample_tenant_data: dict[str, Any],
        test_user_token: Any
    ) -> None:
        """Test refreshing a principal from identity provider."""
        # Create a tenant
        create_response = test_client.post(
            ENDPOINT_TENANTS,
            json=sample_tenant_data,
            headers=auth_headers
        )
        assert create_response.status_code == status.HTTP_201_CREATED
        tenant_id = create_response.json()["id"]
        
        # Refresh the principal
        response = test_client.patch(
            ENDPOINT_PRINCIPAL_REFRESH.format(
                tenant_id=tenant_id,
                principal_id=test_user_token.get_id()
            ),
            json={"principal_type": PRINCIPAL_TYPE_USER},
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["principal_id"] == test_user_token.get_id()
        assert data["principal_type"] == PRINCIPAL_TYPE_USER
        assert "display_name" in data
        assert "is_active" in data

    def test_refresh_principal_missing_type(
        self,
        test_client: TestClient,
        auth_headers: dict[str, str],
        sample_tenant_data: dict[str, Any],
        test_user_token: Any
    ) -> None:
        """Test that missing principal_type returns validation error."""
        # Create a tenant
        create_response = test_client.post(
            ENDPOINT_TENANTS,
            json=sample_tenant_data,
            headers=auth_headers
        )
        tenant_id = create_response.json()["id"]
        
        # Try to refresh without type
        response = test_client.patch(
            ENDPOINT_PRINCIPAL_REFRESH.format(
                tenant_id=tenant_id,
                principal_id=test_user_token.get_id()
            ),
            json={},
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


class TestGetPrincipalRoutes:
    """Test suite for get principal endpoint."""
    
    def test_get_principal_success(
        self,
        test_client: TestClient,
        auth_headers: dict[str, str],
        sample_tenant_data: dict[str, Any],
        test_user_token: Any
    ) -> None:
        """Test getting a principal's details."""
        # Create a tenant (this also creates the principal)
        create_response = test_client.post(
            ENDPOINT_TENANTS,
            json=sample_tenant_data,
            headers=auth_headers
        )
        assert create_response.status_code == status.HTTP_201_CREATED
        tenant_id = create_response.json()["id"]
        
        # Get the principal
        response = test_client.get(
            ENDPOINT_PRINCIPAL_DETAIL.format(
                tenant_id=tenant_id,
                principal_id=test_user_token.get_id()
            ),
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["principal_id"] == test_user_token.get_id()
        assert data["principal_type"] == PRINCIPAL_TYPE_USER
        assert "is_active" in data
        assert data["is_active"] is True  # Default is active

    def test_get_principal_not_found(
        self,
        test_client: TestClient,
        auth_headers: dict[str, str],
        sample_tenant_data: dict[str, Any]
    ) -> None:
        """Test getting a non-existent principal returns 200 with empty roles."""
        # Create a tenant
        create_response = test_client.post(
            ENDPOINT_TENANTS,
            json=sample_tenant_data,
            headers=auth_headers
        )
        tenant_id = create_response.json()["id"]
        
        # Get non-existent principal - returns 200 with empty roles
        response = test_client.get(
            ENDPOINT_PRINCIPAL_DETAIL.format(
                tenant_id=tenant_id,
                principal_id=NON_EXISTENT_ID
            ),
            headers=auth_headers
        )
        
        # The existing endpoint returns 200 with empty roles for non-existent principals
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["roles"] == []
        assert data["principal_type"] is None
