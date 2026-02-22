"""Tests for organization caching behavior."""

from typing import Any

from fastapi import status
from starlette.testclient import TestClient
from tests.conftest import create_auth_headers

from unifiedui.core.database.enums import OrganizationRoleEnum, PrincipalTypeEnum

# API Endpoints
ENDPOINT_ORGANIZATIONS = "/api/v1/platform-service/organizations"
ENDPOINT_ORGANIZATION_DETAIL = "/api/v1/platform-service/organizations/{organization_id}"
ENDPOINT_ORGANIZATION_MEMBERS = "/api/v1/platform-service/organizations/{organization_id}/members"
ENDPOINT_ORGANIZATION_TENANTS = "/api/v1/platform-service/organizations/{organization_id}/tenants"
ENDPOINT_ORGANIZATION_TENANT_DETAIL = "/api/v1/platform-service/organizations/{organization_id}/tenants/{tenant_id}"

# Organization Roles
ROLE_ORG_GLOBAL_ADMIN = OrganizationRoleEnum.ORGANISATION_GLOBAL_ADMIN.value
ROLE_ORG_ADMIN = OrganizationRoleEnum.ORGANISATION_ADMIN.value
ROLE_ORG_MEMBER = OrganizationRoleEnum.ORGANISATION_MEMBER.value

# Principal Types
PRINCIPAL_TYPE_USER = PrincipalTypeEnum.IDENTITY_USER.value


def _create_org_data(
    name: str = "Cache Org",
    slug: str = "cache-org",
    identity_provider: str = "entra_id",
    identity_tenant_id: str = "cache-idp-001",
    **kwargs: Any,
) -> dict[str, Any]:
    """Helper to create organization request data."""
    return {
        "name": name,
        "slug": slug,
        "identity_provider": identity_provider,
        "identity_tenant_id": identity_tenant_id,
        "subscription_tier": kwargs.get("subscription_tier", "free"),
    }


def _create_org(test_client: TestClient, headers: dict[str, str], **kwargs: Any) -> dict[str, Any]:
    """Helper to create an organization and return its response data."""
    org_data = _create_org_data(**kwargs)
    response = test_client.post(ENDPOINT_ORGANIZATIONS, json=org_data, headers=headers)
    assert response.status_code == status.HTTP_201_CREATED
    return response.json()


