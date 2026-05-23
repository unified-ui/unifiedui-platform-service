"""Tests for tags API endpoints."""

import uuid
from typing import Any

from fastapi import status
from starlette.testclient import TestClient

from tests.conftest import create_auth_headers
from tests.helpers.tenant import create_tenant_for_user
from unifiedui.core.database.enums import PermissionActionEnum
from unifiedui.core.database.models import (
    ChatAgent,
    ChatAgentMember,
    ChatWidget,
    ChatWidgetMember,
    Credential,
    CredentialMember,
    Workflow,
    WorkflowMember,
)

# API Endpoints
ENDPOINT_TAGS = "/api/v1/platform-service/tenants/{tenant_id}/tags"
ENDPOINT_TAG_DETAIL = "/api/v1/platform-service/tenants/{tenant_id}/tags/{tag_id}"
ENDPOINT_CHAT_AGENT_TAGS = "/api/v1/platform-service/tenants/{tenant_id}/chat-agents/{chat_agent_id}/tags"
ENDPOINT_AUTONOMOUS_AGENT_TAGS = "/api/v1/platform-service/tenants/{tenant_id}/workflows/{workflow_id}/tags"
ENDPOINT_CHAT_WIDGET_TAGS = "/api/v1/platform-service/tenants/{tenant_id}/chat-widgets/{chat_widget_id}/tags"
ENDPOINT_CREDENTIAL_TAGS = "/api/v1/platform-service/tenants/{tenant_id}/credentials/{credential_id}/tags"

# Resource endpoints for list with tags filter
ENDPOINT_CHAT_AGENTS = "/api/v1/platform-service/tenants/{tenant_id}/chat-agents"
ENDPOINT_WORKFLOWS = "/api/v1/platform-service/tenants/{tenant_id}/workflows"
ENDPOINT_CHAT_WIDGETS = "/api/v1/platform-service/tenants/{tenant_id}/chat-widgets"
ENDPOINT_CREDENTIALS = "/api/v1/platform-service/tenants/{tenant_id}/credentials"
ENDPOINT_DEVELOPMENT_PLATFORMS = "/api/v1/platform-service/tenants/{tenant_id}/development-platforms"

# Resource-type tag list endpoints
ENDPOINT_CHAT_AGENTS_TAGS_LIST = "/api/v1/platform-service/tenants/{tenant_id}/chat-agents/tags"
ENDPOINT_WORKFLOWS_TAGS_LIST = "/api/v1/platform-service/tenants/{tenant_id}/workflows/tags"
ENDPOINT_CHAT_WIDGETS_TAGS_LIST = "/api/v1/platform-service/tenants/{tenant_id}/chat-widgets/tags"
ENDPOINT_CREDENTIALS_TAGS_LIST = "/api/v1/platform-service/tenants/{tenant_id}/credentials/tags"


