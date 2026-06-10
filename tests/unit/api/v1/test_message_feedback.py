"""Tests for the message-feedback API endpoints."""

from typing import Any

from fastapi import status
from starlette.testclient import TestClient

from tests.conftest import create_auth_headers
from tests.helpers.tenant import create_tenant_for_user

ENDPOINT_CHAT_AGENTS = "/api/v1/platform-service/tenants/{tenant_id}/chat-agents"
ENDPOINT_CONVERSATIONS = "/api/v1/platform-service/tenants/{tenant_id}/conversations"
ENDPOINT_FEEDBACK = (
    "/api/v1/platform-service/tenants/{tenant_id}/conversations/{conversation_id}/messages/{message_id}/feedback"
)
ENDPOINT_CONV_FEEDBACK = "/api/v1/platform-service/tenants/{tenant_id}/conversations/{conversation_id}/feedback"


def _setup_conversation(test_client: TestClient, user_token: Any) -> tuple[str, str, dict]:
    tenant_id = create_tenant_for_user(test_client, user_token)
    headers = create_auth_headers(user_token, use_cache=False)
    agent = test_client.post(
        ENDPOINT_CHAT_AGENTS.format(tenant_id=tenant_id),
        json={"name": "Agent", "description": "x", "type": "N8N"},
        headers=headers,
    ).json()
    conv = test_client.post(
        ENDPOINT_CONVERSATIONS.format(tenant_id=tenant_id),
        json={"chat_agent_id": agent["id"], "name": "Conv", "description": "x"},
        headers=headers,
    ).json()
    return tenant_id, conv["id"], headers


class TestMessageFeedback:
    """End-to-end tests for the per-user feedback endpoints."""

    def test_upsert_creates_feedback(self, test_client: TestClient, test_user_token: Any) -> None:
        tenant_id, conv_id, headers = _setup_conversation(test_client, test_user_token)
        response = test_client.post(
            ENDPOINT_FEEDBACK.format(tenant_id=tenant_id, conversation_id=conv_id, message_id="msg-1"),
            json={"rating": "THUMBS_UP", "reasons": [], "comment": "great"},
            headers=headers,
        )
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["rating"] == "THUMBS_UP"
        assert body["comment"] == "great"
        assert body["message_id"] == "msg-1"

    def test_upsert_updates_existing(self, test_client: TestClient, test_user_token: Any) -> None:
        tenant_id, conv_id, headers = _setup_conversation(test_client, test_user_token)
        url = ENDPOINT_FEEDBACK.format(tenant_id=tenant_id, conversation_id=conv_id, message_id="msg-2")
        r1 = test_client.post(
            url,
            json={"rating": "THUMBS_UP", "reasons": [], "comment": None},
            headers=headers,
        ).json()
        r2 = test_client.post(
            url,
            json={
                "rating": "THUMBS_DOWN",
                "reasons": ["HALLUCINATION", "INACCURATE"],
                "comment": "bad",
            },
            headers=headers,
        ).json()
        assert r1["id"] == r2["id"]
        assert r2["rating"] == "THUMBS_DOWN"
        assert sorted(r2["reasons"]) == ["HALLUCINATION", "INACCURATE"]

    def test_get_returns_caller_feedback(self, test_client: TestClient, test_user_token: Any) -> None:
        tenant_id, conv_id, headers = _setup_conversation(test_client, test_user_token)
        url = ENDPOINT_FEEDBACK.format(tenant_id=tenant_id, conversation_id=conv_id, message_id="msg-3")
        test_client.post(url, json={"rating": "THUMBS_UP", "reasons": [], "comment": None}, headers=headers)
        response = test_client.get(url, headers=headers)
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["rating"] == "THUMBS_UP"

    def test_get_returns_404_when_missing(self, test_client: TestClient, test_user_token: Any) -> None:
        tenant_id, conv_id, headers = _setup_conversation(test_client, test_user_token)
        url = ENDPOINT_FEEDBACK.format(tenant_id=tenant_id, conversation_id=conv_id, message_id="never")
        assert test_client.get(url, headers=headers).status_code == status.HTTP_404_NOT_FOUND

    def test_delete_removes_feedback(self, test_client: TestClient, test_user_token: Any) -> None:
        tenant_id, conv_id, headers = _setup_conversation(test_client, test_user_token)
        url = ENDPOINT_FEEDBACK.format(tenant_id=tenant_id, conversation_id=conv_id, message_id="msg-d")
        test_client.post(url, json={"rating": "THUMBS_UP", "reasons": [], "comment": None}, headers=headers)
        del_resp = test_client.delete(url, headers=headers)
        assert del_resp.status_code == status.HTTP_204_NO_CONTENT
        assert test_client.get(url, headers=headers).status_code == status.HTTP_404_NOT_FOUND

    def test_delete_returns_404_when_missing(self, test_client: TestClient, test_user_token: Any) -> None:
        tenant_id, conv_id, headers = _setup_conversation(test_client, test_user_token)
        url = ENDPOINT_FEEDBACK.format(tenant_id=tenant_id, conversation_id=conv_id, message_id="ghost")
        assert test_client.delete(url, headers=headers).status_code == status.HTTP_404_NOT_FOUND

    def test_list_conversation_feedback(self, test_client: TestClient, test_user_token: Any) -> None:
        tenant_id, conv_id, headers = _setup_conversation(test_client, test_user_token)
        for i, rating in enumerate(["THUMBS_UP", "THUMBS_DOWN"]):
            test_client.post(
                ENDPOINT_FEEDBACK.format(tenant_id=tenant_id, conversation_id=conv_id, message_id=f"m-{i}"),
                json={"rating": rating, "reasons": [], "comment": None},
                headers=headers,
            )
        response = test_client.get(
            ENDPOINT_CONV_FEEDBACK.format(tenant_id=tenant_id, conversation_id=conv_id),
            headers=headers,
        )
        assert response.status_code == status.HTTP_200_OK
        items = response.json()
        assert len(items) == 2

    def test_upsert_rejects_invalid_rating(self, test_client: TestClient, test_user_token: Any) -> None:
        tenant_id, conv_id, headers = _setup_conversation(test_client, test_user_token)
        response = test_client.post(
            ENDPOINT_FEEDBACK.format(tenant_id=tenant_id, conversation_id=conv_id, message_id="x"),
            json={"rating": "MAYBE", "reasons": [], "comment": None},
            headers=headers,
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_upsert_rejects_unknown_conversation(self, test_client: TestClient, test_user_token: Any) -> None:
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        response = test_client.post(
            ENDPOINT_FEEDBACK.format(tenant_id=tenant_id, conversation_id="nope", message_id="x"),
            json={"rating": "THUMBS_UP", "reasons": [], "comment": None},
            headers=headers,
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_feedback_requires_auth(self, test_client: TestClient, test_user_token: Any) -> None:
        tenant_id, conv_id, _ = _setup_conversation(test_client, test_user_token)
        response = test_client.post(
            ENDPOINT_FEEDBACK.format(tenant_id=tenant_id, conversation_id=conv_id, message_id="m"),
            json={"rating": "THUMBS_UP", "reasons": [], "comment": None},
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
