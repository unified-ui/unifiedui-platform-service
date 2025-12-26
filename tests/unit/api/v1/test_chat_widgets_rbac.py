"""Tests for chat widgets RBAC (Role-Based Access Control)."""
from typing import Any
from fastapi import status
from starlette.testclient import TestClient

from unifiedui.core.database.enums import PermissionActionEnum, PrincipalTypeEnum
from tests.conftest import create_auth_headers


# API Endpoints
ENDPOINT_TENANTS = "/api/v1/tenants"
ENDPOINT_CHAT_WIDGETS = "/api/v1/tenants/{tenant_id}/chat-widgets"
ENDPOINT_CHAT_WIDGET_DETAIL = "/api/v1/tenants/{tenant_id}/chat-widgets/{chat_widget_id}"
ENDPOINT_CHAT_WIDGET_PRINCIPALS = "/api/v1/tenants/{tenant_id}/chat-widgets/{chat_widget_id}/principals"
ENDPOINT_PRINCIPAL_DETAIL = "/api/v1/tenants/{tenant_id}/chat-widgets/{chat_widget_id}/principals/{principal_id}"

# Roles
ROLE_READ = PermissionActionEnum.READ.value
ROLE_WRITE = PermissionActionEnum.WRITE.value
ROLE_ADMIN = PermissionActionEnum.ADMIN.value

# Principal Types
PRINCIPAL_TYPE_USER = PrincipalTypeEnum.IDENTITY_USER.value
PRINCIPAL_TYPE_GROUP = PrincipalTypeEnum.IDENTITY_GROUP.value
PRINCIPAL_TYPE_CUSTOM_GROUP = PrincipalTypeEnum.CUSTOM_GROUP.value


def create_tenant_for_user(test_client: TestClient, user_token: Any, tenant_name: str = "Test Tenant") -> str:
    """Helper function to create a tenant and return its ID."""
    headers = create_auth_headers(user_token, use_cache=False)
    response = test_client.post(
        ENDPOINT_TENANTS,
        json={"name": tenant_name, "description": f"Tenant for {user_token.get_id()}"},
        headers=headers
    )
    assert response.status_code == status.HTTP_201_CREATED
    return response.json()["id"]


def create_chat_widget(test_client: TestClient, tenant_id: str, headers: dict, name: str = "Test Widget") -> str:
    """Helper function to create a chat widget and return its ID."""
    response = test_client.post(
        ENDPOINT_CHAT_WIDGETS.format(tenant_id=tenant_id),
        json={
            "name": name,
            "description": f"Chat Widget {name}",
            "type": "IFRAME",
            "config": {"key": "value"}
        },
        headers=headers
    )
    assert response.status_code == status.HTTP_201_CREATED
    return response.json()["id"]


def add_user_to_tenant(test_client: TestClient, tenant_id: str, admin_headers: dict, user_id: str, role: str = "READER") -> None:
    """Helper function to add a user to a tenant."""
    response = test_client.put(
        f"/api/v1/tenants/{tenant_id}/principals",
        json={
            "principal_id": user_id,
            "principal_type": PRINCIPAL_TYPE_USER,
            "role": role
        },
        headers=admin_headers
    )
    assert response.status_code == status.HTTP_200_OK


