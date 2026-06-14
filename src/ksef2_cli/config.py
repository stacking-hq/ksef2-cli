"""Shared CLI settings and simple enum configuration."""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, Callable, Mapping

import toml
from pydantic import SecretStr, BaseModel, Field, field_validator


class EnvironmentName(StrEnum):
    production = "production"
    demo = "demo"
    test = "test"

class OutputMode(StrEnum):
    text = "text"
    json = "json"


ENVIRONMENT_MEMBERS = {
    EnvironmentName.production: "PRODUCTION",
    EnvironmentName.demo: "DEMO",
    EnvironmentName.test: "TEST",
}

FORM_SCHEMA_NAMES = "FA2, FA3, FA_RR1, PEF3, PEF_KOR3"


@dataclass(frozen=True)
class RuntimeOverrides:
    client_factory: Callable[[], Any] | None = None
    authenticated_client_factory: Callable[[], Any] | None = None
    model_reader: Callable[[Path, type[Any]], Any] | None = None
    p12_credentials_loader: Callable[..., tuple[Any, Any]] | None = None
    pem_credentials_loader: Callable[..., tuple[Any, Any]] | None = None


@dataclass(frozen=True)
class Settings:
    config_file: Path
    config_loaded: bool
    environment: EnvironmentName
    output: OutputMode
    verbose: bool
    nip: str | None
    token: str | None
    context_type: str
    test_certificate: bool
    cert: Path | None
    key: Path | None
    key_password: str | None
    p12: Path | None
    p12_password: str | None
    poll_interval: float
    max_poll_attempts: int
    runtime_overrides: RuntimeOverrides | None = None


CONFIG_ENV_VAR = "KSEF2_CONFIG"
CONFIG_FILE_MODE = 0o600


def secret_value(value: SecretStr | None) -> str | None:
    return value.get_secret_value() if value is not None else None


class LocalConfig(BaseModel):
    nip: str | None = Field(default=None, description="Taxpayer/context NIP.")
    token: SecretStr | None = Field(default=None, description="KSeF authorization token.")
    context_type: str | None = Field(default=None, description="Token-auth context type.")
    cert: Path | None = Field(default=None, description="PEM certificate path for XAdES authentication.")
    key: Path | None = Field(default=None, description="PEM private key path for XAdES authentication.")
    key_password: SecretStr | None = Field(default=None, description="Password for an encrypted PEM private key.")
    p12: Path | None = Field(default=None, description="PKCS#12/PFX archive path for XAdES authentication.")
    p12_password: SecretStr | None = Field(default=None, description="Password for a PKCS#12/PFX archive.")
    poll_interval: float | None = Field(default=None, description="Authentication polling interval.")
    max_poll_attempts: int | None = Field(default=None, description="Authentication polling attempts.")

    @field_validator("cert", "key", "p12", mode="after")
    @classmethod
    def _expand_path(cls, value: Path | None) -> Path | None:
        return value.expanduser() if value else None


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
        "# Store secrets in environment variables such as KSEF2_TOKEN.",
        "[auth]",
    ])

    content = toml.dumps(config.model_dump(mode="json", exclude_none=True))

    return header + "\n" + content
