"""Tests for tags caching behavior."""
from typing import Any
from fastapi import status
from starlette.testclient import TestClient

from aihub.core.database.enums import PermissionActionEnum, PrincipalTypeEnum
from tests.conftest import create_auth_headers


# API Endpoints
ENDPOINT_TENANTS = "/api/v1/tenants"
ENDPOINT_TAGS = "/api/v1/tenants/{tenant_id}/tags"
ENDPOINT_TAG_DETAIL = "/api/v1/tenants/{tenant_id}/tags/{tag_id}"
ENDPOINT_APPLICATIONS = "/api/v1/tenants/{tenant_id}/applications"
ENDPOINT_APPLICATION_DETAIL = "/api/v1/tenants/{tenant_id}/applications/{application_id}"
ENDPOINT_APPLICATION_TAGS = "/api/v1/tenants/{tenant_id}/applications/{application_id}/tags"
ENDPOINT_APPLICATION_PRINCIPALS = "/api/v1/tenants/{tenant_id}/applications/{application_id}/principals"
ENDPOINT_AUTONOMOUS_AGENTS = "/api/v1/tenants/{tenant_id}/autonomous-agents"
ENDPOINT_AUTONOMOUS_AGENT_DETAIL = "/api/v1/tenants/{tenant_id}/autonomous-agents/{autonomous_agent_id}"
ENDPOINT_AUTONOMOUS_AGENT_TAGS = "/api/v1/tenants/{tenant_id}/autonomous-agents/{autonomous_agent_id}/tags"

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


def create_application(test_client: TestClient, tenant_id: str, headers: dict, app_name: str = "Test App") -> str:
    """Helper function to create an application and return its ID."""
    response = test_client.post(
        ENDPOINT_APPLICATIONS.format(tenant_id=tenant_id),
        json={"name": app_name, "description": f"Application {app_name}"},
        headers=headers
    )
    assert response.status_code == status.HTTP_201_CREATED
    return response.json()["id"]


