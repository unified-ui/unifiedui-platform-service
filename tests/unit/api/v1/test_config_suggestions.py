"""Tests for config suggestions API endpoint."""

import uuid

from fastapi import status
from starlette.testclient import TestClient

from tests.conftest import create_auth_headers
from tests.helpers.tenant import create_tenant_for_user
from unifiedui.core.database.models import ChatAgent, Workflow

ENDPOINT = "/api/v1/platform-service/tenants/{tenant_id}/config-suggestions"


def create_chat_agent_with_config(
    test_client: TestClient,
    tenant_id: str,
    user_id: str,
    agent_type: str,
    config: dict,
) -> str:
    """Create a chat agent with a specific config directly in DB."""
    agent_id = str(uuid.uuid4())
    with test_client.db_client.get_session() as session:
        agent = ChatAgent(
            id=agent_id,
            tenant_id=tenant_id,
            name=f"Agent {agent_id[:8]}",
            description="Test agent",
            type=agent_type,
            config=config,
            is_active=True,
            created_by=user_id,
            updated_by=user_id,
        )
        session.add(agent)
        session.commit()
    return agent_id


def create_workflow_with_config(
    test_client: TestClient,
    tenant_id: str,
    user_id: str,
    workflow_type: str,
    config: dict,
) -> str:
    """Create a workflow with a specific config directly in DB."""
    workflow_id = str(uuid.uuid4())
    with test_client.db_client.get_session() as session:
        workflow = Workflow(
            id=workflow_id,
            tenant_id=tenant_id,
            name=f"Workflow {workflow_id[:8]}",
            description="Test workflow",
            type=workflow_type,
            config=config,
            is_active=True,
            created_by=user_id,
            updated_by=user_id,
        )
        session.add(workflow)
        session.commit()
    return workflow_id


