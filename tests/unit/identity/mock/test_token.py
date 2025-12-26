"""Unit tests for unifiedui/identity/mock/token.py - MockIdentityToken."""
import pytest
import jwt
import time

from unifiedui.identity.mock.token import MockIdentityToken
from unifiedui.core.identity.providers import BaseIdentityToken
from unifiedui.core.identity.enums import IdenityProviderEnum


class TestMockIdentityToken:
    """Test suite for MockIdentityToken."""
    
    def test_is_base_identity_token(self):
        """Test that MockIdentityToken extends BaseIdentityToken."""
        token = MockIdentityToken(user_id="test-user-123")
        assert isinstance(token, BaseIdentityToken)
    
    def test_initialization_with_minimal_params(self):
        """Test initialization with only user_id."""
        token = MockIdentityToken(user_id="user-123")
        assert token.get_id() == "user-123"
    
    def test_initialization_with_all_params(self):
        """Test initialization with all parameters."""
        token = MockIdentityToken(
            user_id="user-123",
            name="John Doe",
            mail="john@example.com",
            idp_groups=["group-1", "group-2"]
        )
        assert token.get_id() == "user-123"
        assert token.get_display_name() == "John Doe"
        assert token.get_mail() == "john@example.com"
        assert token.get_groups() == ["group-1", "group-2"]
    
    def test_get_id(self):
        """Test get_id returns user_id."""
        token = MockIdentityToken(user_id="test-user")
        assert token.get_id() == "test-user"
    
    def test_get_identity_tenant_id(self):
        """Test get_identity_tenant_id returns tenant ID."""
        token = MockIdentityToken(user_id="user-123")
        assert token.get_identity_tenant_id() == "test-tenant-123"
    
    def test_get_display_name(self):
        """Test get_display_name returns name."""
        token = MockIdentityToken(user_id="user-123", name="Alice Smith")
        assert token.get_display_name() == "Alice Smith"
    
    def test_get_firstname_single_name(self):
        """Test get_firstname with single word name."""
        token = MockIdentityToken(user_id="user-123", name="Alice")
        assert token.get_firstname() == "Alice"
    
    def test_get_firstname_full_name(self):
        """Test get_firstname with full name."""
        token = MockIdentityToken(user_id="user-123", name="Alice Smith")
        assert token.get_firstname() == "Alice"
    
    def test_get_lastname_single_name(self):
        """Test get_lastname with single word name."""
        token = MockIdentityToken(user_id="user-123", name="Alice")
        assert token.get_lastname() == ""
    
    def test_get_lastname_full_name(self):
        """Test get_lastname with full name."""
        token = MockIdentityToken(user_id="user-123", name="Alice Smith")
        assert token.get_lastname() == "Smith"
    
    def test_get_mail_default(self):
        """Test get_mail returns default email."""
        token = MockIdentityToken(user_id="user-123")
        assert token.get_mail() == "user-123@test.com"
    
    def test_get_mail_custom(self):
        """Test get_mail returns custom email."""
        token = MockIdentityToken(user_id="user-123", mail="custom@example.com")
        assert token.get_mail() == "custom@example.com"
    
    def test_get_identity_provider(self):
        """Test get_identity_provider returns MOCK."""
        token = MockIdentityToken(user_id="user-123")
        assert token.get_identity_provider() == IdenityProviderEnum.MOCK.value
    
    def test_get_groups_default_empty(self):
        """Test get_groups returns empty list by default."""
        token = MockIdentityToken(user_id="user-123")
        assert token.get_groups() == []
    
    def test_get_groups_with_groups(self):
        """Test get_groups returns provided groups."""
        groups = ["group-1", "group-2", "group-3"]
        token = MockIdentityToken(user_id="user-123", idp_groups=groups)
        assert token.get_groups() == groups
    
    def test_get_token_returns_string(self):
        """Test get_token returns JWT string."""
        token = MockIdentityToken(user_id="user-123")
        jwt_token = token.get_token()
        assert isinstance(jwt_token, str)
        assert len(jwt_token) > 0
    
    def test_get_deserialized_token(self):
        """Test get_deserialized_token returns dict."""
        token = MockIdentityToken(user_id="user-123")
        deserialized = token.get_deserialized_token()
        assert isinstance(deserialized, dict)
        assert "oid" in deserialized
        assert deserialized["oid"] == "user-123"
    
    def test_token_has_issuer(self):
        """Test token has correct issuer."""
        token = MockIdentityToken(user_id="user-123")
        deserialized = token.get_deserialized_token()
        assert deserialized["iss"] == "https://mock.identity.provider/test"
    
    def test_token_has_expiration(self):
        """Test token has expiration time."""
        token = MockIdentityToken(user_id="user-123")
        deserialized = token.get_deserialized_token()
        assert "exp" in deserialized
        assert "iat" in deserialized
        assert deserialized["exp"] > deserialized["iat"]
    
    def test_token_not_expired(self):
        """Test created token is not expired."""
        token = MockIdentityToken(user_id="user-123")
        deserialized = token.get_deserialized_token()
        current_time = int(time.time())
        assert deserialized["exp"] > current_time
    
    def test_to_dict_method(self):
        """Test to_dict returns correct structure."""
        token = MockIdentityToken(
            user_id="user-123",
            name="Alice Smith",
            mail="alice@example.com"
        )
        result = token.to_dict()
        
        assert isinstance(result, dict)
        assert result["id"] == "user-123"
        assert result["display_name"] == "Alice Smith"
        assert result["mail"] == "alice@example.com"
        assert result["identity_provider"] == "MOCK"
    
    def test_multiple_tokens_are_independent(self):
        """Test multiple token instances are independent."""
        token1 = MockIdentityToken(user_id="user-1", name="User One")
        token2 = MockIdentityToken(user_id="user-2", name="User Two")
        
        assert token1.get_id() != token2.get_id()
        assert token1.get_display_name() != token2.get_display_name()
        assert token1.get_token() != token2.get_token()
