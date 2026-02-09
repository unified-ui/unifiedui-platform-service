"""Tests for notification API endpoints."""
import uuid
from typing import Any

from fastapi import status
from starlette.testclient import TestClient

from unifiedui.core.database.enums import NotificationTypeEnum
from unifiedui.core.database.models import Notification
from tests.conftest import create_auth_headers


ENDPOINT_NOTIFICATIONS = "/api/v1/platform-service/tenants/{tenant_id}/notifications"
ENDPOINT_UNREAD_COUNT = "/api/v1/platform-service/tenants/{tenant_id}/notifications/unread-count"
ENDPOINT_MARK_READ = "/api/v1/platform-service/tenants/{tenant_id}/notifications/{notification_id}/read"
ENDPOINT_MARK_ALL_READ = "/api/v1/platform-service/tenants/{tenant_id}/notifications/read-all"
ENDPOINT_DELETE = "/api/v1/platform-service/tenants/{tenant_id}/notifications/{notification_id}"


def create_tenant_for_user(test_client: TestClient, user_token: Any, tenant_name: str = "Test Tenant") -> str:
    """Create a tenant and return its ID."""
    headers = create_auth_headers(user_token, use_cache=False)
    response = test_client.post(
        "/api/v1/platform-service/tenants",
        json={"name": tenant_name, "description": f"Tenant for {user_token.get_id()}"},
        headers=headers,
    )
    assert response.status_code == status.HTTP_201_CREATED
    return response.json()["id"]


def create_notification_in_db(
    test_client: TestClient,
    tenant_id: str,
    user_id: str = None,
    notification_type: str = NotificationTypeEnum.AGENT_RUN_FAILED.value,
    title: str = "Test Notification",
    message: str = "Test message",
    is_read: bool = False,
    resource_type: str = None,
    resource_id: str = None,
) -> str:
    """Create a notification directly in DB and return its ID."""
    notif_id = str(uuid.uuid4())
    with test_client.db_client.get_session() as session:
        notif = Notification(
            id=notif_id,
            tenant_id=tenant_id,
            user_id=user_id,
            type=notification_type,
            title=title,
            message=message,
            resource_type=resource_type,
            resource_id=resource_id,
            is_read=is_read,
        )
        session.add(notif)
        session.commit()
    return notif_id


