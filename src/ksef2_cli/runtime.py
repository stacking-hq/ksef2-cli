"""Typer-free runtime helpers for SDK-backed workflows."""

import os
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Literal, Protocol, TypeVar

from ksef2 import Client, Environment
from ksef2.clients.authenticated import AuthenticatedClient
from pydantic import BaseModel

from ksef2_cli.config import AuthenticatedRuntime, EnvironmentName, Settings
from ksef2_cli.exceptions import AuthenticationConfigError
from ksef2_cli.io import read_model_file

AuthMethod = Literal["token", "test_certificate", "p12", "pem"]
T = TypeVar("T")
ModelT = TypeVar("ModelT", bound=BaseModel)

if TYPE_CHECKING:
    from cryptography.x509 import Certificate
    from ksef2.core.xades import XAdESPrivateKey

type CredentialSource = bytes | str | Path


class P12ArchiveLoader(Protocol):
    def __call__(
        self,
        source: CredentialSource,
        *,
        password: bytes | None,
    ) -> tuple["Certificate", "XAdESPrivateKey"]: ...


class CertificateLoader(Protocol):
    def __call__(self, source: CredentialSource) -> "Certificate": ...


class PrivateKeyLoader(Protocol):
    def __call__(
        self,
        source: CredentialSource,
        *,
        password: bytes | None,
    ) -> "XAdESPrivateKey": ...


ENVIRONMENT_MAPPING = {
    EnvironmentName.production: Environment.PRODUCTION,
    EnvironmentName.demo: Environment.DEMO,
    EnvironmentName.test: Environment.TEST,
}


@dataclass
class AuthenticatedContext:
    """An SDK client paired with its authenticated SDK facade."""

    client: Client
    auth: AuthenticatedClient


def create_client(settings: Settings) -> Client:
    """Create a root SDK client for the selected KSeF environment."""

    if settings.runtime_overrides and settings.runtime_overrides.client_factory:
        return settings.runtime_overrides.client_factory()

    return Client(environment=ENVIRONMENT_MAPPING[settings.environment])


@contextmanager
def use_client(settings: Settings) -> Generator[Client]:
    """Create a root SDK client and manage its context lifecycle."""

    with create_client(settings) as client:
        yield client


def run_client(settings: Settings, operation: Callable[[Client], T]) -> T:
    """Run SDK client work inside the client's context manager."""

    with use_client(settings) as client:
        return operation(client)


def fail(message: str, *, code: int = 1) -> None:
    """Abort with a user-facing error."""

    raise AuthenticationConfigError(message, exit_code=code)


def authenticate_client(settings: Settings, client: Client) -> AuthenticatedClient:
    """Authenticate an SDK client using the configured auth method."""

    method = select_auth_method(settings)

    match method:
        case "token":
            assert settings.nip is not None
            token = resolve_secret(
                value=settings.token,
                envvar=settings.token_env,
                label="KSeF token",
            )
            assert token is not None
            assert settings.context_type is not None

            return client.authentication.with_token(
                ksef_token=token,
                nip=settings.nip,
                context_type=settings.context_type,
                poll_interval=settings.poll_interval,
                max_poll_attempts=settings.max_poll_attempts,
            )
        case "test_certificate":
            assert settings.nip is not None
            return client.authentication.with_test_certificate(
                nip=settings.nip,
                poll_interval=settings.poll_interval,
                max_poll_attempts=settings.max_poll_attempts,
            )
        case "p12":
            assert settings.p12 is not None
            p12_loader = (
                settings.runtime_overrides.p12_credentials_loader
                if settings.runtime_overrides
                and settings.runtime_overrides.p12_credentials_loader
                else load_p12_credentials
            )
            cert, private_key = p12_loader(
                settings.p12,
                password=resolve_secret(
                    value=settings.p12_password,
                    envvar=settings.p12_password_env,
                    label="PKCS#12/PFX password",
                ),
            )

            assert settings.nip is not None
            return client.authentication.with_xades(
                nip=settings.nip,
                cert=cert,
                private_key=private_key,
                poll_interval=settings.poll_interval,
                max_poll_attempts=settings.max_poll_attempts,
            )

        case "pem":
            pem_loader = (
                settings.runtime_overrides.pem_credentials_loader
                if settings.runtime_overrides
                and settings.runtime_overrides.pem_credentials_loader
                else load_pem_credentials
            )

            assert settings.cert is not None
            assert settings.key is not None
            cert, private_key = pem_loader(
                cert_path=settings.cert,
                key_path=settings.key,
                key_password=resolve_secret(
                    value=settings.key_password,
                    envvar=settings.key_password_env,
                    label="PEM private key password",
                ),
            )

            assert settings.nip is not None
            return client.authentication.with_xades(
                nip=settings.nip,
                cert=cert,
                private_key=private_key,
                poll_interval=settings.poll_interval,
                max_poll_attempts=settings.max_poll_attempts,
            )


