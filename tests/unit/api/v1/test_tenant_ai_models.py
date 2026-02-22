"""Tests for tenant AI models API endpoints."""

from typing import Any

from fastapi import status
from starlette.testclient import TestClient

from tests.conftest import create_auth_headers

ENDPOINT_AI_MODELS = "/api/v1/platform-service/tenants/{tenant_id}/ai-models"
ENDPOINT_AI_MODEL_DETAIL = "/api/v1/platform-service/tenants/{tenant_id}/ai-models/{model_id}"

NON_EXISTENT_ID = "non-existent-id"


def create_tenant_for_user(test_client: TestClient, user_token: Any, tenant_name: str = "Test Tenant") -> str:
    """Helper function to create a tenant and return its ID."""
    headers = create_auth_headers(user_token, use_cache=False)
    response = test_client.post(
        "/api/v1/platform-service/tenants",
        json={"name": tenant_name, "description": f"Tenant for {user_token.get_id()}"},
        headers=headers,
    )
    assert response.status_code == status.HTTP_201_CREATED
    return response.json()["id"]


def create_ai_model(
    test_client: TestClient,
    tenant_id: str,
    headers: dict,
    model_name: str = "Test Model",
    provider: str = "AZURE_OPENAI",
    model_type: str = "LLM_MODEL",
) -> dict:
    """Helper function to create an AI model and return its data."""
    config = {
        "endpoint": "https://test.openai.azure.com/",
        "deployment_name": "gpt-4o",
        "api_version": "2024-02-01",
    }
    if provider != "AZURE_OPENAI":
        config = {"model_name": "gpt-4"}

    model_data = {
        "name": model_name,
        "description": f"AI model {model_name}",
        "type": model_type,
        "provider": provider,
        "purpose_groups": ["CONVERSATION_TITLE_GENERATION"],
        "config": config,
        "priority": 0,
        "is_active": False,
    }
    response = test_client.post(
        ENDPOINT_AI_MODELS.format(tenant_id=tenant_id),
        json=model_data,
        headers=headers,
    )
    assert response.status_code == status.HTTP_201_CREATED
    return response.json()


