"""Tests for organization API endpoints."""

from typing import Any
from unittest.mock import patch

import pytest
from fastapi import status
from starlette.testclient import TestClient

from tests.conftest import create_auth_headers
from unifiedui.core.database.enums import OrganizationRoleEnum, PrincipalTypeEnum


@pytest.fixture(autouse=True)
def _disable_system_admin_restriction():
    """Disable system admin restriction for all org tests in this module."""
    with patch("unifiedui.core.config.settings") as mock_settings:
        mock_settings.msal_system_admin_email = None
        mock_settings.ldap_system_admin_username = None
        mock_settings.oidc_zitadel_system_admin_username = None
        yield


# API Endpoints
ENDPOINT_ORGANIZATIONS = "/api/v1/platform-service/organizations"
ENDPOINT_ORGANIZATION_DETAIL = "/api/v1/platform-service/organizations/{organization_id}"
ENDPOINT_ORGANIZATION_PRINCIPALS = "/api/v1/platform-service/organizations/{organization_id}/principals"
ENDPOINT_ORGANIZATION_TENANTS = "/api/v1/platform-service/organizations/{organization_id}/tenants"
ENDPOINT_ORGANIZATION_TENANT_DETAIL = "/api/v1/platform-service/organizations/{organization_id}/tenants/{tenant_id}"

# Common Test IDs
NON_EXISTENT_ID = "non-existent-id"

# Roles
ROLE_ORG_TENANT_GLOBAL_ADMIN = OrganizationRoleEnum.ORGANISATION_GLOBAL_ADMIN.value
ROLE_ORG_TENANT_ADMIN = OrganizationRoleEnum.ORGANISATION_TENANT_ADMIN.value
ROLE_ORG_TENANT_CREATOR = OrganizationRoleEnum.ORGANISATION_TENANT_CREATOR.value

# Principal Types
PRINCIPAL_TYPE_USER = PrincipalTypeEnum.IDENTITY_USER.value
PRINCIPAL_TYPE_GROUP = PrincipalTypeEnum.IDENTITY_GROUP.value


def _create_org_data(
    name: str | None = None,
    slug: str = "test-org",
    description: str | None = "A test organization",
    identity_provider: str = "entra_id",
    identity_tenant_id: str = "idp-tenant-001",
    subscription_tier: str = "free",
) -> dict[str, Any]:
    """Helper to create organization request data."""
    data: dict[str, Any] = {
        "name": name if name is not None else f"Org {slug}",
        "slug": slug,
        "identity_provider": identity_provider,
        "identity_tenant_id": identity_tenant_id,
        "subscription_tier": subscription_tier,
    }
    if description is not None:
        data["description"] = description
    return data


def _create_org(test_client: TestClient, headers: dict[str, str], **kwargs: Any) -> dict[str, Any]:
    """Helper to create an organization and return its response data."""
    org_data = _create_org_data(**kwargs)
    response = test_client.post(ENDPOINT_ORGANIZATIONS, json=org_data, headers=headers)
    assert response.status_code == status.HTTP_201_CREATED
    return response.json()


