"""Small parsers for CLI option values."""

from datetime import datetime


def parse_iso_datetime(value: str, *, option_name: str) -> datetime:
    """Parse a date or datetime option in ISO 8601 form, e.g. 2026-09-17T08:00:00Z."""
    try:
        return datetime.fromisoformat(value)
    except ValueError as error:
        raise ValueError(
            f"{option_name} must be an ISO 8601 date or datetime: {error}"
        ) from error


def parse_optional_bool(value: str | None, *, option_name: str) -> bool | None:
    if value is None:
        return None
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "no", "n", "off"}:
        return False
    raise ValueError(f"{option_name} must be yes or no.")
