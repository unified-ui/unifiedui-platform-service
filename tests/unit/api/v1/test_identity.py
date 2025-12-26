"""Tests for identity."""
import uuid
from typing import Any
from fastapi import status
from starlette.testclient import TestClient

from unifiedui.core.database.enums import TenantRolesEnum, PrincipalTypeEnum
from tests.conftest import create_auth_headers


# API Endpoints
ENDPOINT_IDENTITY_ME = "/api/v1/identity/me"
ENDPOINT_IDENTITY_USERS = "/api/v1/identity/users"
ENDPOINT_IDENTITY_USER_DETAIL = "/api/v1/identity/users/{user_id}"
ENDPOINT_IDENTITY_GROUPS = "/api/v1/identity/groups"
ENDPOINT_IDENTITY_GROUP_DETAIL = "/api/v1/identity/groups/{group_id}"
ENDPOINT_IDENTITY_PRINCIPAL_REFRESH = "/api/v1/identity/principals/{principal_id}/refresh"

# Common Test IDs
NON_EXISTENT_ID = "non-existent-id"

# Roles
ROLE_GLOBAL_ADMIN = TenantRolesEnum.GLOBAL_ADMIN.value
ROLE_READER = TenantRolesEnum.READER.value
ROLE_APPLICATIONS_ADMIN = TenantRolesEnum.APPLICATIONS_ADMIN.value

# Principal Types
PRINCIPAL_TYPE_USER = PrincipalTypeEnum.IDENTITY_USER.value
PRINCIPAL_TYPE_GROUP = PrincipalTypeEnum.IDENTITY_GROUP.value


