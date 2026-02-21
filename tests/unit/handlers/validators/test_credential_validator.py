"""Tests for credential validators."""

import json

import pytest
from pydantic import ValidationError

from unifiedui.handlers.validators.credential_validator import (
    BasicAuthCredential,
    CredentialTypeEnum,
    CredentialValidationError,
    UnsupportedCredentialTypeError,
    validate_credential_secret,
)


class TestCredentialTypeEnum:
    """Tests for CredentialTypeEnum."""

    def test_api_key_value(self):
        """Test that API_KEY is a valid type."""
        assert CredentialTypeEnum.API_KEY.value == "API_KEY"

    def test_basic_auth_value(self):
        """Test that BASIC_AUTH is a valid type."""
        assert CredentialTypeEnum.BASIC_AUTH.value == "BASIC_AUTH"

    def test_all_returns_list(self):
        """Test that all() returns a list of values."""
        types = CredentialTypeEnum.all()
        assert isinstance(types, list)
        assert "API_KEY" in types
        assert "BASIC_AUTH" in types
        assert "OPENAPI_CONNECTION" in types
        assert "AI_MODEL_PROVIDER" in types
        assert len(types) == 4


class TestBasicAuthCredential:
    """Tests for BasicAuthCredential Pydantic model."""

    def test_valid_basic_auth(self):
        """Test a valid basic auth credential."""
        cred = BasicAuthCredential(username="user", password="pass123")

        assert cred.username == "user"
        assert cred.password == "pass123"

    def test_empty_username_not_allowed(self):
        """Test that empty username is not allowed."""
        with pytest.raises(ValidationError):
            BasicAuthCredential(username="", password="pass123")

    def test_empty_password_not_allowed(self):
        """Test that empty password is not allowed."""
        with pytest.raises(ValidationError):
            BasicAuthCredential(username="user", password="")

    def test_missing_username(self):
        """Test that missing username raises ValidationError."""
        with pytest.raises(ValidationError):
            BasicAuthCredential(password="pass123")

    def test_missing_password(self):
        """Test that missing password raises ValidationError."""
        with pytest.raises(ValidationError):
            BasicAuthCredential(username="user")

    def test_whitespace_only_username_allowed_by_pydantic(self):
        """Test that whitespace-only username is allowed by Pydantic.

        Note: Pydantic's min_length only checks length, not that it's non-whitespace.
        "   " has length 3 which passes min_length=1.
        """
        cred = BasicAuthCredential(username="   ", password="pass123")
        assert cred.username == "   "

    def test_whitespace_only_password_allowed_by_pydantic(self):
        """Test that whitespace-only password is allowed by Pydantic.

        Note: Pydantic's min_length only checks length, not that it's non-whitespace.
        "   " has length 3 which passes min_length=1.
        """
        cred = BasicAuthCredential(username="user", password="   ")
        assert cred.password == "   "


