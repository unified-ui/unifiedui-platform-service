"""Tests for the internal message-metrics ingestion endpoints."""

from typing import Any
from unittest.mock import patch

from fastapi import status
from starlette.testclient import TestClient

from tests.helpers.tenant import create_tenant_for_user

ENDPOINT_INGEST = "/api/v1/platform-service/internal/metrics/messages"
ENDPOINT_INGEST_BATCH = "/api/v1/platform-service/internal/metrics/messages:batch"
TEST_SERVICE_KEY = "test-service-key-for-s2s-12345"


def _payload(tenant_id: str, message_id: str = "msg-1", **overrides: Any) -> dict:
    base = {
        "tenant_id": tenant_id,
        "message_id": message_id,
        "chat_agent_id": None,
        "workflow_id": None,
        "conversation_id": None,
        "user_id": None,
        "provider": "AZURE_OPENAI",
        "model": "gpt-4.1",
        "tokens_input": 100,
        "tokens_output": 50,
        "latency_ms": 1234,
        "agent_type": "AGENT",
        "status": "SUCCESS",
        "error_code": None,
    }
    base.update(overrides)
    return base


class TestMessageMetricIngest:
    """Single-metric ingest endpoint."""

    def test_requires_service_key(self, test_client: TestClient, test_user_token: Any) -> None:
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        response = test_client.post(ENDPOINT_INGEST, json=_payload(tenant_id))
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_rejects_invalid_service_key(self, test_client: TestClient, test_user_token: Any) -> None:
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        with patch("unifiedui.core.middleware.apis.v1.auth.settings") as mock_settings:
            mock_settings.x_agent_service_key = TEST_SERVICE_KEY
            response = test_client.post(
                ENDPOINT_INGEST,
                json=_payload(tenant_id),
                headers={"X-Service-Key": "wrong-key"},
            )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_ingest_creates_metric(self, test_client: TestClient, test_user_token: Any) -> None:
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        with patch(
            "unifiedui.core.middleware.apis.v1.auth._resolve_service_credential",
            return_value=TEST_SERVICE_KEY,
        ):
            response = test_client.post(
                ENDPOINT_INGEST,
                json=_payload(tenant_id, message_id="m-create"),
                headers={"X-Service-Key": TEST_SERVICE_KEY},
            )
        assert response.status_code == status.HTTP_201_CREATED
        body = response.json()
        assert body["tenant_id"] == tenant_id
        assert body["message_id"] == "m-create"
        assert body["tokens_input"] == 100
        assert body["status"] == "SUCCESS"
        assert body["id"]

    def test_ingest_is_idempotent_on_message_id(self, test_client: TestClient, test_user_token: Any) -> None:
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        with patch(
            "unifiedui.core.middleware.apis.v1.auth._resolve_service_credential",
            return_value=TEST_SERVICE_KEY,
        ):
            r1 = test_client.post(
                ENDPOINT_INGEST,
                json=_payload(tenant_id, message_id="m-idem", tokens_input=10),
                headers={"X-Service-Key": TEST_SERVICE_KEY},
            )
            r2 = test_client.post(
                ENDPOINT_INGEST,
                json=_payload(tenant_id, message_id="m-idem", tokens_input=999),
                headers={"X-Service-Key": TEST_SERVICE_KEY},
            )
        assert r1.status_code == status.HTTP_201_CREATED
        assert r2.status_code == status.HTTP_201_CREATED
        assert r1.json()["id"] == r2.json()["id"]
        assert r2.json()["tokens_input"] == 999

    def test_ingest_rejects_invalid_status(self, test_client: TestClient, test_user_token: Any) -> None:
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        with patch(
            "unifiedui.core.middleware.apis.v1.auth._resolve_service_credential",
            return_value=TEST_SERVICE_KEY,
        ):
            response = test_client.post(
                ENDPOINT_INGEST,
                json=_payload(tenant_id, message_id="m-bad", status="BOGUS"),
                headers={"X-Service-Key": TEST_SERVICE_KEY},
            )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_ingest_rejects_negative_tokens(self, test_client: TestClient, test_user_token: Any) -> None:
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        with patch(
            "unifiedui.core.middleware.apis.v1.auth._resolve_service_credential",
            return_value=TEST_SERVICE_KEY,
        ):
            response = test_client.post(
                ENDPOINT_INGEST,
                json=_payload(tenant_id, message_id="m-neg", tokens_input=-1),
                headers={"X-Service-Key": TEST_SERVICE_KEY},
            )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


class TestMessageMetricBatchIngest:
    """Batch ingest endpoint."""

    def test_batch_inserts_and_updates(self, test_client: TestClient, test_user_token: Any) -> None:
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        with patch(
            "unifiedui.core.middleware.apis.v1.auth._resolve_service_credential",
            return_value=TEST_SERVICE_KEY,
        ):
            seed = test_client.post(
                ENDPOINT_INGEST,
                json=_payload(tenant_id, message_id="m-batch-1"),
                headers={"X-Service-Key": TEST_SERVICE_KEY},
            )
            assert seed.status_code == status.HTTP_201_CREATED

            response = test_client.post(
                ENDPOINT_INGEST_BATCH,
                json={
                    "items": [
                        _payload(tenant_id, message_id="m-batch-1", tokens_input=42),
                        _payload(tenant_id, message_id="m-batch-2"),
                        _payload(tenant_id, message_id="m-batch-3"),
                    ]
                },
                headers={"X-Service-Key": TEST_SERVICE_KEY},
            )
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["inserted"] == 2
        assert body["updated"] == 1

    def test_batch_rejects_empty(self, test_client: TestClient, test_user_token: Any) -> None:
        with patch(
            "unifiedui.core.middleware.apis.v1.auth._resolve_service_credential",
            return_value=TEST_SERVICE_KEY,
        ):
            response = test_client.post(
                ENDPOINT_INGEST_BATCH,
                json={"items": []},
                headers={"X-Service-Key": TEST_SERVICE_KEY},
            )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_batch_rejects_oversize(self, test_client: TestClient, test_user_token: Any) -> None:
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        items = [_payload(tenant_id, message_id=f"m-x-{i}") for i in range(101)]
        with patch(
            "unifiedui.core.middleware.apis.v1.auth._resolve_service_credential",
            return_value=TEST_SERVICE_KEY,
        ):
            response = test_client.post(
                ENDPOINT_INGEST_BATCH,
                json={"items": items},
                headers={"X-Service-Key": TEST_SERVICE_KEY},
            )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
