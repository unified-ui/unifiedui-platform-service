"""Tests for the per-resource analytics endpoints."""

import uuid

from fastapi import status
from starlette.testclient import TestClient

from tests.conftest import create_auth_headers
from tests.helpers.tenant import create_tenant_for_user
from tests.unit.api.v1.test_admin_analytics import _seed_metrics
from unifiedui.core.database.client import SQLAlchemyClient


class TestPerResourceAnalytics:
    """Verify per-resource analytics endpoints."""

    def test_chat_agent_resource_returns_filtered_kpis(
        self, test_client: TestClient, test_user_token, test_db_client: SQLAlchemyClient
    ) -> None:
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        a, b = str(uuid.uuid4()), str(uuid.uuid4())
        _seed_metrics(test_db_client, tenant_id, chat_agent_id=a, count=2)
        _seed_metrics(test_db_client, tenant_id, chat_agent_id=b, count=5)
        response = test_client.get(
            f"/api/v1/platform-service/tenants/{tenant_id}/chat-agents/{a}/analytics",
            headers=headers,
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["kpis"]["total_messages"] == 2

    def test_workflow_resource_returns_filtered_kpis(
        self, test_client: TestClient, test_user_token, test_db_client: SQLAlchemyClient
    ) -> None:
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)
        wf = str(uuid.uuid4())
        _seed_metrics(test_db_client, tenant_id, workflow_id=wf, count=3)
        response = test_client.get(
            f"/api/v1/platform-service/tenants/{tenant_id}/workflows/{wf}/analytics",
            headers=headers,
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["total_executions"] == 3
