"""Tests for applications API endpoints."""
import time
from typing import Any
from fastapi import status
from starlette.testclient import TestClient

from unifiedui.core.database.enums import PermissionActionEnum, PrincipalTypeEnum
from tests.conftest import create_auth_headers


# API Endpoints
ENDPOINT_APPLICATIONS = "/api/v1/platform-service/tenants/{tenant_id}/applications"
ENDPOINT_APPLICATION_DETAIL = "/api/v1/platform-service/tenants/{tenant_id}/applications/{application_id}"
ENDPOINT_APPLICATION_PRINCIPALS = "/api/v1/platform-service/tenants/{tenant_id}/applications/{application_id}/principals"
ENDPOINT_PRINCIPAL_DETAIL = "/api/v1/platform-service/tenants/{tenant_id}/applications/{application_id}/principals/{principal_id}"

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


def get_valid_n8n_config() -> dict:
    """Returns a valid N8N application config for testing."""
    return {
        "api_version": "v1",
        "workflow_type": "N8N_CHAT_AGENT_WORKFLOW",
        "use_unified_chat_history": True,
        "chat_history_count": 30,
        "chat_url": "https://example.com/webhook",
        "api_api_key_credential_id": "test-cred-123",
        "chat_auth_credential_id": "test-cred-456"
    }


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


