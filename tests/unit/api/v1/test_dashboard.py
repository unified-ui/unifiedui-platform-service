"""Tests for dashboard API endpoints."""

import uuid

from fastapi import status
from starlette.testclient import TestClient

from tests.conftest import create_auth_headers
from tests.helpers.tenant import create_tenant_for_user
from unifiedui.core.database.enums import PermissionActionEnum, PrincipalTypeEnum
from unifiedui.core.database.models import (
    AutonomousAgent,
    AutonomousAgentMember,
    ChatAgent,
    ChatAgentMember,
    Conversation,
    ConversationMember,
)

ENDPOINT_DASHBOARD_STATS = "/api/v1/platform-service/tenants/{tenant_id}/dashboard/stats"


def create_chat_agent_in_db(
    test_client: TestClient,
    tenant_id: str,
    user_id: str,
    name: str = "Test App",
    is_active: bool = True,
) -> str:
    """Create a chat agent directly in DB and return its ID."""
    app_id = str(uuid.uuid4())
    with test_client.db_client.get_session() as session:
        app = ChatAgent(
            id=app_id,
            tenant_id=tenant_id,
            name=name,
            description="Test chat agent",
            type="N8N",
            config={},
            is_active=is_active,
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


def create_autonomous_agent_in_db(
    test_client: TestClient,
    tenant_id: str,
    user_id: str,
    name: str = "Test Agent",
    is_active: bool = True,
) -> str:
    """Create an autonomous agent directly in DB and return its ID."""
    agent_id = str(uuid.uuid4())
    with test_client.db_client.get_session() as session:
        agent = AutonomousAgent(
            id=agent_id,
            tenant_id=tenant_id,
            name=name,
            description="Test agent",
            type="N8N",
            config={},
            is_active=is_active,
            created_by=user_id,
            updated_by=user_id,
        )
        session.add(agent)
        session.commit()
        member = AutonomousAgentMember(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            autonomous_agent_id=agent_id,
            principal_id=user_id,
            role=PermissionActionEnum.ADMIN,
            created_by=user_id,
            updated_by=user_id,
        )
        session.add(member)
        session.commit()
    return agent_id


def create_conversation_in_db(
    test_client: TestClient,
    tenant_id: str,
    user_id: str,
    app_id: str,
    name: str = "Test Conv",
) -> str:
    """Create a conversation directly in DB and return its ID."""
    conv_id = str(uuid.uuid4())
    with test_client.db_client.get_session() as session:
        conv = Conversation(
            id=conv_id,
            tenant_id=tenant_id,
            chat_agent_id=app_id,
            name=name,
            created_by=user_id,
            updated_by=user_id,
        )
        session.add(conv)
        session.commit()
        member = ConversationMember(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            conversation_id=conv_id,
            principal_id=user_id,
            role=PermissionActionEnum.ADMIN,
            created_by=user_id,
            updated_by=user_id,
        )
        session.add(member)
        session.commit()
    return conv_id


def test_get_dashboard_stats_empty(test_client: TestClient):
    """Test dashboard stats with no entities returns all zeros."""
    user = test_client.create_test_user(name="Stats User")
    headers = create_auth_headers(user, use_cache=False)
    tenant_id = create_tenant_for_user(test_client, user)

    response = test_client.get(
        ENDPOINT_DASHBOARD_STATS.format(tenant_id=tenant_id),
        headers=headers,
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["chat_agents"]["total"] == 0
    assert data["chat_agents"]["active"] == 0
    assert data["chat_agents"]["inactive"] == 0
    assert data["autonomous_agents"]["total"] == 0
    assert data["conversations"]["total"] == 0


def test_get_dashboard_stats_with_entities(test_client: TestClient):
    """Test dashboard stats returns correct counts."""
    user = test_client.create_test_user(name="Stats User")
    headers = create_auth_headers(user, use_cache=False)
    tenant_id = create_tenant_for_user(test_client, user)
    user_id = user.get_id()

    app1_id = create_chat_agent_in_db(test_client, tenant_id, user_id, "App1", is_active=True)
    create_chat_agent_in_db(test_client, tenant_id, user_id, "App2", is_active=True)
    create_chat_agent_in_db(test_client, tenant_id, user_id, "App3", is_active=False)

    create_autonomous_agent_in_db(test_client, tenant_id, user_id, "Agent1", is_active=True)
    create_autonomous_agent_in_db(test_client, tenant_id, user_id, "Agent2", is_active=False)

    create_conversation_in_db(test_client, tenant_id, user_id, app1_id, "Conv1")
    create_conversation_in_db(test_client, tenant_id, user_id, app1_id, "Conv2")

    response = test_client.get(
        ENDPOINT_DASHBOARD_STATS.format(tenant_id=tenant_id),
        headers=headers,
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert data["chat_agents"]["total"] == 3
    assert data["chat_agents"]["active"] == 2
    assert data["chat_agents"]["inactive"] == 1

    assert data["autonomous_agents"]["total"] == 2
    assert data["autonomous_agents"]["active"] == 1
    assert data["autonomous_agents"]["inactive"] == 1

    assert data["conversations"]["total"] == 2
    assert data["conversations"]["active"] == 2
    assert data["conversations"]["inactive"] == 0


def test_get_dashboard_stats_permission_filtering(test_client: TestClient):
    """Test that non-admin users only see entities they have access to."""
    admin_user = test_client.create_test_user(name="Admin User")
    regular_user = test_client.create_test_user(name="Regular User")
    admin_headers = create_auth_headers(admin_user, use_cache=False)
    regular_headers = create_auth_headers(regular_user, use_cache=False)
    admin_id = admin_user.get_id()
    regular_id = regular_user.get_id()

    tenant_id = create_tenant_for_user(test_client, admin_user)

    PRINCIPAL_TYPE_USER = PrincipalTypeEnum.IDENTITY_USER.value
    response = test_client.put(
        f"/api/v1/platform-service/tenants/{tenant_id}/principals",
        json={
            "principal_id": regular_id,
            "principal_type": PRINCIPAL_TYPE_USER,
            "role": "READER",
        },
        headers=admin_headers,
    )
    assert response.status_code == status.HTTP_200_OK

    create_chat_agent_in_db(test_client, tenant_id, admin_id, "Admin App1")
    create_chat_agent_in_db(test_client, tenant_id, admin_id, "Admin App2")

    shared_app_id = str(uuid.uuid4())
    with test_client.db_client.get_session() as session:
        app = ChatAgent(
            id=shared_app_id,
            tenant_id=tenant_id,
            name="Shared App",
            description="Shared",
            type="N8N",
            config={},
            is_active=True,
            created_by=admin_id,
            updated_by=admin_id,
        )
        session.add(app)
        session.commit()
        admin_member = ChatAgentMember(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            chat_agent_id=shared_app_id,
            principal_id=admin_id,
            role=PermissionActionEnum.ADMIN,
            created_by=admin_id,
            updated_by=admin_id,
        )
        session.add(admin_member)
        regular_member = ChatAgentMember(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            chat_agent_id=shared_app_id,
            principal_id=regular_id,
            role=PermissionActionEnum.READ,
            created_by=admin_id,
            updated_by=admin_id,
        )
        session.add(regular_member)
        session.commit()

    admin_response = test_client.get(
        ENDPOINT_DASHBOARD_STATS.format(tenant_id=tenant_id),
        headers=admin_headers,
    )
    assert admin_response.status_code == status.HTTP_200_OK
    admin_data = admin_response.json()
    assert admin_data["chat_agents"]["total"] == 3

    regular_response = test_client.get(
        ENDPOINT_DASHBOARD_STATS.format(tenant_id=tenant_id),
        headers=regular_headers,
    )
    assert regular_response.status_code == status.HTTP_200_OK
    regular_data = regular_response.json()
    assert regular_data["chat_agents"]["total"] == 1


def test_get_dashboard_stats_unauthenticated(test_client: TestClient):
    """Test that unauthenticated requests are rejected."""
    tenant_id = str(uuid.uuid4())
    response = test_client.get(
        ENDPOINT_DASHBOARD_STATS.format(tenant_id=tenant_id),
    )
    assert response.status_code in (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN)
