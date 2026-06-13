"""Small parsers for CLI option values."""

from __future__ import annotations

from typing import Any

from ksef2_cli.config import FORM_SCHEMA_NAMES


def _parse_form_schema(value: str) -> Any:
    from ksef2 import FormSchema

    normalized = value.strip().upper().replace("-", "_")
    try:
        return FormSchema[normalized]
    except KeyError as exc:
        raise ValueError(f"Invalid form schema {value!r}. Valid values: {FORM_SCHEMA_NAMES}") from exc

def _safe_filename(value: str, suffix: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in value)
    return safe if safe.endswith(suffix) else f"{safe}{suffix}"


def _parse_optional_bool(value: str | None, *, option_name: str) -> bool | None:
    if value is None:
        return None
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "no", "n", "off"}:
        return False
    raise ValueError(f"{option_name} must be yes or no.")
