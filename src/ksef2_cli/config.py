"""Shared CLI settings, profiles, and simple enum configuration."""

import os
import tomllib
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Callable, Literal, Mapping, Protocol, Self, TypeVar

from cryptography.x509 import Certificate
from ksef2 import Client, FormSchema
from ksef2.clients.authenticated import AuthenticatedClient
from ksef2.core.xades import XAdESPrivateKey
from ksef2.domain.models.auth import ContextIdentifierTypeEnum
from pydantic import BaseModel, Field, field_validator, model_validator
import toml

ModelT = TypeVar("ModelT", bound=BaseModel)


class EnvironmentName(StrEnum):
    production = "production"
    demo = "demo"
    test = "test"


class OutputMode(StrEnum):
    text = "text"
    json = "json"


class ProfileAuthType(StrEnum):
    token = "token"
    test_certificate = "test_certificate"
    xades_pem = "xades_pem"
    xades_p12 = "xades_p12"


ENVIRONMENT_MEMBERS = {
    EnvironmentName.production: "PRODUCTION",
    EnvironmentName.demo: "DEMO",
    EnvironmentName.test: "TEST",
}


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
    config_file: Path
    config_loaded: bool
    profile_name: str | None
    environment: EnvironmentName
    output: OutputMode
    verbose: bool
    nip: str | None
    token: str | None
    token_env: str | None
    context_type: Literal["nip", "internal_id", "nip_vat_ue", "peppol_id"]
    test_certificate: bool
    cert: Path | None
    key: Path | None
    key_password: str | None
    key_password_env: str | None
    p12: Path | None
    p12_password: str | None
    p12_password_env: str | None
    poll_interval: float
    max_poll_attempts: int
    runtime_overrides: RuntimeOverrides | None = None


CONFIG_ENV_VAR = "KSEF2_CONFIG"
PROFILE_ENV_VAR = "KSEF2_PROFILE"
CONFIG_FILE_MODE = 0o600


class ProfileAuthConfig(BaseModel):
    type: ProfileAuthType
    token_env: str | None = Field(
        default=None, description="Environment variable containing a KSeF token."
    )
    context_type: ContextIdentifierTypeEnum | None = Field(
        default=None, description="Token-auth context type."
    )
    cert: Path | None = Field(
        default=None, description="PEM certificate path for XAdES authentication."
    )
    key: Path | None = Field(
        default=None, description="PEM private key path for XAdES authentication."
    )
    key_password_env: str | None = Field(
        default=None,
        description="Environment variable containing an encrypted PEM key password.",
    )
    p12: Path | None = Field(
        default=None, description="PKCS#12/PFX archive path for XAdES authentication."
    )
    p12_password_env: str | None = Field(
        default=None,
        description="Environment variable containing a PKCS#12/PFX archive password.",
    )

    @field_validator("cert", "key", "p12", mode="after")
    @classmethod
    def _expand_path(cls, value: Path | None) -> Path | None:
        return value.expanduser() if value else None

    @model_validator(mode="after")
    def _validate_auth_fields(self) -> Self:
        if self.type is ProfileAuthType.token and not self.token_env:
            raise ValueError("Token profiles require auth.token_env.")
        if self.type is ProfileAuthType.xades_pem and (
            self.cert is None or self.key is None
        ):
            raise ValueError("PEM XAdES profiles require auth.cert and auth.key.")
        if self.type is ProfileAuthType.xades_p12 and self.p12 is None:
            raise ValueError("PKCS#12/PFX profiles require auth.p12.")
        return self


class ProfileConfig(BaseModel):
    environment: EnvironmentName
    nip: str
    auth: ProfileAuthConfig
    poll_interval: float | None = Field(
        default=None, ge=0.1, description="Authentication polling interval."
    )
    max_poll_attempts: int | None = Field(
        default=None, ge=1, description="Authentication polling attempts."
    )


class CliConfig(BaseModel):
    active_profile: str | None = None
    profiles: dict[str, ProfileConfig] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_active_profile(self) -> Self:
        if self.active_profile is not None and self.active_profile not in self.profiles:
            raise ValueError(
                f"Active profile {self.active_profile!r} is not defined."
            )
        return self


