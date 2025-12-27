"""Tests for chat widgets caching behavior."""
from typing import Any
from fastapi import status
from starlette.testclient import TestClient

from unifiedui.core.database.enums import PermissionActionEnum, PrincipalTypeEnum
from tests.conftest import create_auth_headers


# API Endpoints
ENDPOINT_TENANTS = "/api/v1/tenants"
ENDPOINT_CHAT_WIDGETS = "/api/v1/tenants/{tenant_id}/chat-widgets"
ENDPOINT_CHAT_WIDGET_DETAIL = "/api/v1/tenants/{tenant_id}/chat-widgets/{chat_widget_id}"
ENDPOINT_CHAT_WIDGET_PRINCIPALS = "/api/v1/tenants/{tenant_id}/chat-widgets/{chat_widget_id}/principals"
ENDPOINT_CHAT_WIDGET_TAGS = "/api/v1/tenants/{tenant_id}/chat-widgets/{chat_widget_id}/tags"

# Roles
ROLE_READ = PermissionActionEnum.READ.value
ROLE_WRITE = PermissionActionEnum.WRITE.value
ROLE_ADMIN = PermissionActionEnum.ADMIN.value

# Principal Types
PRINCIPAL_TYPE_USER = PrincipalTypeEnum.IDENTITY_USER.value


def create_tenant_for_user(test_client: TestClient, user_token: Any, tenant_name: str = "Test Tenant") -> str:
    """Helper function to create a tenant and return its ID."""
    headers = create_auth_headers(user_token, use_cache=False)
    response = test_client.post(
        ENDPOINT_TENANTS,
        json={"name": tenant_name, "description": f"Tenant for {user_token.get_id()}"},
        headers=headers
    )
    assert response.status_code == status.HTTP_201_CREATED
    return response.json()["id"]


def create_chat_widget(test_client: TestClient, tenant_id: str, headers: dict, name: str = "Test Widget") -> str:
    """Helper function to create a chat widget and return its ID."""
    response = test_client.post(
        ENDPOINT_CHAT_WIDGETS.format(tenant_id=tenant_id),
        json={
            "name": name,
            "description": f"Chat Widget {name}",
            "type": "IFRAME",
            "config": {"key": "value"}
        },
        headers=headers
    )
    assert response.status_code == status.HTTP_201_CREATED
    return response.json()["id"]


def add_user_to_tenant(test_client: TestClient, tenant_id: str, admin_headers: dict, user_id: str, role: str = "READER") -> None:
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


