"""Caching tests for user favorites API endpoints."""
import uuid
from fastapi import status
from starlette.testclient import TestClient

from unifiedui.core.database.enums import PermissionActionEnum, PrincipalTypeEnum
from unifiedui.core.database.models import Application, ApplicationMember
from tests.conftest import create_auth_headers


# API Endpoints
ENDPOINT_USER_FAVORITES = "/api/v1/tenants/{tenant_id}/users/{user_id}/favorites/{resource_type}"
ENDPOINT_USER_FAVORITE_DETAIL = "/api/v1/tenants/{tenant_id}/users/{user_id}/favorites/{resource_type}/{resource_id}"

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


def add_user_to_tenant(test_client: TestClient, tenant_id: str, admin_headers: dict, user_id: str) -> None:
    """Helper function to add a user to a tenant."""
    response = test_client.put(
        f"/api/v1/tenants/{tenant_id}/principals",
        json={
            "principal_id": user_id,
            "principal_type": PRINCIPAL_TYPE_USER,
            "role": "READER"
        },
        headers=admin_headers
    )
    assert response.status_code in [status.HTTP_200_OK, status.HTTP_201_CREATED]


def create_application_in_db(test_client: TestClient, tenant_id: str, user_id: str, name: str = "Test App") -> str:
    """Helper function to create an application directly in DB and return its ID."""
    app_id = str(uuid.uuid4())
    with test_client.db_client.get_session() as session:
        app = Application(
            id=app_id,
            tenant_id=tenant_id,
            name=name,
            description="Test application",
            type="N8N",
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


class TestUserFavoritesCaching:
    """Test suite for user favorites caching."""
    
    def test_list_favorites_cached_response(self, test_client: TestClient) -> None:
        """Test that list favorites response is cached."""
        user_token = test_client.create_test_user("cache-list-user", "Cache List User")
        headers_no_cache = create_auth_headers(user_token, use_cache=False)
        headers_cache = create_auth_headers(user_token, use_cache=True)
        tenant_id = create_tenant_for_user(test_client, user_token)
        user_id = user_token.get_id()
        
        # Create application directly in DB and add to favorites
        app_id = create_application_in_db(test_client, tenant_id, user_id)
        test_client.put(
            ENDPOINT_USER_FAVORITE_DETAIL.format(
                tenant_id=tenant_id,
                user_id=user_id,
                resource_type="applications",
                resource_id=app_id
            ),
            headers=headers_no_cache
        )
        
        # First request without cache - should populate cache
        response1 = test_client.get(
            ENDPOINT_USER_FAVORITES.format(
                tenant_id=tenant_id,
                user_id=user_id,
                resource_type="applications"
            ),
            headers=headers_no_cache
        )
        assert response1.status_code == status.HTTP_200_OK
        assert response1.json()["total"] == 1
        
        # Second request with cache - should use cached response
        response2 = test_client.get(
            ENDPOINT_USER_FAVORITES.format(
                tenant_id=tenant_id,
                user_id=user_id,
                resource_type="applications"
            ),
            headers=headers_cache
        )
        assert response2.status_code == status.HTTP_200_OK
        assert response2.json()["total"] == 1
    
    def test_cache_invalidated_on_add_favorite(self, test_client: TestClient) -> None:
        """Test that cache is invalidated when a favorite is added."""
        user_token = test_client.create_test_user("cache-add-user", "Cache Add User")
        headers_no_cache = create_auth_headers(user_token, use_cache=False)
        headers_cache = create_auth_headers(user_token, use_cache=True)
        tenant_id = create_tenant_for_user(test_client, user_token)
        user_id = user_token.get_id()
        
        # Create applications directly in DB
        app_id1 = create_application_in_db(test_client, tenant_id, user_id, "App 1")
        app_id2 = create_application_in_db(test_client, tenant_id, user_id, "App 2")
        
        # Add first app to favorites
        test_client.put(
            ENDPOINT_USER_FAVORITE_DETAIL.format(
                tenant_id=tenant_id,
                user_id=user_id,
                resource_type="applications",
                resource_id=app_id1
            ),
            headers=headers_no_cache
        )
        
        # First list (populates cache)
        response1 = test_client.get(
            ENDPOINT_USER_FAVORITES.format(
                tenant_id=tenant_id,
                user_id=user_id,
                resource_type="applications"
            ),
            headers=headers_no_cache
        )
        assert response1.json()["total"] == 1
        
        # Add second app (should invalidate cache)
        test_client.put(
            ENDPOINT_USER_FAVORITE_DETAIL.format(
                tenant_id=tenant_id,
                user_id=user_id,
                resource_type="applications",
                resource_id=app_id2
            ),
            headers=headers_no_cache
        )
        
        # Second list with cache header - should show updated data due to invalidation
        response2 = test_client.get(
            ENDPOINT_USER_FAVORITES.format(
                tenant_id=tenant_id,
                user_id=user_id,
                resource_type="applications"
            ),
            headers=headers_cache
        )
        assert response2.json()["total"] == 2
    
    def test_cache_invalidated_on_remove_favorite(self, test_client: TestClient) -> None:
        """Test that cache is invalidated when a favorite is removed."""
        user_token = test_client.create_test_user("cache-remove-user", "Cache Remove User")
        headers_no_cache = create_auth_headers(user_token, use_cache=False)
        headers_cache = create_auth_headers(user_token, use_cache=True)
        tenant_id = create_tenant_for_user(test_client, user_token)
        user_id = user_token.get_id()
        
        # Create applications directly in DB and add to favorites
        app_id1 = create_application_in_db(test_client, tenant_id, user_id, "App 1")
        app_id2 = create_application_in_db(test_client, tenant_id, user_id, "App 2")
        
        test_client.put(
            ENDPOINT_USER_FAVORITE_DETAIL.format(
                tenant_id=tenant_id,
                user_id=user_id,
                resource_type="applications",
                resource_id=app_id1
            ),
            headers=headers_no_cache
        )
        test_client.put(
            ENDPOINT_USER_FAVORITE_DETAIL.format(
                tenant_id=tenant_id,
                user_id=user_id,
                resource_type="applications",
                resource_id=app_id2
            ),
            headers=headers_no_cache
        )
        
        # First list (populates cache)
        response1 = test_client.get(
            ENDPOINT_USER_FAVORITES.format(
                tenant_id=tenant_id,
                user_id=user_id,
                resource_type="applications"
            ),
            headers=headers_no_cache
        )
        assert response1.json()["total"] == 2
        
        # Remove one favorite (should invalidate cache)
        test_client.delete(
            ENDPOINT_USER_FAVORITE_DETAIL.format(
                tenant_id=tenant_id,
                user_id=user_id,
                resource_type="applications",
                resource_id=app_id1
            ),
            headers=headers_no_cache
        )
        
        # Second list with cache header - should show updated data due to invalidation
        response2 = test_client.get(
            ENDPOINT_USER_FAVORITES.format(
                tenant_id=tenant_id,
                user_id=user_id,
                resource_type="applications"
            ),
            headers=headers_cache
        )
        assert response2.json()["total"] == 1
    
    def test_cache_isolated_between_resource_types(self, test_client: TestClient) -> None:
        """Test that cache is isolated between different resource types."""
        user_token = test_client.create_test_user("cache-type-user", "Cache Type User")
        headers_no_cache = create_auth_headers(user_token, use_cache=False)
        headers_cache = create_auth_headers(user_token, use_cache=True)
        tenant_id = create_tenant_for_user(test_client, user_token)
        user_id = user_token.get_id()
        
        # Create application directly in DB and add to favorites
        app_id = create_application_in_db(test_client, tenant_id, user_id)
        test_client.put(
            ENDPOINT_USER_FAVORITE_DETAIL.format(
                tenant_id=tenant_id,
                user_id=user_id,
                resource_type="applications",
                resource_id=app_id
            ),
            headers=headers_no_cache
        )
        
        # List applications favorites (populates cache)
        response1 = test_client.get(
            ENDPOINT_USER_FAVORITES.format(
                tenant_id=tenant_id,
                user_id=user_id,
                resource_type="applications"
            ),
            headers=headers_no_cache
        )
        assert response1.json()["total"] == 1
        
        # List autonomous-agents favorites - should be separate cache
        response2 = test_client.get(
            ENDPOINT_USER_FAVORITES.format(
                tenant_id=tenant_id,
                user_id=user_id,
                resource_type="autonomous-agents"
            ),
            headers=headers_cache
        )
        assert response2.json()["total"] == 0
        
        # Applications cache should still work
        response3 = test_client.get(
            ENDPOINT_USER_FAVORITES.format(
                tenant_id=tenant_id,
                user_id=user_id,
                resource_type="applications"
            ),
            headers=headers_cache
        )
        assert response3.json()["total"] == 1
    
    def test_cache_isolated_between_users(self, test_client: TestClient) -> None:
        """Test that cache is isolated between different users."""
        # User 1 creates tenant
        user_1_token = test_client.create_test_user("cache-iso-user-1", "Cache Iso User 1")
        user_1_headers = create_auth_headers(user_1_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, user_1_token, "Cache Test Tenant")
        user_1_id = user_1_token.get_id()
        
        # Create user 2 and add to tenant
        user_2_token = test_client.create_test_user("cache-iso-user-2", "Cache Iso User 2")
        user_2_id = user_2_token.get_id()
        add_user_to_tenant(test_client, tenant_id, user_1_headers, user_2_id)
        user_2_headers = create_auth_headers(user_2_token, use_cache=False)
        
        # Create application directly in DB
        app_id = create_application_in_db(test_client, tenant_id, user_1_id)
        
        # Give user 2 access to app directly in DB
        add_user_to_application_in_db(test_client, tenant_id, app_id, user_2_id, user_1_id)
        
        # User 1 adds favorite
        test_client.put(
            ENDPOINT_USER_FAVORITE_DETAIL.format(
                tenant_id=tenant_id,
                user_id=user_1_id,
                resource_type="applications",
                resource_id=app_id
            ),
            headers=user_1_headers
        )
        
        # User 1 list populates their cache
        response1 = test_client.get(
            ENDPOINT_USER_FAVORITES.format(
                tenant_id=tenant_id,
                user_id=user_1_id,
                resource_type="applications"
            ),
            headers=user_1_headers
        )
        assert response1.json()["total"] == 1
        
        # User 2 list - should have separate cache and see 0 favorites
        response2 = test_client.get(
            ENDPOINT_USER_FAVORITES.format(
                tenant_id=tenant_id,
                user_id=user_2_id,
                resource_type="applications"
            ),
            headers=user_2_headers
        )
        assert response2.json()["total"] == 0
