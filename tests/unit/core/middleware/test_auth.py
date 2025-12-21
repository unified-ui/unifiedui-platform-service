"""Unit tests for aihub/core/middleware/apis/v1/auth.py - Authentication middleware."""
import pytest
from unittest.mock import Mock, MagicMock, AsyncMock, patch
from fastapi import Request, HTTPException, status

from aihub.core.middleware.apis.v1.auth import authenticate, check_permissions
from aihub.core.identity.users import ContextIdentityUser
from aihub.core.database.enums import TenantPermissionEnum, PermissionActionEnum


class TestAuthenticateDecorator:
    """Test suite for @authenticate decorator."""
    
    @pytest.mark.asyncio
    async def test_authenticate_extracts_bearer_token(self):
        """Test that authenticate extracts Bearer token from Authorization header."""
        mock_request = Mock(spec=Request)
        mock_request.headers = {"Authorization": "Bearer test-token-123"}
        mock_request.path_params = {}
        
        mock_user = Mock()
        mock_identity = Mock()
        mock_identity.get_id.return_value = "user-123"
        mock_user.identity = mock_identity
        mock_user.tenants = []
        
        # Mock function to decorate
        @authenticate
        async def test_handler(request: Request):
            return "success"
        
        with patch('aihub.core.middleware.apis.v1.auth.ContextIdentityUser', return_value=mock_user):
            with patch('aihub.core.middleware.apis.v1.auth.get_db_client'):
                with patch('aihub.core.middleware.apis.v1.auth.get_cache_client'):
                    result = await test_handler(mock_request)
        
        assert result == "success"
        assert hasattr(mock_request.state, 'user')
        assert mock_request.state.user is mock_user
    
    @pytest.mark.asyncio
    async def test_authenticate_missing_authorization_header(self):
        """Test that missing Authorization header raises 401."""
        mock_request = Mock(spec=Request)
        mock_request.headers = {}
        
        @authenticate
        async def test_handler(request: Request):
            return "success"
        
        with pytest.raises(HTTPException) as exc_info:
            await test_handler(mock_request)
        
        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Authorization header missing" in exc_info.value.detail
    
    @pytest.mark.asyncio
    async def test_authenticate_invalid_authorization_scheme(self):
        """Test that non-Bearer authorization raises 401."""
        mock_request = Mock(spec=Request)
        mock_request.headers = {"Authorization": "Basic dXNlcjpwYXNz"}
        
        @authenticate
        async def test_handler(request: Request):
            return "success"
        
        with pytest.raises(HTTPException) as exc_info:
            await test_handler(mock_request)
        
        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Invalid authorization scheme" in exc_info.value.detail
    
    @pytest.mark.asyncio
    async def test_authenticate_empty_token(self):
        """Test that empty token raises 401."""
        mock_request = Mock(spec=Request)
        mock_request.headers = {"Authorization": "Bearer "}
        
        @authenticate
        async def test_handler(request: Request):
            return "success"
        
        with pytest.raises(HTTPException) as exc_info:
            await test_handler(mock_request)
        
        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Token is empty" in exc_info.value.detail
    
    @pytest.mark.asyncio
    async def test_authenticate_respects_cache_header(self):
        """Test that X-Use-Cache header is respected."""
        mock_request = Mock(spec=Request)
        mock_request.headers = {
            "Authorization": "Bearer test-token",
            "X-Use-Cache": "false"
        }
        mock_request.path_params = {}
        
        mock_user = Mock()
        mock_identity = Mock()
        mock_identity.get_id.return_value = "user-123"
        mock_user.identity = mock_identity
        mock_user.tenants = []
        
        @authenticate
        async def test_handler(request: Request):
            return "success"
        
        with patch('aihub.core.middleware.apis.v1.auth.ContextIdentityUser', return_value=mock_user) as mock_user_class:
            with patch('aihub.core.middleware.apis.v1.auth.get_db_client'):
                with patch('aihub.core.middleware.apis.v1.auth.get_cache_client'):
                    await test_handler(mock_request)
        
        # Check that use_cache=False was passed
        assert mock_request.state.use_cache is False
    
    @pytest.mark.asyncio
    async def test_authenticate_checks_tenant_access(self):
        """Test that tenant_id in path is validated."""
        mock_request = Mock(spec=Request)
        mock_request.headers = {"Authorization": "Bearer test-token"}
        mock_request.path_params = {"tenant_id": "tenant-123"}
        
        mock_user = Mock()
        mock_identity = Mock()
        mock_identity.get_id.return_value = "user-123"
        mock_user.identity = mock_identity
        mock_user.tenants = [
            {"tenant": {"id": "tenant-456"}}
        ]
        
        @authenticate
        async def test_handler(request: Request):
            return "success"
        
        with patch('aihub.core.middleware.apis.v1.auth.ContextIdentityUser', return_value=mock_user):
            with patch('aihub.core.middleware.apis.v1.auth.get_db_client'):
                with patch('aihub.core.middleware.apis.v1.auth.get_cache_client'):
                    with pytest.raises(HTTPException) as exc_info:
                        await test_handler(mock_request)
        
        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
        assert "does not have access to tenant" in exc_info.value.detail
    
    @pytest.mark.asyncio
    async def test_authenticate_allows_tenant_access(self):
        """Test that user with tenant access can proceed."""
        mock_request = Mock(spec=Request)
        mock_request.headers = {"Authorization": "Bearer test-token"}
        mock_request.path_params = {"tenant_id": "tenant-123"}
        
        mock_user = Mock()
        mock_identity = Mock()
        mock_identity.get_id.return_value = "user-123"
        mock_user.identity = mock_identity
        mock_user.tenants = [
            {"tenant": {"id": "tenant-123"}, "roles": ["READER"]}
        ]
        
        @authenticate
        async def test_handler(request: Request):
            return "success"
        
        with patch('aihub.core.middleware.apis.v1.auth.ContextIdentityUser', return_value=mock_user):
            with patch('aihub.core.middleware.apis.v1.auth.get_db_client'):
                with patch('aihub.core.middleware.apis.v1.auth.get_cache_client'):
                    result = await test_handler(mock_request)
        
        assert result == "success"
    
    @pytest.mark.asyncio
    async def test_authenticate_invalid_token_raises_401(self):
        """Test that invalid token raises 401."""
        mock_request = Mock(spec=Request)
        mock_request.headers = {"Authorization": "Bearer invalid-token"}
        mock_request.path_params = {}
        
        @authenticate
        async def test_handler(request: Request):
            return "success"
        
        with patch('aihub.core.middleware.apis.v1.auth.ContextIdentityUser', side_effect=ValueError("Invalid token")):
            with patch('aihub.core.middleware.apis.v1.auth.get_db_client'):
                with patch('aihub.core.middleware.apis.v1.auth.get_cache_client'):
                    with pytest.raises(HTTPException) as exc_info:
                        await test_handler(mock_request)
        
        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Invalid token" in exc_info.value.detail


