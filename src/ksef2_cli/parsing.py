"""Small parsers for CLI option values."""


def parse_optional_bool(value: str | None, *, option_name: str) -> bool | None:
    if value is None:
        return None
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "no", "n", "off"}:
        return False
    raise ValueError(f"{option_name} must be yes or no.")