class TestValidateCredentialSecret:
    """Tests for validate_credential_secret function.

    IMPORTANT: This function expects secret_value to be a STRING.
    - For API_KEY: any non-empty string
    - For BASIC_AUTH: a JSON STRING that parses to {"username": ..., "password": ...}
    """

    # API_KEY tests
    def test_api_key_valid_string(self):
        """Test that non-empty string is valid for API_KEY."""
        result = validate_credential_secret(CredentialTypeEnum.API_KEY, "my-secret-key")
        assert result == "my-secret-key"

    def test_api_key_empty_string_raises_error(self):
        """Test that empty string raises error for API_KEY."""
        with pytest.raises(CredentialValidationError) as exc_info:
            validate_credential_secret(CredentialTypeEnum.API_KEY, "")
        assert "cannot be empty" in str(exc_info.value)

    def test_api_key_whitespace_only_raises_error(self):
        """Test that whitespace-only string raises error for API_KEY."""
        with pytest.raises(CredentialValidationError) as exc_info:
            validate_credential_secret(CredentialTypeEnum.API_KEY, "   ")
        assert "cannot be empty" in str(exc_info.value)

    def test_api_key_non_string_raises_attribute_error(self):
        """Test that non-string value raises AttributeError.

        The implementation calls .strip() without type checking first.
        """
        with pytest.raises(AttributeError):
            validate_credential_secret(CredentialTypeEnum.API_KEY, 12345)

    def test_api_key_dict_raises_attribute_error(self):
        """Test that dict value raises AttributeError.

        The implementation calls .strip() without type checking first.
        """
        with pytest.raises(AttributeError):
            validate_credential_secret(CredentialTypeEnum.API_KEY, {"key": "value"})

    def test_api_key_none_raises_error(self):
        """Test that None raises error for API_KEY."""
        with pytest.raises(CredentialValidationError) as exc_info:
            validate_credential_secret(CredentialTypeEnum.API_KEY, None)
        assert "cannot be empty" in str(exc_info.value)

    # BASIC_AUTH tests - EXPECTS JSON STRING, NOT DICT
    def test_basic_auth_valid_json_string(self):
        """Test that valid JSON string is accepted for BASIC_AUTH."""
        secret = json.dumps({"username": "user", "password": "pass123"})
        result = validate_credential_secret(CredentialTypeEnum.BASIC_AUTH, secret)
        assert result == secret

    def test_basic_auth_dict_raises_type_error(self):
        """Test that dict (not JSON string) raises TypeError from json.loads.

        The implementation expects a string to pass to json.loads().
        """
        with pytest.raises(TypeError):
            validate_credential_secret(CredentialTypeEnum.BASIC_AUTH, {"username": "user", "password": "pass123"})

    def test_basic_auth_missing_username_json(self):
        """Test that missing username in JSON raises error for BASIC_AUTH."""
        with pytest.raises(CredentialValidationError) as exc_info:
            validate_credential_secret(CredentialTypeEnum.BASIC_AUTH, json.dumps({"password": "pass123"}))
        assert "validation failed" in str(exc_info.value).lower()

    def test_basic_auth_missing_password_json(self):
        """Test that missing password in JSON raises error for BASIC_AUTH."""
        with pytest.raises(CredentialValidationError) as exc_info:
            validate_credential_secret(CredentialTypeEnum.BASIC_AUTH, json.dumps({"username": "user"}))
        assert "validation failed" in str(exc_info.value).lower()

    def test_basic_auth_empty_username_json(self):
        """Test that empty username in JSON raises error for BASIC_AUTH."""
        with pytest.raises(CredentialValidationError) as exc_info:
            validate_credential_secret(
                CredentialTypeEnum.BASIC_AUTH, json.dumps({"username": "", "password": "pass123"})
            )
        assert "validation failed" in str(exc_info.value).lower()

    def test_basic_auth_empty_password_json(self):
        """Test that empty password in JSON raises error for BASIC_AUTH."""
        with pytest.raises(CredentialValidationError) as exc_info:
            validate_credential_secret(CredentialTypeEnum.BASIC_AUTH, json.dumps({"username": "user", "password": ""}))
        assert "validation failed" in str(exc_info.value).lower()

    def test_basic_auth_invalid_json_string(self):
        """Test that invalid JSON string raises error for BASIC_AUTH."""
        with pytest.raises(CredentialValidationError) as exc_info:
            validate_credential_secret(CredentialTypeEnum.BASIC_AUTH, "not valid json")
        assert "valid JSON string" in str(exc_info.value)

    def test_basic_auth_non_dict_value_raises_type_error(self):
        """Test that non-string value raises TypeError from json.loads."""
        with pytest.raises(TypeError):
            validate_credential_secret(CredentialTypeEnum.BASIC_AUTH, 12345)

    def test_basic_auth_none_raises_type_error(self):
        """Test that None raises TypeError from json.loads."""
        with pytest.raises(TypeError):
            validate_credential_secret(CredentialTypeEnum.BASIC_AUTH, None)

    def test_basic_auth_extra_fields_are_ignored_json(self):
        """Test that extra fields in BASIC_AUTH JSON are ignored."""
        secret = json.dumps({"username": "user", "password": "pass123", "extra": "field"})
        # Should not raise - extra fields are ignored by Pydantic
        result = validate_credential_secret(CredentialTypeEnum.BASIC_AUTH, secret)
        assert result == secret

    def test_basic_auth_json_array_raises_error(self):
        """Test that JSON array raises error (must be object)."""
        with pytest.raises(CredentialValidationError) as exc_info:
            validate_credential_secret(CredentialTypeEnum.BASIC_AUTH, '["user", "pass"]')
        assert "JSON object" in str(exc_info.value)

    # Unsupported type tests
    def test_unsupported_type_raises_error(self):
        """Test that unsupported type raises error."""
        with pytest.raises(UnsupportedCredentialTypeError) as exc_info:
            validate_credential_secret("UNKNOWN_TYPE", "some-value")
        assert "not supported" in str(exc_info.value)
        assert "UNKNOWN_TYPE" in str(exc_info.value)

    # Edge cases
    def test_api_key_long_string(self):
        """Test that long strings are valid for API_KEY."""
        long_key = "a" * 10000
        result = validate_credential_secret(CredentialTypeEnum.API_KEY, long_key)
        assert result == long_key

    def test_api_key_special_characters(self):
        """Test that special characters are valid for API_KEY."""
        special_key = "!@#$%^&*()_+-=[]{}|;':\",./<>?"
        result = validate_credential_secret(CredentialTypeEnum.API_KEY, special_key)
        assert result == special_key

    def test_basic_auth_unicode_values_json(self):
        """Test that unicode values are valid for BASIC_AUTH."""
        secret = json.dumps({"username": "用户名", "password": "密码123"})
        result = validate_credential_secret(CredentialTypeEnum.BASIC_AUTH, secret)
        assert result == secret

    def test_lowercase_credential_type_is_normalized(self):
        """Test that lowercase credential type is normalized to uppercase."""
        result = validate_credential_secret("api_key", "my-key")
        assert result == "my-key"

    def test_mixed_case_credential_type_is_normalized(self):
        """Test that mixed case credential type is normalized to uppercase."""
        result = validate_credential_secret("Api_Key", "my-key")
        assert result == "my-key"
