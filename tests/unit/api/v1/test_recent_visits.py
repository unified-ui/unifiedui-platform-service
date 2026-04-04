"""Tests for recent visits API endpoints."""

import uuid

from fastapi import status
from starlette.testclient import TestClient

from tests.conftest import create_auth_headers
from tests.helpers.tenant import create_tenant_for_user
from unifiedui.core.database.models import RecentVisit

ENDPOINT_RECENT_VISITS = "/api/v1/platform-service/tenants/{tenant_id}/users/{user_id}/recent-visits"
ENDPOINT_SYNC = "/api/v1/platform-service/tenants/{tenant_id}/users/{user_id}/recent-visits/sync"


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

    create_visit_in_db(test_client, tenant_id, user_id, "chat_agent", resource_name="App 1")
    create_visit_in_db(test_client, tenant_id, user_id, "workflow", resource_name="Agent 1")
    create_visit_in_db(test_client, tenant_id, user_id, "conversation", resource_name="Conv 1")

    response = test_client.get(
        ENDPOINT_RECENT_VISITS.format(tenant_id=tenant_id, user_id=user_id),
        headers=headers,
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["total"] == 3
    assert len(data["visits"]) == 3


def test_list_recent_visits_with_limit(test_client: TestClient):
    """Test listing visits respects limit."""
    user = test_client.create_test_user(name="Visit User")
    headers = create_auth_headers(user, use_cache=False)
    tenant_id = create_tenant_for_user(test_client, user)
    user_id = user.get_id()

    for i in range(5):
        create_visit_in_db(test_client, tenant_id, user_id, resource_name=f"Resource {i}")

    response = test_client.get(
        ENDPOINT_RECENT_VISITS.format(tenant_id=tenant_id, user_id=user_id),
        headers=headers,
        params={"limit": 2},
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert len(data["visits"]) == 2
    assert data["total"] == 5


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

    response = test_client.post(
        ENDPOINT_SYNC.format(tenant_id=tenant_id, user_id=user_id),
        json={
            "visits": [
                {"resource_type": "chat_agent", "resource_id": str(uuid.uuid4()), "resource_name": "App A"},
                {"resource_type": "workflow", "resource_id": str(uuid.uuid4()), "resource_name": "Agent B"},
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
    resource_id = str(uuid.uuid4())

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

    for i in range(50):
        create_visit_in_db(test_client, tenant_id, user_id, resource_name=f"Old Resource {i}")

    response = test_client.post(
        ENDPOINT_SYNC.format(tenant_id=tenant_id, user_id=user_id),
        json={
            "visits": [
                {"resource_type": "chat_agent", "resource_id": str(uuid.uuid4()), "resource_name": "New Resource"},
            ],
        },
        headers=headers,
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["total"] == 50


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
