"""Tests for user favorites API endpoints."""
import uuid
from typing import Any
from fastapi import status
from starlette.testclient import TestClient

from unifiedui.core.database.enums import PermissionActionEnum
from unifiedui.core.database.models import (
    Application, ApplicationMember,
    AutonomousAgent, AutonomousAgentMember,
    Conversation, ConversationMember,
)
from tests.conftest import create_auth_headers


# API Endpoints
ENDPOINT_USER_FAVORITES = "/api/v1/platform-service/tenants/{tenant_id}/users/{user_id}/favorites/{resource_type}"
ENDPOINT_USER_FAVORITE_DETAIL = "/api/v1/platform-service/tenants/{tenant_id}/users/{user_id}/favorites/{resource_type}/{resource_id}"


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
            type="N8N",
            config={},
            is_active=True,
            created_by=user_id,
            updated_by=user_id
        )
        session.add(agent)
        session.commit()
        
        # Add user as ADMIN member
        member = AutonomousAgentMember(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            autonomous_agent_id=agent_id,
            principal_id=user_id,
            role=PermissionActionEnum.ADMIN,
            created_by=user_id,
            updated_by=user_id
        )
        session.add(member)
        session.commit()
    return agent_id


def create_conversation_in_db(test_client: TestClient, tenant_id: str, user_id: str, name: str = "Test Conversation") -> str:
    """Helper function to create a conversation directly in DB and return its ID."""
    conversation_id = str(uuid.uuid4())
    application_id = str(uuid.uuid4())
    with test_client.db_client.get_session() as session:
        # First create an application (required for conversation)
        app = Application(
            id=application_id,
            tenant_id=tenant_id,
            name=f"App for {name}",
            description="Test application for conversation",
            type="N8N",
            config={},
            is_active=True,
            created_by=user_id,
            updated_by=user_id
        )
        session.add(app)
        session.commit()
        
        # Add user as ADMIN member of the application
        app_member = ApplicationMember(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            application_id=application_id,
            principal_id=user_id,
            role=PermissionActionEnum.ADMIN,
            created_by=user_id,
            updated_by=user_id
        )
        session.add(app_member)
        session.commit()
        
        # Now create the conversation with application_id
        conversation = Conversation(
            id=conversation_id,
            tenant_id=tenant_id,
            application_id=application_id,
            name=name,
            description="Test conversation",
            is_active=True,
            created_by=user_id,
            updated_by=user_id
        )
        session.add(conversation)
        session.commit()
        
        # Add user as ADMIN member
        member = ConversationMember(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            conversation_id=conversation_id,
            principal_id=user_id,
            role=PermissionActionEnum.ADMIN,
            created_by=user_id,
            updated_by=user_id
        )
        session.add(member)
        session.commit()
    return conversation_id


