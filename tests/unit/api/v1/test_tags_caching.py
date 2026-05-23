"""Tests for tags caching behavior."""

import uuid
from typing import Any

from fastapi import status
from starlette.testclient import TestClient

from tests.conftest import create_auth_headers
from tests.helpers.tenant import add_user_to_tenant, create_tenant_for_user
from unifiedui.core.database.enums import PermissionActionEnum, PrincipalTypeEnum
from unifiedui.core.database.models import (
    ChatAgent,
    ChatAgentMember,
    Workflow,
    WorkflowMember,
)

# API Endpoints
ENDPOINT_TENANTS = "/api/v1/platform-service/tenants"
ENDPOINT_TAGS = "/api/v1/platform-service/tenants/{tenant_id}/tags"
ENDPOINT_TAG_DETAIL = "/api/v1/platform-service/tenants/{tenant_id}/tags/{tag_id}"
ENDPOINT_CHAT_AGENTS = "/api/v1/platform-service/tenants/{tenant_id}/chat-agents"
ENDPOINT_CHAT_AGENT_DETAIL = "/api/v1/platform-service/tenants/{tenant_id}/chat-agents/{chat_agent_id}"
ENDPOINT_CHAT_AGENT_TAGS = "/api/v1/platform-service/tenants/{tenant_id}/chat-agents/{chat_agent_id}/tags"
ENDPOINT_CHAT_AGENT_PRINCIPALS = "/api/v1/platform-service/tenants/{tenant_id}/chat-agents/{chat_agent_id}/principals"
ENDPOINT_WORKFLOWS = "/api/v1/platform-service/tenants/{tenant_id}/workflows"
ENDPOINT_AUTONOMOUS_AGENT_DETAIL = "/api/v1/platform-service/tenants/{tenant_id}/workflows/{workflow_id}"
ENDPOINT_AUTONOMOUS_AGENT_TAGS = "/api/v1/platform-service/tenants/{tenant_id}/workflows/{workflow_id}/tags"

# Roles
ROLE_READ = PermissionActionEnum.READ.value
ROLE_WRITE = PermissionActionEnum.WRITE.value
ROLE_ADMIN = PermissionActionEnum.ADMIN.value

# Principal Types
PRINCIPAL_TYPE_USER = PrincipalTypeEnum.IDENTITY_USER.value


def create_chat_agent_in_db(test_client: TestClient, tenant_id: str, user_id: str, name: str = "Test App") -> str:
    """Helper function to create a chat agent directly in DB and return its ID."""
    app_id = str(uuid.uuid4())
    with test_client.db_client.get_session() as session:
        app = ChatAgent(
            id=app_id,
            tenant_id=tenant_id,
            name=name,
            description=f"ChatAgent {name}",
            type="N8N",
            config={},
            is_active=True,
            created_by=user_id,
            updated_by=user_id,
        )
        session.add(app)
        session.commit()

        member = ChatAgentMember(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            chat_agent_id=app_id,
            principal_id=user_id,
            role=PermissionActionEnum.ADMIN,
            created_by=user_id,
            updated_by=user_id,
        )
        session.add(member)
        session.commit()
    return app_id


def create_workflow_in_db(test_client: TestClient, tenant_id: str, user_id: str, name: str = "Test Agent") -> str:
    """Helper function to create an autonomous agent directly in DB and return its ID."""
    agent_id = str(uuid.uuid4())
    with test_client.db_client.get_session() as session:
        agent = Workflow(
            id=agent_id,
            tenant_id=tenant_id,
            name=name,
            description=f"Agent {name}",
            type="N8N",
            config={},
            created_by=user_id,
            updated_by=user_id,
        )
        session.add(agent)
        session.commit()

        member = WorkflowMember(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            workflow_id=agent_id,
            principal_id=user_id,
            role=PermissionActionEnum.ADMIN,
            created_by=user_id,
            updated_by=user_id,
        )
        session.add(member)
        session.commit()
    return agent_id