def get_authenticated_client(settings: Settings) -> AuthenticatedRuntime:
    """Create and authenticate an SDK client for one command operation."""

    if (
        settings.runtime_overrides
        and settings.runtime_overrides.authenticated_client_factory
    ):
        return settings.runtime_overrides.authenticated_client_factory()

    client = create_client(settings)
    return AuthenticatedContext(
        client=client, auth=authenticate_client(settings, client)
    )


def run_authenticated(
    settings: Settings, operation: Callable[[AuthenticatedClient], T]
) -> T:
    """Run authenticated SDK work inside the client's context manager."""

    authenticated = get_authenticated_client(settings)
    with authenticated.client:
        return operation(authenticated.auth)


def read_model(settings: Settings, path: Path, model_type: type[ModelT]) -> ModelT:
    """Read a model payload, using a runtime fake when supplied by tests."""

    if settings.runtime_overrides and settings.runtime_overrides.model_reader:
        return settings.runtime_overrides.model_reader(path, model_type)

    return read_model_file(path, model_type)


def select_auth_method(settings: Settings) -> AuthMethod:
    """Validate auth settings and return the configured auth method."""

    if not settings.nip:
        fail(
            "Authentication requires --nip, KSEF2_NIP, "
            "or a selected profile with nip."
        )

    has_pem = settings.cert is not None or settings.key is not None
    configured_methods: list[tuple[AuthMethod, bool]] = [
        ("token", settings.token is not None or settings.token_env is not None),
        ("test_certificate", settings.test_certificate),
        ("p12", settings.p12 is not None),
        ("pem", has_pem),
    ]
    selected: list[AuthMethod] = [
        name for name, enabled in configured_methods if enabled
    ]

    if not selected:
        fail("Provide one auth method: --token, --test-cert, --cert/--key, or --p12.")
    if len(selected) > 1:
        fail(
            "Provide only one auth method: --token, --test-cert, --cert/--key, or --p12."
        )

    method = selected[0]
    if method == "pem" and (settings.cert is None or settings.key is None):
        fail("Both --cert and --key are required for PEM XAdES authentication.")

    return method


def resolve_secret(
    *,
    value: str | None,
    envvar: str | None,
    label: str,
) -> str | None:
    """Resolve a direct secret value or a profile-owned secret environment variable."""

    if value is not None:
        return value
    if envvar is None:
        return None

    env_value = os.environ.get(envvar)
    if env_value is None:
        fail(f"{label} environment variable {envvar} is not set.")
    return env_value


def load_p12_credentials(
    path: Path,
    *,
    password: str | None,
    loader: P12ArchiveLoader | None = None,
) -> tuple["Certificate", "XAdESPrivateKey"]:
    """Load certificate and private key from a PKCS#12/PFX archive."""

    if loader is None:
        from ksef2.core.xades import load_certificate_and_key_from_p12

        loader = load_certificate_and_key_from_p12

    return loader(
        path,
        password=password_bytes(password),
    )


def load_pem_credentials(
    *,
    cert_path: Path,
    key_path: Path,
    key_password: str | None,
    cert_loader: CertificateLoader | None = None,
    key_loader: PrivateKeyLoader | None = None,
) -> tuple["Certificate", "XAdESPrivateKey"]:
    """Load certificate and private key from PEM files."""

    if cert_loader is None or key_loader is None:
        from ksef2.core.xades import (
            load_certificate_from_pem,
            load_private_key_from_pem,
        )

        cert_loader = cert_loader or load_certificate_from_pem
        key_loader = key_loader or load_private_key_from_pem

    return (
        cert_loader(cert_path),
        key_loader(key_path, password=password_bytes(key_password)),
    )


def password_bytes(value: str | None) -> bytes | None:
    """Encode optional password text for SDK credential loaders."""

    return value.encode("utf-8") if value else None
