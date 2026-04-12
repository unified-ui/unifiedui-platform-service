"""Tests for organization role bypass on tenant-scoped entities.

Verifies that ORGANISATION_GLOBAL_ADMIN and ORGANISATION_TENANT_ADMIN
bypass ALL tenant-level permission checks (tenant, chat_agent, credential,
workflow, conversation, custom_group, chat_widget, tool,
tag, tenant_ai_model). Also verifies that ORGANISATION_TENANT_CREATOR does NOT
get bypass.
"""

import uuid
from typing import Any
from unittest.mock import patch

from fastapi import status
from starlette.testclient import TestClient

from tests.conftest import create_auth_headers
from tests.fixtures.client import TEST_ORGANIZATION_ID
from unifiedui.core.database.enums import (
    OrganizationRoleEnum,
    PrincipalTypeEnum,
    TenantRolesEnum,
)

ENDPOINT_TENANTS = "/api/v1/platform-service/tenants"
ENDPOINT_TENANT_DETAIL = "/api/v1/platform-service/tenants/{tenant_id}"
ENDPOINT_TENANT_PRINCIPALS = "/api/v1/platform-service/tenants/{tenant_id}/principals"
ENDPOINT_CHAT_AGENTS = "/api/v1/platform-service/tenants/{tenant_id}/chat-agents"
ENDPOINT_CHAT_AGENT_DETAIL = "/api/v1/platform-service/tenants/{tenant_id}/chat-agents/{entity_id}"
ENDPOINT_CREDENTIALS = "/api/v1/platform-service/tenants/{tenant_id}/credentials"
ENDPOINT_CREDENTIAL_DETAIL = "/api/v1/platform-service/tenants/{tenant_id}/credentials/{entity_id}"
ENDPOINT_WORKFLOWS = "/api/v1/platform-service/tenants/{tenant_id}/workflows"
ENDPOINT_AUTONOMOUS_AGENT_DETAIL = "/api/v1/platform-service/tenants/{tenant_id}/workflows/{entity_id}"
ENDPOINT_CONVERSATIONS = "/api/v1/platform-service/tenants/{tenant_id}/conversations"
ENDPOINT_CONVERSATION_DETAIL = "/api/v1/platform-service/tenants/{tenant_id}/conversations/{entity_id}"
ENDPOINT_CUSTOM_GROUPS = "/api/v1/platform-service/tenants/{tenant_id}/custom-groups"
ENDPOINT_CUSTOM_GROUP_DETAIL = "/api/v1/platform-service/tenants/{tenant_id}/custom-groups/{entity_id}"
ENDPOINT_CHAT_WIDGETS = "/api/v1/platform-service/tenants/{tenant_id}/chat-widgets"
ENDPOINT_CHAT_WIDGET_DETAIL = "/api/v1/platform-service/tenants/{tenant_id}/chat-widgets/{entity_id}"
ENDPOINT_TAGS = "/api/v1/platform-service/tenants/{tenant_id}/tags"
ENDPOINT_TENANT_AI_MODELS = "/api/v1/platform-service/tenants/{tenant_id}/ai-models"

ENDPOINT_ORGANIZATIONS = "/api/v1/platform-service/organizations"
ENDPOINT_ORGANIZATION_PRINCIPALS = "/api/v1/platform-service/organizations/{organization_id}/principals"

ROLE_ORG_GLOBAL_ADMIN = OrganizationRoleEnum.ORGANISATION_GLOBAL_ADMIN.value
ROLE_ORG_TENANT_ADMIN = OrganizationRoleEnum.ORGANISATION_TENANT_ADMIN.value
ROLE_ORG_TENANT_CREATOR = OrganizationRoleEnum.ORGANISATION_TENANT_CREATOR.value

PRINCIPAL_TYPE_USER = PrincipalTypeEnum.IDENTITY_USER.value


def _get_admin_headers(test_client: TestClient) -> dict[str, str]:
    """Get auth headers for the seed org's ORGANISATION_GLOBAL_ADMIN (test-user-123)."""
    token = test_client.create_test_user("test-user-123", "Default Admin")
    return create_auth_headers(token, use_cache=False)


def _create_user_with_org_role(
    test_client: TestClient,
    user_slug: str,
    org_role: str,
) -> tuple[Any, dict[str, str]]:
    """Create a new user and assign them a role in the seed organization.

    Returns:
        (token, headers)
    """
    admin_headers = _get_admin_headers(test_client)

    user_id = f"orgbypass-{user_slug}-{uuid.uuid4().hex[:6]}"
    token = test_client.create_test_user(user_id, f"User {user_slug}")
    headers = create_auth_headers(token, use_cache=False)

    resp = test_client.post(
        ENDPOINT_ORGANIZATION_PRINCIPALS.format(organization_id=TEST_ORGANIZATION_ID),
        json={
            "principal_id": user_id,
            "principal_type": PRINCIPAL_TYPE_USER,
            "role": org_role,
        },
        headers=admin_headers,
    )
    assert resp.status_code == status.HTTP_201_CREATED, f"Failed to set org role: {resp.text}"
    return token, headers


def _create_tenant(test_client: TestClient, admin_headers: dict[str, str], name: str = "Bypass Tenant") -> str:
    """Create a tenant via the /tenants endpoint, returning tenant_id."""
    resp = test_client.post(
        ENDPOINT_TENANTS,
        json={"name": name, "description": f"Tenant {name}"},
        headers=admin_headers,
    )
    assert resp.status_code == status.HTTP_201_CREATED
    return resp.json()["id"]


def _create_chat_agent(test_client: TestClient, tenant_id: str, headers: dict[str, str]) -> str:
    """Create a chat agent and return its ID."""
    resp = test_client.post(
        ENDPOINT_CHAT_AGENTS.format(tenant_id=tenant_id),
        json={"name": "Bypass Chat Agent", "description": "Test", "type": "N8N"},
        headers=headers,
    )
    assert resp.status_code == status.HTTP_201_CREATED
    return resp.json()["id"]


