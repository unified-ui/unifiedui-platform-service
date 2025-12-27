"""Tests for ResourcePermissionsHandler."""
import uuid
import pytest
from unittest.mock import Mock, MagicMock, patch

from unifiedui.handlers.resource_permissions import (
    ResourcePermissionsHandler,
    RESOURCE_PERMISSION_CONFIG
)
from unifiedui.core.database.models import (
    Tenant, Principal, Application, ApplicationMember,
    Credential, CredentialMember, AutonomousAgent, AutonomousAgentMember,
    ChatWidget, ChatWidgetMember, Conversation, ConversationMember,
    DevelopmentPlatform, DevelopmentPlatformMember
)
from unifiedui.core.database.enums import (
    PermissionActionEnum, PrincipalTypeEnum, TenantRolesEnum
)


class TestResourcePermissionsHandlerConfig:
    """Tests for ResourcePermissionsHandler configuration."""
    
    def test_supported_resource_types(self):
        """Test that all expected resource types are configured."""
        expected_types = [
            "application", "autonomous_agent", "chat_widget",
            "conversation", "credential", "development_platform", "custom_group"
        ]
        for resource_type in expected_types:
            assert resource_type in RESOURCE_PERMISSION_CONFIG

    def test_invalid_resource_type_raises_error(self, test_db_client, test_cache_client):
        """Test that invalid resource type raises ValueError."""
        handler = ResourcePermissionsHandler(
            db_client=test_db_client,
            cache_client=test_cache_client
        )
        
        with pytest.raises(ValueError, match="Unknown resource type"):
            handler._get_config("invalid_type")


