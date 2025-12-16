from datetime import datetime, timezone
import uuid


def current_iso_datetime() -> str:
    return datetime.now(timezone.utc).isoformat()


def generate_id() -> str:
    """Generate a unique ID using UUID4."""
    return uuid.uuid4().hex