def _create_credential(test_client: TestClient, tenant_id: str, headers: dict[str, str]) -> str:
    """Create a credential and return its ID."""
    resp = test_client.post(
        ENDPOINT_CREDENTIALS.format(tenant_id=tenant_id),
        json={
            "name": "Bypass Credential",
            "description": "Test",
            "credential_type": "API_KEY",
            "secret_value": "test-secret-value-12345",
        },
        headers=headers,
    )
    assert resp.status_code == status.HTTP_201_CREATED
    return resp.json()["id"]


@patch("unifiedui.apis.v1.workflows.trigger_workflow_run", return_value=None)
def _create_workflow(mock_trigger: Any, test_client: TestClient, tenant_id: str, headers: dict[str, str]) -> str:
    """Create an autonomous agent and return its ID."""
    resp = test_client.post(
        ENDPOINT_WORKFLOWS.format(tenant_id=tenant_id),
        json={"name": "Bypass Autonomous", "description": "Test", "type": "N8N"},
        headers=headers,
    )
    assert resp.status_code == status.HTTP_201_CREATED
    return resp.json()["id"]


def _create_conversation(
    test_client: TestClient, tenant_id: str, headers: dict[str, str], chat_agent_id: str | None = None
) -> str:
    """Create a conversation and return its ID."""
    if chat_agent_id is None:
        chat_agent_id = _create_chat_agent(test_client, tenant_id, headers)
    resp = test_client.post(
        ENDPOINT_CONVERSATIONS.format(tenant_id=tenant_id),
        json={"name": "Bypass Conversation", "chat_agent_id": chat_agent_id},
        headers=headers,
    )
    assert resp.status_code == status.HTTP_201_CREATED
    return resp.json()["id"]


def _create_custom_group(test_client: TestClient, tenant_id: str, headers: dict[str, str]) -> str:
    """Create a custom group and return its ID."""
    resp = test_client.post(
        ENDPOINT_CUSTOM_GROUPS.format(tenant_id=tenant_id),
        json={"name": "Bypass Group", "description": "Test"},
        headers=headers,
    )
    assert resp.status_code == status.HTTP_201_CREATED
    return resp.json()["id"]


def _create_chat_widget(test_client: TestClient, tenant_id: str, headers: dict[str, str]) -> str:
    """Create a chat widget and return its ID."""
    resp = test_client.post(
        ENDPOINT_CHAT_WIDGETS.format(tenant_id=tenant_id),
        json={
            "name": "Bypass Widget",
            "description": "Test",
            "type": "IFRAME",
            "config": {"url": "https://example.com"},
        },
        headers=headers,
    )
    assert resp.status_code == status.HTTP_201_CREATED
    return resp.json()["id"]


def _create_tag(test_client: TestClient, tenant_id: str, headers: dict[str, str]) -> str:
    """Create a tag and return its ID."""
    resp = test_client.post(
        ENDPOINT_TAGS.format(tenant_id=tenant_id),
        json={"name": f"bypass-tag-{uuid.uuid4().hex[:6]}", "color": "#FF0000"},
        headers=headers,
    )
    assert resp.status_code == status.HTTP_201_CREATED
    return resp.json()["id"]