class TestCheckPermissionsDecorator:
    """Test suite for @check_permissions decorator."""
    
    @pytest.mark.asyncio
    async def test_check_permissions_no_permissions_required(self):
        """Test that no permission check is performed when required_permissions is None."""
        mock_request = Mock(spec=Request)
        mock_request.state = Mock()
        mock_request.state.user = Mock()
        
        @check_permissions(entity="tenant", required_permissions=None)
        async def test_handler(request: Request):
            return "success"
        
        result = await test_handler(mock_request)
        assert result == "success"
    
    @pytest.mark.asyncio
    async def test_check_permissions_user_not_authenticated(self):
        """Test that unauthenticated request raises 401."""
        mock_request = Mock(spec=Request)
        mock_request.state = Mock(spec=[])  # No user attribute
        
        @check_permissions(entity="tenant", required_permissions=[TenantPermissionEnum.READER])
        async def test_handler(request: Request):
            return "success"
        
        with pytest.raises(HTTPException) as exc_info:
            await test_handler(mock_request)
        
        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert "User not authenticated" in exc_info.value.detail
    
    @pytest.mark.asyncio
    async def test_check_permissions_missing_tenant_id(self):
        """Test that missing tenant_id in path raises 400."""
        mock_request = Mock(spec=Request)
        mock_request.state = Mock()
        mock_request.state.user = Mock()
        mock_request.path_params = {}
        
        @check_permissions(entity="tenant", required_permissions=[TenantPermissionEnum.READER])
        async def test_handler(request: Request):
            return "success"
        
        with pytest.raises(HTTPException) as exc_info:
            await test_handler(mock_request)
        
        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "tenant_id not found" in exc_info.value.detail
    
    @pytest.mark.asyncio
    async def test_check_permissions_tenant_access_denied(self):
        """Test that user without tenant access is denied."""
        mock_user = Mock()
        mock_user.tenants = [
            {"tenant": {"id": "other-tenant"}, "roles": ["READER"]}
        ]
        
        mock_request = Mock(spec=Request)
        mock_request.state = Mock()
        mock_request.state.user = mock_user
        mock_request.path_params = {"tenant_id": "tenant-123"}
        
        @check_permissions(entity="tenant", required_permissions=[TenantPermissionEnum.READER])
        async def test_handler(request: Request):
            return "success"
        
        with pytest.raises(HTTPException) as exc_info:
            await test_handler(mock_request)
        
        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
    
    @pytest.mark.asyncio
    async def test_check_permissions_tenant_permission_granted(self):
        """Test that user with correct tenant permission is allowed."""
        mock_user = Mock()
        mock_user.tenants = [
            {"tenant": {"id": "tenant-123"}, "roles": [TenantPermissionEnum.READER.value]}
        ]
        
        mock_request = Mock(spec=Request)
        mock_request.state = Mock()
        mock_request.state.user = mock_user
        mock_request.path_params = {"tenant_id": "tenant-123"}
        
        @check_permissions(entity="tenant", required_permissions=[TenantPermissionEnum.READER])
        async def test_handler(request: Request):
            return "success"
        
        result = await test_handler(mock_request)
        assert result == "success"
    
    @pytest.mark.asyncio
    async def test_check_permissions_global_admin_bypass(self):
        """Test that GLOBAL_ADMIN bypasses resource-level checks."""
        mock_user = Mock()
        mock_user.identity.get_id.return_value = "user-123"
        mock_user.groups = []
        mock_user.custom_groups = []
        mock_user.tenants = [
            {"tenant": {"id": "tenant-123"}, "roles": [TenantPermissionEnum.GLOBAL_ADMIN.value]}
        ]
        
        mock_request = Mock(spec=Request)
        mock_request.state = Mock()
        mock_request.state.user = mock_user
        mock_request.path_params = {
            "tenant_id": "tenant-123",
            "application_id": "app-123"
        }
        
        @check_permissions(entity="application", required_permissions=[PermissionActionEnum.WRITE])
        async def test_handler(request: Request):
            return "success"
        
        result = await test_handler(mock_request)
        assert result == "success"
    
    @pytest.mark.asyncio
    async def test_check_permissions_unsupported_entity(self):
        """Test that unsupported entity type raises 500."""
        mock_user = Mock()
        mock_request = Mock(spec=Request)
        mock_request.state = Mock()
        mock_request.state.user = mock_user
        mock_request.path_params = {"tenant_id": "tenant-123"}
        
        @check_permissions(entity="unsupported_entity", required_permissions=[PermissionActionEnum.READ])
        async def test_handler(request: Request):
            return "success"
        
        with pytest.raises(HTTPException) as exc_info:
            await test_handler(mock_request)
        
        assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert "Unsupported entity type" in exc_info.value.detail