class TestChatWidgetCaching:
    """Test suite for chat widget caching behavior with X-Use-Cache enabled."""
    
    def test_creator_permissions_cached(self, test_client: TestClient, fake_redis_client: Any) -> None:
        """Test that creator's ADMIN permission is cached correctly."""
        user_token = test_client.create_test_user("cw-cache-creator", "CW Cache Creator")
        headers = create_auth_headers(user_token)
        tenant_id = create_tenant_for_user(test_client, user_token)
        
        widget_id = create_chat_widget(test_client, tenant_id, headers, "Cached Widget")
        
        # First access - should cache
        response1 = test_client.get(
            ENDPOINT_CHAT_WIDGET_DETAIL.format(tenant_id=tenant_id, chat_widget_id=widget_id),
            headers=headers
        )
        assert response1.status_code == status.HTTP_200_OK
        
        # Second access - should use cache
        response2 = test_client.get(
            ENDPOINT_CHAT_WIDGET_DETAIL.format(tenant_id=tenant_id, chat_widget_id=widget_id),
            headers=headers
        )
        assert response2.status_code == status.HTTP_200_OK
        
        # User should still be able to update
        update_response = test_client.patch(
            ENDPOINT_CHAT_WIDGET_DETAIL.format(tenant_id=tenant_id, chat_widget_id=widget_id),
            json={"name": "Updated Cached Widget"},
            headers=headers
        )
        assert update_response.status_code == status.HTTP_200_OK
    
    def test_no_access_cached(self, test_client: TestClient, fake_redis_client: Any) -> None:
        """Test that lack of access is handled correctly with caching."""
        user_a_token = test_client.create_test_user("cw-cache-a", "CW Cache A")
        headers_a = create_auth_headers(user_a_token)
        tenant_id = create_tenant_for_user(test_client, user_a_token)
        widget_id = create_chat_widget(test_client, tenant_id, headers_a, "Private Widget")
        
        user_b_token = test_client.create_test_user("cw-cache-b", "CW Cache B")
        headers_b = create_auth_headers(user_b_token)
        
        # First access - no permission
        response1 = test_client.get(
            ENDPOINT_CHAT_WIDGET_DETAIL.format(tenant_id=tenant_id, chat_widget_id=widget_id),
            headers=headers_b
        )
        assert response1.status_code == status.HTTP_403_FORBIDDEN
        
        # Second access - still forbidden
        response2 = test_client.get(
            ENDPOINT_CHAT_WIDGET_DETAIL.format(tenant_id=tenant_id, chat_widget_id=widget_id),
            headers=headers_b
        )
        assert response2.status_code == status.HTTP_403_FORBIDDEN
    
    def test_permission_grant_invalidates_cache(self, test_client: TestClient, fake_redis_client: Any) -> None:
        """Test that granting permission invalidates cache."""
        admin_token = test_client.create_test_user("cw-cache-admin-1", "CW Cache Admin 1")
        admin_headers = create_auth_headers(admin_token)
        tenant_id = create_tenant_for_user(test_client, admin_token)
        widget_id = create_chat_widget(test_client, tenant_id, admin_headers, "Grant Test")
        
        user_token = test_client.create_test_user("cw-cache-user-1", "CW Cache User 1")
        user_headers = create_auth_headers(user_token)
        
        add_user_to_tenant(test_client, tenant_id, admin_headers, "cw-cache-user-1", "READER")
        
        # User cannot access initially
        response_before = test_client.get(
            ENDPOINT_CHAT_WIDGET_DETAIL.format(tenant_id=tenant_id, chat_widget_id=widget_id),
            headers=user_headers
        )
        assert response_before.status_code == status.HTTP_403_FORBIDDEN
        
        # Grant WRITE permission
        test_client.put(
            ENDPOINT_CHAT_WIDGET_PRINCIPALS.format(tenant_id=tenant_id, chat_widget_id=widget_id),
            json={
                "principal_id": "cw-cache-user-1",
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_WRITE
            },
            headers=admin_headers
        )
        
        # User should now have access
        response_after = test_client.patch(
            ENDPOINT_CHAT_WIDGET_DETAIL.format(tenant_id=tenant_id, chat_widget_id=widget_id),
            json={"name": "Now It Works"},
            headers=user_headers
        )
        assert response_after.status_code == status.HTTP_200_OK
    
    def test_permission_revoke_invalidates_cache(self, test_client: TestClient, fake_redis_client: Any) -> None:
        """Test that revoking permission invalidates cache."""
        admin_token = test_client.create_test_user("cw-cache-admin-2", "CW Cache Admin 2")
        admin_headers = create_auth_headers(admin_token)
        tenant_id = create_tenant_for_user(test_client, admin_token)
        widget_id = create_chat_widget(test_client, tenant_id, admin_headers, "Revoke Test")
        
        user_token = test_client.create_test_user("cw-cache-user-2", "CW Cache User 2")
        user_headers = create_auth_headers(user_token)
        
        add_user_to_tenant(test_client, tenant_id, admin_headers, "cw-cache-user-2", "READER")
        
        # Grant ADMIN permission
        test_client.put(
            ENDPOINT_CHAT_WIDGET_PRINCIPALS.format(tenant_id=tenant_id, chat_widget_id=widget_id),
            json={
                "principal_id": "cw-cache-user-2",
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_ADMIN
            },
            headers=admin_headers
        )
        
        # User CAN update
        update_response1 = test_client.patch(
            ENDPOINT_CHAT_WIDGET_DETAIL.format(tenant_id=tenant_id, chat_widget_id=widget_id),
            json={"name": "Updated Once"},
            headers=user_headers
        )
        assert update_response1.status_code == status.HTTP_200_OK
        
        # Revoke permission
        test_client.request(
            "DELETE",
            ENDPOINT_CHAT_WIDGET_PRINCIPALS.format(tenant_id=tenant_id, chat_widget_id=widget_id),
            json={
                "principal_id": "cw-cache-user-2",
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_ADMIN
            },
            headers=admin_headers
        )
        
        # User should NOT have access anymore
        update_response2 = test_client.patch(
            ENDPOINT_CHAT_WIDGET_DETAIL.format(tenant_id=tenant_id, chat_widget_id=widget_id),
            json={"name": "Should Fail"},
            headers=user_headers
        )
        assert update_response2.status_code == status.HTTP_403_FORBIDDEN
    
    def test_chat_widgets_list_cached_correctly(self, test_client: TestClient, fake_redis_client: Any) -> None:
        """Test that chat widgets list respects permissions and caching."""
        admin_token = test_client.create_test_user("cw-list-admin", "CW List Admin")
        admin_headers = create_auth_headers(admin_token)
        tenant_id = create_tenant_for_user(test_client, admin_token)
        
        # Create multiple widgets
        widget1_id = create_chat_widget(test_client, tenant_id, admin_headers, "Widget 1")
        widget2_id = create_chat_widget(test_client, tenant_id, admin_headers, "Widget 2")
        widget3_id = create_chat_widget(test_client, tenant_id, admin_headers, "Widget 3")
        
        user_token = test_client.create_test_user("cw-list-user", "CW List User")
        user_headers = create_auth_headers(user_token)
        
        add_user_to_tenant(test_client, tenant_id, admin_headers, "cw-list-user", "READER")
        
        # User sees no widgets initially
        response1 = test_client.get(
            ENDPOINT_CHAT_WIDGETS.format(tenant_id=tenant_id),
            headers=user_headers
        )
        assert response1.status_code == status.HTTP_200_OK
        assert len(response1.json()) == 0
        
        # Grant permission to widgets 1 and 2
        test_client.put(
            ENDPOINT_CHAT_WIDGET_PRINCIPALS.format(tenant_id=tenant_id, chat_widget_id=widget1_id),
            json={"principal_id": "cw-list-user", "principal_type": PRINCIPAL_TYPE_USER, "role": ROLE_READ},
            headers=admin_headers
        )
        test_client.put(
            ENDPOINT_CHAT_WIDGET_PRINCIPALS.format(tenant_id=tenant_id, chat_widget_id=widget2_id),
            json={"principal_id": "cw-list-user", "principal_type": PRINCIPAL_TYPE_USER, "role": ROLE_WRITE},
            headers=admin_headers
        )
        
        # User now sees 2 widgets
        response2 = test_client.get(
            ENDPOINT_CHAT_WIDGETS.format(tenant_id=tenant_id),
            headers=user_headers
        )
        assert response2.status_code == status.HTTP_200_OK
        data = response2.json()
        assert len(data) == 2
        widget_ids = [w["id"] for w in data]
        assert widget1_id in widget_ids
        assert widget2_id in widget_ids
        assert widget3_id not in widget_ids
    
    def test_cache_isolated_between_users(self, test_client: TestClient, fake_redis_client: Any) -> None:
        """Test that cache is properly isolated between users."""
        admin_token = test_client.create_test_user("cw-iso-admin", "CW Isolation Admin")
        admin_headers = create_auth_headers(admin_token)
        tenant_id = create_tenant_for_user(test_client, admin_token)
        widget_id = create_chat_widget(test_client, tenant_id, admin_headers, "Isolation Test")
        
        # User A gets READ
        user_a_token = test_client.create_test_user("cw-iso-a", "CW Isolation A")
        user_a_headers = create_auth_headers(user_a_token)
        add_user_to_tenant(test_client, tenant_id, admin_headers, "cw-iso-a", "READER")
        test_client.put(
            ENDPOINT_CHAT_WIDGET_PRINCIPALS.format(tenant_id=tenant_id, chat_widget_id=widget_id),
            json={"principal_id": "cw-iso-a", "principal_type": PRINCIPAL_TYPE_USER, "role": ROLE_READ},
            headers=admin_headers
        )
        
        # User B gets WRITE
        user_b_token = test_client.create_test_user("cw-iso-b", "CW Isolation B")
        user_b_headers = create_auth_headers(user_b_token)
        add_user_to_tenant(test_client, tenant_id, admin_headers, "cw-iso-b", "READER")
        test_client.put(
            ENDPOINT_CHAT_WIDGET_PRINCIPALS.format(tenant_id=tenant_id, chat_widget_id=widget_id),
            json={"principal_id": "cw-iso-b", "principal_type": PRINCIPAL_TYPE_USER, "role": ROLE_WRITE},
            headers=admin_headers
        )
        
        # User A can view
        get_a = test_client.get(
            ENDPOINT_CHAT_WIDGET_DETAIL.format(tenant_id=tenant_id, chat_widget_id=widget_id),
            headers=user_a_headers
        )
        assert get_a.status_code == status.HTTP_200_OK
        
        # User A cannot update
        update_a = test_client.patch(
            ENDPOINT_CHAT_WIDGET_DETAIL.format(tenant_id=tenant_id, chat_widget_id=widget_id),
            json={"name": "User A Update"},
            headers=user_a_headers
        )
        assert update_a.status_code == status.HTTP_403_FORBIDDEN
        
        # User B can update
        update_b = test_client.patch(
            ENDPOINT_CHAT_WIDGET_DETAIL.format(tenant_id=tenant_id, chat_widget_id=widget_id),
            json={"name": "User B Update"},
            headers=user_b_headers
        )
        assert update_b.status_code == status.HTTP_200_OK
    
    def test_tenant_admin_bypass_cached_correctly(self, test_client: TestClient, fake_redis_client: Any) -> None:
        """Test that tenant admin bypass is cached correctly."""
        admin_token = test_client.create_test_user("cw-bypass-admin", "CW Bypass Admin")
        admin_headers = create_auth_headers(admin_token)
        tenant_id = create_tenant_for_user(test_client, admin_token)
        widget_id = create_chat_widget(test_client, tenant_id, admin_headers, "Bypass Test")
        
        global_admin_token = test_client.create_test_user("cw-bypass-global", "CW Bypass Global")
        global_admin_headers = create_auth_headers(global_admin_token)
        
        add_user_to_tenant(test_client, tenant_id, admin_headers, "cw-bypass-global", "GLOBAL_ADMIN")
        
        # Global admin can access without explicit permission
        response1 = test_client.get(
            ENDPOINT_CHAT_WIDGET_DETAIL.format(tenant_id=tenant_id, chat_widget_id=widget_id),
            headers=global_admin_headers
        )
        assert response1.status_code == status.HTTP_200_OK
        
        # Global admin can update
        response2 = test_client.patch(
            ENDPOINT_CHAT_WIDGET_DETAIL.format(tenant_id=tenant_id, chat_widget_id=widget_id),
            json={"name": "Updated by Global Admin"},
            headers=global_admin_headers
        )
        assert response2.status_code == status.HTTP_200_OK


