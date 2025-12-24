"""RBAC tests for user favorites API endpoints."""
import uuid
from fastapi import status
from starlette.testclient import TestClient

from aihub.core.database.enums import PermissionActionEnum, PrincipalTypeEnum
from aihub.core.database.models import Application, ApplicationMember
from tests.conftest import create_auth_headers


# API Endpoints
ENDPOINT_USER_FAVORITES = "/api/v1/tenants/{tenant_id}/users/{user_id}/favorites/{resource_type}"
ENDPOINT_USER_FAVORITE_DETAIL = "/api/v1/tenants/{tenant_id}/users/{user_id}/favorites/{resource_type}/{resource_id}"

# Principal Types
PRINCIPAL_TYPE_USER = PrincipalTypeEnum.IDENTITY_USER.value


def create_tenant_for_user(test_client: TestClient, user_token, tenant_name: str = "Test Tenant") -> str:
    """Helper function to create a tenant and return its ID."""
    headers = create_auth_headers(user_token, use_cache=False)
    response = test_client.post(
        "/api/v1/tenants",
        json={"name": tenant_name, "description": f"Tenant for {user_token.get_id()}"},
        headers=headers
    )
    assert response.status_code == status.HTTP_201_CREATED
    return response.json()["id"]


def add_user_to_tenant(
    test_client: TestClient, 
    tenant_id: str, 
    admin_headers: dict, 
    user_id: str,
    role: str = "READER"
) -> None:
    """Helper function to add a user to a tenant."""
    response = test_client.put(
        f"/api/v1/tenants/{tenant_id}/principals",
        json={
            "principal_id": user_id,
            "principal_type": PRINCIPAL_TYPE_USER,
            "role": role
        },
        headers=admin_headers
    )
    assert response.status_code == status.HTTP_200_OK


def create_application_in_db(test_client: TestClient, tenant_id: str, user_id: str, name: str = "Test App") -> str:
    """Helper function to create an application directly in DB and return its ID."""
    app_id = str(uuid.uuid4())
    with test_client.db_client.get_session() as session:
        app = Application(
            id=app_id,
            tenant_id=tenant_id,
            name=name,
            description="Test application",
            config={},
            is_active=True,
            created_by=user_id,
            updated_by=user_id
        )
        session.add(app)
        session.commit()
        
        # Add user as ADMIN member
        member = ApplicationMember(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            application_id=app_id,
            principal_id=user_id,
            principal_type=PrincipalTypeEnum.IDENTITY_USER,
            role=PermissionActionEnum.ADMIN,
            created_by=user_id,
            updated_by=user_id
        )
        session.add(member)
        session.commit()
    return app_id


def add_user_to_application_in_db(
    test_client: TestClient, 
    tenant_id: str, 
    app_id: str, 
    user_id: str, 
    admin_id: str,
    role: PermissionActionEnum = PermissionActionEnum.READ
) -> None:
    """Helper function to add a user to an application directly in DB."""
    with test_client.db_client.get_session() as session:
        member = ApplicationMember(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            application_id=app_id,
            principal_id=user_id,
            principal_type=PrincipalTypeEnum.IDENTITY_USER,
            role=role,
            created_by=admin_id,
            updated_by=admin_id
        )
        session.add(member)
        session.commit()