class TestOrgGlobalAdminBypassOnTenantResources:
    """ORGANISATION_GLOBAL_ADMIN bypasses all tenant-level permission checks.

    The user only has ORGANISATION_GLOBAL_ADMIN in the org — they are NOT
    a tenant member or resource member — yet they can read/write everything.
    """

    @staticmethod
    def _setup(
        test_client: TestClient,
    ) -> tuple[str, dict[str, str], dict[str, str]]:
        """Create a tenant owned by admin, return (tenant_id, admin_headers, bypass_headers).

        Admin creates the tenant and resources.
        Bypass user has only ORGANISATION_GLOBAL_ADMIN — no tenant membership.
        """
        admin_token = test_client.create_test_user(f"orgadm-owner-{uuid.uuid4().hex[:6]}", "Tenant Owner")
        admin_headers = create_auth_headers(admin_token, use_cache=False)
        tenant_id = _create_tenant(test_client, admin_headers)

        _, bypass_headers = _create_user_with_org_role(test_client, "ga-bypass", ROLE_ORG_GLOBAL_ADMIN)
        return tenant_id, admin_headers, bypass_headers

    def test_can_read_tenant(self, test_client: TestClient) -> None:
        """ORGANISATION_GLOBAL_ADMIN can GET a tenant they are not a member of."""
        tenant_id, _, bypass_headers = self._setup(test_client)
        resp = test_client.get(
            ENDPOINT_TENANT_DETAIL.format(tenant_id=tenant_id),
            headers=bypass_headers,
        )
        assert resp.status_code == status.HTTP_200_OK

    def test_can_update_tenant(self, test_client: TestClient) -> None:
        """ORGANISATION_GLOBAL_ADMIN can PATCH a tenant they are not a member of."""
        tenant_id, _, bypass_headers = self._setup(test_client)
        resp = test_client.patch(
            ENDPOINT_TENANT_DETAIL.format(tenant_id=tenant_id),
            json={"name": "Org Admin Updated"},
            headers=bypass_headers,
        )
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()["name"] == "Org Admin Updated"

    def test_can_list_tenant_principals(self, test_client: TestClient) -> None:
        """ORGANISATION_GLOBAL_ADMIN can list principals of a tenant they are not a member of."""
        tenant_id, _, bypass_headers = self._setup(test_client)
        resp = test_client.get(
            ENDPOINT_TENANT_PRINCIPALS.format(tenant_id=tenant_id),
            headers=bypass_headers,
        )
        assert resp.status_code == status.HTTP_200_OK

    def test_can_read_chat_agent(self, test_client: TestClient) -> None:
        """ORGANISATION_GLOBAL_ADMIN can GET a chat agent without resource membership."""
        tenant_id, admin_headers, bypass_headers = self._setup(test_client)
        agent_id = _create_chat_agent(test_client, tenant_id, admin_headers)
        resp = test_client.get(
            ENDPOINT_CHAT_AGENT_DETAIL.format(tenant_id=tenant_id, entity_id=agent_id),
            headers=bypass_headers,
        )
        assert resp.status_code == status.HTTP_200_OK

    def test_can_update_chat_agent(self, test_client: TestClient) -> None:
        """ORGANISATION_GLOBAL_ADMIN can PATCH a chat agent without resource membership."""
        tenant_id, admin_headers, bypass_headers = self._setup(test_client)
        agent_id = _create_chat_agent(test_client, tenant_id, admin_headers)
        resp = test_client.patch(
            ENDPOINT_CHAT_AGENT_DETAIL.format(tenant_id=tenant_id, entity_id=agent_id),
            json={"name": "OrgAdmin Updated Agent"},
            headers=bypass_headers,
        )
        assert resp.status_code == status.HTTP_200_OK

    def test_can_create_chat_agent(self, test_client: TestClient) -> None:
        """ORGANISATION_GLOBAL_ADMIN can POST a new chat agent in a foreign tenant."""
        tenant_id, _, bypass_headers = self._setup(test_client)
        resp = test_client.post(
            ENDPOINT_CHAT_AGENTS.format(tenant_id=tenant_id),
            json={"name": "OrgAdmin Created Agent", "description": "Test", "type": "N8N"},
            headers=bypass_headers,
        )
        assert resp.status_code == status.HTTP_201_CREATED

    def test_can_read_credential(self, test_client: TestClient) -> None:
        """ORGANISATION_GLOBAL_ADMIN can GET a credential without resource membership."""
        tenant_id, admin_headers, bypass_headers = self._setup(test_client)
        cred_id = _create_credential(test_client, tenant_id, admin_headers)
        resp = test_client.get(
            ENDPOINT_CREDENTIAL_DETAIL.format(tenant_id=tenant_id, entity_id=cred_id),
            headers=bypass_headers,
        )
        assert resp.status_code == status.HTTP_200_OK

    def test_can_update_credential(self, test_client: TestClient) -> None:
        """ORGANISATION_GLOBAL_ADMIN can PATCH a credential without resource membership."""
        tenant_id, admin_headers, bypass_headers = self._setup(test_client)
        cred_id = _create_credential(test_client, tenant_id, admin_headers)
        resp = test_client.patch(
            ENDPOINT_CREDENTIAL_DETAIL.format(tenant_id=tenant_id, entity_id=cred_id),
            json={"name": "OrgAdmin Updated Cred"},
            headers=bypass_headers,
        )
        assert resp.status_code == status.HTTP_200_OK

    def test_can_read_conversation(self, test_client: TestClient) -> None:
        """ORGANISATION_GLOBAL_ADMIN can GET a conversation without resource membership."""
        tenant_id, admin_headers, bypass_headers = self._setup(test_client)
        conv_id = _create_conversation(test_client, tenant_id, admin_headers)
        resp = test_client.get(
            ENDPOINT_CONVERSATION_DETAIL.format(tenant_id=tenant_id, entity_id=conv_id),
            headers=bypass_headers,
        )
        assert resp.status_code == status.HTTP_200_OK

    def test_can_read_custom_group(self, test_client: TestClient) -> None:
        """ORGANISATION_GLOBAL_ADMIN can GET a custom group without resource membership."""
        tenant_id, admin_headers, bypass_headers = self._setup(test_client)
        group_id = _create_custom_group(test_client, tenant_id, admin_headers)
        resp = test_client.get(
            ENDPOINT_CUSTOM_GROUP_DETAIL.format(tenant_id=tenant_id, entity_id=group_id),
            headers=bypass_headers,
        )
        assert resp.status_code == status.HTTP_200_OK

    def test_can_read_chat_widget(self, test_client: TestClient) -> None:
        """ORGANISATION_GLOBAL_ADMIN can GET a chat widget without resource membership."""
        tenant_id, admin_headers, bypass_headers = self._setup(test_client)
        widget_id = _create_chat_widget(test_client, tenant_id, admin_headers)
        resp = test_client.get(
            ENDPOINT_CHAT_WIDGET_DETAIL.format(tenant_id=tenant_id, entity_id=widget_id),
            headers=bypass_headers,
        )
        assert resp.status_code == status.HTTP_200_OK

    def test_can_list_tags(self, test_client: TestClient) -> None:
        """ORGANISATION_GLOBAL_ADMIN can list tags in a foreign tenant."""
        tenant_id, admin_headers, bypass_headers = self._setup(test_client)
        _create_tag(test_client, tenant_id, admin_headers)
        resp = test_client.get(
            ENDPOINT_TAGS.format(tenant_id=tenant_id),
            headers=bypass_headers,
        )
        assert resp.status_code == status.HTTP_200_OK

    def test_can_list_tenant_ai_models(self, test_client: TestClient) -> None:
        """ORGANISATION_GLOBAL_ADMIN can list tenant AI models in a foreign tenant."""
        tenant_id, _, bypass_headers = self._setup(test_client)
        resp = test_client.get(
            ENDPOINT_TENANT_AI_MODELS.format(tenant_id=tenant_id),
            headers=bypass_headers,
        )
        assert resp.status_code == status.HTTP_200_OK


