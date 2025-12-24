"""Tests for development platforms API endpoints."""
from typing import Any
from fastapi import status
from starlette.testclient import TestClient

from aihub.core.database.enums import PermissionActionEnum, PrincipalTypeEnum
from tests.conftest import create_auth_headers


# API Endpoints
ENDPOINT_DEVELOPMENT_PLATFORMS = "/api/v1/tenants/{tenant_id}/development-platforms"
ENDPOINT_DEVELOPMENT_PLATFORM_DETAIL = "/api/v1/tenants/{tenant_id}/development-platforms/{development_platform_id}"
ENDPOINT_DEVELOPMENT_PLATFORM_PRINCIPALS = "/api/v1/tenants/{tenant_id}/development-platforms/{development_platform_id}/principals"
ENDPOINT_PRINCIPAL_DETAIL = "/api/v1/tenants/{tenant_id}/development-platforms/{development_platform_id}/principals/{principal_id}"

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


class TestDevelopmentPlatformRoutes:
    """Test suite for development platform API routes."""
    
    def test_create_development_platform_success(
        self, 
        test_client: TestClient, 
        test_user_token: Any
    ) -> None:
        """Test successful development platform creation."""
        # Create a tenant first
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        # Create development platform
        dp_data = {
            "name": "Test Development Platform",
            "description": "A test development platform",
            "type": "IDE",
            "iframe_url": "https://example.com/ide",
            "config": {"key": "value"}
        }
        
        response = test_client.post(
            ENDPOINT_DEVELOPMENT_PLATFORMS.format(tenant_id=tenant_id),
            json=dp_data,
            headers=headers
        )
        
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        
        assert data["name"] == dp_data["name"]
        assert data["description"] == dp_data["description"]
        assert data["type"] == dp_data["type"]
        assert data["iframe_url"] == dp_data["iframe_url"]
        assert data["config"] == dp_data["config"]
        assert "id" in data
        assert data["tenant_id"] == tenant_id
        assert "created_at" in data
        assert "updated_at" in data
        assert data["created_by"] == test_user_token.get_id()
    
    def test_create_development_platform_minimal(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test development platform creation with minimal required fields."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        # Create with only required fields
        dp_data = {
            "name": "Minimal Platform",
            "iframe_url": "https://example.com/minimal"
        }
        
        response = test_client.post(
            ENDPOINT_DEVELOPMENT_PLATFORMS.format(tenant_id=tenant_id),
            json=dp_data,
            headers=headers
        )
        
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        
        assert data["name"] == dp_data["name"]
        assert data["iframe_url"] == dp_data["iframe_url"]
        assert data["description"] is None
        assert data["type"] is None
        assert data["config"] == {}
    
    def test_create_development_platform_missing_name(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test development platform creation with missing name."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        response = test_client.post(
            ENDPOINT_DEVELOPMENT_PLATFORMS.format(tenant_id=tenant_id),
            json={"iframe_url": "https://example.com"},
            headers=headers
        )
        
        assert response.status_code == 422
    
    def test_create_development_platform_missing_iframe_url(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test development platform creation with missing iframe_url."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        response = test_client.post(
            ENDPOINT_DEVELOPMENT_PLATFORMS.format(tenant_id=tenant_id),
            json={"name": "Test Platform"},
            headers=headers
        )
        
        assert response.status_code == 422
    
    def test_create_development_platform_invalid_name_type(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test development platform creation with invalid name type."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        response = test_client.post(
            ENDPOINT_DEVELOPMENT_PLATFORMS.format(tenant_id=tenant_id),
            json={"name": 123, "iframe_url": "https://example.com"},
            headers=headers
        )
        
        assert response.status_code == 422
    
    def test_create_development_platform_empty_name(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test development platform creation with empty name."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        response = test_client.post(
            ENDPOINT_DEVELOPMENT_PLATFORMS.format(tenant_id=tenant_id),
            json={"name": "", "iframe_url": "https://example.com"},
            headers=headers
        )
        
        assert response.status_code == 422
    
    def test_create_development_platform_empty_iframe_url(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test development platform creation with empty iframe_url."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        response = test_client.post(
            ENDPOINT_DEVELOPMENT_PLATFORMS.format(tenant_id=tenant_id),
            json={"name": "Test", "iframe_url": ""},
            headers=headers
        )
        
        assert response.status_code == 422
    
    def test_create_development_platform_empty_body(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test development platform creation with empty JSON body."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        response = test_client.post(
            ENDPOINT_DEVELOPMENT_PLATFORMS.format(tenant_id=tenant_id),
            json={},
            headers=headers
        )
        
        assert response.status_code == 422
    
    def test_create_development_platform_without_permission(self, test_client: TestClient) -> None:
        """Test that user without DEVELOPMENT_PLATFORMS_CREATOR permission cannot create."""
        # Create user1 with a tenant
        user1_token = test_client.create_test_user("user-1", "User One")
        tenant_id = create_tenant_for_user(test_client, user1_token)
        
        # Create user2 (not a member of the tenant)
        user2_token = test_client.create_test_user("user-2", "User Two")
        headers2 = create_auth_headers(user2_token, use_cache=False)
        
        # Try to create development platform as user2 (should fail - no tenant membership)
        response = test_client.post(
            ENDPOINT_DEVELOPMENT_PLATFORMS.format(tenant_id=tenant_id),
            json={"name": "Unauthorized Platform", "iframe_url": "https://example.com"},
            headers=headers2
        )
        
        assert response.status_code == status.HTTP_403_FORBIDDEN
    
    def test_get_development_platform_success(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test successful development platform retrieval."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        # Create a development platform
        dp_data = {"name": "Test Platform", "description": "Test description", "iframe_url": "https://example.com"}
        create_response = test_client.post(
            ENDPOINT_DEVELOPMENT_PLATFORMS.format(tenant_id=tenant_id),
            json=dp_data,
            headers=headers
        )
        dp_id = create_response.json()["id"]
        
        # Retrieve the development platform
        response = test_client.get(
            ENDPOINT_DEVELOPMENT_PLATFORM_DETAIL.format(tenant_id=tenant_id, development_platform_id=dp_id),
            headers=headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["id"] == dp_id
        assert data["name"] == dp_data["name"]
        assert data["description"] == dp_data["description"]
        assert data["iframe_url"] == dp_data["iframe_url"]
    
    def test_get_development_platform_not_found(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test development platform retrieval with non-existent ID."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        response = test_client.get(
            ENDPOINT_DEVELOPMENT_PLATFORM_DETAIL.format(tenant_id=tenant_id, development_platform_id=NON_EXISTENT_ID),
            headers=headers
        )
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
    
    def test_list_development_platforms_empty(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test listing development platforms when none exist."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        response = test_client.get(
            ENDPOINT_DEVELOPMENT_PLATFORMS.format(tenant_id=tenant_id),
            headers=headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert isinstance(data, list)
        assert len(data) == 0
    
    def test_list_development_platforms_with_data(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test listing development platforms with existing data."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        # Create multiple development platforms
        dp1_data = {"name": "Platform 1", "description": "First platform", "iframe_url": "https://example1.com"}
        dp2_data = {"name": "Platform 2", "description": "Second platform", "iframe_url": "https://example2.com"}
        
        test_client.post(
            ENDPOINT_DEVELOPMENT_PLATFORMS.format(tenant_id=tenant_id),
            json=dp1_data,
            headers=headers
        )
        test_client.post(
            ENDPOINT_DEVELOPMENT_PLATFORMS.format(tenant_id=tenant_id),
            json=dp2_data,
            headers=headers
        )
        
        # List development platforms
        response = test_client.get(
            ENDPOINT_DEVELOPMENT_PLATFORMS.format(tenant_id=tenant_id),
            headers=headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert isinstance(data, list)
        assert len(data) == 2
        
        names = [dp["name"] for dp in data]
        assert "Platform 1" in names
        assert "Platform 2" in names
    
    def test_list_development_platforms_with_pagination(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test listing development platforms with pagination parameters."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        # Create multiple development platforms
        for i in range(5):
            test_client.post(
                ENDPOINT_DEVELOPMENT_PLATFORMS.format(tenant_id=tenant_id),
                json={"name": f"Platform {i}", "description": f"Description {i}", "iframe_url": f"https://example{i}.com"},
                headers=headers
            )
        
        # Test with limit
        response = test_client.get(
            f"{ENDPOINT_DEVELOPMENT_PLATFORMS.format(tenant_id=tenant_id)}?limit=3",
            headers=headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 3
        
        # Test with skip
        response = test_client.get(
            f"{ENDPOINT_DEVELOPMENT_PLATFORMS.format(tenant_id=tenant_id)}?skip=2&limit=2",
            headers=headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 2
    
    def test_list_development_platforms_with_name_filter(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test listing development platforms with name filter."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        # Create development platforms with different names
        test_client.post(
            ENDPOINT_DEVELOPMENT_PLATFORMS.format(tenant_id=tenant_id),
            json={"name": "Production IDE", "description": "Prod", "iframe_url": "https://prod.example.com"},
            headers=headers
        )
        test_client.post(
            ENDPOINT_DEVELOPMENT_PLATFORMS.format(tenant_id=tenant_id),
            json={"name": "Development IDE", "description": "Dev", "iframe_url": "https://dev.example.com"},
            headers=headers
        )
        
        # Filter by name
        response = test_client.get(
            f"{ENDPOINT_DEVELOPMENT_PLATFORMS.format(tenant_id=tenant_id)}?name_filter=Production",
            headers=headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "Production IDE"
    
    def test_update_development_platform_success(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test successful development platform update."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        # Create a development platform
        dp_data = {"name": "Original Name", "description": "Original", "iframe_url": "https://original.com"}
        create_response = test_client.post(
            ENDPOINT_DEVELOPMENT_PLATFORMS.format(tenant_id=tenant_id),
            json=dp_data,
            headers=headers
        )
        dp_id = create_response.json()["id"]
        
        # Update the development platform
        update_data = {"name": "Updated Name", "description": "Updated", "iframe_url": "https://updated.com"}
        update_response = test_client.patch(
            ENDPOINT_DEVELOPMENT_PLATFORM_DETAIL.format(tenant_id=tenant_id, development_platform_id=dp_id),
            json=update_data,
            headers=headers
        )
        
        assert update_response.status_code == status.HTTP_200_OK
        data = update_response.json()
        
        assert data["name"] == update_data["name"]
        assert data["description"] == update_data["description"]
        assert data["iframe_url"] == update_data["iframe_url"]
        assert data["id"] == dp_id
    
    def test_update_development_platform_not_found(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test development platform update with non-existent ID."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        response = test_client.patch(
            ENDPOINT_DEVELOPMENT_PLATFORM_DETAIL.format(tenant_id=tenant_id, development_platform_id=NON_EXISTENT_ID),
            json={"name": "Updated"},
            headers=headers
        )
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
    
    def test_update_development_platform_partial(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test partial development platform update."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        # Create a development platform
        dp_data = {"name": "Original", "description": "Description", "iframe_url": "https://original.com", "type": "IDE"}
        create_response = test_client.post(
            ENDPOINT_DEVELOPMENT_PLATFORMS.format(tenant_id=tenant_id),
            json=dp_data,
            headers=headers
        )
        dp_id = create_response.json()["id"]
        
        # Update only name
        update_response = test_client.patch(
            ENDPOINT_DEVELOPMENT_PLATFORM_DETAIL.format(tenant_id=tenant_id, development_platform_id=dp_id),
            json={"name": "Only Name Updated"},
            headers=headers
        )
        
        assert update_response.status_code == status.HTTP_200_OK
        data = update_response.json()
        
        assert data["name"] == "Only Name Updated"
        assert data["description"] == dp_data["description"]  # Should remain unchanged
        assert data["iframe_url"] == dp_data["iframe_url"]  # Should remain unchanged
        assert data["type"] == dp_data["type"]  # Should remain unchanged
    
    def test_delete_development_platform_success(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test successful development platform deletion."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        # Create a development platform
        dp_data = {"name": "To Delete", "description": "Will be deleted", "iframe_url": "https://delete.com"}
        create_response = test_client.post(
            ENDPOINT_DEVELOPMENT_PLATFORMS.format(tenant_id=tenant_id),
            json=dp_data,
            headers=headers
        )
        dp_id = create_response.json()["id"]
        
        # Delete the development platform
        delete_response = test_client.request(
            "DELETE",
            ENDPOINT_DEVELOPMENT_PLATFORM_DETAIL.format(tenant_id=tenant_id, development_platform_id=dp_id),
            headers=headers
        )
        
        assert delete_response.status_code == status.HTTP_204_NO_CONTENT
        
        # Verify it's deleted
        get_response = test_client.get(
            ENDPOINT_DEVELOPMENT_PLATFORM_DETAIL.format(tenant_id=tenant_id, development_platform_id=dp_id),
            headers=headers
        )
        
        assert get_response.status_code == status.HTTP_404_NOT_FOUND
    
    def test_delete_development_platform_not_found(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test development platform deletion with non-existent ID."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        response = test_client.request(
            "DELETE",
            ENDPOINT_DEVELOPMENT_PLATFORM_DETAIL.format(tenant_id=tenant_id, development_platform_id=NON_EXISTENT_ID),
            headers=headers
        )
        
        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestDevelopmentPlatformPrincipalRoutes:
    """Test suite for development platform principal/permission management routes."""
    
    def test_list_development_platform_principals_creator_only(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test that only creator has permissions initially."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        # Create a development platform
        dp_data = {"name": "Test Platform", "description": "Test", "iframe_url": "https://example.com"}
        create_response = test_client.post(
            ENDPOINT_DEVELOPMENT_PLATFORMS.format(tenant_id=tenant_id),
            json=dp_data,
            headers=headers
        )
        dp_id = create_response.json()["id"]
        
        # List principals
        response = test_client.get(
            ENDPOINT_DEVELOPMENT_PLATFORM_PRINCIPALS.format(tenant_id=tenant_id, development_platform_id=dp_id),
            headers=headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert "development_platform_id" in data
        assert "principals" in data
        assert len(data["principals"]) >= 1  # At least the creator
        
        # Check creator has ADMIN permission
        creator_principal = next(
            (p for p in data["principals"] if p["principal_id"] == test_user_token.get_id()),
            None
        )
        assert creator_principal is not None
        assert ROLE_ADMIN in creator_principal["roles"]
    
    def test_get_principal_permissions(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test getting permissions for a specific principal."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        # Create a development platform
        dp_data = {"name": "Test Platform", "description": "Test", "iframe_url": "https://example.com"}
        create_response = test_client.post(
            ENDPOINT_DEVELOPMENT_PLATFORMS.format(tenant_id=tenant_id),
            json=dp_data,
            headers=headers
        )
        dp_id = create_response.json()["id"]
        
        # Get creator's permissions
        response = test_client.get(
            ENDPOINT_PRINCIPAL_DETAIL.format(
                tenant_id=tenant_id,
                development_platform_id=dp_id,
                principal_id=test_user_token.get_id()
            ),
            headers=headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["principal_id"] == test_user_token.get_id()
        assert data["principal_type"] == PRINCIPAL_TYPE_USER
        assert ROLE_ADMIN in data["roles"]
    
    def test_set_principal_permission_new_user(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test adding a new principal with permission."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        # Create a development platform
        dp_data = {"name": "Test Platform", "description": "Test", "iframe_url": "https://example.com"}
        create_response = test_client.post(
            ENDPOINT_DEVELOPMENT_PLATFORMS.format(tenant_id=tenant_id),
            json=dp_data,
            headers=headers
        )
        dp_id = create_response.json()["id"]
        
        # Add permission for another user
        permission_data = {
            "principal_id": "other-user",
            "principal_type": PRINCIPAL_TYPE_USER,
            "role": ROLE_READ
        }
        
        response = test_client.put(
            ENDPOINT_DEVELOPMENT_PLATFORM_PRINCIPALS.format(tenant_id=tenant_id, development_platform_id=dp_id),
            json=permission_data,
            headers=headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["principal_id"] == "other-user"
        assert data["principal_type"] == PRINCIPAL_TYPE_USER
        assert data["role"] == ROLE_READ
    
    def test_set_principal_permission_update_existing(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test updating an existing principal's permission."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        # Create a development platform
        dp_data = {"name": "Test Platform", "description": "Test", "iframe_url": "https://example.com"}
        create_response = test_client.post(
            ENDPOINT_DEVELOPMENT_PLATFORMS.format(tenant_id=tenant_id),
            json=dp_data,
            headers=headers
        )
        dp_id = create_response.json()["id"]
        
        # Add READ permission
        test_client.put(
            ENDPOINT_DEVELOPMENT_PLATFORM_PRINCIPALS.format(tenant_id=tenant_id, development_platform_id=dp_id),
            json={
                "principal_id": "other-user",
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_READ
            },
            headers=headers
        )
        
        # Update to WRITE permission
        update_response = test_client.put(
            ENDPOINT_DEVELOPMENT_PLATFORM_PRINCIPALS.format(tenant_id=tenant_id, development_platform_id=dp_id),
            json={
                "principal_id": "other-user",
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_WRITE
            },
            headers=headers
        )
        
        assert update_response.status_code == status.HTTP_200_OK
        data = update_response.json()
        
        assert data["principal_id"] == "other-user"
        assert data["role"] == ROLE_WRITE
    
    def test_set_principal_permission_missing_principal_id(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test setting permission with missing principal_id."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        # Create a development platform
        dp_data = {"name": "Test Platform", "description": "Test", "iframe_url": "https://example.com"}
        create_response = test_client.post(
            ENDPOINT_DEVELOPMENT_PLATFORMS.format(tenant_id=tenant_id),
            json=dp_data,
            headers=headers
        )
        dp_id = create_response.json()["id"]
        
        response = test_client.put(
            ENDPOINT_DEVELOPMENT_PLATFORM_PRINCIPALS.format(tenant_id=tenant_id, development_platform_id=dp_id),
            json={"role": ROLE_READ},
            headers=headers
        )
        
        assert response.status_code == 422
    
    def test_set_principal_permission_missing_role(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test setting permission with missing role."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        # Create a development platform
        dp_data = {"name": "Test Platform", "description": "Test", "iframe_url": "https://example.com"}
        create_response = test_client.post(
            ENDPOINT_DEVELOPMENT_PLATFORMS.format(tenant_id=tenant_id),
            json=dp_data,
            headers=headers
        )
        dp_id = create_response.json()["id"]
        
        response = test_client.put(
            ENDPOINT_DEVELOPMENT_PLATFORM_PRINCIPALS.format(tenant_id=tenant_id, development_platform_id=dp_id),
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
        
        # Create a development platform
        dp_data = {"name": "Test Platform", "description": "Test", "iframe_url": "https://example.com"}
        create_response = test_client.post(
            ENDPOINT_DEVELOPMENT_PLATFORMS.format(tenant_id=tenant_id),
            json=dp_data,
            headers=headers
        )
        dp_id = create_response.json()["id"]
        
        response = test_client.put(
            ENDPOINT_DEVELOPMENT_PLATFORM_PRINCIPALS.format(tenant_id=tenant_id, development_platform_id=dp_id),
            json={
                "principal_id": "some-user",
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": "INVALID_ROLE"
            },
            headers=headers
        )
        
        assert response.status_code == 422
    
    def test_set_principal_permission_invalid_principal_type(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test setting permission with invalid principal_type."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        # Create a development platform
        dp_data = {"name": "Test Platform", "description": "Test", "iframe_url": "https://example.com"}
        create_response = test_client.post(
            ENDPOINT_DEVELOPMENT_PLATFORMS.format(tenant_id=tenant_id),
            json=dp_data,
            headers=headers
        )
        dp_id = create_response.json()["id"]
        
        response = test_client.put(
            ENDPOINT_DEVELOPMENT_PLATFORM_PRINCIPALS.format(tenant_id=tenant_id, development_platform_id=dp_id),
            json={
                "principal_id": "some-user",
                "principal_type": "INVALID_TYPE",
                "role": ROLE_READ
            },
            headers=headers
        )
        
        assert response.status_code == 422
    
    def test_delete_principal_permission(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test deleting a principal's permission."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        # Create a development platform
        dp_data = {"name": "Test Platform", "description": "Test", "iframe_url": "https://example.com"}
        create_response = test_client.post(
            ENDPOINT_DEVELOPMENT_PLATFORMS.format(tenant_id=tenant_id),
            json=dp_data,
            headers=headers
        )
        dp_id = create_response.json()["id"]
        
        # Add permission
        test_client.put(
            ENDPOINT_DEVELOPMENT_PLATFORM_PRINCIPALS.format(tenant_id=tenant_id, development_platform_id=dp_id),
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
            ENDPOINT_DEVELOPMENT_PLATFORM_PRINCIPALS.format(tenant_id=tenant_id, development_platform_id=dp_id),
            json={
                "principal_id": "other-user",
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_READ
            },
            headers=headers
        )
        
        assert delete_response.status_code == status.HTTP_204_NO_CONTENT
        
        # Verify permission is deleted
        get_response = test_client.get(
            ENDPOINT_PRINCIPAL_DETAIL.format(
                tenant_id=tenant_id,
                development_platform_id=dp_id,
                principal_id="other-user"
            ),
            headers=headers
        )
        
        assert get_response.status_code == status.HTTP_404_NOT_FOUND
    
    def test_delete_principal_permission_not_found(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test deleting a non-existent permission."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        # Create a development platform
        dp_data = {"name": "Test Platform", "description": "Test", "iframe_url": "https://example.com"}
        create_response = test_client.post(
            ENDPOINT_DEVELOPMENT_PLATFORMS.format(tenant_id=tenant_id),
            json=dp_data,
            headers=headers
        )
        dp_id = create_response.json()["id"]
        
        # Try to delete non-existent permission
        response = test_client.request(
            "DELETE",
            ENDPOINT_DEVELOPMENT_PLATFORM_PRINCIPALS.format(tenant_id=tenant_id, development_platform_id=dp_id),
            json={
                "principal_id": "non-existent-user",
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_READ
            },
            headers=headers
        )
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
