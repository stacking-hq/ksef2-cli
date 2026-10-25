"""Small parsers for CLI option values."""

import re
from datetime import datetime


def parse_iso_datetime(
    value: str, *, option_name: str, require_offset: bool = False
) -> datetime:
    """Parse an ISO 8601 date/datetime or a day-first Polish date.

    Args:
        value: Raw option value.
        option_name: Option as the user typed it, used in the message on failure.
        require_offset: Reject values that carry no UTC offset, for endpoints that
            act on one unambiguous instant.

    Raises:
        ValueError: If the value is not a supported date/datetime, or if
            `require_offset` is set and the value is naive.
    """
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as error:
        try:
            match = re.fullmatch(r"([0-9]{1,2})([.-])([0-9]{1,2})\2([0-9]{4})", value)
            if match is None:
                raise error
            day, _, month, year = match.groups()
            parsed = datetime(int(year), int(month), int(day))
        except ValueError as date_error:
            raise ValueError(
                f"{option_name} must be a date like 2026-10-01 or 01.10.2026, "
                "or an ISO 8601 datetime like 2026-10-01T08:00:00Z."
            ) from date_error
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