def default_config_path(environ: Mapping[str, str] | None = None) -> Path:
    env = os.environ if environ is None else environ
    override = env.get(CONFIG_ENV_VAR)
    if override:
        return Path(override).expanduser()
    config_home = Path(env.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return config_home.expanduser() / "ksef2-cli" / "config.toml"


def resolve_config_path(path: Path | None) -> Path:
    return path.expanduser() if path else default_config_path()


def load_cli_config(path: Path | None) -> CliConfig:
    config_path = resolve_config_path(path)
    if not config_path.exists():
        return CliConfig()

    payload = tomllib.loads(config_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Config file must be a TOML table.")

    return CliConfig.model_validate(payload)


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
    context_type: (
        ContextIdentifierTypeEnum
        | Literal["nip", "internal_id", "nip_vat_ue", "peppol_id"]
        | None
    ) = None,
    test_certificate: bool = False,
    cert: Path | None = None,
    key: Path | None = None,
    key_password: str | None = None,
    p12: Path | None = None,
    p12_password: str | None = None,
    poll_interval: float | None = None,
    max_poll_attempts: int | None = None,
    runtime_overrides: RuntimeOverrides | None = None,
    environ: Mapping[str, str] | None = None,
) -> Settings:
    env = os.environ if environ is None else environ
    resolved_config_file = resolve_config_path(config_file)
    local_config = (
        load_cli_config(resolved_config_file) if not no_config else CliConfig()
    )
    config_loaded = not no_config and resolved_config_file.exists()

    selected_profile_name = profile
    if selected_profile_name is None and not no_config:
        selected_profile_name = env.get(PROFILE_ENV_VAR) or local_config.active_profile
    if selected_profile_name is not None and no_config:
        raise ValueError("--profile cannot be used with --no-config.")

    selected_profile: ProfileConfig | None = None
    if selected_profile_name is not None:
        selected_profile = local_config.profiles.get(selected_profile_name)
        if selected_profile is None:
            raise ValueError(f"Profile {selected_profile_name!r} is not defined.")

    local_context_type = (
        selected_profile.auth.context_type.value
        if selected_profile and selected_profile.auth.context_type
        else None
    )
    requested_context_type = (
        context_type.value
        if isinstance(context_type, ContextIdentifierTypeEnum)
        else context_type
    )

    auth = _profile_auth_values(selected_profile)
    _apply_auth_overrides(
        auth,
        token=token,
        test_certificate=test_certificate,
        cert=cert,
        key=key,
        key_password=key_password,
        p12=p12,
        p12_password=p12_password,
    )

    effective_poll_interval = 1.0
    if selected_profile and selected_profile.poll_interval is not None:
        effective_poll_interval = selected_profile.poll_interval
    if poll_interval is not None:
        effective_poll_interval = poll_interval

    effective_max_poll_attempts = 60
    if selected_profile and selected_profile.max_poll_attempts is not None:
        effective_max_poll_attempts = selected_profile.max_poll_attempts
    if max_poll_attempts is not None:
        effective_max_poll_attempts = max_poll_attempts

    return Settings(
        config_file=resolved_config_file,
        config_loaded=config_loaded,
        profile_name=selected_profile_name,
        environment=environment
        or (selected_profile.environment if selected_profile else None)
        or EnvironmentName.production,
        output=OutputMode.json if json_output else output or OutputMode.text,
        verbose=verbose,
        nip=nip or (selected_profile.nip if selected_profile else None),
        token=auth["token"],
        token_env=auth["token_env"],
        context_type=requested_context_type or local_context_type or "nip",
        test_certificate=auth["test_certificate"],
        cert=auth["cert"],
        key=auth["key"],
        key_password=auth["key_password"],
        key_password_env=auth["key_password_env"],
        p12=auth["p12"],
        p12_password=auth["p12_password"],
        p12_password_env=auth["p12_password_env"],
        poll_interval=effective_poll_interval,
        max_poll_attempts=effective_max_poll_attempts,
        runtime_overrides=runtime_overrides,
    )


def _profile_auth_values(profile: ProfileConfig | None) -> dict[str, object]:
    values: dict[str, object] = {
        "token": None,
        "token_env": None,
        "test_certificate": False,
        "cert": None,
        "key": None,
        "key_password": None,
        "key_password_env": None,
        "p12": None,
        "p12_password": None,
        "p12_password_env": None,
    }
    if profile is None:
        return values

    auth = profile.auth
    if auth.type is ProfileAuthType.token:
        values["token_env"] = auth.token_env
    elif auth.type is ProfileAuthType.test_certificate:
        values["test_certificate"] = True
    elif auth.type is ProfileAuthType.xades_pem:
        values["cert"] = auth.cert
        values["key"] = auth.key
        values["key_password_env"] = auth.key_password_env
    elif auth.type is ProfileAuthType.xades_p12:
        values["p12"] = auth.p12
        values["p12_password_env"] = auth.p12_password_env
    return values


def _apply_auth_overrides(
    values: dict[str, object],
    *,
    token: str | None,
    test_certificate: bool,
    cert: Path | None,
    key: Path | None,
    key_password: str | None,
    p12: Path | None,
    p12_password: str | None,
) -> None:
    if token is not None:
        _clear_auth(values)
        values["token"] = token
    elif test_certificate:
        _clear_auth(values)
        values["test_certificate"] = True
    elif p12 is not None:
        _clear_auth(values)
        values["p12"] = p12
        values["p12_password"] = p12_password
    elif cert is not None or key is not None:
        if values["cert"] is None and values["key"] is None:
            _clear_auth(values)
        values["cert"] = cert or values["cert"]
        values["key"] = key or values["key"]
        values["key_password"] = key_password
        if key_password is not None:
            values["key_password_env"] = None
    else:
        if key_password is not None:
            values["key_password"] = key_password
            values["key_password_env"] = None
        if p12_password is not None:
            values["p12_password"] = p12_password
            values["p12_password_env"] = None


def _clear_auth(values: dict[str, object]) -> None:
    values["token"] = None
    values["token_env"] = None
    values["test_certificate"] = False
    values["cert"] = None
    values["key"] = None
    values["key_password"] = None
    values["key_password_env"] = None
    values["p12"] = None
    values["p12_password"] = None
    values["p12_password_env"] = None


def write_cli_config(path: Path, config: CliConfig, *, force: bool = False) -> None:
    config_path = path.expanduser()
    if config_path.exists() and not force:
        raise FileExistsError(
            f"{config_path} already exists. Re-run with --force to overwrite it."
        )

    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(render_cli_config(config), encoding="utf-8")
    config_path.chmod(CONFIG_FILE_MODE)


def render_cli_config(config: CliConfig) -> str:
    header = "\n".join(
        [
            "# ksef2-cli local profiles",
            "# CLI options override the selected profile for one invocation.",
            "# Store token and password secrets in environment variables.",
        ]
    )

    content = toml.dumps(config.model_dump(mode="json", exclude_none=True))
    return header + "\n" + content