class TestOrgTenantAdminBypassOnTenantResources:
    """ORGANISATION_TENANT_ADMIN bypasses all tenant-level permission checks.

    Same as ORGANISATION_GLOBAL_ADMIN but for the TENANT_ADMIN org role.
    """

    @staticmethod
    def _setup(
        test_client: TestClient,
    ) -> tuple[str, dict[str, str], dict[str, str]]:
        """Create a tenant owned by admin, return (tenant_id, admin_headers, bypass_headers)."""
        admin_token = test_client.create_test_user(f"orgta-owner-{uuid.uuid4().hex[:6]}", "Tenant Owner")
        admin_headers = create_auth_headers(admin_token, use_cache=False)
        tenant_id = _create_tenant(test_client, admin_headers)

        _, bypass_headers = _create_user_with_org_role(test_client, "ta-bypass", ROLE_ORG_TENANT_ADMIN)
        return tenant_id, admin_headers, bypass_headers

    def test_can_read_tenant(self, test_client: TestClient) -> None:
        """ORGANISATION_TENANT_ADMIN can GET a tenant they are not a member of."""
        tenant_id, _, bypass_headers = self._setup(test_client)
        resp = test_client.get(
            ENDPOINT_TENANT_DETAIL.format(tenant_id=tenant_id),
            headers=bypass_headers,
        )
        assert resp.status_code == status.HTTP_200_OK

    def test_can_update_tenant(self, test_client: TestClient) -> None:
        """ORGANISATION_TENANT_ADMIN can PATCH a tenant they are not a member of."""
        tenant_id, _, bypass_headers = self._setup(test_client)
        resp = test_client.patch(
            ENDPOINT_TENANT_DETAIL.format(tenant_id=tenant_id),
            json={"name": "OrgTA Updated"},
            headers=bypass_headers,
        )
        assert resp.status_code == status.HTTP_200_OK

    def test_can_list_tenant_principals(self, test_client: TestClient) -> None:
        """ORGANISATION_TENANT_ADMIN can list principals of a foreign tenant."""
        tenant_id, _, bypass_headers = self._setup(test_client)
        resp = test_client.get(
            ENDPOINT_TENANT_PRINCIPALS.format(tenant_id=tenant_id),
            headers=bypass_headers,
        )
        assert resp.status_code == status.HTTP_200_OK

    def test_can_read_chat_agent(self, test_client: TestClient) -> None:
        """ORGANISATION_TENANT_ADMIN can read a chat agent without resource membership."""
        tenant_id, admin_headers, bypass_headers = self._setup(test_client)
        agent_id = _create_chat_agent(test_client, tenant_id, admin_headers)
        resp = test_client.get(
            ENDPOINT_CHAT_AGENT_DETAIL.format(tenant_id=tenant_id, entity_id=agent_id),
            headers=bypass_headers,
        )
        assert resp.status_code == status.HTTP_200_OK

    def test_can_update_chat_agent(self, test_client: TestClient) -> None:
        """ORGANISATION_TENANT_ADMIN can update a chat agent without resource membership."""
        tenant_id, admin_headers, bypass_headers = self._setup(test_client)
        agent_id = _create_chat_agent(test_client, tenant_id, admin_headers)
        resp = test_client.patch(
            ENDPOINT_CHAT_AGENT_DETAIL.format(tenant_id=tenant_id, entity_id=agent_id),
            json={"name": "OrgTA Updated Agent"},
            headers=bypass_headers,
        )
        assert resp.status_code == status.HTTP_200_OK

    def test_can_create_credential(self, test_client: TestClient) -> None:
        """ORGANISATION_TENANT_ADMIN can create a credential in a foreign tenant."""
        tenant_id, _, bypass_headers = self._setup(test_client)
        resp = test_client.post(
            ENDPOINT_CREDENTIALS.format(tenant_id=tenant_id),
            json={
                "name": "OrgTA Credential",
                "description": "Test",
                "credential_type": "API_KEY",
                "secret_value": "test-secret-value-12345",
            },
            headers=bypass_headers,
        )
        assert resp.status_code == status.HTTP_201_CREATED

    def test_can_read_credential(self, test_client: TestClient) -> None:
        """ORGANISATION_TENANT_ADMIN can read a credential without resource membership."""
        tenant_id, admin_headers, bypass_headers = self._setup(test_client)
        cred_id = _create_credential(test_client, tenant_id, admin_headers)
        resp = test_client.get(
            ENDPOINT_CREDENTIAL_DETAIL.format(tenant_id=tenant_id, entity_id=cred_id),
            headers=bypass_headers,
        )
        assert resp.status_code == status.HTTP_200_OK

    def test_can_read_conversation(self, test_client: TestClient) -> None:
        """ORGANISATION_TENANT_ADMIN can read a conversation without resource membership."""
        tenant_id, admin_headers, bypass_headers = self._setup(test_client)
        conv_id = _create_conversation(test_client, tenant_id, admin_headers)
        resp = test_client.get(
            ENDPOINT_CONVERSATION_DETAIL.format(tenant_id=tenant_id, entity_id=conv_id),
            headers=bypass_headers,
        )
        assert resp.status_code == status.HTTP_200_OK

    def test_can_read_custom_group(self, test_client: TestClient) -> None:
        """ORGANISATION_TENANT_ADMIN can read a custom group without resource membership."""
        tenant_id, admin_headers, bypass_headers = self._setup(test_client)
        group_id = _create_custom_group(test_client, tenant_id, admin_headers)
        resp = test_client.get(
            ENDPOINT_CUSTOM_GROUP_DETAIL.format(tenant_id=tenant_id, entity_id=group_id),
            headers=bypass_headers,
        )
        assert resp.status_code == status.HTTP_200_OK

    def test_can_read_chat_widget(self, test_client: TestClient) -> None:
        """ORGANISATION_TENANT_ADMIN can read a chat widget without resource membership."""
        tenant_id, admin_headers, bypass_headers = self._setup(test_client)
        widget_id = _create_chat_widget(test_client, tenant_id, admin_headers)
        resp = test_client.get(
            ENDPOINT_CHAT_WIDGET_DETAIL.format(tenant_id=tenant_id, entity_id=widget_id),
            headers=bypass_headers,
        )
        assert resp.status_code == status.HTTP_200_OK

    def test_can_list_tags(self, test_client: TestClient) -> None:
        """ORGANISATION_TENANT_ADMIN can list tags in a foreign tenant."""
        tenant_id, admin_headers, bypass_headers = self._setup(test_client)
        _create_tag(test_client, tenant_id, admin_headers)
        resp = test_client.get(
            ENDPOINT_TAGS.format(tenant_id=tenant_id),
            headers=bypass_headers,
        )
        assert resp.status_code == status.HTTP_200_OK


