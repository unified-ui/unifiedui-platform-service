"""Tests for tags pagination and filtering."""
import uuid
from typing import Any
from fastapi import status
from starlette.testclient import TestClient

from tests.conftest import create_auth_headers


# API Endpoints
ENDPOINT_TENANTS = "/api/v1/tenants"
ENDPOINT_TAGS = "/api/v1/tenants/{tenant_id}/tags"
ENDPOINT_RESOURCE_TYPE_TAGS = "/api/v1/tenants/{tenant_id}/{resource_type}/tags"


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


def create_tag(test_client: TestClient, tenant_id: str, headers: dict, name: str) -> int:
    """Helper function to create a tag and return its ID."""
    response = test_client.post(
        ENDPOINT_TAGS.format(tenant_id=tenant_id),
        json={"name": name},
        headers=headers
    )
    assert response.status_code == status.HTTP_201_CREATED
    return response.json()["id"]


class TestTagsPagination:
    """Test suite for tags list pagination and filtering."""
    
    def test_list_tags_default_pagination(
        self, 
        test_client: TestClient, 
        test_user_token: Any
    ) -> None:
        """Test listing tags with default pagination (skip=0, limit=100)."""
        # Setup
        headers = create_auth_headers(test_user_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        
        # Create 5 tags
        for i in range(5):
            create_tag(test_client, tenant_id, headers, f"TAG{i}")
        
        # Test
        response = test_client.get(
            ENDPOINT_TAGS.format(tenant_id=tenant_id),
            headers=headers
        )
        
        # Verify
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 5
    
    def test_list_tags_with_limit(
        self, 
        test_client: TestClient, 
        test_user_token: Any
    ) -> None:
        """Test listing tags with custom limit."""
        # Setup
        headers = create_auth_headers(test_user_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        
        # Create 10 tags
        for i in range(10):
            create_tag(test_client, tenant_id, headers, f"TAG{i:02d}")
        
        # Test with limit=5
        response = test_client.get(
            ENDPOINT_TAGS.format(tenant_id=tenant_id),
            params={"limit": 5},
            headers=headers
        )
        
        # Verify
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 5
    
    def test_list_tags_with_skip(
        self, 
        test_client: TestClient, 
        test_user_token: Any
    ) -> None:
        """Test listing tags with skip parameter."""
        # Setup
        headers = create_auth_headers(test_user_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        
        # Create tags in alphabetical order
        tag_names = ["APPLE", "BANANA", "CHERRY", "DATE", "ELDERBERRY"]
        for name in tag_names:
            create_tag(test_client, tenant_id, headers, name)
        
        # Test with skip=2
        response = test_client.get(
            ENDPOINT_TAGS.format(tenant_id=tenant_id),
            params={"skip": 2},
            headers=headers
        )
        
        # Verify
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 3
        # Should return last 3 tags (CHERRY, DATE, ELDERBERRY)
        returned_names = [tag["name"] for tag in data]
        assert "CHERRY" in returned_names
        assert "DATE" in returned_names
        assert "ELDERBERRY" in returned_names
    
    def test_list_tags_with_skip_and_limit(
        self, 
        test_client: TestClient, 
        test_user_token: Any
    ) -> None:
        """Test listing tags with both skip and limit."""
        # Setup
        headers = create_auth_headers(test_user_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        
        # Create 10 tags
        for i in range(10):
            create_tag(test_client, tenant_id, headers, f"TAG{i:02d}")
        
        # Test with skip=3, limit=4
        response = test_client.get(
            ENDPOINT_TAGS.format(tenant_id=tenant_id),
            params={"skip": 3, "limit": 4},
            headers=headers
        )
        
        # Verify
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 4
    
    def test_list_tags_with_name_filter(
        self, 
        test_client: TestClient, 
        test_user_token: Any
    ) -> None:
        """Test listing tags with name filter."""
        # Setup
        headers = create_auth_headers(test_user_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        
        # Create tags with different patterns
        create_tag(test_client, tenant_id, headers, "BACKEND")
        create_tag(test_client, tenant_id, headers, "FRONTEND")
        create_tag(test_client, tenant_id, headers, "DATABASE")
        create_tag(test_client, tenant_id, headers, "BACKOFFICE")
        
        # Test with name filter "BACK"
        response = test_client.get(
            ENDPOINT_TAGS.format(tenant_id=tenant_id),
            params={"name": "BACK"},
            headers=headers
        )
        
        # Verify
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 2
        names = [tag["name"] for tag in data]
        assert "BACKEND" in names
        assert "BACKOFFICE" in names
    
    def test_list_tags_name_filter_with_pagination(
        self, 
        test_client: TestClient, 
        test_user_token: Any
    ) -> None:
        """Test combining name filter with pagination."""
        # Setup
        headers = create_auth_headers(test_user_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        
        # Create tags
        for i in range(5):
            create_tag(test_client, tenant_id, headers, f"TAG{i:02d}")
        for i in range(5):
            create_tag(test_client, tenant_id, headers, f"LABEL{i:02d}")
        
        # Test with name filter and limit
        response = test_client.get(
            ENDPOINT_TAGS.format(tenant_id=tenant_id),
            params={"name": "TAG", "limit": 3},
            headers=headers
        )
        
        # Verify
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 3
    
    def test_list_tags_invalid_limit(
        self, 
        test_client: TestClient, 
        test_user_token: Any
    ) -> None:
        """Test listing tags with invalid limit."""
        # Setup
        headers = create_auth_headers(test_user_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        
        # Test with limit=0 (invalid)
        response = test_client.get(
            ENDPOINT_TAGS.format(tenant_id=tenant_id),
            params={"limit": 0},
            headers=headers
        )
        
        # Verify
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    
    def test_list_tags_negative_skip(
        self, 
        test_client: TestClient, 
        test_user_token: Any
    ) -> None:
        """Test listing tags with negative skip."""
        # Setup
        headers = create_auth_headers(test_user_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        
        # Test with skip=-1 (invalid)
        response = test_client.get(
            ENDPOINT_TAGS.format(tenant_id=tenant_id),
            params={"skip": -1},
            headers=headers
        )
        
        # Verify
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    
    def test_list_tags_skip_beyond_total(
        self, 
        test_client: TestClient, 
        test_user_token: Any
    ) -> None:
        """Test listing tags when skip is beyond total count."""
        # Setup
        headers = create_auth_headers(test_user_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        
        # Create 5 tags
        for i in range(5):
            create_tag(test_client, tenant_id, headers, f"TAG{i}")
        
        # Test with skip=10 (beyond total)
        response = test_client.get(
            ENDPOINT_TAGS.format(tenant_id=tenant_id),
            params={"skip": 10},
            headers=headers
        )
        
        # Verify
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 0


class TestResourceTypeTagsList:
    """Test suite for resource-type-specific tags list."""
    
    def test_list_application_tags(
        self, 
        test_client: TestClient, 
        test_user_token: Any
    ) -> None:
        """Test listing tags that are applied to applications."""
        # Setup
        headers = create_auth_headers(test_user_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        user_id = test_user_token.get_id()
        
        # Create application via API
        app_response = test_client.post(
            f"/api/v1/tenants/{tenant_id}/applications",
            json={
                "name": "Test App",
                "description": "Test",
                "type": "N8N",
                "config": {}
            },
            headers=headers
        )
        assert app_response.status_code == status.HTTP_201_CREATED
        app_id = app_response.json()["id"]
        
        # Create tags and assign to application
        tag1_id = create_tag(test_client, tenant_id, headers, "BACKEND")
        tag2_id = create_tag(test_client, tenant_id, headers, "PRODUCTION")
        create_tag(test_client, tenant_id, headers, "UNUSED")
        
        # Set tags on application
        test_client.put(
            f"/api/v1/tenants/{tenant_id}/applications/{app_id}/tags",
            json={"tags": ["BACKEND", "PRODUCTION"]},
            headers=headers
        )
        
        # Test
        response = test_client.get(
            ENDPOINT_RESOURCE_TYPE_TAGS.format(tenant_id=tenant_id, resource_type="applications"),
            headers=headers
        )
        
        # Verify
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 2
        tag_names = [tag["name"] for tag in data]
        assert "BACKEND" in tag_names
        assert "PRODUCTION" in tag_names
        assert "UNUSED" not in tag_names
    
    def test_list_autonomous_agent_tags(
        self, 
        test_client: TestClient, 
        test_user_token: Any
    ) -> None:
        """Test listing tags for autonomous agents."""
        # Setup
        headers = create_auth_headers(test_user_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        
        # Create agent via API
        agent_response = test_client.post(
            f"/api/v1/tenants/{tenant_id}/autonomous-agents",
            json={
                "name": "Test Agent",
                "description": "Test",
                "config": {}
            },
            headers=headers
        )
        assert agent_response.status_code == status.HTTP_201_CREATED
        agent_id = agent_response.json()["id"]
        
        # Create and assign tags
        create_tag(test_client, tenant_id, headers, "AI")
        create_tag(test_client, tenant_id, headers, "AUTOMATION")
        
        test_client.put(
            f"/api/v1/tenants/{tenant_id}/autonomous-agents/{agent_id}/tags",
            json={"tags": ["AI", "AUTOMATION"]},
            headers=headers
        )
        
        # Test
        response = test_client.get(
            ENDPOINT_RESOURCE_TYPE_TAGS.format(tenant_id=tenant_id, resource_type="autonomous-agents"),
            headers=headers
        )
        
        # Verify
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 2
    
    def test_list_resource_tags_with_name_filter(
        self, 
        test_client: TestClient, 
        test_user_token: Any
    ) -> None:
        """Test filtering resource tags by name."""
        # Setup
        headers = create_auth_headers(test_user_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        
        # Create application and tags
        app_response = test_client.post(
            f"/api/v1/tenants/{tenant_id}/applications",
            json={"name": "Test App", "description": "Test", "type": "N8N", "config": {}},
            headers=headers
        )
        app_id = app_response.json()["id"]
        
        create_tag(test_client, tenant_id, headers, "BACKEND")
        create_tag(test_client, tenant_id, headers, "BACKOFFICE")
        create_tag(test_client, tenant_id, headers, "FRONTEND")
        
        test_client.put(
            f"/api/v1/tenants/{tenant_id}/applications/{app_id}/tags",
            json={"tags": ["BACKEND", "BACKOFFICE", "FRONTEND"]},
            headers=headers
        )
        
        # Test with filter
        response = test_client.get(
            ENDPOINT_RESOURCE_TYPE_TAGS.format(tenant_id=tenant_id, resource_type="applications"),
            params={"name": "BACK"},
            headers=headers
        )
        
        # Verify
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        names = [tag["name"] for tag in data]
        assert "BACKEND" in names
        assert "BACKOFFICE" in names
    
    def test_list_resource_tags_with_pagination(
        self, 
        test_client: TestClient, 
        test_user_token: Any
    ) -> None:
        """Test paginating resource tags."""
        # Setup
        headers = create_auth_headers(test_user_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        
        # Create application with many tags
        app_response = test_client.post(
            f"/api/v1/tenants/{tenant_id}/applications",
            json={"name": "Test App", "description": "Test", "type": "N8N", "config": {}},
            headers=headers
        )
        app_id = app_response.json()["id"]
        
        # Create 10 tags and assign all
        tag_names = [f"TAG{i:02d}" for i in range(10)]
        for name in tag_names:
            create_tag(test_client, tenant_id, headers, name)
        
        test_client.put(
            f"/api/v1/tenants/{tenant_id}/applications/{app_id}/tags",
            json={"tags": tag_names},
            headers=headers
        )
        
        # Test with pagination
        response = test_client.get(
            ENDPOINT_RESOURCE_TYPE_TAGS.format(tenant_id=tenant_id, resource_type="applications"),
            params={"skip": 3, "limit": 4},
            headers=headers
        )
        
        # Verify
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 4
    
    def test_list_resource_tags_invalid_resource_type(
        self, 
        test_client: TestClient, 
        test_user_token: Any
    ) -> None:
        """Test listing tags with invalid resource type returns 404 (no route exists)."""
        # Setup
        headers = create_auth_headers(test_user_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        
        # Test with invalid resource type - since we have explicit routes for each
        # resource type, an invalid type will return 404 (Not Found)
        response = test_client.get(
            ENDPOINT_RESOURCE_TYPE_TAGS.format(tenant_id=tenant_id, resource_type="invalid-type"),
            headers=headers
        )
        
        # Verify - 404 because no route matches /invalid-type/tags
        assert response.status_code == status.HTTP_404_NOT_FOUND
    
    def test_list_resource_tags_empty(
        self, 
        test_client: TestClient, 
        test_user_token: Any
    ) -> None:
        """Test listing resource tags when none are assigned."""
        # Setup
        headers = create_auth_headers(test_user_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        
        # Create tags but don't assign to any resource
        create_tag(test_client, tenant_id, headers, "TAG1")
        create_tag(test_client, tenant_id, headers, "TAG2")
        
        # Test
        response = test_client.get(
            ENDPOINT_RESOURCE_TYPE_TAGS.format(tenant_id=tenant_id, resource_type="applications"),
            headers=headers
        )
        
        # Verify
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 0