def add_user_to_chat_agent_in_db(
    test_client: TestClient,
    tenant_id: str,
    chat_agent_id: str,
    user_id: str,
    admin_id: str,
    role: PermissionActionEnum = PermissionActionEnum.READ,
) -> None:
    """Helper function to add a user to a chat agent directly in DB."""
    with test_client.db_client.get_session() as session:
        member = ChatAgentMember(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            chat_agent_id=chat_agent_id,
            principal_id=user_id,
            role=role,
            created_by=admin_id,
            updated_by=admin_id,
        )
        session.add(member)
        session.commit()


def create_tag(test_client: TestClient, tenant_id: str, headers: dict, name: str) -> str:
    """Helper function to create a tag and return its ID."""
    response = test_client.post(ENDPOINT_TAGS.format(tenant_id=tenant_id), json={"name": name}, headers=headers)
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
        create_tag(test_client, tenant_id, headers, "TAG1")
        create_tag(test_client, tenant_id, headers, "TAG2")

        # First access - should cache
        response1 = test_client.get(ENDPOINT_TAGS.format(tenant_id=tenant_id), headers=headers)
        assert response1.status_code == status.HTTP_200_OK
        assert len(response1.json()) == 2

        # Second access - should use cache
        response2 = test_client.get(ENDPOINT_TAGS.format(tenant_id=tenant_id), headers=headers)
        assert response2.status_code == status.HTTP_200_OK
        assert len(response2.json()) == 2

    def test_tag_creation_invalidates_list_cache(self, test_client: TestClient, fake_redis_client: Any) -> None:
        """Test that creating a tag invalidates the list cache."""
        user_token = test_client.create_test_user("tag-cache-2", "Tag Cache 2")
        headers = create_auth_headers(user_token)
        tenant_id = create_tenant_for_user(test_client, user_token)

        # Create initial tag and cache the list
        create_tag(test_client, tenant_id, headers, "initial-tag")
        response1 = test_client.get(ENDPOINT_TAGS.format(tenant_id=tenant_id), headers=headers)
        assert len(response1.json()) == 1

        # Create another tag (should invalidate cache)
        create_tag(test_client, tenant_id, headers, "new-tag")

        # List should now show 2 tags
        response2 = test_client.get(ENDPOINT_TAGS.format(tenant_id=tenant_id), headers=headers)
        assert len(response2.json()) == 2

    def test_tag_deletion_invalidates_list_cache(self, test_client: TestClient, fake_redis_client: Any) -> None:
        """Test that deleting a tag invalidates the list cache."""
        user_token = test_client.create_test_user("tag-cache-3", "Tag Cache 3")
        headers = create_auth_headers(user_token)
        tenant_id = create_tenant_for_user(test_client, user_token)

        # Create tags and cache the list
        create_tag(test_client, tenant_id, headers, "tag-to-keep")
        tag2_id = create_tag(test_client, tenant_id, headers, "tag-to-delete")

        response1 = test_client.get(ENDPOINT_TAGS.format(tenant_id=tenant_id), headers=headers)
        assert len(response1.json()) == 2

        # Delete one tag
        test_client.delete(ENDPOINT_TAG_DETAIL.format(tenant_id=tenant_id, tag_id=tag2_id), headers=headers)

        # List should now show 1 tag
        response2 = test_client.get(ENDPOINT_TAGS.format(tenant_id=tenant_id), headers=headers)
        assert len(response2.json()) == 1