class TestOrgTenantCreatorDoesNotGetBypass:
    """ORGANISATION_TENANT_CREATOR does NOT bypass tenant-level permission checks.

    This role only allows org-level actions (create tenants, view org).
    It should get 403 on tenant resources if not a tenant/resource member.
    """

    @staticmethod
    def _setup(
        test_client: TestClient,
    ) -> tuple[str, dict[str, str], dict[str, str]]:
        """Create a tenant owned by admin, return (tenant_id, admin_headers, creator_headers)."""
        admin_token = test_client.create_test_user(f"orgtc-owner-{uuid.uuid4().hex[:6]}", "Tenant Owner")
        admin_headers = create_auth_headers(admin_token, use_cache=False)
        tenant_id = _create_tenant(test_client, admin_headers)

        _, creator_headers = _create_user_with_org_role(test_client, "tc-nobypass", ROLE_ORG_TENANT_CREATOR)
        return tenant_id, admin_headers, creator_headers

    def test_cannot_read_tenant(self, test_client: TestClient) -> None:
        """ORGANISATION_TENANT_CREATOR cannot GET a tenant they are not a member of."""
        tenant_id, _, creator_headers = self._setup(test_client)
        resp = test_client.get(
            ENDPOINT_TENANT_DETAIL.format(tenant_id=tenant_id),
            headers=creator_headers,
        )
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_cannot_update_tenant(self, test_client: TestClient) -> None:
        """ORGANISATION_TENANT_CREATOR cannot PATCH a foreign tenant."""
        tenant_id, _, creator_headers = self._setup(test_client)
        resp = test_client.patch(
            ENDPOINT_TENANT_DETAIL.format(tenant_id=tenant_id),
            json={"name": "Should Fail"},
            headers=creator_headers,
        )
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_cannot_read_chat_agent(self, test_client: TestClient) -> None:
        """ORGANISATION_TENANT_CREATOR cannot GET a chat agent in a foreign tenant."""
        tenant_id, admin_headers, creator_headers = self._setup(test_client)
        agent_id = _create_chat_agent(test_client, tenant_id, admin_headers)
        resp = test_client.get(
            ENDPOINT_CHAT_AGENT_DETAIL.format(tenant_id=tenant_id, entity_id=agent_id),
            headers=creator_headers,
        )
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_cannot_read_credential(self, test_client: TestClient) -> None:
        """ORGANISATION_TENANT_CREATOR cannot GET a credential in a foreign tenant."""
        tenant_id, admin_headers, creator_headers = self._setup(test_client)
        cred_id = _create_credential(test_client, tenant_id, admin_headers)
        resp = test_client.get(
            ENDPOINT_CREDENTIAL_DETAIL.format(tenant_id=tenant_id, entity_id=cred_id),
            headers=creator_headers,
        )
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_cannot_read_conversation(self, test_client: TestClient) -> None:
        """ORGANISATION_TENANT_CREATOR cannot GET a conversation in a foreign tenant."""
        tenant_id, admin_headers, creator_headers = self._setup(test_client)
        conv_id = _create_conversation(test_client, tenant_id, admin_headers)
        resp = test_client.get(
            ENDPOINT_CONVERSATION_DETAIL.format(tenant_id=tenant_id, entity_id=conv_id),
            headers=creator_headers,
        )
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_cannot_read_custom_group(self, test_client: TestClient) -> None:
        """ORGANISATION_TENANT_CREATOR cannot GET a custom group in a foreign tenant."""
        tenant_id, admin_headers, creator_headers = self._setup(test_client)
        group_id = _create_custom_group(test_client, tenant_id, admin_headers)
        resp = test_client.get(
            ENDPOINT_CUSTOM_GROUP_DETAIL.format(tenant_id=tenant_id, entity_id=group_id),
            headers=creator_headers,
        )
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_cannot_read_chat_widget(self, test_client: TestClient) -> None:
        """ORGANISATION_TENANT_CREATOR cannot GET a chat widget in a foreign tenant."""
        tenant_id, admin_headers, creator_headers = self._setup(test_client)
        widget_id = _create_chat_widget(test_client, tenant_id, admin_headers)
        resp = test_client.get(
            ENDPOINT_CHAT_WIDGET_DETAIL.format(tenant_id=tenant_id, entity_id=widget_id),
            headers=creator_headers,
        )
        assert resp.status_code == status.HTTP_403_FORBIDDEN


