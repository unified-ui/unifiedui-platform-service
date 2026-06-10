"""Unit tests for unifiedui/core/identity/enums.py"""

from enum import Enum

import pytest

from unifiedui.core.identity.enums import IdenityProviderEnum


class TestIdenityProviderEnum:
    """Test suite for IdenityProviderEnum."""

    def test_is_enum(self):
        """Test that IdenityProviderEnum is an Enum."""
        assert issubclass(IdenityProviderEnum, Enum)

    def test_is_string_enum(self):
        """Test that enum inherits from str."""
        assert issubclass(IdenityProviderEnum, str)

    def test_has_mock_value(self):
        """Test MOCK value exists."""
        assert hasattr(IdenityProviderEnum, "MOCK")
        assert IdenityProviderEnum.MOCK == "MOCK"

    def test_has_extra_id_value(self):
        """Test EXTRA_ID value exists."""
        assert hasattr(IdenityProviderEnum, "EXTRA_ID")
        assert IdenityProviderEnum.EXTRA_ID == "EXTRA_ID"

    def test_has_aws_cognito_value(self):
        """Test AWS_COGNITO value exists."""
        assert hasattr(IdenityProviderEnum, "AWS_COGNITO")
        assert IdenityProviderEnum.AWS_COGNITO == "AWS_COGNITO"

    def test_has_google_identity_value(self):
        """Test GOOGLE_IDENTITY value exists."""
        assert hasattr(IdenityProviderEnum, "GOOGLE_IDENTITY")
        assert IdenityProviderEnum.GOOGLE_IDENTITY == "GOOGLE_IDENTITY"

    def test_has_ldap_value(self):
        """Test LDAP value exists."""
        assert hasattr(IdenityProviderEnum, "LDAP")
        assert IdenityProviderEnum.LDAP == "LDAP"

    def test_has_okta_value(self):
        """Test OKTA value exists."""
        assert hasattr(IdenityProviderEnum, "OKTA")
        assert IdenityProviderEnum.OKTA == "OKTA"

    def test_has_oidc_value(self):
        """Test OIDC value exists."""
        assert hasattr(IdenityProviderEnum, "OIDC")
        assert IdenityProviderEnum.OIDC == "OIDC"

    def test_all_values_are_strings(self):
        """Test all enum values are strings."""
        for member in IdenityProviderEnum:
            assert isinstance(member.value, str)

    def test_enum_members_count(self):
        """Test the number of enum members."""
        assert len(IdenityProviderEnum) == 7

    def test_can_create_from_string(self):
        """Test enum can be created from string."""
        provider = IdenityProviderEnum("MOCK")
        assert provider == IdenityProviderEnum.MOCK

    def test_invalid_value_raises_error(self):
        """Test invalid value raises ValueError."""
        with pytest.raises(ValueError):
            IdenityProviderEnum("INVALID_PROVIDER")
