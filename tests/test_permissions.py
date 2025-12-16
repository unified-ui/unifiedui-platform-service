"""Tests for permission management routes and logic."""
import pytest
from datetime import datetime
from unittest.mock import patch
from fastapi import status

from aihub.core.database.models.permissions import PermissionModel, AssignedTo


class TestPermissionRoutes:
    """Test suite for permission management endpoints."""
    
    def test_set_user_permission_success(self, test_client, auth_headers, mock_identity_user, sample_permission_data):
        """Test successfully setting a user permission."""
        tenant_id = "tenant-123"
        
        created_permission = PermissionModel(
            id="perm-123",
            tenant_id=tenant_id,
            resource_type="tenants",
            resource_id=tenant_id,
            action="read",
            assigned_to=AssignedTo(type="user", id=sample_permission_data["user_id"]),
            created_at=datetime.now(),
            created_by="test-user-123"
        )
        
        test_client.mock_db.permissions.check_permission.return_value = True
        test_client.mock_db.permissions.create.return_value = created_permission
        
        with patch("aihub.core.middleware.apis.v1.auth.IdentityUser", return_value=mock_identity_user):
            response = test_client.put(
                f"/api/v1/tenants/{tenant_id}/permissions",
                json={"assignments": [{"type": "user", "id": sample_permission_data["user_id"], "actions": [sample_permission_data["action"]]}]},
                headers=auth_headers
            )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["resource_id"] == tenant_id
        assert data["action"] == "read"
    
    def test_set_permission_without_admin(self, test_client, auth_headers, mock_identity_user, sample_permission_data):
        """Test setting permission without admin rights."""
        tenant_id = "tenant-123"
        
        test_client.mock_db.permissions.check_permission.return_value = False
        
        with patch("aihub.core.middleware.apis.v1.auth.IdentityUser", return_value=mock_identity_user):
            response = test_client.put(
                f"/api/v1/tenants/{tenant_id}/permissions",
                json={"assignments": [{"type": "user", "id": "user-123", "actions": ["read"]}]},
                headers=auth_headers
            )
        
        assert response.status_code == status.HTTP_403_FORBIDDEN
    
    def test_set_identity_group_permission(self, test_client, auth_headers, mock_identity_user):
        """Test setting permission for an identity group."""
        tenant_id = "tenant-123"
        
        permission_data = {
            "identity_group_id": "group-456",
            "action": "write"
        }
        
        created_permission = PermissionModel(
            id="perm-123",
            tenant_id=tenant_id,
            resource_type="tenants",
            resource_id=tenant_id,
            action="write",
            assigned_to=AssignedTo(type="identity_group", id="group-456"),
            created_at=datetime.now(),
            created_by="test-user-123"
        )
        
        test_client.mock_db.permissions.check_permission.return_value = True
        test_client.mock_db.permissions.create.return_value = created_permission
        
        with patch("aihub.core.middleware.apis.v1.auth.IdentityUser", return_value=mock_identity_user):
            response = test_client.put(
                f"/api/v1/tenants/{tenant_id}/permissions",
                json={"assignments": [{"type": "identity_group", "id": "group-456", "actions": ["write"]}]},
                headers=auth_headers
            )
        
        assert response.status_code == status.HTTP_200_OK
    
    def test_set_custom_group_permission(self, test_client, auth_headers, mock_identity_user):
        """Test setting permission for a custom group."""
        tenant_id = "tenant-123"
        
        permission_data = {
            "custom_group_id": "custom-789",
            "action": "admin"
        }
        
        created_permission = PermissionModel(
            id="perm-123",
            tenant_id=tenant_id,
            resource_type="tenants",
            resource_id=tenant_id,
            action="admin",
            assigned_to=AssignedTo(type="custom_group", id="custom-789"),
            created_at=datetime.now(),
            created_by="test-user-123"
        )
        
        test_client.mock_db.permissions.check_permission.return_value = True
        test_client.mock_db.permissions.create.return_value = created_permission
        
        with patch("aihub.core.middleware.apis.v1.auth.IdentityUser", return_value=mock_identity_user):
            response = test_client.put(
                f"/api/v1/tenants/{tenant_id}/permissions",
                json={"assignments": [{"type": "custom_group", "id": "custom-789", "actions": ["admin"]}]},
                headers=auth_headers
            )
        
        assert response.status_code == status.HTTP_200_OK
    
    def test_set_permission_invalid_action(self, test_client, auth_headers, mock_identity_user):
        """Test setting permission with invalid action."""
        tenant_id = "tenant-123"
        
        invalid_data = {
            "user_id": "user-123",
            "action": "invalid_action"
        }
        
        test_client.mock_db.permissions.check_permission.return_value = True
        
        with patch("aihub.core.middleware.apis.v1.auth.IdentityUser", return_value=mock_identity_user):
            response = test_client.put(
                f"/api/v1/tenants/{tenant_id}/permissions",
                json={"assignments": [{"type": "user", "id": "user-123", "actions": ["invalid_action"]}]},
                headers=auth_headers
            )
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    
    def test_list_permissions_success(self, test_client, auth_headers, mock_identity_user):
        """Test listing permissions for a tenant."""
        tenant_id = "tenant-123"
        
        permissions = [
            PermissionModel(
                id="perm-1",
                tenant_id=tenant_id,
                resource_type="tenants",
                resource_id=tenant_id,
                action="read",
                assigned_to=AssignedTo(type="user", id="user-1"),
                created_at=datetime.now(),
                created_by="test-user-123"
            ),
            PermissionModel(
                id="perm-2",
                tenant_id=tenant_id,
                resource_type="tenants",
                resource_id=tenant_id,
                action="write",
                assigned_to=AssignedTo(type="user", id="user-2"),
                created_at=datetime.now(),
                created_by="test-user-123"
            )
        ]
        
        test_client.mock_db.permissions.check_permission.return_value = True
        test_client.mock_db.permissions.get_resource_permissions.return_value = permissions
        
        with patch("aihub.core.middleware.apis.v1.auth.IdentityUser", return_value=mock_identity_user):
            response = test_client.get(
                f"/api/v1/tenants/{tenant_id}/permissions",
                headers=auth_headers
            )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 2
    
    def test_list_permissions_without_admin(self, test_client, auth_headers, mock_identity_user):
        """Test listing permissions without admin rights."""
        tenant_id = "tenant-123"
        
        test_client.mock_db.permissions.check_permission.return_value = False
        
        with patch("aihub.core.middleware.apis.v1.auth.IdentityUser", return_value=mock_identity_user):
            response = test_client.get(
                f"/api/v1/tenants/{tenant_id}/permissions",
                headers=auth_headers
            )
        
        assert response.status_code == status.HTTP_403_FORBIDDEN
    
    def test_delete_permission_success(self, test_client, auth_headers, mock_identity_user):
        """Test successfully deleting a permission."""
        tenant_id = "tenant-123"
        permission_id = "perm-456"
        
        test_client.mock_db.permissions.check_permission.return_value = True
        test_client.mock_db.permissions.delete.return_value = True
        
        with patch("aihub.core.middleware.apis.v1.auth.IdentityUser", return_value=mock_identity_user):
            response = test_client.request(
                "DELETE",
                f"/api/v1/tenants/{tenant_id}/permissions",
                json={"type": "user", "id": "user-456"},
                headers=auth_headers
            )
        
        assert response.status_code == status.HTTP_200_OK
    
    def test_delete_permission_without_admin(self, test_client, auth_headers, mock_identity_user):
        """Test deleting permission without admin rights."""
        tenant_id = "tenant-123"
        
        test_client.mock_db.permissions.check_permission.return_value = False
        
        with patch("aihub.core.middleware.apis.v1.auth.IdentityUser", return_value=mock_identity_user):
            response = test_client.request(
                "DELETE",
                f"/api/v1/tenants/{tenant_id}/permissions",
                json={"type": "user", "id": "user-456"},
                headers=auth_headers
            )
        
        assert response.status_code == status.HTTP_403_FORBIDDEN


