"""Tests for field_filter utility."""

import pytest
from fastapi import HTTPException
from pydantic import BaseModel

from unifiedui.handlers.field_filter import filter_response_fields, parse_ids


class SampleModel(BaseModel):
    """Sample model for testing field filtering."""

    id: str
    name: str
    description: str
    my_permission: str | None = None


class SampleModelNoPermission(BaseModel):
    """Sample model without my_permission field."""

    id: int
    name: str
    value: float


class TestFilterResponseFields:
    """Test suite for filter_response_fields."""

    def test_none_fields_returns_original_single(self) -> None:
        """Should return the original model when fields is None."""
        model = SampleModel(id="1", name="test", description="desc", my_permission="read")
        result = filter_response_fields(model, None)
        assert result is model

    def test_none_fields_returns_original_list(self) -> None:
        """Should return the original list when fields is None."""
        models = [SampleModel(id="1", name="test", description="desc")]
        result = filter_response_fields(models, None)
        assert result is models

    def test_empty_fields_returns_original(self) -> None:
        """Should return original when fields string is empty."""
        model = SampleModel(id="1", name="test", description="desc")
        result = filter_response_fields(model, "  ,  ,  ")
        assert result is model

    def test_single_field_on_single_model(self) -> None:
        """Should return only requested fields plus always-include fields."""
        model = SampleModel(id="1", name="test", description="desc", my_permission="read")
        result = filter_response_fields(model, "name")
        assert isinstance(result, dict)
        assert result == {"id": "1", "name": "test", "my_permission": "read"}

    def test_multiple_fields_on_list(self) -> None:
        """Should filter all models in the list."""
        models = [
            SampleModel(id="1", name="a", description="d1", my_permission="read"),
            SampleModel(id="2", name="b", description="d2", my_permission="write"),
        ]
        result = filter_response_fields(models, "name")
        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0] == {"id": "1", "name": "a", "my_permission": "read"}
        assert result[1] == {"id": "2", "name": "b", "my_permission": "write"}

    def test_always_include_id(self) -> None:
        """Should always include 'id' even when not requested."""
        model = SampleModel(id="1", name="test", description="desc")
        result = filter_response_fields(model, "description")
        assert isinstance(result, dict)
        assert "id" in result
        assert "description" in result

    def test_always_include_my_permission_when_exists(self) -> None:
        """Should include my_permission when present on model."""
        model = SampleModel(id="1", name="test", description="desc", my_permission="admin")
        result = filter_response_fields(model, "name")
        assert isinstance(result, dict)
        assert result["my_permission"] == "admin"

    def test_always_include_skips_nonexistent_fields(self) -> None:
        """Should not fail when always-include field doesn't exist on model."""
        model = SampleModelNoPermission(id=1, name="test", value=3.14)
        result = filter_response_fields(model, "name")
        assert isinstance(result, dict)
        assert "id" in result
        assert "name" in result
        assert "my_permission" not in result

    def test_invalid_field_raises_http_exception(self) -> None:
        """Should raise HTTPException for invalid field names."""
        model = SampleModel(id="1", name="test", description="desc")
        with pytest.raises(HTTPException) as exc_info:
            filter_response_fields(model, "nonexistent")
        assert exc_info.value.status_code == 400
        assert "Invalid field names" in str(exc_info.value.detail)

    def test_mixed_valid_invalid_fields_raises(self) -> None:
        """Should raise HTTPException when mix of valid and invalid fields."""
        model = SampleModel(id="1", name="test", description="desc")
        with pytest.raises(HTTPException) as exc_info:
            filter_response_fields(model, "name,bad_field")
        assert exc_info.value.status_code == 400
        assert "bad_field" in str(exc_info.value.detail)

    def test_whitespace_handling(self) -> None:
        """Should handle whitespace around field names."""
        model = SampleModel(id="1", name="test", description="desc")
        result = filter_response_fields(model, " name , description ")
        assert isinstance(result, dict)
        assert "name" in result
        assert "description" in result

    def test_empty_list_returns_empty(self) -> None:
        """Should handle empty list gracefully."""
        result = filter_response_fields([], "name")
        assert result == []

    def test_custom_always_include(self) -> None:
        """Should respect custom always_include set."""
        model = SampleModel(id="1", name="test", description="desc")
        result = filter_response_fields(model, "name", always_include={"id"})
        assert isinstance(result, dict)
        assert "id" in result
        assert "name" in result
        assert "my_permission" not in result


class TestParseIds:
    """Test suite for parse_ids."""

    def test_none_returns_none(self) -> None:
        """Should return None when input is None."""
        assert parse_ids(None) is None

    def test_single_id(self) -> None:
        """Should parse a single ID."""
        assert parse_ids("abc-123") == ["abc-123"]

    def test_multiple_ids(self) -> None:
        """Should parse multiple comma-separated IDs."""
        assert parse_ids("id1,id2,id3") == ["id1", "id2", "id3"]

    def test_whitespace_handling(self) -> None:
        """Should strip whitespace from IDs."""
        assert parse_ids(" id1 , id2 , id3 ") == ["id1", "id2", "id3"]

    def test_empty_string_returns_empty_list(self) -> None:
        """Should return empty list for empty string."""
        assert parse_ids("") == []

    def test_trailing_comma(self) -> None:
        """Should handle trailing commas."""
        assert parse_ids("id1,id2,") == ["id1", "id2"]