class TestResourcePermissionsHandlerOperations:
    """Tests for ResourcePermissionsHandler CRUD operations."""
    
    @pytest.fixture
    def handler(self, test_db_client, test_cache_client):
        """Create handler instance."""
        return ResourcePermissionsHandler(
            db_client=test_db_client,
            cache_client=test_cache_client
        )
    
    @pytest.fixture
    def setup_tenant_and_application(self, test_db_client, test_db_session):
        """Create a tenant and application for testing."""
        tenant_id = str(uuid.uuid4())
        user_id = f"test-user-{str(uuid.uuid4())[:8]}"
        application_id = str(uuid.uuid4())
        
        # Create tenant
        tenant = Tenant(
            id=tenant_id,
            name="Test Tenant",
            description="Test Description",
            created_by=user_id,
            updated_by=user_id
        )
        test_db_session.add(tenant)
        
        # Create principal for user
        principal = Principal(
            tenant_id=tenant_id,
            principal_id=user_id,
            principal_type=PrincipalTypeEnum.IDENTITY_USER.value,
            display_name="Test User",
            principal_name="test@example.com",
            mail="test@example.com"
        )
        test_db_session.add(principal)
        
        # Create application
        application = Application(
            id=application_id,
            tenant_id=tenant_id,
            name="Test Application",
            description="Test Description",
            type="N8N",
            config={},
            is_active=True,
            created_by=user_id,
            updated_by=user_id
        )
        test_db_session.add(application)
        test_db_session.commit()
        
        return {
            "tenant_id": tenant_id,
            "user_id": user_id,
            "application_id": application_id
        }
    
    def test_list_permissions_empty(self, handler, setup_tenant_and_application):
        """Test listing permissions when none exist."""
        data = setup_tenant_and_application
        
        result = handler.list_permissions(
            resource_type="application",
            tenant_id=data["tenant_id"],
            resource_id=data["application_id"],
            use_cache=False
        )
        
        assert result["resource_id"] == data["application_id"]
        assert result["resource_type"] == "application"
        assert result["tenant_id"] == data["tenant_id"]
        assert result["principals"] == []
    
    def test_list_permissions_resource_not_found(self, handler, setup_tenant_and_application):
        """Test listing permissions for non-existent resource."""
        data = setup_tenant_and_application
        
        with pytest.raises(ValueError, match="not found"):
            handler.list_permissions(
                resource_type="application",
                tenant_id=data["tenant_id"],
                resource_id="non-existent-id",
                use_cache=False
            )
    
    def test_set_permission_creates_new_member(self, handler, setup_tenant_and_application):
        """Test setting a permission creates a new member."""
        data = setup_tenant_and_application
        
        # Create mock user
        mock_user = Mock()
        mock_user.identity.get_id.return_value = data["user_id"]
        
        # Mock ensure_principal_exists to do nothing (principal already exists)
        with patch('unifiedui.handlers.resource_permissions.ensure_principal_exists'):
            result = handler.set_permission(
                resource_type="application",
                tenant_id=data["tenant_id"],
                resource_id=data["application_id"],
                principal_id=data["user_id"],
                principal_type=PrincipalTypeEnum.IDENTITY_USER.value,
                role=PermissionActionEnum.ADMIN,
                user_id=data["user_id"],
                user=mock_user
            )
        
        assert result["principal_id"] == data["user_id"]
        assert result["role"] == PermissionActionEnum.ADMIN.value
        assert result["resource_id"] == data["application_id"]
        
        # Verify permission is listed
        list_result = handler.list_permissions(
            resource_type="application",
            tenant_id=data["tenant_id"],
            resource_id=data["application_id"],
            use_cache=False
        )
        
        assert len(list_result["principals"]) == 1
        assert list_result["principals"][0]["principal_id"] == data["user_id"]
    
    def test_set_permission_updates_existing_member(self, handler, setup_tenant_and_application):
        """Test setting a permission updates existing member's role."""
        data = setup_tenant_and_application
        
        mock_user = Mock()
        mock_user.identity.get_id.return_value = data["user_id"]
        
        with patch('unifiedui.handlers.resource_permissions.ensure_principal_exists'):
            # Create with READ
            handler.set_permission(
                resource_type="application",
                tenant_id=data["tenant_id"],
                resource_id=data["application_id"],
                principal_id=data["user_id"],
                principal_type=PrincipalTypeEnum.IDENTITY_USER.value,
                role=PermissionActionEnum.READ,
                user_id=data["user_id"],
                user=mock_user
            )
            
            # Update to ADMIN
            result = handler.set_permission(
                resource_type="application",
                tenant_id=data["tenant_id"],
                resource_id=data["application_id"],
                principal_id=data["user_id"],
                principal_type=PrincipalTypeEnum.IDENTITY_USER.value,
                role=PermissionActionEnum.ADMIN,
                user_id=data["user_id"],
                user=mock_user
            )
        
        assert result["role"] == PermissionActionEnum.ADMIN.value
        
        # Verify only one permission exists
        list_result = handler.list_permissions(
            resource_type="application",
            tenant_id=data["tenant_id"],
            resource_id=data["application_id"],
            use_cache=False
        )
        
        assert len(list_result["principals"]) == 1
    
    def test_get_permission(self, handler, setup_tenant_and_application):
        """Test getting a specific principal's permission."""
        data = setup_tenant_and_application
        
        mock_user = Mock()
        mock_user.identity.get_id.return_value = data["user_id"]
        
        with patch('unifiedui.handlers.resource_permissions.ensure_principal_exists'):
            handler.set_permission(
                resource_type="application",
                tenant_id=data["tenant_id"],
                resource_id=data["application_id"],
                principal_id=data["user_id"],
                principal_type=PrincipalTypeEnum.IDENTITY_USER.value,
                role=PermissionActionEnum.WRITE,
                user_id=data["user_id"],
                user=mock_user
            )
        
        result = handler.get_permission(
            resource_type="application",
            tenant_id=data["tenant_id"],
            resource_id=data["application_id"],
            principal_id=data["user_id"]
        )
        
        assert result["principal_id"] == data["user_id"]
        assert PermissionActionEnum.WRITE.value in result["roles"]
    
    def test_get_permission_not_found(self, handler, setup_tenant_and_application):
        """Test getting permission for non-existent principal."""
        data = setup_tenant_and_application
        
        with pytest.raises(ValueError, match="No permissions found"):
            handler.get_permission(
                resource_type="application",
                tenant_id=data["tenant_id"],
                resource_id=data["application_id"],
                principal_id="non-existent-principal"
            )
    
    def test_delete_permission(self, handler, setup_tenant_and_application):
        """Test deleting a permission."""
        data = setup_tenant_and_application
        
        mock_user = Mock()
        mock_user.identity.get_id.return_value = data["user_id"]
        
        with patch('unifiedui.handlers.resource_permissions.ensure_principal_exists'):
            handler.set_permission(
                resource_type="application",
                tenant_id=data["tenant_id"],
                resource_id=data["application_id"],
                principal_id=data["user_id"],
                principal_type=PrincipalTypeEnum.IDENTITY_USER.value,
                role=PermissionActionEnum.ADMIN,
                user_id=data["user_id"],
                user=mock_user
            )
        
        # Delete the permission
        handler.delete_permission(
            resource_type="application",
            tenant_id=data["tenant_id"],
            resource_id=data["application_id"],
            principal_id=data["user_id"],
            principal_type=PrincipalTypeEnum.IDENTITY_USER.value,
            role=PermissionActionEnum.ADMIN.value
        )
        
        # Verify it's deleted
        list_result = handler.list_permissions(
            resource_type="application",
            tenant_id=data["tenant_id"],
            resource_id=data["application_id"],
            use_cache=False
        )
        
        assert len(list_result["principals"]) == 0
    
    def test_delete_permission_not_found(self, handler, setup_tenant_and_application):
        """Test deleting non-existent permission."""
        data = setup_tenant_and_application
        
        with pytest.raises(ValueError, match="not found"):
            handler.delete_permission(
                resource_type="application",
                tenant_id=data["tenant_id"],
                resource_id=data["application_id"],
                principal_id="non-existent-principal",
                principal_type=PrincipalTypeEnum.IDENTITY_USER.value,
                role=PermissionActionEnum.ADMIN.value
            )