class TestOrgCreationRestriction:
    """Verify that organization creation is restricted to system admin."""

    def test_create_org_allowed_for_system_admin(self, test_client: TestClient) -> None:
        """User whose email matches msal_system_admin_email can create an org."""
        slug = f"sysadm-org-{uuid.uuid4().hex[:6]}"
        token = test_client.create_test_user("sysadm-creator", "Sys Admin", mail="admin@example.com")
        headers = create_auth_headers(token, use_cache=False)

        with patch("unifiedui.core.config.settings") as mock_settings:
            mock_settings.msal_system_admin_email = "admin@example.com"
            mock_settings.ldap_system_admin_username = None
            mock_settings.oidc_zitadel_system_admin_username = None
            resp = test_client.post(
                ENDPOINT_ORGANIZATIONS,
                json={
                    "name": "SysAdmin Org",
                    "slug": slug,
                    "identity_provider": "entra_id",
                    "identity_tenant_id": f"sysadm-idp-{slug}",
                },
                headers=headers,
            )
        assert resp.status_code == status.HTTP_201_CREATED
        assert resp.json()["name"] == "SysAdmin Org"

    def test_create_org_denied_for_non_system_admin(self, test_client: TestClient) -> None:
        """User whose email does NOT match system admin gets 403."""
        token = test_client.create_test_user("nonsysadm", "Normal User", mail="user@example.com")
        headers = create_auth_headers(token, use_cache=False)

        with patch("unifiedui.core.config.settings") as mock_settings:
            mock_settings.msal_system_admin_email = "admin@example.com"
            mock_settings.ldap_system_admin_username = None
            mock_settings.oidc_zitadel_system_admin_username = None
            resp = test_client.post(
                ENDPOINT_ORGANIZATIONS,
                json={
                    "name": "Unauthorized Org",
                    "slug": "unauth-org",
                    "identity_provider": "entra_id",
                    "identity_tenant_id": "unauth-idp",
                },
                headers=headers,
            )
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_create_org_denied_when_no_email(self, test_client: TestClient) -> None:
        """User with no email set gets 403 when system admin is configured."""
        token = test_client.create_test_user("nomail", "No Mail User")
        headers = create_auth_headers(token, use_cache=False)

        with patch("unifiedui.core.config.settings") as mock_settings:
            mock_settings.msal_system_admin_email = "admin@example.com"
            mock_settings.ldap_system_admin_username = None
            mock_settings.oidc_zitadel_system_admin_username = None
            resp = test_client.post(
                ENDPOINT_ORGANIZATIONS,
                json={
                    "name": "No Mail Org",
                    "slug": "nomail-org",
                    "identity_provider": "entra_id",
                    "identity_tenant_id": "nomail-idp",
                },
                headers=headers,
            )
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_create_org_allowed_when_no_restriction(self, test_client: TestClient) -> None:
        """When no system admin is configured, any authenticated user can create an org."""
        slug = f"norestrict-{uuid.uuid4().hex[:6]}"
        token = test_client.create_test_user("anyuser", "Any User", mail="any@example.com")
        headers = create_auth_headers(token, use_cache=False)

        with patch("unifiedui.core.config.settings") as mock_settings:
            mock_settings.msal_system_admin_email = None
            mock_settings.ldap_system_admin_username = None
            mock_settings.oidc_zitadel_system_admin_username = None
            resp = test_client.post(
                ENDPOINT_ORGANIZATIONS,
                json={
                    "name": "Open Org",
                    "slug": slug,
                    "identity_provider": "entra_id",
                    "identity_tenant_id": f"norestrict-idp-{slug}",
                },
                headers=headers,
            )
        assert resp.status_code == status.HTTP_201_CREATED


class TestGetOrgRequiresMembership:
    """Verify that GET organization requires org principalship (any role)."""

    def test_member_can_get_org(self, test_client: TestClient) -> None:
        """User with ORGANISATION_TENANT_CREATOR can GET their org."""
        _, creator_headers = _create_user_with_org_role(test_client, "getorg-member", ROLE_ORG_TENANT_CREATOR)
        resp = test_client.get(
            f"{ENDPOINT_ORGANIZATIONS}/{TEST_ORGANIZATION_ID}",
            headers=creator_headers,
        )
        assert resp.status_code == status.HTTP_200_OK

    def test_non_member_cannot_get_org(self, test_client: TestClient) -> None:
        """User without any org role gets 403 on GET org."""
        token = test_client.create_test_user(f"getorg-nonmember-{uuid.uuid4().hex[:6]}", "Non Member")
        headers = create_auth_headers(token, use_cache=False)

        admin_headers = _get_admin_headers(test_client)
        slug = f"other-org-{uuid.uuid4().hex[:6]}"
        with patch("unifiedui.core.config.settings") as mock_settings:
            mock_settings.msal_system_admin_email = None
            mock_settings.ldap_system_admin_username = None
            mock_settings.oidc_zitadel_system_admin_username = None
            resp_create = test_client.post(
                ENDPOINT_ORGANIZATIONS,
                json={
                    "name": "Other Org",
                    "slug": slug,
                    "identity_provider": "other_idp",
                    "identity_tenant_id": f"other-idp-{slug}",
                },
                headers=admin_headers,
            )
        assert resp_create.status_code == status.HTTP_201_CREATED
        other_org_id = resp_create.json()["id"]

        resp = test_client.get(
            f"{ENDPOINT_ORGANIZATIONS}/{other_org_id}",
            headers=headers,
        )
        assert resp.status_code == status.HTTP_403_FORBIDDEN


