import uuid
from datetime import UTC, datetime


def current_iso_datetime() -> str:
    return datetime.now(UTC).isoformat()


def generate_id() -> str:
    """Generate a unique ID using UUID4."""
    return uuid.uuid4().hex