class TestResourcePermissionsHandlerPermissionChecks:
    """Tests for permission checking functionality."""
    
    @pytest.fixture
    def handler(self, test_db_client, test_cache_client):
        """Create handler instance."""
        return ResourcePermissionsHandler(
            db_client=test_db_client,
            cache_client=test_cache_client
        )
    
    @pytest.fixture
    def setup_with_member(self, test_db_client, test_db_session):
        """Create tenant, application, and member for testing."""
        tenant_id = str(uuid.uuid4())
        user_id = f"test-user-{str(uuid.uuid4())[:8]}"
        application_id = str(uuid.uuid4())
        
        # Create tenant
        tenant = Tenant(
            id=tenant_id,
            name="Test Tenant",
            description="Test Description",
            created_by=user_id,
            updated_by=user_id
        )
        test_db_session.add(tenant)
        
        # Create principal
        principal = Principal(
            tenant_id=tenant_id,
            principal_id=user_id,
            principal_type=PrincipalTypeEnum.IDENTITY_USER.value,
            display_name="Test User",
            principal_name="test@example.com",
            mail="test@example.com"
        )
        test_db_session.add(principal)
        
        # Create application
        application = Application(
            id=application_id,
            tenant_id=tenant_id,
            name="Test Application",
            description="Test Description",
            type="N8N",
            config={},
            is_active=True,
            created_by=user_id,
            updated_by=user_id
        )
        test_db_session.add(application)
        
        # Create member with WRITE permission
        member = ApplicationMember(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            application_id=application_id,
            principal_id=user_id,
            role=PermissionActionEnum.WRITE.value,
            created_by=user_id,
            updated_by=user_id
        )
        test_db_session.add(member)
        test_db_session.commit()
        
        return {
            "tenant_id": tenant_id,
            "user_id": user_id,
            "application_id": application_id
        }
    
    def test_check_user_permission_has_permission(self, handler, setup_with_member):
        """Test checking permission when user has access."""
        data = setup_with_member
        
        # Create mock user
        mock_user = Mock()
        mock_user.identity.get_id.return_value = data["user_id"]
        mock_user.tenants = [{"tenant": {"id": data["tenant_id"]}, "roles": []}]
        mock_user.groups = []
        
        # User has WRITE, should have READ access
        has_access = handler.check_user_permission(
            resource_type="application",
            tenant_id=data["tenant_id"],
            resource_id=data["application_id"],
            user=mock_user,
            required_permission=PermissionActionEnum.READ
        )
        
        assert has_access is True
    
    def test_check_user_permission_no_permission(self, handler, setup_with_member):
        """Test checking permission when user lacks access."""
        data = setup_with_member
        
        # Create mock user with different ID
        mock_user = Mock()
        mock_user.identity.get_id.return_value = "different-user-id"
        mock_user.tenants = [{"tenant": {"id": data["tenant_id"]}, "roles": []}]
        mock_user.groups = []
        
        has_access = handler.check_user_permission(
            resource_type="application",
            tenant_id=data["tenant_id"],
            resource_id=data["application_id"],
            user=mock_user,
            required_permission=PermissionActionEnum.READ
        )
        
        assert has_access is False
    
    def test_check_user_permission_admin_hierarchy(self, handler, setup_with_member):
        """Test that WRITE permission doesn't grant ADMIN access."""
        data = setup_with_member
        
        mock_user = Mock()
        mock_user.identity.get_id.return_value = data["user_id"]
        mock_user.tenants = [{"tenant": {"id": data["tenant_id"]}, "roles": []}]
        mock_user.groups = []
        
        # User has WRITE, should NOT have ADMIN access
        has_access = handler.check_user_permission(
            resource_type="application",
            tenant_id=data["tenant_id"],
            resource_id=data["application_id"],
            user=mock_user,
            required_permission=PermissionActionEnum.ADMIN
        )
        
        assert has_access is False
    
    def test_check_user_permission_global_admin_bypass(self, handler, setup_with_member):
        """Test that GLOBAL_ADMIN bypasses resource-level permissions."""
        data = setup_with_member
        
        mock_user = Mock()
        mock_user.identity.get_id.return_value = "different-user-id"
        mock_user.tenants = [{
            "tenant": {"id": data["tenant_id"]},
            "roles": [TenantRolesEnum.GLOBAL_ADMIN.value]
        }]
        mock_user.groups = []
        
        # GLOBAL_ADMIN should have access even without member record
        has_access = handler.check_user_permission(
            resource_type="application",
            tenant_id=data["tenant_id"],
            resource_id=data["application_id"],
            user=mock_user,
            required_permission=PermissionActionEnum.ADMIN
        )
        
        assert has_access is True
    
    def test_check_user_permission_resource_admin_bypass(self, handler, setup_with_member):
        """Test that resource-specific admin bypasses resource-level permissions."""
        data = setup_with_member
        
        mock_user = Mock()
        mock_user.identity.get_id.return_value = "different-user-id"
        mock_user.tenants = [{
            "tenant": {"id": data["tenant_id"]},
            "roles": [TenantRolesEnum.APPLICATIONS_ADMIN.value]
        }]
        mock_user.groups = []
        
        # APPLICATIONS_ADMIN should have access
        has_access = handler.check_user_permission(
            resource_type="application",
            tenant_id=data["tenant_id"],
            resource_id=data["application_id"],
            user=mock_user,
            required_permission=PermissionActionEnum.ADMIN
        )
        
        assert has_access is True
    
    def test_is_user_admin_true(self, handler, setup_with_member):
        """Test is_user_admin returns True for admin users."""
        data = setup_with_member
        
        mock_user = Mock()
        mock_user.tenants = [{
            "tenant": {"id": data["tenant_id"]},
            "roles": [TenantRolesEnum.GLOBAL_ADMIN.value]
        }]
        
        is_admin = handler.is_user_admin(
            resource_type="application",
            tenant_id=data["tenant_id"],
            user=mock_user
        )
        
        assert is_admin is True
    
    def test_is_user_admin_false(self, handler, setup_with_member):
        """Test is_user_admin returns False for non-admin users."""
        data = setup_with_member
        
        mock_user = Mock()
        mock_user.tenants = [{
            "tenant": {"id": data["tenant_id"]},
            "roles": []
        }]
        
        is_admin = handler.is_user_admin(
            resource_type="application",
            tenant_id=data["tenant_id"],
            user=mock_user
        )
        
        assert is_admin is False