def create_autonomous_agent(test_client: TestClient, tenant_id: str, headers: dict, name: str = "Test Agent") -> str:
    """Helper function to create an autonomous agent and return its ID."""
    response = test_client.post(
        ENDPOINT_AUTONOMOUS_AGENTS.format(tenant_id=tenant_id),
        json={"name": name, "description": f"Agent {name}"},
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


def create_tag(test_client: TestClient, tenant_id: str, headers: dict, name: str) -> str:
    """Helper function to create a tag and return its ID."""
    response = test_client.post(
        ENDPOINT_TAGS.format(tenant_id=tenant_id),
        json={"name": name},
        headers=headers
    )
    assert response.status_code == status.HTTP_201_CREATED
    return response.json()["id"]


class TestTagCaching:
    """Test suite for tag caching behavior."""
    
    def test_tags_cached_on_list(self, test_client: TestClient, fake_redis_client: Any) -> None:
        """Test that tag list is cached correctly."""
        # Create user and tenant
        user_token = test_client.create_test_user("tag-cache-1", "Tag Cache 1")
        headers = create_auth_headers(user_token)
        tenant_id = create_tenant_for_user(test_client, user_token)
        
        # Create tags
        create_tag(test_client, tenant_id, headers, "tag1")
        create_tag(test_client, tenant_id, headers, "tag2")
        
        # First access - should cache
        response1 = test_client.get(
            ENDPOINT_TAGS.format(tenant_id=tenant_id),
            headers=headers
        )
        assert response1.status_code == status.HTTP_200_OK
        assert response1.json()["total"] == 2
        
        # Second access - should use cache
        response2 = test_client.get(
            ENDPOINT_TAGS.format(tenant_id=tenant_id),
            headers=headers
        )
        assert response2.status_code == status.HTTP_200_OK
        assert response2.json()["total"] == 2
    
    def test_tag_creation_invalidates_list_cache(self, test_client: TestClient, fake_redis_client: Any) -> None:
        """Test that creating a tag invalidates the list cache."""
        user_token = test_client.create_test_user("tag-cache-2", "Tag Cache 2")
        headers = create_auth_headers(user_token)
        tenant_id = create_tenant_for_user(test_client, user_token)
        
        # Create initial tag and cache the list
        create_tag(test_client, tenant_id, headers, "initial-tag")
        response1 = test_client.get(
            ENDPOINT_TAGS.format(tenant_id=tenant_id),
            headers=headers
        )
        assert response1.json()["total"] == 1
        
        # Create another tag (should invalidate cache)
        create_tag(test_client, tenant_id, headers, "new-tag")
        
        # List should now show 2 tags
        response2 = test_client.get(
            ENDPOINT_TAGS.format(tenant_id=tenant_id),
            headers=headers
        )
        assert response2.json()["total"] == 2
    
    def test_tag_deletion_invalidates_list_cache(self, test_client: TestClient, fake_redis_client: Any) -> None:
        """Test that deleting a tag invalidates the list cache."""
        user_token = test_client.create_test_user("tag-cache-3", "Tag Cache 3")
        headers = create_auth_headers(user_token)
        tenant_id = create_tenant_for_user(test_client, user_token)
        
        # Create tags and cache the list
        tag1_id = create_tag(test_client, tenant_id, headers, "tag-to-keep")
        tag2_id = create_tag(test_client, tenant_id, headers, "tag-to-delete")
        
        response1 = test_client.get(
            ENDPOINT_TAGS.format(tenant_id=tenant_id),
            headers=headers
        )
        assert response1.json()["total"] == 2
        
        # Delete one tag
        test_client.delete(
            ENDPOINT_TAG_DETAIL.format(tenant_id=tenant_id, tag_id=tag2_id),
            headers=headers
        )
        
        # List should now show 1 tag
        response2 = test_client.get(
            ENDPOINT_TAGS.format(tenant_id=tenant_id),
            headers=headers
        )
        assert response2.json()["total"] == 1


class TestResourceTagCacheInvalidation:
    """Test suite for cache invalidation when adding/removing tags from resources."""
    
    def test_adding_tags_to_application_invalidates_cache(self, test_client: TestClient, fake_redis_client: Any) -> None:
        """Test that adding tags to an application invalidates the application cache."""
        admin_token = test_client.create_test_user("app-tag-cache-1", "App Tag Cache 1")
        admin_headers = create_auth_headers(admin_token)
        tenant_id = create_tenant_for_user(test_client, admin_token)
        app_id = create_application(test_client, tenant_id, admin_headers, "Cached App")
        
        # First read - cache the application (no tags)
        response1 = test_client.get(
            ENDPOINT_APPLICATION_DETAIL.format(tenant_id=tenant_id, application_id=app_id),
            headers=admin_headers
        )
        assert response1.status_code == status.HTTP_200_OK
        assert response1.json()["tags"] == []
        
        # Add tags to application
        test_client.put(
            ENDPOINT_APPLICATION_TAGS.format(tenant_id=tenant_id, application_id=app_id),
            json={"tags": ["production", "critical"]},
            headers=admin_headers
        )
        
        # Read application again - should see the tags (cache invalidated)
        response2 = test_client.get(
            ENDPOINT_APPLICATION_DETAIL.format(tenant_id=tenant_id, application_id=app_id),
            headers=admin_headers
        )
        assert response2.status_code == status.HTTP_200_OK
        assert len(response2.json()["tags"]) == 2
    
    def test_removing_tags_from_application_invalidates_cache(self, test_client: TestClient, fake_redis_client: Any) -> None:
        """Test that removing tags from an application invalidates the application cache."""
        admin_token = test_client.create_test_user("app-tag-cache-2", "App Tag Cache 2")
        admin_headers = create_auth_headers(admin_token)
        tenant_id = create_tenant_for_user(test_client, admin_token)
        app_id = create_application(test_client, tenant_id, admin_headers, "Cached App 2")
        
        # Set initial tags
        test_client.put(
            ENDPOINT_APPLICATION_TAGS.format(tenant_id=tenant_id, application_id=app_id),
            json={"tags": ["tag1", "tag2"]},
            headers=admin_headers
        )
        
        # Read and cache
        response1 = test_client.get(
            ENDPOINT_APPLICATION_DETAIL.format(tenant_id=tenant_id, application_id=app_id),
            headers=admin_headers
        )
        assert len(response1.json()["tags"]) == 2
        
        # Remove tags
        test_client.delete(
            ENDPOINT_APPLICATION_TAGS.format(tenant_id=tenant_id, application_id=app_id),
            headers=admin_headers
        )
        
        # Read application again - should see no tags
        response2 = test_client.get(
            ENDPOINT_APPLICATION_DETAIL.format(tenant_id=tenant_id, application_id=app_id),
            headers=admin_headers
        )
        assert response2.json()["tags"] == []
    
    def test_replacing_tags_invalidates_cache(self, test_client: TestClient, fake_redis_client: Any) -> None:
        """Test that replacing tags invalidates the application cache."""
        admin_token = test_client.create_test_user("app-tag-cache-3", "App Tag Cache 3")
        admin_headers = create_auth_headers(admin_token)
        tenant_id = create_tenant_for_user(test_client, admin_token)
        app_id = create_application(test_client, tenant_id, admin_headers, "Cached App 3")
        
        # Set initial tags
        test_client.put(
            ENDPOINT_APPLICATION_TAGS.format(tenant_id=tenant_id, application_id=app_id),
            json={"tags": ["old-tag-1", "old-tag-2"]},
            headers=admin_headers
        )
        
        # Read and cache
        response1 = test_client.get(
            ENDPOINT_APPLICATION_DETAIL.format(tenant_id=tenant_id, application_id=app_id),
            headers=admin_headers
        )
        tag_names1 = [t["name"] for t in response1.json()["tags"]]
        assert "old-tag-1" in tag_names1
        assert "old-tag-2" in tag_names1
        
        # Replace with new tags
        test_client.put(
            ENDPOINT_APPLICATION_TAGS.format(tenant_id=tenant_id, application_id=app_id),
            json={"tags": ["new-tag-1", "new-tag-2", "new-tag-3"]},
            headers=admin_headers
        )
        
        # Read application again - should see new tags
        response2 = test_client.get(
            ENDPOINT_APPLICATION_DETAIL.format(tenant_id=tenant_id, application_id=app_id),
            headers=admin_headers
        )
        tag_names2 = [t["name"] for t in response2.json()["tags"]]
        assert len(tag_names2) == 3
        assert "new-tag-1" in tag_names2
        assert "new-tag-2" in tag_names2
        assert "new-tag-3" in tag_names2
        assert "old-tag-1" not in tag_names2
    
    def test_adding_tags_to_autonomous_agent_invalidates_cache(self, test_client: TestClient, fake_redis_client: Any) -> None:
        """Test that adding tags to an autonomous agent invalidates the agent cache."""
        admin_token = test_client.create_test_user("agent-tag-cache-1", "Agent Tag Cache 1")
        admin_headers = create_auth_headers(admin_token)
        tenant_id = create_tenant_for_user(test_client, admin_token)
        agent_id = create_autonomous_agent(test_client, tenant_id, admin_headers, "Cached Agent")
        
        # First read - cache the agent (no tags)
        response1 = test_client.get(
            ENDPOINT_AUTONOMOUS_AGENT_DETAIL.format(tenant_id=tenant_id, autonomous_agent_id=agent_id),
            headers=admin_headers
        )
        assert response1.status_code == status.HTTP_200_OK
        assert response1.json()["tags"] == []
        
        # Add tags to agent
        test_client.put(
            ENDPOINT_AUTONOMOUS_AGENT_TAGS.format(tenant_id=tenant_id, autonomous_agent_id=agent_id),
            json={"tags": ["ai", "ml"]},
            headers=admin_headers
        )
        
        # Read agent again - should see the tags
        response2 = test_client.get(
            ENDPOINT_AUTONOMOUS_AGENT_DETAIL.format(tenant_id=tenant_id, autonomous_agent_id=agent_id),
            headers=admin_headers
        )
        assert len(response2.json()["tags"]) == 2
    
    def test_applications_list_cache_invalidated_on_tag_change(self, test_client: TestClient, fake_redis_client: Any) -> None:
        """Test that the applications list cache is invalidated when tags change."""
        admin_token = test_client.create_test_user("app-list-tag-cache-1", "App List Tag Cache 1")
        admin_headers = create_auth_headers(admin_token)
        tenant_id = create_tenant_for_user(test_client, admin_token)
        
        # Create multiple applications
        app1_id = create_application(test_client, tenant_id, admin_headers, "App 1")
        app2_id = create_application(test_client, tenant_id, admin_headers, "App 2")
        
        # Set tags on app1
        test_client.put(
            ENDPOINT_APPLICATION_TAGS.format(tenant_id=tenant_id, application_id=app1_id),
            json={"tags": ["production"]},
            headers=admin_headers
        )
        
        # Get tag ID
        tags_response = test_client.get(
            ENDPOINT_TAGS.format(tenant_id=tenant_id) + "?name=production",
            headers=admin_headers
        )
        prod_tag_id = tags_response.json()["tags"][0]["id"]
        
        # List applications filtered by production tag - cache this
        response1 = test_client.get(
            ENDPOINT_APPLICATIONS.format(tenant_id=tenant_id) + f"?tags={prod_tag_id}",
            headers=admin_headers
        )
        assert len(response1.json()) == 1
        assert response1.json()[0]["name"] == "App 1"
        
        # Add production tag to app2
        test_client.put(
            ENDPOINT_APPLICATION_TAGS.format(tenant_id=tenant_id, application_id=app2_id),
            json={"tags": ["production"]},
            headers=admin_headers
        )
        
        # List again - should now show 2 apps
        response2 = test_client.get(
            ENDPOINT_APPLICATIONS.format(tenant_id=tenant_id) + f"?tags={prod_tag_id}",
            headers=admin_headers
        )
        assert len(response2.json()) == 2
    
    def test_user_with_write_permission_tag_changes_visible(self, test_client: TestClient, fake_redis_client: Any) -> None:
        """Test that tag changes made by user with WRITE permission are visible immediately."""
        admin_token = test_client.create_test_user("write-tag-cache-1", "Write Tag Cache 1")
        admin_headers = create_auth_headers(admin_token)
        tenant_id = create_tenant_for_user(test_client, admin_token)
        app_id = create_application(test_client, tenant_id, admin_headers, "Shared App")
        
        # Create writer user with WRITE permission
        writer_token = test_client.create_test_user("write-tag-writer-1", "Write Tag Writer 1")
        writer_headers = create_auth_headers(writer_token)
        add_user_to_tenant(test_client, tenant_id, admin_headers, "write-tag-writer-1", "READER")
        test_client.put(
            ENDPOINT_APPLICATION_PRINCIPALS.format(tenant_id=tenant_id, application_id=app_id),
            json={"principal_id": "write-tag-writer-1", "principal_type": PRINCIPAL_TYPE_USER, "role": ROLE_WRITE},
            headers=admin_headers
        )
        
        # Admin reads application (caches it)
        response1 = test_client.get(
            ENDPOINT_APPLICATION_DETAIL.format(tenant_id=tenant_id, application_id=app_id),
            headers=admin_headers
        )
        assert response1.json()["tags"] == []
        
        # Writer adds tags
        test_client.put(
            ENDPOINT_APPLICATION_TAGS.format(tenant_id=tenant_id, application_id=app_id),
            json={"tags": ["writer-tag"]},
            headers=writer_headers
        )
        
        # Admin reads again - should see the new tags
        response2 = test_client.get(
            ENDPOINT_APPLICATION_DETAIL.format(tenant_id=tenant_id, application_id=app_id),
            headers=admin_headers
        )
        assert len(response2.json()["tags"]) == 1
        assert response2.json()["tags"][0]["name"] == "writer-tag"
    
    def test_deleting_tag_invalidates_resource_caches(self, test_client: TestClient, fake_redis_client: Any) -> None:
        """Test that deleting a tag invalidates caches of resources using that tag."""
        admin_token = test_client.create_test_user("delete-tag-cache-1", "Delete Tag Cache 1")
        admin_headers = create_auth_headers(admin_token)
        tenant_id = create_tenant_for_user(test_client, admin_token)
        app_id = create_application(test_client, tenant_id, admin_headers, "Tagged App")
        
        # Set tags on application
        test_client.put(
            ENDPOINT_APPLICATION_TAGS.format(tenant_id=tenant_id, application_id=app_id),
            json={"tags": ["to-delete", "to-keep"]},
            headers=admin_headers
        )
        
        # Read and cache application
        response1 = test_client.get(
            ENDPOINT_APPLICATION_DETAIL.format(tenant_id=tenant_id, application_id=app_id),
            headers=admin_headers
        )
        assert len(response1.json()["tags"]) == 2
        
        # Get the tag ID for "to-delete"
        tags_response = test_client.get(
            ENDPOINT_TAGS.format(tenant_id=tenant_id) + "?name=to-delete",
            headers=admin_headers
        )
        tag_id = tags_response.json()["tags"][0]["id"]
        
        # Delete the tag
        test_client.delete(
            ENDPOINT_TAG_DETAIL.format(tenant_id=tenant_id, tag_id=tag_id),
            headers=admin_headers
        )
        
        # Read application again - should only have one tag
        response2 = test_client.get(
            ENDPOINT_APPLICATION_DETAIL.format(tenant_id=tenant_id, application_id=app_id),
            headers=admin_headers
        )
        assert len(response2.json()["tags"]) == 1
        assert response2.json()["tags"][0]["name"] == "to-keep"
