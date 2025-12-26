"""Tests for tags API endpoints."""
import uuid
from typing import Any
from fastapi import status
from starlette.testclient import TestClient

from unifiedui.core.database.enums import PermissionActionEnum, PrincipalTypeEnum
from unifiedui.core.database.models import (
    Application, ApplicationMember,
    AutonomousAgent, AutonomousAgentMember,
    ChatWidget, ChatWidgetMember,
    Credential, CredentialMember,
    DevelopmentPlatform, DevelopmentPlatformMember,
)
from tests.conftest import create_auth_headers


# API Endpoints
ENDPOINT_TAGS = "/api/v1/tenants/{tenant_id}/tags"
ENDPOINT_TAG_DETAIL = "/api/v1/tenants/{tenant_id}/tags/{tag_id}"
ENDPOINT_APPLICATION_TAGS = "/api/v1/tenants/{tenant_id}/applications/{application_id}/tags"
ENDPOINT_AUTONOMOUS_AGENT_TAGS = "/api/v1/tenants/{tenant_id}/autonomous-agents/{autonomous_agent_id}/tags"
ENDPOINT_CHAT_WIDGET_TAGS = "/api/v1/tenants/{tenant_id}/chat-widgets/{chat_widget_id}/tags"
ENDPOINT_CREDENTIAL_TAGS = "/api/v1/tenants/{tenant_id}/credentials/{credential_id}/tags"
ENDPOINT_DEVELOPMENT_PLATFORM_TAGS = "/api/v1/tenants/{tenant_id}/development-platforms/{development_platform_id}/tags"

# Resource endpoints for list with tags filter
ENDPOINT_APPLICATIONS = "/api/v1/tenants/{tenant_id}/applications"
ENDPOINT_AUTONOMOUS_AGENTS = "/api/v1/tenants/{tenant_id}/autonomous-agents"
ENDPOINT_CHAT_WIDGETS = "/api/v1/tenants/{tenant_id}/chat-widgets"
ENDPOINT_CREDENTIALS = "/api/v1/tenants/{tenant_id}/credentials"
ENDPOINT_DEVELOPMENT_PLATFORMS = "/api/v1/tenants/{tenant_id}/development-platforms"


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


def create_autonomous_agent_in_db(test_client: TestClient, tenant_id: str, user_id: str, name: str = "Test Agent") -> str:
    """Helper function to create an autonomous agent directly in DB and return its ID."""
    agent_id = str(uuid.uuid4())
    with test_client.db_client.get_session() as session:
        agent = AutonomousAgent(
            id=agent_id,
            tenant_id=tenant_id,
            name=name,
            description="Test autonomous agent",
            config={},
            is_active=True,
            created_by=user_id,
            updated_by=user_id
        )
        session.add(agent)
        session.commit()

        member = AutonomousAgentMember(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            autonomous_agent_id=agent_id,
            principal_id=user_id,
            principal_type=PrincipalTypeEnum.IDENTITY_USER,
            role=PermissionActionEnum.ADMIN,
            created_by=user_id,
            updated_by=user_id
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
            is_active=True,
            created_by=user_id,
            updated_by=user_id
        )
        session.add(widget)
        session.commit()

        member = ChatWidgetMember(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            chat_widget_id=widget_id,
            principal_id=user_id,
            principal_type=PrincipalTypeEnum.IDENTITY_USER,
            role=PermissionActionEnum.ADMIN,
            created_by=user_id,
            updated_by=user_id
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
            updated_by=user_id
        )
        session.add(cred)
        session.commit()

        member = CredentialMember(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            credential_id=cred_id,
            principal_id=user_id,
            principal_type=PrincipalTypeEnum.IDENTITY_USER,
            role=PermissionActionEnum.ADMIN,
            created_by=user_id,
            updated_by=user_id
        )
        session.add(member)
        session.commit()
    return cred_id


