"""Local TOML config file support."""

from __future__ import annotations

import os
import tomllib
from collections.abc import Callable
from pathlib import Path
from typing import Annotated, Any, Mapping, cast

import toml
from pydantic import BaseModel, Field, GetPydanticSchema, field_validator
from pydantic_core import core_schema
from secret_type import secret
from secret_type.containers.sequence import SecretStr as SecretTextValue

CONFIG_ENV_VAR = "KSEF2_CONFIG"
CONFIG_FILE_MODE = 0o600


def secret_value(value: SecretTextValue | None) -> str | None:
    if value is None:
        return None
    with value.dangerous_reveal() as text:
        return str(text)


def _secret_text_schema(_source_type: object, _handler: object) -> core_schema.CoreSchema:
    return core_schema.no_info_wrap_validator_function(
        _validate_secret_text,
        core_schema.str_schema(),
        serialization=core_schema.plain_serializer_function_ser_schema(
            secret_value,
            return_schema=core_schema.str_schema(),
            when_used="json",
        ),
    )


def _validate_secret_text(value: Any, handler: Callable[[Any], str]) -> SecretTextValue:
    if isinstance(value, SecretTextValue):
        return value
    return cast(SecretTextValue, secret(handler(value)))


SecretText = Annotated[SecretTextValue, GetPydanticSchema(_secret_text_schema)]


class LocalConfig(BaseModel):
    nip: str | None = Field(default=None, description="Taxpayer/context NIP.")
    token: SecretText | None = Field(default=None, description="KSeF authorization token.")
    context_type: str | None = None
    cert: Path | None = None
    key: Path | None = None
    key_password: SecretText | None = None
    p12: Path | None = None
    p12_password: SecretText | None = None
    poll_interval: float | None = None
    max_poll_attempts: int | None = None

    @field_validator("cert", "key", "p12", mode="after")
    @classmethod
    def _expand_path(cls, value: Path | None) -> Path | None:
        return value.expanduser() if value else None

    def as_dict(self, *, redact_token: bool = True) -> dict[str, Any]:
        token = secret_value(self.token)
        key_password = secret_value(self.key_password)
        p12_password = secret_value(self.p12_password)
        return {
            "nip": self.nip,
            "token": _redact_secret(token) if redact_token else token,
            "context_type": self.context_type,
            "cert": str(self.cert) if self.cert else None,
            "key": str(self.key) if self.key else None,
            "key_password": "***" if redact_token and key_password else key_password,
            "p12": str(self.p12) if self.p12 else None,
            "p12_password": "***" if redact_token and p12_password else p12_password,
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

    return LocalConfig.model_validate(auth)


def write_local_config(path: Path, config: LocalConfig, *, force: bool = False) -> None:
    config_path = path.expanduser()
    if config_path.exists() and not force:
        raise FileExistsError(f"{config_path} already exists. Re-run with --force to overwrite it.")

    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(render_local_config(config), encoding="utf-8")
    config_path.chmod(CONFIG_FILE_MODE)


def render_local_config(config: LocalConfig) -> str:
    header = "\n".join([
        "# ksef2-cli local defaults",
        "# CLI options override environment variables; environment variables override this file.",
        "# Tokens stored here are plaintext. Prefer KSEF2_TOKEN on shared machines.",
        "[auth]",
    ])

    content = toml.dumps(config.model_dump(mode="json", exclude_none=True))

    return header + "\n" + content


def _redact_secret(value: str | None) -> str | None:
    if not value:
        return value
    return f"{value[:4]}...{value[-4:]}" if len(value) > 8 else "***"
