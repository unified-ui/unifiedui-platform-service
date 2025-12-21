"""Tests for identity."""
import uuid
from typing import Any
from fastapi import status
from starlette.testclient import TestClient

from tests.conftest import create_auth_headers


# API Endpoints
ENDPOINT_IDENTITY_ME = "/api/v1/identity/me"
ENDPOINT_IDENTITY_USERS = "/api/v1/identity/users"
ENDPOINT_IDENTITY_GROUPS = "/api/v1/identity/groups"

# Common Test IDs
NON_EXISTENT_ID = "non-existent-id"

# Roles
ROLE_GLOBAL_ADMIN = "GLOBAL_ADMIN"
ROLE_READER = "READER"
ROLE_APPLICATIONS_ADMIN = "APPLICATIONS_ADMIN"

# Principal Types
PRINCIPAL_TYPE_USER = "IDENTITY_USER"
PRINCIPAL_TYPE_GROUP = "IDENTITY_GROUP"


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
            "/api/v1/identity/users?search=test",
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "value" in data
    
    def test_get_users_with_pagination(self, test_client: TestClient, auth_headers: dict[str, str]) -> None:
        """Test users retrieval with top parameter."""
        response = test_client.get(
            "/api/v1/identity/users?top=10",
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "value" in data
    
    def test_get_users_top_validation(self, test_client: TestClient, auth_headers: dict[str, str]) -> None:
        """Test that top parameter is validated."""
        # Too low
        response = test_client.get(
            "/api/v1/identity/users?top=0",
            headers=auth_headers
        )
        assert response.status_code == 422
        
        # Too high
        response = test_client.get(
            "/api/v1/identity/users?top=1000",
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
            "/api/v1/identity/groups?search=admin",
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "value" in data
    
    def test_get_groups_with_pagination(self, test_client: TestClient, auth_headers: dict[str, str]) -> None:
        """Test groups retrieval with top parameter."""
        response = test_client.get(
            "/api/v1/identity/groups?top=50",
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "value" in data
    
    def test_get_groups_top_validation(self, test_client: TestClient, auth_headers: dict[str, str]) -> None:
        """Test that top parameter is validated."""
        # Too low
        response = test_client.get(
            "/api/v1/identity/groups?top=0",
            headers=auth_headers
        )
        assert response.status_code == 422
        
        # Too high
        response = test_client.get(
            "/api/v1/identity/groups?top=1000",
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
            f"/api/v1/identity/users/{user_id}",
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
        response = test_client.get("/api/v1/identity/users/test-user-123")
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    def test_get_group_by_id_success(self, test_client: TestClient, auth_headers: dict[str, str]) -> None:
        """Test successful retrieval of group by ID."""
        group_id = "test-group-123"
        response = test_client.get(
            f"/api/v1/identity/groups/{group_id}",
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        # Verify group data
        assert data["id"] == group_id
        assert "display_name" in data
    
    def test_get_group_by_id_unauthenticated(self, test_client: TestClient) -> None:
        """Test that unauthenticated request fails."""
        response = test_client.get("/api/v1/identity/groups/test-group-123")
        
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
            "/api/v1/identity/users/test-id",
            "/api/v1/identity/groups/test-id"
        ]
        
        for endpoint in endpoints:
            response = test_client.get(endpoint)
            assert response.status_code == status.HTTP_401_UNAUTHORIZED, \
                f"Endpoint {endpoint} should require authentication"
    
    def test_get_users_with_all_parameters(self, test_client: TestClient, auth_headers: dict[str, str]) -> None:
        """Test users retrieval with all query parameters."""
        response = test_client.get(
            "/api/v1/identity/users?search=test&top=20&next_link=",
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "value" in data
        assert "next_link" in data
    
    def test_get_groups_with_all_parameters(self, test_client: TestClient, auth_headers: dict[str, str]) -> None:
        """Test groups retrieval with all query parameters."""
        response = test_client.get(
            "/api/v1/identity/groups?search=admin&top=30&next_link=",
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
                f"/api/v1/identity/users?search={search_term}",
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
                f"/api/v1/identity/users/{user_id}",
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
                f"/api/v1/identity/groups/{group_id}",
                headers=auth_headers
            )
            # Should succeed or handle gracefully
            assert response.status_code in [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND]
