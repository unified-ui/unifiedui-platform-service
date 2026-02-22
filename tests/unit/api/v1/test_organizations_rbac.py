"""Tests for organization RBAC (Role-Based Access Control)."""

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

# Common Test IDs
NON_EXISTENT_ID = "non-existent-id"

# Organization Roles
ROLE_ORG_GLOBAL_ADMIN = OrganizationRoleEnum.ORGANISATION_GLOBAL_ADMIN.value
ROLE_ORG_ADMIN = OrganizationRoleEnum.ORGANISATION_ADMIN.value
ROLE_ORG_TENANT_ADMIN = OrganizationRoleEnum.ORGANISATION_TENANT_ADMIN.value
ROLE_ORG_TENANT_CREATOR = OrganizationRoleEnum.ORGANISATION_TENANT_CREATOR.value
ROLE_ORG_MEMBER = OrganizationRoleEnum.ORGANISATION_MEMBER.value

# Principal Types
PRINCIPAL_TYPE_USER = PrincipalTypeEnum.IDENTITY_USER.value
PRINCIPAL_TYPE_GROUP = PrincipalTypeEnum.IDENTITY_GROUP.value


def _create_org_data(
    name: str = "RBAC Org",
    slug: str = "rbac-org",
    identity_provider: str = "entra_id",
    identity_tenant_id: str = "rbac-idp-001",
    **kwargs: Any,
) -> dict[str, Any]:
    """Helper to create organization request data."""
    data: dict[str, Any] = {
        "name": name,
        "slug": slug,
        "identity_provider": identity_provider,
        "identity_tenant_id": identity_tenant_id,
        "subscription_tier": kwargs.get("subscription_tier", "free"),
    }
    if "description" in kwargs:
        data["description"] = kwargs["description"]
    return data


def _create_org(test_client: TestClient, headers: dict[str, str], **kwargs: Any) -> dict[str, Any]:
    """Helper to create an organization and return its response data."""
    org_data = _create_org_data(**kwargs)
    response = test_client.post(ENDPOINT_ORGANIZATIONS, json=org_data, headers=headers)
    assert response.status_code == status.HTTP_201_CREATED
    return response.json()