def create_development_platform_in_db(test_client: TestClient, tenant_id: str, user_id: str, name: str = "Test Platform") -> str:
    """Helper function to create a development platform directly in DB and return its ID."""
    platform_id = str(uuid.uuid4())
    with test_client.db_client.get_session() as session:
        platform = DevelopmentPlatform(
            id=platform_id,
            tenant_id=tenant_id,
            name=name,
            description="Test development platform",
            type="IDE",
            iframe_url="https://example.com/ide",
            config={},
            is_active=True,
            created_by=user_id,
            updated_by=user_id
        )
        session.add(platform)
        session.commit()

        member = DevelopmentPlatformMember(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            development_platform_id=platform_id,
            principal_id=user_id,
            principal_type=PrincipalTypeEnum.IDENTITY_USER,
            role=PermissionActionEnum.ADMIN,
            created_by=user_id,
            updated_by=user_id
        )
        session.add(member)
        session.commit()
    return platform_id


class TestTagRoutes:
    """Test suite for tag API routes."""
    
    def test_create_tag_success(
        self, 
        test_client: TestClient, 
        test_user_token: Any
    ) -> None:
        """Test successful tag creation."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        response = test_client.post(
            ENDPOINT_TAGS.format(tenant_id=tenant_id),
            json={"name": "production"},
            headers=headers
        )
        
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        
        assert data["name"] == "production"
        assert "id" in data
        assert data["tenant_id"] == tenant_id
        assert "created_at" in data
        assert "updated_at" in data
    
    def test_create_tag_missing_name(
        self, 
        test_client: TestClient, 
        test_user_token: Any
    ) -> None:
        """Test tag creation with missing name."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        response = test_client.post(
            ENDPOINT_TAGS.format(tenant_id=tenant_id),
            json={},
            headers=headers
        )
        
        assert response.status_code == 422
    
    def test_list_tags_empty(
        self, 
        test_client: TestClient, 
        test_user_token: Any
    ) -> None:
        """Test listing tags when none exist."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        response = test_client.get(
            ENDPOINT_TAGS.format(tenant_id=tenant_id),
            headers=headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["tags"] == []
        assert data["total"] == 0
    
    def test_list_tags_with_data(
        self, 
        test_client: TestClient, 
        test_user_token: Any
    ) -> None:
        """Test listing tags with existing data."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        # Create some tags
        test_client.post(
            ENDPOINT_TAGS.format(tenant_id=tenant_id),
            json={"name": "production"},
            headers=headers
        )
        test_client.post(
            ENDPOINT_TAGS.format(tenant_id=tenant_id),
            json={"name": "staging"},
            headers=headers
        )
        test_client.post(
            ENDPOINT_TAGS.format(tenant_id=tenant_id),
            json={"name": "development"},
            headers=headers
        )
        
        response = test_client.get(
            ENDPOINT_TAGS.format(tenant_id=tenant_id),
            headers=headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total"] == 3
        assert len(data["tags"]) == 3
        
        tag_names = [t["name"] for t in data["tags"]]
        assert "production" in tag_names
        assert "staging" in tag_names
        assert "development" in tag_names
    
    def test_list_tags_with_name_filter(
        self, 
        test_client: TestClient, 
        test_user_token: Any
    ) -> None:
        """Test listing tags with name filter."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        # Create some tags
        test_client.post(
            ENDPOINT_TAGS.format(tenant_id=tenant_id),
            json={"name": "production"},
            headers=headers
        )
        test_client.post(
            ENDPOINT_TAGS.format(tenant_id=tenant_id),
            json={"name": "staging"},
            headers=headers
        )
        
        response = test_client.get(
            ENDPOINT_TAGS.format(tenant_id=tenant_id) + "?name=prod",
            headers=headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total"] == 1
        assert data["tags"][0]["name"] == "production"
    
    def test_delete_tag_success(
        self, 
        test_client: TestClient, 
        test_user_token: Any
    ) -> None:
        """Test successful tag deletion."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        # Create a tag
        create_response = test_client.post(
            ENDPOINT_TAGS.format(tenant_id=tenant_id),
            json={"name": "to-delete"},
            headers=headers
        )
        tag_id = create_response.json()["id"]
        
        # Delete the tag
        response = test_client.delete(
            ENDPOINT_TAG_DETAIL.format(tenant_id=tenant_id, tag_id=tag_id),
            headers=headers
        )
        
        assert response.status_code == status.HTTP_204_NO_CONTENT
        
        # Verify tag is deleted
        list_response = test_client.get(
            ENDPOINT_TAGS.format(tenant_id=tenant_id),
            headers=headers
        )
        assert list_response.json()["total"] == 0
    
    def test_delete_tag_not_found(
        self, 
        test_client: TestClient, 
        test_user_token: Any
    ) -> None:
        """Test deleting a non-existent tag."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        response = test_client.delete(
            ENDPOINT_TAG_DETAIL.format(tenant_id=tenant_id, tag_id=99999),
            headers=headers
        )
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
    
    def test_delete_tag_by_creator_success(
        self, 
        test_client: TestClient, 
        test_user_token: Any
    ) -> None:
        """Test that the tag creator can delete their own tag."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        # Create a tag
        create_response = test_client.post(
            ENDPOINT_TAGS.format(tenant_id=tenant_id),
            json={"name": "creator-tag"},
            headers=headers
        )
        tag_id = create_response.json()["id"]
        
        # Creator can delete
        response = test_client.delete(
            ENDPOINT_TAG_DETAIL.format(tenant_id=tenant_id, tag_id=tag_id),
            headers=headers
        )
        
        assert response.status_code == status.HTTP_204_NO_CONTENT


class TestApplicationTagRoutes:
    """Test suite for application tag management."""
    
    def test_get_application_tags_empty(
        self, 
        test_client: TestClient, 
        test_user_token: Any
    ) -> None:
        """Test getting tags for an application with no tags."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        app_id = create_application_in_db(test_client, tenant_id, test_user_token.get_id())
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        response = test_client.get(
            ENDPOINT_APPLICATION_TAGS.format(tenant_id=tenant_id, application_id=app_id),
            headers=headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["tags"] == []
    
    def test_set_application_tags(
        self, 
        test_client: TestClient, 
        test_user_token: Any
    ) -> None:
        """Test setting tags on an application."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        app_id = create_application_in_db(test_client, tenant_id, test_user_token.get_id())
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        # Set tags (should create new tags automatically)
        response = test_client.put(
            ENDPOINT_APPLICATION_TAGS.format(tenant_id=tenant_id, application_id=app_id),
            json={"tags": ["production", "critical", "backend"]},
            headers=headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["tags"]) == 3
        
        tag_names = [t["name"] for t in data["tags"]]
        assert "production" in tag_names
        assert "critical" in tag_names
        assert "backend" in tag_names
    
    def test_set_application_tags_creates_new_tags(
        self, 
        test_client: TestClient, 
        test_user_token: Any
    ) -> None:
        """Test that setting tags creates new tags if they don't exist."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        app_id = create_application_in_db(test_client, tenant_id, test_user_token.get_id())
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        # Set tags with new tag names
        test_client.put(
            ENDPOINT_APPLICATION_TAGS.format(tenant_id=tenant_id, application_id=app_id),
            json={"tags": ["new-tag-1", "new-tag-2"]},
            headers=headers
        )
        
        # Verify tags were created in the tenant
        list_response = test_client.get(
            ENDPOINT_TAGS.format(tenant_id=tenant_id),
            headers=headers
        )
        
        data = list_response.json()
        assert data["total"] == 2
        
        tag_names = [t["name"] for t in data["tags"]]
        assert "new-tag-1" in tag_names
        assert "new-tag-2" in tag_names
    
    def test_set_application_tags_replaces_existing(
        self, 
        test_client: TestClient, 
        test_user_token: Any
    ) -> None:
        """Test that setting tags replaces existing tags."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        app_id = create_application_in_db(test_client, tenant_id, test_user_token.get_id())
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        # Set initial tags
        test_client.put(
            ENDPOINT_APPLICATION_TAGS.format(tenant_id=tenant_id, application_id=app_id),
            json={"tags": ["tag1", "tag2"]},
            headers=headers
        )
        
        # Replace with new tags
        response = test_client.put(
            ENDPOINT_APPLICATION_TAGS.format(tenant_id=tenant_id, application_id=app_id),
            json={"tags": ["tag3", "tag4"]},
            headers=headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["tags"]) == 2
        
        tag_names = [t["name"] for t in data["tags"]]
        assert "tag3" in tag_names
        assert "tag4" in tag_names
        assert "tag1" not in tag_names
        assert "tag2" not in tag_names
    
    def test_delete_application_tags(
        self, 
        test_client: TestClient, 
        test_user_token: Any
    ) -> None:
        """Test deleting all tags from an application."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        app_id = create_application_in_db(test_client, tenant_id, test_user_token.get_id())
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        # Set tags
        test_client.put(
            ENDPOINT_APPLICATION_TAGS.format(tenant_id=tenant_id, application_id=app_id),
            json={"tags": ["tag1", "tag2"]},
            headers=headers
        )
        
        # Delete all tags
        response = test_client.delete(
            ENDPOINT_APPLICATION_TAGS.format(tenant_id=tenant_id, application_id=app_id),
            headers=headers
        )
        
        assert response.status_code == status.HTTP_204_NO_CONTENT
        
        # Verify tags are removed
        get_response = test_client.get(
            ENDPOINT_APPLICATION_TAGS.format(tenant_id=tenant_id, application_id=app_id),
            headers=headers
        )
        assert get_response.json()["tags"] == []
    
    def test_tags_included_in_application_response(
        self, 
        test_client: TestClient, 
        test_user_token: Any
    ) -> None:
        """Test that tags are included in application responses."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        app_id = create_application_in_db(test_client, tenant_id, test_user_token.get_id())
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        # Set tags
        test_client.put(
            ENDPOINT_APPLICATION_TAGS.format(tenant_id=tenant_id, application_id=app_id),
            json={"tags": ["production", "backend"]},
            headers=headers
        )
        
        # Get the application
        response = test_client.get(
            ENDPOINT_APPLICATIONS.format(tenant_id=tenant_id) + f"/{app_id}",
            headers=headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "tags" in data
        assert len(data["tags"]) == 2
        
        tag_names = [t["name"] for t in data["tags"]]
        assert "production" in tag_names
        assert "backend" in tag_names


class TestApplicationListFilterByTags:
    """Test suite for filtering applications by tags."""
    
    def test_list_applications_filter_by_single_tag(
        self, 
        test_client: TestClient, 
        test_user_token: Any
    ) -> None:
        """Test filtering applications by a single tag."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        # Create applications
        app1_id = create_application_in_db(test_client, tenant_id, test_user_token.get_id(), "App 1")
        app2_id = create_application_in_db(test_client, tenant_id, test_user_token.get_id(), "App 2")
        app3_id = create_application_in_db(test_client, tenant_id, test_user_token.get_id(), "App 3")
        
        # Set tags
        test_client.put(
            ENDPOINT_APPLICATION_TAGS.format(tenant_id=tenant_id, application_id=app1_id),
            json={"tags": ["production"]},
            headers=headers
        )
        test_client.put(
            ENDPOINT_APPLICATION_TAGS.format(tenant_id=tenant_id, application_id=app2_id),
            json={"tags": ["production", "critical"]},
            headers=headers
        )
        test_client.put(
            ENDPOINT_APPLICATION_TAGS.format(tenant_id=tenant_id, application_id=app3_id),
            json={"tags": ["staging"]},
            headers=headers
        )
        
        # Get the production tag ID
        tags_response = test_client.get(
            ENDPOINT_TAGS.format(tenant_id=tenant_id) + "?name=production",
            headers=headers
        )
        prod_tag_id = tags_response.json()["tags"][0]["id"]
        
        # Filter by production tag
        response = test_client.get(
            ENDPOINT_APPLICATIONS.format(tenant_id=tenant_id) + f"?tags={prod_tag_id}",
            headers=headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 2
        
        app_names = [a["name"] for a in data]
        assert "App 1" in app_names
        assert "App 2" in app_names
        assert "App 3" not in app_names
    
    def test_list_applications_filter_by_multiple_tags(
        self, 
        test_client: TestClient, 
        test_user_token: Any
    ) -> None:
        """Test filtering applications by multiple tags (AND logic)."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        # Create applications
        app1_id = create_application_in_db(test_client, tenant_id, test_user_token.get_id(), "App 1")
        app2_id = create_application_in_db(test_client, tenant_id, test_user_token.get_id(), "App 2")
        app3_id = create_application_in_db(test_client, tenant_id, test_user_token.get_id(), "App 3")
        
        # Set tags
        test_client.put(
            ENDPOINT_APPLICATION_TAGS.format(tenant_id=tenant_id, application_id=app1_id),
            json={"tags": ["production"]},
            headers=headers
        )
        test_client.put(
            ENDPOINT_APPLICATION_TAGS.format(tenant_id=tenant_id, application_id=app2_id),
            json={"tags": ["production", "critical"]},
            headers=headers
        )
        test_client.put(
            ENDPOINT_APPLICATION_TAGS.format(tenant_id=tenant_id, application_id=app3_id),
            json={"tags": ["staging", "critical"]},
            headers=headers
        )
        
        # Get tag IDs
        tags_response = test_client.get(
            ENDPOINT_TAGS.format(tenant_id=tenant_id),
            headers=headers
        )
        tags_data = tags_response.json()["tags"]
        prod_tag_id = next(t["id"] for t in tags_data if t["name"] == "production")
        critical_tag_id = next(t["id"] for t in tags_data if t["name"] == "critical")
        
        # Filter by both production AND critical tags
        response = test_client.get(
            ENDPOINT_APPLICATIONS.format(tenant_id=tenant_id) + f"?tags={prod_tag_id},{critical_tag_id}",
            headers=headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "App 2"
    
    def test_list_applications_invalid_tags_format(
        self, 
        test_client: TestClient, 
        test_user_token: Any
    ) -> None:
        """Test filtering applications with invalid tags format."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        # Create an application
        create_application_in_db(test_client, tenant_id, test_user_token.get_id())
        
        # Try to filter with invalid tag format
        response = test_client.get(
            ENDPOINT_APPLICATIONS.format(tenant_id=tenant_id) + "?tags=invalid,abc",
            headers=headers
        )
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Invalid tag IDs format" in response.json()["detail"]


class TestAutonomousAgentTagRoutes:
    """Test suite for autonomous agent tag management."""
    
    def test_set_and_get_autonomous_agent_tags(
        self, 
        test_client: TestClient, 
        test_user_token: Any
    ) -> None:
        """Test setting and getting tags on an autonomous agent."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        agent_id = create_autonomous_agent_in_db(test_client, tenant_id, test_user_token.get_id())
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        # Set tags
        response = test_client.put(
            ENDPOINT_AUTONOMOUS_AGENT_TAGS.format(tenant_id=tenant_id, autonomous_agent_id=agent_id),
            json={"tags": ["ai", "production"]},
            headers=headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["tags"]) == 2
        
        # Get tags
        get_response = test_client.get(
            ENDPOINT_AUTONOMOUS_AGENT_TAGS.format(tenant_id=tenant_id, autonomous_agent_id=agent_id),
            headers=headers
        )
        
        assert get_response.status_code == status.HTTP_200_OK
        assert len(get_response.json()["tags"]) == 2


class TestChatWidgetTagRoutes:
    """Test suite for chat widget tag management."""
    
    def test_set_and_get_chat_widget_tags(
        self, 
        test_client: TestClient, 
        test_user_token: Any
    ) -> None:
        """Test setting and getting tags on a chat widget."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        widget_id = create_chat_widget_in_db(test_client, tenant_id, test_user_token.get_id())
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        # Set tags
        response = test_client.put(
            ENDPOINT_CHAT_WIDGET_TAGS.format(tenant_id=tenant_id, chat_widget_id=widget_id),
            json={"tags": ["customer-support", "live"]},
            headers=headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["tags"]) == 2
        
        # Get tags
        get_response = test_client.get(
            ENDPOINT_CHAT_WIDGET_TAGS.format(tenant_id=tenant_id, chat_widget_id=widget_id),
            headers=headers
        )
        
        assert get_response.status_code == status.HTTP_200_OK
        assert len(get_response.json()["tags"]) == 2


class TestCredentialTagRoutes:
    """Test suite for credential tag management."""
    
    def test_set_and_get_credential_tags(
        self, 
        test_client: TestClient, 
        test_user_token: Any
    ) -> None:
        """Test setting and getting tags on a credential."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        cred_id = create_credential_in_db(test_client, tenant_id, test_user_token.get_id())
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        # Set tags
        response = test_client.put(
            ENDPOINT_CREDENTIAL_TAGS.format(tenant_id=tenant_id, credential_id=cred_id),
            json={"tags": ["api-keys", "production"]},
            headers=headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["tags"]) == 2
        
        # Get tags
        get_response = test_client.get(
            ENDPOINT_CREDENTIAL_TAGS.format(tenant_id=tenant_id, credential_id=cred_id),
            headers=headers
        )
        
        assert get_response.status_code == status.HTTP_200_OK
        assert len(get_response.json()["tags"]) == 2


class TestDevelopmentPlatformTagRoutes:
    """Test suite for development platform tag management."""
    
    def test_set_and_get_development_platform_tags(
        self, 
        test_client: TestClient, 
        test_user_token: Any
    ) -> None:
        """Test setting and getting tags on a development platform."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        platform_id = create_development_platform_in_db(test_client, tenant_id, test_user_token.get_id())
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        # Set tags
        response = test_client.put(
            ENDPOINT_DEVELOPMENT_PLATFORM_TAGS.format(tenant_id=tenant_id, development_platform_id=platform_id),
            json={"tags": ["ide", "web-based"]},
            headers=headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["tags"]) == 2
        
        # Get tags
        get_response = test_client.get(
            ENDPOINT_DEVELOPMENT_PLATFORM_TAGS.format(tenant_id=tenant_id, development_platform_id=platform_id),
            headers=headers
        )
        
        assert get_response.status_code == status.HTTP_200_OK
        assert len(get_response.json()["tags"]) == 2


class TestTagCascadeDelete:
    """Test suite for tag cascade delete behavior."""
    
    def test_delete_tag_removes_from_resources(
        self, 
        test_client: TestClient, 
        test_user_token: Any
    ) -> None:
        """Test that deleting a tag removes it from all associated resources."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        app_id = create_application_in_db(test_client, tenant_id, test_user_token.get_id())
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        # Set tags on application
        test_client.put(
            ENDPOINT_APPLICATION_TAGS.format(tenant_id=tenant_id, application_id=app_id),
            json={"tags": ["to-delete", "keep-me"]},
            headers=headers
        )
        
        # Get the tag ID for "to-delete"
        tags_response = test_client.get(
            ENDPOINT_TAGS.format(tenant_id=tenant_id) + "?name=to-delete",
            headers=headers
        )
        tag_id = tags_response.json()["tags"][0]["id"]
        
        # Delete the tag
        test_client.delete(
            ENDPOINT_TAG_DETAIL.format(tenant_id=tenant_id, tag_id=tag_id),
            headers=headers
        )
        
        # Verify the application only has one tag now
        app_tags_response = test_client.get(
            ENDPOINT_APPLICATION_TAGS.format(tenant_id=tenant_id, application_id=app_id),
            headers=headers
        )
        
        tags = app_tags_response.json()["tags"]
        assert len(tags) == 1
        assert tags[0]["name"] == "keep-me"
