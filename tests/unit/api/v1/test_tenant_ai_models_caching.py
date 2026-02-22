"""Tests for tenant AI models caching."""

from typing import Any

from fastapi import status
from starlette.testclient import TestClient

from tests.conftest import create_auth_headers
from unifiedui.core.database.enums import PrincipalTypeEnum

ENDPOINT_TENANTS = "/api/v1/platform-service/tenants"
ENDPOINT_AI_MODELS = "/api/v1/platform-service/tenants/{tenant_id}/ai-models"
ENDPOINT_AI_MODEL_DETAIL = "/api/v1/platform-service/tenants/{tenant_id}/ai-models/{model_id}"

PRINCIPAL_TYPE_USER = PrincipalTypeEnum.IDENTITY_USER.value


def create_tenant_for_user(test_client: TestClient, user_token: Any, tenant_name: str = "Test Tenant") -> str:
    """Helper function to create a tenant and return its ID."""
    headers = create_auth_headers(user_token, use_cache=False)
    response = test_client.post(
        ENDPOINT_TENANTS,
        json={"name": tenant_name, "description": f"Tenant for {user_token.get_id()}"},
        headers=headers,
    )
    assert response.status_code == status.HTTP_201_CREATED
    return response.json()["id"]


def add_user_to_tenant(
    test_client: TestClient,
    tenant_id: str,
    admin_headers: dict,
    user_id: str,
    role: str = "READER",
) -> None:
    """Helper function to add a user to a tenant."""
    response = test_client.put(
        f"/api/v1/platform-service/tenants/{tenant_id}/principals",
        json={
            "principal_id": user_id,
            "principal_type": PRINCIPAL_TYPE_USER,
            "role": role,
        },
        headers=admin_headers,
    )
    assert response.status_code == status.HTTP_200_OK


def create_ai_model(
    test_client: TestClient,
    tenant_id: str,
    headers: dict,
    model_name: str = "Test Model",
) -> dict:
    """Helper function to create an AI model and return its data."""
    response = test_client.post(
        ENDPOINT_AI_MODELS.format(tenant_id=tenant_id),
        json={
            "name": model_name,
            "description": f"AI model {model_name}",
            "type": "LLM_MODEL",
            "provider": "AZURE_OPENAI",
            "purpose_groups": ["CONVERSATION_TITLE_GENERATION"],
            "config": {
                "endpoint": "https://test.openai.azure.com/",
                "deployment_name": "gpt-4o",
                "api_version": "2024-02-01",
            },
            "priority": 0,
            "is_active": False,
        },
        headers=headers,
    )
    assert response.status_code == status.HTTP_201_CREATED
    return response.json()