class TestApplicationRoutes:
    """Test suite for application API routes."""
    
    def test_create_application_success(
        self, 
        test_client: TestClient, 
        test_user_token: Any
    ) -> None:
        """Test successful application creation."""
        # Create a tenant first
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        # Create application with valid N8N config
        n8n_config = get_valid_n8n_config()
        app_data = {
            "name": "Test Application",
            "description": "A test application",
            "type": "N8N",
            "config": n8n_config
        }
        
        response = test_client.post(
            ENDPOINT_APPLICATIONS.format(tenant_id=tenant_id),
            json=app_data,
            headers=headers
        )
        
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        
        assert data["name"] == app_data["name"]
        assert data["description"] == app_data["description"]
        assert data["type"] == app_data["type"]
        assert data["config"] == n8n_config
        assert data["is_active"] == False
        assert "id" in data
        assert data["tenant_id"] == tenant_id
        assert "created_at" in data
        assert "updated_at" in data
        assert data["created_by"] == test_user_token.get_id()
    
    def test_create_application_missing_name(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test application creation with missing name."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        response = test_client.post(
            ENDPOINT_APPLICATIONS.format(tenant_id=tenant_id),
            json={"description": "Test app"},
            headers=headers
        )
        
        assert response.status_code == 422
    
    def test_create_application_invalid_name_type(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test application creation with invalid name type."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        response = test_client.post(
            ENDPOINT_APPLICATIONS.format(tenant_id=tenant_id),
            json={"name": 123, "description": "Test"},
            headers=headers
        )
        
        assert response.status_code == 422
    
    def test_create_application_empty_name(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test application creation with empty name."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        response = test_client.post(
            ENDPOINT_APPLICATIONS.format(tenant_id=tenant_id),
            json={"name": "", "description": "Test"},
            headers=headers
        )
        
        assert response.status_code == 422
    
    def test_create_application_invalid_description_type(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test application creation with invalid description type."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        response = test_client.post(
            ENDPOINT_APPLICATIONS.format(tenant_id=tenant_id),
            json={"name": "Test App", "description": 123},
            headers=headers
        )
        
        assert response.status_code == 422
    
    def test_create_application_empty_body(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test application creation with empty JSON body."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        response = test_client.post(
            ENDPOINT_APPLICATIONS.format(tenant_id=tenant_id),
            json={},
            headers=headers
        )
        
        assert response.status_code == 422
    
    def test_create_application_without_permission(self, test_client: TestClient) -> None:
        """Test that user without APPLICATION_CREATOR permission cannot create applications."""
        # Create user1 with a tenant
        user1_token = test_client.create_test_user("user-1", "User One")
        tenant_id = create_tenant_for_user(test_client, user1_token)
        headers1 = create_auth_headers(user1_token, use_cache=False)
        
        # Create user2 (not a member of the tenant)
        user2_token = test_client.create_test_user("user-2", "User Two")
        headers2 = create_auth_headers(user2_token, use_cache=False)
        
        # Try to create application as user2 (should fail - no tenant membership)
        response = test_client.post(
            ENDPOINT_APPLICATIONS.format(tenant_id=tenant_id),
            json={"name": "Unauthorized App", "description": "Should fail", "type": "N8N"},
            headers=headers2
        )
        
        assert response.status_code == status.HTTP_403_FORBIDDEN
    
    def test_get_application_success(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test successful application retrieval."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        # Create an application
        app_data = {"name": "Test Application", "description": "Test description", "type": "N8N"}
        create_response = test_client.post(
            ENDPOINT_APPLICATIONS.format(tenant_id=tenant_id),
            json=app_data,
            headers=headers
        )
        app_id = create_response.json()["id"]
        
        # Retrieve the application
        response = test_client.get(
            ENDPOINT_APPLICATION_DETAIL.format(tenant_id=tenant_id, application_id=app_id),
            headers=headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["id"] == app_id
        assert data["name"] == app_data["name"]
        assert data["description"] == app_data["description"]
    
    def test_get_application_not_found(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test application retrieval with non-existent ID."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        response = test_client.get(
            ENDPOINT_APPLICATION_DETAIL.format(tenant_id=tenant_id, application_id=NON_EXISTENT_ID),
            headers=headers
        )
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
    
    def test_list_applications_empty(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test listing applications when none exist."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        response = test_client.get(
            ENDPOINT_APPLICATIONS.format(tenant_id=tenant_id),
            headers=headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert isinstance(data, list)
        assert len(data) == 0
    
    def test_list_applications_with_data(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test listing applications with existing data."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        # Create multiple applications
        app1_data = {"name": "App 1", "description": "First app", "type": "N8N"}
        app2_data = {"name": "App 2", "description": "Second app", "type": "N8N"}
        
        test_client.post(
            ENDPOINT_APPLICATIONS.format(tenant_id=tenant_id),
            json=app1_data,
            headers=headers
        )
        test_client.post(
            ENDPOINT_APPLICATIONS.format(tenant_id=tenant_id),
            json=app2_data,
            headers=headers
        )
        
        # List applications
        response = test_client.get(
            ENDPOINT_APPLICATIONS.format(tenant_id=tenant_id),
            headers=headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert isinstance(data, list)
        assert len(data) == 2
        
        names = [app["name"] for app in data]
        assert "App 1" in names
        assert "App 2" in names
    
    def test_list_applications_with_pagination(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test listing applications with pagination parameters."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        # Create multiple applications
        for i in range(5):
            test_client.post(
                ENDPOINT_APPLICATIONS.format(tenant_id=tenant_id),
                json={"name": f"App {i}", "description": f"Description {i}", "type": "N8N"},
                headers=headers
            )
        
        # Test with limit
        response = test_client.get(
            f"{ENDPOINT_APPLICATIONS.format(tenant_id=tenant_id)}?limit=3",
            headers=headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 3
        
        # Test with skip
        response = test_client.get(
            f"{ENDPOINT_APPLICATIONS.format(tenant_id=tenant_id)}?skip=2&limit=2",
            headers=headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 2
    
    def test_list_applications_with_name_filter(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test listing applications with name filter."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        # Create applications with different names
        test_client.post(
            ENDPOINT_APPLICATIONS.format(tenant_id=tenant_id),
            json={"name": "Production App", "description": "Prod", "type": "N8N"},
            headers=headers
        )
        test_client.post(
            ENDPOINT_APPLICATIONS.format(tenant_id=tenant_id),
            json={"name": "Development App", "description": "Dev", "type": "N8N"},
            headers=headers
        )
        
        # Filter by name
        response = test_client.get(
            f"{ENDPOINT_APPLICATIONS.format(tenant_id=tenant_id)}?name_filter=Production",
            headers=headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "Production App"
    
    def test_list_applications_with_quick_list_view(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test listing applications with quick-list view returns only id and name."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        # Create applications with valid N8N config
        n8n_config = get_valid_n8n_config()
        test_client.post(
            ENDPOINT_APPLICATIONS.format(tenant_id=tenant_id),
            json={"name": "App One", "description": "First app", "type": "N8N", "config": n8n_config},
            headers=headers
        )
        test_client.post(
            ENDPOINT_APPLICATIONS.format(tenant_id=tenant_id),
            json={"name": "App Two", "description": "Second app", "type": "N8N"},
            headers=headers
        )
        
        # Get with quick-list view
        response = test_client.get(
            f"{ENDPOINT_APPLICATIONS.format(tenant_id=tenant_id)}?view=quick-list",
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
            assert "type" not in item
    
    def test_list_applications_with_order_by_name_asc(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test listing applications ordered by name ascending."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        # Create applications with different names (in non-alphabetical order)
        test_client.post(
            ENDPOINT_APPLICATIONS.format(tenant_id=tenant_id),
            json={"name": "Zebra App", "description": "Z app", "type": "N8N"},
            headers=headers
        )
        test_client.post(
            ENDPOINT_APPLICATIONS.format(tenant_id=tenant_id),
            json={"name": "Alpha App", "description": "A app", "type": "N8N"},
            headers=headers
        )
        test_client.post(
            ENDPOINT_APPLICATIONS.format(tenant_id=tenant_id),
            json={"name": "Middle App", "description": "M app", "type": "N8N"},
            headers=headers
        )
        
        # Order by name ascending
        response = test_client.get(
            f"{ENDPOINT_APPLICATIONS.format(tenant_id=tenant_id)}?order_by=name&order_direction=asc",
            headers=headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 3
        assert data[0]["name"] == "Alpha App"
        assert data[1]["name"] == "Middle App"
        assert data[2]["name"] == "Zebra App"
    
    def test_list_applications_with_order_by_name_desc(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test listing applications ordered by name descending."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        # Create applications with different names
        test_client.post(
            ENDPOINT_APPLICATIONS.format(tenant_id=tenant_id),
            json={"name": "Alpha App", "description": "A app", "type": "N8N"},
            headers=headers
        )
        test_client.post(
            ENDPOINT_APPLICATIONS.format(tenant_id=tenant_id),
            json={"name": "Zebra App", "description": "Z app", "type": "N8N"},
            headers=headers
        )
        
        # Order by name descending
        response = test_client.get(
            f"{ENDPOINT_APPLICATIONS.format(tenant_id=tenant_id)}?order_by=name&order_direction=desc",
            headers=headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 2
        assert data[0]["name"] == "Zebra App"
        assert data[1]["name"] == "Alpha App"
    
    def test_list_applications_with_order_by_created_at(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test listing applications ordered by created_at."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        # Create first application
        resp1 = test_client.post(
            ENDPOINT_APPLICATIONS.format(tenant_id=tenant_id),
            json={"name": "First App", "description": "First", "type": "N8N"},
            headers=headers
        )
        first_created_at = resp1.json()["created_at"]
        
        # Wait briefly to ensure different timestamp (now with microsecond precision)
        time.sleep(0.01)
        
        # Create second application
        resp2 = test_client.post(
            ENDPOINT_APPLICATIONS.format(tenant_id=tenant_id),
            json={"name": "Second App", "description": "Second", "type": "N8N"},
            headers=headers
        )
        second_created_at = resp2.json()["created_at"]
        
        # Verify that second was created after first
        assert second_created_at > first_created_at, f"Second ({second_created_at}) should be after First ({first_created_at})"
        
        # Order by created_at descending (newest first)
        response = test_client.get(
            f"{ENDPOINT_APPLICATIONS.format(tenant_id=tenant_id)}?order_by=created_at&order_direction=desc",
            headers=headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 2
        # Second app should be first (newest)
        assert data[0]["name"] == "Second App", f"Expected 'Second App' first but got {data[0]['name']}. Data: {[(d['name'], d['created_at']) for d in data]}"
        assert data[1]["name"] == "First App"
    
    def test_list_applications_order_by_without_direction_defaults_to_asc(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test that order_by without direction defaults to ascending."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        # Create applications
        test_client.post(
            ENDPOINT_APPLICATIONS.format(tenant_id=tenant_id),
            json={"name": "Zebra App", "description": "Z app", "type": "N8N"},
            headers=headers
        )
        test_client.post(
            ENDPOINT_APPLICATIONS.format(tenant_id=tenant_id),
            json={"name": "Alpha App", "description": "A app", "type": "N8N"},
            headers=headers
        )
        
        # Order by name without specifying direction
        response = test_client.get(
            f"{ENDPOINT_APPLICATIONS.format(tenant_id=tenant_id)}?order_by=name",
            headers=headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 2
        # Should be ascending by default
        assert data[0]["name"] == "Alpha App"
        assert data[1]["name"] == "Zebra App"
    
    def test_list_applications_invalid_order_by_column_ignored(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test that invalid order_by column is silently ignored."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        # Create applications
        test_client.post(
            ENDPOINT_APPLICATIONS.format(tenant_id=tenant_id),
            json={"name": "Test App", "description": "Test", "type": "N8N"},
            headers=headers
        )
        
        # Use invalid column name - should not cause error
        response = test_client.get(
            f"{ENDPOINT_APPLICATIONS.format(tenant_id=tenant_id)}?order_by=invalid_column",
            headers=headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 1
    
    def test_update_application_success(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test successful application update."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        # Create an application
        app_data = {"name": "Original Name", "description": "Original", "type": "N8N"}
        create_response = test_client.post(
            ENDPOINT_APPLICATIONS.format(tenant_id=tenant_id),
            json=app_data,
            headers=headers
        )
        app_id = create_response.json()["id"]
        
        # Update the application
        update_data = {"name": "Updated Name", "description": "Updated"}
        update_response = test_client.patch(
            ENDPOINT_APPLICATION_DETAIL.format(tenant_id=tenant_id, application_id=app_id),
            json=update_data,
            headers=headers
        )
        
        assert update_response.status_code == status.HTTP_200_OK
        data = update_response.json()
        
        assert data["name"] == update_data["name"]
        assert data["description"] == update_data["description"]
        assert data["id"] == app_id
    
    def test_update_application_not_found(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test application update with non-existent ID."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        response = test_client.patch(
            ENDPOINT_APPLICATION_DETAIL.format(tenant_id=tenant_id, application_id=NON_EXISTENT_ID),
            json={"name": "Updated"},
            headers=headers
        )
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
    
    def test_update_application_partial(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test partial application update."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        # Create an application
        app_data = {"name": "Original", "description": "Description", "type": "N8N"}
        create_response = test_client.post(
            ENDPOINT_APPLICATIONS.format(tenant_id=tenant_id),
            json=app_data,
            headers=headers
        )
        app_id = create_response.json()["id"]
        
        # Update only name
        update_response = test_client.patch(
            ENDPOINT_APPLICATION_DETAIL.format(tenant_id=tenant_id, application_id=app_id),
            json={"name": "Only Name Updated"},
            headers=headers
        )
        
        assert update_response.status_code == status.HTTP_200_OK
        data = update_response.json()
        
        assert data["name"] == "Only Name Updated"
        assert data["description"] == app_data["description"]  # Should remain unchanged
    
    def test_update_application_is_active(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test updating application is_active status."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        # Create an application (default is_active=False)
        app_data = {"name": "Test App", "description": "Test", "type": "N8N"}
        create_response = test_client.post(
            ENDPOINT_APPLICATIONS.format(tenant_id=tenant_id),
            json=app_data,
            headers=headers
        )
        app_id = create_response.json()["id"]
        assert create_response.json()["is_active"] == False
        
        # Update to active
        update_response = test_client.patch(
            ENDPOINT_APPLICATION_DETAIL.format(tenant_id=tenant_id, application_id=app_id),
            json={"is_active": True},
            headers=headers
        )
        
        assert update_response.status_code == status.HTTP_200_OK
        assert update_response.json()["is_active"] == True
        
        # Update back to inactive
        update_response2 = test_client.patch(
            ENDPOINT_APPLICATION_DETAIL.format(tenant_id=tenant_id, application_id=app_id),
            json={"is_active": False},
            headers=headers
        )
        
        assert update_response2.status_code == status.HTTP_200_OK
        assert update_response2.json()["is_active"] == False
    
    def test_update_application_type(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test updating application type."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        # Create application with N8N type
        create_response = test_client.post(
            ENDPOINT_APPLICATIONS.format(tenant_id=tenant_id),
            json={"name": "Test App", "description": "Test", "type": "N8N"},
            headers=headers
        )
        app_id = create_response.json()["id"]
        assert create_response.json()["type"] == "N8N"
        
        # Update to REST_API type
        update_response = test_client.patch(
            ENDPOINT_APPLICATION_DETAIL.format(tenant_id=tenant_id, application_id=app_id),
            json={"type": "REST_API"},
            headers=headers
        )
        
        if update_response.status_code != status.HTTP_200_OK:
            print(f"Status: {update_response.status_code}, Body: {update_response.json()}")
        assert update_response.status_code == status.HTTP_200_OK
        assert update_response.json()["type"] == "REST_API"
    
    def test_update_application_config(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test updating application config."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        # Create application with initial valid N8N config
        initial_config = get_valid_n8n_config()
        create_response = test_client.post(
            ENDPOINT_APPLICATIONS.format(tenant_id=tenant_id),
            json={"name": "Test App", "description": "Test", "type": "N8N", "config": initial_config},
            headers=headers
        )
        app_id = create_response.json()["id"]
        assert create_response.json()["config"] == initial_config
        
        # Update config with a new valid N8N config (different chat URL)
        updated_config = get_valid_n8n_config()
        updated_config["chat_url"] = "https://updated.example.com/webhook"
        updated_config["chat_history_count"] = 50
        
        update_response = test_client.patch(
            ENDPOINT_APPLICATION_DETAIL.format(tenant_id=tenant_id, application_id=app_id),
            json={"config": updated_config},
            headers=headers
        )
        
        assert update_response.status_code == status.HTTP_200_OK
        assert update_response.json()["config"] == updated_config
    
    def test_delete_application_success(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test successful application deletion."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        # Create an application
        app_data = {"name": "To Delete", "description": "Will be deleted", "type": "N8N"}
        create_response = test_client.post(
            ENDPOINT_APPLICATIONS.format(tenant_id=tenant_id),
            json=app_data,
            headers=headers
        )
        app_id = create_response.json()["id"]
        
        # Delete the application
        delete_response = test_client.request(
            "DELETE",
            ENDPOINT_APPLICATION_DETAIL.format(tenant_id=tenant_id, application_id=app_id),
            headers=headers
        )
        
        assert delete_response.status_code == status.HTTP_204_NO_CONTENT
        
        # Verify it's deleted
        get_response = test_client.get(
            ENDPOINT_APPLICATION_DETAIL.format(tenant_id=tenant_id, application_id=app_id),
            headers=headers
        )
        
        assert get_response.status_code == status.HTTP_404_NOT_FOUND
    
    def test_delete_application_not_found(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test application deletion with non-existent ID."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        response = test_client.request(
            "DELETE",
            ENDPOINT_APPLICATION_DETAIL.format(tenant_id=tenant_id, application_id=NON_EXISTENT_ID),
            headers=headers
        )
        
        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestApplicationPrincipalRoutes:
    """Test suite for application principal/permission management routes."""
    
    def test_list_application_principals_creator_only(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test that only creator has permissions initially."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        # Create an application
        app_data = {"name": "Test App", "description": "Test", "type": "N8N"}
        create_response = test_client.post(
            ENDPOINT_APPLICATIONS.format(tenant_id=tenant_id),
            json=app_data,
            headers=headers
        )
        app_id = create_response.json()["id"]
        
        # List principals
        response = test_client.get(
            ENDPOINT_APPLICATION_PRINCIPALS.format(tenant_id=tenant_id, application_id=app_id),
            headers=headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert "resource_id" in data
        assert "resource_type" in data
        assert data["resource_type"] == "application"
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
        
        # Create an application
        app_data = {"name": "Test App", "description": "Test", "type": "N8N"}
        create_response = test_client.post(
            ENDPOINT_APPLICATIONS.format(tenant_id=tenant_id),
            json=app_data,
            headers=headers
        )
        app_id = create_response.json()["id"]
        
        # Get creator's permissions
        response = test_client.get(
            ENDPOINT_PRINCIPAL_DETAIL.format(
                tenant_id=tenant_id,
                application_id=app_id,
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
        
        # Create an application
        app_data = {"name": "Test App", "description": "Test", "type": "N8N"}
        create_response = test_client.post(
            ENDPOINT_APPLICATIONS.format(tenant_id=tenant_id),
            json=app_data,
            headers=headers
        )
        app_id = create_response.json()["id"]
        
        # Add permission for another user
        permission_data = {
            "principal_id": "other-user",
            "principal_type": PRINCIPAL_TYPE_USER,
            "role": ROLE_READ
        }
        
        response = test_client.put(
            ENDPOINT_APPLICATION_PRINCIPALS.format(tenant_id=tenant_id, application_id=app_id),
            json=permission_data,
            headers=headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["principal_id"] == "other-user"
        assert data["principal_type"] == PRINCIPAL_TYPE_USER
        assert ROLE_READ in data["roles"]
    
    def test_set_principal_permission_update_existing(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test updating an existing principal's permission."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        # Create an application
        app_data = {"name": "Test App", "description": "Test", "type": "N8N"}
        create_response = test_client.post(
            ENDPOINT_APPLICATIONS.format(tenant_id=tenant_id),
            json=app_data,
            headers=headers
        )
        app_id = create_response.json()["id"]
        
        # Add READ permission
        test_client.put(
            ENDPOINT_APPLICATION_PRINCIPALS.format(tenant_id=tenant_id, application_id=app_id),
            json={
                "principal_id": "other-user",
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_READ
            },
            headers=headers
        )
        
        # Update to WRITE permission
        update_response = test_client.put(
            ENDPOINT_APPLICATION_PRINCIPALS.format(tenant_id=tenant_id, application_id=app_id),
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
        assert ROLE_WRITE in data["roles"]
    
    def test_set_principal_permission_missing_principal_id(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test setting permission with missing principal_id."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        # Create an application
        app_data = {"name": "Test App", "description": "Test", "type": "N8N"}
        create_response = test_client.post(
            ENDPOINT_APPLICATIONS.format(tenant_id=tenant_id),
            json=app_data,
            headers=headers
        )
        app_id = create_response.json()["id"]
        
        response = test_client.put(
            ENDPOINT_APPLICATION_PRINCIPALS.format(tenant_id=tenant_id, application_id=app_id),
            json={"role": ROLE_READ},
            headers=headers
        )
        
        assert response.status_code == 422
    
    def test_set_principal_permission_missing_role(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test setting permission with missing role."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        # Create an application
        app_data = {"name": "Test App", "description": "Test", "type": "N8N"}
        create_response = test_client.post(
            ENDPOINT_APPLICATIONS.format(tenant_id=tenant_id),
            json=app_data,
            headers=headers
        )
        app_id = create_response.json()["id"]
        
        response = test_client.put(
            ENDPOINT_APPLICATION_PRINCIPALS.format(tenant_id=tenant_id, application_id=app_id),
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
        
        # Create an application
        app_data = {"name": "Test App", "description": "Test", "type": "N8N"}
        create_response = test_client.post(
            ENDPOINT_APPLICATIONS.format(tenant_id=tenant_id),
            json=app_data,
            headers=headers
        )
        app_id = create_response.json()["id"]
        
        response = test_client.put(
            ENDPOINT_APPLICATION_PRINCIPALS.format(tenant_id=tenant_id, application_id=app_id),
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
        
        # Create an application
        app_data = {"name": "Test App", "description": "Test", "type": "N8N"}
        create_response = test_client.post(
            ENDPOINT_APPLICATIONS.format(tenant_id=tenant_id),
            json=app_data,
            headers=headers
        )
        app_id = create_response.json()["id"]
        
        response = test_client.put(
            ENDPOINT_APPLICATION_PRINCIPALS.format(tenant_id=tenant_id, application_id=app_id),
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
        
        # Create an application
        app_data = {"name": "Test App", "description": "Test", "type": "N8N"}
        create_response = test_client.post(
            ENDPOINT_APPLICATIONS.format(tenant_id=tenant_id),
            json=app_data,
            headers=headers
        )
        app_id = create_response.json()["id"]
        
        # Add permission
        test_client.put(
            ENDPOINT_APPLICATION_PRINCIPALS.format(tenant_id=tenant_id, application_id=app_id),
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
            ENDPOINT_APPLICATION_PRINCIPALS.format(tenant_id=tenant_id, application_id=app_id),
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
                application_id=app_id,
                principal_id="other-user"
            ),
            headers=headers
        )
        
        assert get_response.status_code == status.HTTP_404_NOT_FOUND
    
    def test_delete_principal_permission_not_found(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test deleting a non-existent permission."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        # Create an application
        app_data = {"name": "Test App", "description": "Test", "type": "N8N"}
        create_response = test_client.post(
            ENDPOINT_APPLICATIONS.format(tenant_id=tenant_id),
            json=app_data,
            headers=headers
        )
        app_id = create_response.json()["id"]
        
        # Try to delete non-existent permission
        response = test_client.request(
            "DELETE",
            ENDPOINT_APPLICATION_PRINCIPALS.format(tenant_id=tenant_id, application_id=app_id),
            json={
                "principal_id": "non-existent-user",
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_READ
            },
            headers=headers
        )
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