class TestOrganizationCaching:
    """Test suite for organization caching behavior with X-Use-Cache enabled."""

    def test_org_get_cached_correctly(self, test_client: TestClient, fake_redis_client: Any) -> None:
        """Test that organization GET is consistent across multiple calls."""
        user_token = test_client.create_test_user("cache-org-get-1", "Cache Org Get")
        headers = create_auth_headers(user_token)

        org = _create_org(test_client, headers, identity_tenant_id="cache-idp-get-1", slug="cache-get-org")
        org_id = org["id"]

        # First access
        resp1 = test_client.get(ENDPOINT_ORGANIZATION_DETAIL.format(organization_id=org_id), headers=headers)
        assert resp1.status_code == status.HTTP_200_OK

        # Second access (should use cache if applicable)
        resp2 = test_client.get(ENDPOINT_ORGANIZATION_DETAIL.format(organization_id=org_id), headers=headers)
        assert resp2.status_code == status.HTTP_200_OK

        # Both should return same data
        assert resp1.json()["id"] == resp2.json()["id"]
        assert resp1.json()["name"] == resp2.json()["name"]

    def test_org_update_reflected_after_cache(self, test_client: TestClient, fake_redis_client: Any) -> None:
        """Test that updates are reflected even with caching enabled."""
        user_token = test_client.create_test_user("cache-org-upd-1", "Cache Org Upd")
        headers = create_auth_headers(user_token)

        org = _create_org(test_client, headers, identity_tenant_id="cache-idp-upd-1", slug="cache-upd-org")
        org_id = org["id"]

        # Read original
        resp1 = test_client.get(ENDPOINT_ORGANIZATION_DETAIL.format(organization_id=org_id), headers=headers)
        assert resp1.json()["name"] == "Cache Org"

        # Update
        test_client.patch(
            ENDPOINT_ORGANIZATION_DETAIL.format(organization_id=org_id),
            json={"name": "Updated Cache Org"},
            headers=headers,
        )

        # Read updated
        resp2 = test_client.get(ENDPOINT_ORGANIZATION_DETAIL.format(organization_id=org_id), headers=headers)
        assert resp2.status_code == status.HTTP_200_OK
        assert resp2.json()["name"] == "Updated Cache Org"

    def test_member_list_cached_and_reflects_changes(self, test_client: TestClient, fake_redis_client: Any) -> None:
        """Test that member list reflects additions even with caching."""
        user_token = test_client.create_test_user("cache-mem-list-1", "Cache Mem List")
        headers = create_auth_headers(user_token)

        org = _create_org(test_client, headers, identity_tenant_id="cache-idp-memlist", slug="cache-memlist")
        org_id = org["id"]

        # List members (initially just creator)
        resp1 = test_client.get(ENDPOINT_ORGANIZATION_MEMBERS.format(organization_id=org_id), headers=headers)
        assert resp1.status_code == status.HTTP_200_OK
        initial_count = len(resp1.json()["members"])

        # Add a member
        test_client.post(
            ENDPOINT_ORGANIZATION_MEMBERS.format(organization_id=org_id),
            json={"principal_id": "cache-new-user", "principal_type": PRINCIPAL_TYPE_USER, "role": ROLE_ORG_MEMBER},
            headers=headers,
        )

        # List again — should reflect the new member
        resp2 = test_client.get(ENDPOINT_ORGANIZATION_MEMBERS.format(organization_id=org_id), headers=headers)
        assert resp2.status_code == status.HTTP_200_OK
        assert len(resp2.json()["members"]) == initial_count + 1

    def test_member_removal_reflects_in_cached_list(self, test_client: TestClient, fake_redis_client: Any) -> None:
        """Test that member removal is reflected even with caching."""
        user_token = test_client.create_test_user("cache-mem-rem-1", "Cache Mem Rem")
        headers = create_auth_headers(user_token)

        org = _create_org(test_client, headers, identity_tenant_id="cache-idp-memrem", slug="cache-memrem")
        org_id = org["id"]

        # Add a member
        test_client.post(
            ENDPOINT_ORGANIZATION_MEMBERS.format(organization_id=org_id),
            json={"principal_id": "cache-rm-user", "principal_type": PRINCIPAL_TYPE_USER, "role": ROLE_ORG_MEMBER},
            headers=headers,
        )

        # Read member list (caches)
        resp1 = test_client.get(ENDPOINT_ORGANIZATION_MEMBERS.format(organization_id=org_id), headers=headers)
        members_before = resp1.json()["members"]
        assert any(m["principal_id"] == "cache-rm-user" for m in members_before)

        # Remove the member
        test_client.request(
            "DELETE",
            ENDPOINT_ORGANIZATION_MEMBERS.format(organization_id=org_id),
            json={"principal_id": "cache-rm-user", "principal_type": PRINCIPAL_TYPE_USER, "role": ROLE_ORG_MEMBER},
            headers=headers,
        )

        # Read again — removed member should be gone
        resp2 = test_client.get(ENDPOINT_ORGANIZATION_MEMBERS.format(organization_id=org_id), headers=headers)
        members_after = resp2.json()["members"]
        assert not any(m["principal_id"] == "cache-rm-user" for m in members_after)

    def test_tenant_list_cached_and_reflects_creation(self, test_client: TestClient, fake_redis_client: Any) -> None:
        """Test that tenant list reflects new tenant even with caching."""
        user_token = test_client.create_test_user("cache-tenlist-1", "Cache TenList")
        headers = create_auth_headers(user_token)

        org = _create_org(test_client, headers, identity_tenant_id="cache-idp-tenlist", slug="cache-tenlist")
        org_id = org["id"]

        # List tenants (just default)
        resp1 = test_client.get(ENDPOINT_ORGANIZATION_TENANTS.format(organization_id=org_id), headers=headers)
        assert len(resp1.json()) == 1

        # Create new tenant
        test_client.post(
            ENDPOINT_ORGANIZATION_TENANTS.format(organization_id=org_id),
            json={"name": "Cached Tenant", "environment_type": "SANDBOX"},
            headers=headers,
        )

        # List again — should show 2
        resp2 = test_client.get(ENDPOINT_ORGANIZATION_TENANTS.format(organization_id=org_id), headers=headers)
        assert len(resp2.json()) == 2

    def test_tenant_deletion_reflected_in_cached_list(self, test_client: TestClient, fake_redis_client: Any) -> None:
        """Test that tenant deletion is reflected even with caching."""
        user_token = test_client.create_test_user("cache-tendel-1", "Cache TenDel")
        headers = create_auth_headers(user_token)

        org = _create_org(test_client, headers, identity_tenant_id="cache-idp-tendel", slug="cache-tendel")
        org_id = org["id"]

        # Create tenant
        create_resp = test_client.post(
            ENDPOINT_ORGANIZATION_TENANTS.format(organization_id=org_id),
            json={"name": "To Delete Cached", "environment_type": "SANDBOX"},
            headers=headers,
        )
        tenant_id = create_resp.json()["id"]

        # List (caches) — 2 tenants
        resp1 = test_client.get(ENDPOINT_ORGANIZATION_TENANTS.format(organization_id=org_id), headers=headers)
        assert len(resp1.json()) == 2

        # Delete the tenant
        test_client.request(
            "DELETE",
            ENDPOINT_ORGANIZATION_TENANT_DETAIL.format(organization_id=org_id, tenant_id=tenant_id),
            headers=headers,
        )

        # List again — should be back to 1
        resp2 = test_client.get(ENDPOINT_ORGANIZATION_TENANTS.format(organization_id=org_id), headers=headers)
        assert len(resp2.json()) == 1

    def test_cache_isolated_between_organizations(self, test_client: TestClient, fake_redis_client: Any) -> None:
        """Test that caching is isolated between different organizations."""
        user_token = test_client.create_test_user("cache-iso-1", "Cache Iso")
        headers = create_auth_headers(user_token)

        # Create two separate orgs
        org1 = _create_org(
            test_client,
            headers,
            name="Org 1",
            slug="cache-iso-1",
            identity_tenant_id="cache-idp-iso-1",
        )
        org2 = _create_org(
            test_client,
            headers,
            name="Org 2",
            slug="cache-iso-2",
            identity_tenant_id="cache-idp-iso-2",
        )

        # Add member to org1 only
        test_client.post(
            ENDPOINT_ORGANIZATION_MEMBERS.format(organization_id=org1["id"]),
            json={"principal_id": "iso-user", "principal_type": PRINCIPAL_TYPE_USER, "role": ROLE_ORG_MEMBER},
            headers=headers,
        )

        # Org1 members should include iso-user
        resp1 = test_client.get(ENDPOINT_ORGANIZATION_MEMBERS.format(organization_id=org1["id"]), headers=headers)
        assert any(m["principal_id"] == "iso-user" for m in resp1.json()["members"])

        # Org2 members should NOT include iso-user
        resp2 = test_client.get(ENDPOINT_ORGANIZATION_MEMBERS.format(organization_id=org2["id"]), headers=headers)
        assert not any(m["principal_id"] == "iso-user" for m in resp2.json()["members"])

    def test_multiple_operations_with_cache_consistency(self, test_client: TestClient, fake_redis_client: Any) -> None:
        """Test a sequence of operations maintains cache consistency."""
        user_token = test_client.create_test_user("cache-multi-1", "Cache Multi")
        headers = create_auth_headers(user_token)

        org = _create_org(
            test_client,
            headers,
            identity_tenant_id="cache-idp-multi",
            slug="cache-multi",
        )
        org_id = org["id"]

        # 1. Initial state: 1 member, 1 tenant
        mem_resp = test_client.get(ENDPOINT_ORGANIZATION_MEMBERS.format(organization_id=org_id), headers=headers)
        assert len(mem_resp.json()["members"]) == 1

        ten_resp = test_client.get(ENDPOINT_ORGANIZATION_TENANTS.format(organization_id=org_id), headers=headers)
        assert len(ten_resp.json()) == 1

        # 2. Add member
        test_client.post(
            ENDPOINT_ORGANIZATION_MEMBERS.format(organization_id=org_id),
            json={"principal_id": "multi-user-a", "principal_type": PRINCIPAL_TYPE_USER, "role": ROLE_ORG_MEMBER},
            headers=headers,
        )
        mem_resp2 = test_client.get(ENDPOINT_ORGANIZATION_MEMBERS.format(organization_id=org_id), headers=headers)
        assert len(mem_resp2.json()["members"]) == 2

        # 3. Create tenant
        ct_resp = test_client.post(
            ENDPOINT_ORGANIZATION_TENANTS.format(organization_id=org_id),
            json={"name": "Multi Tenant", "environment_type": "SANDBOX"},
            headers=headers,
        )
        new_tenant_id = ct_resp.json()["id"]
        ten_resp2 = test_client.get(ENDPOINT_ORGANIZATION_TENANTS.format(organization_id=org_id), headers=headers)
        assert len(ten_resp2.json()) == 2

        # 4. Update org
        test_client.patch(
            ENDPOINT_ORGANIZATION_DETAIL.format(organization_id=org_id),
            json={"name": "Multi Updated"},
            headers=headers,
        )
        org_resp = test_client.get(ENDPOINT_ORGANIZATION_DETAIL.format(organization_id=org_id), headers=headers)
        assert org_resp.json()["name"] == "Multi Updated"

        # 5. Remove member
        test_client.request(
            "DELETE",
            ENDPOINT_ORGANIZATION_MEMBERS.format(organization_id=org_id),
            json={"principal_id": "multi-user-a", "principal_type": PRINCIPAL_TYPE_USER, "role": ROLE_ORG_MEMBER},
            headers=headers,
        )
        mem_resp3 = test_client.get(ENDPOINT_ORGANIZATION_MEMBERS.format(organization_id=org_id), headers=headers)
        assert len(mem_resp3.json()["members"]) == 1

        # 6. Delete tenant
        test_client.request(
            "DELETE",
            ENDPOINT_ORGANIZATION_TENANT_DETAIL.format(organization_id=org_id, tenant_id=new_tenant_id),
            headers=headers,
        )
        ten_resp3 = test_client.get(ENDPOINT_ORGANIZATION_TENANTS.format(organization_id=org_id), headers=headers)
        assert len(ten_resp3.json()) == 1

    def test_repeated_reads_with_cache_enabled(self, test_client: TestClient, fake_redis_client: Any) -> None:
        """Test that repeated reads with caching return consistent results."""
        user_token = test_client.create_test_user("cache-repeat-1", "Cache Repeat")
        headers = create_auth_headers(user_token)  # use_cache=True by default

        org = _create_org(
            test_client,
            headers,
            identity_tenant_id="cache-idp-repeat",
            slug="cache-repeat",
        )
        org_id = org["id"]

        # Read org 3 times
        for _ in range(3):
            resp = test_client.get(ENDPOINT_ORGANIZATION_DETAIL.format(organization_id=org_id), headers=headers)
            assert resp.status_code == status.HTTP_200_OK
            assert resp.json()["slug"] == "cache-repeat"

        # Read members 3 times
        for _ in range(3):
            resp = test_client.get(ENDPOINT_ORGANIZATION_MEMBERS.format(organization_id=org_id), headers=headers)
            assert resp.status_code == status.HTTP_200_OK

        # Read tenants 3 times
        for _ in range(3):
            resp = test_client.get(ENDPOINT_ORGANIZATION_TENANTS.format(organization_id=org_id), headers=headers)
            assert resp.status_code == status.HTTP_200_OK
            assert len(resp.json()) == 1

    def test_default_tenant_not_deletable_even_with_cache(
        self, test_client: TestClient, fake_redis_client: Any
    ) -> None:
        """Test that default tenant cannot be deleted even when cached."""
        user_token = test_client.create_test_user("cache-nodeldef-1", "Cache NoDelDef")
        headers = create_auth_headers(user_token)

        org = _create_org(
            test_client,
            headers,
            identity_tenant_id="cache-idp-nodeldef",
            slug="cache-nodeldef",
        )
        org_id = org["id"]

        # Get default tenant id (cached)
        tenants_resp = test_client.get(ENDPOINT_ORGANIZATION_TENANTS.format(organization_id=org_id), headers=headers)
        default_tenant_id = tenants_resp.json()[0]["id"]

        # Attempt to delete default
        resp = test_client.request(
            "DELETE",
            ENDPOINT_ORGANIZATION_TENANT_DETAIL.format(organization_id=org_id, tenant_id=default_tenant_id),
            headers=headers,
        )
        assert resp.status_code == status.HTTP_403_FORBIDDEN

        # Default tenant still exists
        tenants_resp2 = test_client.get(ENDPOINT_ORGANIZATION_TENANTS.format(organization_id=org_id), headers=headers)
        assert len(tenants_resp2.json()) == 1
        assert tenants_resp2.json()[0]["id"] == default_tenant_id