class TestOrgRolePermissionBoundaries:
    """Verify exact permission boundaries for each organization role on org routes."""

    @staticmethod
    def _setup_org_with_principal(
        test_client: TestClient,
        slug: str,
        principal_role: str,
    ) -> tuple[dict[str, Any], dict[str, str], dict[str, str]]:
        """Create an org and add a principal with the given role.

        Returns:
            (org_data, admin_headers, principal_headers)
        """
        admin_token = test_client.create_test_user(f"perm-adm-{slug}", f"Admin {slug}")
        admin_headers = create_auth_headers(admin_token, use_cache=False)

        with patch("unifiedui.core.config.settings") as mock_settings:
            mock_settings.msal_system_admin_email = None
            mock_settings.ldap_system_admin_username = None
            mock_settings.oidc_zitadel_system_admin_username = None
            resp = test_client.post(
                ENDPOINT_ORGANIZATIONS,
                json={
                    "name": f"Perm Org {slug}",
                    "slug": slug,
                    "identity_provider": "entra_id",
                    "identity_tenant_id": f"perm-idp-{slug}",
                },
                headers=admin_headers,
            )
        assert resp.status_code == status.HTTP_201_CREATED
        org = resp.json()

        member_id = f"perm-mbr-{slug}"
        principal_token = test_client.create_test_user(member_id, f"Member {slug}")
        principal_headers = create_auth_headers(principal_token, use_cache=False)

        add_resp = test_client.post(
            ENDPOINT_ORGANIZATION_PRINCIPALS.format(organization_id=org["id"]),
            json={
                "principal_id": member_id,
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": principal_role,
            },
            headers=admin_headers,
        )
        assert add_resp.status_code == status.HTTP_201_CREATED

        return org, admin_headers, principal_headers

    def test_global_admin_can_update_org(self, test_client: TestClient) -> None:
        """ORGANISATION_GLOBAL_ADMIN can PATCH org."""
        org, _, principal_headers = self._setup_org_with_principal(
            test_client, slug=f"ga-upd-{uuid.uuid4().hex[:4]}", principal_role=ROLE_ORG_GLOBAL_ADMIN
        )
        resp = test_client.patch(
            f"{ENDPOINT_ORGANIZATIONS}/{org['id']}",
            json={"name": "GA Updated"},
            headers=principal_headers,
        )
        assert resp.status_code == status.HTTP_200_OK

    def test_global_admin_can_manage_members(self, test_client: TestClient) -> None:
        """ORGANISATION_GLOBAL_ADMIN can list/add/remove org principals."""
        org, _, principal_headers = self._setup_org_with_principal(
            test_client, slug=f"ga-mem-{uuid.uuid4().hex[:4]}", principal_role=ROLE_ORG_GLOBAL_ADMIN
        )
        org_id = org["id"]

        resp_list = test_client.get(
            ENDPOINT_ORGANIZATION_PRINCIPALS.format(organization_id=org_id),
            headers=principal_headers,
        )
        assert resp_list.status_code == status.HTTP_200_OK

        resp_add = test_client.post(
            ENDPOINT_ORGANIZATION_PRINCIPALS.format(organization_id=org_id),
            json={
                "principal_id": "new-user-ga",
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_ORG_TENANT_CREATOR,
            },
            headers=principal_headers,
        )
        assert resp_add.status_code == status.HTTP_201_CREATED

    def test_tenant_admin_cannot_update_org(self, test_client: TestClient) -> None:
        """ORGANISATION_TENANT_ADMIN cannot PATCH org (requires GLOBAL_ADMIN)."""
        org, _, principal_headers = self._setup_org_with_principal(
            test_client, slug=f"ta-noupd-{uuid.uuid4().hex[:4]}", principal_role=ROLE_ORG_TENANT_ADMIN
        )
        resp = test_client.patch(
            f"{ENDPOINT_ORGANIZATIONS}/{org['id']}",
            json={"name": "TA Should Fail"},
            headers=principal_headers,
        )
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_tenant_admin_cannot_manage_principals(self, test_client: TestClient) -> None:
        """ORGANISATION_TENANT_ADMIN cannot list/add/remove org principals."""
        org, _, principal_headers = self._setup_org_with_principal(
            test_client, slug=f"ta-nomem-{uuid.uuid4().hex[:4]}", principal_role=ROLE_ORG_TENANT_ADMIN
        )
        resp = test_client.get(
            ENDPOINT_ORGANIZATION_PRINCIPALS.format(organization_id=org["id"]),
            headers=principal_headers,
        )
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_tenant_admin_can_view_org(self, test_client: TestClient) -> None:
        """ORGANISATION_TENANT_ADMIN can GET org (ORG_ALL_ROLES)."""
        org, _, principal_headers = self._setup_org_with_principal(
            test_client, slug=f"ta-view-{uuid.uuid4().hex[:4]}", principal_role=ROLE_ORG_TENANT_ADMIN
        )
        resp = test_client.get(
            f"{ENDPOINT_ORGANIZATIONS}/{org['id']}",
            headers=principal_headers,
        )
        assert resp.status_code == status.HTTP_200_OK

    def test_tenant_creator_can_view_org(self, test_client: TestClient) -> None:
        """ORGANISATION_TENANT_CREATOR can GET org (ORG_ALL_ROLES)."""
        org, _, principal_headers = self._setup_org_with_principal(
            test_client, slug=f"tc-view-{uuid.uuid4().hex[:4]}", principal_role=ROLE_ORG_TENANT_CREATOR
        )
        resp = test_client.get(
            f"{ENDPOINT_ORGANIZATIONS}/{org['id']}",
            headers=principal_headers,
        )
        assert resp.status_code == status.HTTP_200_OK

    def test_tenant_creator_cannot_update_org(self, test_client: TestClient) -> None:
        """ORGANISATION_TENANT_CREATOR cannot PATCH org."""
        org, _, principal_headers = self._setup_org_with_principal(
            test_client, slug=f"tc-noupd-{uuid.uuid4().hex[:4]}", principal_role=ROLE_ORG_TENANT_CREATOR
        )
        resp = test_client.patch(
            f"{ENDPOINT_ORGANIZATIONS}/{org['id']}",
            json={"name": "TC Should Fail"},
            headers=principal_headers,
        )
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_tenant_creator_cannot_manage_principals(self, test_client: TestClient) -> None:
        """ORGANISATION_TENANT_CREATOR cannot list org principals."""
        org, _, principal_headers = self._setup_org_with_principal(
            test_client, slug=f"tc-nomem-{uuid.uuid4().hex[:4]}", principal_role=ROLE_ORG_TENANT_CREATOR
        )
        resp = test_client.get(
            ENDPOINT_ORGANIZATION_PRINCIPALS.format(organization_id=org["id"]),
            headers=principal_headers,
        )
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_tenant_creator_can_create_tenant(self, test_client: TestClient) -> None:
        """ORGANISATION_TENANT_CREATOR can create a tenant in org (ORG_ALL_ROLES)."""
        org, _, principal_headers = self._setup_org_with_principal(
            test_client, slug=f"tc-crtten-{uuid.uuid4().hex[:4]}", principal_role=ROLE_ORG_TENANT_CREATOR
        )
        resp = test_client.post(
            f"{ENDPOINT_ORGANIZATIONS}/{org['id']}/tenants",
            json={"name": "Creator Tenant", "environment_type": "SANDBOX"},
            headers=principal_headers,
        )
        assert resp.status_code == status.HTTP_201_CREATED

    def test_tenant_creator_cannot_delete_tenant(self, test_client: TestClient) -> None:
        """ORGANISATION_TENANT_CREATOR cannot delete a tenant (requires TENANT_MANAGE_ROLES)."""
        org, admin_headers, principal_headers = self._setup_org_with_principal(
            test_client, slug=f"tc-nodel-{uuid.uuid4().hex[:4]}", principal_role=ROLE_ORG_TENANT_CREATOR
        )
        create_resp = test_client.post(
            f"{ENDPOINT_ORGANIZATIONS}/{org['id']}/tenants",
            json={"name": "To Delete", "environment_type": "SANDBOX"},
            headers=admin_headers,
        )
        assert create_resp.status_code == status.HTTP_201_CREATED
        tenant_id = create_resp.json()["id"]

        resp = test_client.request(
            "DELETE",
            f"{ENDPOINT_ORGANIZATIONS}/{org['id']}/tenants/{tenant_id}",
            headers=principal_headers,
        )
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_tenant_admin_can_delete_tenant(self, test_client: TestClient) -> None:
        """ORGANISATION_TENANT_ADMIN can delete a tenant (ORG_TENANT_MANAGE_ROLES)."""
        org, admin_headers, principal_headers = self._setup_org_with_principal(
            test_client, slug=f"ta-del-{uuid.uuid4().hex[:4]}", principal_role=ROLE_ORG_TENANT_ADMIN
        )
        create_resp = test_client.post(
            f"{ENDPOINT_ORGANIZATIONS}/{org['id']}/tenants",
            json={"name": "TA Delete", "environment_type": "SANDBOX"},
            headers=admin_headers,
        )
        assert create_resp.status_code == status.HTTP_201_CREATED
        tenant_id = create_resp.json()["id"]

        resp = test_client.request(
            "DELETE",
            f"{ENDPOINT_ORGANIZATIONS}/{org['id']}/tenants/{tenant_id}",
            headers=principal_headers,
        )
        assert resp.status_code == status.HTTP_204_NO_CONTENT


