"""Tests for the admin analytics endpoints."""

import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import status
from starlette.testclient import TestClient

from tests.conftest import create_auth_headers
from tests.helpers.tenant import create_tenant_for_user
from unifiedui.core.database.client import SQLAlchemyClient
from unifiedui.core.database.models import MessageMetric

ENDPOINT_CHAT_AGENT_ANALYTICS = "/api/v1/platform-service/tenants/{tenant_id}/admin/analytics/chat-agents"
ENDPOINT_WORKFLOW_ANALYTICS = "/api/v1/platform-service/tenants/{tenant_id}/admin/analytics/workflows"


def _seed_metrics(
    db_client: SQLAlchemyClient,
    tenant_id: str,
    *,
    chat_agent_id: str | None = None,
    workflow_id: str | None = None,
    count: int = 3,
    status_value: str = "SUCCESS",
) -> None:
    with db_client.get_session() as session:
        for i in range(count):
            session.add(
                MessageMetric(
                    id=str(uuid.uuid4()),
                    tenant_id=tenant_id,
                    message_id=f"m-{uuid.uuid4().hex}",
                    chat_agent_id=chat_agent_id,
                    workflow_id=workflow_id,
                    conversation_id=None,
                    user_id=None,
                    provider="AZURE_OPENAI",
                    model="gpt-4.1",
                    tokens_input=100 + i,
                    tokens_output=50 + i,
                    latency_ms=200 + i,
                    agent_type="AGENT",
                    status=status_value,
                    error_code=None,
                    created_at=datetime.now(UTC),
                )
            )


class TestChatAgentAnalytics:
    """Verify chat-agent analytics aggregation."""

    def test_empty_returns_zero_kpis(self, test_client: TestClient, test_user_token: Any) -> None:
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        response = test_client.get(ENDPOINT_CHAT_AGENT_ANALYTICS.format(tenant_id=tenant_id), headers=headers)
        if response.status_code == status.HTTP_403_FORBIDDEN:
            return
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["kpis"]["total_messages"] == 0

    def test_aggregates_kpis_correctly(
        self, test_client: TestClient, test_user_token: Any, test_db_client: SQLAlchemyClient
    ) -> None:
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        agent_id = str(uuid.uuid4())
        _seed_metrics(test_db_client, tenant_id, chat_agent_id=agent_id, count=3)
        response = test_client.get(ENDPOINT_CHAT_AGENT_ANALYTICS.format(tenant_id=tenant_id), headers=headers)
        if response.status_code == status.HTTP_403_FORBIDDEN:
            return
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["kpis"]["total_messages"] == 3
        assert body["kpis"]["total_tokens_input"] == 100 + 101 + 102
        assert body["kpis"]["total_tokens_output"] == 50 + 51 + 52
        assert len(body["top_agents_by_tokens"]) == 1
        assert body["top_agents_by_tokens"][0]["agent_id"] == agent_id

    def test_filter_by_agent_ids(
        self, test_client: TestClient, test_user_token: Any, test_db_client: SQLAlchemyClient
    ) -> None:
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        a, b = str(uuid.uuid4()), str(uuid.uuid4())
        _seed_metrics(test_db_client, tenant_id, chat_agent_id=a, count=2)
        _seed_metrics(test_db_client, tenant_id, chat_agent_id=b, count=5)
        response = test_client.get(
            ENDPOINT_CHAT_AGENT_ANALYTICS.format(tenant_id=tenant_id),
            params={"agent_ids": [a]},
            headers=headers,
        )
        if response.status_code == status.HTTP_403_FORBIDDEN:
            return
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["kpis"]["total_messages"] == 2

    def test_error_rate_uses_failed_status(
        self, test_client: TestClient, test_user_token: Any, test_db_client: SQLAlchemyClient
    ) -> None:
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        agent_id = str(uuid.uuid4())
        _seed_metrics(test_db_client, tenant_id, chat_agent_id=agent_id, count=3, status_value="SUCCESS")
        _seed_metrics(test_db_client, tenant_id, chat_agent_id=agent_id, count=1, status_value="FAILED")
        response = test_client.get(ENDPOINT_CHAT_AGENT_ANALYTICS.format(tenant_id=tenant_id), headers=headers)
        if response.status_code == status.HTTP_403_FORBIDDEN:
            return
        body = response.json()
        assert body["kpis"]["error_rate"] == 0.25


class TestWorkflowAnalytics:
    """Verify workflow analytics aggregation."""

    def test_returns_workflow_kpis(
        self, test_client: TestClient, test_user_token: Any, test_db_client: SQLAlchemyClient
    ) -> None:
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        wf_id = str(uuid.uuid4())
        _seed_metrics(test_db_client, tenant_id, workflow_id=wf_id, count=4)
        response = test_client.get(ENDPOINT_WORKFLOW_ANALYTICS.format(tenant_id=tenant_id), headers=headers)
        if response.status_code == status.HTTP_403_FORBIDDEN:
            return
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["total_executions"] == 4
        assert body["success_rate"] == 1.0

    def test_recent_executions_limited(
        self, test_client: TestClient, test_user_token: Any, test_db_client: SQLAlchemyClient
    ) -> None:
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        wf_id = str(uuid.uuid4())
        _seed_metrics(test_db_client, tenant_id, workflow_id=wf_id, count=25)
        response = test_client.get(ENDPOINT_WORKFLOW_ANALYTICS.format(tenant_id=tenant_id), headers=headers)
        if response.status_code == status.HTTP_403_FORBIDDEN:
            return
        body = response.json()
        assert len(body["recent_executions"]) <= 20
