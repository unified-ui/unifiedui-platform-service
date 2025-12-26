"""Tests for tenant RBAC (Role-Based Access Control)."""
import uuid
from typing import Any
from fastapi import status
from starlette.testclient import TestClient

from unifiedui.core.database.enums import TenantRolesEnum, PrincipalTypeEnum
from tests.conftest import create_auth_headers


# API Endpoints
ENDPOINT_TENANTS = "/api/v1/tenants"
ENDPOINT_TENANT_DETAIL = "/api/v1/tenants/{tenant_id}"
ENDPOINT_TENANT_PRINCIPALS = "/api/v1/tenants/{tenant_id}/principals"
ENDPOINT_PRINCIPAL_DETAIL = "/api/v1/tenants/{tenant_id}/principals/{principal_id}"

# Common Test IDs
NON_EXISTENT_ID = "non-existent-id"

# Roles
ROLE_GLOBAL_ADMIN = TenantRolesEnum.GLOBAL_ADMIN.value
ROLE_READER = TenantRolesEnum.READER.value
ROLE_APPLICATIONS_ADMIN = TenantRolesEnum.APPLICATIONS_ADMIN.value

# Principal Types
PRINCIPAL_TYPE_USER = PrincipalTypeEnum.IDENTITY_USER.value
PRINCIPAL_TYPE_GROUP = PrincipalTypeEnum.IDENTITY_GROUP.value


