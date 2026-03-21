"""Tests for external apps RBAC (Role-Based Access Control)."""

from fastapi import status
from starlette.testclient import TestClient

from tests.conftest import create_auth_headers
from tests.helpers.tenant import add_user_to_tenant, create_tenant_for_user
from unifiedui.core.database.enums import PermissionActionEnum, TenantRolesEnum

ENDPOINT_EXTERNAL_APPS = "/api/v1/platform-service/tenants/{tenant_id}/external-apps"
ENDPOINT_EXTERNAL_APP_DETAIL = "/api/v1/platform-service/tenants/{tenant_id}/external-apps/{external_app_id}"
ENDPOINT_EXTERNAL_APP_PRINCIPALS = (
    "/api/v1/platform-service/tenants/{tenant_id}/external-apps/{external_app_id}/principals"
)


def create_external_app(test_client: TestClient, tenant_id: str, headers: dict, name: str = "Test App") -> str:
    """Helper function to create an external app and return its ID."""
    response = test_client.post(
        ENDPOINT_EXTERNAL_APPS.format(tenant_id=tenant_id),
        json={"name": name, "description": f"Description for {name}", "url": "https://example.com"},
        headers=headers,
    )
    assert response.status_code == status.HTTP_201_CREATED
    return response.json()["id"]