def test_config_suggestions_empty_when_no_resources(test_client: TestClient):
    """Test returns empty suggestions when no agents or workflows exist."""
    user = test_client.create_test_user(name="Suggestions User")
    headers = create_auth_headers(user, use_cache=False)
    tenant_id = create_tenant_for_user(test_client, user)

    response = test_client.get(
        ENDPOINT.format(tenant_id=tenant_id),
        headers=headers,
        params={"type": "N8N"},
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["suggestions"] == {}


def test_config_suggestions_n8n_chat_agent(test_client: TestClient):
    """Test returns distinct endpoint values for N8N chat agents."""
    user = test_client.create_test_user(name="N8N User")
    headers = create_auth_headers(user, use_cache=False)
    tenant_id = create_tenant_for_user(test_client, user)
    user_id = user.get_id()

    create_chat_agent_with_config(
        test_client,
        tenant_id,
        user_id,
        "N8N",
        {"chat_url": "https://n8n.example.com/chat", "workflow_endpoint": "https://n8n.example.com/webhook/abc"},
    )
    create_chat_agent_with_config(
        test_client,
        tenant_id,
        user_id,
        "N8N",
        {"chat_url": "https://n8n.other.com/chat", "workflow_endpoint": "https://n8n.example.com/webhook/abc"},
    )

    response = test_client.get(
        ENDPOINT.format(tenant_id=tenant_id),
        headers=headers,
        params={"type": "N8N"},
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert sorted(data["suggestions"]["chat_url"]) == [
        "https://n8n.example.com/chat",
        "https://n8n.other.com/chat",
    ]
    assert data["suggestions"]["workflow_endpoint"] == ["https://n8n.example.com/webhook/abc"]


def test_config_suggestions_n8n_merges_workflows(test_client: TestClient):
    """Test merges suggestions from chat agents and workflows for N8N."""
    user = test_client.create_test_user(name="N8N Merge User")
    headers = create_auth_headers(user, use_cache=False)
    tenant_id = create_tenant_for_user(test_client, user)
    user_id = user.get_id()

    create_chat_agent_with_config(
        test_client,
        tenant_id,
        user_id,
        "N8N",
        {"workflow_endpoint": "https://n8n.example.com/webhook/agent"},
    )
    create_workflow_with_config(
        test_client,
        tenant_id,
        user_id,
        "N8N",
        {"workflow_endpoint": "https://n8n.example.com/webhook/workflow"},
    )

    response = test_client.get(
        ENDPOINT.format(tenant_id=tenant_id),
        headers=headers,
        params={"type": "N8N"},
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert sorted(data["suggestions"]["workflow_endpoint"]) == [
        "https://n8n.example.com/webhook/agent",
        "https://n8n.example.com/webhook/workflow",
    ]


def test_config_suggestions_foundry(test_client: TestClient):
    """Test returns project_endpoint suggestions for Foundry type."""
    user = test_client.create_test_user(name="Foundry User")
    headers = create_auth_headers(user, use_cache=False)
    tenant_id = create_tenant_for_user(test_client, user)
    user_id = user.get_id()

    create_chat_agent_with_config(
        test_client,
        tenant_id,
        user_id,
        "MICROSOFT_FOUNDRY",
        {"project_endpoint": "https://myproject.openai.azure.com"},
    )
    create_chat_agent_with_config(
        test_client,
        tenant_id,
        user_id,
        "MICROSOFT_FOUNDRY",
        {"project_endpoint": "https://otherproject.openai.azure.com"},
    )

    response = test_client.get(
        ENDPOINT.format(tenant_id=tenant_id),
        headers=headers,
        params={"type": "MICROSOFT_FOUNDRY"},
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert sorted(data["suggestions"]["project_endpoint"]) == [
        "https://myproject.openai.azure.com",
        "https://otherproject.openai.azure.com",
    ]


def test_config_suggestions_rest_api(test_client: TestClient):
    """Test returns endpoint suggestions for REST_API type."""
    user = test_client.create_test_user(name="REST User")
    headers = create_auth_headers(user, use_cache=False)
    tenant_id = create_tenant_for_user(test_client, user)
    user_id = user.get_id()

    create_chat_agent_with_config(
        test_client,
        tenant_id,
        user_id,
        "REST_API",
        {
            "invoke_endpoint": "https://api.example.com/invoke",
            "create_conversation_endpoint": "https://api.example.com/conversations",
        },
    )

    response = test_client.get(
        ENDPOINT.format(tenant_id=tenant_id),
        headers=headers,
        params={"type": "REST_API"},
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["suggestions"]["invoke_endpoint"] == ["https://api.example.com/invoke"]
    assert data["suggestions"]["create_conversation_endpoint"] == ["https://api.example.com/conversations"]


def test_config_suggestions_query_filter(test_client: TestClient):
    """Test q parameter filters suggestion values by substring."""
    user = test_client.create_test_user(name="Filter User")
    headers = create_auth_headers(user, use_cache=False)
    tenant_id = create_tenant_for_user(test_client, user)
    user_id = user.get_id()

    create_chat_agent_with_config(
        test_client,
        tenant_id,
        user_id,
        "MICROSOFT_FOUNDRY",
        {"project_endpoint": "https://myproject.openai.azure.com"},
    )
    create_chat_agent_with_config(
        test_client,
        tenant_id,
        user_id,
        "MICROSOFT_FOUNDRY",
        {"project_endpoint": "https://otherproject.cognitiveservices.azure.com"},
    )

    response = test_client.get(
        ENDPOINT.format(tenant_id=tenant_id),
        headers=headers,
        params={"type": "MICROSOFT_FOUNDRY", "q": "openai"},
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["suggestions"]["project_endpoint"] == ["https://myproject.openai.azure.com"]


def test_config_suggestions_unknown_type(test_client: TestClient):
    """Test unknown platform type returns empty suggestions without error."""
    user = test_client.create_test_user(name="Unknown Type User")
    headers = create_auth_headers(user, use_cache=False)
    tenant_id = create_tenant_for_user(test_client, user)

    response = test_client.get(
        ENDPOINT.format(tenant_id=tenant_id),
        headers=headers,
        params={"type": "UNKNOWN_PLATFORM"},
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["suggestions"] == {}


def test_config_suggestions_tenant_isolation(test_client: TestClient):
    """Test suggestions are scoped to the requested tenant only."""
    user_a = test_client.create_test_user(name="Isolation User A")
    user_b = test_client.create_test_user(name="Isolation User B")
    headers_a = create_auth_headers(user_a, use_cache=False)
    tenant_a = create_tenant_for_user(test_client, user_a, tenant_name="Tenant A")
    tenant_b = create_tenant_for_user(test_client, user_b, tenant_name="Tenant B")

    create_chat_agent_with_config(
        test_client,
        tenant_a,
        user_a.get_id(),
        "MICROSOFT_FOUNDRY",
        {"project_endpoint": "https://tenant-a.openai.azure.com"},
    )
    create_chat_agent_with_config(
        test_client,
        tenant_b,
        user_b.get_id(),
        "MICROSOFT_FOUNDRY",
        {"project_endpoint": "https://tenant-b.openai.azure.com"},
    )

    response = test_client.get(
        ENDPOINT.format(tenant_id=tenant_a),
        headers=headers_a,
        params={"type": "MICROSOFT_FOUNDRY"},
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["suggestions"]["project_endpoint"] == ["https://tenant-a.openai.azure.com"]


def test_config_suggestions_excludes_empty_values(test_client: TestClient):
    """Test that empty or whitespace-only config values are excluded."""
    user = test_client.create_test_user(name="Empty Value User")
    headers = create_auth_headers(user, use_cache=False)
    tenant_id = create_tenant_for_user(test_client, user)
    user_id = user.get_id()

    create_chat_agent_with_config(
        test_client,
        tenant_id,
        user_id,
        "MICROSOFT_FOUNDRY",
        {"project_endpoint": "https://valid.openai.azure.com"},
    )
    create_chat_agent_with_config(
        test_client,
        tenant_id,
        user_id,
        "MICROSOFT_FOUNDRY",
        {"project_endpoint": ""},
    )
    create_chat_agent_with_config(
        test_client,
        tenant_id,
        user_id,
        "MICROSOFT_FOUNDRY",
        {"project_endpoint": "   "},
    )

    response = test_client.get(
        ENDPOINT.format(tenant_id=tenant_id),
        headers=headers,
        params={"type": "MICROSOFT_FOUNDRY"},
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["suggestions"]["project_endpoint"] == ["https://valid.openai.azure.com"]


def test_config_suggestions_deduplicates(test_client: TestClient):
    """Test duplicate config values are deduplicated."""
    user = test_client.create_test_user(name="Dedup User")
    headers = create_auth_headers(user, use_cache=False)
    tenant_id = create_tenant_for_user(test_client, user)
    user_id = user.get_id()

    for _ in range(3):
        create_chat_agent_with_config(
            test_client,
            tenant_id,
            user_id,
            "MICROSOFT_FOUNDRY",
            {"project_endpoint": "https://same.openai.azure.com"},
        )

    response = test_client.get(
        ENDPOINT.format(tenant_id=tenant_id),
        headers=headers,
        params={"type": "MICROSOFT_FOUNDRY"},
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["suggestions"]["project_endpoint"] == ["https://same.openai.azure.com"]


def test_config_suggestions_requires_auth(test_client: TestClient):
    """Test that unauthenticated request returns 401."""
    tenant_id = str(uuid.uuid4())

    response = test_client.get(
        ENDPOINT.format(tenant_id=tenant_id),
        params={"type": "N8N"},
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
