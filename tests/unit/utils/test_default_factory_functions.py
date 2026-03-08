"""Unit tests for unifiedui/utils/default_factory_functions.py"""

import re
import uuid
from datetime import UTC, datetime

import pytest

from unifiedui.utils.default_factory_functions import current_iso_datetime, generate_id


class TestCurrentIsoDatetime:
    """Test suite for current_iso_datetime function."""

    def test_returns_string(self):
        """Test that function returns a string."""
        result = current_iso_datetime()
        assert isinstance(result, str)

    def test_returns_iso_format(self):
        """Test that returned string is in ISO format."""
        result = current_iso_datetime()

        # ISO format pattern: YYYY-MM-DDTHH:MM:SS.ffffff+HH:MM or ...Z
        iso_pattern = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+"
        assert re.match(iso_pattern, result) is not None

    def test_includes_timezone_info(self):
        """Test that datetime includes timezone information."""
        result = current_iso_datetime()

        # Should contain either +00:00 or Z for UTC
        assert "+00:00" in result or result.endswith("Z") or "+" in result or "Z" in result

    def test_is_utc_timezone(self):
        """Test that datetime is in UTC timezone."""
        result = current_iso_datetime()

        # Parse the datetime to verify it's UTC
        parsed = datetime.fromisoformat(result)

        # Should be timezone aware
        assert parsed.tzinfo is not None

        # Should be UTC (offset 0)
        assert parsed.utcoffset().total_seconds() == 0

    def test_returns_current_time(self):
        """Test that returned datetime is approximately current time."""
        before = datetime.now(UTC)
        result_str = current_iso_datetime()
        after = datetime.now(UTC)

        result = datetime.fromisoformat(result_str)

        # Result should be between before and after
        assert before <= result <= after

    def test_multiple_calls_return_different_values(self):
        """Test that consecutive calls return different timestamps."""
        import time

        result1 = current_iso_datetime()
        time.sleep(0.001)  # Sleep for 1ms
        result2 = current_iso_datetime()

        # They should be different (even if just by microseconds)
        assert result1 != result2

    def test_format_is_parseable(self):
        """Test that the returned format can be parsed back to datetime."""
        result = current_iso_datetime()

        # Should not raise any exception
        parsed = datetime.fromisoformat(result)

        assert isinstance(parsed, datetime)
        assert parsed.tzinfo is not None

    def test_year_is_current(self):
        """Test that year in the datetime is current year."""
        result = current_iso_datetime()
        parsed = datetime.fromisoformat(result)
        current_year = datetime.now(UTC).year

        assert parsed.year == current_year

    def test_datetime_has_microseconds(self):
        """Test that datetime includes microsecond precision."""
        result = current_iso_datetime()

        # ISO format with microseconds should have a decimal point
        assert "." in result

        # Verify microseconds are included
        parsed = datetime.fromisoformat(result)
        # Microseconds should exist (even if 0)
        assert hasattr(parsed, "microsecond")


class TestGenerateId:
    """Test suite for generate_id function."""

    def test_returns_string(self):
        """Test that function returns a string."""
        result = generate_id()
        assert isinstance(result, str)

    def test_returns_non_empty_string(self):
        """Test that returned string is not empty."""
        result = generate_id()
        assert len(result) > 0

    def test_returns_hex_string(self):
        """Test that returned string contains only hexadecimal characters."""
        result = generate_id()

        # UUID4 hex should only contain 0-9 and a-f
        assert all(c in "0123456789abcdef" for c in result)

    def test_returns_32_character_string(self):
        """Test that returned string is 32 characters long."""
        result = generate_id()

        # UUID4 hex (without dashes) is 32 characters
        assert len(result) == 32

    def test_multiple_calls_return_different_ids(self):
        """Test that consecutive calls return different IDs."""
        id1 = generate_id()
        id2 = generate_id()
        id3 = generate_id()

        assert id1 != id2
        assert id2 != id3
        assert id1 != id3

    def test_generates_unique_ids(self):
        """Test that function generates unique IDs across many calls."""
        # Generate 1000 IDs and check they're all unique
        ids = [generate_id() for _ in range(1000)]
        unique_ids = set(ids)

        assert len(unique_ids) == 1000

    def test_id_format_matches_uuid4_hex(self):
        """Test that ID format matches UUID4 hex format."""
        result = generate_id()

        # Should be valid hex
        try:
            int(result, 16)
        except ValueError:
            pytest.fail("Generated ID is not valid hexadecimal")

    def test_id_can_be_used_as_uuid(self):
        """Test that generated ID can be converted to UUID object."""
        result = generate_id()

        # Should be able to create UUID from the hex string
        uuid_obj = uuid.UUID(hex=result)

        assert isinstance(uuid_obj, uuid.UUID)
        assert uuid_obj.hex == result

    def test_id_is_lowercase(self):
        """Test that generated ID uses lowercase hexadecimal."""
        result = generate_id()

        # Should not contain uppercase letters
        assert result == result.lower()
        assert not any(c in "ABCDEF" for c in result)

    def test_randomness(self):
        """Test that IDs have sufficient randomness."""
        # Generate multiple IDs and check they don't have obvious patterns
        ids = [generate_id() for _ in range(100)]

        # Check that not all IDs start with the same character
        first_chars = [id_str[0] for id_str in ids]
        unique_first_chars = set(first_chars)

        # Should have multiple different starting characters
        assert len(unique_first_chars) > 1

    def test_collision_resistance(self):
        """Test that collision is extremely unlikely."""
        # Generate many IDs and verify all are unique
        num_ids = 10000
        ids = [generate_id() for _ in range(num_ids)]

        assert len(set(ids)) == num_ids, "Found duplicate IDs in 10000 generations"

    def test_id_usable_as_database_key(self):
        """Test that generated ID is suitable as database primary key."""
        result = generate_id()

        # Should be a reasonable length for a database key
        assert 20 <= len(result) <= 50

        # Should only contain safe characters
        assert result.isalnum()

        # Should not be empty or whitespace
        assert result.strip() == result
        assert len(result) > 0


class TestIntegration:
    """Integration tests for default_factory_functions."""

    def test_both_functions_work_together(self):
        """Test that both functions can be used together."""
        timestamp = current_iso_datetime()
        unique_id = generate_id()

        assert isinstance(timestamp, str)
        assert isinstance(unique_id, str)
        assert timestamp != unique_id

    def test_can_create_timestamped_record(self):
        """Test creating a record with both timestamp and ID."""
        record = {"id": generate_id(), "created_at": current_iso_datetime(), "updated_at": current_iso_datetime()}

        assert "id" in record
        assert "created_at" in record
        assert "updated_at" in record
        assert len(record["id"]) == 32
        assert "T" in record["created_at"]
        assert "T" in record["updated_at"]

    def test_multiple_records_have_unique_ids(self):
        """Test creating multiple records with unique IDs."""
        records = [{"id": generate_id(), "timestamp": current_iso_datetime()} for _ in range(100)]

        ids = [r["id"] for r in records]
        assert len(set(ids)) == 100
