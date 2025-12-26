"""Tests for credentials API endpoints."""
from typing import Any
from fastapi import status
from starlette.testclient import TestClient

from unifiedui.core.database.enums import PermissionActionEnum, PrincipalTypeEnum
from tests.conftest import create_auth_headers


# API Endpoints
ENDPOINT_CREDENTIALS = "/api/v1/tenants/{tenant_id}/credentials"
ENDPOINT_CREDENTIAL_DETAIL = "/api/v1/tenants/{tenant_id}/credentials/{credential_id}"
ENDPOINT_CREDENTIAL_PRINCIPALS = "/api/v1/tenants/{tenant_id}/credentials/{credential_id}/principals"
ENDPOINT_PRINCIPAL_DETAIL = "/api/v1/tenants/{tenant_id}/credentials/{credential_id}/principals/{principal_id}"

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
        "/api/v1/tenants",
        json={"name": tenant_name, "description": f"Tenant for {user_token.get_id()}"},
        headers=headers
    )
    assert response.status_code == status.HTTP_201_CREATED
    return response.json()["id"]


class TestCredentialRoutes:
    """Test suite for credential API routes."""
    
    def test_create_credential_success(
        self, 
        test_client: TestClient, 
        test_user_token: Any
    ) -> None:
        """Test successful credential creation."""
        # Create a tenant first
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        # Create credential
        credential_data = {
            "name": "Test API Key",
            "description": "A test API key",
            "credential_type": "API_KEY",
            "secret_value": "super-secret-key-123",
            "source": "manual"
        }
        
        response = test_client.post(
            ENDPOINT_CREDENTIALS.format(tenant_id=tenant_id),
            json=credential_data,
            headers=headers
        )

        if response.status_code != status.HTTP_201_CREATED:
            print(f"Response status: {response.status_code}")
            print(f"Response body: {response.json()}")
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        
        assert data["name"] == credential_data["name"]
        assert data["description"] == credential_data["description"]
        assert data["type"] == credential_data["credential_type"]
        assert "id" in data
        assert data["tenant_id"] == tenant_id
        assert "created_at" in data
        assert "updated_at" in data
        assert data["created_by"] == test_user_token.get_id()
        # Secret value should NOT be in response
        assert "secret_value" not in data
        assert "credential_uri" in data
    
    def test_create_credential_missing_name(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test credential creation with missing name."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        response = test_client.post(
            ENDPOINT_CREDENTIALS.format(tenant_id=tenant_id),
            json={
                "description": "Test credential",
                "credential_type": "API_KEY",
                "secret_value": "secret"
            },
            headers=headers
        )
        
        assert response.status_code == 422
    
    def test_create_credential_invalid_name_type(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test credential creation with invalid name type."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        response = test_client.post(
            ENDPOINT_CREDENTIALS.format(tenant_id=tenant_id),
            json={
                "name": 123,
                "credential_type": "API_KEY",
                "secret_value": "secret"
            },
            headers=headers
        )
        
        assert response.status_code == 422
    
    def test_create_credential_empty_name(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test credential creation with empty name."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        response = test_client.post(
            ENDPOINT_CREDENTIALS.format(tenant_id=tenant_id),
            json={
                "name": "",
                "credential_type": "API_KEY",
                "secret_value": "secret"
            },
            headers=headers
        )
        
        assert response.status_code == 422
    
    def test_create_credential_missing_secret_value(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test credential creation with missing secret value."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        response = test_client.post(
            ENDPOINT_CREDENTIALS.format(tenant_id=tenant_id),
            json={
                "name": "Test Credential",
                "credential_type": "API_KEY"
            },
            headers=headers
        )
        
        assert response.status_code == 422
    
    def test_create_credential_empty_body(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test credential creation with empty JSON body."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        response = test_client.post(
            ENDPOINT_CREDENTIALS.format(tenant_id=tenant_id),
            json={},
            headers=headers
        )
        
        assert response.status_code == 422
    
    def test_create_credential_without_permission(self, test_client: TestClient) -> None:
        """Test that user without tenant membership cannot create credentials."""
        # Create user1 with a tenant
        user1_token = test_client.create_test_user("user-1", "User One")
        tenant_id = create_tenant_for_user(test_client, user1_token)
        
        # Create user2 (not a member of the tenant)
        user2_token = test_client.create_test_user("user-2", "User Two")
        headers2 = create_auth_headers(user2_token, use_cache=False)
        
        # Try to create credential as user2 (should fail - no tenant membership)
        response = test_client.post(
            ENDPOINT_CREDENTIALS.format(tenant_id=tenant_id),
            json={
                "name": "Unauthorized Credential",
                "credential_type": "API_KEY",
                "secret_value": "secret"
            },
            headers=headers2
        )
        
        assert response.status_code == status.HTTP_403_FORBIDDEN
    
    def test_get_credential_success(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test successful credential retrieval."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        # Create a credential
        credential_data = {
            "name": "Test Credential",
            "description": "Test description",
            "credential_type": "API_KEY",
            "secret_value": "my-secret-key"
        }
        create_response = test_client.post(
            ENDPOINT_CREDENTIALS.format(tenant_id=tenant_id),
            json=credential_data,
            headers=headers
        )
        credential_id = create_response.json()["id"]
        
        # Retrieve the credential
        response = test_client.get(
            ENDPOINT_CREDENTIAL_DETAIL.format(tenant_id=tenant_id, credential_id=credential_id),
            headers=headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["id"] == credential_id
        assert data["name"] == credential_data["name"]
        assert data["description"] == credential_data["description"]
        assert "secret_value" not in data  # Secret should not be exposed
    
    def test_get_credential_not_found(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test credential retrieval with non-existent ID."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        response = test_client.get(
            ENDPOINT_CREDENTIAL_DETAIL.format(tenant_id=tenant_id, credential_id=NON_EXISTENT_ID),
            headers=headers
        )
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
    
    def test_list_credentials_empty(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test listing credentials when none exist."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        response = test_client.get(
            ENDPOINT_CREDENTIALS.format(tenant_id=tenant_id),
            headers=headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert isinstance(data, list)
        assert len(data) == 0
    
    def test_list_credentials_with_data(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test listing credentials with existing data."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        # Create multiple credentials
        cred1_data = {
            "name": "Credential 1",
            "credential_type": "API_KEY",
            "secret_value": "secret1"
        }
        cred2_data = {
            "name": "Credential 2",
            "credential_type": "PASSWORD",
            "secret_value": "secret2"
        }
        
        test_client.post(
            ENDPOINT_CREDENTIALS.format(tenant_id=tenant_id),
            json=cred1_data,
            headers=headers
        )
        test_client.post(
            ENDPOINT_CREDENTIALS.format(tenant_id=tenant_id),
            json=cred2_data,
            headers=headers
        )
        
        # List credentials
        response = test_client.get(
            ENDPOINT_CREDENTIALS.format(tenant_id=tenant_id),
            headers=headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert isinstance(data, list)
        assert len(data) == 2
        
        names = [cred["name"] for cred in data]
        assert "Credential 1" in names
        assert "Credential 2" in names
    
    def test_list_credentials_with_pagination(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test listing credentials with pagination parameters."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        # Create multiple credentials
        for i in range(5):
            test_client.post(
                ENDPOINT_CREDENTIALS.format(tenant_id=tenant_id),
                json={
                    "name": f"Credential {i}",
                    "credential_type": "API_KEY",
                    "secret_value": f"secret{i}"
                },
                headers=headers
            )
        
        # Test with limit
        response = test_client.get(
            f"{ENDPOINT_CREDENTIALS.format(tenant_id=tenant_id)}?limit=3",
            headers=headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 3
        
        # Test with skip
        response = test_client.get(
            f"{ENDPOINT_CREDENTIALS.format(tenant_id=tenant_id)}?skip=2&limit=2",
            headers=headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 2
    
    def test_list_credentials_with_name_filter(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test listing credentials with name filter."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        # Create credentials with different names
        test_client.post(
            ENDPOINT_CREDENTIALS.format(tenant_id=tenant_id),
            json={
                "name": "Production API Key",
                "credential_type": "API_KEY",
                "secret_value": "prod-secret"
            },
            headers=headers
        )
        test_client.post(
            ENDPOINT_CREDENTIALS.format(tenant_id=tenant_id),
            json={
                "name": "Development Token",
                "credential_type": "TOKEN",
                "secret_value": "dev-secret"
            },
            headers=headers
        )
        test_client.post(
            ENDPOINT_CREDENTIALS.format(tenant_id=tenant_id),
            json={
                "name": "QA Password",
                "credential_type": "PASSWORD",
                "secret_value": "qa-secret"
            },
            headers=headers
        )
        
        # Filter by name
        response = test_client.get(
            f"{ENDPOINT_CREDENTIALS.format(tenant_id=tenant_id)}?name_filter=Development",
            headers=headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert len(data) >= 1
        assert any(cred["name"] == "Development Token" for cred in data)
    
    def test_list_credentials_with_quick_list_view(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test listing credentials with quick-list view returns only id and name."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        # Create credentials
        test_client.post(
            ENDPOINT_CREDENTIALS.format(tenant_id=tenant_id),
            json={
                "name": "API Key One",
                "description": "First credential",
                "credential_type": "API_KEY",
                "secret_value": "secret-1"
            },
            headers=headers
        )
        test_client.post(
            ENDPOINT_CREDENTIALS.format(tenant_id=tenant_id),
            json={
                "name": "Token Two",
                "description": "Second credential",
                "credential_type": "TOKEN",
                "secret_value": "secret-2"
            },
            headers=headers
        )
        
        # Get with quick-list view
        response = test_client.get(
            f"{ENDPOINT_CREDENTIALS.format(tenant_id=tenant_id)}?view=quick-list",
            headers=headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 2
        
        # Verify only id and name are returned
        for item in data:
            assert "id" in item
            assert "name" in item
            # These fields should NOT be present in quick-list view
            assert "description" not in item
            assert "credential_type" not in item
            assert "tenant_id" not in item
            assert "created_at" not in item
            assert "updated_at" not in item
            assert "created_by" not in item
            assert "updated_by" not in item
            assert "is_active" not in item
    
    def test_update_credential_success(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test successful credential update."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        # Create a credential
        create_response = test_client.post(
            ENDPOINT_CREDENTIALS.format(tenant_id=tenant_id),
            json={
                "name": "Original Name",
                "description": "Original description",
                "credential_type": "API_KEY",
                "secret_value": "original-secret"
            },
            headers=headers
        )
        credential_id = create_response.json()["id"]
        
        # Update the credential
        update_response = test_client.patch(
            ENDPOINT_CREDENTIAL_DETAIL.format(tenant_id=tenant_id, credential_id=credential_id),
            json={
                "name": "Updated Name",
                "description": "Updated description"
            },
            headers=headers
        )
        
        assert update_response.status_code == status.HTTP_200_OK
        data = update_response.json()
        
        assert data["name"] == "Updated Name"
        assert data["description"] == "Updated description"
        assert data["id"] == credential_id
    
    def test_update_credential_not_found(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test credential update with non-existent ID."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        response = test_client.patch(
            ENDPOINT_CREDENTIAL_DETAIL.format(tenant_id=tenant_id, credential_id=NON_EXISTENT_ID),
            json={"name": "New Name"},
            headers=headers
        )
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
    
    def test_update_credential_partial(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test partial credential update."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        # Create credential
        create_response = test_client.post(
            ENDPOINT_CREDENTIALS.format(tenant_id=tenant_id),
            json={
                "name": "Original",
                "description": "Original Desc",
                "credential_type": "API_KEY",
                "secret_value": "secret"
            },
            headers=headers
        )
        credential_id = create_response.json()["id"]
        original_name = create_response.json()["name"]
        
        # Update only description
        update_response = test_client.patch(
            ENDPOINT_CREDENTIAL_DETAIL.format(tenant_id=tenant_id, credential_id=credential_id),
            json={"description": "New Description Only"},
            headers=headers
        )
        
        assert update_response.status_code == status.HTTP_200_OK
        data = update_response.json()
        
        assert data["name"] == original_name  # Name unchanged
        assert data["description"] == "New Description Only"
    
    def test_delete_credential_success(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test successful credential deletion."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        # Create credential
        create_response = test_client.post(
            ENDPOINT_CREDENTIALS.format(tenant_id=tenant_id),
            json={
                "name": "To Delete",
                "credential_type": "API_KEY",
                "secret_value": "secret"
            },
            headers=headers
        )
        credential_id = create_response.json()["id"]
        
        # Delete credential
        delete_response = test_client.request(
            "DELETE",
            ENDPOINT_CREDENTIAL_DETAIL.format(tenant_id=tenant_id, credential_id=credential_id),
            headers=headers
        )
        
        assert delete_response.status_code == status.HTTP_204_NO_CONTENT
        
        # Verify deletion
        get_response = test_client.get(
            ENDPOINT_CREDENTIAL_DETAIL.format(tenant_id=tenant_id, credential_id=credential_id),
            headers=headers
        )
        assert get_response.status_code == status.HTTP_404_NOT_FOUND
    
    def test_delete_credential_not_found(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test credential deletion with non-existent ID."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        response = test_client.request(
            "DELETE",
            ENDPOINT_CREDENTIAL_DETAIL.format(tenant_id=tenant_id, credential_id=NON_EXISTENT_ID),
            headers=headers
        )
        
        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestCredentialPrincipalRoutes:
    """Test suite for credential principal/permission management routes."""
    
    def test_list_credential_principals_creator_only(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test listing principals when only creator exists."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        # Create credential
        create_response = test_client.post(
            ENDPOINT_CREDENTIALS.format(tenant_id=tenant_id),
            json={
                "name": "Test Credential",
                "credential_type": "API_KEY",
                "secret_value": "secret"
            },
            headers=headers
        )
        credential_id = create_response.json()["id"]
        
        # List principals
        response = test_client.get(
            ENDPOINT_CREDENTIAL_PRINCIPALS.format(tenant_id=tenant_id, credential_id=credential_id),
            headers=headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert "principals" in data
        assert len(data["principals"]) == 1
        assert data["principals"][0]["principal_id"] == test_user_token.get_id()
        assert ROLE_ADMIN in data["principals"][0]["roles"]  # Changed from "role" to "roles"
    
    def test_get_principal_permissions(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test getting specific principal permissions."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        # Create credential
        create_response = test_client.post(
            ENDPOINT_CREDENTIALS.format(tenant_id=tenant_id),
            json={
                "name": "Test Credential",
                "credential_type": "API_KEY",
                "secret_value": "secret"
            },
            headers=headers
        )
        credential_id = create_response.json()["id"]
        
        # Get creator's permissions
        response = test_client.get(
            ENDPOINT_PRINCIPAL_DETAIL.format(
                tenant_id=tenant_id,
                credential_id=credential_id,
                principal_id=test_user_token.get_id()
            ),
            headers=headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["principal_id"] == test_user_token.get_id()
        assert ROLE_ADMIN in data["roles"]
    
    def test_set_principal_permission_new_user(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test adding permission for a new principal."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        # Create credential
        create_response = test_client.post(
            ENDPOINT_CREDENTIALS.format(tenant_id=tenant_id),
            json={
                "name": "Test Credential",
                "credential_type": "API_KEY",
                "secret_value": "secret"
            },
            headers=headers
        )
        credential_id = create_response.json()["id"]
        
        # Add READ permission for another user
        response = test_client.put(
            ENDPOINT_CREDENTIAL_PRINCIPALS.format(tenant_id=tenant_id, credential_id=credential_id),
            json={
                "principal_id": "other-user",
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_READ
            },
            headers=headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["principal_id"] == "other-user"
        assert data["role"] == ROLE_READ  # Changed from 'roles' to 'role'
    
    def test_set_principal_permission_update_existing(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test updating permission for existing principal."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        # Create credential
        create_response = test_client.post(
            ENDPOINT_CREDENTIALS.format(tenant_id=tenant_id),
            json={
                "name": "Test Credential",
                "credential_type": "API_KEY",
                "secret_value": "secret"
            },
            headers=headers
        )
        credential_id = create_response.json()["id"]
        
        # Add READ permission
        test_client.put(
            ENDPOINT_CREDENTIAL_PRINCIPALS.format(tenant_id=tenant_id, credential_id=credential_id),
            json={
                "principal_id": "other-user",
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_READ
            },
            headers=headers
        )
        
        # Update to WRITE permission (replaces READ)
        response = test_client.put(
            ENDPOINT_CREDENTIAL_PRINCIPALS.format(tenant_id=tenant_id, credential_id=credential_id),
            json={
                "principal_id": "other-user",
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_WRITE
            },
            headers=headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["principal_id"] == "other-user"
        assert data["role"] == ROLE_WRITE  # Changed from 'roles' to 'role'
    
    def test_set_principal_permission_missing_principal_id(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test setting permission with missing principal_id."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        create_response = test_client.post(
            ENDPOINT_CREDENTIALS.format(tenant_id=tenant_id),
            json={
                "name": "Test Credential",
                "credential_type": "API_KEY",
                "secret_value": "secret"
            },
            headers=headers
        )
        credential_id = create_response.json()["id"]
        
        response = test_client.put(
            ENDPOINT_CREDENTIAL_PRINCIPALS.format(tenant_id=tenant_id, credential_id=credential_id),
            json={
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_READ
            },
            headers=headers
        )
        
        assert response.status_code == 422
    
    def test_set_principal_permission_missing_role(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test setting permission with missing role."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        create_response = test_client.post(
            ENDPOINT_CREDENTIALS.format(tenant_id=tenant_id),
            json={
                "name": "Test Credential",
                "credential_type": "API_KEY",
                "secret_value": "secret"
            },
            headers=headers
        )
        credential_id = create_response.json()["id"]
        
        response = test_client.put(
            ENDPOINT_CREDENTIAL_PRINCIPALS.format(tenant_id=tenant_id, credential_id=credential_id),
            json={
                "principal_id": "some-user",
                "principal_type": PRINCIPAL_TYPE_USER
            },
            headers=headers
        )
        
        assert response.status_code == 422
    
    def test_set_principal_permission_invalid_role(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test setting permission with invalid role."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        create_response = test_client.post(
            ENDPOINT_CREDENTIALS.format(tenant_id=tenant_id),
            json={
                "name": "Test Credential",
                "credential_type": "API_KEY",
                "secret_value": "secret"
            },
            headers=headers
        )
        credential_id = create_response.json()["id"]
        
        response = test_client.put(
            ENDPOINT_CREDENTIAL_PRINCIPALS.format(tenant_id=tenant_id, credential_id=credential_id),
            json={
                "principal_id": "some-user",
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": "INVALID_ROLE"
            },
            headers=headers
        )
        
        assert response.status_code == 422
    
    def test_set_principal_permission_invalid_principal_type(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test setting permission with invalid principal type."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        create_response = test_client.post(
            ENDPOINT_CREDENTIALS.format(tenant_id=tenant_id),
            json={
                "name": "Test Credential",
                "credential_type": "API_KEY",
                "secret_value": "secret"
            },
            headers=headers
        )
        credential_id = create_response.json()["id"]
        
        response = test_client.put(
            ENDPOINT_CREDENTIAL_PRINCIPALS.format(tenant_id=tenant_id, credential_id=credential_id),
            json={
                "principal_id": "some-user",
                "principal_type": "INVALID_TYPE",
                "role": ROLE_READ
            },
            headers=headers
        )
        
        assert response.status_code == 422
    
    def test_delete_principal_permission(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test deleting principal permission."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        # Create credential
        create_response = test_client.post(
            ENDPOINT_CREDENTIALS.format(tenant_id=tenant_id),
            json={
                "name": "Test Credential",
                "credential_type": "API_KEY",
                "secret_value": "secret"
            },
            headers=headers
        )
        credential_id = create_response.json()["id"]
        
        # Add permission
        test_client.put(
            ENDPOINT_CREDENTIAL_PRINCIPALS.format(tenant_id=tenant_id, credential_id=credential_id),
            json={
                "principal_id": "other-user",
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_READ
            },
            headers=headers
        )
        
        # Delete permission
        delete_response = test_client.request(
            "DELETE",
            ENDPOINT_CREDENTIAL_PRINCIPALS.format(tenant_id=tenant_id, credential_id=credential_id),
            json={
                "principal_id": "other-user",
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_READ
            },
            headers=headers
        )
        
        assert delete_response.status_code == status.HTTP_204_NO_CONTENT  # Changed from 200 to 204
        
        # Verify permission removed
        list_response = test_client.get(
            ENDPOINT_CREDENTIAL_PRINCIPALS.format(tenant_id=tenant_id, credential_id=credential_id),
            headers=headers
        )
        principals = list_response.json()["principals"]
        assert not any(p["principal_id"] == "other-user" for p in principals)
    
    def test_delete_principal_permission_not_found(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test deleting non-existent principal permission."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        create_response = test_client.post(
            ENDPOINT_CREDENTIALS.format(tenant_id=tenant_id),
            json={
                "name": "Test Credential",
                "credential_type": "API_KEY",
                "secret_value": "secret"
            },
            headers=headers
        )
        credential_id = create_response.json()["id"]
        
        response = test_client.request(
            "DELETE",
            ENDPOINT_CREDENTIAL_PRINCIPALS.format(tenant_id=tenant_id, credential_id=credential_id),
            json={
                "principal_id": "non-existent-user",
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_READ
            },
            headers=headers
        )
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
