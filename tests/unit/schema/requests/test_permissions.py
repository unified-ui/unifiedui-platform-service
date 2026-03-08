"""Tests for permission request schemas."""

import pytest
from pydantic import ValidationError

from unifiedui.core.database.enums import PermissionActionEnum, PrincipalTypeEnum
from unifiedui.schema.requests.permissions import SetResourcePermissionRequest


class TestSetResourcePermissionRequest:
    """Test suite for SetResourcePermissionRequest schema."""

    def test_valid_request(self) -> None:
        """Should accept valid permission request."""
        req = SetResourcePermissionRequest(
            principal_id="user-123",
            principal_type=PrincipalTypeEnum.IDENTITY_USER,
            role=PermissionActionEnum.READ,
        )
        assert req.principal_id == "user-123"
        assert req.principal_type == PrincipalTypeEnum.IDENTITY_USER
        assert req.role == PermissionActionEnum.READ

    def test_all_roles(self) -> None:
        """Should accept all valid permission roles."""
        for role in PermissionActionEnum:
            req = SetResourcePermissionRequest(
                principal_id="user-1",
                principal_type=PrincipalTypeEnum.IDENTITY_USER,
                role=role,
            )
            assert req.role == role

    def test_all_principal_types(self) -> None:
        """Should accept all valid principal types."""
        for ptype in PrincipalTypeEnum:
            req = SetResourcePermissionRequest(
                principal_id="id-1",
                principal_type=ptype,
                role=PermissionActionEnum.ADMIN,
            )
            assert req.principal_type == ptype

    def test_empty_principal_id_rejected(self) -> None:
        """Should reject empty principal_id."""
        with pytest.raises(ValidationError):
            SetResourcePermissionRequest(
                principal_id="",
                principal_type=PrincipalTypeEnum.IDENTITY_USER,
                role=PermissionActionEnum.READ,
            )

    def test_missing_principal_id_rejected(self) -> None:
        """Should reject missing principal_id."""
        with pytest.raises(ValidationError):
            SetResourcePermissionRequest(
                principal_type=PrincipalTypeEnum.IDENTITY_USER,
                role=PermissionActionEnum.READ,
            )

    def test_invalid_role_rejected(self) -> None:
        """Should reject invalid role value."""
        with pytest.raises(ValidationError):
            SetResourcePermissionRequest(
                principal_id="user-1",
                principal_type=PrincipalTypeEnum.IDENTITY_USER,
                role="INVALID_ROLE",
            )

    def test_invalid_principal_type_rejected(self) -> None:
        """Should reject invalid principal_type."""
        with pytest.raises(ValidationError):
            SetResourcePermissionRequest(
                principal_id="user-1",
                principal_type="INVALID_TYPE",
                role=PermissionActionEnum.READ,
            )
