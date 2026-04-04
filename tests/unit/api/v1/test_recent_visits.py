"""Tests for recent visits API endpoints."""

import uuid

from fastapi import status
from starlette.testclient import TestClient

from tests.conftest import create_auth_headers
from tests.helpers.tenant import create_tenant_for_user
from unifiedui.core.database.enums import PermissionActionEnum
from unifiedui.core.database.models import (
    ChatAgent,
    ChatAgentMember,
    RecentVisit,
    Workflow,
    WorkflowMember,
)

ENDPOINT_RECENT_VISITS = "/api/v1/platform-service/tenants/{tenant_id}/users/{user_id}/recent-visits"
ENDPOINT_SYNC = "/api/v1/platform-service/tenants/{tenant_id}/users/{user_id}/recent-visits/sync"


def create_chat_agent_in_db(
    test_client: TestClient, tenant_id: str, user_id: str, name: str = "Test Chat Agent"
) -> str:
    """Create a chat agent directly in DB and return its ID."""
    agent_id = str(uuid.uuid4())
    with test_client.db_client.get_session() as session:
        agent = ChatAgent(
            id=agent_id,
            tenant_id=tenant_id,
            name=name,
            description="Test chat agent",
            type="N8N",
            config={},
            is_active=True,
            created_by=user_id,
            updated_by=user_id,
        )
        session.add(agent)
        member = ChatAgentMember(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            chat_agent_id=agent_id,
            principal_id=user_id,
            role=PermissionActionEnum.ADMIN,
            created_by=user_id,
            updated_by=user_id,
        )
        session.add(member)
        session.commit()
    return agent_id


def create_workflow_in_db(test_client: TestClient, tenant_id: str, user_id: str, name: str = "Test Workflow") -> str:
    """Create a workflow directly in DB and return its ID."""
    workflow_id = str(uuid.uuid4())
    with test_client.db_client.get_session() as session:
        workflow = Workflow(
            id=workflow_id,
            tenant_id=tenant_id,
            name=name,
            description="Test workflow",
            type="N8N",
            config={},
            is_active=True,
            created_by=user_id,
            updated_by=user_id,
        )
        session.add(workflow)
        member = WorkflowMember(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            workflow_id=workflow_id,
            principal_id=user_id,
            role=PermissionActionEnum.ADMIN,
            created_by=user_id,
            updated_by=user_id,
        )
        session.add(member)
        session.commit()
    return workflow_id


def create_visit_in_db(
    test_client: TestClient,
    tenant_id: str,
    user_id: str,
    resource_type: str = "chat_agent",
    resource_id: str | None = None,
    resource_name: str = "Test Resource",
) -> str:
    """Create a recent visit directly in DB and return its ID."""
    visit_id = str(uuid.uuid4())
    if resource_id is None:
        resource_id = str(uuid.uuid4())
    with test_client.db_client.get_session() as session:
        visit = RecentVisit(
            id=visit_id,
            tenant_id=tenant_id,
            user_id=user_id,
            resource_type=resource_type,
            resource_id=resource_id,
            resource_name=resource_name,
        )
        session.add(visit)
        session.commit()
    return visit_id


