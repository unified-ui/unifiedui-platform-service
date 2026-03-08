"""Unit tests for unifiedui/schema/requests/custom_groups.py - Custom Groups Request Schemas."""

import pytest
from pydantic import ValidationError

from unifiedui.schema.requests.custom_groups import (
    CreateCustomGroupRequest,
    DeleteCustomGroupRoleRequest,
    DeletePrincipalRoleRequest,
    SetCustomGroupRoleRequest,
    SetPrincipalRoleRequest,
    UpdateCustomGroupRequest,
)


class TestCreateCustomGroupRequest:
    """Test suite for CreateCustomGroupRequest."""

    def test_valid_request(self):
        """Test creating a valid request."""
        request = CreateCustomGroupRequest(name="Test Group", description="A test group")
        assert request.name == "Test Group"
        assert request.description == "A test group"

    def test_name_required(self):
        """Test that name is required."""
        with pytest.raises(ValidationError) as exc_info:
            CreateCustomGroupRequest()
        assert "name" in str(exc_info.value)

    def test_description_optional(self):
        """Test that description is optional."""
        request = CreateCustomGroupRequest(name="Test")
        assert request.name == "Test"
        assert request.description is None


class TestUpdateCustomGroupRequest:
    """Test suite for UpdateCustomGroupRequest."""

    def test_all_fields_optional(self):
        """Test that all fields are optional."""
        request = UpdateCustomGroupRequest()
        assert request.name is None
        assert request.description is None

    def test_partial_update(self):
        """Test partial update."""
        request = UpdateCustomGroupRequest(name="New Name")
        assert request.name == "New Name"
        assert request.description is None


class TestSetPrincipalRoleRequest:
    """Test suite for SetPrincipalRoleRequest."""

    def test_valid_request(self):
        """Test creating a valid request."""
        request = SetPrincipalRoleRequest(principal_id="user-123", principal_type="IDENTITY_USER", role="READ")
        assert request.principal_id == "user-123"
        assert request.principal_type == "IDENTITY_USER"
        assert request.role == "READ"

    def test_invalid_principal_type(self):
        """Test validation error for invalid principal_type."""
        with pytest.raises(ValidationError) as exc_info:
            SetPrincipalRoleRequest(principal_id="user-123", principal_type="INVALID_TYPE", role="READ")
        error = exc_info.value.errors()[0]
        assert "principal_type" in str(error)
        assert "Invalid principal_type" in error["msg"]

    def test_invalid_role(self):
        """Test validation error for invalid role."""
        with pytest.raises(ValidationError) as exc_info:
            SetPrincipalRoleRequest(principal_id="user-123", principal_type="IDENTITY_USER", role="INVALID_ROLE")
        error = exc_info.value.errors()[0]
        assert "role" in str(error)
        assert "Invalid role" in error["msg"]

    def test_all_principal_types(self):
        """Test all valid principal types."""
        for principal_type in ["IDENTITY_USER", "IDENTITY_GROUP", "CUSTOM_GROUP"]:
            request = SetPrincipalRoleRequest(principal_id="test-id", principal_type=principal_type, role="WRITE")
            assert request.principal_type == principal_type

    def test_all_roles(self):
        """Test all valid roles."""
        for role in ["READ", "WRITE", "ADMIN"]:
            request = SetPrincipalRoleRequest(principal_id="test-id", principal_type="IDENTITY_USER", role=role)
            assert request.role == role


class TestDeletePrincipalRoleRequest:
    """Test suite for DeletePrincipalRoleRequest."""

    def test_valid_request(self):
        """Test creating a valid request."""
        request = DeletePrincipalRoleRequest(principal_id="user-123", principal_type="IDENTITY_GROUP", role="ADMIN")
        assert request.principal_id == "user-123"
        assert request.principal_type == "IDENTITY_GROUP"
        assert request.role == "ADMIN"

    def test_invalid_principal_type(self):
        """Test validation error for invalid principal_type."""
        with pytest.raises(ValidationError) as exc_info:
            DeletePrincipalRoleRequest(principal_id="user-123", principal_type="UNKNOWN_TYPE", role="READ")
        error = exc_info.value.errors()[0]
        assert "principal_type" in str(error)
        assert "Invalid principal_type" in error["msg"]

    def test_invalid_role(self):
        """Test validation error for invalid role."""
        with pytest.raises(ValidationError) as exc_info:
            DeletePrincipalRoleRequest(principal_id="user-123", principal_type="CUSTOM_GROUP", role="SUPERUSER")
        error = exc_info.value.errors()[0]
        assert "role" in str(error)
        assert "Invalid role" in error["msg"]


class TestSetCustomGroupRoleRequest:
    """Test suite for SetCustomGroupRoleRequest."""

    def test_valid_request(self):
        """Test creating a valid request."""
        request = SetCustomGroupRoleRequest(principal_id="principal-456", role="WRITE")
        assert request.principal_id == "principal-456"
        assert request.role == "WRITE"

    def test_invalid_role(self):
        """Test validation error for invalid role."""
        with pytest.raises(ValidationError) as exc_info:
            SetCustomGroupRoleRequest(principal_id="principal-456", role="OWNER")
        error = exc_info.value.errors()[0]
        assert "role" in str(error)
        assert "Invalid role" in error["msg"]


class TestDeleteCustomGroupRoleRequest:
    """Test suite for DeleteCustomGroupRoleRequest."""

    def test_valid_request(self):
        """Test creating a valid request."""
        request = DeleteCustomGroupRoleRequest(principal_id="principal-789", role="ADMIN")
        assert request.principal_id == "principal-789"
        assert request.role == "ADMIN"

    def test_invalid_role(self):
        """Test validation error for invalid role."""
        with pytest.raises(ValidationError) as exc_info:
            DeleteCustomGroupRoleRequest(principal_id="principal-789", role="MANAGER")
        error = exc_info.value.errors()[0]
        assert "role" in str(error)
        assert "Invalid role" in error["msg"]
