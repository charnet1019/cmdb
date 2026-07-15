"""Shared datetime formatting helpers."""
from datetime import datetime, timezone


def format_datetime_utc(dt: datetime | None) -> str | None:
    """Format a naive UTC datetime as ISO 8601 with a Z suffix."""
    if dt is None:
        return None
    return dt.replace(tzinfo=timezone.utc).isoformat().replace('+00:00', 'Z')