class TestChatWidgetRBAC:
    """Test suite for chat widget role-based access control."""
    
    def test_creator_becomes_admin(self, test_client: TestClient) -> None:
        """Test that chat widget creator automatically becomes ADMIN."""
        user_token = test_client.create_test_user("cw-creator", "CW Creator")
        headers = create_auth_headers(user_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, user_token)
        
        widget_id = create_chat_widget(test_client, tenant_id, headers, "Creator Test")
        
        # Verify creator has ADMIN role
        principals_response = test_client.get(
            ENDPOINT_PRINCIPAL_DETAIL.format(
                tenant_id=tenant_id,
                chat_widget_id=widget_id,
                principal_id="cw-creator"
            ),
            headers=headers
        )
        
        assert principals_response.status_code == status.HTTP_200_OK
        data = principals_response.json()
        assert ROLE_ADMIN in data["roles"]
    
    def test_admin_can_update_chat_widget(self, test_client: TestClient) -> None:
        """Test that ADMIN can update chat widget."""
        user_token = test_client.create_test_user("cw-admin", "CW Admin")
        headers = create_auth_headers(user_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, user_token)
        
        widget_id = create_chat_widget(test_client, tenant_id, headers, "Original Name")
        
        update_response = test_client.patch(
            ENDPOINT_CHAT_WIDGET_DETAIL.format(tenant_id=tenant_id, chat_widget_id=widget_id),
            json={"name": "Updated Name"},
            headers=headers
        )
        
        assert update_response.status_code == status.HTTP_200_OK
        assert update_response.json()["name"] == "Updated Name"
    
    def test_admin_can_delete_chat_widget(self, test_client: TestClient) -> None:
        """Test that ADMIN can delete chat widget."""
        user_token = test_client.create_test_user("cw-delete-admin", "CW Delete Admin")
        headers = create_auth_headers(user_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, user_token)
        
        widget_id = create_chat_widget(test_client, tenant_id, headers, "To Delete")
        
        delete_response = test_client.request(
            "DELETE",
            ENDPOINT_CHAT_WIDGET_DETAIL.format(tenant_id=tenant_id, chat_widget_id=widget_id),
            headers=headers
        )
        
        assert delete_response.status_code == status.HTTP_204_NO_CONTENT
    
    def test_admin_can_manage_principals(self, test_client: TestClient) -> None:
        """Test that ADMIN can add/remove principals."""
        admin_token = test_client.create_test_user("cw-principal-admin", "CW Principal Admin")
        admin_headers = create_auth_headers(admin_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, admin_token)
        
        widget_id = create_chat_widget(test_client, tenant_id, admin_headers, "Principal Test")
        
        # Add a role to another user
        add_response = test_client.put(
            ENDPOINT_CHAT_WIDGET_PRINCIPALS.format(tenant_id=tenant_id, chat_widget_id=widget_id),
            json={
                "principal_id": "other-user",
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_READ
            },
            headers=admin_headers
        )
        
        assert add_response.status_code == status.HTTP_200_OK
        assert add_response.json()["role"] == ROLE_READ
        
        # Remove the role
        delete_response = test_client.request(
            "DELETE",
            ENDPOINT_CHAT_WIDGET_PRINCIPALS.format(tenant_id=tenant_id, chat_widget_id=widget_id),
            json={
                "principal_id": "other-user",
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_READ
            },
            headers=admin_headers
        )
        
        assert delete_response.status_code == status.HTTP_204_NO_CONTENT
    
    def test_non_member_cannot_access_chat_widget(self, test_client: TestClient) -> None:
        """Test that users without access cannot access chat widget."""
        user_a_token = test_client.create_test_user("cw-user-a", "CW User A")
        headers_a = create_auth_headers(user_a_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, user_a_token)
        widget_id = create_chat_widget(test_client, tenant_id, headers_a, "Private Widget")
        
        user_b_token = test_client.create_test_user("cw-user-b", "CW User B")
        headers_b = create_auth_headers(user_b_token, use_cache=False)
        
        # User B cannot view
        get_response = test_client.get(
            ENDPOINT_CHAT_WIDGET_DETAIL.format(tenant_id=tenant_id, chat_widget_id=widget_id),
            headers=headers_b
        )
        assert get_response.status_code == status.HTTP_403_FORBIDDEN
        
        # User B cannot update
        update_response = test_client.patch(
            ENDPOINT_CHAT_WIDGET_DETAIL.format(tenant_id=tenant_id, chat_widget_id=widget_id),
            json={"name": "Hacked"},
            headers=headers_b
        )
        assert update_response.status_code == status.HTTP_403_FORBIDDEN
        
        # User B cannot delete
        delete_response = test_client.request(
            "DELETE",
            ENDPOINT_CHAT_WIDGET_DETAIL.format(tenant_id=tenant_id, chat_widget_id=widget_id),
            headers=headers_b
        )
        assert delete_response.status_code == status.HTTP_403_FORBIDDEN
    
    def test_read_user_can_view_but_not_modify(self, test_client: TestClient) -> None:
        """Test that READ role can view but cannot modify chat widget."""
        admin_token = test_client.create_test_user("cw-read-admin", "CW Read Admin")
        admin_headers = create_auth_headers(admin_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, admin_token)
        widget_id = create_chat_widget(test_client, tenant_id, admin_headers, "Read Test")
        
        reader_token = test_client.create_test_user("cw-reader", "CW Reader")
        reader_headers = create_auth_headers(reader_token, use_cache=False)
        
        add_user_to_tenant(test_client, tenant_id, admin_headers, "cw-reader", "READER")
        
        test_client.put(
            ENDPOINT_CHAT_WIDGET_PRINCIPALS.format(tenant_id=tenant_id, chat_widget_id=widget_id),
            json={
                "principal_id": "cw-reader",
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_READ
            },
            headers=admin_headers
        )
        
        # Reader CAN view
        get_response = test_client.get(
            ENDPOINT_CHAT_WIDGET_DETAIL.format(tenant_id=tenant_id, chat_widget_id=widget_id),
            headers=reader_headers
        )
        assert get_response.status_code == status.HTTP_200_OK
        
        # Reader CAN list principals
        principals_response = test_client.get(
            ENDPOINT_CHAT_WIDGET_PRINCIPALS.format(tenant_id=tenant_id, chat_widget_id=widget_id),
            headers=reader_headers
        )
        assert principals_response.status_code == status.HTTP_200_OK
        
        # Reader CANNOT update
        update_response = test_client.patch(
            ENDPOINT_CHAT_WIDGET_DETAIL.format(tenant_id=tenant_id, chat_widget_id=widget_id),
            json={"name": "Hacked by Reader"},
            headers=reader_headers
        )
        assert update_response.status_code == status.HTTP_403_FORBIDDEN
        
        # Reader CANNOT delete
        delete_response = test_client.request(
            "DELETE",
            ENDPOINT_CHAT_WIDGET_DETAIL.format(tenant_id=tenant_id, chat_widget_id=widget_id),
            headers=reader_headers
        )
        assert delete_response.status_code == status.HTTP_403_FORBIDDEN
    
    def test_write_user_can_modify_but_not_delete_or_manage_principals(self, test_client: TestClient) -> None:
        """Test that WRITE role can modify but cannot delete or manage principals."""
        admin_token = test_client.create_test_user("cw-write-admin", "CW Write Admin")
        admin_headers = create_auth_headers(admin_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, admin_token)
        widget_id = create_chat_widget(test_client, tenant_id, admin_headers, "Write Test")
        
        writer_token = test_client.create_test_user("cw-writer", "CW Writer")
        writer_headers = create_auth_headers(writer_token, use_cache=False)
        
        add_user_to_tenant(test_client, tenant_id, admin_headers, "cw-writer", "READER")
        
        test_client.put(
            ENDPOINT_CHAT_WIDGET_PRINCIPALS.format(tenant_id=tenant_id, chat_widget_id=widget_id),
            json={
                "principal_id": "cw-writer",
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_WRITE
            },
            headers=admin_headers
        )
        
        # Writer CAN view
        get_response = test_client.get(
            ENDPOINT_CHAT_WIDGET_DETAIL.format(tenant_id=tenant_id, chat_widget_id=widget_id),
            headers=writer_headers
        )
        assert get_response.status_code == status.HTTP_200_OK
        
        # Writer CAN update
        update_response = test_client.patch(
            ENDPOINT_CHAT_WIDGET_DETAIL.format(tenant_id=tenant_id, chat_widget_id=widget_id),
            json={"name": "Updated by Writer"},
            headers=writer_headers
        )
        assert update_response.status_code == status.HTTP_200_OK
        
        # Writer CANNOT delete
        delete_response = test_client.request(
            "DELETE",
            ENDPOINT_CHAT_WIDGET_DETAIL.format(tenant_id=tenant_id, chat_widget_id=widget_id),
            headers=writer_headers
        )
        assert delete_response.status_code == status.HTTP_403_FORBIDDEN
        
        # Writer CANNOT manage principals
        add_principal_response = test_client.put(
            ENDPOINT_CHAT_WIDGET_PRINCIPALS.format(tenant_id=tenant_id, chat_widget_id=widget_id),
            json={
                "principal_id": "another-user",
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_READ
            },
            headers=writer_headers
        )
        assert add_principal_response.status_code == status.HTTP_403_FORBIDDEN
    
    def test_multiple_admins(self, test_client: TestClient) -> None:
        """Test that multiple users can have ADMIN role."""
        admin1_token = test_client.create_test_user("cw-admin-1", "CW Admin 1")
        admin1_headers = create_auth_headers(admin1_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, admin1_token)
        widget_id = create_chat_widget(test_client, tenant_id, admin1_headers, "Multi Admin Test")
        
        admin2_token = test_client.create_test_user("cw-admin-2", "CW Admin 2")
        admin2_headers = create_auth_headers(admin2_token, use_cache=False)
        
        add_user_to_tenant(test_client, tenant_id, admin1_headers, "cw-admin-2", "READER")
        
        test_client.put(
            ENDPOINT_CHAT_WIDGET_PRINCIPALS.format(tenant_id=tenant_id, chat_widget_id=widget_id),
            json={
                "principal_id": "cw-admin-2",
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_ADMIN
            },
            headers=admin1_headers
        )
        
        # Admin 2 can update
        update_response = test_client.patch(
            ENDPOINT_CHAT_WIDGET_DETAIL.format(tenant_id=tenant_id, chat_widget_id=widget_id),
            json={"name": "Updated by Admin 2"},
            headers=admin2_headers
        )
        assert update_response.status_code == status.HTTP_200_OK
        
        # Admin 2 can delete
        delete_response = test_client.request(
            "DELETE",
            ENDPOINT_CHAT_WIDGET_DETAIL.format(tenant_id=tenant_id, chat_widget_id=widget_id),
            headers=admin2_headers
        )
        assert delete_response.status_code == status.HTTP_204_NO_CONTENT
    
    def test_tenant_global_admin_bypasses_chat_widget_permissions(self, test_client: TestClient) -> None:
        """Test that tenant GLOBAL_ADMIN can access all chat widgets."""
        admin_token = test_client.create_test_user("cw-tenant-admin", "CW Tenant Admin")
        admin_headers = create_auth_headers(admin_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, admin_token)
        widget_id = create_chat_widget(test_client, tenant_id, admin_headers, "Global Admin Test")
        
        global_admin_token = test_client.create_test_user("cw-global-admin", "CW Global Admin")
        global_admin_headers = create_auth_headers(global_admin_token, use_cache=False)
        
        add_user_to_tenant(test_client, tenant_id, admin_headers, "cw-global-admin", "GLOBAL_ADMIN")
        
        # Global admin can view
        get_response = test_client.get(
            ENDPOINT_CHAT_WIDGET_DETAIL.format(tenant_id=tenant_id, chat_widget_id=widget_id),
            headers=global_admin_headers
        )
        assert get_response.status_code == status.HTTP_200_OK
        
        # Global admin can update
        update_response = test_client.patch(
            ENDPOINT_CHAT_WIDGET_DETAIL.format(tenant_id=tenant_id, chat_widget_id=widget_id),
            json={"name": "Updated by Global Admin"},
            headers=global_admin_headers
        )
        assert update_response.status_code == status.HTTP_200_OK
        
        # Global admin can delete
        delete_response = test_client.request(
            "DELETE",
            ENDPOINT_CHAT_WIDGET_DETAIL.format(tenant_id=tenant_id, chat_widget_id=widget_id),
            headers=global_admin_headers
        )
        assert delete_response.status_code == status.HTTP_204_NO_CONTENT
    
    def test_tenant_chat_widgets_admin_bypasses_permissions(self, test_client: TestClient) -> None:
        """Test that tenant CHAT_WIDGETS_ADMIN can access all chat widgets."""
        admin_token = test_client.create_test_user("cw-tenant-admin-2", "CW Tenant Admin 2")
        admin_headers = create_auth_headers(admin_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, admin_token)
        widget_id = create_chat_widget(test_client, tenant_id, admin_headers, "CW Admin Test")
        
        cw_admin_token = test_client.create_test_user("cw-widgets-admin", "CW Widgets Admin")
        cw_admin_headers = create_auth_headers(cw_admin_token, use_cache=False)
        
        add_user_to_tenant(test_client, tenant_id, admin_headers, "cw-widgets-admin", "CHAT_WIDGETS_ADMIN")
        
        # Chat widgets admin can view
        get_response = test_client.get(
            ENDPOINT_CHAT_WIDGET_DETAIL.format(tenant_id=tenant_id, chat_widget_id=widget_id),
            headers=cw_admin_headers
        )
        assert get_response.status_code == status.HTTP_200_OK
        
        # Chat widgets admin can update
        update_response = test_client.patch(
            ENDPOINT_CHAT_WIDGET_DETAIL.format(tenant_id=tenant_id, chat_widget_id=widget_id),
            json={"name": "Updated by CW Admin"},
            headers=cw_admin_headers
        )
        assert update_response.status_code == status.HTTP_200_OK
    
    def test_user_role_replacement(self, test_client: TestClient) -> None:
        """Test that setting a new role replaces the old one."""
        admin_token = test_client.create_test_user("cw-role-admin", "CW Role Admin")
        admin_headers = create_auth_headers(admin_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, admin_token)
        widget_id = create_chat_widget(test_client, tenant_id, admin_headers, "Role Replace Test")
        
        # Grant READ role
        test_client.put(
            ENDPOINT_CHAT_WIDGET_PRINCIPALS.format(tenant_id=tenant_id, chat_widget_id=widget_id),
            json={
                "principal_id": "test-user",
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_READ
            },
            headers=admin_headers
        )
        
        # Upgrade to WRITE role
        test_client.put(
            ENDPOINT_CHAT_WIDGET_PRINCIPALS.format(tenant_id=tenant_id, chat_widget_id=widget_id),
            json={
                "principal_id": "test-user",
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_WRITE
            },
            headers=admin_headers
        )
        
        # Verify user has WRITE role
        get_response = test_client.get(
            ENDPOINT_PRINCIPAL_DETAIL.format(
                tenant_id=tenant_id,
                chat_widget_id=widget_id,
                principal_id="test-user"
            ),
            headers=admin_headers
        )
        
        assert get_response.status_code == status.HTTP_200_OK
        assert ROLE_WRITE in get_response.json()["roles"]
    
    def test_removing_admin_role(self, test_client: TestClient, fake_redis_client: Any) -> None:
        """Test removing ADMIN role from a user."""
        admin_token = test_client.create_test_user("cw-remove-admin", "CW Remove Admin")
        admin_headers = create_auth_headers(admin_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, admin_token)
        widget_id = create_chat_widget(test_client, tenant_id, admin_headers, "Remove Admin Test")
        
        user_token = test_client.create_test_user("cw-temp-admin", "CW Temp Admin")
        user_headers = create_auth_headers(user_token, use_cache=False)
        
        add_user_to_tenant(test_client, tenant_id, admin_headers, "cw-temp-admin", "READER")
        
        # Grant ADMIN role
        test_client.put(
            ENDPOINT_CHAT_WIDGET_PRINCIPALS.format(tenant_id=tenant_id, chat_widget_id=widget_id),
            json={
                "principal_id": "cw-temp-admin",
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_ADMIN
            },
            headers=admin_headers
        )
        
        # User can update (has ADMIN)
        update_response1 = test_client.patch(
            ENDPOINT_CHAT_WIDGET_DETAIL.format(tenant_id=tenant_id, chat_widget_id=widget_id),
            json={"name": "Updated by Temp Admin"},
            headers=user_headers
        )
        assert update_response1.status_code == status.HTTP_200_OK
        
        # Remove ADMIN role
        delete_response = test_client.request(
            "DELETE",
            ENDPOINT_CHAT_WIDGET_PRINCIPALS.format(tenant_id=tenant_id, chat_widget_id=widget_id),
            json={
                "principal_id": "cw-temp-admin",
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_ADMIN
            },
            headers=admin_headers
        )
        assert delete_response.status_code == status.HTTP_204_NO_CONTENT
        
        # User can no longer update
        update_response2 = test_client.patch(
            ENDPOINT_CHAT_WIDGET_DETAIL.format(tenant_id=tenant_id, chat_widget_id=widget_id),
            json={"name": "Should Fail"},
            headers=user_headers
        )
        assert update_response2.status_code == status.HTTP_403_FORBIDDEN
