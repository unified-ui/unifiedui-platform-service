"""Unit tests for unifiedui/identity/extra_id/token.py - ExtraID Identity Token."""
import pytest

from unifiedui.identity.extra_id.token import ExtraIDIdentityTokenSerializer
from unifiedui.core.identity.providers import BaseIdentityToken
from unifiedui.core.identity.enums import IdenityProviderEnum


class TestExtraIDIdentityTokenSerializer:
    """Test suite for ExtraIDIdentityTokenSerializer."""

    def test_initialization(self):
        """Test token initialization."""
        token_str = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
        deserialized = {"oid": "user-123", "tid": "tenant-456"}
        
        token = ExtraIDIdentityTokenSerializer(token_str, deserialized)
        
        assert token.token == token_str
        assert token.deserialized_token == deserialized
        assert isinstance(token, BaseIdentityToken)

    def test_get_token(self):
        """Test getting the raw token string."""
        token_str = "test-token-123"
        token = ExtraIDIdentityTokenSerializer(token_str, {})
        
        assert token.get_token() == token_str

    def test_get_deserialized_token(self):
        """Test getting deserialized token dict."""
        deserialized = {"oid": "user-123", "name": "Test User"}
        token = ExtraIDIdentityTokenSerializer("token", deserialized)
        
        assert token.get_deserialized_token() == deserialized

    def test_get_id(self):
        """Test getting user ID from oid claim."""
        deserialized = {"oid": "user-abc-123"}
        token = ExtraIDIdentityTokenSerializer("token", deserialized)
        
        assert token.get_id() == "user-abc-123"

    def test_get_identity_tenant_id(self):
        """Test getting tenant ID from tid claim."""
        deserialized = {"tid": "tenant-xyz-789"}
        token = ExtraIDIdentityTokenSerializer("token", deserialized)
        
        assert token.get_identity_tenant_id() == "tenant-xyz-789"

    def test_get_identity_tenant_id_default(self):
        """Test getting tenant ID returns empty string when missing."""
        token = ExtraIDIdentityTokenSerializer("token", {})
        
        assert token.get_identity_tenant_id() == ""

    def test_get_display_name(self):
        """Test getting display name."""
        deserialized = {"name": "John Doe"}
        token = ExtraIDIdentityTokenSerializer("token", deserialized)
        
        assert token.get_display_name() == "John Doe"

    def test_get_display_name_default(self):
        """Test getting display name returns empty string when missing."""
        token = ExtraIDIdentityTokenSerializer("token", {})
        
        assert token.get_display_name() == ""

    def test_get_firstname_from_given_name(self):
        """Test getting firstname from given_name claim."""
        deserialized = {"given_name": "John", "name": "John Doe"}
        token = ExtraIDIdentityTokenSerializer("token", deserialized)
        
        assert token.get_firstname() == "John"

    def test_get_firstname_from_name_split(self):
        """Test getting firstname by splitting name when given_name missing."""
        deserialized = {"name": "Jane Smith"}
        token = ExtraIDIdentityTokenSerializer("token", deserialized)
        
        assert token.get_firstname() == "Jane"

    def test_get_firstname_from_name_no_space(self):
        """Test firstname returns empty when name has no space."""
        deserialized = {"name": "SingleName"}
        token = ExtraIDIdentityTokenSerializer("token", deserialized)
        
        assert token.get_firstname() == ""

    def test_get_firstname_default(self):
        """Test firstname returns empty string when all fields missing."""
        token = ExtraIDIdentityTokenSerializer("token", {})
        
        assert token.get_firstname() == ""

    def test_get_lastname_from_family_name(self):
        """Test getting lastname from family_name claim."""
        deserialized = {"family_name": "Doe", "name": "John Doe"}
        token = ExtraIDIdentityTokenSerializer("token", deserialized)
        
        assert token.get_lastname() == "Doe"

    def test_get_lastname_from_name_split(self):
        """Test getting lastname by splitting name when family_name missing."""
        deserialized = {"name": "Jane Smith"}
        token = ExtraIDIdentityTokenSerializer("token", deserialized)
        
        assert token.get_lastname() == "Smith"

    def test_get_lastname_from_name_multiple_parts(self):
        """Test lastname with multi-part name."""
        deserialized = {"name": "John von Neumann"}
        token = ExtraIDIdentityTokenSerializer("token", deserialized)
        
        assert token.get_lastname() == "von Neumann"

    def test_get_lastname_from_name_no_space(self):
        """Test lastname returns empty when name has no space."""
        deserialized = {"name": "SingleName"}
        token = ExtraIDIdentityTokenSerializer("token", deserialized)
        
        assert token.get_lastname() == ""

    def test_get_lastname_default(self):
        """Test lastname returns empty string when all fields missing."""
        token = ExtraIDIdentityTokenSerializer("token", {})
        
        assert token.get_lastname() == ""

    def test_get_mail(self):
        """Test getting email from mail claim."""
        deserialized = {"mail": "user@example.com"}
        token = ExtraIDIdentityTokenSerializer("token", deserialized)
        
        assert token.get_mail() == "user@example.com"

    def test_get_mail_default(self):
        """Test getting mail returns empty string when missing."""
        token = ExtraIDIdentityTokenSerializer("token", {})
        
        assert token.get_mail() == ""

    def test_get_identity_provider(self):
        """Test getting identity provider."""
        token = ExtraIDIdentityTokenSerializer("token", {})
        
        assert token.get_identity_provider() == IdenityProviderEnum.EXTRA_ID.value
        assert token.get_identity_provider() == "EXTRA_ID"

    def test_complete_token_with_all_fields(self):
        """Test token with all possible fields."""
        deserialized = {
            "oid": "user-123",
            "tid": "tenant-456",
            "name": "John Doe",
            "given_name": "John",
            "family_name": "Doe",
            "mail": "john.doe@example.com"
        }
        token = ExtraIDIdentityTokenSerializer("full-token", deserialized)
        
        assert token.get_id() == "user-123"
        assert token.get_identity_tenant_id() == "tenant-456"
        assert token.get_display_name() == "John Doe"
        assert token.get_firstname() == "John"
        assert token.get_lastname() == "Doe"
        assert token.get_mail() == "john.doe@example.com"
        assert token.get_identity_provider() == "EXTRA_ID"
