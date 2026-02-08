"""Tests for tenant AI models RBAC (Role-Based Access Control)."""
from typing import Any
from fastapi import status
from starlette.testclient import TestClient

from unifiedui.core.database.enums import PrincipalTypeEnum
from tests.conftest import create_auth_headers


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


class TestTenantAIModelRBAC:
    """Test suite for tenant AI model role-based access control."""

    def test_global_admin_can_create(self, test_client: TestClient) -> None:
        """Test that GLOBAL_ADMIN (tenant creator) can create AI models."""
        user_token = test_client.create_test_user("rbac-admin-1", "Admin User")
        headers = create_auth_headers(user_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, user_token)

        response = test_client.post(
            ENDPOINT_AI_MODELS.format(tenant_id=tenant_id),
            json={
                "name": "Admin Model",
                "type": "LLM_MODEL",
                "provider": "OPENAI",
                "config": {"model_name": "gpt-4"},
            },
            headers=headers,
        )

        assert response.status_code == status.HTTP_201_CREATED

    def test_ai_models_admin_can_create(self, test_client: TestClient) -> None:
        """Test that TENANT_AI_MODELS_ADMIN can create AI models."""
        admin_token = test_client.create_test_user("rbac-admin-2", "Tenant Admin")
        admin_headers = create_auth_headers(admin_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, admin_token)

        ai_admin_token = test_client.create_test_user("rbac-ai-admin", "AI Admin")
        add_user_to_tenant(
            test_client, tenant_id, admin_headers,
            "rbac-ai-admin", "TENANT_AI_MODELS_ADMIN",
        )

        ai_admin_headers = create_auth_headers(ai_admin_token, use_cache=False)
        response = test_client.post(
            ENDPOINT_AI_MODELS.format(tenant_id=tenant_id),
            json={
                "name": "AI Admin Model",
                "type": "LLM_MODEL",
                "provider": "OPENAI",
                "config": {"model_name": "gpt-4"},
            },
            headers=ai_admin_headers,
        )

        assert response.status_code == status.HTTP_201_CREATED

    def test_reader_cannot_create(self, test_client: TestClient) -> None:
        """Test that READER cannot create AI models."""
        admin_token = test_client.create_test_user("rbac-admin-3", "Tenant Admin")
        admin_headers = create_auth_headers(admin_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, admin_token)

        reader_token = test_client.create_test_user("rbac-reader-1", "Reader User")
        add_user_to_tenant(test_client, tenant_id, admin_headers, "rbac-reader-1", "READER")

        reader_headers = create_auth_headers(reader_token, use_cache=False)
        response = test_client.post(
            ENDPOINT_AI_MODELS.format(tenant_id=tenant_id),
            json={
                "name": "Reader Model",
                "type": "LLM_MODEL",
                "provider": "OPENAI",
                "config": {"model_name": "gpt-4"},
            },
            headers=reader_headers,
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_reader_can_list(self, test_client: TestClient) -> None:
        """Test that READER can list AI models."""
        admin_token = test_client.create_test_user("rbac-admin-4", "Tenant Admin")
        admin_headers = create_auth_headers(admin_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, admin_token)

        create_ai_model(test_client, tenant_id, admin_headers)

        reader_token = test_client.create_test_user("rbac-reader-2", "Reader User")
        add_user_to_tenant(test_client, tenant_id, admin_headers, "rbac-reader-2", "READER")

        reader_headers = create_auth_headers(reader_token, use_cache=False)
        response = test_client.get(
            ENDPOINT_AI_MODELS.format(tenant_id=tenant_id),
            headers=reader_headers,
        )

        assert response.status_code == status.HTTP_200_OK

    def test_reader_can_get(self, test_client: TestClient) -> None:
        """Test that READER can get a specific AI model."""
        admin_token = test_client.create_test_user("rbac-admin-5", "Tenant Admin")
        admin_headers = create_auth_headers(admin_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, admin_token)

        created = create_ai_model(test_client, tenant_id, admin_headers)
        model_id = created["id"]

        reader_token = test_client.create_test_user("rbac-reader-3", "Reader User")
        add_user_to_tenant(test_client, tenant_id, admin_headers, "rbac-reader-3", "READER")

        reader_headers = create_auth_headers(reader_token, use_cache=False)
        response = test_client.get(
            ENDPOINT_AI_MODEL_DETAIL.format(tenant_id=tenant_id, model_id=model_id),
            headers=reader_headers,
        )

        assert response.status_code == status.HTTP_200_OK

    def test_reader_cannot_update(self, test_client: TestClient) -> None:
        """Test that READER cannot update AI models."""
        admin_token = test_client.create_test_user("rbac-admin-6", "Tenant Admin")
        admin_headers = create_auth_headers(admin_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, admin_token)

        created = create_ai_model(test_client, tenant_id, admin_headers)
        model_id = created["id"]

        reader_token = test_client.create_test_user("rbac-reader-4", "Reader User")
        add_user_to_tenant(test_client, tenant_id, admin_headers, "rbac-reader-4", "READER")

        reader_headers = create_auth_headers(reader_token, use_cache=False)
        response = test_client.patch(
            ENDPOINT_AI_MODEL_DETAIL.format(tenant_id=tenant_id, model_id=model_id),
            json={"name": "Hacked Name"},
            headers=reader_headers,
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_reader_cannot_delete(self, test_client: TestClient) -> None:
        """Test that READER cannot delete AI models."""
        admin_token = test_client.create_test_user("rbac-admin-7", "Tenant Admin")
        admin_headers = create_auth_headers(admin_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, admin_token)

        created = create_ai_model(test_client, tenant_id, admin_headers)
        model_id = created["id"]

        reader_token = test_client.create_test_user("rbac-reader-5", "Reader User")
        add_user_to_tenant(test_client, tenant_id, admin_headers, "rbac-reader-5", "READER")

        reader_headers = create_auth_headers(reader_token, use_cache=False)
        response = test_client.request(
            "DELETE",
            ENDPOINT_AI_MODEL_DETAIL.format(tenant_id=tenant_id, model_id=model_id),
            headers=reader_headers,
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_non_member_cannot_list(self, test_client: TestClient) -> None:
        """Test that non-members cannot list AI models."""
        admin_token = test_client.create_test_user("rbac-admin-8", "Tenant Admin")
        admin_headers = create_auth_headers(admin_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, admin_token)

        outsider_token = test_client.create_test_user("rbac-outsider-1", "Outsider")
        outsider_headers = create_auth_headers(outsider_token, use_cache=False)

        response = test_client.get(
            ENDPOINT_AI_MODELS.format(tenant_id=tenant_id),
            headers=outsider_headers,
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_non_member_cannot_get(self, test_client: TestClient) -> None:
        """Test that non-members cannot get a specific AI model."""
        admin_token = test_client.create_test_user("rbac-admin-9", "Tenant Admin")
        admin_headers = create_auth_headers(admin_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, admin_token)

        created = create_ai_model(test_client, tenant_id, admin_headers)
        model_id = created["id"]

        outsider_token = test_client.create_test_user("rbac-outsider-2", "Outsider")
        outsider_headers = create_auth_headers(outsider_token, use_cache=False)

        response = test_client.get(
            ENDPOINT_AI_MODEL_DETAIL.format(tenant_id=tenant_id, model_id=model_id),
            headers=outsider_headers,
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_ai_models_admin_can_update(self, test_client: TestClient) -> None:
        """Test that TENANT_AI_MODELS_ADMIN can update AI models."""
        admin_token = test_client.create_test_user("rbac-admin-10", "Tenant Admin")
        admin_headers = create_auth_headers(admin_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, admin_token)

        created = create_ai_model(test_client, tenant_id, admin_headers)
        model_id = created["id"]

        ai_admin_token = test_client.create_test_user("rbac-ai-admin-2", "AI Admin 2")
        add_user_to_tenant(
            test_client, tenant_id, admin_headers,
            "rbac-ai-admin-2", "TENANT_AI_MODELS_ADMIN",
        )

        ai_admin_headers = create_auth_headers(ai_admin_token, use_cache=False)
        response = test_client.patch(
            ENDPOINT_AI_MODEL_DETAIL.format(tenant_id=tenant_id, model_id=model_id),
            json={"name": "AI Admin Updated"},
            headers=ai_admin_headers,
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["name"] == "AI Admin Updated"

    def test_ai_models_admin_can_delete(self, test_client: TestClient) -> None:
        """Test that TENANT_AI_MODELS_ADMIN can delete AI models."""
        admin_token = test_client.create_test_user("rbac-admin-11", "Tenant Admin")
        admin_headers = create_auth_headers(admin_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, admin_token)

        created = create_ai_model(test_client, tenant_id, admin_headers)
        model_id = created["id"]

        ai_admin_token = test_client.create_test_user("rbac-ai-admin-3", "AI Admin 3")
        add_user_to_tenant(
            test_client, tenant_id, admin_headers,
            "rbac-ai-admin-3", "TENANT_AI_MODELS_ADMIN",
        )

        ai_admin_headers = create_auth_headers(ai_admin_token, use_cache=False)
        response = test_client.request(
            "DELETE",
            ENDPOINT_AI_MODEL_DETAIL.format(tenant_id=tenant_id, model_id=model_id),
            headers=ai_admin_headers,
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_cross_tenant_isolation(self, test_client: TestClient) -> None:
        """Test that AI models are isolated between tenants."""
        user_a_token = test_client.create_test_user("rbac-cross-a", "User A")
        user_a_headers = create_auth_headers(user_a_token, use_cache=False)
        tenant_a = create_tenant_for_user(test_client, user_a_token, "Tenant A")

        user_b_token = test_client.create_test_user("rbac-cross-b", "User B")
        user_b_headers = create_auth_headers(user_b_token, use_cache=False)
        tenant_b = create_tenant_for_user(test_client, user_b_token, "Tenant B")

        created = create_ai_model(test_client, tenant_a, user_a_headers, "Tenant A Model")
        model_id = created["id"]

        response = test_client.get(
            ENDPOINT_AI_MODEL_DETAIL.format(tenant_id=tenant_b, model_id=model_id),
            headers=user_b_headers,
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