class TestTenantAIModelRoutes:
    """Test suite for tenant AI model API routes."""

    def test_create_ai_model_success(
        self,
        test_client: TestClient,
        test_user_token: Any,
    ) -> None:
        """Test successful AI model creation."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        model_data = {
            "name": "GPT-4o Azure",
            "description": "Azure OpenAI GPT-4o deployment",
            "type": "LLM_MODEL",
            "provider": "AZURE_OPENAI",
            "purpose_groups": ["CONVERSATION_TITLE_GENERATION", "TRACE_ANALYSIS"],
            "config": {
                "endpoint": "https://my-endpoint.openai.azure.com/",
                "deployment_name": "gpt-4o",
                "api_version": "2024-02-01",
            },
            "priority": 0,
            "is_active": False,
        }

        response = test_client.post(
            ENDPOINT_AI_MODELS.format(tenant_id=tenant_id),
            json=model_data,
            headers=headers,
        )

        if response.status_code != status.HTTP_201_CREATED:
            print(f"Response status: {response.status_code}")
            print(f"Response body: {response.json()}")
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()

        assert data["name"] == model_data["name"]
        assert data["description"] == model_data["description"]
        assert data["type"] == model_data["type"]
        assert data["provider"] == model_data["provider"]
        assert not data["is_active"]
        assert data["priority"] == 0
        assert "id" in data
        assert data["tenant_id"] == tenant_id
        assert "created_at" in data
        assert "updated_at" in data
        assert data["created_by"] == test_user_token.get_id()

    def test_create_ai_model_openai_provider(
        self,
        test_client: TestClient,
        test_user_token: Any,
    ) -> None:
        """Test AI model creation with OpenAI provider."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        model_data = {
            "name": "OpenAI GPT-4",
            "type": "LLM_MODEL",
            "provider": "OPENAI",
            "purpose_groups": ["CONVERSATION_TITLE_GENERATION"],
            "config": {
                "model_name": "gpt-4",
            },
            "priority": 1,
            "is_active": True,
        }

        response = test_client.post(
            ENDPOINT_AI_MODELS.format(tenant_id=tenant_id),
            json=model_data,
            headers=headers,
        )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["provider"] == "OPENAI"
        assert data["is_active"]
        assert data["priority"] == 1

    def test_create_ai_model_embedding_type(
        self,
        test_client: TestClient,
        test_user_token: Any,
    ) -> None:
        """Test AI model creation with embedding type."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        model_data = {
            "name": "Embedding Model",
            "type": "EMBEDDING_MODEL",
            "provider": "OPENAI",
            "purpose_groups": [],
            "config": {
                "model_name": "text-embedding-3-large",
            },
        }

        response = test_client.post(
            ENDPOINT_AI_MODELS.format(tenant_id=tenant_id),
            json=model_data,
            headers=headers,
        )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["type"] == "EMBEDDING_MODEL"

    def test_create_ai_model_missing_name(
        self,
        test_client: TestClient,
        test_user_token: Any,
    ) -> None:
        """Test AI model creation with missing name."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        response = test_client.post(
            ENDPOINT_AI_MODELS.format(tenant_id=tenant_id),
            json={
                "type": "LLM_MODEL",
                "provider": "OPENAI",
                "config": {"model_name": "gpt-4"},
            },
            headers=headers,
        )

        assert response.status_code == 422

    def test_create_ai_model_empty_name(
        self,
        test_client: TestClient,
        test_user_token: Any,
    ) -> None:
        """Test AI model creation with empty name."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        response = test_client.post(
            ENDPOINT_AI_MODELS.format(tenant_id=tenant_id),
            json={
                "name": "",
                "type": "LLM_MODEL",
                "provider": "OPENAI",
                "config": {"model_name": "gpt-4"},
            },
            headers=headers,
        )

        assert response.status_code == 422

    def test_create_ai_model_missing_type(
        self,
        test_client: TestClient,
        test_user_token: Any,
    ) -> None:
        """Test AI model creation with missing type."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        response = test_client.post(
            ENDPOINT_AI_MODELS.format(tenant_id=tenant_id),
            json={
                "name": "Test",
                "provider": "OPENAI",
                "config": {"model_name": "gpt-4"},
            },
            headers=headers,
        )

        assert response.status_code == 422

    def test_create_ai_model_invalid_type(
        self,
        test_client: TestClient,
        test_user_token: Any,
    ) -> None:
        """Test AI model creation with invalid type."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        response = test_client.post(
            ENDPOINT_AI_MODELS.format(tenant_id=tenant_id),
            json={
                "name": "Test",
                "type": "INVALID_TYPE",
                "provider": "OPENAI",
                "config": {"model_name": "gpt-4"},
            },
            headers=headers,
        )

        assert response.status_code == 422

    def test_create_ai_model_invalid_provider(
        self,
        test_client: TestClient,
        test_user_token: Any,
    ) -> None:
        """Test AI model creation with invalid provider."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        response = test_client.post(
            ENDPOINT_AI_MODELS.format(tenant_id=tenant_id),
            json={
                "name": "Test",
                "type": "LLM_MODEL",
                "provider": "INVALID_PROVIDER",
                "config": {},
            },
            headers=headers,
        )

        assert response.status_code == 422

    def test_create_ai_model_empty_body(
        self,
        test_client: TestClient,
        test_user_token: Any,
    ) -> None:
        """Test AI model creation with empty JSON body."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        response = test_client.post(
            ENDPOINT_AI_MODELS.format(tenant_id=tenant_id),
            json={},
            headers=headers,
        )

        assert response.status_code == 422

    def test_create_ai_model_without_permission(
        self,
        test_client: TestClient,
    ) -> None:
        """Test that user without tenant membership cannot create AI models."""
        user1_token = test_client.create_test_user("ai-user-1", "User One")
        tenant_id = create_tenant_for_user(test_client, user1_token)

        user2_token = test_client.create_test_user("ai-user-2", "User Two")
        headers2 = create_auth_headers(user2_token, use_cache=False)

        response = test_client.post(
            ENDPOINT_AI_MODELS.format(tenant_id=tenant_id),
            json={
                "name": "Unauthorized Model",
                "type": "LLM_MODEL",
                "provider": "OPENAI",
                "config": {"model_name": "gpt-4"},
            },
            headers=headers2,
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_get_ai_model_success(
        self,
        test_client: TestClient,
        test_user_token: Any,
    ) -> None:
        """Test successful AI model retrieval."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        created = create_ai_model(test_client, tenant_id, headers)
        model_id = created["id"]

        response = test_client.get(
            ENDPOINT_AI_MODEL_DETAIL.format(tenant_id=tenant_id, model_id=model_id),
            headers=headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["id"] == model_id
        assert data["name"] == created["name"]

    def test_get_ai_model_not_found(
        self,
        test_client: TestClient,
        test_user_token: Any,
    ) -> None:
        """Test getting a non-existent AI model."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        response = test_client.get(
            ENDPOINT_AI_MODEL_DETAIL.format(tenant_id=tenant_id, model_id=NON_EXISTENT_ID),
            headers=headers,
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_list_ai_models_empty(
        self,
        test_client: TestClient,
        test_user_token: Any,
    ) -> None:
        """Test listing AI models when none exist."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        response = test_client.get(
            ENDPOINT_AI_MODELS.format(tenant_id=tenant_id),
            headers=headers,
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == []

    def test_list_ai_models_with_results(
        self,
        test_client: TestClient,
        test_user_token: Any,
    ) -> None:
        """Test listing AI models returns created models."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        create_ai_model(test_client, tenant_id, headers, "Model A")
        create_ai_model(test_client, tenant_id, headers, "Model B")

        response = test_client.get(
            ENDPOINT_AI_MODELS.format(tenant_id=tenant_id),
            headers=headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) >= 2

    def test_list_ai_models_filter_by_type(
        self,
        test_client: TestClient,
        test_user_token: Any,
    ) -> None:
        """Test listing AI models with type filter."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        create_ai_model(test_client, tenant_id, headers, "LLM", model_type="LLM_MODEL")
        create_ai_model(
            test_client,
            tenant_id,
            headers,
            "Embed",
            model_type="EMBEDDING_MODEL",
            provider="OPENAI",
        )

        response = test_client.get(
            ENDPOINT_AI_MODELS.format(tenant_id=tenant_id) + "?type=LLM_MODEL",
            headers=headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        for item in data:
            assert item["type"] == "LLM_MODEL"

    def test_list_ai_models_filter_by_provider(
        self,
        test_client: TestClient,
        test_user_token: Any,
    ) -> None:
        """Test listing AI models with provider filter."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        create_ai_model(test_client, tenant_id, headers, "Azure", provider="AZURE_OPENAI")
        create_ai_model(test_client, tenant_id, headers, "OpenAI", provider="OPENAI")

        response = test_client.get(
            ENDPOINT_AI_MODELS.format(tenant_id=tenant_id) + "?provider=AZURE_OPENAI",
            headers=headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        for item in data:
            assert item["provider"] == "AZURE_OPENAI"

    def test_update_ai_model_success(
        self,
        test_client: TestClient,
        test_user_token: Any,
    ) -> None:
        """Test successful AI model update."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        created = create_ai_model(test_client, tenant_id, headers)
        model_id = created["id"]

        response = test_client.patch(
            ENDPOINT_AI_MODEL_DETAIL.format(tenant_id=tenant_id, model_id=model_id),
            json={"name": "Updated Model Name", "is_active": True},
            headers=headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["name"] == "Updated Model Name"
        assert data["is_active"]

    def test_update_ai_model_not_found(
        self,
        test_client: TestClient,
        test_user_token: Any,
    ) -> None:
        """Test updating a non-existent AI model."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        response = test_client.patch(
            ENDPOINT_AI_MODEL_DETAIL.format(tenant_id=tenant_id, model_id=NON_EXISTENT_ID),
            json={"name": "Updated"},
            headers=headers,
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_delete_ai_model_success(
        self,
        test_client: TestClient,
        test_user_token: Any,
    ) -> None:
        """Test successful AI model deletion."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        created = create_ai_model(test_client, tenant_id, headers)
        model_id = created["id"]

        response = test_client.request(
            "DELETE",
            ENDPOINT_AI_MODEL_DETAIL.format(tenant_id=tenant_id, model_id=model_id),
            headers=headers,
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT

        get_response = test_client.get(
            ENDPOINT_AI_MODEL_DETAIL.format(tenant_id=tenant_id, model_id=model_id),
            headers=headers,
        )
        assert get_response.status_code == status.HTTP_404_NOT_FOUND

    def test_delete_ai_model_not_found(
        self,
        test_client: TestClient,
        test_user_token: Any,
    ) -> None:
        """Test deleting a non-existent AI model."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        response = test_client.request(
            "DELETE",
            ENDPOINT_AI_MODEL_DETAIL.format(tenant_id=tenant_id, model_id=NON_EXISTENT_ID),
            headers=headers,
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_update_ai_model_purpose_groups(
        self,
        test_client: TestClient,
        test_user_token: Any,
    ) -> None:
        """Test updating purpose groups on an AI model."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        created = create_ai_model(test_client, tenant_id, headers)
        model_id = created["id"]

        response = test_client.patch(
            ENDPOINT_AI_MODEL_DETAIL.format(tenant_id=tenant_id, model_id=model_id),
            json={"purpose_groups": ["CONVERSATION_TITLE_GENERATION", "TRACE_ANALYSIS", "DESCRIPTION_GENERATION"]},
            headers=headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "CONVERSATION_TITLE_GENERATION" in data["purpose_groups"]
        assert "TRACE_ANALYSIS" in data["purpose_groups"]
        assert "DESCRIPTION_GENERATION" in data["purpose_groups"]

    def test_update_ai_model_priority(
        self,
        test_client: TestClient,
        test_user_token: Any,
    ) -> None:
        """Test updating priority on an AI model."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        created = create_ai_model(test_client, tenant_id, headers)
        model_id = created["id"]

        response = test_client.patch(
            ENDPOINT_AI_MODEL_DETAIL.format(tenant_id=tenant_id, model_id=model_id),
            json={"priority": 5},
            headers=headers,
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["priority"] == 5

    def test_list_ai_models_pagination(
        self,
        test_client: TestClient,
        test_user_token: Any,
    ) -> None:
        """Test listing AI models with pagination."""
        tenant_id = create_tenant_for_user(test_client, test_user_token)
        headers = create_auth_headers(test_user_token, use_cache=False)

        for i in range(5):
            create_ai_model(test_client, tenant_id, headers, f"Model {i}")

        response = test_client.get(
            ENDPOINT_AI_MODELS.format(tenant_id=tenant_id) + "?skip=0&limit=2",
            headers=headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 2
