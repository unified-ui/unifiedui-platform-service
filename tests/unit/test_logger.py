"""Tests for centralized logging with log injection prevention."""

import io
import logging

import pytest

from unifiedui.logger import (
    ColoredFormatter,
    SafeLogger,
    _sanitize_log_args,
    sanitize_log_value,
)


class TestSanitizeLogValue:
    """Tests for the sanitize_log_value function."""

    def test_strips_newline(self) -> None:
        assert sanitize_log_value("hello\nworld") == "hello\\nworld"

    def test_strips_carriage_return(self) -> None:
        assert sanitize_log_value("hello\rworld") == "hello\\rworld"

    def test_strips_crlf(self) -> None:
        assert sanitize_log_value("hello\r\nworld") == "hello\\r\\nworld"

    def test_multiple_newlines(self) -> None:
        assert sanitize_log_value("a\nb\nc") == "a\\nb\\nc"

    def test_no_newlines_unchanged(self) -> None:
        assert sanitize_log_value("safe value") == "safe value"

    def test_empty_string(self) -> None:
        assert sanitize_log_value("") == ""

    def test_non_string_passthrough_int(self) -> None:
        assert sanitize_log_value(42) == 42

    def test_non_string_passthrough_none(self) -> None:
        assert sanitize_log_value(None) is None

    def test_non_string_passthrough_list(self) -> None:
        result = sanitize_log_value([1, 2, 3])
        assert result == [1, 2, 3]

    def test_injection_attack_fake_log_entry(self) -> None:
        malicious = "normal\n2026-03-08 - FAKE - INFO - Injected log entry"
        result = sanitize_log_value(malicious)
        assert "\n" not in str(result)
        assert "\\n" in str(result)


class TestSanitizeLogArgs:
    """Tests for the _sanitize_log_args helper."""

    def test_none_args(self) -> None:
        assert _sanitize_log_args(None) is None

    def test_tuple_args(self) -> None:
        result = _sanitize_log_args(("value\n", 42, "safe"))
        assert result == ("value\\n", 42, "safe")

    def test_dict_args(self) -> None:
        result = _sanitize_log_args({"key": "val\nue", "num": 1})
        assert result == {"key": "val\\nue", "num": 1}

    def test_empty_tuple(self) -> None:
        assert _sanitize_log_args(()) == ()

    def test_empty_dict(self) -> None:
        assert _sanitize_log_args({}) == {}


class TestColoredFormatter:
    """Tests for ColoredFormatter with log injection prevention."""

    @pytest.fixture()
    def formatter(self) -> ColoredFormatter:
        """Create a ColoredFormatter instance."""
        return ColoredFormatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    def test_sanitizes_message(self, formatter: ColoredFormatter) -> None:
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="User said\ninjected line",
            args=(),
            exc_info=None,
        )
        output = formatter.format(record)
        assert "\ninjected line" not in output
        assert "\\ninjected line" in output

    def test_sanitizes_args(self, formatter: ColoredFormatter) -> None:
        record = logging.LogRecord(
            name="test",
            level=logging.WARNING,
            pathname="test.py",
            lineno=1,
            msg="Value: %s",
            args=("data\r\ninjection",),
            exc_info=None,
        )
        output = formatter.format(record)
        assert "\r\n" not in output
        assert "data\\r\\ninjection" in output

    def test_preserves_exc_info(self, formatter: ColoredFormatter) -> None:
        try:
            raise ValueError("test error")
        except ValueError:
            import sys

            exc_info = sys.exc_info()

        record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname="test.py",
            lineno=1,
            msg="Error occurred",
            args=(),
            exc_info=exc_info,
        )
        output = formatter.format(record)
        assert "ValueError" in output
        assert "test error" in output

    def test_clean_message_unchanged(self, formatter: ColoredFormatter) -> None:
        record = logging.LogRecord(
            name="test",
            level=logging.DEBUG,
            pathname="test.py",
            lineno=1,
            msg="Clean message with tenant %s",
            args=("abc-123",),
            exc_info=None,
        )
        output = formatter.format(record)
        assert "Clean message with tenant abc-123" in output

    def test_applies_color_codes(self, formatter: ColoredFormatter) -> None:
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Colored output",
            args=(),
            exc_info=None,
        )
        output = formatter.format(record)
        assert "\x1b[" in output


class TestSafeLogger:
    """Tests for SafeLogger subclass."""

    @pytest.fixture()
    def safe_logger(self) -> tuple[logging.Logger, io.StringIO]:
        """Create a SafeLogger instance with a capturing handler."""
        stream = io.StringIO()
        logger = SafeLogger("test_safe", logging.DEBUG)
        logger.handlers.clear()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)
        return logger, stream

    def test_is_logger_subclass(self) -> None:
        logger = SafeLogger("test", logging.INFO)
        assert isinstance(logger, logging.Logger)

    def test_sanitizes_info_message(self, safe_logger: tuple[logging.Logger, io.StringIO]) -> None:
        logger, stream = safe_logger
        logger.info("User: %s", "evil\nINFO - fake entry")
        output = stream.getvalue()
        assert "\nINFO - fake entry" not in output

    def test_sanitizes_extra_values(self, safe_logger: tuple[logging.Logger, io.StringIO]) -> None:
        logger, stream = safe_logger
        fmt = logging.Formatter("%(message)s - %(user_id)s")
        logger.handlers[0].setFormatter(fmt)
        logger.info(
            "Request",
            extra={"user_id": "id\nINJECTED"},
        )
        output = stream.getvalue()
        assert "\nINJECTED" not in output
        assert "id\\nINJECTED" in output

    def test_preserves_exception_info(self, safe_logger: tuple[logging.Logger, io.StringIO]) -> None:
        logger, stream = safe_logger
        try:
            raise RuntimeError("test exception")
        except RuntimeError:
            logger.exception("Error occurred")
        output = stream.getvalue()
        assert "RuntimeError" in output
        assert "test exception" in output

    def test_logger_class_is_safe_logger(self) -> None:
        assert logging.getLoggerClass() is SafeLogger