class TestExternalAppRBAC:
    """Test suite for external app role-based access control."""

    def test_tenant_global_admin_can_create(self, test_client: TestClient) -> None:
        """Test that TENANT_GLOBAL_ADMIN can create external apps."""
        admin_token = test_client.create_test_user("ea-admin-1", "EA Admin 1")
        headers = create_auth_headers(admin_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, admin_token)

        response = test_client.post(
            ENDPOINT_EXTERNAL_APPS.format(tenant_id=tenant_id),
            json={"name": "Admin App", "url": "https://example.com"},
            headers=headers,
        )
        assert response.status_code == status.HTTP_201_CREATED

    def test_external_apps_admin_can_create(self, test_client: TestClient) -> None:
        """Test that EXTERNAL_APPS_ADMIN can create external apps."""
        owner_token = test_client.create_test_user("ea-owner-1", "EA Owner 1")
        owner_headers = create_auth_headers(owner_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, owner_token)

        user_token = test_client.create_test_user("ea-app-admin", "EA App Admin")
        user_headers = create_auth_headers(user_token, use_cache=False)
        add_user_to_tenant(
            test_client, tenant_id, owner_headers, "ea-app-admin", TenantRolesEnum.EXTERNAL_APPS_ADMIN.value
        )

        response = test_client.post(
            ENDPOINT_EXTERNAL_APPS.format(tenant_id=tenant_id),
            json={"name": "Admin Created App", "url": "https://example.com"},
            headers=user_headers,
        )
        assert response.status_code == status.HTTP_201_CREATED

    def test_external_apps_creator_can_create(self, test_client: TestClient) -> None:
        """Test that EXTERNAL_APPS_CREATOR can create external apps."""
        owner_token = test_client.create_test_user("ea-owner-2", "EA Owner 2")
        owner_headers = create_auth_headers(owner_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, owner_token)

        user_token = test_client.create_test_user("ea-creator", "EA Creator")
        user_headers = create_auth_headers(user_token, use_cache=False)
        add_user_to_tenant(
            test_client, tenant_id, owner_headers, "ea-creator", TenantRolesEnum.EXTERNAL_APPS_CREATOR.value
        )

        response = test_client.post(
            ENDPOINT_EXTERNAL_APPS.format(tenant_id=tenant_id),
            json={"name": "Creator App", "url": "https://example.com"},
            headers=user_headers,
        )
        assert response.status_code == status.HTTP_201_CREATED

    def test_reader_cannot_create(self, test_client: TestClient) -> None:
        """Test that READER cannot create external apps."""
        owner_token = test_client.create_test_user("ea-owner-3", "EA Owner 3")
        owner_headers = create_auth_headers(owner_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, owner_token)

        reader_token = test_client.create_test_user("ea-reader-1", "EA Reader 1")
        reader_headers = create_auth_headers(reader_token, use_cache=False)
        add_user_to_tenant(test_client, tenant_id, owner_headers, "ea-reader-1", TenantRolesEnum.READER.value)

        response = test_client.post(
            ENDPOINT_EXTERNAL_APPS.format(tenant_id=tenant_id),
            json={"name": "Reader App", "url": "https://example.com"},
            headers=reader_headers,
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_reader_can_list(self, test_client: TestClient) -> None:
        """Test that READER with entity permission can list external apps."""
        owner_token = test_client.create_test_user("ea-owner-4", "EA Owner 4")
        owner_headers = create_auth_headers(owner_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, owner_token)

        app_id = create_external_app(test_client, tenant_id, owner_headers)

        reader_token = test_client.create_test_user("ea-reader-2", "EA Reader 2")
        reader_headers = create_auth_headers(reader_token, use_cache=False)
        add_user_to_tenant(test_client, tenant_id, owner_headers, "ea-reader-2", TenantRolesEnum.READER.value)

        test_client.put(
            ENDPOINT_EXTERNAL_APP_PRINCIPALS.format(tenant_id=tenant_id, external_app_id=app_id),
            json={
                "principal_id": "ea-reader-2",
                "principal_type": "IDENTITY_USER",
                "role": PermissionActionEnum.READ.value,
            },
            headers=owner_headers,
        )

        response = test_client.get(ENDPOINT_EXTERNAL_APPS.format(tenant_id=tenant_id), headers=reader_headers)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()) == 1

    def test_reader_can_get(self, test_client: TestClient) -> None:
        """Test that READER with entity permission can get an external app."""
        owner_token = test_client.create_test_user("ea-owner-5", "EA Owner 5")
        owner_headers = create_auth_headers(owner_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, owner_token)

        app_id = create_external_app(test_client, tenant_id, owner_headers)

        reader_token = test_client.create_test_user("ea-reader-3", "EA Reader 3")
        reader_headers = create_auth_headers(reader_token, use_cache=False)
        add_user_to_tenant(test_client, tenant_id, owner_headers, "ea-reader-3", TenantRolesEnum.READER.value)

        test_client.put(
            ENDPOINT_EXTERNAL_APP_PRINCIPALS.format(tenant_id=tenant_id, external_app_id=app_id),
            json={
                "principal_id": "ea-reader-3",
                "principal_type": "IDENTITY_USER",
                "role": PermissionActionEnum.READ.value,
            },
            headers=owner_headers,
        )

        response = test_client.get(
            ENDPOINT_EXTERNAL_APP_DETAIL.format(tenant_id=tenant_id, external_app_id=app_id), headers=reader_headers
        )
        assert response.status_code == status.HTTP_200_OK

    def test_reader_cannot_update(self, test_client: TestClient) -> None:
        """Test that READER cannot update external apps."""
        owner_token = test_client.create_test_user("ea-owner-6", "EA Owner 6")
        owner_headers = create_auth_headers(owner_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, owner_token)

        app_id = create_external_app(test_client, tenant_id, owner_headers)

        reader_token = test_client.create_test_user("ea-reader-4", "EA Reader 4")
        reader_headers = create_auth_headers(reader_token, use_cache=False)
        add_user_to_tenant(test_client, tenant_id, owner_headers, "ea-reader-4", TenantRolesEnum.READER.value)

        response = test_client.patch(
            ENDPOINT_EXTERNAL_APP_DETAIL.format(tenant_id=tenant_id, external_app_id=app_id),
            json={"name": "Hacked"},
            headers=reader_headers,
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_reader_cannot_delete(self, test_client: TestClient) -> None:
        """Test that READER cannot delete external apps."""
        owner_token = test_client.create_test_user("ea-owner-7", "EA Owner 7")
        owner_headers = create_auth_headers(owner_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, owner_token)

        app_id = create_external_app(test_client, tenant_id, owner_headers)

        reader_token = test_client.create_test_user("ea-reader-5", "EA Reader 5")
        reader_headers = create_auth_headers(reader_token, use_cache=False)
        add_user_to_tenant(test_client, tenant_id, owner_headers, "ea-reader-5", TenantRolesEnum.READER.value)

        response = test_client.request(
            "DELETE",
            ENDPOINT_EXTERNAL_APP_DETAIL.format(tenant_id=tenant_id, external_app_id=app_id),
            headers=reader_headers,
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_creator_cannot_update(self, test_client: TestClient) -> None:
        """Test that EXTERNAL_APPS_CREATOR cannot update external apps."""
        owner_token = test_client.create_test_user("ea-owner-8", "EA Owner 8")
        owner_headers = create_auth_headers(owner_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, owner_token)

        app_id = create_external_app(test_client, tenant_id, owner_headers)

        creator_token = test_client.create_test_user("ea-creator-2", "EA Creator 2")
        creator_headers = create_auth_headers(creator_token, use_cache=False)
        add_user_to_tenant(
            test_client, tenant_id, owner_headers, "ea-creator-2", TenantRolesEnum.EXTERNAL_APPS_CREATOR.value
        )

        response = test_client.patch(
            ENDPOINT_EXTERNAL_APP_DETAIL.format(tenant_id=tenant_id, external_app_id=app_id),
            json={"name": "Updated by Creator"},
            headers=creator_headers,
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_creator_cannot_delete(self, test_client: TestClient) -> None:
        """Test that EXTERNAL_APPS_CREATOR cannot delete external apps."""
        owner_token = test_client.create_test_user("ea-owner-9", "EA Owner 9")
        owner_headers = create_auth_headers(owner_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, owner_token)

        app_id = create_external_app(test_client, tenant_id, owner_headers)

        creator_token = test_client.create_test_user("ea-creator-3", "EA Creator 3")
        creator_headers = create_auth_headers(creator_token, use_cache=False)
        add_user_to_tenant(
            test_client, tenant_id, owner_headers, "ea-creator-3", TenantRolesEnum.EXTERNAL_APPS_CREATOR.value
        )

        response = test_client.request(
            "DELETE",
            ENDPOINT_EXTERNAL_APP_DETAIL.format(tenant_id=tenant_id, external_app_id=app_id),
            headers=creator_headers,
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_non_member_cannot_access(self, test_client: TestClient) -> None:
        """Test that non-tenant members cannot access external apps."""
        owner_token = test_client.create_test_user("ea-owner-10", "EA Owner 10")
        owner_headers = create_auth_headers(owner_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, owner_token)

        create_external_app(test_client, tenant_id, owner_headers)

        outsider_token = test_client.create_test_user("ea-outsider", "EA Outsider")
        outsider_headers = create_auth_headers(outsider_token, use_cache=False)

        response = test_client.get(ENDPOINT_EXTERNAL_APPS.format(tenant_id=tenant_id), headers=outsider_headers)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_admin_can_update(self, test_client: TestClient) -> None:
        """Test that EXTERNAL_APPS_ADMIN can update external apps."""
        owner_token = test_client.create_test_user("ea-owner-11", "EA Owner 11")
        owner_headers = create_auth_headers(owner_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, owner_token)

        app_id = create_external_app(test_client, tenant_id, owner_headers)

        admin_token = test_client.create_test_user("ea-admin-2", "EA Admin 2")
        admin_headers = create_auth_headers(admin_token, use_cache=False)
        add_user_to_tenant(
            test_client, tenant_id, owner_headers, "ea-admin-2", TenantRolesEnum.EXTERNAL_APPS_ADMIN.value
        )

        response = test_client.patch(
            ENDPOINT_EXTERNAL_APP_DETAIL.format(tenant_id=tenant_id, external_app_id=app_id),
            json={"name": "Admin Updated"},
            headers=admin_headers,
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["name"] == "Admin Updated"

    def test_admin_can_delete(self, test_client: TestClient) -> None:
        """Test that EXTERNAL_APPS_ADMIN can delete external apps."""
        owner_token = test_client.create_test_user("ea-owner-12", "EA Owner 12")
        owner_headers = create_auth_headers(owner_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, owner_token)

        app_id = create_external_app(test_client, tenant_id, owner_headers)

        admin_token = test_client.create_test_user("ea-admin-3", "EA Admin 3")
        admin_headers = create_auth_headers(admin_token, use_cache=False)
        add_user_to_tenant(
            test_client, tenant_id, owner_headers, "ea-admin-3", TenantRolesEnum.EXTERNAL_APPS_ADMIN.value
        )

        response = test_client.request(
            "DELETE",
            ENDPOINT_EXTERNAL_APP_DETAIL.format(tenant_id=tenant_id, external_app_id=app_id),
            headers=admin_headers,
        )
        assert response.status_code == status.HTTP_204_NO_CONTENT