class TestChatWidgetTagCacheInvalidation:
    """Test suite for cache invalidation when adding/removing tags from chat widgets."""
    
    def test_adding_tags_invalidates_cache(self, test_client: TestClient, fake_redis_client: Any) -> None:
        """Test that adding tags invalidates the chat widget cache."""
        admin_token = test_client.create_test_user("cw-tag-cache-1", "CW Tag Cache 1")
        admin_headers = create_auth_headers(admin_token)
        tenant_id = create_tenant_for_user(test_client, admin_token)
        widget_id = create_chat_widget(test_client, tenant_id, admin_headers, "Tagged Widget")
        
        # First read - cache (no tags)
        response1 = test_client.get(
            ENDPOINT_CHAT_WIDGET_DETAIL.format(tenant_id=tenant_id, chat_widget_id=widget_id),
            headers=admin_headers
        )
        assert response1.json()["tags"] == []
        
        # Add tags
        test_client.put(
            ENDPOINT_CHAT_WIDGET_TAGS.format(tenant_id=tenant_id, chat_widget_id=widget_id),
            json={"tags": ["support", "live"]},
            headers=admin_headers
        )
        
        # Read again - should see tags
        response2 = test_client.get(
            ENDPOINT_CHAT_WIDGET_DETAIL.format(tenant_id=tenant_id, chat_widget_id=widget_id),
            headers=admin_headers
        )
        assert len(response2.json()["tags"]) == 2
    
    def test_removing_tags_invalidates_cache(self, test_client: TestClient, fake_redis_client: Any) -> None:
        """Test that removing tags invalidates the chat widget cache."""
        admin_token = test_client.create_test_user("cw-tag-cache-2", "CW Tag Cache 2")
        admin_headers = create_auth_headers(admin_token)
        tenant_id = create_tenant_for_user(test_client, admin_token)
        widget_id = create_chat_widget(test_client, tenant_id, admin_headers, "Tagged Widget 2")
        
        # Set tags and cache
        test_client.put(
            ENDPOINT_CHAT_WIDGET_TAGS.format(tenant_id=tenant_id, chat_widget_id=widget_id),
            json={"tags": ["TAG1", "TAG2"]},
            headers=admin_headers
        )
        
        response1 = test_client.get(
            ENDPOINT_CHAT_WIDGET_DETAIL.format(tenant_id=tenant_id, chat_widget_id=widget_id),
            headers=admin_headers
        )
        assert len(response1.json()["tags"]) == 2
        
        # Remove tags
        test_client.delete(
            ENDPOINT_CHAT_WIDGET_TAGS.format(tenant_id=tenant_id, chat_widget_id=widget_id),
            headers=admin_headers
        )
        
        # Read again - no tags
        response2 = test_client.get(
            ENDPOINT_CHAT_WIDGET_DETAIL.format(tenant_id=tenant_id, chat_widget_id=widget_id),
            headers=admin_headers
        )
        assert response2.json()["tags"] == []
    
    def test_replacing_tags_invalidates_cache(self, test_client: TestClient, fake_redis_client: Any) -> None:
        """Test that replacing tags invalidates the chat widget cache."""
        admin_token = test_client.create_test_user("cw-tag-cache-3", "CW Tag Cache 3")
        admin_headers = create_auth_headers(admin_token)
        tenant_id = create_tenant_for_user(test_client, admin_token)
        widget_id = create_chat_widget(test_client, tenant_id, admin_headers, "Tagged Widget 3")
        
        # Set initial tags
        test_client.put(
            ENDPOINT_CHAT_WIDGET_TAGS.format(tenant_id=tenant_id, chat_widget_id=widget_id),
            json={"tags": ["OLD-1", "OLD-2"]},
            headers=admin_headers
        )
        
        response1 = test_client.get(
            ENDPOINT_CHAT_WIDGET_DETAIL.format(tenant_id=tenant_id, chat_widget_id=widget_id),
            headers=admin_headers
        )
        tag_names1 = [t["name"] for t in response1.json()["tags"]]
        assert "OLD-1" in tag_names1
        
        # Replace tags
        test_client.put(
            ENDPOINT_CHAT_WIDGET_TAGS.format(tenant_id=tenant_id, chat_widget_id=widget_id),
            json={"tags": ["NEW-1", "NEW-2", "NEW-3"]},
            headers=admin_headers
        )
        
        # Read again - new tags
        response2 = test_client.get(
            ENDPOINT_CHAT_WIDGET_DETAIL.format(tenant_id=tenant_id, chat_widget_id=widget_id),
            headers=admin_headers
        )
        tag_names2 = [t["name"] for t in response2.json()["tags"]]
        assert len(tag_names2) == 3
        assert "NEW-1" in tag_names2
        assert "OLD-1" not in tag_names2


