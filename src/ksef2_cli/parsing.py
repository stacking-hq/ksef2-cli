"""Small parsers for CLI option values."""

import re
from datetime import UTC, datetime

from ksef2_cli.exceptions import UsageError

_DATE_ONLY = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")


def parse_iso_datetime(
    value: str, *, option_name: str, require_offset: bool = False
) -> datetime:
    """Parse an ISO 8601 date/datetime or a day-first Polish date.

    Args:
        value: Raw option value.
        option_name: Option as the user typed it, used in the message on failure.
        require_offset: Reject values that carry no UTC offset, for endpoints that
            act on one unambiguous instant. A date with no time of day, such as
            `2026-10-01` or `01.10.2026`, is taken as the start of that day in UTC,
            the one instant a bare date names, and passes.

    Raises:
        ValueError: If the value is not a supported date/datetime, or if
            `require_offset` is set and the value is a naive datetime.
    """
    date_only = _DATE_ONLY.fullmatch(value) is not None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as error:
        try:
            match = re.fullmatch(r"([0-9]{1,2})([.-])([0-9]{1,2})\2([0-9]{4})", value)
            if match is None:
                raise error
            day, _, month, year = match.groups()
            parsed = datetime(int(year), int(month), int(day))
            date_only = True
        except ValueError as date_error:
            raise ValueError(
                f"{option_name} must be a date like 2026-10-01 or 01.10.2026, "
                "or an ISO 8601 datetime like 2026-10-01T08:00:00Z."
            ) from date_error
    if require_offset:
        if parsed.tzinfo is not None:
            return parsed
        if not date_only:
            raise ValueError(
                f"{option_name} must include a UTC offset, e.g. 2026-03-01T12:00:00Z "
                "or 2026-03-01T12:00:00+02:00. A date with no time of day, such as "
                "2026-03-01, names one instant already: midnight UTC."
            )
        return parsed.replace(tzinfo=UTC)
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


def validate_offset_pagination(*, all_pages: bool, page_offset: int) -> None:
    """Reject an offset that conflicts with fetching all pages."""
    if all_pages and page_offset != 0:
        raise UsageError(
            "--all cannot be combined with a nonzero --page-offset. "
            "Omit --page-offset or use --page-offset 0.",
            exit_code=2,
        )