class TestTenantRBAC:
    """Test suite for tenant role-based access control."""
    
    def test_creator_becomes_global_admin(self, test_client: TestClient) -> None:
        """Test that tenant creator automatically becomes GLOBAL_ADMIN."""
        # Create user and tenant
        user_token = test_client.create_test_user("creator-user", "Creator User")
        headers = create_auth_headers(user_token, use_cache=False)
        
        # Create tenant
        response = test_client.post(
            ENDPOINT_TENANTS,
            json={"name": "Test Tenant", "description": "Test"},
            headers=headers
        )
        
        assert response.status_code == status.HTTP_201_CREATED
        tenant_id = response.json()["id"]
        
        # Verify creator has GLOBAL_ADMIN role
        principals_response = test_client.get(
            ENDPOINT_PRINCIPAL_DETAIL.format(tenant_id=tenant_id, principal_id="creator-user"),
            headers=headers
        )
        
        assert principals_response.status_code == status.HTTP_200_OK
        data = principals_response.json()
        assert data["principal_id"] == "creator-user"
        assert ROLE_GLOBAL_ADMIN in data["roles"]
    
    def test_global_admin_can_update_tenant(self, test_client: TestClient) -> None:
        """Test that GLOBAL_ADMIN can update tenant."""
        # Create user and tenant
        user_token = test_client.create_test_user("admin-user", "Admin User")
        headers = create_auth_headers(user_token, use_cache=False)
        
        create_response = test_client.post(
            ENDPOINT_TENANTS,
            json={"name": "Original Name", "description": "Original"},
            headers=headers
        )
        tenant_id = create_response.json()["id"]
        
        # Update tenant
        update_response = test_client.patch(
            ENDPOINT_TENANT_DETAIL.format(tenant_id=tenant_id),
            json={"name": "Updated Name"},
            headers=headers
        )
        
        assert update_response.status_code == status.HTTP_200_OK
        assert update_response.json()["name"] == "Updated Name"
    
    def test_global_admin_can_delete_tenant(self, test_client: TestClient) -> None:
        """Test that GLOBAL_ADMIN can delete tenant."""
        # Create user and tenant
        user_token = test_client.create_test_user("delete-admin", "Delete Admin")
        headers = create_auth_headers(user_token, use_cache=False)
        
        create_response = test_client.post(
            ENDPOINT_TENANTS,
            json={"name": "To Delete", "description": "Will be deleted"},
            headers=headers
        )
        tenant_id = create_response.json()["id"]
        
        # Delete tenant
        delete_response = test_client.request(
            "DELETE",
            ENDPOINT_TENANT_DETAIL.format(tenant_id=tenant_id),
            headers=headers
        )
        
        assert delete_response.status_code == status.HTTP_204_NO_CONTENT
    
    def test_global_admin_can_manage_principals(self, test_client: TestClient) -> None:
        """Test that GLOBAL_ADMIN can add/remove principals."""
        # Create admin user and tenant
        admin_token = test_client.create_test_user("principal-admin", "Principal Admin")
        admin_headers = create_auth_headers(admin_token, use_cache=False)
        
        create_response = test_client.post(
            ENDPOINT_TENANTS,
            json={"name": "Principal Test", "description": "Test"},
            headers=admin_headers
        )
        tenant_id = create_response.json()["id"]
        
        # Add a role to another user
        add_response = test_client.put(
            ENDPOINT_TENANT_PRINCIPALS.format(tenant_id=tenant_id),
            json={
                "principal_id": "other-user",
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_READER
            },
            headers=admin_headers
        )
        
        assert add_response.status_code == status.HTTP_200_OK
        assert ROLE_READER in add_response.json()["roles"]
        
        # Remove the role
        delete_response = test_client.request(
            "DELETE",
            ENDPOINT_TENANT_PRINCIPALS.format(tenant_id=tenant_id),
            json={
                "principal_id": "other-user",
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_READER
            },
            headers=admin_headers
        )
        
        assert delete_response.status_code == status.HTTP_200_OK
    
    def test_non_member_cannot_access_tenant(self, test_client: TestClient) -> None:
        """Test that users without access cannot see/modify tenant."""
        # User A creates tenant
        user_a_token = test_client.create_test_user("user-a", "User A")
        headers_a = create_auth_headers(user_a_token)
        
        create_response = test_client.post(
            ENDPOINT_TENANTS,
            json={"name": "Private Tenant", "description": "Only for User A"},
            headers=headers_a
        )
        tenant_id = create_response.json()["id"]
        
        # User B tries to access
        user_b_token = test_client.create_test_user("user-b", "User B")
        headers_b = create_auth_headers(user_b_token)
        
        # User B cannot get tenant
        get_response = test_client.get(
            ENDPOINT_TENANT_DETAIL.format(tenant_id=tenant_id),
            headers=headers_b
        )
        assert get_response.status_code == status.HTTP_403_FORBIDDEN
        
        # User B cannot update tenant
        update_response = test_client.patch(
            ENDPOINT_TENANT_DETAIL.format(tenant_id=tenant_id),
            json={"name": "Hacked"},
            headers=headers_b
        )
        assert update_response.status_code == status.HTTP_403_FORBIDDEN
        
        # User B cannot delete tenant
        delete_response = test_client.request(
            "DELETE",
            ENDPOINT_TENANT_DETAIL.format(tenant_id=tenant_id),
            headers=headers_b
        )
        assert delete_response.status_code == status.HTTP_403_FORBIDDEN
        
        # User B cannot manage principals
        principal_response = test_client.put(
            ENDPOINT_TENANT_PRINCIPALS.format(tenant_id=tenant_id),
            json={
                "principal_id": "some-user",
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_READER
            },
            headers=headers_b
        )
        assert principal_response.status_code == status.HTTP_403_FORBIDDEN
    
    def test_reader_can_view_but_not_modify(self, test_client: TestClient) -> None:
        """Test that READER role can view but cannot modify tenant."""
        # Admin creates tenant
        admin_token = test_client.create_test_user("reader-admin", "Reader Admin")
        admin_headers = create_auth_headers(admin_token, use_cache=False)
        
        create_response = test_client.post(
            ENDPOINT_TENANTS,
            json={"name": "Reader Test", "description": "Test"},
            headers=admin_headers
        )
        tenant_id = create_response.json()["id"]
        
        # Create reader user
        reader_token = test_client.create_test_user("reader-user", "Reader User")
        reader_headers = create_auth_headers(reader_token, use_cache=False)
        
        # Admin adds reader with READER role
        test_client.put(
            ENDPOINT_TENANT_PRINCIPALS.format(tenant_id=tenant_id),
            json={
                "principal_id": "reader-user",
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_READER
            },
            headers=admin_headers
        )
        
        # Reader CAN view tenant
        get_response = test_client.get(
            ENDPOINT_TENANT_DETAIL.format(tenant_id=tenant_id),
            headers=reader_headers
        )
        assert get_response.status_code == status.HTTP_200_OK
        assert get_response.json()["id"] == tenant_id
        
        # Reader CAN list principals
        principals_response = test_client.get(
            ENDPOINT_TENANT_PRINCIPALS.format(tenant_id=tenant_id),
            headers=reader_headers
        )
        assert principals_response.status_code == status.HTTP_200_OK
        
        # Reader CANNOT update tenant (needs GLOBAL_ADMIN)
        update_response = test_client.patch(
            ENDPOINT_TENANT_DETAIL.format(tenant_id=tenant_id),
            json={"name": "Hacked by Reader"},
            headers=reader_headers
        )
        assert update_response.status_code == status.HTTP_403_FORBIDDEN
        
        # Reader CANNOT delete tenant (needs GLOBAL_ADMIN)
        delete_response = test_client.request(
            "DELETE",
            ENDPOINT_TENANT_DETAIL.format(tenant_id=tenant_id),
            headers=reader_headers
        )
        assert delete_response.status_code == status.HTTP_403_FORBIDDEN
        
        # Reader CANNOT manage principals (needs GLOBAL_ADMIN)
        add_principal_response = test_client.put(
            ENDPOINT_TENANT_PRINCIPALS.format(tenant_id=tenant_id),
            json={
                "principal_id": "another-user",
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_READER
            },
            headers=reader_headers
        )
        assert add_principal_response.status_code == status.HTTP_403_FORBIDDEN
    
    def test_applications_admin_can_view_but_not_modify_tenant(self, test_client: TestClient) -> None:
        """Test that APPLICATIONS_ADMIN role can view but cannot modify tenant structure."""
        # Admin creates tenant
        admin_token = test_client.create_test_user("app-admin", "App Admin")
        admin_headers = create_auth_headers(admin_token, use_cache=False)
        
        create_response = test_client.post(
            ENDPOINT_TENANTS,
            json={"name": "App Test", "description": "Test"},
            headers=admin_headers
        )
        tenant_id = create_response.json()["id"]
        
        # Create app admin user
        app_user_token = test_client.create_test_user("app-user", "App User")
        app_user_headers = create_auth_headers(app_user_token, use_cache=False)
        
        # Admin adds user with APPLICATIONS_ADMIN role
        test_client.put(
            ENDPOINT_TENANT_PRINCIPALS.format(tenant_id=tenant_id),
            json={
                "principal_id": "app-user",
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_APPLICATIONS_ADMIN
            },
            headers=admin_headers
        )
        
        # App admin CAN view tenant
        get_response = test_client.get(
            ENDPOINT_TENANT_DETAIL.format(tenant_id=tenant_id),
            headers=app_user_headers
        )
        assert get_response.status_code == status.HTTP_200_OK
        
        # App admin CANNOT update tenant (needs GLOBAL_ADMIN)
        update_response = test_client.patch(
            ENDPOINT_TENANT_DETAIL.format(tenant_id=tenant_id),
            json={"name": "Hacked"},
            headers=app_user_headers
        )
        assert update_response.status_code == status.HTTP_403_FORBIDDEN
        
        # App admin CANNOT delete tenant (needs GLOBAL_ADMIN)
        delete_response = test_client.request(
            "DELETE",
            ENDPOINT_TENANT_DETAIL.format(tenant_id=tenant_id),
            headers=app_user_headers
        )
        assert delete_response.status_code == status.HTTP_403_FORBIDDEN
        
        # App admin CANNOT manage principals (needs GLOBAL_ADMIN)
        principal_response = test_client.put(
            ENDPOINT_TENANT_PRINCIPALS.format(tenant_id=tenant_id),
            json={
                "principal_id": "another-user",
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_READER
            },
            headers=app_user_headers
        )
        assert principal_response.status_code == status.HTTP_403_FORBIDDEN
    
    def test_multiple_global_admins(self, test_client: TestClient) -> None:
        """Test that multiple users can be GLOBAL_ADMIN and all have full access."""
        # First admin creates tenant
        admin1_token = test_client.create_test_user("admin-1", "Admin 1")
        admin1_headers = create_auth_headers(admin1_token, use_cache=False)
        
        create_response = test_client.post(
            ENDPOINT_TENANTS,
            json={"name": "Multi Admin", "description": "Test"},
            headers=admin1_headers
        )
        tenant_id = create_response.json()["id"]
        
        # Create second admin user
        admin2_token = test_client.create_test_user("admin-2", "Admin 2")
        admin2_headers = create_auth_headers(admin2_token, use_cache=False)
        
        # First admin adds second admin with GLOBAL_ADMIN role
        add_response = test_client.put(
            ENDPOINT_TENANT_PRINCIPALS.format(tenant_id=tenant_id),
            json={
                "principal_id": "admin-2",
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_GLOBAL_ADMIN
            },
            headers=admin1_headers
        )
        assert add_response.status_code == status.HTTP_200_OK
        assert ROLE_GLOBAL_ADMIN in add_response.json()["roles"]
        
        # Second admin CAN update tenant
        update_response = test_client.patch(
            ENDPOINT_TENANT_DETAIL.format(tenant_id=tenant_id),
            json={"name": "Updated by Admin 2"},
            headers=admin2_headers
        )
        assert update_response.status_code == status.HTTP_200_OK
        assert update_response.json()["name"] == "Updated by Admin 2"
        
        # Second admin CAN manage principals
        add_user_response = test_client.put(
            ENDPOINT_TENANT_PRINCIPALS.format(tenant_id=tenant_id),
            json={
                "principal_id": "new-user",
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_READER
            },
            headers=admin2_headers
        )
        assert add_user_response.status_code == status.HTTP_200_OK
        
        # Second admin CAN delete tenant
        delete_response = test_client.request(
            "DELETE",
            ENDPOINT_TENANT_DETAIL.format(tenant_id=tenant_id),
            headers=admin2_headers
        )
        assert delete_response.status_code == status.HTTP_204_NO_CONTENT
    
    def test_user_with_multiple_roles_on_same_tenant(self, test_client: TestClient) -> None:
        """Test that a user can have multiple roles on the same tenant."""
        # Admin creates tenant
        admin_token = test_client.create_test_user("multi-role-admin", "Multi Role Admin")
        admin_headers = create_auth_headers(admin_token, use_cache=False)
        
        create_response = test_client.post(
            ENDPOINT_TENANTS,
            json={"name": "Multi Role", "description": "Test"},
            headers=admin_headers
        )
        tenant_id = create_response.json()["id"]
        
        # Create multi-role user
        multi_user_token = test_client.create_test_user("multi-user", "Multi User")
        
        # Admin adds READER role
        test_client.put(
            ENDPOINT_TENANT_PRINCIPALS.format(tenant_id=tenant_id),
            json={
                "principal_id": "multi-user",
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_READER
            },
            headers=admin_headers
        )
        
        # Admin adds APPLICATIONS_ADMIN role
        test_client.put(
            ENDPOINT_TENANT_PRINCIPALS.format(tenant_id=tenant_id),
            json={
                "principal_id": "multi-user",
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_APPLICATIONS_ADMIN
            },
            headers=admin_headers
        )
        
        # Admin adds CREDENTIALS_ADMIN role
        add_response = test_client.put(
            ENDPOINT_TENANT_PRINCIPALS.format(tenant_id=tenant_id),
            json={
                "principal_id": "multi-user",
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": "CREDENTIALS_ADMIN"
            },
            headers=admin_headers
        )
        
        # User should have all three roles
        assert add_response.status_code == status.HTTP_200_OK
        roles = add_response.json()["roles"]
        assert ROLE_READER in roles
        assert ROLE_APPLICATIONS_ADMIN in roles
        assert "CREDENTIALS_ADMIN" in roles
        assert len(roles) == 3
    
    def test_removing_global_admin_role(self, test_client: TestClient, fake_redis_client: Any) -> None:
        """Test that GLOBAL_ADMIN role can be removed (user loses admin access)."""
        # Admin creates tenant
        admin_token = test_client.create_test_user("demote-admin", "Demote Admin")
        admin_headers = create_auth_headers(admin_token, use_cache=False)
        
        create_response = test_client.post(
            ENDPOINT_TENANTS,
            json={"name": "Demote Test", "description": "Test"},
            headers=admin_headers
        )
        tenant_id = create_response.json()["id"]
        
        # Create second admin
        admin2_token = test_client.create_test_user("admin-to-demote", "Admin To Demote")
        admin2_headers = create_auth_headers(admin2_token, use_cache=False)
        
        # Give second user GLOBAL_ADMIN role
        test_client.put(
            ENDPOINT_TENANT_PRINCIPALS.format(tenant_id=tenant_id),
            json={
                "principal_id": "admin-to-demote",
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_GLOBAL_ADMIN
            },
            headers=admin_headers
        )
        
        # Verify second admin CAN update tenant
        update_response = test_client.patch(
            ENDPOINT_TENANT_DETAIL.format(tenant_id=tenant_id),
            json={"name": "Updated"},
            headers=admin2_headers
        )
        assert update_response.status_code == status.HTTP_200_OK
        
        # First admin removes GLOBAL_ADMIN role from second admin
        remove_response = test_client.request(
            "DELETE",
            ENDPOINT_TENANT_PRINCIPALS.format(tenant_id=tenant_id),
            json={
                "principal_id": "admin-to-demote",
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_GLOBAL_ADMIN
            },
            headers=admin_headers
        )
        assert remove_response.status_code == status.HTTP_200_OK
        assert ROLE_GLOBAL_ADMIN not in remove_response.json()["roles"]
        
        # Verify role was actually removed
        check_response = test_client.get(
            ENDPOINT_PRINCIPAL_DETAIL.format(tenant_id=tenant_id, principal_id="admin-to-demote"),
            headers=admin_headers
        )
        assert check_response.status_code == status.HTTP_200_OK
        roles_after = check_response.json()["roles"]
        assert ROLE_GLOBAL_ADMIN not in roles_after
        
        # Second user now has NO roles, so should get 403 when trying to access tenant
        update_response2 = test_client.patch(
            ENDPOINT_TENANT_DETAIL.format(tenant_id=tenant_id),
            json={"name": "Should Fail"},
            headers=admin2_headers
        )
        assert update_response2.status_code == status.HTTP_403_FORBIDDEN
    
    def test_custom_group_grants_permissions_to_members(self, test_client: TestClient, fake_redis_client: Any) -> None:
        """Test that users in a custom group inherit the group's permissions."""
        from unifiedui.core.database.models import Principal, CustomGroupMember
        from unifiedui.core.database.enums import PrincipalTypeEnum
        import uuid
        
        # Admin creates tenant (use unique user ID to avoid conflicts)
        admin_token = test_client.create_test_user(None, "CG Admin")  # Let it generate unique ID
        admin_headers = create_auth_headers(admin_token, use_cache=False)
        
        create_response = test_client.post(
            ENDPOINT_TENANTS,
            json={"name": "Custom Group Test", "description": "Test"},
            headers=admin_headers
        )
        tenant_id = create_response.json()["id"]
        
        # Create a custom group directly in DB (not via API)
        custom_group_id = str(uuid.uuid4())
        
        # Use test_client.db_client to write to the SAME DB that the API reads from!
        with test_client.db_client.get_session() as session:
            # Create custom group as Principal
            custom_group = Principal(
                tenant_id=tenant_id,
                principal_id=custom_group_id,
                principal_type=PrincipalTypeEnum.CUSTOM_GROUP.value,
                display_name="Admins Group",
                principal_name="Admins Group",
                description="Group of administrators"
            )
            session.add(custom_group)
            session.commit()
        
        # Create a regular user (not admin yet) - use unique ID
        regular_user_token = test_client.create_test_user(None, "CG User")  # Let it generate unique ID
        regular_user_headers = create_auth_headers(regular_user_token, use_cache=False)
        regular_user_id = regular_user_token.get_id()  # Get actual user ID from token
        
        # User CANNOT access tenant yet
        access_before = test_client.get(
            ENDPOINT_TENANT_DETAIL.format(tenant_id=tenant_id),
            headers=regular_user_headers
        )
        assert access_before.status_code == status.HTTP_403_FORBIDDEN
        
        # Add user to custom group directly in DB (not via API)
        # Grant GLOBAL_ADMIN role to the custom group directly in DB (not via API)
        from unifiedui.core.database.models import TenantMemberRole
        
        # Use test_client.db_client to write to the SAME DB that the API reads from!
        with test_client.db_client.get_session() as session:
            # First ensure user is in principals table
            user_principal = Principal(
                tenant_id=tenant_id,
                principal_id=regular_user_id,
                principal_type=PrincipalTypeEnum.IDENTITY_USER.value,
                display_name="CG User",
                principal_name="cg-user@test.com"
            )
            session.add(user_principal)
            session.flush()
            
            member = CustomGroupMember(
                id=str(uuid.uuid4()),
                tenant_id=tenant_id,
                custom_group_id=custom_group_id,
                principal_id=regular_user_id,  # Use actual user ID
                role="READ",
                created_by=admin_token.get_id(),
                updated_by=admin_token.get_id()
            )
            session.add(member)
            session.commit()
            
            # Custom group is already in principals table (created above)
            tenant_member_role = TenantMemberRole(
                id=str(uuid.uuid4()),
                tenant_id=tenant_id,
                principal_id=custom_group_id,
                role=ROLE_GLOBAL_ADMIN,
                created_by=admin_token.get_id(),
                updated_by=admin_token.get_id()
            )
            session.add(tenant_member_role)
            session.commit()
        
        # Clear ALL cache databases to ensure fresh data is loaded
        fake_redis_client.client.flushall()  # Clear all DBs, not just one
        
        # Now user CAN access tenant (through custom group membership)
        access_after = test_client.get(
            ENDPOINT_TENANT_DETAIL.format(tenant_id=tenant_id),
            headers=regular_user_headers
        )
        assert access_after.status_code == status.HTTP_200_OK
        
        # User CAN update tenant (has GLOBAL_ADMIN via custom group)
        update_response = test_client.patch(
            ENDPOINT_TENANT_DETAIL.format(tenant_id=tenant_id),
            json={"name": "Updated by Group Member"},
            headers=regular_user_headers
        )
        assert update_response.status_code == status.HTTP_200_OK
        assert update_response.json()["name"] == "Updated by Group Member"
        
        # User CAN manage principals (has GLOBAL_ADMIN via custom group)
        add_principal_response = test_client.put(
            ENDPOINT_TENANT_PRINCIPALS.format(tenant_id=tenant_id),
            json={
                "principal_id": "another-user",
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_READER
            },
            headers=regular_user_headers
        )
        assert add_principal_response.status_code == status.HTTP_200_OK
        
        # User CAN delete tenant (has GLOBAL_ADMIN via custom group)
        delete_response = test_client.request(
            "DELETE",
            ENDPOINT_TENANT_DETAIL.format(tenant_id=tenant_id),
            headers=regular_user_headers
        )
        assert delete_response.status_code == status.HTTP_204_NO_CONTENT
    
    def test_custom_group_with_reader_role_limits_members(self, test_client: TestClient, fake_redis_client: Any) -> None:
        """Test that custom group with READER role limits member capabilities."""
        from unifiedui.core.database.models import Principal, CustomGroupMember
        from unifiedui.core.database.enums import PrincipalTypeEnum
        import uuid
        
        # Admin creates tenant
        admin_token = test_client.create_test_user("cg-reader-admin", "CG Reader Admin")
        admin_headers = create_auth_headers(admin_token, use_cache=False)
        
        create_response = test_client.post(
            ENDPOINT_TENANTS,
            json={"name": "Reader Group Test", "description": "Test"},
            headers=admin_headers
        )
        tenant_id = create_response.json()["id"]
        
        # Create a custom group directly in DB (not via API)
        custom_group_id = str(uuid.uuid4())
        
        # Use test_client.db_client to write to the SAME DB that the API reads from!
        with test_client.db_client.get_session() as session:
            # Create custom group as Principal
            custom_group = Principal(
                tenant_id=tenant_id,
                principal_id=custom_group_id,
                principal_type=PrincipalTypeEnum.CUSTOM_GROUP.value,
                display_name="Readers Group",
                principal_name="Readers Group",
                description="Read-only users"
            )
            session.add(custom_group)
            session.commit()
        
        # Create a regular user
        reader_user_token = test_client.create_test_user("cg-reader-user", "CG Reader User")
        reader_user_headers = create_auth_headers(reader_user_token, use_cache=False)
        reader_user_id = reader_user_token.get_id()  # Get actual user ID from token
        
        # Add user to custom group and grant permissions directly in DB (not via API)
        from unifiedui.core.database.models import TenantMemberRole
        
        # Use test_client.db_client to write to the SAME DB that the API reads from!
        with test_client.db_client.get_session() as session:
            # First ensure user is in principals table
            user_principal = Principal(
                tenant_id=tenant_id,
                principal_id=reader_user_id,
                principal_type=PrincipalTypeEnum.IDENTITY_USER.value,
                display_name="CG Reader User",
                principal_name="cg-reader-user@test.com"
            )
            session.add(user_principal)
            session.flush()
            
            member = CustomGroupMember(
                id=str(uuid.uuid4()),
                tenant_id=tenant_id,
                custom_group_id=custom_group_id,
                principal_id=reader_user_id,  # Use actual user ID
                role="READ",
                created_by="cg-reader-admin",
                updated_by="cg-reader-admin"
            )
            session.add(member)
            session.commit()
            
            # Custom group is already in principals table (created above)
            tenant_member_role = TenantMemberRole(
                id=str(uuid.uuid4()),
                tenant_id=tenant_id,
                principal_id=custom_group_id,
                role=ROLE_READER,
                created_by="cg-reader-admin",
                updated_by="cg-reader-admin"
            )
            session.add(tenant_member_role)
            session.commit()  # Detach all objects from session
        
        # Clear ALL cache databases to ensure fresh data is loaded
        fake_redis_client.client.flushall()  # Clear all DBs, not just one
        
        # User CAN read tenant (has READER via custom group)
        get_response = test_client.get(
            ENDPOINT_TENANT_DETAIL.format(tenant_id=tenant_id),
            headers=reader_user_headers
        )
        assert get_response.status_code == status.HTTP_200_OK
        
        # User CANNOT update tenant (only READER, needs GLOBAL_ADMIN)
        update_response = test_client.patch(
            ENDPOINT_TENANT_DETAIL.format(tenant_id=tenant_id),
            json={"name": "Should Fail"},
            headers=reader_user_headers
        )
        assert update_response.status_code == status.HTTP_403_FORBIDDEN
        
        # User CANNOT delete tenant (only READER, needs GLOBAL_ADMIN)
        delete_response = test_client.request(
            "DELETE",
            ENDPOINT_TENANT_DETAIL.format(tenant_id=tenant_id),
            headers=reader_user_headers
        )
        assert delete_response.status_code == status.HTTP_403_FORBIDDEN
        
        # User CANNOT manage principals (only READER, needs GLOBAL_ADMIN)
        add_principal_response = test_client.put(
            ENDPOINT_TENANT_PRINCIPALS.format(tenant_id=tenant_id),
            json={
                "principal_id": "another-user",
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_READER
            },
            headers=reader_user_headers
        )
        assert add_principal_response.status_code == status.HTTP_403_FORBIDDEN
    
    def test_user_not_in_custom_group_has_no_group_permissions(self, test_client: TestClient, fake_redis_client: Any) -> None:
        """Test that users who are NOT in a custom group do not get the group's permissions."""
        from unifiedui.core.database.models import Principal, CustomGroupMember
        from unifiedui.core.database.enums import PrincipalTypeEnum
        import uuid
        
        # Admin creates tenant
        admin_token = test_client.create_test_user("cg-isolation-admin", "CG Isolation Admin")
        admin_headers = create_auth_headers(admin_token, use_cache=False)
        
        create_response = test_client.post(
            ENDPOINT_TENANTS,
            json={"name": "Isolation Test", "description": "Test"},
            headers=admin_headers
        )
        tenant_id = create_response.json()["id"]
        
        # Create a custom group directly in DB (not via API)
        custom_group_id = str(uuid.uuid4())
        
        # Use test_client.db_client to write to the SAME DB that the API reads from!
        with test_client.db_client.get_session() as session:
            # Create custom group as Principal
            custom_group = Principal(
                tenant_id=tenant_id,
                principal_id=custom_group_id,
                principal_type=PrincipalTypeEnum.CUSTOM_GROUP.value,
                display_name="Privileged Group",
                principal_name="Privileged Group",
                description="Only for select users"
            )
            session.add(custom_group)
            session.commit()
        
        # Create two users
        member_token = test_client.create_test_user("cg-member", "CG Member")
        non_member_token = test_client.create_test_user("cg-non-member", "CG Non-Member")
        member_user_id = member_token.get_id()  # Get actual user ID from token
        non_member_headers = create_auth_headers(non_member_token, use_cache=False)
        
        # Add only first user to custom group and grant permissions directly in DB (not via API)
        from unifiedui.core.database.models import TenantMemberRole
        
        # Use test_client.db_client to write to the SAME DB that the API reads from!
        with test_client.db_client.get_session() as session:
            # First ensure user is in principals table
            user_principal = Principal(
                tenant_id=tenant_id,
                principal_id=member_user_id,
                principal_type=PrincipalTypeEnum.IDENTITY_USER.value,
                display_name="CG Member",
                principal_name="cg-member@test.com"
            )
            session.add(user_principal)
            session.flush()
            
            member = CustomGroupMember(
                id=str(uuid.uuid4()),
                tenant_id=tenant_id,
                custom_group_id=custom_group_id,
                principal_id=member_user_id,  # Use actual user ID
                role="READ",
                created_by="cg-isolation-admin",
                updated_by="cg-isolation-admin"
            )
            session.add(member)
            session.commit()
            
            tenant_member_role = TenantMemberRole(
                id=str(uuid.uuid4()),
                tenant_id=tenant_id,
                principal_id=custom_group_id,
                role=ROLE_GLOBAL_ADMIN,
                created_by="cg-isolation-admin",
                updated_by="cg-isolation-admin"
            )
            session.add(tenant_member_role)
            session.commit()
        
        # Clear ALL cache databases to ensure fresh data is loaded
        fake_redis_client.client.flushall()  # Clear all DBs, not just one
        
        # Non-member CANNOT access tenant (not in the privileged group)
        access_response = test_client.get(
            ENDPOINT_TENANT_DETAIL.format(tenant_id=tenant_id),
            headers=non_member_headers
        )
        assert access_response.status_code == status.HTTP_403_FORBIDDEN
        
        # Non-member CANNOT update tenant
        update_response = test_client.patch(
            ENDPOINT_TENANT_DETAIL.format(tenant_id=tenant_id),
            json={"name": "Should Fail"},
            headers=non_member_headers
        )
        assert update_response.status_code == status.HTTP_403_FORBIDDEN
    
    def test_identity_group_grants_permissions_to_members(self, test_client: TestClient, fake_redis_client: Any) -> None:
        """Test that users in an identity group inherit the group's permissions."""
        # Define an identity group ID
        identity_group_id = "ig-admins-001"
        
        # Admin creates tenant (without being in the group)
        admin_token = test_client.create_test_user(None, "IG Admin")
        admin_headers = create_auth_headers(admin_token, use_cache=False)
        
        create_response = test_client.post(
            ENDPOINT_TENANTS,
            json={"name": "Identity Group Test", "description": "Test"},
            headers=admin_headers
        )
        tenant_id = create_response.json()["id"]
        
        # Create a user who is member of the identity group
        group_member_token = test_client.create_test_user(
            None, 
            "IG Member",
            idp_groups=[identity_group_id]  # User is in the identity group
        )
        group_member_headers = create_auth_headers(group_member_token, use_cache=False)
        
        # User CANNOT access tenant yet (group doesn't have permissions)
        access_before = test_client.get(
            ENDPOINT_TENANT_DETAIL.format(tenant_id=tenant_id),
            headers=group_member_headers
        )
        assert access_before.status_code == status.HTTP_403_FORBIDDEN
        
        # Admin grants GLOBAL_ADMIN role to the identity group
        grant_response = test_client.put(
            ENDPOINT_TENANT_PRINCIPALS.format(tenant_id=tenant_id),
            json={
                "principal_id": identity_group_id,
                "principal_type": PRINCIPAL_TYPE_GROUP,
                "role": ROLE_GLOBAL_ADMIN
            },
            headers=admin_headers
        )
        assert grant_response.status_code == status.HTTP_200_OK
        assert ROLE_GLOBAL_ADMIN in grant_response.json()["roles"]
        
        # Clear cache to ensure fresh data
        fake_redis_client.client.flushall()
        
        # Now user CAN access tenant (through identity group membership)
        access_after = test_client.get(
            ENDPOINT_TENANT_DETAIL.format(tenant_id=tenant_id),
            headers=group_member_headers
        )
        assert access_after.status_code == status.HTTP_200_OK
        
        # User CAN update tenant (has GLOBAL_ADMIN via identity group)
        update_response = test_client.patch(
            ENDPOINT_TENANT_DETAIL.format(tenant_id=tenant_id),
            json={"name": "Updated by Group Member"},
            headers=group_member_headers
        )
        assert update_response.status_code == status.HTTP_200_OK
        assert update_response.json()["name"] == "Updated by Group Member"
        
        # User CAN manage principals (has GLOBAL_ADMIN via identity group)
        add_principal_response = test_client.put(
            ENDPOINT_TENANT_PRINCIPALS.format(tenant_id=tenant_id),
            json={
                "principal_id": "another-user",
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_READER
            },
            headers=group_member_headers
        )
        assert add_principal_response.status_code == status.HTTP_200_OK
        
        # User CAN delete tenant (has GLOBAL_ADMIN via identity group)
        delete_response = test_client.request(
            "DELETE",
            ENDPOINT_TENANT_DETAIL.format(tenant_id=tenant_id),
            headers=group_member_headers
        )
        assert delete_response.status_code == status.HTTP_204_NO_CONTENT
    
    def test_identity_group_with_reader_role_limits_members(self, test_client: TestClient, fake_redis_client: Any) -> None:
        """Test that identity group with READER role limits member capabilities."""
        # Admin creates tenant
        admin_token = test_client.create_test_user("ig-reader-admin", "IG Reader Admin")
        admin_headers = create_auth_headers(admin_token, use_cache=False)
        
        create_response = test_client.post(
            ENDPOINT_TENANTS,
            json={"name": "Reader Identity Group Test", "description": "Test"},
            headers=admin_headers
        )
        tenant_id = create_response.json()["id"]
        
        # Define an identity group ID
        reader_group_id = "ig-readers-001"
        
        # Create a user who is member of the reader identity group
        reader_token = test_client.create_test_user(
            "ig-reader-user",
            "IG Reader User",
            idp_groups=[reader_group_id]
        )
        reader_headers = create_auth_headers(reader_token, use_cache=False)
        
        # Admin grants READER role to the identity group
        grant_response = test_client.put(
            ENDPOINT_TENANT_PRINCIPALS.format(tenant_id=tenant_id),
            json={
                "principal_id": reader_group_id,
                "principal_type": PRINCIPAL_TYPE_GROUP,
                "role": ROLE_READER
            },
            headers=admin_headers
        )
        assert grant_response.status_code == status.HTTP_200_OK
        assert ROLE_READER in grant_response.json()["roles"]
        
        # Clear cache
        fake_redis_client.client.flushall()
        
        # User CAN read tenant (has READER via identity group)
        get_response = test_client.get(
            ENDPOINT_TENANT_DETAIL.format(tenant_id=tenant_id),
            headers=reader_headers
        )
        assert get_response.status_code == status.HTTP_200_OK
        
        # User CANNOT update tenant (only READER, needs GLOBAL_ADMIN)
        update_response = test_client.patch(
            ENDPOINT_TENANT_DETAIL.format(tenant_id=tenant_id),
            json={"name": "Should Fail"},
            headers=reader_headers
        )
        assert update_response.status_code == status.HTTP_403_FORBIDDEN
        
        # User CANNOT delete tenant (only READER, needs GLOBAL_ADMIN)
        delete_response = test_client.request(
            "DELETE",
            ENDPOINT_TENANT_DETAIL.format(tenant_id=tenant_id),
            headers=reader_headers
        )
        assert delete_response.status_code == status.HTTP_403_FORBIDDEN
        
        # User CANNOT manage principals (only READER, needs GLOBAL_ADMIN)
        add_principal_response = test_client.put(
            ENDPOINT_TENANT_PRINCIPALS.format(tenant_id=tenant_id),
            json={
                "principal_id": "another-user",
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_READER
            },
            headers=reader_headers
        )
        assert add_principal_response.status_code == status.HTTP_403_FORBIDDEN
    
    def test_user_not_in_identity_group_has_no_group_permissions(self, test_client: TestClient, fake_redis_client: Any) -> None:
        """Test that users who are NOT in an identity group do not get the group's permissions."""
        # Admin creates tenant
        admin_token = test_client.create_test_user("ig-isolation-admin", "IG Isolation Admin")
        admin_headers = create_auth_headers(admin_token, use_cache=False)
        
        create_response = test_client.post(
            ENDPOINT_TENANTS,
            json={"name": "IG Isolation Test", "description": "Test"},
            headers=admin_headers
        )
        tenant_id = create_response.json()["id"]
        
        # Define an identity group ID
        privileged_group_id = "ig-privileged-001"
        
        # Create two users - one in the group, one not
        member_token = test_client.create_test_user(
            "ig-member",
            "IG Member",
            idp_groups=[privileged_group_id]
        )
        
        non_member_token = test_client.create_test_user(
            "ig-non-member",
            "IG Non-Member",
            idp_groups=[]  # Explicitly not in the group
        )
        non_member_headers = create_auth_headers(non_member_token, use_cache=False)
        
        # Admin grants GLOBAL_ADMIN role to the identity group
        grant_response = test_client.put(
            ENDPOINT_TENANT_PRINCIPALS.format(tenant_id=tenant_id),
            json={
                "principal_id": privileged_group_id,
                "principal_type": PRINCIPAL_TYPE_GROUP,
                "role": ROLE_GLOBAL_ADMIN
            },
            headers=admin_headers
        )
        assert grant_response.status_code == status.HTTP_200_OK
        
        # Clear cache
        fake_redis_client.client.flushall()
        
        # Non-member CANNOT access tenant (not in the privileged group)
        access_response = test_client.get(
            ENDPOINT_TENANT_DETAIL.format(tenant_id=tenant_id),
            headers=non_member_headers
        )
        assert access_response.status_code == status.HTTP_403_FORBIDDEN
        
        # Non-member CANNOT update tenant
        update_response = test_client.patch(
            ENDPOINT_TENANT_DETAIL.format(tenant_id=tenant_id),
            json={"name": "Should Fail"},
            headers=non_member_headers
        )
        assert update_response.status_code == status.HTTP_403_FORBIDDEN
    
    def test_user_with_multiple_identity_groups(self, test_client: TestClient, fake_redis_client: Any) -> None:
        """Test that a user can be in multiple identity groups and accumulate permissions."""
        # Admin creates tenant
        admin_token = test_client.create_test_user("ig-multi-admin", "IG Multi Admin")
        admin_headers = create_auth_headers(admin_token, use_cache=False)
        
        create_response = test_client.post(
            ENDPOINT_TENANTS,
            json={"name": "Multi IG Test", "description": "Test"},
            headers=admin_headers
        )
        tenant_id = create_response.json()["id"]
        
        # Define multiple identity groups
        reader_group_id = "ig-readers-002"
        apps_admin_group_id = "ig-apps-admins-001"
        
        # Create a user who is in multiple identity groups
        multi_group_token = test_client.create_test_user(
            "ig-multi-user",
            "IG Multi User",
            idp_groups=[reader_group_id, apps_admin_group_id]
        )
        multi_group_headers = create_auth_headers(multi_group_token, use_cache=False)
        
        # Admin grants different roles to different groups
        test_client.put(
            ENDPOINT_TENANT_PRINCIPALS.format(tenant_id=tenant_id),
            json={
                "principal_id": reader_group_id,
                "principal_type": PRINCIPAL_TYPE_GROUP,
                "role": ROLE_READER
            },
            headers=admin_headers
        )
        
        test_client.put(
            ENDPOINT_TENANT_PRINCIPALS.format(tenant_id=tenant_id),
            json={
                "principal_id": apps_admin_group_id,
                "principal_type": PRINCIPAL_TYPE_GROUP,
                "role": ROLE_APPLICATIONS_ADMIN
            },
            headers=admin_headers
        )
        
        # Clear cache
        fake_redis_client.client.flushall()
        
        # User CAN read tenant (has READER from first group)
        get_response = test_client.get(
            ENDPOINT_TENANT_DETAIL.format(tenant_id=tenant_id),
            headers=multi_group_headers
        )
        assert get_response.status_code == status.HTTP_200_OK
        
        # User still CANNOT update tenant (neither READER nor APPLICATIONS_ADMIN grants this)
        update_response = test_client.patch(
            ENDPOINT_TENANT_DETAIL.format(tenant_id=tenant_id),
            json={"name": "Should Fail"},
            headers=multi_group_headers
        )
        assert update_response.status_code == status.HTTP_403_FORBIDDEN
    
    def test_identity_group_and_direct_user_permissions_combine(self, test_client: TestClient, fake_redis_client: Any) -> None:
        """Test that user permissions from identity group and direct assignment combine."""
        # Admin creates tenant
        admin_token = test_client.create_test_user("ig-combo-admin", "IG Combo Admin")
        admin_headers = create_auth_headers(admin_token, use_cache=False)
        
        create_response = test_client.post(
            ENDPOINT_TENANTS,
            json={"name": "Combo Permissions Test", "description": "Test"},
            headers=admin_headers
        )
        tenant_id = create_response.json()["id"]
        
        # Define an identity group
        reader_group_id = "ig-readers-003"
        
        # Create a user who is in the identity group
        combo_user_token = test_client.create_test_user(
            "ig-combo-user",
            "IG Combo User",
            idp_groups=[reader_group_id]
        )
        combo_user_headers = create_auth_headers(combo_user_token, use_cache=False)
        combo_user_id = combo_user_token.get_id()
        
        # Admin grants READER role to the identity group
        test_client.put(
            ENDPOINT_TENANT_PRINCIPALS.format(tenant_id=tenant_id),
            json={
                "principal_id": reader_group_id,
                "principal_type": PRINCIPAL_TYPE_GROUP,
                "role": ROLE_READER
            },
            headers=admin_headers
        )
        
        # Admin also grants GLOBAL_ADMIN directly to the user
        test_client.put(
            ENDPOINT_TENANT_PRINCIPALS.format(tenant_id=tenant_id),
            json={
                "principal_id": combo_user_id,
                "principal_type": PRINCIPAL_TYPE_USER,
                "role": ROLE_GLOBAL_ADMIN
            },
            headers=admin_headers
        )
        
        # Clear cache
        fake_redis_client.client.flushall()
        
        # User CAN read tenant (from both sources)
        get_response = test_client.get(
            ENDPOINT_TENANT_DETAIL.format(tenant_id=tenant_id),
            headers=combo_user_headers
        )
        assert get_response.status_code == status.HTTP_200_OK
        
        # User CAN update tenant (has GLOBAL_ADMIN from direct assignment)
        update_response = test_client.patch(
            ENDPOINT_TENANT_DETAIL.format(tenant_id=tenant_id),
            json={"name": "Updated with Combined Permissions"},
            headers=combo_user_headers
        )
        assert update_response.status_code == status.HTTP_200_OK
        assert update_response.json()["name"] == "Updated with Combined Permissions"

