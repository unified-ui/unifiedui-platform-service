"""Tests for tags RBAC (Role-Based Access Control)."""
import uuid
from typing import Any
from fastapi import status
from starlette.testclient import TestClient

from unifiedui.core.database.enums import PermissionActionEnum, PrincipalTypeEnum
from unifiedui.core.database.models import (
    Application, ApplicationMember,
    AutonomousAgent, AutonomousAgentMember,
)
from tests.conftest import create_auth_headers


# API Endpoints
ENDPOINT_TENANTS = "/api/v1/tenants"
ENDPOINT_TAGS = "/api/v1/tenants/{tenant_id}/tags"
ENDPOINT_TAG_DETAIL = "/api/v1/tenants/{tenant_id}/tags/{tag_id}"
ENDPOINT_APPLICATIONS = "/api/v1/tenants/{tenant_id}/applications"
ENDPOINT_APPLICATION_TAGS = "/api/v1/tenants/{tenant_id}/applications/{application_id}/tags"
ENDPOINT_APPLICATION_PRINCIPALS = "/api/v1/tenants/{tenant_id}/applications/{application_id}/principals"
ENDPOINT_AUTONOMOUS_AGENTS = "/api/v1/tenants/{tenant_id}/autonomous-agents"
ENDPOINT_AUTONOMOUS_AGENT_TAGS = "/api/v1/tenants/{tenant_id}/autonomous-agents/{autonomous_agent_id}/tags"
ENDPOINT_AUTONOMOUS_AGENT_PRINCIPALS = "/api/v1/tenants/{tenant_id}/autonomous-agents/{autonomous_agent_id}/principals"

# Common Test IDs
NON_EXISTENT_ID = "non-existent-id"

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


def create_application_in_db(test_client: TestClient, tenant_id: str, user_id: str, name: str = "Test App") -> str:
    """Helper function to create an application directly in DB and return its ID."""
    app_id = str(uuid.uuid4())
    with test_client.db_client.get_session() as session:
        app = Application(
            id=app_id,
            tenant_id=tenant_id,
            name=name,
            description=f"Application {name}",
            type="N8N",
            config={},
            is_active=True,
            created_by=user_id,
            updated_by=user_id
        )
        session.add(app)
        session.commit()

        member = ApplicationMember(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            application_id=app_id,
            principal_id=user_id,
            principal_type=PrincipalTypeEnum.IDENTITY_USER,
            role=PermissionActionEnum.ADMIN,
            created_by=user_id,
            updated_by=user_id
        )
        session.add(member)
        session.commit()
    return app_id


def create_autonomous_agent_in_db(test_client: TestClient, tenant_id: str, user_id: str, name: str = "Test Agent") -> str:
    """Helper function to create an autonomous agent directly in DB and return its ID."""
    agent_id = str(uuid.uuid4())
    with test_client.db_client.get_session() as session:
        agent = AutonomousAgent(
            id=agent_id,
            tenant_id=tenant_id,
            name=name,
            description=f"Agent {name}",
            config={},
            is_active=True,
            created_by=user_id,
            updated_by=user_id
        )
        session.add(agent)
        session.commit()

        member = AutonomousAgentMember(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            autonomous_agent_id=agent_id,
            principal_id=user_id,
            principal_type=PrincipalTypeEnum.IDENTITY_USER,
            role=PermissionActionEnum.ADMIN,
            created_by=user_id,
            updated_by=user_id
        )
        session.add(member)
        session.commit()
    return agent_id


def add_user_to_application_in_db(
    test_client: TestClient,
    tenant_id: str,
    application_id: str,
    user_id: str,
    admin_id: str,
    role: PermissionActionEnum = PermissionActionEnum.READ
) -> None:
    """Helper function to add a user to an application directly in DB."""
    with test_client.db_client.get_session() as session:
        member = ApplicationMember(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            application_id=application_id,
            principal_id=user_id,
            principal_type=PrincipalTypeEnum.IDENTITY_USER,
            role=role,
            created_by=admin_id,
            updated_by=admin_id
        )
        session.add(member)
        session.commit()