class TestOrganizationRBAC:
    """Test suite for organization role-based access control."""

    def test_unauthenticated_cannot_create_org(self, test_client: TestClient) -> None:
        """Test that unauthenticated users cannot create an organization."""
        org_data = _create_org_data(identity_tenant_id="unauth-create")
        response = test_client.post(ENDPOINT_ORGANIZATIONS, json=org_data)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_unauthenticated_cannot_get_org(self, test_client: TestClient) -> None:
        """Test that unauthenticated users cannot get an organization."""
        response = test_client.get(ENDPOINT_ORGANIZATION_DETAIL.format(organization_id="some-org-id"))
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_unauthenticated_cannot_update_org(self, test_client: TestClient) -> None:
        """Test that unauthenticated users cannot update an organization."""
        response = test_client.patch(
            ENDPOINT_ORGANIZATION_DETAIL.format(organization_id="some-org-id"),
            json={"name": "Hacked"},
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_unauthenticated_cannot_list_members(self, test_client: TestClient) -> None:
        """Test that unauthenticated users cannot list org members."""
        response = test_client.get(ENDPOINT_ORGANIZATION_MEMBERS.format(organization_id="some-org-id"))
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_unauthenticated_cannot_set_member(self, test_client: TestClient) -> None:
        """Test that unauthenticated users cannot add org members."""
        response = test_client.post(
            ENDPOINT_ORGANIZATION_MEMBERS.format(organization_id="some-org-id"),
            json={
                "principal_id": "hacker",
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_ORG_GLOBAL_ADMIN,
            },
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_unauthenticated_cannot_delete_member(self, test_client: TestClient) -> None:
        """Test that unauthenticated users cannot delete org members."""
        response = test_client.request(
            "DELETE",
            ENDPOINT_ORGANIZATION_MEMBERS.format(organization_id="some-org-id"),
            json={
                "principal_id": "someone",
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_ORG_MEMBER,
            },
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_unauthenticated_cannot_list_tenants(self, test_client: TestClient) -> None:
        """Test that unauthenticated users cannot list org tenants."""
        response = test_client.get(ENDPOINT_ORGANIZATION_TENANTS.format(organization_id="some-org-id"))
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_unauthenticated_cannot_create_tenant(self, test_client: TestClient) -> None:
        """Test that unauthenticated users cannot create org tenants."""
        response = test_client.post(
            ENDPOINT_ORGANIZATION_TENANTS.format(organization_id="some-org-id"),
            json={"name": "Hacker Tenant", "environment_type": "SANDBOX"},
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_unauthenticated_cannot_delete_tenant(self, test_client: TestClient) -> None:
        """Test that unauthenticated users cannot delete org tenants."""
        response = test_client.request(
            "DELETE",
            ENDPOINT_ORGANIZATION_TENANT_DETAIL.format(organization_id="some-org-id", tenant_id="some-tenant"),
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_creator_becomes_org_global_admin(self, test_client: TestClient) -> None:
        """Test that organization creator gets ORGANISATION_GLOBAL_ADMIN role."""
        user_token = test_client.create_test_user("rbac-creator-1", "RBAC Creator")
        headers = create_auth_headers(user_token, use_cache=False)

        org = _create_org(test_client, headers, identity_tenant_id="rbac-idp-creator")

        # Verify creator has GLOBAL_ADMIN
        members_resp = test_client.get(ENDPOINT_ORGANIZATION_MEMBERS.format(organization_id=org["id"]), headers=headers)
        assert members_resp.status_code == status.HTTP_200_OK

        members = members_resp.json()["members"]
        creator = next((m for m in members if m["principal_id"] == "rbac-creator-1"), None)
        assert creator is not None
        roles = [r["role"] for r in creator["roles"]]
        assert ROLE_ORG_GLOBAL_ADMIN in roles

    def test_creator_gets_global_admin_on_default_tenant(self, test_client: TestClient) -> None:
        """Test that org creator gets GLOBAL_ADMIN on the auto-created default tenant."""
        user_token = test_client.create_test_user("rbac-def-tenant-1", "RBAC Def Tenant")
        headers = create_auth_headers(user_token, use_cache=False)

        org = _create_org(test_client, headers, identity_tenant_id="rbac-idp-def-tenant", slug="rbac-def-tenant")

        # Get default tenant
        tenants_resp = test_client.get(ENDPOINT_ORGANIZATION_TENANTS.format(organization_id=org["id"]), headers=headers)
        default_tenant = tenants_resp.json()[0]

        # The user should be able to access the default tenant via normal tenant routes
        # since they were assigned GLOBAL_ADMIN on it
        tenant_detail_resp = test_client.get(
            f"/api/v1/platform-service/tenants/{default_tenant['id']}", headers=headers
        )
        assert tenant_detail_resp.status_code == status.HTTP_200_OK

    def test_all_org_roles_can_be_assigned(self, test_client: TestClient) -> None:
        """Test that all 5 organization roles can be assigned."""
        user_token = test_client.create_test_user("rbac-allroles-1", "RBAC AllRoles")
        headers = create_auth_headers(user_token, use_cache=False)

        org = _create_org(test_client, headers, identity_tenant_id="rbac-idp-allroles", slug="rbac-allroles")
        org_id = org["id"]

        all_roles = [ROLE_ORG_ADMIN, ROLE_ORG_TENANT_ADMIN, ROLE_ORG_TENANT_CREATOR, ROLE_ORG_MEMBER]
        for i, role in enumerate(all_roles):
            resp = test_client.post(
                ENDPOINT_ORGANIZATION_MEMBERS.format(organization_id=org_id),
                json={
                    "principal_id": f"role-user-{i}",
                    "principal_type": PRINCIPAL_TYPE_USER,
                    "role": role,
                },
                headers=headers,
            )
            assert resp.status_code == status.HTTP_201_CREATED
            assert resp.json()["role"] == role

    def test_invalid_token_is_rejected(self, test_client: TestClient) -> None:
        """Test that requests with invalid tokens are rejected."""
        headers = {"Authorization": "Bearer invalid-token-here"}

        response = test_client.get(
            ENDPOINT_ORGANIZATION_DETAIL.format(organization_id="some-org-id"),
            headers=headers,
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_different_users_can_create_separate_orgs(self, test_client: TestClient) -> None:
        """Test that different users can each create their own organizations."""
        user1_token = test_client.create_test_user("rbac-user-1", "RBAC User 1")
        headers1 = create_auth_headers(user1_token, use_cache=False)

        user2_token = test_client.create_test_user("rbac-user-2", "RBAC User 2")
        headers2 = create_auth_headers(user2_token, use_cache=False)

        # User 1 creates org
        org1 = _create_org(
            test_client,
            headers1,
            name="User1 Org",
            slug="user1-org",
            identity_tenant_id="rbac-idp-u1",
        )
        assert org1["created_by"] == "rbac-user-1"

        # User 2 creates org
        org2 = _create_org(
            test_client,
            headers2,
            name="User2 Org",
            slug="user2-org",
            identity_tenant_id="rbac-idp-u2",
        )
        assert org2["created_by"] == "rbac-user-2"

        assert org1["id"] != org2["id"]

    def test_authenticated_user_can_access_all_org_endpoints(self, test_client: TestClient) -> None:
        """Test that any authenticated user can access org CRUD endpoints they own."""
        user_token = test_client.create_test_user("rbac-access-1", "RBAC Access")
        headers = create_auth_headers(user_token, use_cache=False)

        # Create org
        org = _create_org(test_client, headers, identity_tenant_id="rbac-idp-access", slug="rbac-access")
        org_id = org["id"]

        # Get org
        resp_get = test_client.get(ENDPOINT_ORGANIZATION_DETAIL.format(organization_id=org_id), headers=headers)
        assert resp_get.status_code == status.HTTP_200_OK

        # Update org
        resp_upd = test_client.patch(
            ENDPOINT_ORGANIZATION_DETAIL.format(organization_id=org_id),
            json={"name": "Updated"},
            headers=headers,
        )
        assert resp_upd.status_code == status.HTTP_200_OK

        # List members
        resp_mem = test_client.get(ENDPOINT_ORGANIZATION_MEMBERS.format(organization_id=org_id), headers=headers)
        assert resp_mem.status_code == status.HTTP_200_OK

        # Set member
        resp_set = test_client.post(
            ENDPOINT_ORGANIZATION_MEMBERS.format(organization_id=org_id),
            json={"principal_id": "new-user", "principal_type": PRINCIPAL_TYPE_USER, "role": ROLE_ORG_MEMBER},
            headers=headers,
        )
        assert resp_set.status_code == status.HTTP_201_CREATED

        # Delete member
        resp_del = test_client.request(
            "DELETE",
            ENDPOINT_ORGANIZATION_MEMBERS.format(organization_id=org_id),
            json={"principal_id": "new-user", "principal_type": PRINCIPAL_TYPE_USER, "role": ROLE_ORG_MEMBER},
            headers=headers,
        )
        assert resp_del.status_code == status.HTTP_204_NO_CONTENT

        # List tenants
        resp_ten = test_client.get(ENDPOINT_ORGANIZATION_TENANTS.format(organization_id=org_id), headers=headers)
        assert resp_ten.status_code == status.HTTP_200_OK

        # Create tenant
        resp_ct = test_client.post(
            ENDPOINT_ORGANIZATION_TENANTS.format(organization_id=org_id),
            json={"name": "New Tenant", "environment_type": "SANDBOX"},
            headers=headers,
        )
        assert resp_ct.status_code == status.HTTP_201_CREATED
        new_tenant_id = resp_ct.json()["id"]

        # Delete tenant
        resp_dt = test_client.request(
            "DELETE",
            ENDPOINT_ORGANIZATION_TENANT_DETAIL.format(organization_id=org_id, tenant_id=new_tenant_id),
            headers=headers,
        )
        assert resp_dt.status_code == status.HTTP_204_NO_CONTENT

    def test_member_role_assignment_and_removal_flow(self, test_client: TestClient) -> None:
        """Test the full flow of adding and removing org member roles."""
        admin_token = test_client.create_test_user("rbac-admin-flow", "RBAC Admin Flow")
        admin_headers = create_auth_headers(admin_token, use_cache=False)

        org = _create_org(
            test_client,
            admin_headers,
            identity_tenant_id="rbac-idp-flow",
            slug="rbac-flow",
        )
        org_id = org["id"]

        # Assign MEMBER role to new user
        set_resp = test_client.post(
            ENDPOINT_ORGANIZATION_MEMBERS.format(organization_id=org_id),
            json={"principal_id": "flow-user", "principal_type": PRINCIPAL_TYPE_USER, "role": ROLE_ORG_MEMBER},
            headers=admin_headers,
        )
        assert set_resp.status_code == status.HTTP_201_CREATED

        # Assign additional TENANT_CREATOR role
        set2_resp = test_client.post(
            ENDPOINT_ORGANIZATION_MEMBERS.format(organization_id=org_id),
            json={
                "principal_id": "flow-user",
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_ORG_TENANT_CREATOR,
            },
            headers=admin_headers,
        )
        assert set2_resp.status_code == status.HTTP_201_CREATED

        # Verify both roles exist
        members_resp = test_client.get(
            ENDPOINT_ORGANIZATION_MEMBERS.format(organization_id=org_id), headers=admin_headers
        )
        flow_member = next((m for m in members_resp.json()["members"] if m["principal_id"] == "flow-user"), None)
        assert flow_member is not None
        roles = [r["role"] for r in flow_member["roles"]]
        assert ROLE_ORG_MEMBER in roles
        assert ROLE_ORG_TENANT_CREATOR in roles

        # Remove MEMBER role
        del_resp = test_client.request(
            "DELETE",
            ENDPOINT_ORGANIZATION_MEMBERS.format(organization_id=org_id),
            json={"principal_id": "flow-user", "principal_type": PRINCIPAL_TYPE_USER, "role": ROLE_ORG_MEMBER},
            headers=admin_headers,
        )
        assert del_resp.status_code == status.HTTP_204_NO_CONTENT

        # Verify only TENANT_CREATOR remains
        members_resp2 = test_client.get(
            ENDPOINT_ORGANIZATION_MEMBERS.format(organization_id=org_id), headers=admin_headers
        )
        flow_member2 = next((m for m in members_resp2.json()["members"] if m["principal_id"] == "flow-user"), None)
        assert flow_member2 is not None
        roles2 = [r["role"] for r in flow_member2["roles"]]
        assert ROLE_ORG_MEMBER not in roles2
        assert ROLE_ORG_TENANT_CREATOR in roles2

    def test_default_tenant_cannot_be_deleted(self, test_client: TestClient) -> None:
        """Test that the default tenant cant be deleted (RBAC/business rule)."""
        user_token = test_client.create_test_user("rbac-no-del-def", "RBAC No Del Def")
        headers = create_auth_headers(user_token, use_cache=False)

        org = _create_org(
            test_client,
            headers,
            identity_tenant_id="rbac-idp-nodeldef",
            slug="rbac-nodeldef",
        )
        org_id = org["id"]

        tenants_resp = test_client.get(ENDPOINT_ORGANIZATION_TENANTS.format(organization_id=org_id), headers=headers)
        default_tenant = next(t for t in tenants_resp.json() if t["is_default"])

        response = test_client.request(
            "DELETE",
            ENDPOINT_ORGANIZATION_TENANT_DETAIL.format(organization_id=org_id, tenant_id=default_tenant["id"]),
            headers=headers,
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_non_default_tenant_can_be_deleted(self, test_client: TestClient) -> None:
        """Test that a non-default tenant CAN be deleted."""
        user_token = test_client.create_test_user("rbac-del-ok", "RBAC Del OK")
        headers = create_auth_headers(user_token, use_cache=False)

        org = _create_org(
            test_client,
            headers,
            identity_tenant_id="rbac-idp-delok",
            slug="rbac-delok",
        )
        org_id = org["id"]

        create_resp = test_client.post(
            ENDPOINT_ORGANIZATION_TENANTS.format(organization_id=org_id),
            json={"name": "Deletable", "environment_type": "SANDBOX"},
            headers=headers,
        )
        tenant_id = create_resp.json()["id"]

        response = test_client.request(
            "DELETE",
            ENDPOINT_ORGANIZATION_TENANT_DETAIL.format(organization_id=org_id, tenant_id=tenant_id),
            headers=headers,
        )
        assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_group_as_org_member(self, test_client: TestClient) -> None:
        """Test that identity groups can be added as org members."""
        user_token = test_client.create_test_user("rbac-grp-1", "RBAC Grp")
        headers = create_auth_headers(user_token, use_cache=False)

        org = _create_org(
            test_client,
            headers,
            identity_tenant_id="rbac-idp-grp",
            slug="rbac-grp",
        )
        org_id = org["id"]

        # Add group as MEMBER
        resp = test_client.post(
            ENDPOINT_ORGANIZATION_MEMBERS.format(organization_id=org_id),
            json={
                "principal_id": "group-rbac-001",
                "principal_type": PRINCIPAL_TYPE_GROUP,
                "role": ROLE_ORG_ADMIN,
            },
            headers=headers,
        )
        assert resp.status_code == status.HTTP_201_CREATED
        assert resp.json()["principal_type"] == PRINCIPAL_TYPE_GROUP
        assert resp.json()["role"] == ROLE_ORG_ADMIN