class TestOrganizationRoutes:
    """Test suite for organization CRUD API routes."""

    def test_create_organization_success(self, test_client: TestClient) -> None:
        """Test successful organization creation."""
        user_token = test_client.create_test_user("org-creator-1", "Org Creator")
        headers = create_auth_headers(user_token, use_cache=False)

        org_data = _create_org_data()
        response = test_client.post(ENDPOINT_ORGANIZATIONS, json=org_data, headers=headers)

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()

        assert data["name"] == org_data["name"]
        assert data["slug"] == org_data["slug"]
        assert data["description"] == org_data["description"]
        assert data["identity_provider"] == org_data["identity_provider"]
        assert data["identity_tenant_id"] == org_data["identity_tenant_id"]
        assert data["subscription_tier"] == org_data["subscription_tier"]
        assert data["is_active"] is True
        assert "id" in data
        assert "created_at" in data
        assert "updated_at" in data
        assert data["created_by"] == "org-creator-1"

    def test_create_organization_creates_default_tenant(self, test_client: TestClient) -> None:
        """Test that creating an organization also creates a default tenant."""
        user_token = test_client.create_test_user("org-creator-2", "Org Creator 2")
        headers = create_auth_headers(user_token, use_cache=False)

        org = _create_org(test_client, headers, identity_tenant_id="idp-tenant-002", slug="test-org-2")
        org_id = org["id"]

        # List tenants in org
        response = test_client.get(ENDPOINT_ORGANIZATION_TENANTS.format(organization_id=org_id), headers=headers)
        assert response.status_code == status.HTTP_200_OK
        tenants = response.json()

        assert len(tenants) == 1
        default_tenant = tenants[0]
        assert default_tenant["name"] == "Default"
        assert default_tenant["is_default"] is True
        assert default_tenant["can_be_deleted"] is False
        assert default_tenant["organization_id"] == org_id
        assert default_tenant["environment_type"] == "SANDBOX"

    def test_create_organization_assigns_global_admin_role(self, test_client: TestClient) -> None:
        """Test that creator is assigned ORGANISATION_GLOBAL_ADMIN role."""
        user_token = test_client.create_test_user("org-creator-3", "Org Creator 3")
        headers = create_auth_headers(user_token, use_cache=False)

        org = _create_org(test_client, headers, identity_tenant_id="idp-tenant-003", slug="test-org-3")
        org_id = org["id"]

        # List principals
        response = test_client.get(ENDPOINT_ORGANIZATION_PRINCIPALS.format(organization_id=org_id), headers=headers)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["organization_id"] == org_id
        assert len(data["principals"]) >= 1

        creator_principal = next((m for m in data["principals"] if m["principal_id"] == "org-creator-3"), None)
        assert creator_principal is not None
        role_values = [r["role"] for r in creator_principal["roles"]]
        assert ROLE_ORG_TENANT_GLOBAL_ADMIN in role_values

    def test_create_organization_missing_name(self, test_client: TestClient) -> None:
        """Test organization creation with missing name."""
        user_token = test_client.create_test_user("org-val-1", "Org Val 1")
        headers = create_auth_headers(user_token, use_cache=False)

        data = {"slug": "test-slug", "identity_provider": "entra_id", "identity_tenant_id": "t1"}
        response = test_client.post(ENDPOINT_ORGANIZATIONS, json=data, headers=headers)
        assert response.status_code == 422

    def test_create_organization_missing_slug(self, test_client: TestClient) -> None:
        """Test organization creation with missing slug."""
        user_token = test_client.create_test_user("org-val-2", "Org Val 2")
        headers = create_auth_headers(user_token, use_cache=False)

        data = {"name": "Test Org", "identity_provider": "entra_id", "identity_tenant_id": "t1"}
        response = test_client.post(ENDPOINT_ORGANIZATIONS, json=data, headers=headers)
        assert response.status_code == 422

    def test_create_organization_missing_identity_provider(self, test_client: TestClient) -> None:
        """Test organization creation with missing identity_provider."""
        user_token = test_client.create_test_user("org-val-3", "Org Val 3")
        headers = create_auth_headers(user_token, use_cache=False)

        data = {"name": "Test Org", "slug": "test-slug", "identity_tenant_id": "t1"}
        response = test_client.post(ENDPOINT_ORGANIZATIONS, json=data, headers=headers)
        assert response.status_code == 422

    def test_create_organization_missing_identity_tenant_id(self, test_client: TestClient) -> None:
        """Test organization creation with missing identity_tenant_id."""
        user_token = test_client.create_test_user("org-val-4", "Org Val 4")
        headers = create_auth_headers(user_token, use_cache=False)

        data = {"name": "Test Org", "slug": "test-slug", "identity_provider": "entra_id"}
        response = test_client.post(ENDPOINT_ORGANIZATIONS, json=data, headers=headers)
        assert response.status_code == 422

    def test_create_organization_empty_body(self, test_client: TestClient) -> None:
        """Test organization creation with empty body."""
        user_token = test_client.create_test_user("org-val-5", "Org Val 5")
        headers = create_auth_headers(user_token, use_cache=False)

        response = test_client.post(ENDPOINT_ORGANIZATIONS, json={}, headers=headers)
        assert response.status_code == 422

    def test_create_organization_empty_name(self, test_client: TestClient) -> None:
        """Test organization creation with empty name."""
        user_token = test_client.create_test_user("org-val-6", "Org Val 6")
        headers = create_auth_headers(user_token, use_cache=False)

        data = _create_org_data(name="")
        response = test_client.post(ENDPOINT_ORGANIZATIONS, json=data, headers=headers)
        assert response.status_code == 422

    def test_create_organization_duplicate_identity_tenant(self, test_client: TestClient) -> None:
        """Test that creating two organizations with the same identity_tenant_id fails."""
        user_token = test_client.create_test_user("org-dup-1", "Org Dup 1")
        headers = create_auth_headers(user_token, use_cache=False)

        _create_org(test_client, headers, identity_tenant_id="dup-idp-tenant", slug="org-dup-a")

        # Second creation with same identity_tenant_id should fail
        org_data2 = _create_org_data(name="Second Org", slug="org-dup-b", identity_tenant_id="dup-idp-tenant")
        response = test_client.post(ENDPOINT_ORGANIZATIONS, json=org_data2, headers=headers)
        assert response.status_code == status.HTTP_409_CONFLICT

    def test_create_organization_duplicate_slug(self, test_client: TestClient) -> None:
        """Test that creating two organizations with the same slug fails."""
        user_token = test_client.create_test_user("org-slug-1", "Org Slug 1")
        headers = create_auth_headers(user_token, use_cache=False)

        _create_org(test_client, headers, identity_tenant_id="idp-slug-a", slug="same-slug")

        org_data2 = _create_org_data(name="Second Org", slug="same-slug", identity_tenant_id="idp-slug-b")
        response = test_client.post(ENDPOINT_ORGANIZATIONS, json=org_data2, headers=headers)
        assert response.status_code == status.HTTP_409_CONFLICT

    def test_get_organization_success(self, test_client: TestClient) -> None:
        """Test successful organization retrieval."""
        user_token = test_client.create_test_user("org-get-1", "Org Get 1")
        headers = create_auth_headers(user_token, use_cache=False)

        org = _create_org(test_client, headers, identity_tenant_id="idp-get-1", slug="get-org-1")
        org_id = org["id"]

        response = test_client.get(ENDPOINT_ORGANIZATION_DETAIL.format(organization_id=org_id), headers=headers)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["id"] == org_id
        assert data["name"] == "Org get-org-1"
        assert data["slug"] == "get-org-1"

    def test_get_organization_not_found(self, test_client: TestClient) -> None:
        """Test organization retrieval with non-existent ID returns 403 (user not a member)."""
        user_token = test_client.create_test_user("org-get-nf", "Org Get NF")
        headers = create_auth_headers(user_token, use_cache=False)

        response = test_client.get(
            ENDPOINT_ORGANIZATION_DETAIL.format(organization_id=NON_EXISTENT_ID), headers=headers
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_update_organization_success(self, test_client: TestClient) -> None:
        """Test successful organization update."""
        user_token = test_client.create_test_user("org-upd-1", "Org Upd 1")
        headers = create_auth_headers(user_token, use_cache=False)

        org = _create_org(test_client, headers, identity_tenant_id="idp-upd-1", slug="upd-org-1")
        org_id = org["id"]

        update_data = {"name": "Updated Org Name", "description": "Updated description"}
        response = test_client.patch(
            ENDPOINT_ORGANIZATION_DETAIL.format(organization_id=org_id),
            json=update_data,
            headers=headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["name"] == "Updated Org Name"
        assert data["description"] == "Updated description"
        assert data["updated_by"] == "org-upd-1"

    def test_update_organization_partial(self, test_client: TestClient) -> None:
        """Test partial organization update (only name)."""
        user_token = test_client.create_test_user("org-upd-p", "Org Upd P")
        headers = create_auth_headers(user_token, use_cache=False)

        org = _create_org(
            test_client, headers, identity_tenant_id="idp-upd-p", slug="upd-org-p", description="Original description"
        )
        org_id = org["id"]

        response = test_client.patch(
            ENDPOINT_ORGANIZATION_DETAIL.format(organization_id=org_id),
            json={"name": "Only Name Updated"},
            headers=headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["name"] == "Only Name Updated"
        assert data["description"] == "Original description"

    def test_update_organization_subscription_tier(self, test_client: TestClient) -> None:
        """Test updating subscription tier."""
        user_token = test_client.create_test_user("org-upd-tier", "Org Upd Tier")
        headers = create_auth_headers(user_token, use_cache=False)

        org = _create_org(test_client, headers, identity_tenant_id="idp-upd-tier", slug="upd-org-tier")
        org_id = org["id"]

        response = test_client.patch(
            ENDPOINT_ORGANIZATION_DETAIL.format(organization_id=org_id),
            json={"subscription_tier": "enterprise"},
            headers=headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["subscription_tier"] == "enterprise"

    def test_update_organization_deactivate(self, test_client: TestClient) -> None:
        """Test deactivating an organization."""
        user_token = test_client.create_test_user("org-upd-deact", "Org Upd Deact")
        headers = create_auth_headers(user_token, use_cache=False)

        org = _create_org(test_client, headers, identity_tenant_id="idp-upd-deact", slug="upd-org-deact")
        org_id = org["id"]

        response = test_client.patch(
            ENDPOINT_ORGANIZATION_DETAIL.format(organization_id=org_id),
            json={"is_active": False},
            headers=headers,
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["is_active"] is False

    def test_update_organization_not_found(self, test_client: TestClient) -> None:
        """Test updating a non-existent organization returns 403 (RBAC before handler)."""
        user_token = test_client.create_test_user("org-upd-nf", "Org Upd NF")
        headers = create_auth_headers(user_token, use_cache=False)

        response = test_client.patch(
            ENDPOINT_ORGANIZATION_DETAIL.format(organization_id=NON_EXISTENT_ID),
            json={"name": "Should Fail"},
            headers=headers,
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN


class TestOrganizationPrincipalRoutes:
    """Test suite for organization principal management routes."""

    def test_list_principals_success(self, test_client: TestClient) -> None:
        """Test listing organization principals after creation."""
        user_token = test_client.create_test_user("org-prin-list-1", "Org Prin List")
        headers = create_auth_headers(user_token, use_cache=False)

        org = _create_org(test_client, headers, identity_tenant_id="idp-mem-list-1", slug="mem-list-org")
        org_id = org["id"]

        response = test_client.get(ENDPOINT_ORGANIZATION_PRINCIPALS.format(organization_id=org_id), headers=headers)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["organization_id"] == org_id
        assert len(data["principals"]) >= 1

    def test_list_principals_not_found_org(self, test_client: TestClient) -> None:
        """Test listing members of a non-existent organization returns 403 (RBAC before handler)."""
        user_token = test_client.create_test_user("org-prin-nf", "Org Prin NF")
        headers = create_auth_headers(user_token, use_cache=False)

        response = test_client.get(
            ENDPOINT_ORGANIZATION_PRINCIPALS.format(organization_id=NON_EXISTENT_ID), headers=headers
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_set_principal_success(self, test_client: TestClient) -> None:
        """Test adding a principal to the organization."""
        user_token = test_client.create_test_user("org-prin-set-1", "Org Prin Set")
        headers = create_auth_headers(user_token, use_cache=False)

        org = _create_org(test_client, headers, identity_tenant_id="idp-mem-set-1", slug="mem-set-org")
        org_id = org["id"]

        principal_data = {
            "principal_id": "new-member-1",
            "principal_type": PRINCIPAL_TYPE_USER,
            "role": ROLE_ORG_TENANT_CREATOR,
        }
        response = test_client.post(
            ENDPOINT_ORGANIZATION_PRINCIPALS.format(organization_id=org_id),
            json=principal_data,
            headers=headers,
        )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["principal_id"] == "new-member-1"
        assert data["principal_type"] == PRINCIPAL_TYPE_USER
        assert data["role"] == ROLE_ORG_TENANT_CREATOR
        assert "id" in data
        assert "created_at" in data

    def test_set_principal_multiple_roles(self, test_client: TestClient) -> None:
        """Test adding multiple roles to the same member."""
        user_token = test_client.create_test_user("org-prin-multi-1", "Org Prin Multi")
        headers = create_auth_headers(user_token, use_cache=False)

        org = _create_org(test_client, headers, identity_tenant_id="idp-mem-multi-1", slug="mem-multi-org")
        org_id = org["id"]

        # Add TENANT_ADMIN role
        test_client.post(
            ENDPOINT_ORGANIZATION_PRINCIPALS.format(organization_id=org_id),
            json={"principal_id": "multi-user", "principal_type": PRINCIPAL_TYPE_USER, "role": ROLE_ORG_TENANT_ADMIN},
            headers=headers,
        )

        # Add TENANT_CREATOR role
        response = test_client.post(
            ENDPOINT_ORGANIZATION_PRINCIPALS.format(organization_id=org_id),
            json={"principal_id": "multi-user", "principal_type": PRINCIPAL_TYPE_USER, "role": ROLE_ORG_TENANT_CREATOR},
            headers=headers,
        )
        assert response.status_code == status.HTTP_201_CREATED

        # List principals and verify both roles
        list_response = test_client.get(
            ENDPOINT_ORGANIZATION_PRINCIPALS.format(organization_id=org_id), headers=headers
        )
        members = list_response.json()["principals"]
        multi_principal = next((m for m in members if m["principal_id"] == "multi-user"), None)
        assert multi_principal is not None
        role_values = [r["role"] for r in multi_principal["roles"]]
        assert ROLE_ORG_TENANT_ADMIN in role_values
        assert ROLE_ORG_TENANT_CREATOR in role_values

    def test_set_principal_duplicate_role(self, test_client: TestClient) -> None:
        """Test adding the same role twice to the same member fails."""
        user_token = test_client.create_test_user("org-prin-dup-1", "Org Prin Dup")
        headers = create_auth_headers(user_token, use_cache=False)

        org = _create_org(test_client, headers, identity_tenant_id="idp-mem-dup-1", slug="mem-dup-org")
        org_id = org["id"]

        principal_data = {
            "principal_id": "dup-member",
            "principal_type": PRINCIPAL_TYPE_USER,
            "role": ROLE_ORG_TENANT_CREATOR,
        }

        # First add succeeds
        resp1 = test_client.post(
            ENDPOINT_ORGANIZATION_PRINCIPALS.format(organization_id=org_id),
            json=principal_data,
            headers=headers,
        )
        assert resp1.status_code == status.HTTP_201_CREATED

        # Second add fails
        resp2 = test_client.post(
            ENDPOINT_ORGANIZATION_PRINCIPALS.format(organization_id=org_id),
            json=principal_data,
            headers=headers,
        )
        assert resp2.status_code == status.HTTP_409_CONFLICT

    def test_set_principal_invalid_role(self, test_client: TestClient) -> None:
        """Test adding a principal with an invalid role."""
        user_token = test_client.create_test_user("org-prin-ir-1", "Org Prin IR")
        headers = create_auth_headers(user_token, use_cache=False)

        org = _create_org(test_client, headers, identity_tenant_id="idp-mem-ir-1", slug="mem-ir-org")
        org_id = org["id"]

        principal_data = {
            "principal_id": "inv-member",
            "principal_type": PRINCIPAL_TYPE_USER,
            "role": "INVALID_ROLE",
        }
        response = test_client.post(
            ENDPOINT_ORGANIZATION_PRINCIPALS.format(organization_id=org_id),
            json=principal_data,
            headers=headers,
        )
        assert response.status_code == 422

    def test_set_principal_invalid_principal_type(self, test_client: TestClient) -> None:
        """Test adding a principal with an invalid principal type."""
        user_token = test_client.create_test_user("org-prin-ipt-1", "Org Prin IPT")
        headers = create_auth_headers(user_token, use_cache=False)

        org = _create_org(test_client, headers, identity_tenant_id="idp-mem-ipt-1", slug="mem-ipt-org")
        org_id = org["id"]

        principal_data = {
            "principal_id": "inv-member",
            "principal_type": "INVALID_TYPE",
            "role": ROLE_ORG_TENANT_CREATOR,
        }
        response = test_client.post(
            ENDPOINT_ORGANIZATION_PRINCIPALS.format(organization_id=org_id),
            json=principal_data,
            headers=headers,
        )
        assert response.status_code == 422

    def test_set_principal_missing_fields(self, test_client: TestClient) -> None:
        """Test adding a principal with missing required fields."""
        user_token = test_client.create_test_user("org-prin-mf-1", "Org Prin MF")
        headers = create_auth_headers(user_token, use_cache=False)

        org = _create_org(test_client, headers, identity_tenant_id="idp-mem-mf-1", slug="mem-mf-org")
        org_id = org["id"]

        # Missing principal_id
        resp1 = test_client.post(
            ENDPOINT_ORGANIZATION_PRINCIPALS.format(organization_id=org_id),
            json={"principal_type": PRINCIPAL_TYPE_USER, "role": ROLE_ORG_TENANT_CREATOR},
            headers=headers,
        )
        assert resp1.status_code == 422

        # Missing role
        resp2 = test_client.post(
            ENDPOINT_ORGANIZATION_PRINCIPALS.format(organization_id=org_id),
            json={"principal_id": "some-user", "principal_type": PRINCIPAL_TYPE_USER},
            headers=headers,
        )
        assert resp2.status_code == 422

        # Missing principal_type
        resp3 = test_client.post(
            ENDPOINT_ORGANIZATION_PRINCIPALS.format(organization_id=org_id),
            json={"principal_id": "some-user", "role": ROLE_ORG_TENANT_CREATOR},
            headers=headers,
        )
        assert resp3.status_code == 422

        # Empty body
        resp4 = test_client.post(
            ENDPOINT_ORGANIZATION_PRINCIPALS.format(organization_id=org_id),
            json={},
            headers=headers,
        )
        assert resp4.status_code == 422

    def test_set_principal_org_not_found(self, test_client: TestClient) -> None:
        """Test adding a principal to a non-existent organization."""
        user_token = test_client.create_test_user("org-prin-onf-1", "Org Prin ONF")
        headers = create_auth_headers(user_token, use_cache=False)

        principal_data = {
            "principal_id": "some-user",
            "principal_type": PRINCIPAL_TYPE_USER,
            "role": ROLE_ORG_TENANT_CREATOR,
        }
        response = test_client.post(
            ENDPOINT_ORGANIZATION_PRINCIPALS.format(organization_id=NON_EXISTENT_ID),
            json=principal_data,
            headers=headers,
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_set_principal_group_principal(self, test_client: TestClient) -> None:
        """Test adding a group principal as org principal."""
        user_token = test_client.create_test_user("org-prin-grp-1", "Org Prin Grp")
        headers = create_auth_headers(user_token, use_cache=False)

        org = _create_org(test_client, headers, identity_tenant_id="idp-mem-grp-1", slug="mem-grp-org")
        org_id = org["id"]

        principal_data = {
            "principal_id": "group-001",
            "principal_type": PRINCIPAL_TYPE_GROUP,
            "role": ROLE_ORG_TENANT_CREATOR,
        }
        response = test_client.post(
            ENDPOINT_ORGANIZATION_PRINCIPALS.format(organization_id=org_id),
            json=principal_data,
            headers=headers,
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.json()["principal_type"] == PRINCIPAL_TYPE_GROUP

    def test_delete_principal_success(self, test_client: TestClient) -> None:
        """Test removing a principal role from the organization."""
        user_token = test_client.create_test_user("org-prin-del-1", "Org Prin Del")
        headers = create_auth_headers(user_token, use_cache=False)

        org = _create_org(test_client, headers, identity_tenant_id="idp-mem-del-1", slug="mem-del-org")
        org_id = org["id"]

        # Add a principal
        test_client.post(
            ENDPOINT_ORGANIZATION_PRINCIPALS.format(organization_id=org_id),
            json={"principal_id": "del-user", "principal_type": PRINCIPAL_TYPE_USER, "role": ROLE_ORG_TENANT_CREATOR},
            headers=headers,
        )

        # Delete the principal role
        delete_data = {
            "principal_id": "del-user",
            "principal_type": PRINCIPAL_TYPE_USER,
            "role": ROLE_ORG_TENANT_CREATOR,
        }
        response = test_client.request(
            "DELETE",
            ENDPOINT_ORGANIZATION_PRINCIPALS.format(organization_id=org_id),
            json=delete_data,
            headers=headers,
        )
        assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_delete_principal_not_found(self, test_client: TestClient) -> None:
        """Test removing a non-existent principal role."""
        user_token = test_client.create_test_user("org-prin-dnf-1", "Org Prin DNF")
        headers = create_auth_headers(user_token, use_cache=False)

        org = _create_org(test_client, headers, identity_tenant_id="idp-mem-dnf-1", slug="mem-dnf-org")
        org_id = org["id"]

        delete_data = {
            "principal_id": "non-existent-user",
            "principal_type": PRINCIPAL_TYPE_USER,
            "role": ROLE_ORG_TENANT_CREATOR,
        }
        response = test_client.request(
            "DELETE",
            ENDPOINT_ORGANIZATION_PRINCIPALS.format(organization_id=org_id),
            json=delete_data,
            headers=headers,
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_delete_principal_missing_fields(self, test_client: TestClient) -> None:
        """Test deleting a principal with missing required fields."""
        user_token = test_client.create_test_user("org-prin-dmf-1", "Org Prin DMF")
        headers = create_auth_headers(user_token, use_cache=False)

        org = _create_org(test_client, headers, identity_tenant_id="idp-mem-dmf-1", slug="mem-dmf-org")
        org_id = org["id"]

        # Missing principal_id
        resp = test_client.request(
            "DELETE",
            ENDPOINT_ORGANIZATION_PRINCIPALS.format(organization_id=org_id),
            json={"principal_type": PRINCIPAL_TYPE_USER, "role": ROLE_ORG_TENANT_CREATOR},
            headers=headers,
        )
        assert resp.status_code == 422

    def test_delete_principal_org_not_found(self, test_client: TestClient) -> None:
        """Test deleting a principal from a non-existent organization."""
        user_token = test_client.create_test_user("org-prin-donf-1", "Org Prin DONF")
        headers = create_auth_headers(user_token, use_cache=False)

        delete_data = {
            "principal_id": "some-user",
            "principal_type": PRINCIPAL_TYPE_USER,
            "role": ROLE_ORG_TENANT_CREATOR,
        }
        response = test_client.request(
            "DELETE",
            ENDPOINT_ORGANIZATION_PRINCIPALS.format(organization_id=NON_EXISTENT_ID),
            json=delete_data,
            headers=headers,
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN


class TestOrganizationTenantRoutes:
    """Test suite for organization tenant management routes."""

    def test_list_tenants_success(self, test_client: TestClient) -> None:
        """Test listing tenants in an organization (includes default)."""
        user_token = test_client.create_test_user("org-ten-list-1", "Org Ten List")
        headers = create_auth_headers(user_token, use_cache=False)

        org = _create_org(test_client, headers, identity_tenant_id="idp-ten-list-1", slug="ten-list-org")
        org_id = org["id"]

        response = test_client.get(ENDPOINT_ORGANIZATION_TENANTS.format(organization_id=org_id), headers=headers)
        assert response.status_code == status.HTTP_200_OK
        tenants = response.json()
        assert len(tenants) == 1  # default tenant

    def test_list_tenants_org_not_found(self, test_client: TestClient) -> None:
        """Test listing tenants of a non-existent organization returns 403 (RBAC before handler)."""
        user_token = test_client.create_test_user("org-ten-nf-1", "Org Ten NF")
        headers = create_auth_headers(user_token, use_cache=False)

        response = test_client.get(
            ENDPOINT_ORGANIZATION_TENANTS.format(organization_id=NON_EXISTENT_ID), headers=headers
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_create_tenant_success(self, test_client: TestClient) -> None:
        """Test creating a new tenant in the organization."""
        user_token = test_client.create_test_user("org-ten-cr-1", "Org Ten Cr")
        headers = create_auth_headers(user_token, use_cache=False)

        org = _create_org(test_client, headers, identity_tenant_id="idp-ten-cr-1", slug="ten-cr-org")
        org_id = org["id"]

        tenant_data = {
            "name": "Development",
            "description": "Dev environment",
            "environment_type": "SANDBOX",
        }
        response = test_client.post(
            ENDPOINT_ORGANIZATION_TENANTS.format(organization_id=org_id),
            json=tenant_data,
            headers=headers,
        )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["name"] == "Development"
        assert data["description"] == "Dev environment"
        assert data["organization_id"] == org_id
        assert data["environment_type"] == "SANDBOX"
        assert data["is_default"] is False
        assert data["can_be_deleted"] is True
        assert "id" in data

    def test_create_tenant_production_type(self, test_client: TestClient) -> None:
        """Test creating a PRODUCTION environment tenant."""
        user_token = test_client.create_test_user("org-ten-prod-1", "Org Ten Prod")
        headers = create_auth_headers(user_token, use_cache=False)

        org = _create_org(test_client, headers, identity_tenant_id="idp-ten-prod-1", slug="ten-prod-org")
        org_id = org["id"]

        tenant_data = {
            "name": "Production",
            "description": "Production environment",
            "environment_type": "PRODUCTION",
        }
        response = test_client.post(
            ENDPOINT_ORGANIZATION_TENANTS.format(organization_id=org_id),
            json=tenant_data,
            headers=headers,
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.json()["environment_type"] == "PRODUCTION"

    def test_create_tenant_with_previous_stage(self, test_client: TestClient) -> None:
        """Test creating a tenant with a previous stage reference."""
        user_token = test_client.create_test_user("org-ten-stage-1", "Org Ten Stage")
        headers = create_auth_headers(user_token, use_cache=False)

        org = _create_org(
            test_client,
            headers,
            identity_tenant_id="idp-ten-stage-1",
            slug="ten-stage-org",
        )
        org_id = org["id"]

        # Create dev tenant
        dev_resp = test_client.post(
            ENDPOINT_ORGANIZATION_TENANTS.format(organization_id=org_id),
            json={"name": "Dev", "environment_type": "SANDBOX"},
            headers=headers,
        )
        dev_id = dev_resp.json()["id"]

        # Create staging tenant referencing dev
        staging_resp = test_client.post(
            ENDPOINT_ORGANIZATION_TENANTS.format(organization_id=org_id),
            json={"name": "Staging", "environment_type": "SANDBOX", "previous_stage_id": dev_id},
            headers=headers,
        )
        assert staging_resp.status_code == status.HTTP_201_CREATED
        assert staging_resp.json()["previous_stage_id"] == dev_id

    def test_create_tenant_invalid_environment_type(self, test_client: TestClient) -> None:
        """Test creating a tenant with invalid environment type."""
        user_token = test_client.create_test_user("org-ten-iet-1", "Org Ten IET")
        headers = create_auth_headers(user_token, use_cache=False)

        org = _create_org(test_client, headers, identity_tenant_id="idp-ten-iet-1", slug="ten-iet-org")
        org_id = org["id"]

        tenant_data = {"name": "Invalid Env", "environment_type": "INVALID"}
        response = test_client.post(
            ENDPOINT_ORGANIZATION_TENANTS.format(organization_id=org_id),
            json=tenant_data,
            headers=headers,
        )
        assert response.status_code == 422

    def test_create_tenant_missing_name(self, test_client: TestClient) -> None:
        """Test creating a tenant without a name."""
        user_token = test_client.create_test_user("org-ten-mn-1", "Org Ten MN")
        headers = create_auth_headers(user_token, use_cache=False)

        org = _create_org(test_client, headers, identity_tenant_id="idp-ten-mn-1", slug="ten-mn-org")
        org_id = org["id"]

        response = test_client.post(
            ENDPOINT_ORGANIZATION_TENANTS.format(organization_id=org_id),
            json={"environment_type": "SANDBOX"},
            headers=headers,
        )
        assert response.status_code == 422

    def test_create_tenant_org_not_found(self, test_client: TestClient) -> None:
        """Test creating a tenant in a non-existent organization returns 403 (RBAC before handler)."""
        user_token = test_client.create_test_user("org-ten-cnf-1", "Org Ten CNF")
        headers = create_auth_headers(user_token, use_cache=False)

        tenant_data = {"name": "Test Tenant", "environment_type": "SANDBOX"}
        response = test_client.post(
            ENDPOINT_ORGANIZATION_TENANTS.format(organization_id=NON_EXISTENT_ID),
            json=tenant_data,
            headers=headers,
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_delete_tenant_success(self, test_client: TestClient) -> None:
        """Test deleting a non-default tenant from the organization."""
        user_token = test_client.create_test_user("org-ten-del-1", "Org Ten Del")
        headers = create_auth_headers(user_token, use_cache=False)

        org = _create_org(test_client, headers, identity_tenant_id="idp-ten-del-1", slug="ten-del-org")
        org_id = org["id"]

        # Create a deletable tenant
        create_resp = test_client.post(
            ENDPOINT_ORGANIZATION_TENANTS.format(organization_id=org_id),
            json={"name": "To Delete", "environment_type": "SANDBOX"},
            headers=headers,
        )
        tenant_id = create_resp.json()["id"]

        # Delete it
        response = test_client.request(
            "DELETE",
            ENDPOINT_ORGANIZATION_TENANT_DETAIL.format(organization_id=org_id, tenant_id=tenant_id),
            headers=headers,
        )
        assert response.status_code == status.HTTP_204_NO_CONTENT

        # Verify it's gone
        list_resp = test_client.get(ENDPOINT_ORGANIZATION_TENANTS.format(organization_id=org_id), headers=headers)
        tenant_ids = [t["id"] for t in list_resp.json()]
        assert tenant_id not in tenant_ids

    def test_delete_default_tenant_fails(self, test_client: TestClient) -> None:
        """Test that deleting the default tenant fails (can_be_deleted=false)."""
        user_token = test_client.create_test_user("org-ten-ddf-1", "Org Ten DDF")
        headers = create_auth_headers(user_token, use_cache=False)

        org = _create_org(test_client, headers, identity_tenant_id="idp-ten-ddf-1", slug="ten-ddf-org")
        org_id = org["id"]

        # Get the default tenant ID
        list_resp = test_client.get(ENDPOINT_ORGANIZATION_TENANTS.format(organization_id=org_id), headers=headers)
        default_tenant = next(t for t in list_resp.json() if t["is_default"] is True)
        default_tenant_id = default_tenant["id"]

        # Try to delete default tenant
        response = test_client.request(
            "DELETE",
            ENDPOINT_ORGANIZATION_TENANT_DETAIL.format(organization_id=org_id, tenant_id=default_tenant_id),
            headers=headers,
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_delete_tenant_not_found(self, test_client: TestClient) -> None:
        """Test deleting a non-existent tenant from the organization."""
        user_token = test_client.create_test_user("org-ten-tnf-1", "Org Ten TNF")
        headers = create_auth_headers(user_token, use_cache=False)

        org = _create_org(test_client, headers, identity_tenant_id="idp-ten-tnf-1", slug="ten-tnf-org")
        org_id = org["id"]

        response = test_client.request(
            "DELETE",
            ENDPOINT_ORGANIZATION_TENANT_DETAIL.format(organization_id=org_id, tenant_id=NON_EXISTENT_ID),
            headers=headers,
        )
        # 403 because auth middleware checks tenant_id access before handler runs
        assert response.status_code in [status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND]

    def test_delete_tenant_org_not_found(self, test_client: TestClient) -> None:
        """Test deleting a tenant from a non-existent organization."""
        user_token = test_client.create_test_user("org-ten-donf-1", "Org Ten DONF")
        headers = create_auth_headers(user_token, use_cache=False)

        response = test_client.request(
            "DELETE",
            ENDPOINT_ORGANIZATION_TENANT_DETAIL.format(organization_id=NON_EXISTENT_ID, tenant_id="some-tenant-id"),
            headers=headers,
        )
        # 403 because auth middleware checks tenant_id access before handler runs
        assert response.status_code in [status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND]

    def test_create_multiple_tenants(self, test_client: TestClient) -> None:
        """Test creating multiple tenants in an organization."""
        user_token = test_client.create_test_user("org-ten-multi-1", "Org Ten Multi")
        headers = create_auth_headers(user_token, use_cache=False)

        org = _create_org(
            test_client,
            headers,
            identity_tenant_id="idp-ten-multi-1",
            slug="ten-multi-org",
        )
        org_id = org["id"]

        # Create 3 additional tenants
        for i in range(3):
            resp = test_client.post(
                ENDPOINT_ORGANIZATION_TENANTS.format(organization_id=org_id),
                json={"name": f"Tenant {i}", "environment_type": "SANDBOX"},
                headers=headers,
            )
            assert resp.status_code == status.HTTP_201_CREATED

        # List should show 4 (1 default + 3 new)
        list_resp = test_client.get(ENDPOINT_ORGANIZATION_TENANTS.format(organization_id=org_id), headers=headers)
        assert len(list_resp.json()) == 4