def add_user_to_autonomous_agent_in_db(
    test_client: TestClient,
    tenant_id: str,
    autonomous_agent_id: str,
    user_id: str,
    admin_id: str,
    role: PermissionActionEnum = PermissionActionEnum.READ
) -> None:
    """Helper function to add a user to an autonomous agent directly in DB."""
    with test_client.db_client.get_session() as session:
        member = AutonomousAgentMember(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            autonomous_agent_id=autonomous_agent_id,
            principal_id=user_id,
            principal_type=PrincipalTypeEnum.IDENTITY_USER,
            role=role,
            created_by=admin_id,
            updated_by=admin_id
        )
        session.add(member)
        session.commit()


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


def create_tag(test_client: TestClient, tenant_id: str, headers: dict, name: str) -> str:
    """Helper function to create a tag and return its ID."""
    response = test_client.post(
        ENDPOINT_TAGS.format(tenant_id=tenant_id),
        json={"name": name},
        headers=headers
    )
    assert response.status_code == status.HTTP_201_CREATED
    return response.json()["id"]


class TestTagRBAC:
    """Test suite for tag role-based access control."""
    
    def test_any_tenant_member_can_list_tags(self, test_client: TestClient) -> None:
        """Test that any tenant member can list tags."""
        # Admin creates tenant
        admin_token = test_client.create_test_user("tag-admin-1", "Tag Admin 1")
        admin_headers = create_auth_headers(admin_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, admin_token)
        
        # Create some tags
        create_tag(test_client, tenant_id, admin_headers, "tag1")
        create_tag(test_client, tenant_id, admin_headers, "tag2")
        
        # Add regular user to tenant (only READER)
        user_token = test_client.create_test_user("tag-reader-1", "Tag Reader 1")
        user_headers = create_auth_headers(user_token, use_cache=False)
        add_user_to_tenant(test_client, tenant_id, admin_headers, "tag-reader-1", "READER")
        
        # Reader can list tags
        response = test_client.get(
            ENDPOINT_TAGS.format(tenant_id=tenant_id),
            headers=user_headers
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["total"] == 2
    
    def test_any_tenant_member_can_create_tags(self, test_client: TestClient) -> None:
        """Test that any tenant member can create tags."""
        # Admin creates tenant
        admin_token = test_client.create_test_user("tag-admin-2", "Tag Admin 2")
        admin_headers = create_auth_headers(admin_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, admin_token)
        
        # Add regular user to tenant
        user_token = test_client.create_test_user("tag-creator-1", "Tag Creator 1")
        user_headers = create_auth_headers(user_token, use_cache=False)
        add_user_to_tenant(test_client, tenant_id, admin_headers, "tag-creator-1", "READER")
        
        # Regular user can create tags
        response = test_client.post(
            ENDPOINT_TAGS.format(tenant_id=tenant_id),
            json={"name": "user-created-tag"},
            headers=user_headers
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.json()["name"] == "user-created-tag"
    
    def test_non_tenant_member_cannot_list_tags(self, test_client: TestClient) -> None:
        """Test that non-tenant members cannot list tags."""
        # Admin creates tenant with tags
        admin_token = test_client.create_test_user("tag-admin-3", "Tag Admin 3")
        admin_headers = create_auth_headers(admin_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, admin_token)
        create_tag(test_client, tenant_id, admin_headers, "private-tag")
        
        # Non-member tries to list tags
        outsider_token = test_client.create_test_user("tag-outsider-1", "Tag Outsider 1")
        outsider_headers = create_auth_headers(outsider_token, use_cache=False)
        
        response = test_client.get(
            ENDPOINT_TAGS.format(tenant_id=tenant_id),
            headers=outsider_headers
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN
    
    def test_non_tenant_member_cannot_create_tags(self, test_client: TestClient) -> None:
        """Test that non-tenant members cannot create tags."""
        # Admin creates tenant
        admin_token = test_client.create_test_user("tag-admin-4", "Tag Admin 4")
        admin_headers = create_auth_headers(admin_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, admin_token)
        
        # Non-member tries to create tag
        outsider_token = test_client.create_test_user("tag-outsider-2", "Tag Outsider 2")
        outsider_headers = create_auth_headers(outsider_token, use_cache=False)
        
        response = test_client.post(
            ENDPOINT_TAGS.format(tenant_id=tenant_id),
            json={"name": "hacker-tag"},
            headers=outsider_headers
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN
    
    def test_global_admin_can_delete_any_tag(self, test_client: TestClient) -> None:
        """Test that GLOBAL_ADMIN can delete any tag."""
        # Admin creates tenant
        admin_token = test_client.create_test_user("tag-admin-5", "Tag Admin 5")
        admin_headers = create_auth_headers(admin_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, admin_token)
        
        # Regular user creates a tag
        user_token = test_client.create_test_user("tag-creator-2", "Tag Creator 2")
        user_headers = create_auth_headers(user_token, use_cache=False)
        add_user_to_tenant(test_client, tenant_id, admin_headers, "tag-creator-2", "READER")
        tag_id = create_tag(test_client, tenant_id, user_headers, "user-tag")
        
        # GLOBAL_ADMIN can delete it
        response = test_client.delete(
            ENDPOINT_TAG_DETAIL.format(tenant_id=tenant_id, tag_id=tag_id),
            headers=admin_headers  # Tenant creator is GLOBAL_ADMIN
        )
        assert response.status_code == status.HTTP_204_NO_CONTENT
    
    def test_creator_can_delete_own_tag(self, test_client: TestClient) -> None:
        """Test that tag creator can delete their own tag."""
        # Admin creates tenant
        admin_token = test_client.create_test_user("tag-admin-6", "Tag Admin 6")
        admin_headers = create_auth_headers(admin_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, admin_token)
        
        # Regular user creates and deletes their own tag
        user_token = test_client.create_test_user("tag-creator-3", "Tag Creator 3")
        user_headers = create_auth_headers(user_token, use_cache=False)
        add_user_to_tenant(test_client, tenant_id, admin_headers, "tag-creator-3", "READER")
        tag_id = create_tag(test_client, tenant_id, user_headers, "my-tag")
        
        response = test_client.delete(
            ENDPOINT_TAG_DETAIL.format(tenant_id=tenant_id, tag_id=tag_id),
            headers=user_headers
        )
        assert response.status_code == status.HTTP_204_NO_CONTENT
    
    def test_non_creator_non_admin_cannot_delete_tag(self, test_client: TestClient) -> None:
        """Test that non-creator and non-GLOBAL_ADMIN cannot delete a tag."""
        # Admin creates tenant
        admin_token = test_client.create_test_user("tag-admin-7", "Tag Admin 7")
        admin_headers = create_auth_headers(admin_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, admin_token)
        
        # User A creates a tag
        user_a_token = test_client.create_test_user("tag-creator-4", "Tag Creator 4")
        user_a_headers = create_auth_headers(user_a_token, use_cache=False)
        add_user_to_tenant(test_client, tenant_id, admin_headers, "tag-creator-4", "READER")
        tag_id = create_tag(test_client, tenant_id, user_a_headers, "user-a-tag")
        
        # User B tries to delete User A's tag
        user_b_token = test_client.create_test_user("tag-deleter-1", "Tag Deleter 1")
        user_b_headers = create_auth_headers(user_b_token, use_cache=False)
        add_user_to_tenant(test_client, tenant_id, admin_headers, "tag-deleter-1", "READER")
        
        response = test_client.delete(
            ENDPOINT_TAG_DETAIL.format(tenant_id=tenant_id, tag_id=tag_id),
            headers=user_b_headers
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN


class TestResourceTagRBAC:
    """Test suite for resource tag management permissions."""
    
    def test_read_user_can_get_resource_tags(self, test_client: TestClient) -> None:
        """Test that READ permission allows getting resource tags."""
        # Admin creates tenant and application
        admin_token = test_client.create_test_user("res-tag-admin-1", "Resource Tag Admin 1")
        admin_headers = create_auth_headers(admin_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, admin_token)
        app_id = create_application_in_db(test_client, tenant_id, "res-tag-admin-1", "Test App")
        
        # Set tags on application
        test_client.put(
            ENDPOINT_APPLICATION_TAGS.format(tenant_id=tenant_id, application_id=app_id),
            json={"tags": ["tag1", "tag2"]},
            headers=admin_headers
        )
        
        # Add reader user
        reader_token = test_client.create_test_user("res-tag-reader-1", "Resource Tag Reader 1")
        reader_headers = create_auth_headers(reader_token, use_cache=False)
        add_user_to_tenant(test_client, tenant_id, admin_headers, "res-tag-reader-1", "READER")
        add_user_to_application_in_db(test_client, tenant_id, app_id, "res-tag-reader-1", "res-tag-admin-1", PermissionActionEnum.READ)
        
        # Reader can get tags
        response = test_client.get(
            ENDPOINT_APPLICATION_TAGS.format(tenant_id=tenant_id, application_id=app_id),
            headers=reader_headers
        )
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()["tags"]) == 2
    
    def test_read_user_cannot_set_resource_tags(self, test_client: TestClient) -> None:
        """Test that READ permission does not allow setting resource tags."""
        # Admin creates tenant and application
        admin_token = test_client.create_test_user("res-tag-admin-2", "Resource Tag Admin 2")
        admin_headers = create_auth_headers(admin_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, admin_token)
        app_id = create_application_in_db(test_client, tenant_id, "res-tag-admin-2", "Test App 2")
        
        # Add reader user
        reader_token = test_client.create_test_user("res-tag-reader-2", "Resource Tag Reader 2")
        reader_headers = create_auth_headers(reader_token, use_cache=False)
        add_user_to_tenant(test_client, tenant_id, admin_headers, "res-tag-reader-2", "READER")
        add_user_to_application_in_db(test_client, tenant_id, app_id, "res-tag-reader-2", "res-tag-admin-2", PermissionActionEnum.READ)
        
        # Reader cannot set tags
        response = test_client.put(
            ENDPOINT_APPLICATION_TAGS.format(tenant_id=tenant_id, application_id=app_id),
            json={"tags": ["hacker-tag"]},
            headers=reader_headers
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN
    
    def test_read_user_cannot_delete_resource_tags(self, test_client: TestClient) -> None:
        """Test that READ permission does not allow deleting resource tags."""
        # Admin creates tenant and application with tags
        admin_token = test_client.create_test_user("res-tag-admin-3", "Resource Tag Admin 3")
        admin_headers = create_auth_headers(admin_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, admin_token)
        app_id = create_application_in_db(test_client, tenant_id, "res-tag-admin-3", "Test App 3")
        
        test_client.put(
            ENDPOINT_APPLICATION_TAGS.format(tenant_id=tenant_id, application_id=app_id),
            json={"tags": ["tag1"]},
            headers=admin_headers
        )
        
        # Add reader user
        reader_token = test_client.create_test_user("res-tag-reader-3", "Resource Tag Reader 3")
        reader_headers = create_auth_headers(reader_token, use_cache=False)
        add_user_to_tenant(test_client, tenant_id, admin_headers, "res-tag-reader-3", "READER")
        add_user_to_application_in_db(test_client, tenant_id, app_id, "res-tag-reader-3", "res-tag-admin-3", PermissionActionEnum.READ)
        
        # Reader cannot delete tags
        response = test_client.delete(
            ENDPOINT_APPLICATION_TAGS.format(tenant_id=tenant_id, application_id=app_id),
            headers=reader_headers
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN
    
    def test_write_user_can_set_resource_tags(self, test_client: TestClient) -> None:
        """Test that WRITE permission allows setting resource tags."""
        # Admin creates tenant and application
        admin_token = test_client.create_test_user("res-tag-admin-4", "Resource Tag Admin 4")
        admin_headers = create_auth_headers(admin_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, admin_token)
        app_id = create_application_in_db(test_client, tenant_id, "res-tag-admin-4", "Test App 4")
        
        # Add writer user
        writer_token = test_client.create_test_user("res-tag-writer-1", "Resource Tag Writer 1")
        writer_headers = create_auth_headers(writer_token, use_cache=False)
        add_user_to_tenant(test_client, tenant_id, admin_headers, "res-tag-writer-1", "READER")
        add_user_to_application_in_db(test_client, tenant_id, app_id, "res-tag-writer-1", "res-tag-admin-4", PermissionActionEnum.WRITE)
        
        # Writer can set tags
        response = test_client.put(
            ENDPOINT_APPLICATION_TAGS.format(tenant_id=tenant_id, application_id=app_id),
            json={"tags": ["new-tag-1", "new-tag-2"]},
            headers=writer_headers
        )
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()["tags"]) == 2
    
    def test_write_user_can_delete_resource_tags(self, test_client: TestClient) -> None:
        """Test that WRITE permission allows deleting resource tags."""
        # Admin creates tenant and application with tags
        admin_token = test_client.create_test_user("res-tag-admin-5", "Resource Tag Admin 5")
        admin_headers = create_auth_headers(admin_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, admin_token)
        app_id = create_application_in_db(test_client, tenant_id, "res-tag-admin-5", "Test App 5")
        
        test_client.put(
            ENDPOINT_APPLICATION_TAGS.format(tenant_id=tenant_id, application_id=app_id),
            json={"tags": ["tag-to-delete"]},
            headers=admin_headers
        )
        
        # Add writer user
        writer_token = test_client.create_test_user("res-tag-writer-2", "Resource Tag Writer 2")
        writer_headers = create_auth_headers(writer_token, use_cache=False)
        add_user_to_tenant(test_client, tenant_id, admin_headers, "res-tag-writer-2", "READER")
        add_user_to_application_in_db(test_client, tenant_id, app_id, "res-tag-writer-2", "res-tag-admin-5", PermissionActionEnum.WRITE)
        
        # Writer can delete tags
        response = test_client.delete(
            ENDPOINT_APPLICATION_TAGS.format(tenant_id=tenant_id, application_id=app_id),
            headers=writer_headers
        )
        assert response.status_code == status.HTTP_204_NO_CONTENT
    
    def test_admin_user_can_manage_resource_tags(self, test_client: TestClient) -> None:
        """Test that ADMIN permission allows full tag management."""
        # Tenant creator creates tenant
        admin_token = test_client.create_test_user("res-tag-admin-6", "Resource Tag Admin 6")
        admin_headers = create_auth_headers(admin_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, admin_token)
        app_id = create_application_in_db(test_client, tenant_id, "res-tag-admin-6", "Test App 6")
        
        # Add resource admin user
        res_admin_token = test_client.create_test_user("res-tag-admin-user-1", "Resource Tag Admin User 1")
        res_admin_headers = create_auth_headers(res_admin_token, use_cache=False)
        add_user_to_tenant(test_client, tenant_id, admin_headers, "res-tag-admin-user-1", "READER")
        add_user_to_application_in_db(test_client, tenant_id, app_id, "res-tag-admin-user-1", "res-tag-admin-6", PermissionActionEnum.ADMIN)
        
        # Resource admin can set tags
        set_response = test_client.put(
            ENDPOINT_APPLICATION_TAGS.format(tenant_id=tenant_id, application_id=app_id),
            json={"tags": ["admin-tag"]},
            headers=res_admin_headers
        )
        assert set_response.status_code == status.HTTP_200_OK
        
        # Resource admin can get tags
        get_response = test_client.get(
            ENDPOINT_APPLICATION_TAGS.format(tenant_id=tenant_id, application_id=app_id),
            headers=res_admin_headers
        )
        assert get_response.status_code == status.HTTP_200_OK
        
        # Resource admin can delete tags
        delete_response = test_client.delete(
            ENDPOINT_APPLICATION_TAGS.format(tenant_id=tenant_id, application_id=app_id),
            headers=res_admin_headers
        )
        assert delete_response.status_code == status.HTTP_204_NO_CONTENT
    
    def test_global_admin_bypasses_resource_permissions(self, test_client: TestClient) -> None:
        """Test that tenant GLOBAL_ADMIN can manage any resource's tags."""
        # Admin creates tenant and application
        admin_token = test_client.create_test_user("res-tag-admin-7", "Resource Tag Admin 7")
        admin_headers = create_auth_headers(admin_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, admin_token)
        app_id = create_application_in_db(test_client, tenant_id, "res-tag-admin-7", "Test App 7")
        
        # Create another GLOBAL_ADMIN
        global_admin_token = test_client.create_test_user("res-tag-global-1", "Resource Tag Global 1")
        global_admin_headers = create_auth_headers(global_admin_token, use_cache=False)
        add_user_to_tenant(test_client, tenant_id, admin_headers, "res-tag-global-1", "GLOBAL_ADMIN")
        
        # Global admin can set tags without explicit permission
        set_response = test_client.put(
            ENDPOINT_APPLICATION_TAGS.format(tenant_id=tenant_id, application_id=app_id),
            json={"tags": ["global-admin-tag"]},
            headers=global_admin_headers
        )
        assert set_response.status_code == status.HTTP_200_OK
        
        # Global admin can delete tags
        delete_response = test_client.delete(
            ENDPOINT_APPLICATION_TAGS.format(tenant_id=tenant_id, application_id=app_id),
            headers=global_admin_headers
        )
        assert delete_response.status_code == status.HTTP_204_NO_CONTENT
    
    def test_applications_admin_bypasses_resource_permissions(self, test_client: TestClient) -> None:
        """Test that tenant APPLICATIONS_ADMIN can manage application tags."""
        # Admin creates tenant and application
        admin_token = test_client.create_test_user("res-tag-admin-8", "Resource Tag Admin 8")
        admin_headers = create_auth_headers(admin_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, admin_token)
        app_id = create_application_in_db(test_client, tenant_id, "res-tag-admin-8", "Test App 8")
        
        # Create APPLICATIONS_ADMIN
        apps_admin_token = test_client.create_test_user("res-tag-apps-admin-1", "Resource Tag Apps Admin 1")
        apps_admin_headers = create_auth_headers(apps_admin_token, use_cache=False)
        add_user_to_tenant(test_client, tenant_id, admin_headers, "res-tag-apps-admin-1", "APPLICATIONS_ADMIN")
        
        # Applications admin can set tags
        set_response = test_client.put(
            ENDPOINT_APPLICATION_TAGS.format(tenant_id=tenant_id, application_id=app_id),
            json={"tags": ["apps-admin-tag"]},
            headers=apps_admin_headers
        )
        assert set_response.status_code == status.HTTP_200_OK


class TestAutonomousAgentTagRBAC:
    """Test suite for autonomous agent tag permissions."""
    
    def test_write_user_can_set_agent_tags(self, test_client: TestClient) -> None:
        """Test that WRITE permission allows setting autonomous agent tags."""
        admin_token = test_client.create_test_user("agent-tag-admin-1", "Agent Tag Admin 1")
        admin_headers = create_auth_headers(admin_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, admin_token)
        agent_id = create_autonomous_agent_in_db(test_client, tenant_id, "agent-tag-admin-1", "Test Agent")
        
        # Add writer user
        writer_token = test_client.create_test_user("agent-tag-writer-1", "Agent Tag Writer 1")
        writer_headers = create_auth_headers(writer_token, use_cache=False)
        add_user_to_tenant(test_client, tenant_id, admin_headers, "agent-tag-writer-1", "READER")
        add_user_to_autonomous_agent_in_db(test_client, tenant_id, agent_id, "agent-tag-writer-1", "agent-tag-admin-1", PermissionActionEnum.WRITE)
        
        # Writer can set tags
        response = test_client.put(
            ENDPOINT_AUTONOMOUS_AGENT_TAGS.format(tenant_id=tenant_id, autonomous_agent_id=agent_id),
            json={"tags": ["ai-tag", "production"]},
            headers=writer_headers
        )
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()["tags"]) == 2
    
    def test_read_user_cannot_set_agent_tags(self, test_client: TestClient) -> None:
        """Test that READ permission does not allow setting autonomous agent tags."""
        admin_token = test_client.create_test_user("agent-tag-admin-2", "Agent Tag Admin 2")
        admin_headers = create_auth_headers(admin_token, use_cache=False)
        tenant_id = create_tenant_for_user(test_client, admin_token)
        agent_id = create_autonomous_agent_in_db(test_client, tenant_id, "agent-tag-admin-2", "Test Agent 2")
        
        # Add reader user
        reader_token = test_client.create_test_user("agent-tag-reader-1", "Agent Tag Reader 1")
        reader_headers = create_auth_headers(reader_token, use_cache=False)
        add_user_to_tenant(test_client, tenant_id, admin_headers, "agent-tag-reader-1", "READER")
        add_user_to_autonomous_agent_in_db(test_client, tenant_id, agent_id, "agent-tag-reader-1", "agent-tag-admin-2", PermissionActionEnum.READ)
        
        # Reader cannot set tags
        response = test_client.put(
            ENDPOINT_AUTONOMOUS_AGENT_TAGS.format(tenant_id=tenant_id, autonomous_agent_id=agent_id),
            json={"tags": ["hacker-tag"]},
            headers=reader_headers
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN
