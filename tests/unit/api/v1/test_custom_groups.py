"""Tests for custom groups API endpoints."""
from typing import Any
from fastapi import status
from starlette.testclient import TestClient

from unifiedui.core.database.enums import PermissionActionEnum, PrincipalTypeEnum
from tests.conftest import create_auth_headers


# API Endpoints
ENDPOINT_CUSTOM_GROUPS = "/api/v1/platform-service/tenants/{tenant_id}/custom-groups"
ENDPOINT_CUSTOM_GROUP_DETAIL = "/api/v1/platform-service/tenants/{tenant_id}/custom-groups/{custom_group_id}"
ENDPOINT_CUSTOM_GROUP_PRINCIPALS = "/api/v1/platform-service/tenants/{tenant_id}/custom-groups/{custom_group_id}/principals"
ENDPOINT_PRINCIPAL_DETAIL = "/api/v1/platform-service/tenants/{tenant_id}/custom-groups/{custom_group_id}/principals/{principal_id}"

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
        "/api/v1/platform-service/tenants",
        json={"name": tenant_name, "description": f"Tenant for {user_token.get_id()}"},
        headers=headers
    )
    assert response.status_code == status.HTTP_201_CREATED
    return response.json()["id"]


class TestCustomGroupRoutes:
    """Test suite for custom group API routes."""
    
    def test_create_custom_group_success(
        self, 
        test_client: TestClient, 
        test_user_token: Any
    ) -> None:
        """Test successful custom group creation."""
        # Create a tenant first
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        # Create custom group
        group_data = {
            "name": "Test Group",
            "description": "A test custom group"
        }
        
        response = test_client.post(
            ENDPOINT_CUSTOM_GROUPS.format(tenant_id=tenant_id),
            json=group_data,
            headers=headers
        )
        
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        
        assert data["name"] == group_data["name"]
        assert data["description"] == group_data["description"]
        assert "id" in data
        assert data["tenant_id"] == tenant_id
        assert "created_at" in data
        assert "updated_at" in data
        # Principal model doesn't track created_by, so it will be None
        assert data["created_by"] is None
    
    def test_create_custom_group_missing_name(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test custom group creation with missing name."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        response = test_client.post(
            ENDPOINT_CUSTOM_GROUPS.format(tenant_id=tenant_id),
            json={"description": "Test group"},
            headers=headers
        )
        
        assert response.status_code == 422
    
    def test_create_custom_group_invalid_name_type(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test custom group creation with invalid name type."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        response = test_client.post(
            ENDPOINT_CUSTOM_GROUPS.format(tenant_id=tenant_id),
            json={"name": 123, "description": "Test"},
            headers=headers
        )
        
        assert response.status_code == 422
    
    def test_create_custom_group_empty_name(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test custom group creation with empty name."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        response = test_client.post(
            ENDPOINT_CUSTOM_GROUPS.format(tenant_id=tenant_id),
            json={"name": "", "description": "Test"},
            headers=headers
        )
        
        assert response.status_code == 422
    
    def test_create_custom_group_invalid_description_type(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test custom group creation with invalid description type."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        response = test_client.post(
            ENDPOINT_CUSTOM_GROUPS.format(tenant_id=tenant_id),
            json={"name": "Test Group", "description": 123},
            headers=headers
        )
        
        assert response.status_code == 422
    
    def test_create_custom_group_empty_body(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test custom group creation with empty JSON body."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        response = test_client.post(
            ENDPOINT_CUSTOM_GROUPS.format(tenant_id=tenant_id),
            json={},
            headers=headers
        )
        
        assert response.status_code == 422
    
    def test_create_custom_group_without_permission(self, test_client: TestClient) -> None:
        """Test that user without CUSTOM_GROUP_CREATOR permission cannot create groups."""
        # Create user1 with a tenant
        user1_token = test_client.create_test_user("user-1", "User One")
        tenant_id = create_tenant_for_user(test_client, user1_token)
        headers1 = create_auth_headers(user1_token, use_cache=False)
        
        # Create user2 (not a member of the tenant)
        user2_token = test_client.create_test_user("user-2", "User Two")
        headers2 = create_auth_headers(user2_token, use_cache=False)
        
        # Try to create group as user2 (should fail - no tenant membership)
        response = test_client.post(
            ENDPOINT_CUSTOM_GROUPS.format(tenant_id=tenant_id),
            json={"name": "Unauthorized Group", "description": "Should fail"},
            headers=headers2
        )
        
        assert response.status_code == status.HTTP_403_FORBIDDEN
    
    def test_get_custom_group_success(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test successful custom group retrieval."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        # Create a custom group
        group_data = {"name": "Test Group", "description": "Test description"}
        create_response = test_client.post(
            ENDPOINT_CUSTOM_GROUPS.format(tenant_id=tenant_id),
            json=group_data,
            headers=headers
        )
        group_id = create_response.json()["id"]
        
        # Retrieve the group
        response = test_client.get(
            ENDPOINT_CUSTOM_GROUP_DETAIL.format(tenant_id=tenant_id, custom_group_id=group_id),
            headers=headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["id"] == group_id
        assert data["name"] == group_data["name"]
        assert data["description"] == group_data["description"]
    
    def test_get_custom_group_not_found(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test custom group retrieval with non-existent ID."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        response = test_client.get(
            ENDPOINT_CUSTOM_GROUP_DETAIL.format(tenant_id=tenant_id, custom_group_id=NON_EXISTENT_ID),
            headers=headers
        )
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
    
    def test_list_custom_groups_empty(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test listing custom groups when none exist."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        response = test_client.get(
            ENDPOINT_CUSTOM_GROUPS.format(tenant_id=tenant_id),
            headers=headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert isinstance(data, list)
        assert len(data) == 0
    
    def test_list_custom_groups_with_data(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test listing custom groups with existing data."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        # Create multiple custom groups
        group1_data = {"name": "Group 1", "description": "First group"}
        group2_data = {"name": "Group 2", "description": "Second group"}
        
        test_client.post(
            ENDPOINT_CUSTOM_GROUPS.format(tenant_id=tenant_id),
            json=group1_data,
            headers=headers
        )
        test_client.post(
            ENDPOINT_CUSTOM_GROUPS.format(tenant_id=tenant_id),
            json=group2_data,
            headers=headers
        )
        
        # List groups
        response = test_client.get(
            ENDPOINT_CUSTOM_GROUPS.format(tenant_id=tenant_id),
            headers=headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert isinstance(data, list)
        assert len(data) == 2
        
        names = [group["name"] for group in data]
        assert "Group 1" in names
        assert "Group 2" in names
    
    def test_list_custom_groups_with_pagination(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test listing custom groups with pagination parameters."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        # Create multiple custom groups
        for i in range(5):
            test_client.post(
                ENDPOINT_CUSTOM_GROUPS.format(tenant_id=tenant_id),
                json={"name": f"Group {i}", "description": f"Test group {i}"},
                headers=headers
            )
        
        # Test with limit
        response = test_client.get(
            f"{ENDPOINT_CUSTOM_GROUPS.format(tenant_id=tenant_id)}?limit=3",
            headers=headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 3
        
        # Test with skip
        response = test_client.get(
            f"{ENDPOINT_CUSTOM_GROUPS.format(tenant_id=tenant_id)}?skip=2&limit=2",
            headers=headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 2
    
    def test_list_custom_groups_with_name_filter(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test listing custom groups with name filter."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        # Create groups with different names
        test_client.post(
            ENDPOINT_CUSTOM_GROUPS.format(tenant_id=tenant_id),
            json={"name": "Production Team", "description": "Prod"},
            headers=headers
        )
        test_client.post(
            ENDPOINT_CUSTOM_GROUPS.format(tenant_id=tenant_id),
            json={"name": "Development Team", "description": "Dev"},
            headers=headers
        )
        test_client.post(
            ENDPOINT_CUSTOM_GROUPS.format(tenant_id=tenant_id),
            json={"name": "QA Team", "description": "QA"},
            headers=headers
        )
        
        # Filter by name
        response = test_client.get(
            f"{ENDPOINT_CUSTOM_GROUPS.format(tenant_id=tenant_id)}?name=Development",
            headers=headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert len(data) >= 1
        assert any(group["name"] == "Development Team" for group in data)
    
    def test_update_custom_group_success(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test successful custom group update."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        # Create a custom group
        create_response = test_client.post(
            ENDPOINT_CUSTOM_GROUPS.format(tenant_id=tenant_id),
            json={"name": "Original Name", "description": "Original description"},
            headers=headers
        )
        group_id = create_response.json()["id"]
        
        # Update the group
        update_data = {
            "name": "Updated Name",
            "description": "Updated description"
        }
        
        response = test_client.patch(
            ENDPOINT_CUSTOM_GROUP_DETAIL.format(tenant_id=tenant_id, custom_group_id=group_id),
            json=update_data,
            headers=headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["id"] == group_id
        assert data["name"] == update_data["name"]
        assert data["description"] == update_data["description"]
        # Principal model doesn't track updated_by, so it will be None
        assert data["updated_by"] is None
    
    def test_update_custom_group_not_found(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test updating a non-existent custom group."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        response = test_client.patch(
            ENDPOINT_CUSTOM_GROUP_DETAIL.format(tenant_id=tenant_id, custom_group_id=NON_EXISTENT_ID),
            json={"name": "Updated Name"},
            headers=headers
        )
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
    
    def test_update_custom_group_partial(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test partial custom group update."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        # Create a custom group
        original_data = {"name": "Original Name", "description": "Original description"}
        create_response = test_client.post(
            ENDPOINT_CUSTOM_GROUPS.format(tenant_id=tenant_id),
            json=original_data,
            headers=headers
        )
        group_id = create_response.json()["id"]
        
        # Update only name
        response = test_client.patch(
            ENDPOINT_CUSTOM_GROUP_DETAIL.format(tenant_id=tenant_id, custom_group_id=group_id),
            json={"name": "Partially Updated"},
            headers=headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["name"] == "Partially Updated"
        assert data["description"] == original_data["description"]
    
    def test_delete_custom_group_success(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test successful custom group deletion."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        # Create a custom group
        create_response = test_client.post(
            ENDPOINT_CUSTOM_GROUPS.format(tenant_id=tenant_id),
            json={"name": "To Delete", "description": "Will be deleted"},
            headers=headers
        )
        group_id = create_response.json()["id"]
        
        # Delete the group
        response = test_client.request(
            "DELETE",
            ENDPOINT_CUSTOM_GROUP_DETAIL.format(tenant_id=tenant_id, custom_group_id=group_id),
            headers=headers
        )
        
        assert response.status_code == status.HTTP_204_NO_CONTENT
        
        # Verify group is deleted
        get_response = test_client.get(
            ENDPOINT_CUSTOM_GROUP_DETAIL.format(tenant_id=tenant_id, custom_group_id=group_id),
            headers=headers
        )
        assert get_response.status_code == status.HTTP_404_NOT_FOUND
    
    def test_delete_custom_group_not_found(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test deleting a non-existent custom group."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        response = test_client.request(
            "DELETE",
            ENDPOINT_CUSTOM_GROUP_DETAIL.format(tenant_id=tenant_id, custom_group_id=NON_EXISTENT_ID),
            headers=headers
        )
        
        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestCustomGroupPrincipalRoutes:
    """Test suite for custom group principal/permission management routes."""
    
    def test_list_custom_group_principals_creator_only(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test listing principals for a custom group with only the creator."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        # Create a custom group
        create_response = test_client.post(
            ENDPOINT_CUSTOM_GROUPS.format(tenant_id=tenant_id),
            json={"name": "Test Group", "description": "Test"},
            headers=headers
        )
        group_id = create_response.json()["id"]
        
        # List principals
        response = test_client.get(
            ENDPOINT_CUSTOM_GROUP_PRINCIPALS.format(tenant_id=tenant_id, custom_group_id=group_id),
            headers=headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert "resource_id" in data
        assert "resource_type" in data
        assert data["resource_type"] == "custom_group"
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
        
        # Create a custom group
        create_response = test_client.post(
            ENDPOINT_CUSTOM_GROUPS.format(tenant_id=tenant_id),
            json={"name": "Test Group", "description": "Test"},
            headers=headers
        )
        group_id = create_response.json()["id"]
        
        # Get creator's permissions
        response = test_client.get(
            ENDPOINT_PRINCIPAL_DETAIL.format(
                tenant_id=tenant_id,
                custom_group_id=group_id,
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
        """Test adding a permission for a new principal."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        # Create a custom group
        create_response = test_client.post(
            ENDPOINT_CUSTOM_GROUPS.format(tenant_id=tenant_id),
            json={"name": "Test Group", "description": "Test"},
            headers=headers
        )
        group_id = create_response.json()["id"]
        
        # Add a new user with READ permission
        permission_data = {
            "principal_id": "user-456",
            "principal_type": PRINCIPAL_TYPE_USER,
            "role": ROLE_READ
        }
        
        response = test_client.put(
            ENDPOINT_CUSTOM_GROUP_PRINCIPALS.format(tenant_id=tenant_id, custom_group_id=group_id),
            json=permission_data,
            headers=headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["principal_id"] == "user-456"
        assert data["principal_type"] == PRINCIPAL_TYPE_USER
        assert ROLE_READ in data["roles"]
    
    def test_set_principal_permission_update_existing(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test updating permission for an existing principal (replaces old role)."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        # Create a custom group
        create_response = test_client.post(
            ENDPOINT_CUSTOM_GROUPS.format(tenant_id=tenant_id),
            json={"name": "Test Group", "description": "Test"},
            headers=headers
        )
        group_id = create_response.json()["id"]
        
        # Add user with READ permission
        test_client.put(
            ENDPOINT_CUSTOM_GROUP_PRINCIPALS.format(tenant_id=tenant_id, custom_group_id=group_id),
            json={
                "principal_id": "user-789",
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_READ
            },
            headers=headers
        )
        
        # Update to WRITE permission (replaces READ)
        response = test_client.put(
            ENDPOINT_CUSTOM_GROUP_PRINCIPALS.format(tenant_id=tenant_id, custom_group_id=group_id),
            json={
                "principal_id": "user-789",
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_WRITE
            },
            headers=headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["principal_id"] == "user-789"
        # Should only have WRITE role now (READ was replaced)
        assert len(data["roles"]) == 1
        assert ROLE_WRITE in data["roles"]
        assert ROLE_READ not in data["roles"]
    
    def test_set_principal_permission_missing_principal_id(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test setting permission with missing principal_id."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        # Create a custom group
        create_response = test_client.post(
            ENDPOINT_CUSTOM_GROUPS.format(tenant_id=tenant_id),
            json={"name": "Test Group", "description": "Test"},
            headers=headers
        )
        group_id = create_response.json()["id"]
        
        response = test_client.put(
            ENDPOINT_CUSTOM_GROUP_PRINCIPALS.format(tenant_id=tenant_id, custom_group_id=group_id),
            json={"principal_type": PRINCIPAL_TYPE_USER, "role": ROLE_READ},
            headers=headers
        )
        
        assert response.status_code == 422
    
    def test_set_principal_permission_missing_role(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test setting permission with missing role."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        # Create a custom group
        create_response = test_client.post(
            ENDPOINT_CUSTOM_GROUPS.format(tenant_id=tenant_id),
            json={"name": "Test Group", "description": "Test"},
            headers=headers
        )
        group_id = create_response.json()["id"]
        
        response = test_client.put(
            ENDPOINT_CUSTOM_GROUP_PRINCIPALS.format(tenant_id=tenant_id, custom_group_id=group_id),
            json={"principal_id": "user-123", "principal_type": PRINCIPAL_TYPE_USER},
            headers=headers
        )
        
        assert response.status_code == 422
    
    def test_set_principal_permission_invalid_role(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test setting permission with invalid role."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        # Create a custom group
        create_response = test_client.post(
            ENDPOINT_CUSTOM_GROUPS.format(tenant_id=tenant_id),
            json={"name": "Test Group", "description": "Test"},
            headers=headers
        )
        group_id = create_response.json()["id"]
        
        response = test_client.put(
            ENDPOINT_CUSTOM_GROUP_PRINCIPALS.format(tenant_id=tenant_id, custom_group_id=group_id),
            json={
                "principal_id": "user-123",
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
        
        # Create a custom group
        create_response = test_client.post(
            ENDPOINT_CUSTOM_GROUPS.format(tenant_id=tenant_id),
            json={"name": "Test Group", "description": "Test"},
            headers=headers
        )
        group_id = create_response.json()["id"]
        
        response = test_client.put(
            ENDPOINT_CUSTOM_GROUP_PRINCIPALS.format(tenant_id=tenant_id, custom_group_id=group_id),
            json={
                "principal_id": "user-123",
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
        
        # Create a custom group
        create_response = test_client.post(
            ENDPOINT_CUSTOM_GROUPS.format(tenant_id=tenant_id),
            json={"name": "Test Group", "description": "Test"},
            headers=headers
        )
        group_id = create_response.json()["id"]
        
        # Add a user with READ permission
        test_client.put(
            ENDPOINT_CUSTOM_GROUP_PRINCIPALS.format(tenant_id=tenant_id, custom_group_id=group_id),
            json={
                "principal_id": "user-delete",
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_READ
            },
            headers=headers
        )
        
        # Delete the permission
        response = test_client.request(
            "DELETE",
            ENDPOINT_CUSTOM_GROUP_PRINCIPALS.format(tenant_id=tenant_id, custom_group_id=group_id),
            json={
                "principal_id": "user-delete",
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_READ
            },
            headers=headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        # Verify principal has no permissions
        assert data["principal_id"] == "user-delete"
        assert len(data["roles"]) == 0
    
    def test_delete_principal_permission_not_found(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test deleting a permission that doesn't exist."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        # Create a custom group
        create_response = test_client.post(
            ENDPOINT_CUSTOM_GROUPS.format(tenant_id=tenant_id),
            json={"name": "Test Group", "description": "Test"},
            headers=headers
        )
        group_id = create_response.json()["id"]
        
        response = test_client.request(
            "DELETE",
            ENDPOINT_CUSTOM_GROUP_PRINCIPALS.format(tenant_id=tenant_id, custom_group_id=group_id),
            json={
                "principal_id": "non-existent-user",
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_READ
            },
            headers=headers
        )
        
        # Should succeed (idempotent) or return 404/400
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND, status.HTTP_400_BAD_REQUEST]
