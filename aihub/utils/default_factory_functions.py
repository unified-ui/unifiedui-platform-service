from datetime import datetime, timezone


def current_iso_datetime() -> str:
    return datetime.now(timezone.utc).isoformat()
