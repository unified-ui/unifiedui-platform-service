"""Tests for chat widgets API endpoints."""
from typing import Any
from fastapi import status
from starlette.testclient import TestClient

from unifiedui.core.database.enums import PermissionActionEnum, PrincipalTypeEnum, ChatWidgetTypeEnum
from tests.conftest import create_auth_headers


# API Endpoints
ENDPOINT_CHAT_WIDGETS = "/api/v1/tenants/{tenant_id}/chat-widgets"
ENDPOINT_CHAT_WIDGET_DETAIL = "/api/v1/tenants/{tenant_id}/chat-widgets/{chat_widget_id}"
ENDPOINT_CHAT_WIDGET_PRINCIPALS = "/api/v1/tenants/{tenant_id}/chat-widgets/{chat_widget_id}/principals"
ENDPOINT_PRINCIPAL_DETAIL = "/api/v1/tenants/{tenant_id}/chat-widgets/{chat_widget_id}/principals/{principal_id}"

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


class TestChatWidgetRoutes:
    """Test suite for chat widget API routes."""
    
    def test_create_chat_widget_success(
        self, 
        test_client: TestClient, 
        test_user_token: Any
    ) -> None:
        """Test successful chat widget creation."""
        # Create a tenant first
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        # Create chat widget
        cw_data = {
            "name": "Test Chat Widget",
            "description": "A test chat widget",
            "type": "IFRAME",
            "config": {"key": "value", "url": "https://example.com"}
        }
        
        response = test_client.post(
            ENDPOINT_CHAT_WIDGETS.format(tenant_id=tenant_id),
            json=cw_data,
            headers=headers
        )
        
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        
        assert data["name"] == cw_data["name"]
        assert data["description"] == cw_data["description"]
        assert data["type"] == cw_data["type"]
        assert data["config"] == cw_data["config"]
        assert data["is_active"] == False
        assert "id" in data
        assert data["tenant_id"] == tenant_id
        assert "created_at" in data
        assert "updated_at" in data
        assert data["created_by"] == test_user_token.get_id()
    
    def test_create_chat_widget_with_form_type(
        self, 
        test_client: TestClient, 
        test_user_token: Any
    ) -> None:
        """Test chat widget creation with FORM type."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        cw_data = {
            "name": "Form Widget",
            "description": "A form-based widget",
            "type": "FORM",
            "config": {"fields": ["name", "email"]}
        }
        
        response = test_client.post(
            ENDPOINT_CHAT_WIDGETS.format(tenant_id=tenant_id),
            json=cw_data,
            headers=headers
        )
        
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["type"] == "FORM"
    
    def test_create_chat_widget_without_type(
        self, 
        test_client: TestClient, 
        test_user_token: Any
    ) -> None:
        """Test chat widget creation without type (optional)."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        cw_data = {
            "name": "Widget Without Type",
            "config": {"key": "value"}
        }
        
        response = test_client.post(
            ENDPOINT_CHAT_WIDGETS.format(tenant_id=tenant_id),
            json=cw_data,
            headers=headers
        )
        
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["type"] is None
    
    def test_create_chat_widget_missing_name(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test chat widget creation with missing name."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        response = test_client.post(
            ENDPOINT_CHAT_WIDGETS.format(tenant_id=tenant_id),
            json={"description": "Test widget", "config": {}},
            headers=headers
        )
        
        assert response.status_code == 422
    
    def test_create_chat_widget_missing_config(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test chat widget creation with missing config (required)."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        response = test_client.post(
            ENDPOINT_CHAT_WIDGETS.format(tenant_id=tenant_id),
            json={"name": "Test Widget"},
            headers=headers
        )
        
        assert response.status_code == 422
    
    def test_create_chat_widget_invalid_name_type(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test chat widget creation with invalid name type."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        response = test_client.post(
            ENDPOINT_CHAT_WIDGETS.format(tenant_id=tenant_id),
            json={"name": 123, "config": {}},
            headers=headers
        )
        
        assert response.status_code == 422
    
    def test_create_chat_widget_empty_name(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test chat widget creation with empty name."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        response = test_client.post(
            ENDPOINT_CHAT_WIDGETS.format(tenant_id=tenant_id),
            json={"name": "", "config": {}},
            headers=headers
        )
        
        assert response.status_code == 422
    
    def test_create_chat_widget_invalid_type(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test chat widget creation with invalid type."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        response = test_client.post(
            ENDPOINT_CHAT_WIDGETS.format(tenant_id=tenant_id),
            json={"name": "Test Widget", "type": "INVALID_TYPE", "config": {}},
            headers=headers
        )
        
        assert response.status_code == 422
    
    def test_create_chat_widget_empty_body(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test chat widget creation with empty JSON body."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        response = test_client.post(
            ENDPOINT_CHAT_WIDGETS.format(tenant_id=tenant_id),
            json={},
            headers=headers
        )
        
        assert response.status_code == 422
    
    def test_create_chat_widget_without_permission(self, test_client: TestClient) -> None:
        """Test that user without CHAT_WIDGETS_CREATOR permission cannot create chat widgets."""
        # Create user1 with a tenant
        user1_token = test_client.create_test_user("user-1", "User One")
        tenant_id = create_tenant_for_user(test_client, user1_token)
        
        # Create user2 (not a member of the tenant)
        user2_token = test_client.create_test_user("user-2", "User Two")
        headers2 = create_auth_headers(user2_token, use_cache=False)
        
        # Try to create chat widget as user2 (should fail - no tenant membership)
        response = test_client.post(
            ENDPOINT_CHAT_WIDGETS.format(tenant_id=tenant_id),
            json={"name": "Unauthorized Widget", "config": {}},
            headers=headers2
        )
        
        assert response.status_code == status.HTTP_403_FORBIDDEN
    
    def test_get_chat_widget_success(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test successful chat widget retrieval."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        # Create a chat widget
        cw_data = {"name": "Test Chat Widget", "description": "Test description", "config": {"key": "value"}}
        create_response = test_client.post(
            ENDPOINT_CHAT_WIDGETS.format(tenant_id=tenant_id),
            json=cw_data,
            headers=headers
        )
        cw_id = create_response.json()["id"]
        
        # Retrieve the chat widget
        response = test_client.get(
            ENDPOINT_CHAT_WIDGET_DETAIL.format(tenant_id=tenant_id, chat_widget_id=cw_id),
            headers=headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["id"] == cw_id
        assert data["name"] == cw_data["name"]
        assert data["description"] == cw_data["description"]
        assert data["config"] == cw_data["config"]
    
    def test_get_chat_widget_not_found(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test chat widget retrieval with non-existent ID."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        response = test_client.get(
            ENDPOINT_CHAT_WIDGET_DETAIL.format(tenant_id=tenant_id, chat_widget_id=NON_EXISTENT_ID),
            headers=headers
        )
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
    
    def test_list_chat_widgets_empty(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test listing chat widgets when none exist."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        response = test_client.get(
            ENDPOINT_CHAT_WIDGETS.format(tenant_id=tenant_id),
            headers=headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert isinstance(data, list)
        assert len(data) == 0
    
    def test_list_chat_widgets_with_data(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test listing chat widgets with existing data."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        # Create multiple chat widgets
        cw1_data = {"name": "Widget 1", "description": "First widget", "config": {}}
        cw2_data = {"name": "Widget 2", "description": "Second widget", "config": {}}
        
        test_client.post(
            ENDPOINT_CHAT_WIDGETS.format(tenant_id=tenant_id),
            json=cw1_data,
            headers=headers
        )
        test_client.post(
            ENDPOINT_CHAT_WIDGETS.format(tenant_id=tenant_id),
            json=cw2_data,
            headers=headers
        )
        
        # List chat widgets
        response = test_client.get(
            ENDPOINT_CHAT_WIDGETS.format(tenant_id=tenant_id),
            headers=headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert isinstance(data, list)
        assert len(data) == 2
        
        names = [cw["name"] for cw in data]
        assert "Widget 1" in names
        assert "Widget 2" in names
    
    def test_list_chat_widgets_with_pagination(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test listing chat widgets with pagination parameters."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        # Create multiple chat widgets
        for i in range(5):
            test_client.post(
                ENDPOINT_CHAT_WIDGETS.format(tenant_id=tenant_id),
                json={"name": f"Widget {i}", "description": f"Description {i}", "config": {}},
                headers=headers
            )
        
        # Test with limit
        response = test_client.get(
            f"{ENDPOINT_CHAT_WIDGETS.format(tenant_id=tenant_id)}?limit=3",
            headers=headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 3
        
        # Test with skip
        response = test_client.get(
            f"{ENDPOINT_CHAT_WIDGETS.format(tenant_id=tenant_id)}?skip=2&limit=2",
            headers=headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 2
    
    def test_list_chat_widgets_with_name_filter(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test listing chat widgets with name filter."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        # Create chat widgets with different names
        test_client.post(
            ENDPOINT_CHAT_WIDGETS.format(tenant_id=tenant_id),
            json={"name": "Production Widget", "description": "Prod", "config": {}},
            headers=headers
        )
        test_client.post(
            ENDPOINT_CHAT_WIDGETS.format(tenant_id=tenant_id),
            json={"name": "Development Widget", "description": "Dev", "config": {}},
            headers=headers
        )
        
        # Filter by name
        response = test_client.get(
            f"{ENDPOINT_CHAT_WIDGETS.format(tenant_id=tenant_id)}?name_filter=Production",
            headers=headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "Production Widget"
    
    def test_list_chat_widgets_with_quick_list_view(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test listing chat widgets with quick-list view returns only id and name."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        # Create chat widgets
        test_client.post(
            ENDPOINT_CHAT_WIDGETS.format(tenant_id=tenant_id),
            json={"name": "Widget One", "description": "First widget", "config": {"key": "value"}},
            headers=headers
        )
        test_client.post(
            ENDPOINT_CHAT_WIDGETS.format(tenant_id=tenant_id),
            json={"name": "Widget Two", "description": "Second widget", "config": {}},
            headers=headers
        )
        
        # Get with quick-list view
        response = test_client.get(
            f"{ENDPOINT_CHAT_WIDGETS.format(tenant_id=tenant_id)}?view=quick-list",
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
            assert "config" not in item
            assert "tenant_id" not in item
            assert "created_at" not in item
            assert "updated_at" not in item
            assert "created_by" not in item
            assert "updated_by" not in item
            assert "is_active" not in item
    
    def test_update_chat_widget_success(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test successful chat widget update."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        # Create a chat widget
        cw_data = {"name": "Original Name", "description": "Original", "config": {"key": "original"}}
        create_response = test_client.post(
            ENDPOINT_CHAT_WIDGETS.format(tenant_id=tenant_id),
            json=cw_data,
            headers=headers
        )
        cw_id = create_response.json()["id"]
        
        # Update the chat widget
        update_data = {"name": "Updated Name", "description": "Updated", "config": {"key": "updated"}}
        update_response = test_client.patch(
            ENDPOINT_CHAT_WIDGET_DETAIL.format(tenant_id=tenant_id, chat_widget_id=cw_id),
            json=update_data,
            headers=headers
        )
        
        assert update_response.status_code == status.HTTP_200_OK
        data = update_response.json()
        
        assert data["name"] == update_data["name"]
        assert data["description"] == update_data["description"]
        assert data["config"] == update_data["config"]
        assert data["id"] == cw_id
    
    def test_update_chat_widget_type(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test updating chat widget type."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        # Create a chat widget with IFRAME type
        create_response = test_client.post(
            ENDPOINT_CHAT_WIDGETS.format(tenant_id=tenant_id),
            json={"name": "Widget", "type": "IFRAME", "config": {}},
            headers=headers
        )
        cw_id = create_response.json()["id"]
        
        # Update to FORM type
        update_response = test_client.patch(
            ENDPOINT_CHAT_WIDGET_DETAIL.format(tenant_id=tenant_id, chat_widget_id=cw_id),
            json={"type": "FORM"},
            headers=headers
        )
        
        assert update_response.status_code == status.HTTP_200_OK
        assert update_response.json()["type"] == "FORM"
    
    def test_update_chat_widget_not_found(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test chat widget update with non-existent ID."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        response = test_client.patch(
            ENDPOINT_CHAT_WIDGET_DETAIL.format(tenant_id=tenant_id, chat_widget_id=NON_EXISTENT_ID),
            json={"name": "Updated"},
            headers=headers
        )
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
    
    def test_update_chat_widget_partial(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test partial chat widget update."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
    
    def test_update_chat_widget_is_active(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test updating chat widget is_active status."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        # Create chat widget (default is_active=False)
        create_response = test_client.post(
            ENDPOINT_CHAT_WIDGETS.format(tenant_id=tenant_id),
            json={"name": "Test Widget", "description": "Test", "config": {}},
            headers=headers
        )
        cw_id = create_response.json()["id"]
        assert create_response.json()["is_active"] == False
        
        # Update to active
        update_response = test_client.patch(
            ENDPOINT_CHAT_WIDGET_DETAIL.format(tenant_id=tenant_id, chat_widget_id=cw_id),
            json={"is_active": True},
            headers=headers
        )
        
        assert update_response.status_code == status.HTTP_200_OK
        assert update_response.json()["is_active"] == True
        
        # Update back to inactive
        update_response2 = test_client.patch(
            ENDPOINT_CHAT_WIDGET_DETAIL.format(tenant_id=tenant_id, chat_widget_id=cw_id),
            json={"is_active": False},
            headers=headers
        )
        
        assert update_response2.status_code == status.HTTP_200_OK
        assert update_response2.json()["is_active"] == False
        
        # Create a chat widget
        cw_data = {"name": "Original", "description": "Description", "config": {"key": "value"}}
        create_response = test_client.post(
            ENDPOINT_CHAT_WIDGETS.format(tenant_id=tenant_id),
            json=cw_data,
            headers=headers
        )
        cw_id = create_response.json()["id"]
        
        # Update only name
        update_response = test_client.patch(
            ENDPOINT_CHAT_WIDGET_DETAIL.format(tenant_id=tenant_id, chat_widget_id=cw_id),
            json={"name": "Only Name Updated"},
            headers=headers
        )
        
        assert update_response.status_code == status.HTTP_200_OK
        data = update_response.json()
        
        assert data["name"] == "Only Name Updated"
        assert data["description"] == cw_data["description"]  # Should remain unchanged
        assert data["config"] == cw_data["config"]  # Should remain unchanged
    
    def test_delete_chat_widget_success(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test successful chat widget deletion."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        # Create a chat widget
        cw_data = {"name": "To Delete", "description": "Will be deleted", "config": {}}
        create_response = test_client.post(
            ENDPOINT_CHAT_WIDGETS.format(tenant_id=tenant_id),
            json=cw_data,
            headers=headers
        )
        cw_id = create_response.json()["id"]
        
        # Delete the chat widget
        delete_response = test_client.request(
            "DELETE",
            ENDPOINT_CHAT_WIDGET_DETAIL.format(tenant_id=tenant_id, chat_widget_id=cw_id),
            headers=headers
        )
        
        assert delete_response.status_code == status.HTTP_204_NO_CONTENT
        
        # Verify it's deleted
        get_response = test_client.get(
            ENDPOINT_CHAT_WIDGET_DETAIL.format(tenant_id=tenant_id, chat_widget_id=cw_id),
            headers=headers
        )
        
        assert get_response.status_code == status.HTTP_404_NOT_FOUND
    
    def test_delete_chat_widget_not_found(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test chat widget deletion with non-existent ID."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        response = test_client.request(
            "DELETE",
            ENDPOINT_CHAT_WIDGET_DETAIL.format(tenant_id=tenant_id, chat_widget_id=NON_EXISTENT_ID),
            headers=headers
        )
        
        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestChatWidgetPrincipalRoutes:
    """Test suite for chat widget principal/permission management routes."""
    
    def test_list_chat_widget_principals_creator_only(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test that only creator has permissions initially."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        # Create a chat widget
        cw_data = {"name": "Test Widget", "description": "Test", "config": {}}
        create_response = test_client.post(
            ENDPOINT_CHAT_WIDGETS.format(tenant_id=tenant_id),
            json=cw_data,
            headers=headers
        )
        cw_id = create_response.json()["id"]
        
        # List principals
        response = test_client.get(
            ENDPOINT_CHAT_WIDGET_PRINCIPALS.format(tenant_id=tenant_id, chat_widget_id=cw_id),
            headers=headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert "chat_widget_id" in data
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
        
        # Create a chat widget
        cw_data = {"name": "Test Widget", "description": "Test", "config": {}}
        create_response = test_client.post(
            ENDPOINT_CHAT_WIDGETS.format(tenant_id=tenant_id),
            json=cw_data,
            headers=headers
        )
        cw_id = create_response.json()["id"]
        
        # Get creator's permissions
        response = test_client.get(
            ENDPOINT_PRINCIPAL_DETAIL.format(
                tenant_id=tenant_id,
                chat_widget_id=cw_id,
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
        
        # Create a chat widget
        cw_data = {"name": "Test Widget", "description": "Test", "config": {}}
        create_response = test_client.post(
            ENDPOINT_CHAT_WIDGETS.format(tenant_id=tenant_id),
            json=cw_data,
            headers=headers
        )
        cw_id = create_response.json()["id"]
        
        # Add permission for another user
        permission_data = {
            "principal_id": "other-user",
            "principal_type": PRINCIPAL_TYPE_USER,
            "role": ROLE_READ
        }
        
        response = test_client.put(
            ENDPOINT_CHAT_WIDGET_PRINCIPALS.format(tenant_id=tenant_id, chat_widget_id=cw_id),
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
        
        # Create a chat widget
        cw_data = {"name": "Test Widget", "description": "Test", "config": {}}
        create_response = test_client.post(
            ENDPOINT_CHAT_WIDGETS.format(tenant_id=tenant_id),
            json=cw_data,
            headers=headers
        )
        cw_id = create_response.json()["id"]
        
        # Add READ permission
        test_client.put(
            ENDPOINT_CHAT_WIDGET_PRINCIPALS.format(tenant_id=tenant_id, chat_widget_id=cw_id),
            json={
                "principal_id": "other-user",
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_READ
            },
            headers=headers
        )
        
        # Update to WRITE permission
        update_response = test_client.put(
            ENDPOINT_CHAT_WIDGET_PRINCIPALS.format(tenant_id=tenant_id, chat_widget_id=cw_id),
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
        
        # Create a chat widget
        cw_data = {"name": "Test Widget", "description": "Test", "config": {}}
        create_response = test_client.post(
            ENDPOINT_CHAT_WIDGETS.format(tenant_id=tenant_id),
            json=cw_data,
            headers=headers
        )
        cw_id = create_response.json()["id"]
        
        response = test_client.put(
            ENDPOINT_CHAT_WIDGET_PRINCIPALS.format(tenant_id=tenant_id, chat_widget_id=cw_id),
            json={"role": ROLE_READ},
            headers=headers
        )
        
        assert response.status_code == 422
    
    def test_set_principal_permission_missing_role(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test setting permission with missing role."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        # Create a chat widget
        cw_data = {"name": "Test Widget", "description": "Test", "config": {}}
        create_response = test_client.post(
            ENDPOINT_CHAT_WIDGETS.format(tenant_id=tenant_id),
            json=cw_data,
            headers=headers
        )
        cw_id = create_response.json()["id"]
        
        response = test_client.put(
            ENDPOINT_CHAT_WIDGET_PRINCIPALS.format(tenant_id=tenant_id, chat_widget_id=cw_id),
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
        
        # Create a chat widget
        cw_data = {"name": "Test Widget", "description": "Test", "config": {}}
        create_response = test_client.post(
            ENDPOINT_CHAT_WIDGETS.format(tenant_id=tenant_id),
            json=cw_data,
            headers=headers
        )
        cw_id = create_response.json()["id"]
        
        response = test_client.put(
            ENDPOINT_CHAT_WIDGET_PRINCIPALS.format(tenant_id=tenant_id, chat_widget_id=cw_id),
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
        
        # Create a chat widget
        cw_data = {"name": "Test Widget", "description": "Test", "config": {}}
        create_response = test_client.post(
            ENDPOINT_CHAT_WIDGETS.format(tenant_id=tenant_id),
            json=cw_data,
            headers=headers
        )
        cw_id = create_response.json()["id"]
        
        response = test_client.put(
            ENDPOINT_CHAT_WIDGET_PRINCIPALS.format(tenant_id=tenant_id, chat_widget_id=cw_id),
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
        
        # Create a chat widget
        cw_data = {"name": "Test Widget", "description": "Test", "config": {}}
        create_response = test_client.post(
            ENDPOINT_CHAT_WIDGETS.format(tenant_id=tenant_id),
            json=cw_data,
            headers=headers
        )
        cw_id = create_response.json()["id"]
        
        # Add permission
        test_client.put(
            ENDPOINT_CHAT_WIDGET_PRINCIPALS.format(tenant_id=tenant_id, chat_widget_id=cw_id),
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
            ENDPOINT_CHAT_WIDGET_PRINCIPALS.format(tenant_id=tenant_id, chat_widget_id=cw_id),
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
                chat_widget_id=cw_id,
                principal_id="other-user"
            ),
            headers=headers
        )
        
        assert get_response.status_code == status.HTTP_404_NOT_FOUND
    
    def test_delete_principal_permission_not_found(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test deleting a non-existent permission."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        # Create a chat widget
        cw_data = {"name": "Test Widget", "description": "Test", "config": {}}
        create_response = test_client.post(
            ENDPOINT_CHAT_WIDGETS.format(tenant_id=tenant_id),
            json=cw_data,
            headers=headers
        )
        cw_id = create_response.json()["id"]
        
        # Try to delete non-existent permission
        response = test_client.request(
            "DELETE",
            ENDPOINT_CHAT_WIDGET_PRINCIPALS.format(tenant_id=tenant_id, chat_widget_id=cw_id),
            json={
                "principal_id": "non-existent-user",
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_READ
            },
            headers=headers
        )
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