class TestResourceTagCacheInvalidation:
    """Test suite for cache invalidation when adding/removing tags from resources."""

    def test_adding_tags_to_chat_agent_invalidates_cache(self, test_client: TestClient, fake_redis_client: Any) -> None:
        """Test that adding tags to a chat agent invalidates the chat agent cache."""
        admin_token = test_client.create_test_user("app-tag-cache-1", "App Tag Cache 1")
        admin_headers = create_auth_headers(admin_token)
        tenant_id = create_tenant_for_user(test_client, admin_token)
        app_id = create_chat_agent_in_db(test_client, tenant_id, "app-tag-cache-1", "Cached App")

        # First read - cache the chat agent (no tags)
        response1 = test_client.get(
            ENDPOINT_CHAT_AGENT_DETAIL.format(tenant_id=tenant_id, chat_agent_id=app_id), headers=admin_headers
        )
        assert response1.status_code == status.HTTP_200_OK
        assert response1.json()["tags"] == []

        # Add tags to chat agent
        test_client.put(
            ENDPOINT_CHAT_AGENT_TAGS.format(tenant_id=tenant_id, chat_agent_id=app_id),
            json={"tags": ["PRODUCTION", "CRITICAL"]},
            headers=admin_headers,
        )

        # Read chat agent again - should see the tags (cache invalidated)
        response2 = test_client.get(
            ENDPOINT_CHAT_AGENT_DETAIL.format(tenant_id=tenant_id, chat_agent_id=app_id), headers=admin_headers
        )
        assert response2.status_code == status.HTTP_200_OK
        assert len(response2.json()["tags"]) == 2

    def test_removing_tags_from_chat_agent_invalidates_cache(
        self, test_client: TestClient, fake_redis_client: Any
    ) -> None:
        """Test that removing tags from a chat agent invalidates the chat agent cache."""
        admin_token = test_client.create_test_user("app-tag-cache-2", "App Tag Cache 2")
        admin_headers = create_auth_headers(admin_token)
        tenant_id = create_tenant_for_user(test_client, admin_token)
        app_id = create_chat_agent_in_db(test_client, tenant_id, "app-tag-cache-2", "Cached App 2")

        # Set initial tags
        test_client.put(
            ENDPOINT_CHAT_AGENT_TAGS.format(tenant_id=tenant_id, chat_agent_id=app_id),
            json={"tags": ["TAG1", "TAG2"]},
            headers=admin_headers,
        )

        # Read and cache
        response1 = test_client.get(
            ENDPOINT_CHAT_AGENT_DETAIL.format(tenant_id=tenant_id, chat_agent_id=app_id), headers=admin_headers
        )
        assert len(response1.json()["tags"]) == 2

        # Remove tags
        test_client.delete(
            ENDPOINT_CHAT_AGENT_TAGS.format(tenant_id=tenant_id, chat_agent_id=app_id), headers=admin_headers
        )

        # Read chat agent again - should see no tags
        response2 = test_client.get(
            ENDPOINT_CHAT_AGENT_DETAIL.format(tenant_id=tenant_id, chat_agent_id=app_id), headers=admin_headers
        )
        assert response2.json()["tags"] == []

    def test_replacing_tags_invalidates_cache(self, test_client: TestClient, fake_redis_client: Any) -> None:
        """Test that replacing tags invalidates the chat agent cache."""
        admin_token = test_client.create_test_user("app-tag-cache-3", "App Tag Cache 3")
        admin_headers = create_auth_headers(admin_token)
        tenant_id = create_tenant_for_user(test_client, admin_token)
        app_id = create_chat_agent_in_db(test_client, tenant_id, "app-tag-cache-3", "Cached App 3")

        # Set initial tags
        test_client.put(
            ENDPOINT_CHAT_AGENT_TAGS.format(tenant_id=tenant_id, chat_agent_id=app_id),
            json={"tags": ["OLD-TAG-1", "OLD-TAG-2"]},
            headers=admin_headers,
        )

        # Read and cache
        response1 = test_client.get(
            ENDPOINT_CHAT_AGENT_DETAIL.format(tenant_id=tenant_id, chat_agent_id=app_id), headers=admin_headers
        )
        tag_names1 = [t["name"] for t in response1.json()["tags"]]
        assert "OLD-TAG-1" in tag_names1
        assert "OLD-TAG-2" in tag_names1

        # Replace with new tags
        test_client.put(
            ENDPOINT_CHAT_AGENT_TAGS.format(tenant_id=tenant_id, chat_agent_id=app_id),
            json={"tags": ["NEW-TAG-1", "NEW-TAG-2", "NEW-TAG-3"]},
            headers=admin_headers,
        )

        # Read chat agent again - should see new tags
        response2 = test_client.get(
            ENDPOINT_CHAT_AGENT_DETAIL.format(tenant_id=tenant_id, chat_agent_id=app_id), headers=admin_headers
        )
        tag_names2 = [t["name"] for t in response2.json()["tags"]]
        assert len(tag_names2) == 3
        assert "NEW-TAG-1" in tag_names2
        assert "NEW-TAG-2" in tag_names2
        assert "NEW-TAG-3" in tag_names2
        assert "OLD-TAG-1" not in tag_names2

    def test_adding_tags_to_workflow_invalidates_cache(self, test_client: TestClient, fake_redis_client: Any) -> None:
        """Test that adding tags to an autonomous agent invalidates the agent cache."""
        admin_token = test_client.create_test_user("agent-tag-cache-1", "Agent Tag Cache 1")
        admin_headers = create_auth_headers(admin_token)
        tenant_id = create_tenant_for_user(test_client, admin_token)
        agent_id = create_workflow_in_db(test_client, tenant_id, "agent-tag-cache-1", "Cached Agent")

        # First read - cache the agent (no tags)
        response1 = test_client.get(
            ENDPOINT_AUTONOMOUS_AGENT_DETAIL.format(tenant_id=tenant_id, workflow_id=agent_id),
            headers=admin_headers,
        )
        assert response1.status_code == status.HTTP_200_OK
        assert response1.json()["tags"] == []

        # Add tags to agent
        test_client.put(
            ENDPOINT_AUTONOMOUS_AGENT_TAGS.format(tenant_id=tenant_id, workflow_id=agent_id),
            json={"tags": ["ai", "ml"]},
            headers=admin_headers,
        )

        # Read agent again - should see the tags
        response2 = test_client.get(
            ENDPOINT_AUTONOMOUS_AGENT_DETAIL.format(tenant_id=tenant_id, workflow_id=agent_id),
            headers=admin_headers,
        )
        assert len(response2.json()["tags"]) == 2

    def test_chat_agents_list_cache_invalidated_on_tag_change(
        self, test_client: TestClient, fake_redis_client: Any
    ) -> None:
        """Test that the chat agents list cache is invalidated when tags change."""
        admin_token = test_client.create_test_user("app-list-tag-cache-1", "App List Tag Cache 1")
        admin_headers = create_auth_headers(admin_token)
        tenant_id = create_tenant_for_user(test_client, admin_token)

        # Create multiple chat agents
        app1_id = create_chat_agent_in_db(test_client, tenant_id, "app-list-tag-cache-1", "App 1")
        app2_id = create_chat_agent_in_db(test_client, tenant_id, "app-list-tag-cache-1", "App 2")

        # Set tags on app1
        test_client.put(
            ENDPOINT_CHAT_AGENT_TAGS.format(tenant_id=tenant_id, chat_agent_id=app1_id),
            json={"tags": ["PRODUCTION"]},
            headers=admin_headers,
        )

        # Get tag ID
        tags_response = test_client.get(
            ENDPOINT_TAGS.format(tenant_id=tenant_id) + "?name=production", headers=admin_headers
        )
        prod_tag_id = tags_response.json()[0]["id"]

        # List chat agents filtered by production tag - cache this
        response1 = test_client.get(
            ENDPOINT_CHAT_AGENTS.format(tenant_id=tenant_id) + f"?tags={prod_tag_id}", headers=admin_headers
        )
        assert len(response1.json()) == 1
        assert response1.json()[0]["name"] == "App 1"

        # Add production tag to app2
        test_client.put(
            ENDPOINT_CHAT_AGENT_TAGS.format(tenant_id=tenant_id, chat_agent_id=app2_id),
            json={"tags": ["PRODUCTION"]},
            headers=admin_headers,
        )

        # List again - should now show 2 apps
        response2 = test_client.get(
            ENDPOINT_CHAT_AGENTS.format(tenant_id=tenant_id) + f"?tags={prod_tag_id}", headers=admin_headers
        )
        assert len(response2.json()) == 2

    def test_user_with_write_permission_tag_changes_visible(
        self, test_client: TestClient, fake_redis_client: Any
    ) -> None:
        """Test that tag changes made by user with WRITE permission are visible immediately."""
        admin_token = test_client.create_test_user("write-tag-cache-1", "Write Tag Cache 1")
        admin_headers = create_auth_headers(admin_token)
        tenant_id = create_tenant_for_user(test_client, admin_token)
        app_id = create_chat_agent_in_db(test_client, tenant_id, "write-tag-cache-1", "Shared App")

        # Create writer user with WRITE permission
        writer_token = test_client.create_test_user("write-tag-writer-1", "Write Tag Writer 1")
        writer_headers = create_auth_headers(writer_token)
        add_user_to_tenant(test_client, tenant_id, admin_headers, "write-tag-writer-1", "READER")
        add_user_to_chat_agent_in_db(
            test_client, tenant_id, app_id, "write-tag-writer-1", "write-tag-cache-1", PermissionActionEnum.WRITE
        )

        # Admin reads chat agent (caches it)
        response1 = test_client.get(
            ENDPOINT_CHAT_AGENT_DETAIL.format(tenant_id=tenant_id, chat_agent_id=app_id), headers=admin_headers
        )
        assert response1.json()["tags"] == []

        # Writer adds tags
        test_client.put(
            ENDPOINT_CHAT_AGENT_TAGS.format(tenant_id=tenant_id, chat_agent_id=app_id),
            json={"tags": ["WRITER-TAG"]},
            headers=writer_headers,
        )

        # Admin reads again - should see the new tags
        response2 = test_client.get(
            ENDPOINT_CHAT_AGENT_DETAIL.format(tenant_id=tenant_id, chat_agent_id=app_id), headers=admin_headers
        )
        assert len(response2.json()["tags"]) == 1
        assert response2.json()["tags"][0]["name"] == "WRITER-TAG"

    def test_deleting_tag_invalidates_resource_caches(self, test_client: TestClient, fake_redis_client: Any) -> None:
        """Test that deleting a tag invalidates caches of resources using that tag."""
        admin_token = test_client.create_test_user("delete-tag-cache-1", "Delete Tag Cache 1")
        admin_headers = create_auth_headers(admin_token)
        tenant_id = create_tenant_for_user(test_client, admin_token)
        app_id = create_chat_agent_in_db(test_client, tenant_id, "delete-tag-cache-1", "Tagged App")

        # Set tags on chat agent
        test_client.put(
            ENDPOINT_CHAT_AGENT_TAGS.format(tenant_id=tenant_id, chat_agent_id=app_id),
            json={"tags": ["to-delete", "TO-KEEP"]},
            headers=admin_headers,
        )

        # Read and cache chat agent
        response1 = test_client.get(
            ENDPOINT_CHAT_AGENT_DETAIL.format(tenant_id=tenant_id, chat_agent_id=app_id), headers=admin_headers
        )
        assert len(response1.json()["tags"]) == 2

        # Get the tag ID for "to-delete"
        tags_response = test_client.get(
            ENDPOINT_TAGS.format(tenant_id=tenant_id) + "?name=to-delete", headers=admin_headers
        )
        tag_id = tags_response.json()[0]["id"]

        # Delete the tag
        test_client.delete(ENDPOINT_TAG_DETAIL.format(tenant_id=tenant_id, tag_id=tag_id), headers=admin_headers)

        # Read chat agent again - should only have one tag
        response2 = test_client.get(
            ENDPOINT_CHAT_AGENT_DETAIL.format(tenant_id=tenant_id, chat_agent_id=app_id), headers=admin_headers
        )
        assert len(response2.json()["tags"]) == 1
        assert response2.json()["tags"][0]["name"] == "TO-KEEP"