class TestTenantGlobalAdminRename:
    """Verify that TENANT_GLOBAL_ADMIN (renamed from GLOBAL_ADMIN) works correctly."""

    def test_creator_gets_tenant_global_admin(self, test_client: TestClient) -> None:
        """Tenant creator automatically receives TENANT_GLOBAL_ADMIN role."""
        token = test_client.create_test_user(f"tga-creator-{uuid.uuid4().hex[:6]}", "TGA Creator")
        headers = create_auth_headers(token, use_cache=False)
        resp = test_client.post(
            ENDPOINT_TENANTS,
            json={"name": "TGA Test Tenant"},
            headers=headers,
        )
        assert resp.status_code == status.HTTP_201_CREATED
        tenant_id = resp.json()["id"]

        principals_resp = test_client.get(
            f"{ENDPOINT_TENANT_PRINCIPALS.format(tenant_id=tenant_id)}/{token.get_id()}",
            headers=headers,
        )
        assert principals_resp.status_code == status.HTTP_200_OK
        data = principals_resp.json()
        assert TenantRolesEnum.TENANT_GLOBAL_ADMIN.value in data["roles"]

    def test_tenant_global_admin_can_manage_all(self, test_client: TestClient) -> None:
        """TENANT_GLOBAL_ADMIN can update tenant, manage principals, and access all resources."""
        token = test_client.create_test_user(f"tga-manage-{uuid.uuid4().hex[:6]}", "TGA Manager")
        headers = create_auth_headers(token, use_cache=False)
        resp = test_client.post(
            ENDPOINT_TENANTS,
            json={"name": "TGA Manage Tenant"},
            headers=headers,
        )
        tenant_id = resp.json()["id"]

        update_resp = test_client.patch(
            ENDPOINT_TENANT_DETAIL.format(tenant_id=tenant_id),
            json={"name": "TGA Updated"},
            headers=headers,
        )
        assert update_resp.status_code == status.HTTP_200_OK

        principals_resp = test_client.get(
            ENDPOINT_TENANT_PRINCIPALS.format(tenant_id=tenant_id),
            headers=headers,
        )
        assert principals_resp.status_code == status.HTTP_200_OK

        agent_resp = test_client.post(
            ENDPOINT_CHAT_AGENTS.format(tenant_id=tenant_id),
            json={"name": "TGA Agent", "description": "Test", "type": "N8N"},
            headers=headers,
        )
        assert agent_resp.status_code == status.HTTP_201_CREATED

    def test_reader_cannot_update_tenant(self, test_client: TestClient) -> None:
        """READER role cannot update a tenant — only TENANT_GLOBAL_ADMIN can."""
        admin_token = test_client.create_test_user(f"tga-admin-{uuid.uuid4().hex[:6]}", "TGA Admin")
        admin_headers = create_auth_headers(admin_token, use_cache=False)
        resp = test_client.post(
            ENDPOINT_TENANTS,
            json={"name": "Reader Test Tenant"},
            headers=admin_headers,
        )
        tenant_id = resp.json()["id"]

        reader_id = f"tga-reader-{uuid.uuid4().hex[:6]}"
        reader_token = test_client.create_test_user(reader_id, "TGA Reader")
        reader_headers = create_auth_headers(reader_token, use_cache=False)

        test_client.put(
            ENDPOINT_TENANT_PRINCIPALS.format(tenant_id=tenant_id),
            json={
                "principal_id": reader_id,
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": TenantRolesEnum.READER.value,
            },
            headers=admin_headers,
        )

        update_resp = test_client.patch(
            ENDPOINT_TENANT_DETAIL.format(tenant_id=tenant_id),
            json={"name": "Should Fail"},
            headers=reader_headers,
        )
        assert update_resp.status_code == status.HTTP_403_FORBIDDEN