class TestUserFavoritesRoutes:
    """Test suite for user favorites API routes."""
    
    def test_list_favorites_empty(
        self, 
        test_client: TestClient, 
        test_user_token: Any
    ) -> None:
        """Test listing user favorites when empty."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        user_id = test_user_token.get_id()
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        response = test_client.get(
            ENDPOINT_USER_FAVORITES.format(
                tenant_id=tenant_id,
                user_id=user_id,
                resource_type="applications"
            ),
            headers=headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["favorites"] == []
        assert data["total"] == 0
    
    def test_add_application_favorite(
        self, 
        test_client: TestClient, 
        test_user_token: Any
    ) -> None:
        """Test adding an application to favorites."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        user_id = test_user_token.get_id()
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        # Create an application directly in DB
        app_id = create_application_in_db(test_client, tenant_id, user_id)
        
        # Add to favorites
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
        data = response.json()
        assert data["resource_id"] == app_id
        assert data["resource_type"] == "applications"
        assert data["user_id"] == user_id
        assert data["tenant_id"] == tenant_id
    
    def test_list_favorites_with_data(
        self, 
        test_client: TestClient, 
        test_user_token: Any
    ) -> None:
        """Test listing user favorites with data."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        user_id = test_user_token.get_id()
        headers = create_auth_headers(test_user_token, use_cache=False)
        
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
            headers=headers
        )
        test_client.put(
            ENDPOINT_USER_FAVORITE_DETAIL.format(
                tenant_id=tenant_id,
                user_id=user_id,
                resource_type="applications",
                resource_id=app_id2
            ),
            headers=headers
        )
        
        # List favorites
        response = test_client.get(
            ENDPOINT_USER_FAVORITES.format(
                tenant_id=tenant_id,
                user_id=user_id,
                resource_type="applications"
            ),
            headers=headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total"] == 2
        assert len(data["favorites"]) == 2
        resource_ids = [f["resource_id"] for f in data["favorites"]]
        assert app_id1 in resource_ids
        assert app_id2 in resource_ids
    
    def test_remove_favorite(
        self, 
        test_client: TestClient, 
        test_user_token: Any
    ) -> None:
        """Test removing a favorite."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        user_id = test_user_token.get_id()
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        # Create an application directly in DB and add to favorites
        app_id = create_application_in_db(test_client, tenant_id, user_id)
        test_client.put(
            ENDPOINT_USER_FAVORITE_DETAIL.format(
                tenant_id=tenant_id,
                user_id=user_id,
                resource_type="applications",
                resource_id=app_id
            ),
            headers=headers
        )
        
        # Remove from favorites
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
        
        # Verify it's gone
        response = test_client.get(
            ENDPOINT_USER_FAVORITES.format(
                tenant_id=tenant_id,
                user_id=user_id,
                resource_type="applications"
            ),
            headers=headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total"] == 0
    
    def test_add_duplicate_favorite_returns_existing(
        self, 
        test_client: TestClient, 
        test_user_token: Any
    ) -> None:
        """Test that adding a duplicate favorite returns the existing one."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        user_id = test_user_token.get_id()
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        # Create an application directly in DB
        app_id = create_application_in_db(test_client, tenant_id, user_id)
        
        # Add to favorites twice
        response1 = test_client.put(
            ENDPOINT_USER_FAVORITE_DETAIL.format(
                tenant_id=tenant_id,
                user_id=user_id,
                resource_type="applications",
                resource_id=app_id
            ),
            headers=headers
        )
        response2 = test_client.put(
            ENDPOINT_USER_FAVORITE_DETAIL.format(
                tenant_id=tenant_id,
                user_id=user_id,
                resource_type="applications",
                resource_id=app_id
            ),
            headers=headers
        )
        
        assert response1.status_code == status.HTTP_200_OK
        assert response2.status_code == status.HTTP_200_OK
        
        # Should still only have one favorite
        response = test_client.get(
            ENDPOINT_USER_FAVORITES.format(
                tenant_id=tenant_id,
                user_id=user_id,
                resource_type="applications"
            ),
            headers=headers
        )
        
        assert response.json()["total"] == 1
    
    def test_invalid_resource_type(
        self, 
        test_client: TestClient, 
        test_user_token: Any
    ) -> None:
        """Test that invalid resource type returns error."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        user_id = test_user_token.get_id()
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        response = test_client.get(
            ENDPOINT_USER_FAVORITES.format(
                tenant_id=tenant_id,
                user_id=user_id,
                resource_type="invalid-type"
            ),
            headers=headers
        )
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST


class TestAutonomousAgentFavorites:
    """Test suite for autonomous agent favorites."""
    
    def test_add_and_list_autonomous_agent_favorite(
        self, 
        test_client: TestClient, 
        test_user_token: Any
    ) -> None:
        """Test adding and listing autonomous agent favorites."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        user_id = test_user_token.get_id()
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        # Create an autonomous agent directly in DB
        agent_id = create_autonomous_agent_in_db(test_client, tenant_id, user_id)
        
        # Add to favorites
        response = test_client.put(
            ENDPOINT_USER_FAVORITE_DETAIL.format(
                tenant_id=tenant_id,
                user_id=user_id,
                resource_type="autonomous-agents",
                resource_id=agent_id
            ),
            headers=headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        
        # List favorites
        response = test_client.get(
            ENDPOINT_USER_FAVORITES.format(
                tenant_id=tenant_id,
                user_id=user_id,
                resource_type="autonomous-agents"
            ),
            headers=headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total"] == 1
        assert data["favorites"][0]["resource_id"] == agent_id


class TestConversationFavorites:
    """Test suite for conversation favorites."""
    
    def test_add_and_list_conversation_favorite(
        self, 
        test_client: TestClient, 
        test_user_token: Any
    ) -> None:
        """Test adding and listing conversation favorites."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        user_id = test_user_token.get_id()
        headers = create_auth_headers(test_user_token, use_cache=False)
        
        # Create a conversation directly in DB
        conversation_id = create_conversation_in_db(test_client, tenant_id, user_id)
        
        # Add to favorites
        response = test_client.put(
            ENDPOINT_USER_FAVORITE_DETAIL.format(
                tenant_id=tenant_id,
                user_id=user_id,
                resource_type="conversations",
                resource_id=conversation_id
            ),
            headers=headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        
        # List favorites
        response = test_client.get(
            ENDPOINT_USER_FAVORITES.format(
                tenant_id=tenant_id,
                user_id=user_id,
                resource_type="conversations"
            ),
            headers=headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total"] == 1
        assert data["favorites"][0]["resource_id"] == conversation_id
