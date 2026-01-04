"""Tests for principals API RBAC (Role-Based Access Control)."""
from typing import Any
from fastapi import status
from starlette.testclient import TestClient

from tests.fixtures.auth import create_auth_headers, create_test_user


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


class TestPrincipalRBAC:
    """Test suite for principal RBAC."""
    
    def test_global_admin_can_update_status(
        self,
        test_client: TestClient,
        auth_headers: dict[str, str],
        sample_tenant_data: dict[str, Any],
        test_user_token: Any
    ) -> None:
        """Test that GLOBAL_ADMIN can update principal status."""
        # Create a tenant (creator is GLOBAL_ADMIN)
        create_response = test_client.post(
            ENDPOINT_TENANTS,
            json=sample_tenant_data,
            headers=auth_headers
        )
        assert create_response.status_code == status.HTTP_201_CREATED
        tenant_id = create_response.json()["id"]
        
        # Update status (should succeed)
        response = test_client.patch(
            ENDPOINT_PRINCIPAL_STATUS.format(
                tenant_id=tenant_id,
                principal_id=test_user_token.get_id()
            ),
            json={"is_active": False},
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK

    def test_reader_cannot_update_status(
        self,
        test_client: TestClient,
        auth_headers: dict[str, str],
        sample_tenant_data: dict[str, Any],
        test_user_token: Any
    ) -> None:
        """Test that READER cannot update principal status."""
        # Create a tenant
        create_response = test_client.post(
            ENDPOINT_TENANTS,
            json=sample_tenant_data,
            headers=auth_headers
        )
        assert create_response.status_code == status.HTTP_201_CREATED
        tenant_id = create_response.json()["id"]
        
        # Create second user with only READER role
        reader_token = create_test_user(
            user_id="reader-user",
            name="Reader User"
        )
        reader_headers = create_auth_headers(reader_token, use_cache=False)
        
        # Add reader user to tenant with READER role
        test_client.put(
            ENDPOINT_TENANT_PRINCIPALS.format(tenant_id=tenant_id),
            json={
                "principal_id": reader_token.get_id(),
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_READER
            },
            headers=auth_headers
        )
        
        # Reader tries to update status (should fail)
        response = test_client.patch(
            ENDPOINT_PRINCIPAL_STATUS.format(
                tenant_id=tenant_id,
                principal_id=test_user_token.get_id()
            ),
            json={"is_active": False},
            headers=reader_headers
        )
        
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_reader_can_get_principal(
        self,
        test_client: TestClient,
        auth_headers: dict[str, str],
        sample_tenant_data: dict[str, Any],
        test_user_token: Any
    ) -> None:
        """Test that READER can get principal details."""
        # Create a tenant
        create_response = test_client.post(
            ENDPOINT_TENANTS,
            json=sample_tenant_data,
            headers=auth_headers
        )
        assert create_response.status_code == status.HTTP_201_CREATED
        tenant_id = create_response.json()["id"]
        
        # Create second user with READER role
        reader_token = create_test_user(
            user_id="reader-user-2",
            name="Reader User 2"
        )
        reader_headers = create_auth_headers(reader_token, use_cache=False)
        
        # Add reader user to tenant with READER role
        test_client.put(
            ENDPOINT_TENANT_PRINCIPALS.format(tenant_id=tenant_id),
            json={
                "principal_id": reader_token.get_id(),
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_READER
            },
            headers=auth_headers
        )
        
        # Reader gets principal details (should succeed)
        response = test_client.get(
            ENDPOINT_PRINCIPAL_DETAIL.format(
                tenant_id=tenant_id,
                principal_id=test_user_token.get_id()
            ),
            headers=reader_headers
        )
        
        assert response.status_code == status.HTTP_200_OK

    def test_global_admin_can_refresh_principal(
        self,
        test_client: TestClient,
        auth_headers: dict[str, str],
        sample_tenant_data: dict[str, Any],
        test_user_token: Any
    ) -> None:
        """Test that GLOBAL_ADMIN can refresh principal from IDP."""
        # Create a tenant
        create_response = test_client.post(
            ENDPOINT_TENANTS,
            json=sample_tenant_data,
            headers=auth_headers
        )
        assert create_response.status_code == status.HTTP_201_CREATED
        tenant_id = create_response.json()["id"]
        
        # Refresh principal (should succeed)
        response = test_client.patch(
            ENDPOINT_PRINCIPAL_REFRESH.format(
                tenant_id=tenant_id,
                principal_id=test_user_token.get_id()
            ),
            json={"principal_type": PRINCIPAL_TYPE_USER},
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK

    def test_reader_cannot_refresh_principal(
        self,
        test_client: TestClient,
        auth_headers: dict[str, str],
        sample_tenant_data: dict[str, Any],
        test_user_token: Any
    ) -> None:
        """Test that READER cannot refresh principal from IDP."""
        # Create a tenant
        create_response = test_client.post(
            ENDPOINT_TENANTS,
            json=sample_tenant_data,
            headers=auth_headers
        )
        assert create_response.status_code == status.HTTP_201_CREATED
        tenant_id = create_response.json()["id"]
        
        # Create second user with only READER role
        reader_token = create_test_user(
            user_id="reader-user-3",
            name="Reader User 3"
        )
        reader_headers = create_auth_headers(reader_token, use_cache=False)
        
        # Add reader user to tenant with READER role
        test_client.put(
            ENDPOINT_TENANT_PRINCIPALS.format(tenant_id=tenant_id),
            json={
                "principal_id": reader_token.get_id(),
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_READER
            },
            headers=auth_headers
        )
        
        # Reader tries to refresh (should fail)
        response = test_client.patch(
            ENDPOINT_PRINCIPAL_REFRESH.format(
                tenant_id=tenant_id,
                principal_id=test_user_token.get_id()
            ),
            json={"principal_type": PRINCIPAL_TYPE_USER},
            headers=reader_headers
        )
        
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_non_member_cannot_access_principals(
        self,
        test_client: TestClient,
        auth_headers: dict[str, str],
        sample_tenant_data: dict[str, Any],
        test_user_token: Any
    ) -> None:
        """Test that non-members cannot access principal endpoints."""
        # Create a tenant
        create_response = test_client.post(
            ENDPOINT_TENANTS,
            json=sample_tenant_data,
            headers=auth_headers
        )
        assert create_response.status_code == status.HTTP_201_CREATED
        tenant_id = create_response.json()["id"]
        
        # Create a user that is NOT a member of the tenant
        outsider_token = create_test_user(
            user_id="outsider-user",
            name="Outsider User"
        )
        outsider_headers = create_auth_headers(outsider_token, use_cache=False)
        
        # Try to get principal (should fail with 403)
        response = test_client.get(
            ENDPOINT_PRINCIPAL_DETAIL.format(
                tenant_id=tenant_id,
                principal_id=test_user_token.get_id()
            ),
            headers=outsider_headers
        )
        
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_unauthenticated_cannot_access_principals(
        self,
        test_client: TestClient,
        auth_headers: dict[str, str],
        sample_tenant_data: dict[str, Any],
        test_user_token: Any
    ) -> None:
        """Test that unauthenticated users cannot access principal endpoints."""
        # Create a tenant
        create_response = test_client.post(
            ENDPOINT_TENANTS,
            json=sample_tenant_data,
            headers=auth_headers
        )
        tenant_id = create_response.json()["id"]
        
        # Try to access without auth headers
        response = test_client.get(
            ENDPOINT_PRINCIPAL_DETAIL.format(
                tenant_id=tenant_id,
                principal_id=test_user_token.get_id()
            )
        )
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