class TestChatWidgetListCaching:
    """Test suite for chat widget list caching with order_by, order_direction, and is_active."""
    
    def test_list_cached_with_order_by(self, test_client: TestClient, fake_redis_client: Any) -> None:
        """Test that list responses are cached correctly with order_by parameter."""
        user_token = test_client.create_test_user("cw-list-cache-order", "CW List Cache Order")
        headers = create_auth_headers(user_token)
        tenant_id = create_tenant_for_user(test_client, user_token)
        
        # Create chat widgets
        create_chat_widget(test_client, tenant_id, headers, "Widget A")
        create_chat_widget(test_client, tenant_id, headers, "Widget B")
        
        # First request with order_by=name asc
        response1 = test_client.get(
            ENDPOINT_CHAT_WIDGETS.format(tenant_id=tenant_id),
            params={"order_by": "name", "order_direction": "asc"},
            headers=headers
        )
        assert response1.status_code == status.HTTP_200_OK
        assert len(response1.json()) == 2
        assert response1.json()[0]["name"] == "Widget A"
        
        # Second request with same params - should use cache
        response2 = test_client.get(
            ENDPOINT_CHAT_WIDGETS.format(tenant_id=tenant_id),
            params={"order_by": "name", "order_direction": "asc"},
            headers=headers
        )
        assert response2.status_code == status.HTTP_200_OK
        assert response2.json() == response1.json()
        
        # Request with different order_direction - different cache key
        response3 = test_client.get(
            ENDPOINT_CHAT_WIDGETS.format(tenant_id=tenant_id),
            params={"order_by": "name", "order_direction": "desc"},
            headers=headers
        )
        assert response3.status_code == status.HTTP_200_OK
        assert response3.json()[0]["name"] == "Widget B"
    
    def test_list_cached_with_is_active(self, test_client: TestClient, fake_redis_client: Any) -> None:
        """Test that list responses work correctly with is_active parameter and different values use different cache keys."""
        user_token = test_client.create_test_user("cw-list-cache-active", "CW List Cache Active")
        headers = create_auth_headers(user_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, user_token)
        
        # Create two widgets (default is_active=False)
        create_chat_widget(test_client, tenant_id, headers, "Widget Inactive")
        widget_id_2 = create_chat_widget(test_client, tenant_id, headers, "Widget Active")
        
        # Activate second widget
        test_client.patch(
            ENDPOINT_CHAT_WIDGET_DETAIL.format(tenant_id=tenant_id, chat_widget_id=widget_id_2),
            json={"is_active": True},
            headers=headers
        )
        
        # Test is_active=1 (only active)
        response_active = test_client.get(
            ENDPOINT_CHAT_WIDGETS.format(tenant_id=tenant_id),
            params={"is_active": 1},
            headers=headers
        )
        assert response_active.status_code == status.HTTP_200_OK
        assert len(response_active.json()) == 1
        assert response_active.json()[0]["name"] == "Widget Active"
        
        # Test is_active=0 (only inactive)
        response_inactive = test_client.get(
            ENDPOINT_CHAT_WIDGETS.format(tenant_id=tenant_id),
            params={"is_active": 0},
            headers=headers
        )
        assert response_inactive.status_code == status.HTTP_200_OK
        assert len(response_inactive.json()) == 1
        assert response_inactive.json()[0]["name"] == "Widget Inactive"
        
        # Test without is_active (all widgets)
        response_all = test_client.get(
            ENDPOINT_CHAT_WIDGETS.format(tenant_id=tenant_id),
            headers=headers
        )
        assert response_all.status_code == status.HTTP_200_OK
        assert len(response_all.json()) == 2
    
    def test_list_cache_key_includes_all_params(self, test_client: TestClient, fake_redis_client: Any) -> None:
        """Test that cache keys correctly differentiate based on all parameters."""
        user_token = test_client.create_test_user("cw-list-cache-params", "CW List Cache Params")
        headers = create_auth_headers(user_token)
        tenant_id = create_tenant_for_user(test_client, user_token)
        
        create_chat_widget(test_client, tenant_id, headers, "Test Widget")
        
        # Different parameter combinations should return results
        combos = [
            {},
            {"order_by": "name"},
            {"order_by": "name", "order_direction": "desc"},
            {"is_active": 1},
            {"is_active": 0},
            {"order_by": "created_at", "is_active": 1},
            {"view": "quick-list"},
            {"view": "quick-list", "is_active": 1},
        ]
        
        for params in combos:
            response = test_client.get(
                ENDPOINT_CHAT_WIDGETS.format(tenant_id=tenant_id),
                params=params,
                headers=headers
            )
            assert response.status_code == status.HTTP_200_OK
