"""Shared CLI settings and simple enum configuration."""

import os
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Callable, Mapping, Protocol, TypeVar

from cryptography.x509 import Certificate
from ksef2 import Client, Environment, FormSchema
from ksef2.clients.authenticated import AuthenticatedClient
from ksef2.core.xades import XAdESPrivateKey
from ksef2.domain.models.auth import ContextIdentifierType, ContextIdentifierTypeEnum

# The ksef2 SDK owns the profile schema. These are the same models that
# ``client.authentication.with_profile()`` reads, so the CLI never redeclares them.
from ksef2.profiles import (
    PROFILE_ENV_VAR,
    CliProfileConfig,
    ProfileConfig,
    default_profile_config_path,
    load_cli_profile,
    load_profile_config,
    write_profile_config,
)
from pydantic import BaseModel

ModelT = TypeVar("ModelT", bound=BaseModel)

# Authentication polling defaults mirror the SDK ``with_token``/``with_xades``
# defaults; the SDK does not publish them as constants.
DEFAULT_POLL_INTERVAL = 1.0
DEFAULT_AUTH_TIMEOUT = 60.0


class EnvironmentName(StrEnum):
    """Typer-facing environment choice kept lowercase for readable ``--help``."""

    production = "production"
    demo = "demo"
    test = "test"

    @property
    def sdk_environment(self) -> Environment:
        return Environment[self.value.upper()]


class OutputMode(StrEnum):
    text = "text"
    json = "json"


class FormSchemaChoice(StrEnum):
    FA2 = "FA2"
    FA3 = "FA3"
    FA_RR1 = "FA_RR1"
    PEF3 = "PEF3"
    PEF_KOR3 = "PEF_KOR3"

    @property
    def form_schema(self) -> FormSchema:
        return FormSchema[self.value]


FORM_SCHEMA_NAMES = ", ".join(item for item in FormSchemaChoice.__members__)


class AuthenticatedRuntime(Protocol):
    client: "Client"
    auth: "AuthenticatedClient"


class ModelReader(Protocol):
    def __call__(self, path: Path, model_type: type[ModelT]) -> ModelT: ...


class P12CredentialsLoader(Protocol):
    def __call__(
        self, path: Path, *, password: str | None
    ) -> tuple["Certificate", "XAdESPrivateKey"]: ...


class PemCredentialsLoader(Protocol):
    def __call__(
        self,
        *,
        cert_path: Path,
        key_path: Path,
        key_password: str | None,
    ) -> tuple["Certificate", "XAdESPrivateKey"]: ...


@dataclass(frozen=True)
class RuntimeOverrides:
    client_factory: Callable[[], "Client"] | None = None
    authenticated_client_factory: Callable[[], AuthenticatedRuntime] | None = None
    model_reader: ModelReader | None = None
    p12_credentials_loader: P12CredentialsLoader | None = None
    pem_credentials_loader: PemCredentialsLoader | None = None


@dataclass(frozen=True)
class Settings:
    """Resolved settings for one invocation: CLI flags layered over a profile."""

    config_file: Path
    config_loaded: bool
    profile_name: str | None
    profile: ProfileConfig | None
    environment: Environment
    output: OutputMode
    verbose: bool
    nip: str | None
    token: str | None
    context_type: ContextIdentifierTypeEnum | ContextIdentifierType | None
    test_certificate: bool
    cert: Path | None
    key: Path | None
    key_password: str | None
    p12: Path | None
    p12_password: str | None
    poll_interval: float | None
    auth_timeout: float | None
    runtime_overrides: RuntimeOverrides | None = None

    @property
    def effective_poll_interval(self) -> float:
        if self.poll_interval is not None:
            return self.poll_interval
        if self.profile is not None and self.profile.poll_interval is not None:
            return self.profile.poll_interval
        return DEFAULT_POLL_INTERVAL

    @property
    def effective_auth_timeout(self) -> float:
        if self.auth_timeout is not None:
            return self.auth_timeout
        # Mirrors the timeout the SDK derives from a profile's polling attempts.
        if self.profile is not None and self.profile.max_poll_attempts is not None:
            return self.profile.max_poll_attempts * self.effective_poll_interval
        return DEFAULT_AUTH_TIMEOUT


def resolve_config_path(path: Path | None) -> Path:
    return path.expanduser() if path else default_profile_config_path()


def load_cli_config(path: Path | None) -> CliProfileConfig:
    return load_profile_config(resolve_config_path(path))


def write_cli_config(
    path: Path, config: CliProfileConfig, *, force: bool = False
) -> None:
    config_path = path.expanduser()
    if config_path.exists() and not force:
        raise FileExistsError(
            f"{config_path} already exists. Re-run with --force to overwrite it."
        )

    write_profile_config(config_path, config)


def resolve_settings(
    *,
    environment: EnvironmentName | None = None,
    output: OutputMode | None = None,
    json_output: bool = False,
    verbose: bool = False,
    config_file: Path | None = None,
    no_config: bool = False,
    profile: str | None = None,
    nip: str | None = None,
    token: str | None = None,
    context_type: ContextIdentifierTypeEnum | ContextIdentifierType | None = None,
    test_certificate: bool = False,
    cert: Path | None = None,
    key: Path | None = None,
    key_password: str | None = None,
    p12: Path | None = None,
    p12_password: str | None = None,
    poll_interval: float | None = None,
    auth_timeout: float | None = None,
    runtime_overrides: RuntimeOverrides | None = None,
    environ: Mapping[str, str] | None = None,
) -> Settings:
    env = os.environ if environ is None else environ
    resolved_config_file = resolve_config_path(config_file)

    selected_name: str | None = None
    selected_profile: ProfileConfig | None = None
    if no_config:
        if profile is not None:
            raise ValueError("--profile cannot be used with --no-config.")
    else:
        # ``load_cli_profile`` owns selection order and unknown-profile errors, but
        # raises when nothing is selected, so an empty local config is detected first.
        local_config = load_profile_config(resolved_config_file)
        if (
            profile is not None
            or PROFILE_ENV_VAR in env
            or local_config.active_profile is not None
        ):
            selected_name, selected_profile = load_cli_profile(
                profile, config_path=resolved_config_file, environ=env
            )

    resolved_environment = Environment.PRODUCTION
    if selected_profile is not None:
        resolved_environment = selected_profile.sdk_environment
    if environment is not None:
        resolved_environment = environment.sdk_environment

    resolved_nip = nip
    if resolved_nip is None and selected_profile is not None:
        resolved_nip = selected_profile.nip

    return Settings(
        config_file=resolved_config_file,
        config_loaded=resolved_config_file.exists(),
        profile_name=selected_name,
        profile=selected_profile,
        environment=resolved_environment,
        output=OutputMode.json if json_output else output or OutputMode.text,
        verbose=verbose,
        nip=resolved_nip,
        token=token,
        context_type=context_type,
        test_certificate=test_certificate,
        cert=cert,
        key=key,
        key_password=key_password,
        p12=p12,
        p12_password=p12_password,
        poll_interval=poll_interval,
        auth_timeout=auth_timeout,
        runtime_overrides=runtime_overrides,
    )