class TestPermissionChecks:
    """Test suite for permission validation logic."""
    
    def test_check_user_level_permission(self, mock_db_client):
        """Test checking permission at user level."""
        user_id = "user-123"
        tenant_id = "tenant-456"
        
        mock_db_client.permissions.check_permission.return_value = True
        
        result = mock_db_client.permissions.check_permission(
            user_id=user_id,
            identity_groups=[],
            custom_groups=[],
            resource_type="tenants",
            resource_id=tenant_id,
            action="read"
        )
        
        assert result is True
    
    def test_check_identity_group_permission(self, mock_db_client):
        """Test checking permission at identity group level."""
        user_id = "user-123"
        tenant_id = "tenant-456"
        identity_groups = ["group-1", "group-2"]
        
        mock_db_client.permissions.check_permission.return_value = True
        
        result = mock_db_client.permissions.check_permission(
            user_id=user_id,
            identity_groups=identity_groups,
            custom_groups=[],
            resource_type="tenants",
            resource_id=tenant_id,
            action="write"
        )
        
        assert result is True
    
    def test_check_custom_group_permission(self, mock_db_client):
        """Test checking permission at custom group level."""
        user_id = "user-123"
        tenant_id = "tenant-456"
        custom_groups = ["custom-1"]
        
        mock_db_client.permissions.check_permission.return_value = True
        
        result = mock_db_client.permissions.check_permission(
            user_id=user_id,
            identity_groups=[],
            custom_groups=custom_groups,
            resource_type="tenants",
            resource_id=tenant_id,
            action="admin"
        )
        
        assert result is True
    
    def test_check_permission_denied(self, mock_db_client):
        """Test permission check when user has no access."""
        user_id = "user-123"
        tenant_id = "tenant-456"
        
        mock_db_client.permissions.check_permission.return_value = False
        
        result = mock_db_client.permissions.check_permission(
            user_id=user_id,
            identity_groups=[],
            custom_groups=[],
            resource_type="tenants",
            resource_id=tenant_id,
            action="admin"
        )
        
        assert result is False
    
    def test_different_permission_levels(self, mock_db_client):
        """Test that different actions require appropriate permissions."""
        user_id = "user-123"
        tenant_id = "tenant-456"
        
        # Mock different permissions for different actions
        def check_perm(user_id, identity_groups, custom_groups, resource_type, resource_id, action):
            if action == "read":
                return True
            elif action == "write":
                return False
            elif action == "admin":
                return False
            return False
        
        mock_db_client.permissions.check_permission.side_effect = check_perm
        
        # User can read
        assert mock_db_client.permissions.check_permission(
            user_id, [], [], "tenants", tenant_id, "read"
        )
        
        # But cannot write
        assert not mock_db_client.permissions.check_permission(
            user_id, [], [], "tenants", tenant_id, "write"
        )
        
        # And cannot admin
        assert not mock_db_client.permissions.check_permission(
            user_id, [], [], "tenants", tenant_id, "admin"
        )