def test_list_notifications_empty(test_client: TestClient):
    """Test listing notifications with no notifications returns empty."""
    user = test_client.create_test_user(name="Notif User")
    headers = create_auth_headers(user, use_cache=False)
    tenant_id = create_tenant_for_user(test_client, user)

    response = test_client.get(
        ENDPOINT_NOTIFICATIONS.format(tenant_id=tenant_id),
        headers=headers,
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["notifications"] == []
    assert data["total"] == 0


def test_list_notifications_with_data(test_client: TestClient):
    """Test listing notifications returns user-specific and broadcast notifications."""
    user = test_client.create_test_user(name="Notif User")
    headers = create_auth_headers(user, use_cache=False)
    tenant_id = create_tenant_for_user(test_client, user)
    user_id = user.get_id()

    create_notification_in_db(test_client, tenant_id, user_id=user_id, title="User Specific")
    create_notification_in_db(test_client, tenant_id, user_id=None, title="Broadcast")
    create_notification_in_db(test_client, tenant_id, user_id="other-user", title="Other User")

    response = test_client.get(
        ENDPOINT_NOTIFICATIONS.format(tenant_id=tenant_id),
        headers=headers,
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["total"] == 2
    titles = {n["title"] for n in data["notifications"]}
    assert "User Specific" in titles
    assert "Broadcast" in titles
    assert "Other User" not in titles


def test_list_notifications_filter_read(test_client: TestClient):
    """Test filtering notifications by read status."""
    user = test_client.create_test_user(name="Notif User")
    headers = create_auth_headers(user, use_cache=False)
    tenant_id = create_tenant_for_user(test_client, user)
    user_id = user.get_id()

    create_notification_in_db(test_client, tenant_id, user_id=user_id, title="Unread", is_read=False)
    create_notification_in_db(test_client, tenant_id, user_id=user_id, title="Read", is_read=True)

    response = test_client.get(
        ENDPOINT_NOTIFICATIONS.format(tenant_id=tenant_id),
        headers=headers,
        params={"is_read": "false"},
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["total"] == 1
    assert data["notifications"][0]["title"] == "Unread"


def test_get_unread_count(test_client: TestClient):
    """Test getting unread notification count."""
    user = test_client.create_test_user(name="Notif User")
    headers = create_auth_headers(user, use_cache=False)
    tenant_id = create_tenant_for_user(test_client, user)
    user_id = user.get_id()

    create_notification_in_db(test_client, tenant_id, user_id=user_id, is_read=False)
    create_notification_in_db(test_client, tenant_id, user_id=user_id, is_read=False)
    create_notification_in_db(test_client, tenant_id, user_id=user_id, is_read=True)
    create_notification_in_db(test_client, tenant_id, user_id=None, is_read=False)

    response = test_client.get(
        ENDPOINT_UNREAD_COUNT.format(tenant_id=tenant_id),
        headers=headers,
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["unread_count"] == 3


def test_mark_notification_read(test_client: TestClient):
    """Test marking a single notification as read."""
    user = test_client.create_test_user(name="Notif User")
    headers = create_auth_headers(user, use_cache=False)
    tenant_id = create_tenant_for_user(test_client, user)
    user_id = user.get_id()

    notif_id = create_notification_in_db(test_client, tenant_id, user_id=user_id, title="Mark Me", is_read=False)

    response = test_client.put(
        ENDPOINT_MARK_READ.format(tenant_id=tenant_id, notification_id=notif_id),
        headers=headers,
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["is_read"] is True
    assert data["title"] == "Mark Me"


def test_mark_notification_read_not_found(test_client: TestClient):
    """Test marking non-existent notification returns 404."""
    user = test_client.create_test_user(name="Notif User")
    headers = create_auth_headers(user, use_cache=False)
    tenant_id = create_tenant_for_user(test_client, user)

    response = test_client.put(
        ENDPOINT_MARK_READ.format(tenant_id=tenant_id, notification_id=str(uuid.uuid4())),
        headers=headers,
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_mark_all_read(test_client: TestClient):
    """Test marking all notifications as read."""
    user = test_client.create_test_user(name="Notif User")
    headers = create_auth_headers(user, use_cache=False)
    tenant_id = create_tenant_for_user(test_client, user)
    user_id = user.get_id()

    create_notification_in_db(test_client, tenant_id, user_id=user_id, is_read=False)
    create_notification_in_db(test_client, tenant_id, user_id=user_id, is_read=False)
    create_notification_in_db(test_client, tenant_id, user_id=None, is_read=False)

    response = test_client.put(
        ENDPOINT_MARK_ALL_READ.format(tenant_id=tenant_id),
        headers=headers,
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["marked_count"] == 3

    unread_response = test_client.get(
        ENDPOINT_UNREAD_COUNT.format(tenant_id=tenant_id),
        headers=headers,
    )
    assert unread_response.json()["unread_count"] == 0


def test_delete_notification(test_client: TestClient):
    """Test deleting a notification."""
    user = test_client.create_test_user(name="Notif User")
    headers = create_auth_headers(user, use_cache=False)
    tenant_id = create_tenant_for_user(test_client, user)
    user_id = user.get_id()

    notif_id = create_notification_in_db(test_client, tenant_id, user_id=user_id)

    response = test_client.delete(
        ENDPOINT_DELETE.format(tenant_id=tenant_id, notification_id=notif_id),
        headers=headers,
    )

    assert response.status_code == status.HTTP_204_NO_CONTENT

    list_response = test_client.get(
        ENDPOINT_NOTIFICATIONS.format(tenant_id=tenant_id),
        headers=headers,
    )
    assert list_response.json()["total"] == 0


def test_delete_notification_not_found(test_client: TestClient):
    """Test deleting non-existent notification returns 404."""
    user = test_client.create_test_user(name="Notif User")
    headers = create_auth_headers(user, use_cache=False)
    tenant_id = create_tenant_for_user(test_client, user)

    response = test_client.delete(
        ENDPOINT_DELETE.format(tenant_id=tenant_id, notification_id=str(uuid.uuid4())),
        headers=headers,
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_create_notification_webhook(test_client: TestClient):
    """Test creating a notification via internal webhook."""
    user = test_client.create_test_user(name="Notif User")
    tenant_id = create_tenant_for_user(test_client, user)

    response = test_client.post(
        ENDPOINT_NOTIFICATIONS.format(tenant_id=tenant_id),
        json={
            "tenant_id": tenant_id,
            "type": NotificationTypeEnum.TRACE_IMPORTED.value,
            "title": "Trace imported",
            "message": "Execution #14 imported successfully",
            "resource_type": "autonomous_agent",
            "resource_id": str(uuid.uuid4()),
        },
    )

    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["title"] == "Trace imported"
    assert data["type"] == "TRACE_IMPORTED"
    assert data["is_read"] is False


def test_notifications_unauthenticated(test_client: TestClient):
    """Test that unauthenticated requests are rejected for list endpoint."""
    tenant_id = str(uuid.uuid4())
    response = test_client.get(
        ENDPOINT_NOTIFICATIONS.format(tenant_id=tenant_id),
    )
    assert response.status_code in (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN)
