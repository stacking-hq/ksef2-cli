"""Shared CLI settings and simple enum configuration."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Callable


class EnvironmentName(str, Enum):
    production = "production"
    demo = "demo"
    test = "test"


class OutputMode(str, Enum):
    table = "table"
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
