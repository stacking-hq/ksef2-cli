"""Local TOML config file support."""

from __future__ import annotations

import json
import os
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

CONFIG_ENV_VAR = "KSEF2_CONFIG"
CONFIG_FILE_MODE = 0o600


@dataclass(frozen=True)
class LocalConfig:
    nip: str | None = None
    token: str | None = None
    context_type: str | None = None
    cert: Path | None = None
    key: Path | None = None
    key_password: str | None = None
    p12: Path | None = None
    p12_password: str | None = None
    poll_interval: float | None = None
    max_poll_attempts: int | None = None

    def as_dict(self, *, redact_token: bool = True) -> dict[str, Any]:
        token = self.token
        if redact_token and token:
            token = f"{token[:4]}...{token[-4:]}" if len(token) > 8 else "***"
        return {
            "nip": self.nip,
            "token": token,
            "context_type": self.context_type,
            "cert": str(self.cert) if self.cert else None,
            "key": str(self.key) if self.key else None,
            "key_password": "***" if redact_token and self.key_password else self.key_password,
            "p12": str(self.p12) if self.p12 else None,
            "p12_password": "***" if redact_token and self.p12_password else self.p12_password,
            "poll_interval": self.poll_interval,
            "max_poll_attempts": self.max_poll_attempts,
        }


def default_config_path(environ: Mapping[str, str] | None = None) -> Path:
    env = os.environ if environ is None else environ
    override = env.get(CONFIG_ENV_VAR)
    if override:
        return Path(override).expanduser()
    config_home = Path(env.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return config_home.expanduser() / "ksef2-cli" / "config.toml"


def resolve_config_path(path: Path | None) -> Path:
    return path.expanduser() if path else default_config_path()


def load_local_config(path: Path | None) -> LocalConfig:
    config_path = resolve_config_path(path)
    if not config_path.exists():
        return LocalConfig()

    payload = tomllib.loads(config_path.read_text(encoding="utf-8"))
    auth = payload.get("auth", payload)
    if not isinstance(auth, dict):
        raise ValueError("Config file [auth] section must be a table.")

    return LocalConfig(
        nip=_optional_str(auth, "nip"),
        token=_optional_str(auth, "token"),
        context_type=_optional_str(auth, "context_type"),
        cert=_optional_path(auth, "cert"),
        key=_optional_path(auth, "key"),
        key_password=_optional_str(auth, "key_password"),
        p12=_optional_path(auth, "p12"),
        p12_password=_optional_str(auth, "p12_password"),
        poll_interval=_optional_float(auth, "poll_interval"),
        max_poll_attempts=_optional_int(auth, "max_poll_attempts"),
    )


def write_local_config(path: Path, config: LocalConfig, *, force: bool = False) -> None:
    config_path = path.expanduser()
    if config_path.exists() and not force:
        raise FileExistsError(f"{config_path} already exists. Re-run with --force to overwrite it.")

    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(render_local_config(config), encoding="utf-8")
    config_path.chmod(CONFIG_FILE_MODE)


def render_local_config(config: LocalConfig) -> str:
    lines = [
        "# ksef2-cli local defaults",
        "# CLI options override environment variables; environment variables override this file.",
        "# Tokens stored here are plaintext. Prefer KSEF2_TOKEN on shared machines.",
        "[auth]",
    ]
    fields = config.as_dict(redact_token=False)
    for key, value in fields.items():
        if value is None:
            continue
        lines.append(f"{key} = {_toml_value(value)}")
    return "\n".join(lines) + "\n"


def _optional_str(payload: dict[str, Any], key: str) -> str | None:
    value = payload.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"Config value auth.{key} must be a string.")
    return value


def _optional_path(payload: dict[str, Any], key: str) -> Path | None:
    value = _optional_str(payload, key)
    return Path(value).expanduser() if value else None


def _optional_float(payload: dict[str, Any], key: str) -> float | None:
    value = payload.get(key)
    if value is None:
        return None
    if not isinstance(value, (int, float)):
        raise ValueError(f"Config value auth.{key} must be a number.")
    return float(value)


def _optional_int(payload: dict[str, Any], key: str) -> int | None:
    value = payload.get(key)
    if value is None:
        return None
    if not isinstance(value, int):
        raise ValueError(f"Config value auth.{key} must be an integer.")
    return value


def _toml_value(value: Any) -> str:
    if isinstance(value, (int, float)):
        return str(value)
    return json.dumps(str(value))
