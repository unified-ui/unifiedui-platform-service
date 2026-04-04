"""Tests for global search API endpoint."""

import uuid

from fastapi import status
from starlette.testclient import TestClient

from tests.conftest import create_auth_headers
from tests.helpers.tenant import add_user_to_tenant, create_tenant_for_user
from unifiedui.core.database.enums import PermissionActionEnum, PrincipalTypeEnum
from unifiedui.core.database.models import (
    ChatAgent,
    ChatAgentMember,
    Conversation,
    ConversationMember,
    Workflow,
    WorkflowMember,
)

ENDPOINT_SEARCH = "/api/v1/platform-service/tenants/{tenant_id}/search"
PRINCIPAL_TYPE_USER = PrincipalTypeEnum.IDENTITY_USER.value


def create_chat_agent_in_db(
    test_client: TestClient,
    tenant_id: str,
    user_id: str,
    name: str = "Test App",
    description: str = "Test chat agent",
    is_active: bool = True,
) -> str:
    """Create a chat agent directly in DB and return its ID."""
    app_id = str(uuid.uuid4())
    with test_client.db_client.get_session() as session:
        app = ChatAgent(
            id=app_id,
            tenant_id=tenant_id,
            name=name,
            description=description,
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


def create_workflow_in_db(
    test_client: TestClient,
    tenant_id: str,
    user_id: str,
    name: str = "Test Agent",
    description: str = "Test agent",
    is_active: bool = True,
) -> str:
    """Create an autonomous agent directly in DB and return its ID."""
    agent_id = str(uuid.uuid4())
    with test_client.db_client.get_session() as session:
        agent = Workflow(
            id=agent_id,
            tenant_id=tenant_id,
            name=name,
            description=description,
            type="N8N",
            config={},
            is_active=is_active,
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


def test_search_empty_query(test_client: TestClient):
    """Test that empty query returns no results."""
    user = test_client.create_test_user(name="Search User")
    headers = create_auth_headers(user, use_cache=False)
    tenant_id = create_tenant_for_user(test_client, user)

    response = test_client.get(
        ENDPOINT_SEARCH.format(tenant_id=tenant_id),
        headers=headers,
        params={"q": ""},
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["results"] == []
    assert data["total"] == 0


def test_search_by_name(test_client: TestClient):
    """Test search finds entities by name."""
    user = test_client.create_test_user(name="Search User")
    headers = create_auth_headers(user, use_cache=False)
    tenant_id = create_tenant_for_user(test_client, user)
    user_id = user.get_id()

    create_chat_agent_in_db(test_client, tenant_id, user_id, "Support Bot", "Handles support")
    create_chat_agent_in_db(test_client, tenant_id, user_id, "Invoice Agent", "Processes invoices")
    create_workflow_in_db(test_client, tenant_id, user_id, "Support Monitor", "Monitors support")

    response = test_client.get(
        ENDPOINT_SEARCH.format(tenant_id=tenant_id),
        headers=headers,
        params={"q": "Support"},
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["total"] == 2
    assert data["query"] == "Support"
    result_names = {r["name"] for r in data["results"]}
    assert "Support Bot" in result_names
    assert "Support Monitor" in result_names


def test_search_by_description(test_client: TestClient):
    """Test search finds entities by description."""
    user = test_client.create_test_user(name="Search User")
    headers = create_auth_headers(user, use_cache=False)
    tenant_id = create_tenant_for_user(test_client, user)
    user_id = user.get_id()

    create_chat_agent_in_db(test_client, tenant_id, user_id, "App Alpha", "Financial processing system")
    create_chat_agent_in_db(test_client, tenant_id, user_id, "App Beta", "Customer management")

    response = test_client.get(
        ENDPOINT_SEARCH.format(tenant_id=tenant_id),
        headers=headers,
        params={"q": "financial"},
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["total"] == 1
    assert data["results"][0]["name"] == "App Alpha"
    assert data["results"][0]["match_field"] == "description"


def test_search_with_type_filter(test_client: TestClient):
    """Test search filters by entity type."""
    user = test_client.create_test_user(name="Search User")
    headers = create_auth_headers(user, use_cache=False)
    tenant_id = create_tenant_for_user(test_client, user)
    user_id = user.get_id()

    create_chat_agent_in_db(test_client, tenant_id, user_id, "Support App")
    create_workflow_in_db(test_client, tenant_id, user_id, "Support Agent")

    response = test_client.get(
        ENDPOINT_SEARCH.format(tenant_id=tenant_id),
        headers=headers,
        params={"q": "Support", "types": "chat_agent"},
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["total"] == 1
    assert data["results"][0]["type"] == "chat_agent"
    assert data["results"][0]["name"] == "Support App"


def test_search_permission_filtering(test_client: TestClient):
    """Test that non-admin users only see entities they have access to."""
    admin_user = test_client.create_test_user(name="Admin User")
    regular_user = test_client.create_test_user(name="Regular User")
    admin_headers = create_auth_headers(admin_user, use_cache=False)
    regular_headers = create_auth_headers(regular_user, use_cache=False)
    admin_id = admin_user.get_id()
    regular_id = regular_user.get_id()

    tenant_id = create_tenant_for_user(test_client, admin_user)
    add_user_to_tenant(test_client, tenant_id, admin_headers, regular_id, "READER")

    create_chat_agent_in_db(test_client, tenant_id, admin_id, "Secret App")

    shared_app_id = str(uuid.uuid4())
    with test_client.db_client.get_session() as session:
        app = ChatAgent(
            id=shared_app_id,
            tenant_id=tenant_id,
            name="Shared App",
            description="Shared chat agent",
            type="N8N",
            config={},
            is_active=True,
            created_by=admin_id,
            updated_by=admin_id,
        )
        session.add(app)
        session.commit()
        for pid, role in [(admin_id, PermissionActionEnum.ADMIN), (regular_id, PermissionActionEnum.READ)]:
            member = ChatAgentMember(
                id=str(uuid.uuid4()),
                tenant_id=tenant_id,
                chat_agent_id=shared_app_id,
                principal_id=pid,
                role=role,
                created_by=admin_id,
                updated_by=admin_id,
            )
            session.add(member)
        session.commit()

    admin_response = test_client.get(
        ENDPOINT_SEARCH.format(tenant_id=tenant_id),
        headers=admin_headers,
        params={"q": "App"},
    )
    assert admin_response.status_code == status.HTTP_200_OK
    assert admin_response.json()["total"] == 2

    regular_response = test_client.get(
        ENDPOINT_SEARCH.format(tenant_id=tenant_id),
        headers=regular_headers,
        params={"q": "App"},
    )
    assert regular_response.status_code == status.HTTP_200_OK
    assert regular_response.json()["total"] == 1
    assert regular_response.json()["results"][0]["name"] == "Shared App"


def test_search_with_limit(test_client: TestClient):
    """Test search respects limit parameter."""
    user = test_client.create_test_user(name="Search User")
    headers = create_auth_headers(user, use_cache=False)
    tenant_id = create_tenant_for_user(test_client, user)
    user_id = user.get_id()

    for i in range(5):
        create_chat_agent_in_db(test_client, tenant_id, user_id, f"App {i}")

    response = test_client.get(
        ENDPOINT_SEARCH.format(tenant_id=tenant_id),
        headers=headers,
        params={"q": "App", "limit": 2},
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert len(data["results"]) == 2


def test_search_across_multiple_types(test_client: TestClient):
    """Test search returns results from multiple entity types."""
    user = test_client.create_test_user(name="Search User")
    headers = create_auth_headers(user, use_cache=False)
    tenant_id = create_tenant_for_user(test_client, user)
    user_id = user.get_id()

    create_chat_agent_in_db(test_client, tenant_id, user_id, "Invoice Bot")
    create_workflow_in_db(test_client, tenant_id, user_id, "Invoice Monitor")
    app_id = create_chat_agent_in_db(test_client, tenant_id, user_id, "Helper App")
    create_conversation_in_db(test_client, tenant_id, user_id, app_id, "Invoice Discussion")

    response = test_client.get(
        ENDPOINT_SEARCH.format(tenant_id=tenant_id),
        headers=headers,
        params={"q": "Invoice"},
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["total"] == 3
    result_types = {r["type"] for r in data["results"]}
    assert "chat_agent" in result_types
    assert "workflow" in result_types
    assert "conversation" in result_types


def test_search_case_insensitive(test_client: TestClient):
    """Test search is case-insensitive."""
    user = test_client.create_test_user(name="Search User")
    headers = create_auth_headers(user, use_cache=False)
    tenant_id = create_tenant_for_user(test_client, user)
    user_id = user.get_id()

    create_chat_agent_in_db(test_client, tenant_id, user_id, "Support Bot")

    response = test_client.get(
        ENDPOINT_SEARCH.format(tenant_id=tenant_id),
        headers=headers,
        params={"q": "support bot"},
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["total"] == 1


def test_search_unauthenticated(test_client: TestClient):
    """Test that unauthenticated requests are rejected."""
    tenant_id = str(uuid.uuid4())
    response = test_client.get(
        ENDPOINT_SEARCH.format(tenant_id=tenant_id),
        params={"q": "test"},
    )
    assert response.status_code in (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN)
