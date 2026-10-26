import json
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import BaseModel

from ksef2_cli.io import (
    SECRET_MODEL_FILE_MODE,
    read_model_file,
    write_bytes_file,
    write_model_file,
)
from ksef2_cli.parsing import parse_iso_datetime, parse_optional_bool


class DemoModel(BaseModel):
    name: str


def test_optional_bool_parser_accepts_common_values() -> None:
    assert parse_optional_bool(None, option_name="--x") is None
    assert parse_optional_bool("yes", option_name="--x") is True
    assert parse_optional_bool("false", option_name="--x") is False
    assert parse_optional_bool("on", option_name="--x") is True
    assert parse_optional_bool("0", option_name="--x") is False


def test_optional_bool_parser_rejects_unknown_value() -> None:
    with pytest.raises(ValueError, match="--x must be yes or no"):
        parse_optional_bool("maybe", option_name="--x")


def test_iso_datetime_parser_allows_naive_values_by_default() -> None:
    assert parse_iso_datetime("2026-03-01T12:00:00", option_name="--x") == datetime(
        2026, 3, 1, 12
    )


def test_iso_datetime_parser_requires_an_offset_when_asked() -> None:
    parsed = parse_iso_datetime(
        "2026-03-01T12:00:00+02:00", option_name="--x", require_offset=True
    )
    assert parsed.utcoffset() == timedelta(hours=2)

    for value in ("2026-03-01T12:00:00",):
        with pytest.raises(ValueError, match="--x must include a UTC offset"):
            parse_iso_datetime(value, option_name="--x", require_offset=True)

    with pytest.raises(ValueError, match="--x must be a date like"):
        parse_iso_datetime("next-month", option_name="--x", require_offset=True)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("2026-03-01", datetime(2026, 3, 1, tzinfo=UTC)),
        ("01.03.2026", datetime(2026, 3, 1, tzinfo=UTC)),
        ("1-3-2026", datetime(2026, 3, 1, tzinfo=UTC)),
    ],
)
def test_iso_datetime_parser_reads_a_bare_date_as_midnight_utc(
    value, expected
) -> None:
    """A date with no time of day names one instant, so offset-strict options take it."""

    parsed = parse_iso_datetime(value, option_name="--x", require_offset=True)

    assert parsed == expected
    assert parsed.tzinfo is UTC


def test_iso_datetime_parser_offset_hint_names_the_bare_date_default() -> None:
    with pytest.raises(ValueError) as error:
        parse_iso_datetime("2026-03-01T12:00:00", option_name="--x", require_offset=True)

    assert str(error.value) == (
        "--x must include a UTC offset, e.g. 2026-03-01T12:00:00Z or "
        "2026-03-01T12:00:00+02:00. A date with no time of day, such as "
        "2026-03-01, names one instant already: midnight UTC."
    )


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("01.10.2026", datetime(2026, 10, 1)),
        ("1.10.2026", datetime(2026, 10, 1)),
        ("01-10-2026", datetime(2026, 10, 1)),
        ("1-2-2026", datetime(2026, 2, 1)),
        ("2026-10-01", datetime(2026, 10, 1)),
        ("2026-10-01T08:00:00Z", datetime(2026, 10, 1, 8, tzinfo=UTC)),
    ],
)
def test_datetime_parser_accepts_iso_and_polish_dates(value, expected) -> None:
    assert parse_iso_datetime(value, option_name="--date-from") == expected


@pytest.mark.parametrize(
    "value",
    [
        "01/10/2026",
        "01.10.26",
        "31.02.2026",
        "01.10.2026 08:00",
        "13.13.2026",
        "01.10-2026",
        "01-10-2026T08:00:00Z",
    ],
)
def test_datetime_parser_rejects_invalid_dates(value) -> None:
    with pytest.raises(ValueError) as error:
        parse_iso_datetime(value, option_name="--date-from")
    assert str(error.value) == (
        "--date-from must be a date like 2026-10-01 or 01.10.2026, "
        "or an ISO 8601 datetime like 2026-10-01T08:00:00Z."
    )


@pytest.mark.parametrize("value", ["01.10.2026", "1.10.2026", "01-10-2026"])
def test_polish_dates_equal_iso_dates(value) -> None:
    assert parse_iso_datetime(value, option_name="--x") == parse_iso_datetime(
        "2026-10-01", option_name="--x"
    )


def test_model_file_helpers_read_and_write_json(tmp_path) -> None:
    path = tmp_path / "payload.json"
    path.write_text('{"name": "demo"}', encoding="utf-8")

    assert read_model_file(path, DemoModel) == DemoModel(name="demo")

    target = tmp_path / "nested" / "out.json"
    assert write_model_file(target, DemoModel(name="written")) == target
    data = json.loads(target.read_text(encoding="utf-8"))
    assert data == {"name": "written"}

    secret_target = tmp_path / "nested" / "secret.json"
    assert (
        write_model_file(
            secret_target,
            DemoModel(name="secret"),
            file_mode=SECRET_MODEL_FILE_MODE,
        )
        == secret_target
    )
    assert secret_target.stat().st_mode & 0o777 == SECRET_MODEL_FILE_MODE

    binary_target = tmp_path / "nested" / "file.bin"
    assert write_bytes_file(binary_target, b"abc") == binary_target
    assert binary_target.read_bytes() == b"abc"