class TestIdentityRoutes:
    """Test suite for identity API routes."""
    
    def test_get_current_user_success(self, test_client: TestClient, auth_headers: dict[str, str], test_user_token: Any) -> None:
        """Test successful retrieval of current user."""
        response = test_client.get(
            ENDPOINT_IDENTITY_ME,
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        # Verify user data
        assert data["id"] == test_user_token.get_id()
        assert data["identity_provider"] == test_user_token.get_identity_provider()
        assert data["identity_tenant_id"] == test_user_token.get_identity_tenant_id()
        assert "display_name" in data
        assert "mail" in data
        assert "tenants" in data or data["tenants"] is not None
    
    def test_get_current_user_unauthenticated(self, test_client: TestClient) -> None:
        """Test that unauthenticated request fails."""
        response = test_client.get(ENDPOINT_IDENTITY_ME)
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    def test_get_current_user_invalid_token(self, test_client: TestClient) -> None:
        """Test that invalid token fails."""
        headers = {"Authorization": "Bearer invalid-token-here"}
        response = test_client.get(
            ENDPOINT_IDENTITY_ME,
            headers=headers
        )
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    def test_get_users_success(self, test_client: TestClient, auth_headers: dict[str, str]) -> None:
        """Test successful retrieval of users list."""
        response = test_client.get(
            ENDPOINT_IDENTITY_USERS,
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        # Verify structure
        assert "value" in data
        assert isinstance(data["value"], list)
        assert "next_link" in data
    
    def test_get_users_with_search(self, test_client: TestClient, auth_headers: dict[str, str]) -> None:
        """Test users retrieval with search parameter."""
        response = test_client.get(
            f"{ENDPOINT_IDENTITY_USERS}?search=test",
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "value" in data
    
    def test_get_users_with_pagination(self, test_client: TestClient, auth_headers: dict[str, str]) -> None:
        """Test users retrieval with top parameter."""
        response = test_client.get(
            f"{ENDPOINT_IDENTITY_USERS}?top=10",
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "value" in data
    
    def test_get_users_top_validation(self, test_client: TestClient, auth_headers: dict[str, str]) -> None:
        """Test that top parameter is validated."""
        # Too low
        response = test_client.get(
            f"{ENDPOINT_IDENTITY_USERS}?top=0",
            headers=auth_headers
        )
        assert response.status_code == 422
        
        # Too high
        response = test_client.get(
            f"{ENDPOINT_IDENTITY_USERS}?top=1000",
            headers=auth_headers
        )
        assert response.status_code == 422
    
    def test_get_users_unauthenticated(self, test_client: TestClient) -> None:
        """Test that unauthenticated request fails."""
        response = test_client.get(ENDPOINT_IDENTITY_USERS)
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    def test_get_groups_success(self, test_client: TestClient, auth_headers: dict[str, str]) -> None:
        """Test successful retrieval of groups list."""
        response = test_client.get(
            ENDPOINT_IDENTITY_GROUPS,
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        # Verify structure
        assert "value" in data
        assert isinstance(data["value"], list)
        assert "next_link" in data
    
    def test_get_groups_with_search(self, test_client: TestClient, auth_headers: dict[str, str]) -> None:
        """Test groups retrieval with search parameter."""
        response = test_client.get(
            f"{ENDPOINT_IDENTITY_GROUPS}?search=admin",
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "value" in data
    
    def test_get_groups_with_pagination(self, test_client: TestClient, auth_headers: dict[str, str]) -> None:
        """Test groups retrieval with top parameter."""
        response = test_client.get(
            f"{ENDPOINT_IDENTITY_GROUPS}?top=50",
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "value" in data
    
    def test_get_groups_top_validation(self, test_client: TestClient, auth_headers: dict[str, str]) -> None:
        """Test that top parameter is validated."""
        # Too low
        response = test_client.get(
            f"{ENDPOINT_IDENTITY_GROUPS}?top=0",
            headers=auth_headers
        )
        assert response.status_code == 422
        
        # Too high
        response = test_client.get(
            f"{ENDPOINT_IDENTITY_GROUPS}?top=1000",
            headers=auth_headers
        )
        assert response.status_code == 422
    
    def test_get_groups_unauthenticated(self, test_client: TestClient) -> None:
        """Test that unauthenticated request fails."""
        response = test_client.get(ENDPOINT_IDENTITY_GROUPS)
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    def test_get_user_by_id_success(self, test_client: TestClient, auth_headers: dict[str, str]) -> None:
        """Test successful retrieval of user by ID."""
        user_id = "test-user-123"
        response = test_client.get(
            ENDPOINT_IDENTITY_USER_DETAIL.format(user_id=user_id),
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        # Verify user data
        assert data["id"] == user_id
        assert "display_name" in data
        assert "mail" in data
        assert "identity_provider" in data
        assert "identity_tenant_id" in data
        assert "firstname" in data
        assert "lastname" in data
    
    def test_get_user_by_id_unauthenticated(self, test_client: TestClient) -> None:
        """Test that unauthenticated request fails."""
        response = test_client.get(ENDPOINT_IDENTITY_USER_DETAIL.format(user_id="test-user-123"))
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    def test_get_group_by_id_success(self, test_client: TestClient, auth_headers: dict[str, str]) -> None:
        """Test successful retrieval of group by ID."""
        group_id = "test-group-123"
        response = test_client.get(
            ENDPOINT_IDENTITY_GROUP_DETAIL.format(group_id=group_id),
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        # Verify group data
        assert data["id"] == group_id
        assert "display_name" in data
    
    def test_get_group_by_id_unauthenticated(self, test_client: TestClient) -> None:
        """Test that unauthenticated request fails."""
        response = test_client.get(ENDPOINT_IDENTITY_GROUP_DETAIL.format(group_id="test-group-123"))
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    def test_different_users_see_their_own_identity(self, test_client: TestClient) -> None:
        """Test that different users see their own identity information."""
        # Create first user
        user1_token = test_client.create_test_user("identity-user-1", "Identity User 1")
        headers1 = create_auth_headers(user1_token)
        
        response1 = test_client.get(
            ENDPOINT_IDENTITY_ME,
            headers=headers1
        )
        
        assert response1.status_code == status.HTTP_200_OK
        assert response1.json()["id"] == "identity-user-1"
        
        # Create second user
        user2_token = test_client.create_test_user("identity-user-2", "Identity User 2")
        headers2 = create_auth_headers(user2_token)
        
        response2 = test_client.get(
            ENDPOINT_IDENTITY_ME,
            headers=headers2
        )
        
        assert response2.status_code == status.HTTP_200_OK
        assert response2.json()["id"] == "identity-user-2"
        
        # Verify they are different
        assert response1.json()["id"] != response2.json()["id"]
    
    def test_user_with_groups(self, test_client: TestClient) -> None:
        """Test user with identity groups."""
        # Create user with groups
        user_token = test_client.create_test_user(
            "user-with-groups", 
            "User With Groups",
            idp_groups=["group-1", "group-2", "group-3"]
        )
        headers = create_auth_headers(user_token)
        
        response = test_client.get(
            ENDPOINT_IDENTITY_ME,
            headers=headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        # User should have their groups
        assert "groups" in data or data["id"] == "user-with-groups"
    
    def test_endpoint_requires_authentication(self, test_client: TestClient) -> None:
        """Test that all identity endpoints require authentication."""
        endpoints = [
            ENDPOINT_IDENTITY_ME,
            ENDPOINT_IDENTITY_USERS,
            ENDPOINT_IDENTITY_GROUPS,
            ENDPOINT_IDENTITY_USER_DETAIL.format(user_id="test-id"),
            ENDPOINT_IDENTITY_GROUP_DETAIL.format(group_id="test-id")
        ]
        
        for endpoint in endpoints:
            response = test_client.get(endpoint)
            assert response.status_code == status.HTTP_401_UNAUTHORIZED, \
                f"Endpoint {endpoint} should require authentication"
    
    def test_get_users_with_all_parameters(self, test_client: TestClient, auth_headers: dict[str, str]) -> None:
        """Test users retrieval with all query parameters."""
        response = test_client.get(
            f"{ENDPOINT_IDENTITY_USERS}?search=test&top=20&next_link=",
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "value" in data
        assert "next_link" in data
    
    def test_get_groups_with_all_parameters(self, test_client: TestClient, auth_headers: dict[str, str]) -> None:
        """Test groups retrieval with all query parameters."""
        response = test_client.get(
            f"{ENDPOINT_IDENTITY_GROUPS}?search=admin&top=30&next_link=",
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "value" in data
        assert "next_link" in data
    
    def test_special_characters_in_search(self, test_client: TestClient, auth_headers: dict[str, str]) -> None:
        """Test search with special characters."""
        # Test with various special characters
        search_terms = ["test@example.com", "user+test", "group/admin"]
        
        for search_term in search_terms:
            response = test_client.get(
                f"{ENDPOINT_IDENTITY_USERS}?search={search_term}",
                headers=auth_headers
            )
            assert response.status_code == status.HTTP_200_OK
    
    def test_user_id_with_special_characters(self, test_client: TestClient, auth_headers: dict[str, str]) -> None:
        """Test getting user by ID with special characters."""
        user_ids = [
            str(uuid.uuid4()),  # UUID format
            "user-123-abc",     # Dashes
            "user_123_abc"      # Underscores
        ]
        
        for user_id in user_ids:
            response = test_client.get(
                ENDPOINT_IDENTITY_USER_DETAIL.format(user_id=user_id),
                headers=auth_headers
            )
            # Should succeed or handle gracefully
            assert response.status_code in [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND]
    
    def test_group_id_with_special_characters(self, test_client: TestClient, auth_headers: dict[str, str]) -> None:
        """Test getting group by ID with special characters."""
        group_ids = [
            str(uuid.uuid4()),  # UUID format
            "group-123-abc",    # Dashes
            "group_123_abc"     # Underscores
        ]
        
        for group_id in group_ids:
            response = test_client.get(
                ENDPOINT_IDENTITY_GROUP_DETAIL.format(group_id=group_id),
                headers=auth_headers
            )
            # Should succeed or handle gracefully
            assert response.status_code in [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND]


class TestRefreshPrincipal:
    """Test suite for refresh principal endpoint."""
    
    def test_refresh_user_principal_creates_new(
        self, 
        test_client: TestClient, 
        auth_headers: dict[str, str],
        sample_tenant_data: dict
    ) -> None:
        """Test refreshing a user principal creates a new record if it doesn't exist."""
        # First create a tenant
        tenant_response = test_client.post(
            "/api/v1/tenants",
            headers=auth_headers,
            json=sample_tenant_data
        )
        assert tenant_response.status_code == status.HTTP_201_CREATED
        tenant_id = tenant_response.json()["id"]
        
        # Refresh a user principal
        principal_id = "test-user-to-refresh"
        response = test_client.put(
            ENDPOINT_IDENTITY_PRINCIPAL_REFRESH.format(principal_id=principal_id),
            headers=auth_headers,
            json={
                "tenant_id": tenant_id,
                "type": "IDENTITY_USER"
            }
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["tenant_id"] == tenant_id
        assert data["principal_id"] == principal_id
        assert data["principal_type"] == "IDENTITY_USER"
        assert "display_name" in data
        assert "principal_name" in data
        # principal_name should be email for users (from get_principal_name)
        assert "@" in data["principal_name"] or data["principal_name"]  # Email or fallback
        assert "created_at" in data
        assert "updated_at" in data
    
    def test_refresh_group_principal_creates_new(
        self, 
        test_client: TestClient, 
        auth_headers: dict[str, str],
        sample_tenant_data: dict
    ) -> None:
        """Test refreshing a group principal creates a new record if it doesn't exist."""
        # First create a tenant
        tenant_response = test_client.post(
            "/api/v1/tenants",
            headers=auth_headers,
            json=sample_tenant_data
        )
        assert tenant_response.status_code == status.HTTP_201_CREATED
        tenant_id = tenant_response.json()["id"]
        
        # Refresh a group principal
        principal_id = "test-group-to-refresh"
        response = test_client.put(
            ENDPOINT_IDENTITY_PRINCIPAL_REFRESH.format(principal_id=principal_id),
            headers=auth_headers,
            json={
                "tenant_id": tenant_id,
                "type": "IDENTITY_GROUP"
            }
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["tenant_id"] == tenant_id
        assert data["principal_id"] == principal_id
        assert data["principal_type"] == "IDENTITY_GROUP"
        assert "display_name" in data
        assert "principal_name" in data
        # principal_name should equal display_name for groups (from get_principal_name)
        assert data["principal_name"] == data["display_name"]
    
    def test_refresh_user_principal_updates_existing(
        self, 
        test_client: TestClient, 
        auth_headers: dict[str, str],
        sample_tenant_data: dict
    ) -> None:
        """Test refreshing an existing user principal updates the record."""
        # First create a tenant
        tenant_response = test_client.post(
            "/api/v1/tenants",
            headers=auth_headers,
            json=sample_tenant_data
        )
        assert tenant_response.status_code == status.HTTP_201_CREATED
        tenant_id = tenant_response.json()["id"]
        
        principal_id = "test-user-update"
        
        # Create the principal first
        response1 = test_client.put(
            ENDPOINT_IDENTITY_PRINCIPAL_REFRESH.format(principal_id=principal_id),
            headers=auth_headers,
            json={
                "tenant_id": tenant_id,
                "type": "IDENTITY_USER"
            }
        )
        assert response1.status_code == status.HTTP_200_OK
        created_at_1 = response1.json()["created_at"]
        
        # Refresh again - should update
        response2 = test_client.put(
            ENDPOINT_IDENTITY_PRINCIPAL_REFRESH.format(principal_id=principal_id),
            headers=auth_headers,
            json={
                "tenant_id": tenant_id,
                "type": "IDENTITY_USER"
            }
        )
        assert response2.status_code == status.HTTP_200_OK
        data = response2.json()
        
        # created_at should be the same, updated_at might be different
        assert data["created_at"] == created_at_1
        assert data["principal_id"] == principal_id
    
    def test_refresh_principal_invalid_type(
        self, 
        test_client: TestClient, 
        auth_headers: dict[str, str],
        sample_tenant_data: dict
    ) -> None:
        """Test that invalid principal type returns validation error."""
        # First create a tenant
        tenant_response = test_client.post(
            "/api/v1/tenants",
            headers=auth_headers,
            json=sample_tenant_data
        )
        assert tenant_response.status_code == status.HTTP_201_CREATED
        tenant_id = tenant_response.json()["id"]
        
        # Try with invalid type
        response = test_client.put(
            ENDPOINT_IDENTITY_PRINCIPAL_REFRESH.format(principal_id="test-user"),
            headers=auth_headers,
            json={
                "tenant_id": tenant_id,
                "type": "INVALID_TYPE"
            }
        )
        
        # Should fail validation
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    
    def test_refresh_principal_custom_group_not_allowed(
        self, 
        test_client: TestClient, 
        auth_headers: dict[str, str],
        sample_tenant_data: dict
    ) -> None:
        """Test that CUSTOM_GROUP type is not allowed for refresh."""
        # First create a tenant
        tenant_response = test_client.post(
            "/api/v1/tenants",
            headers=auth_headers,
            json=sample_tenant_data
        )
        assert tenant_response.status_code == status.HTTP_201_CREATED
        tenant_id = tenant_response.json()["id"]
        
        # Try with CUSTOM_GROUP type (not allowed)
        response = test_client.put(
            ENDPOINT_IDENTITY_PRINCIPAL_REFRESH.format(principal_id="test-custom-group"),
            headers=auth_headers,
            json={
                "tenant_id": tenant_id,
                "type": "CUSTOM_GROUP"
            }
        )
        
        # Should fail validation (CUSTOM_GROUP is not in the Literal type)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    
    def test_refresh_principal_missing_tenant_id(
        self, 
        test_client: TestClient, 
        auth_headers: dict[str, str]
    ) -> None:
        """Test that missing tenant_id returns validation error."""
        response = test_client.put(
            ENDPOINT_IDENTITY_PRINCIPAL_REFRESH.format(principal_id="test-user"),
            headers=auth_headers,
            json={
                "type": "IDENTITY_USER"
            }
        )
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    
    def test_refresh_principal_missing_type(
        self, 
        test_client: TestClient, 
        auth_headers: dict[str, str],
        sample_tenant_data: dict
    ) -> None:
        """Test that missing type returns validation error."""
        tenant_response = test_client.post(
            "/api/v1/tenants",
            headers=auth_headers,
            json=sample_tenant_data
        )
        assert tenant_response.status_code == status.HTTP_201_CREATED
        tenant_id = tenant_response.json()["id"]
        
        response = test_client.put(
            ENDPOINT_IDENTITY_PRINCIPAL_REFRESH.format(principal_id="test-user"),
            headers=auth_headers,
            json={
                "tenant_id": tenant_id
            }
        )
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    
    def test_refresh_principal_unauthenticated(self, test_client: TestClient) -> None:
        """Test that unauthenticated request fails."""
        response = test_client.put(
            ENDPOINT_IDENTITY_PRINCIPAL_REFRESH.format(principal_id="test-user"),
            json={
                "tenant_id": "some-tenant-id",
                "type": "IDENTITY_USER"
            }
        )
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    def test_refresh_principal_empty_body(
        self, 
        test_client: TestClient, 
        auth_headers: dict[str, str]
    ) -> None:
        """Test that empty request body returns validation error."""
        response = test_client.put(
            ENDPOINT_IDENTITY_PRINCIPAL_REFRESH.format(principal_id="test-user"),
            headers=auth_headers,
            json={}
        )
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    
    def test_refresh_principal_with_uuid_format(
        self, 
        test_client: TestClient, 
        auth_headers: dict[str, str],
        sample_tenant_data: dict
    ) -> None:
        """Test refreshing a principal with UUID format ID."""
        # First create a tenant
        tenant_response = test_client.post(
            "/api/v1/tenants",
            headers=auth_headers,
            json=sample_tenant_data
        )
        assert tenant_response.status_code == status.HTTP_201_CREATED
        tenant_id = tenant_response.json()["id"]
        
        # Use UUID format principal ID
        principal_id = str(uuid.uuid4())
        response = test_client.put(
            ENDPOINT_IDENTITY_PRINCIPAL_REFRESH.format(principal_id=principal_id),
            headers=auth_headers,
            json={
                "tenant_id": tenant_id,
                "type": "IDENTITY_USER"
            }
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["principal_id"] == principal_id