def create_chat_agent_in_db(test_client: TestClient, tenant_id: str, user_id: str, name: str = "Test App") -> str:
    """Helper function to create a chat agent directly in DB and return its ID."""
    app_id = str(uuid.uuid4())
    with test_client.db_client.get_session() as session:
        app = ChatAgent(
            id=app_id,
            tenant_id=tenant_id,
            name=name,
            description="Test chat agent",
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
            description="Test autonomous agent",
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


def create_chat_widget_in_db(test_client: TestClient, tenant_id: str, user_id: str, name: str = "Test Widget") -> str:
    """Helper function to create a chat widget directly in DB and return its ID."""
    widget_id = str(uuid.uuid4())
    with test_client.db_client.get_session() as session:
        widget = ChatWidget(
            id=widget_id,
            tenant_id=tenant_id,
            name=name,
            description="Test chat widget",
            type="IFRAME",
            config={},
            created_by=user_id,
            updated_by=user_id,
        )
        session.add(widget)
        session.commit()

        member = ChatWidgetMember(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            chat_widget_id=widget_id,
            principal_id=user_id,
            role=PermissionActionEnum.ADMIN,
            created_by=user_id,
            updated_by=user_id,
        )
        session.add(member)
        session.commit()
    return widget_id


def create_credential_in_db(test_client: TestClient, tenant_id: str, user_id: str, name: str = "Test Cred") -> str:
    """Helper function to create a credential directly in DB and return its ID."""
    cred_id = str(uuid.uuid4())
    with test_client.db_client.get_session() as session:
        cred = Credential(
            id=cred_id,
            tenant_id=tenant_id,
            name=name,
            description="Test credential",
            type="API_KEY",
            source="test",
            credential_uri="vault://test",
            is_active=True,
            created_by=user_id,
            updated_by=user_id,
        )
        session.add(cred)
        session.commit()

        member = CredentialMember(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            credential_id=cred_id,
            principal_id=user_id,
            role=PermissionActionEnum.ADMIN,
            created_by=user_id,
            updated_by=user_id,
        )
        session.add(member)
        session.commit()
    return cred_id


class TestTagRoutes:
    """Test suite for tag API routes."""

    def test_create_tag_success(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test successful tag creation."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        response = test_client.post(
            ENDPOINT_TAGS.format(tenant_id=tenant_id), json={"name": "PRODUCTION"}, headers=headers
        )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()

        assert data["name"] == "PRODUCTION"
        assert "id" in data
        assert data["tenant_id"] == tenant_id
        assert "created_at" in data
        assert "updated_at" in data

    def test_create_tag_missing_name(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test tag creation with missing name."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        response = test_client.post(ENDPOINT_TAGS.format(tenant_id=tenant_id), json={}, headers=headers)

        assert response.status_code == 422

    def test_list_tags_empty(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test listing tags when none exist."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        response = test_client.get(ENDPOINT_TAGS.format(tenant_id=tenant_id), headers=headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data == []

    def test_list_tags_with_data(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test listing tags with existing data."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        # Create some tags
        test_client.post(ENDPOINT_TAGS.format(tenant_id=tenant_id), json={"name": "PRODUCTION"}, headers=headers)
        test_client.post(ENDPOINT_TAGS.format(tenant_id=tenant_id), json={"name": "STAGING"}, headers=headers)
        test_client.post(ENDPOINT_TAGS.format(tenant_id=tenant_id), json={"name": "DEVELOPMENT"}, headers=headers)

        response = test_client.get(ENDPOINT_TAGS.format(tenant_id=tenant_id), headers=headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 3

        tag_names = [t["name"] for t in data]
        assert "PRODUCTION" in tag_names
        assert "STAGING" in tag_names
        assert "DEVELOPMENT" in tag_names

    def test_list_tags_with_name_filter(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test listing tags with name filter."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        # Create some tags
        test_client.post(ENDPOINT_TAGS.format(tenant_id=tenant_id), json={"name": "PRODUCTION"}, headers=headers)
        test_client.post(ENDPOINT_TAGS.format(tenant_id=tenant_id), json={"name": "STAGING"}, headers=headers)

        response = test_client.get(ENDPOINT_TAGS.format(tenant_id=tenant_id) + "?name=prod", headers=headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data[0]["name"] == "PRODUCTION"

    def test_delete_tag_success(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test successful tag deletion."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        # Create a tag
        create_response = test_client.post(
            ENDPOINT_TAGS.format(tenant_id=tenant_id), json={"name": "to-delete"}, headers=headers
        )
        tag_id = create_response.json()["id"]

        # Delete the tag
        response = test_client.delete(ENDPOINT_TAG_DETAIL.format(tenant_id=tenant_id, tag_id=tag_id), headers=headers)

        assert response.status_code == status.HTTP_204_NO_CONTENT

        # Verify tag is deleted
        list_response = test_client.get(ENDPOINT_TAGS.format(tenant_id=tenant_id), headers=headers)
        assert len(list_response.json()) == 0

    def test_delete_tag_not_found(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test deleting a non-existent tag."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        response = test_client.delete(ENDPOINT_TAG_DETAIL.format(tenant_id=tenant_id, tag_id=99999), headers=headers)

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_delete_tag_by_creator_success(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test that the tag creator can delete their own tag."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        # Create a tag
        create_response = test_client.post(
            ENDPOINT_TAGS.format(tenant_id=tenant_id), json={"name": "creator-tag"}, headers=headers
        )
        tag_id = create_response.json()["id"]

        # Creator can delete
        response = test_client.delete(ENDPOINT_TAG_DETAIL.format(tenant_id=tenant_id, tag_id=tag_id), headers=headers)

        assert response.status_code == status.HTTP_204_NO_CONTENT


class TestChatAgentTagRoutes:
    """Test suite for chat agent tag management."""

    def test_get_chat_agent_tags_empty(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test getting tags for a chat agent with no tags."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        app_id = create_chat_agent_in_db(test_client, tenant_id, test_user_token.get_id())
        headers = create_auth_headers(test_user_token, use_cache=False)

        response = test_client.get(
            ENDPOINT_CHAT_AGENT_TAGS.format(tenant_id=tenant_id, chat_agent_id=app_id), headers=headers
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data == []

    def test_set_chat_agent_tags(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test setting tags on a chat agent."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        app_id = create_chat_agent_in_db(test_client, tenant_id, test_user_token.get_id())
        headers = create_auth_headers(test_user_token, use_cache=False)

        # Set tags (should create new tags automatically)
        response = test_client.put(
            ENDPOINT_CHAT_AGENT_TAGS.format(tenant_id=tenant_id, chat_agent_id=app_id),
            json={"tags": ["PRODUCTION", "CRITICAL", "BACKEND"]},
            headers=headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 3

        tag_names = [t["name"] for t in data]
        assert "PRODUCTION" in tag_names
        assert "CRITICAL" in tag_names
        assert "BACKEND" in tag_names

    def test_set_chat_agent_tags_creates_new_tags(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test that setting tags creates new tags if they don't exist."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        app_id = create_chat_agent_in_db(test_client, tenant_id, test_user_token.get_id())
        headers = create_auth_headers(test_user_token, use_cache=False)

        # Set tags with new tag names
        test_client.put(
            ENDPOINT_CHAT_AGENT_TAGS.format(tenant_id=tenant_id, chat_agent_id=app_id),
            json={"tags": ["NEW-TAG-1", "NEW-TAG-2"]},
            headers=headers,
        )

        # Verify tags were created in the tenant
        list_response = test_client.get(ENDPOINT_TAGS.format(tenant_id=tenant_id), headers=headers)

        data = list_response.json()
        tag_names = [t["name"] for t in data]
        assert "NEW-TAG-1" in tag_names
        assert "NEW-TAG-2" in tag_names

    def test_set_chat_agent_tags_replaces_existing(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test that setting tags replaces existing tags."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        app_id = create_chat_agent_in_db(test_client, tenant_id, test_user_token.get_id())
        headers = create_auth_headers(test_user_token, use_cache=False)

        # Set initial tags
        test_client.put(
            ENDPOINT_CHAT_AGENT_TAGS.format(tenant_id=tenant_id, chat_agent_id=app_id),
            json={"tags": ["TAG1", "TAG2"]},
            headers=headers,
        )

        # Replace with new tags
        response = test_client.put(
            ENDPOINT_CHAT_AGENT_TAGS.format(tenant_id=tenant_id, chat_agent_id=app_id),
            json={"tags": ["TAG3", "TAG4"]},
            headers=headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 2

        tag_names = [t["name"] for t in data]
        assert "TAG3" in tag_names
        assert "TAG4" in tag_names
        assert "TAG1" not in tag_names
        assert "TAG2" not in tag_names

    def test_delete_chat_agent_tags(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test deleting all tags from a chat agent."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        app_id = create_chat_agent_in_db(test_client, tenant_id, test_user_token.get_id())
        headers = create_auth_headers(test_user_token, use_cache=False)

        # Set tags
        test_client.put(
            ENDPOINT_CHAT_AGENT_TAGS.format(tenant_id=tenant_id, chat_agent_id=app_id),
            json={"tags": ["TAG1", "TAG2"]},
            headers=headers,
        )

        # Delete all tags
        response = test_client.delete(
            ENDPOINT_CHAT_AGENT_TAGS.format(tenant_id=tenant_id, chat_agent_id=app_id), headers=headers
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT

        # Verify tags are removed
        get_response = test_client.get(
            ENDPOINT_CHAT_AGENT_TAGS.format(tenant_id=tenant_id, chat_agent_id=app_id), headers=headers
        )
        assert get_response.json() == []

    def test_tags_included_in_chat_agent_response(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test that tags are included in chat agent responses."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        app_id = create_chat_agent_in_db(test_client, tenant_id, test_user_token.get_id())
        headers = create_auth_headers(test_user_token, use_cache=False)

        # Set tags
        test_client.put(
            ENDPOINT_CHAT_AGENT_TAGS.format(tenant_id=tenant_id, chat_agent_id=app_id),
            json={"tags": ["PRODUCTION", "BACKEND"]},
            headers=headers,
        )

        # Get the chat agent
        response = test_client.get(ENDPOINT_CHAT_AGENTS.format(tenant_id=tenant_id) + f"/{app_id}", headers=headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "tags" in data
        assert len(data["tags"]) == 2

        tag_names = [t["name"] for t in data["tags"]]
        assert "PRODUCTION" in tag_names
        assert "BACKEND" in tag_names


class TestChatAgentListFilterByTags:
    """Test suite for filtering chat agents by tags."""

    def test_list_chat_agents_filter_by_single_tag(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test filtering chat agents by a single tag."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        # Create chat agents
        app1_id = create_chat_agent_in_db(test_client, tenant_id, test_user_token.get_id(), "App 1")
        app2_id = create_chat_agent_in_db(test_client, tenant_id, test_user_token.get_id(), "App 2")
        app3_id = create_chat_agent_in_db(test_client, tenant_id, test_user_token.get_id(), "App 3")

        # Set tags
        test_client.put(
            ENDPOINT_CHAT_AGENT_TAGS.format(tenant_id=tenant_id, chat_agent_id=app1_id),
            json={"tags": ["PRODUCTION"]},
            headers=headers,
        )
        test_client.put(
            ENDPOINT_CHAT_AGENT_TAGS.format(tenant_id=tenant_id, chat_agent_id=app2_id),
            json={"tags": ["PRODUCTION", "CRITICAL"]},
            headers=headers,
        )
        test_client.put(
            ENDPOINT_CHAT_AGENT_TAGS.format(tenant_id=tenant_id, chat_agent_id=app3_id),
            json={"tags": ["STAGING"]},
            headers=headers,
        )

        # Get the production tag ID
        tags_response = test_client.get(ENDPOINT_TAGS.format(tenant_id=tenant_id) + "?name=production", headers=headers)
        prod_tag_id = tags_response.json()[0]["id"]

        # Filter by production tag
        response = test_client.get(
            ENDPOINT_CHAT_AGENTS.format(tenant_id=tenant_id) + f"?tags={prod_tag_id}", headers=headers
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 2

        app_names = [a["name"] for a in data]
        assert "App 1" in app_names
        assert "App 2" in app_names
        assert "App 3" not in app_names

    def test_list_chat_agents_filter_by_multiple_tags(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test filtering chat agents by multiple tags (OR logic)."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        # Create chat agents
        app1_id = create_chat_agent_in_db(test_client, tenant_id, test_user_token.get_id(), "App 1")
        app2_id = create_chat_agent_in_db(test_client, tenant_id, test_user_token.get_id(), "App 2")
        app3_id = create_chat_agent_in_db(test_client, tenant_id, test_user_token.get_id(), "App 3")
        app4_id = create_chat_agent_in_db(test_client, tenant_id, test_user_token.get_id(), "App 4")

        # Set tags
        # App 1: only "PRODUCTION"
        test_client.put(
            ENDPOINT_CHAT_AGENT_TAGS.format(tenant_id=tenant_id, chat_agent_id=app1_id),
            json={"tags": ["PRODUCTION"]},
            headers=headers,
        )
        # App 2: both "PRODUCTION" and "CRITICAL"
        test_client.put(
            ENDPOINT_CHAT_AGENT_TAGS.format(tenant_id=tenant_id, chat_agent_id=app2_id),
            json={"tags": ["PRODUCTION", "CRITICAL"]},
            headers=headers,
        )
        # App 3: only "CRITICAL"
        test_client.put(
            ENDPOINT_CHAT_AGENT_TAGS.format(tenant_id=tenant_id, chat_agent_id=app3_id),
            json={"tags": ["CRITICAL"]},
            headers=headers,
        )
        # App 4: only "STAGING" (should NOT be returned)
        test_client.put(
            ENDPOINT_CHAT_AGENT_TAGS.format(tenant_id=tenant_id, chat_agent_id=app4_id),
            json={"tags": ["STAGING"]},
            headers=headers,
        )

        # Get tag IDs
        tags_response = test_client.get(ENDPOINT_TAGS.format(tenant_id=tenant_id), headers=headers)
        tags_data = tags_response.json()
        prod_tag_id = next(t["id"] for t in tags_data if t["name"] == "PRODUCTION")
        critical_tag_id = next(t["id"] for t in tags_data if t["name"] == "CRITICAL")

        # Filter by production OR critical tags (should return App 1, App 2, App 3)
        response = test_client.get(
            ENDPOINT_CHAT_AGENTS.format(tenant_id=tenant_id) + f"?tags={prod_tag_id},{critical_tag_id}", headers=headers
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 3, f"Expected 3 chat agents with production OR critical tags, got {len(data)}"

        # Verify all three apps are returned
        app_names = {app["name"] for app in data}
        assert app_names == {"App 1", "App 2", "App 3"}, f"Expected App 1, App 2, App 3, got {app_names}"

        # Verify App 4 (with only staging tag) is NOT returned
        assert "App 4" not in app_names

    def test_list_chat_agents_invalid_tags_format(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test filtering chat agents with invalid tags format."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        # Create a chat agent
        create_chat_agent_in_db(test_client, tenant_id, test_user_token.get_id())

        # Try to filter with invalid tag format
        response = test_client.get(
            ENDPOINT_CHAT_AGENTS.format(tenant_id=tenant_id) + "?tags=invalid,abc", headers=headers
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Invalid tag IDs format" in response.json()["detail"]


class TestWorkflowTagRoutes:
    """Test suite for autonomous agent tag management."""

    def test_set_and_get_workflow_tags(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test setting and getting tags on an autonomous agent."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        agent_id = create_workflow_in_db(test_client, tenant_id, test_user_token.get_id())
        headers = create_auth_headers(test_user_token, use_cache=False)

        # Set tags
        response = test_client.put(
            ENDPOINT_AUTONOMOUS_AGENT_TAGS.format(tenant_id=tenant_id, workflow_id=agent_id),
            json={"tags": ["ai", "PRODUCTION"]},
            headers=headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 2

        # Get tags
        get_response = test_client.get(
            ENDPOINT_AUTONOMOUS_AGENT_TAGS.format(tenant_id=tenant_id, workflow_id=agent_id), headers=headers
        )

        assert get_response.status_code == status.HTTP_200_OK
        assert len(get_response.json()) == 2


class TestChatWidgetTagRoutes:
    """Test suite for chat widget tag management."""

    def test_set_and_get_chat_widget_tags(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test setting and getting tags on a chat widget."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        widget_id = create_chat_widget_in_db(test_client, tenant_id, test_user_token.get_id())
        headers = create_auth_headers(test_user_token, use_cache=False)

        # Set tags
        response = test_client.put(
            ENDPOINT_CHAT_WIDGET_TAGS.format(tenant_id=tenant_id, chat_widget_id=widget_id),
            json={"tags": ["customer-support", "live"]},
            headers=headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 2

        # Get tags
        get_response = test_client.get(
            ENDPOINT_CHAT_WIDGET_TAGS.format(tenant_id=tenant_id, chat_widget_id=widget_id), headers=headers
        )

        assert get_response.status_code == status.HTTP_200_OK
        assert len(get_response.json()) == 2


class TestCredentialTagRoutes:
    """Test suite for credential tag management."""

    def test_set_and_get_credential_tags(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test setting and getting tags on a credential."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        cred_id = create_credential_in_db(test_client, tenant_id, test_user_token.get_id())
        headers = create_auth_headers(test_user_token, use_cache=False)

        # Set tags
        response = test_client.put(
            ENDPOINT_CREDENTIAL_TAGS.format(tenant_id=tenant_id, credential_id=cred_id),
            json={"tags": ["api-keys", "PRODUCTION"]},
            headers=headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 2

        # Get tags
        get_response = test_client.get(
            ENDPOINT_CREDENTIAL_TAGS.format(tenant_id=tenant_id, credential_id=cred_id), headers=headers
        )

        assert get_response.status_code == status.HTTP_200_OK
        assert len(get_response.json()) == 2


class TestTagCascadeDelete:
    """Test suite for tag cascade delete behavior."""

    def test_delete_tag_removes_from_resources(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test that deleting a tag removes it from all associated resources."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        app_id = create_chat_agent_in_db(test_client, tenant_id, test_user_token.get_id())
        headers = create_auth_headers(test_user_token, use_cache=False)

        # Set tags on chat agent
        test_client.put(
            ENDPOINT_CHAT_AGENT_TAGS.format(tenant_id=tenant_id, chat_agent_id=app_id),
            json={"tags": ["to-delete", "KEEP-ME"]},
            headers=headers,
        )

        # Get the tag ID for "to-delete"
        tags_response = test_client.get(ENDPOINT_TAGS.format(tenant_id=tenant_id) + "?name=to-delete", headers=headers)
        tag_id = tags_response.json()[0]["id"]

        # Delete the tag
        test_client.delete(ENDPOINT_TAG_DETAIL.format(tenant_id=tenant_id, tag_id=tag_id), headers=headers)

        # Verify the chat agent only has one tag now
        app_tags_response = test_client.get(
            ENDPOINT_CHAT_AGENT_TAGS.format(tenant_id=tenant_id, chat_agent_id=app_id), headers=headers
        )

        tags = app_tags_response.json()
        assert len(tags) == 1
        assert tags[0]["name"] == "KEEP-ME"


class TestResourceTypeTagListEndpoints:
    """Test suite for resource-type tag list endpoints."""

    def test_list_chat_agent_tags(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test listing tags filtered by chat agents resource type."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        app_id = create_chat_agent_in_db(test_client, tenant_id, test_user_token.get_id())
        headers = create_auth_headers(test_user_token, use_cache=False)

        test_client.put(
            ENDPOINT_CHAT_AGENT_TAGS.format(tenant_id=tenant_id, chat_agent_id=app_id),
            json={"tags": ["CHAT-AGENT-TAG"]},
            headers=headers,
        )

        response = test_client.get(ENDPOINT_CHAT_AGENTS_TAGS_LIST.format(tenant_id=tenant_id), headers=headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) >= 1

    def test_list_workflow_tags(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test listing tags filtered by autonomous agents resource type."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        agent_id = create_workflow_in_db(test_client, tenant_id, test_user_token.get_id())
        headers = create_auth_headers(test_user_token, use_cache=False)

        test_client.put(
            ENDPOINT_AUTONOMOUS_AGENT_TAGS.format(tenant_id=tenant_id, workflow_id=agent_id),
            json={"tags": ["AUTO-AGENT-TAG"]},
            headers=headers,
        )

        response = test_client.get(ENDPOINT_WORKFLOWS_TAGS_LIST.format(tenant_id=tenant_id), headers=headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) >= 1

    def test_list_chat_widget_tags(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test listing tags filtered by chat widgets resource type."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        widget_id = create_chat_widget_in_db(test_client, tenant_id, test_user_token.get_id())
        headers = create_auth_headers(test_user_token, use_cache=False)

        test_client.put(
            ENDPOINT_CHAT_WIDGET_TAGS.format(tenant_id=tenant_id, chat_widget_id=widget_id),
            json={"tags": ["WIDGET-TAG"]},
            headers=headers,
        )

        response = test_client.get(ENDPOINT_CHAT_WIDGETS_TAGS_LIST.format(tenant_id=tenant_id), headers=headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) >= 1

    def test_list_credential_tags(self, test_client: TestClient, test_user_token: Any) -> None:
        """Test listing tags filtered by credentials resource type."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        cred_id = create_credential_in_db(test_client, tenant_id, test_user_token.get_id())
        headers = create_auth_headers(test_user_token, use_cache=False)

        test_client.put(
            ENDPOINT_CREDENTIAL_TAGS.format(tenant_id=tenant_id, credential_id=cred_id),
            json={"tags": ["CRED-TAG"]},
            headers=headers,
        )

        response = test_client.get(ENDPOINT_CREDENTIALS_TAGS_LIST.format(tenant_id=tenant_id), headers=headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) >= 1