class TestResourcePermissionsHandlerRoleHierarchy:
    """Tests for role hierarchy logic."""
    
    def test_get_allowed_roles_read(self):
        """Test allowed roles for READ permission."""
        allowed = ResourcePermissionsHandler._get_allowed_roles(PermissionActionEnum.READ)
        
        assert PermissionActionEnum.READ.value in allowed
        assert PermissionActionEnum.WRITE.value in allowed
        assert PermissionActionEnum.ADMIN.value in allowed
    
    def test_get_allowed_roles_write(self):
        """Test allowed roles for WRITE permission."""
        allowed = ResourcePermissionsHandler._get_allowed_roles(PermissionActionEnum.WRITE)
        
        assert PermissionActionEnum.READ.value not in allowed
        assert PermissionActionEnum.WRITE.value in allowed
        assert PermissionActionEnum.ADMIN.value in allowed
    
    def test_get_allowed_roles_admin(self):
        """Test allowed roles for ADMIN permission."""
        allowed = ResourcePermissionsHandler._get_allowed_roles(PermissionActionEnum.ADMIN)
        
        assert PermissionActionEnum.READ.value not in allowed
        assert PermissionActionEnum.WRITE.value not in allowed
        assert PermissionActionEnum.ADMIN.value in allowed


class TestResourcePermissionsHandlerMultipleResourceTypes:
    """Tests for different resource types."""
    
    @pytest.fixture
    def handler(self, test_db_client, test_cache_client):
        """Create handler instance."""
        return ResourcePermissionsHandler(
            db_client=test_db_client,
            cache_client=test_cache_client
        )
    
    @pytest.fixture
    def setup_tenant_with_resources(self, test_db_client, test_db_session):
        """Create tenant with multiple resource types."""
        tenant_id = str(uuid.uuid4())
        user_id = f"test-user-{str(uuid.uuid4())[:8]}"
        
        # Create tenant
        tenant = Tenant(
            id=tenant_id,
            name="Test Tenant",
            description="Test Description",
            created_by=user_id,
            updated_by=user_id
        )
        test_db_session.add(tenant)
        
        # Create principal
        principal = Principal(
            tenant_id=tenant_id,
            principal_id=user_id,
            principal_type=PrincipalTypeEnum.IDENTITY_USER.value,
            display_name="Test User",
            principal_name="test@example.com"
        )
        test_db_session.add(principal)
        
        # Create resources
        credential_id = str(uuid.uuid4())
        credential = Credential(
            id=credential_id,
            tenant_id=tenant_id,
            name="Test Credential",
            description="Test",
            type="API_KEY",
            source="manual",
            credential_uri="test://uri",
            is_active=True,
            created_by=user_id,
            updated_by=user_id
        )
        test_db_session.add(credential)
        
        conversation_id = str(uuid.uuid4())
        conversation = Conversation(
            id=conversation_id,
            tenant_id=tenant_id,
            name="Test Conversation",
            description="Test",
            is_active=True,
            created_by=user_id,
            updated_by=user_id
        )
        test_db_session.add(conversation)
        
        test_db_session.commit()
        
        return {
            "tenant_id": tenant_id,
            "user_id": user_id,
            "credential_id": credential_id,
            "conversation_id": conversation_id
        }
    
    def test_list_permissions_credential(self, handler, setup_tenant_with_resources):
        """Test listing permissions for credential resource type."""
        data = setup_tenant_with_resources
        
        result = handler.list_permissions(
            resource_type="credential",
            tenant_id=data["tenant_id"],
            resource_id=data["credential_id"],
            use_cache=False
        )
        
        assert result["resource_type"] == "credential"
        assert result["resource_id"] == data["credential_id"]
    
    def test_list_permissions_conversation(self, handler, setup_tenant_with_resources):
        """Test listing permissions for conversation resource type."""
        data = setup_tenant_with_resources
        
        result = handler.list_permissions(
            resource_type="conversation",
            tenant_id=data["tenant_id"],
            resource_id=data["conversation_id"],
            use_cache=False
        )
        
        assert result["resource_type"] == "conversation"
        assert result["resource_id"] == data["conversation_id"]