class TestUserFavoritesRBAC:
    """RBAC test suite for user favorites - only users can manage their own favorites."""
    
    def test_user_cannot_access_other_users_favorites(self, test_client: TestClient) -> None:
        """Test that a user cannot list another user's favorites."""
        # User 1 creates tenant
        user_1_token = test_client.create_test_user("rbac-user-1", "RBAC User 1")
        user_1_headers = create_auth_headers(user_1_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, user_1_token, "RBAC Test Tenant")
        user_1_id = user_1_token.get_id()
        
        # Create user 2 and add to tenant
        user_2_token = test_client.create_test_user("rbac-user-2", "RBAC User 2")
        user_2_id = user_2_token.get_id()
        add_user_to_tenant(test_client, tenant_id, user_1_headers, user_2_id)
        
        # User 2 tries to access User 1's favorites
        user_2_headers = create_auth_headers(user_2_token, use_cache=False)
        response = test_client.get(
            ENDPOINT_USER_FAVORITES.format(
                tenant_id=tenant_id,
                user_id=user_1_id,  # Trying to access another user's favorites
                resource_type="applications"
            ),
            headers=user_2_headers
        )
        
        assert response.status_code == status.HTTP_403_FORBIDDEN
    
    def test_user_cannot_add_favorites_for_other_user(self, test_client: TestClient) -> None:
        """Test that a user cannot add favorites for another user."""
        # User 1 creates tenant
        user_1_token = test_client.create_test_user("rbac-add-user-1", "RBAC Add User 1")
        user_1_headers = create_auth_headers(user_1_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, user_1_token, "RBAC Test Tenant")
        user_1_id = user_1_token.get_id()
        
        # Create user 2 and add to tenant
        user_2_token = test_client.create_test_user("rbac-add-user-2", "RBAC Add User 2")
        user_2_id = user_2_token.get_id()
        add_user_to_tenant(test_client, tenant_id, user_1_headers, user_2_id)
        
        # Create an application directly in DB
        app_id = create_application_in_db(test_client, tenant_id, user_1_id)
        
        # User 2 tries to add favorite for User 1
        user_2_headers = create_auth_headers(user_2_token, use_cache=False)
        response = test_client.put(
            ENDPOINT_USER_FAVORITE_DETAIL.format(
                tenant_id=tenant_id,
                user_id=user_1_id,  # Trying to add to another user's favorites
                resource_type="applications",
                resource_id=app_id
            ),
            headers=user_2_headers
        )
        
        assert response.status_code == status.HTTP_403_FORBIDDEN
    
    def test_user_cannot_delete_other_users_favorites(self, test_client: TestClient) -> None:
        """Test that a user cannot delete another user's favorites."""
        # User 1 creates tenant
        user_1_token = test_client.create_test_user("rbac-del-user-1", "RBAC Del User 1")
        user_1_headers = create_auth_headers(user_1_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, user_1_token, "RBAC Test Tenant")
        user_1_id = user_1_token.get_id()
        
        # Create user 2 and add to tenant
        user_2_token = test_client.create_test_user("rbac-del-user-2", "RBAC Del User 2")
        user_2_id = user_2_token.get_id()
        add_user_to_tenant(test_client, tenant_id, user_1_headers, user_2_id)
        
        # Create an application directly in DB and add to user 1's favorites
        app_id = create_application_in_db(test_client, tenant_id, user_1_id)
        test_client.put(
            ENDPOINT_USER_FAVORITE_DETAIL.format(
                tenant_id=tenant_id,
                user_id=user_1_id,
                resource_type="applications",
                resource_id=app_id
            ),
            headers=user_1_headers
        )
        
        # User 2 tries to delete User 1's favorite
        user_2_headers = create_auth_headers(user_2_token, use_cache=False)
        response = test_client.delete(
            ENDPOINT_USER_FAVORITE_DETAIL.format(
                tenant_id=tenant_id,
                user_id=user_1_id,  # Trying to delete another user's favorites
                resource_type="applications",
                resource_id=app_id
            ),
            headers=user_2_headers
        )
        
        assert response.status_code == status.HTTP_403_FORBIDDEN
        
        # Verify favorite still exists for user 1
        response = test_client.get(
            ENDPOINT_USER_FAVORITES.format(
                tenant_id=tenant_id,
                user_id=user_1_id,
                resource_type="applications"
            ),
            headers=user_1_headers
        )
        assert response.json()["total"] == 1
    
    def test_user_can_manage_own_favorites(self, test_client: TestClient) -> None:
        """Test that a user can manage their own favorites."""
        user_token = test_client.create_test_user("rbac-own-user", "RBAC Own User")
        headers = create_auth_headers(user_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, user_token)
        user_id = user_token.get_id()
        
        # Create application directly in DB
        app_id = create_application_in_db(test_client, tenant_id, user_id)
        
        # User can add favorite
        response = test_client.put(
            ENDPOINT_USER_FAVORITE_DETAIL.format(
                tenant_id=tenant_id,
                user_id=user_id,
                resource_type="applications",
                resource_id=app_id
            ),
            headers=headers
        )
        assert response.status_code == status.HTTP_200_OK
        
        # User can list favorites
        response = test_client.get(
            ENDPOINT_USER_FAVORITES.format(
                tenant_id=tenant_id,
                user_id=user_id,
                resource_type="applications"
            ),
            headers=headers
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["total"] == 1
        
        # User can delete favorite
        response = test_client.delete(
            ENDPOINT_USER_FAVORITE_DETAIL.format(
                tenant_id=tenant_id,
                user_id=user_id,
                resource_type="applications",
                resource_id=app_id
            ),
            headers=headers
        )
        assert response.status_code == status.HTTP_204_NO_CONTENT
    
    def test_unauthenticated_user_cannot_access_favorites(self, test_client: TestClient) -> None:
        """Test that an unauthenticated user cannot access favorites."""
        user_token = test_client.create_test_user("rbac-unauth-user", "RBAC Unauth User")
        tenant_id = create_tenant_for_user(test_client, user_token)
        user_id = user_token.get_id()
        
        # No auth headers
        response = test_client.get(
            ENDPOINT_USER_FAVORITES.format(
                tenant_id=tenant_id,
                user_id=user_id,
                resource_type="applications"
            )
        )
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    def test_user_not_in_tenant_cannot_access_favorites(self, test_client: TestClient) -> None:
        """Test that a user not in the tenant cannot access favorites."""
        # User 1 creates tenant
        user_1_token = test_client.create_test_user("rbac-tenant-user-1", "RBAC Tenant User 1")
        tenant_id = create_tenant_for_user(test_client, user_1_token, "Private Tenant")
        
        # User 2 is NOT added to tenant
        user_2_token = test_client.create_test_user("rbac-tenant-user-2", "RBAC Tenant User 2")
        user_2_id = user_2_token.get_id()
        user_2_headers = create_auth_headers(user_2_token, use_cache=False)
        
        # User 2 tries to access their own favorites in this tenant
        response = test_client.get(
            ENDPOINT_USER_FAVORITES.format(
                tenant_id=tenant_id,
                user_id=user_2_id,
                resource_type="applications"
            ),
            headers=user_2_headers
        )
        
        # Should fail because user is not a member of the tenant
        assert response.status_code == status.HTTP_403_FORBIDDEN


class TestUserFavoritesIsolation:
    """Tests for user favorites isolation between users."""
    
    def test_favorites_isolated_between_users(self, test_client: TestClient) -> None:
        """Test that favorites are properly isolated between users."""
        # User 1 creates tenant
        user_1_token = test_client.create_test_user("iso-user-1", "Isolation User 1")
        user_1_headers = create_auth_headers(user_1_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, user_1_token, "Shared Tenant")
        user_1_id = user_1_token.get_id()
        
        # Create user 2 and add to tenant
        user_2_token = test_client.create_test_user("iso-user-2", "Isolation User 2")
        user_2_id = user_2_token.get_id()
        add_user_to_tenant(test_client, tenant_id, user_1_headers, user_2_id)
        
        # Create an application directly in DB
        app_id = create_application_in_db(test_client, tenant_id, user_1_id)
        
        # Give user 2 access to the application directly in DB
        add_user_to_application_in_db(test_client, tenant_id, app_id, user_2_id, user_1_id)
        
        # User 1 adds app to favorites
        test_client.put(
            ENDPOINT_USER_FAVORITE_DETAIL.format(
                tenant_id=tenant_id,
                user_id=user_1_id,
                resource_type="applications",
                resource_id=app_id
            ),
            headers=user_1_headers
        )
        
        # User 2 should have empty favorites
        user_2_headers = create_auth_headers(user_2_token, use_cache=False)
        response = test_client.get(
            ENDPOINT_USER_FAVORITES.format(
                tenant_id=tenant_id,
                user_id=user_2_id,
                resource_type="applications"
            ),
            headers=user_2_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["total"] == 0
        
        # User 2 adds their own favorite
        test_client.put(
            ENDPOINT_USER_FAVORITE_DETAIL.format(
                tenant_id=tenant_id,
                user_id=user_2_id,
                resource_type="applications",
                resource_id=app_id
            ),
            headers=user_2_headers
        )
        
        # Now both users have one favorite
        response = test_client.get(
            ENDPOINT_USER_FAVORITES.format(
                tenant_id=tenant_id,
                user_id=user_2_id,
                resource_type="applications"
            ),
            headers=user_2_headers
        )
        assert response.json()["total"] == 1
        
        response = test_client.get(
            ENDPOINT_USER_FAVORITES.format(
                tenant_id=tenant_id,
                user_id=user_1_id,
                resource_type="applications"
            ),
            headers=user_1_headers
        )
        assert response.json()["total"] == 1
        
        # User 1 deletes their favorite
        test_client.delete(
            ENDPOINT_USER_FAVORITE_DETAIL.format(
                tenant_id=tenant_id,
                user_id=user_1_id,
                resource_type="applications",
                resource_id=app_id
            ),
            headers=user_1_headers
        )
        
        # User 2's favorite should still exist
        response = test_client.get(
            ENDPOINT_USER_FAVORITES.format(
                tenant_id=tenant_id,
                user_id=user_2_id,
                resource_type="applications"
            ),
            headers=user_2_headers
        )
        assert response.json()["total"] == 1