class TestTenantAIModelCaching:
    """Test suite for tenant AI model caching behavior with X-Use-Cache enabled."""

    def test_list_cached_on_second_request(
        self,
        test_client: TestClient,
        fake_redis_client: Any,
    ) -> None:
        """Test that listing AI models uses cache on second request."""
        user_token = test_client.create_test_user("cache-list-1", "Cache List User")
        headers = create_auth_headers(user_token)
        tenant_id = create_tenant_for_user(test_client, user_token)

        create_ai_model(test_client, tenant_id, headers)

        response1 = test_client.get(
            ENDPOINT_AI_MODELS.format(tenant_id=tenant_id),
            headers=headers,
        )
        assert response1.status_code == status.HTTP_200_OK

        response2 = test_client.get(
            ENDPOINT_AI_MODELS.format(tenant_id=tenant_id),
            headers=headers,
        )
        assert response2.status_code == status.HTTP_200_OK
        assert response1.json() == response2.json()

    def test_detail_cached_on_second_request(
        self,
        test_client: TestClient,
        fake_redis_client: Any,
    ) -> None:
        """Test that getting AI model detail uses cache on second request."""
        user_token = test_client.create_test_user("cache-detail-1", "Cache Detail User")
        headers = create_auth_headers(user_token)
        tenant_id = create_tenant_for_user(test_client, user_token)

        created = create_ai_model(test_client, tenant_id, headers)
        model_id = created["id"]

        response1 = test_client.get(
            ENDPOINT_AI_MODEL_DETAIL.format(tenant_id=tenant_id, model_id=model_id),
            headers=headers,
        )
        assert response1.status_code == status.HTTP_200_OK

        response2 = test_client.get(
            ENDPOINT_AI_MODEL_DETAIL.format(tenant_id=tenant_id, model_id=model_id),
            headers=headers,
        )
        assert response2.status_code == status.HTTP_200_OK
        assert response1.json() == response2.json()

    def test_create_invalidates_list_cache(
        self,
        test_client: TestClient,
        fake_redis_client: Any,
    ) -> None:
        """Test that creating a model invalidates the list cache."""
        user_token = test_client.create_test_user("cache-create-1", "Cache Create User")
        headers = create_auth_headers(user_token)
        tenant_id = create_tenant_for_user(test_client, user_token)

        response1 = test_client.get(
            ENDPOINT_AI_MODELS.format(tenant_id=tenant_id),
            headers=headers,
        )
        assert response1.status_code == status.HTTP_200_OK
        initial_count = len(response1.json())

        create_ai_model(test_client, tenant_id, headers)

        response2 = test_client.get(
            ENDPOINT_AI_MODELS.format(tenant_id=tenant_id),
            headers=headers,
        )
        assert response2.status_code == status.HTTP_200_OK
        assert len(response2.json()) == initial_count + 1

    def test_update_invalidates_caches(
        self,
        test_client: TestClient,
        fake_redis_client: Any,
    ) -> None:
        """Test that updating a model invalidates both list and detail caches."""
        user_token = test_client.create_test_user("cache-update-1", "Cache Update User")
        headers = create_auth_headers(user_token)
        tenant_id = create_tenant_for_user(test_client, user_token)

        created = create_ai_model(test_client, tenant_id, headers)
        model_id = created["id"]

        test_client.get(
            ENDPOINT_AI_MODEL_DETAIL.format(tenant_id=tenant_id, model_id=model_id),
            headers=headers,
        )

        test_client.patch(
            ENDPOINT_AI_MODEL_DETAIL.format(tenant_id=tenant_id, model_id=model_id),
            json={"name": "Updated Cached Model"},
            headers=headers,
        )

        response = test_client.get(
            ENDPOINT_AI_MODEL_DETAIL.format(tenant_id=tenant_id, model_id=model_id),
            headers=headers,
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["name"] == "Updated Cached Model"

    def test_delete_invalidates_caches(
        self,
        test_client: TestClient,
        fake_redis_client: Any,
    ) -> None:
        """Test that deleting a model invalidates both list and detail caches."""
        user_token = test_client.create_test_user("cache-delete-1", "Cache Delete User")
        headers = create_auth_headers(user_token)
        tenant_id = create_tenant_for_user(test_client, user_token)

        created = create_ai_model(test_client, tenant_id, headers)
        model_id = created["id"]

        test_client.get(
            ENDPOINT_AI_MODEL_DETAIL.format(tenant_id=tenant_id, model_id=model_id),
            headers=headers,
        )

        test_client.request(
            "DELETE",
            ENDPOINT_AI_MODEL_DETAIL.format(tenant_id=tenant_id, model_id=model_id),
            headers=headers,
        )

        response = test_client.get(
            ENDPOINT_AI_MODEL_DETAIL.format(tenant_id=tenant_id, model_id=model_id),
            headers=headers,
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_cached_permissions_for_reader(
        self,
        test_client: TestClient,
        fake_redis_client: Any,
    ) -> None:
        """Test that cached permissions work correctly for READER."""
        admin_token = test_client.create_test_user("cache-admin-1", "Cache Admin")
        admin_headers = create_auth_headers(admin_token)
        tenant_id = create_tenant_for_user(test_client, admin_token)

        create_ai_model(test_client, tenant_id, admin_headers)

        reader_token = test_client.create_test_user("cache-reader-1", "Cache Reader")
        add_user_to_tenant(test_client, tenant_id, admin_headers, "cache-reader-1", "READER")

        reader_headers = create_auth_headers(reader_token)

        response1 = test_client.get(
            ENDPOINT_AI_MODELS.format(tenant_id=tenant_id),
            headers=reader_headers,
        )
        assert response1.status_code == status.HTTP_200_OK

        response2 = test_client.get(
            ENDPOINT_AI_MODELS.format(tenant_id=tenant_id),
            headers=reader_headers,
        )
        assert response2.status_code == status.HTTP_200_OK

    def test_no_access_with_cache(
        self,
        test_client: TestClient,
        fake_redis_client: Any,
    ) -> None:
        """Test that lack of access is handled correctly with caching."""
        admin_token = test_client.create_test_user("cache-admin-2", "Cache Admin 2")
        create_auth_headers(admin_token)
        tenant_id = create_tenant_for_user(test_client, admin_token)

        outsider_token = test_client.create_test_user("cache-outsider-1", "Cache Outsider")
        outsider_headers = create_auth_headers(outsider_token)

        response1 = test_client.get(
            ENDPOINT_AI_MODELS.format(tenant_id=tenant_id),
            headers=outsider_headers,
        )
        assert response1.status_code == status.HTTP_403_FORBIDDEN

        response2 = test_client.get(
            ENDPOINT_AI_MODELS.format(tenant_id=tenant_id),
            headers=outsider_headers,
        )
        assert response2.status_code == status.HTTP_403_FORBIDDEN
