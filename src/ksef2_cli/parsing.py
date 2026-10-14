"""Small parsers for CLI option values."""

from datetime import datetime


def parse_iso_datetime(
    value: str, *, option_name: str, require_offset: bool = False
) -> datetime:
    """Parse a date or datetime option in ISO 8601 form, e.g. 2026-09-17T08:00:00Z.

    Args:
        value: Raw option value.
        option_name: Option as the user typed it, used in the message on failure.
        require_offset: Reject values that carry no UTC offset, for endpoints that
            act on one unambiguous instant.

    Raises:
        ValueError: If the value is not ISO 8601, or if `require_offset` is set and
            the value is naive.
    """
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as error:
        raise ValueError(
            f"{option_name} must be an ISO 8601 date or datetime: {error}"
        ) from error
    if require_offset and parsed.tzinfo is None:
        raise ValueError(
            f"{option_name} must include a UTC offset, e.g. 2026-03-01T12:00:00Z "
            "or 2026-03-01T12:00:00+02:00."
        )
    return parsed


def parse_optional_bool(value: str | None, *, option_name: str) -> bool | None:
    if value is None:
        return None
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "no", "n", "off"}:
        return False
    raise ValueError(f"{option_name} must be yes or no.")
