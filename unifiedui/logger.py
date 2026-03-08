"""Centralized logging configuration for unifiedui."""

from __future__ import annotations

import copy
import logging
import re
import sys
from collections.abc import Mapping
from typing import TYPE_CHECKING

from unifiedui.core.config import settings

if TYPE_CHECKING:
    from logging import _ExcInfoType

_LOG_INJECTION_PATTERN = re.compile(r"[\r\n]")


def sanitize_log_value(value: object) -> object:
    """Sanitize a value for safe logging by escaping newline characters.

    Prevents log injection attacks by replacing CR/LF characters
    with their escaped representations (\\r, \\n).

    Args:
        value: The value to sanitize.

    Returns:
        The sanitized value with newlines escaped (strings only),
        or the original value unchanged for non-string types.
    """
    if isinstance(value, str):
        return _LOG_INJECTION_PATTERN.sub(lambda m: "\\r" if m.group() == "\r" else "\\n", value)
    return value


def _sanitize_log_args(
    args: tuple[object, ...] | Mapping[str, object] | None,
) -> tuple[object, ...] | Mapping[str, object] | None:
    """Sanitize log message arguments to prevent log injection.

    Args:
        args: The log record args (tuple or dict/mapping of format values).

    Returns:
        Sanitized copy of args with newline characters escaped.
    """
    if args is None:
        return None
    if isinstance(args, Mapping):
        return {k: sanitize_log_value(v) for k, v in args.items()}
    return tuple(sanitize_log_value(a) for a in args)


class ColoredFormatter(logging.Formatter):
    """Custom formatter with colors and log injection prevention."""

    grey = "\x1b[38;21m"
    blue = "\x1b[38;5;39m"
    yellow = "\x1b[38;5;226m"
    red = "\x1b[38;5;196m"
    bold_red = "\x1b[31;1m"
    reset = "\x1b[0m"

    def __init__(self, fmt: str):
        super().__init__()
        self.fmt = fmt
        self.FORMATS = {
            logging.DEBUG: self.grey + self.fmt + self.reset,
            logging.INFO: self.blue + self.fmt + self.reset,
            logging.WARNING: self.yellow + self.fmt + self.reset,
            logging.ERROR: self.red + self.fmt + self.reset,
            logging.CRITICAL: self.bold_red + self.fmt + self.reset,
        }

    def format(self, record: logging.LogRecord) -> str:
        """Format log record with color and log injection sanitization.

        Sanitizes message content and arguments to prevent log injection
        attacks while preserving exception tracebacks.

        Args:
            record: The log record to format.

        Returns:
            Colored and sanitized log entry string.
        """
        sanitized = copy.copy(record)
        sanitized.msg = sanitize_log_value(sanitized.msg)
        sanitized.args = _sanitize_log_args(sanitized.args)
        log_fmt = self.FORMATS.get(sanitized.levelno)
        formatter = logging.Formatter(log_fmt)
        return formatter.format(sanitized)


class SafeLogger(logging.Logger):
    """Logger subclass that sanitizes all inputs to prevent log injection.

    Overrides the internal _log method to sanitize message content,
    format arguments, and extra dict values before they reach the
    log record. This provides defense-in-depth alongside the
    ColoredFormatter sanitization.
    """

    def _log(  # type: ignore[override]
        self,
        level: int,
        msg: object,
        args: tuple[object, ...] | Mapping[str, object] | None,
        exc_info: _ExcInfoType | None = None,
        extra: dict[str, object] | None = None,
        stack_info: bool = False,
        stacklevel: int = 1,
    ) -> None:
        """Log with sanitized message, args, and extra values.

        Args:
            level: Numeric logging level.
            msg: The log message (may contain %s placeholders).
            args: Arguments for message formatting.
            exc_info: Exception info tuple or boolean.
            extra: Extra dict to merge into the LogRecord.
            stack_info: Whether to include stack info.
            stacklevel: Stack level for caller identification.
        """
        sanitized_msg = sanitize_log_value(msg)
        sanitized_args = _sanitize_log_args(args)
        sanitized_extra = {k: sanitize_log_value(v) for k, v in extra.items()} if extra is not None else None
        super()._log(
            level,
            sanitized_msg,
            sanitized_args,  # type: ignore[arg-type]
            exc_info=exc_info,
            extra=sanitized_extra,
            stack_info=stack_info,
            stacklevel=stacklevel,
        )


logging.setLoggerClass(SafeLogger)


def setup_logging(log_level: str | None = None) -> None:
    """
    Configure logging for the application.

    Args:
        log_level: Optional log level override (defaults to settings.log_level)
    """
    level = log_level or settings.log_level
    log_level_int = getattr(logging, level.upper(), logging.INFO)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level_int)

    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    colored_formatter = ColoredFormatter(log_format)
    console_handler.setFormatter(colored_formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level_int)

    root_logger.handlers.clear()

    root_logger.addHandler(console_handler)

    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("pymongo").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for a specific module.

    Args:
        name: Logger name (typically __name__ of the calling module)

    Returns:
        logging.Logger: Configured logger instance
    """
    return logging.getLogger(name)


setup_logging()