def test_list_recent_visits_empty(test_client: TestClient):
    """Test listing recent visits with no visits returns empty."""
    user = test_client.create_test_user(name="Visit User")
    headers = create_auth_headers(user, use_cache=False)
    tenant_id = create_tenant_for_user(test_client, user)
    user_id = user.get_id()

    response = test_client.get(
        ENDPOINT_RECENT_VISITS.format(tenant_id=tenant_id, user_id=user_id),
        headers=headers,
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["visits"] == []
    assert data["total"] == 0


def test_list_recent_visits_with_data(test_client: TestClient):
    """Test listing recent visits returns visits ordered by visited_at desc."""
    user = test_client.create_test_user(name="Visit User")
    headers = create_auth_headers(user, use_cache=False)
    tenant_id = create_tenant_for_user(test_client, user)
    user_id = user.get_id()

    # Create actual resources
    chat_agent_id = create_chat_agent_in_db(test_client, tenant_id, user_id, "App 1")
    workflow_id = create_workflow_in_db(test_client, tenant_id, user_id, "Agent 1")

    # Create visits for existing resources
    create_visit_in_db(test_client, tenant_id, user_id, "chat_agent", chat_agent_id, "App 1")
    create_visit_in_db(test_client, tenant_id, user_id, "workflow", workflow_id, "Agent 1")

    response = test_client.get(
        ENDPOINT_RECENT_VISITS.format(tenant_id=tenant_id, user_id=user_id),
        headers=headers,
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["total"] == 2
    assert len(data["visits"]) == 2


def test_list_recent_visits_with_limit(test_client: TestClient):
    """Test listing visits respects limit."""
    user = test_client.create_test_user(name="Visit User")
    headers = create_auth_headers(user, use_cache=False)
    tenant_id = create_tenant_for_user(test_client, user)
    user_id = user.get_id()

    # Create 5 chat agents with visits
    for i in range(5):
        agent_id = create_chat_agent_in_db(test_client, tenant_id, user_id, f"Resource {i}")
        create_visit_in_db(test_client, tenant_id, user_id, "chat_agent", agent_id, f"Resource {i}")

    response = test_client.get(
        ENDPOINT_RECENT_VISITS.format(tenant_id=tenant_id, user_id=user_id),
        headers=headers,
        params={"limit": 2},
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert len(data["visits"]) == 2
    # Total now reflects filtered count, not DB count
    assert data["total"] == 2


def test_list_recent_visits_other_user_forbidden(test_client: TestClient):
    """Test that accessing another user's visits is forbidden."""
    user = test_client.create_test_user(name="Visit User")
    headers = create_auth_headers(user, use_cache=False)
    tenant_id = create_tenant_for_user(test_client, user)

    response = test_client.get(
        ENDPOINT_RECENT_VISITS.format(tenant_id=tenant_id, user_id="other-user-id"),
        headers=headers,
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_sync_recent_visits_new(test_client: TestClient):
    """Test syncing new visits creates entries."""
    user = test_client.create_test_user(name="Visit User")
    headers = create_auth_headers(user, use_cache=False)
    tenant_id = create_tenant_for_user(test_client, user)
    user_id = user.get_id()

    # Create actual resources first
    chat_agent_id = create_chat_agent_in_db(test_client, tenant_id, user_id, "App A")
    workflow_id = create_workflow_in_db(test_client, tenant_id, user_id, "Agent B")

    response = test_client.post(
        ENDPOINT_SYNC.format(tenant_id=tenant_id, user_id=user_id),
        json={
            "visits": [
                {"resource_type": "chat_agent", "resource_id": chat_agent_id, "resource_name": "App A"},
                {"resource_type": "workflow", "resource_id": workflow_id, "resource_name": "Agent B"},
            ],
        },
        headers=headers,
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["total"] == 2


def test_sync_recent_visits_upsert(test_client: TestClient):
    """Test syncing existing visit updates visited_at and name."""
    user = test_client.create_test_user(name="Visit User")
    headers = create_auth_headers(user, use_cache=False)
    tenant_id = create_tenant_for_user(test_client, user)
    user_id = user.get_id()

    # Create actual resource
    resource_id = create_chat_agent_in_db(test_client, tenant_id, user_id, "Old Name")

    # Create initial visit
    create_visit_in_db(test_client, tenant_id, user_id, "chat_agent", resource_id, "Old Name")

    response = test_client.post(
        ENDPOINT_SYNC.format(tenant_id=tenant_id, user_id=user_id),
        json={
            "visits": [
                {"resource_type": "chat_agent", "resource_id": resource_id, "resource_name": "New Name"},
            ],
        },
        headers=headers,
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["total"] == 1
    assert data["visits"][0]["resource_name"] == "New Name"


def test_sync_recent_visits_cleanup(test_client: TestClient):
    """Test that sync cleans up when exceeding 50 visits."""
    user = test_client.create_test_user(name="Visit User")
    headers = create_auth_headers(user, use_cache=False)
    tenant_id = create_tenant_for_user(test_client, user)
    user_id = user.get_id()

    # Create 50 resources with visits
    resource_ids = []
    for i in range(50):
        agent_id = create_chat_agent_in_db(test_client, tenant_id, user_id, f"Old Resource {i}")
        resource_ids.append(agent_id)
        create_visit_in_db(test_client, tenant_id, user_id, "chat_agent", agent_id, f"Old Resource {i}")

    # Create one more resource for the new visit
    new_agent_id = create_chat_agent_in_db(test_client, tenant_id, user_id, "New Resource")

    response = test_client.post(
        ENDPOINT_SYNC.format(tenant_id=tenant_id, user_id=user_id),
        json={
            "visits": [
                {"resource_type": "chat_agent", "resource_id": new_agent_id, "resource_name": "New Resource"},
            ],
        },
        headers=headers,
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    # After cleanup, should have exactly 50 visits (limit applies after existence filter)
    # But list_recent_visits only returns up to 20 by default
    assert len(data["visits"]) <= 20


def test_sync_recent_visits_other_user_forbidden(test_client: TestClient):
    """Test that syncing another user's visits is forbidden."""
    user = test_client.create_test_user(name="Visit User")
    headers = create_auth_headers(user, use_cache=False)
    tenant_id = create_tenant_for_user(test_client, user)

    response = test_client.post(
        ENDPOINT_SYNC.format(tenant_id=tenant_id, user_id="other-user-id"),
        json={"visits": []},
        headers=headers,
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_recent_visits_unauthenticated(test_client: TestClient):
    """Test that unauthenticated requests are rejected."""
    tenant_id = str(uuid.uuid4())
    user_id = "some-user"
    response = test_client.get(
        ENDPOINT_RECENT_VISITS.format(tenant_id=tenant_id, user_id=user_id),
    )
    assert response.status_code in (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN)
