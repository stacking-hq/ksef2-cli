"""Typer-free runtime helpers for SDK-backed workflows."""

import os
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Callable, NoReturn, Protocol, TypeVar

from ksef2 import Client
from ksef2.clients.authenticated import AuthenticatedClient
from ksef2.profiles import ProfileAuthType
from pydantic import BaseModel

from ksef2_cli.config import AuthenticatedRuntime, Settings
from ksef2_cli.exceptions import AuthenticationConfigError
from ksef2_cli.io import read_model_file

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


@dataclass
class AuthenticatedContext:
    """An SDK client paired with its authenticated SDK facade."""

    client: Client
    auth: AuthenticatedClient


def create_client(settings: Settings) -> Client:
    """Create a root SDK client for the selected KSeF environment."""

    if settings.runtime_overrides and settings.runtime_overrides.client_factory:
        return settings.runtime_overrides.client_factory()

    return Client(environment=settings.environment)


@contextmanager
def use_client(settings: Settings) -> Generator[Client]:
    """Create a root SDK client and manage its context lifecycle."""

    with create_client(settings) as client:
        yield client


def run_client(settings: Settings, operation: Callable[[Client], T]) -> T:
    """Run SDK client work inside the client's context manager."""

    with use_client(settings) as client:
        return operation(client)


def fail(message: str, *, code: int = 1) -> NoReturn:
    """Abort with a user-facing error."""

    raise AuthenticationConfigError(message, exit_code=code)


def authenticate_client(settings: Settings, client: Client) -> AuthenticatedClient:
    """Authenticate an SDK client from the selected profile or from CLI flags."""

    profile = settings.profile
    if profile is not None:
        # ``with_profile()`` reads profile auth, secrets, and polling on its own. Any
        # CLI auth flag, or a profile-displacing --env/--nip, has to stay CLI-side
        # because that SDK call cannot override a profile's values.
        overrides_profile = (
            settings.nip != profile.nip
            or settings.environment is not profile.sdk_environment
            or settings.token is not None
            or settings.context_type is not None
            or settings.test_certificate
            or settings.cert is not None
            or settings.key is not None
            or settings.key_password is not None
            or settings.p12 is not None
            or settings.p12_password is not None
        )
        if not overrides_profile:
            return client.authentication.with_profile(
                settings.profile_name,
                config_path=settings.config_file,
                timeout=settings.auth_timeout,
                poll_interval=settings.poll_interval,
            )

    auth_config = profile.auth if profile is not None else None
    method = select_auth_method(settings)
    if method is None:
        if auth_config is None:
            fail(
                "Provide one auth method: --token, --test-cert, --cert/--key, or --p12."
            )
        method = auth_config.type

    if not settings.nip:
        fail(
            "Authentication requires --nip, KSEF2_NIP, or a selected profile with nip."
        )

    match method:
        case ProfileAuthType.TOKEN:
            token_env = auth_config.token_env if auth_config is not None else None
            token = resolve_secret(
                value=settings.token,
                envvar=token_env,
                label="KSeF token",
            )
            if token is None:
                fail(
                    "Set auth.token_env in the profile or pass --token for token auth."
                )
            profile_context_type = (
                auth_config.context_type if auth_config is not None else None
            )
            context_type = settings.context_type or profile_context_type or "nip"
            return client.authentication.with_token(
                ksef_token=token,
                nip=settings.nip,
                context_type=context_type,
                poll_interval=settings.effective_poll_interval,
                timeout=settings.effective_auth_timeout,
            )
        case ProfileAuthType.TEST_CERTIFICATE:
            return client.authentication.with_test_certificate(
                nip=settings.nip,
                poll_interval=settings.effective_poll_interval,
                timeout=settings.effective_auth_timeout,
            )
        case ProfileAuthType.XADES_P12:
            profile_p12 = auth_config.p12 if auth_config is not None else None
            p12_password_env = (
                auth_config.p12_password_env if auth_config is not None else None
            )
            p12_path = settings.p12 or profile_p12
            if p12_path is None:
                fail("Provide --p12 or a profile with auth.p12 for PKCS#12/PFX auth.")

            p12_loader = (
                settings.runtime_overrides.p12_credentials_loader
                if settings.runtime_overrides
                and settings.runtime_overrides.p12_credentials_loader
                else load_p12_credentials
            )
            cert, private_key = p12_loader(
                p12_path,
                password=resolve_secret(
                    value=settings.p12_password,
                    envvar=p12_password_env,
                    label="PKCS#12/PFX password",
                ),
            )
            return client.authentication.with_xades(
                nip=settings.nip,
                cert=cert,
                private_key=private_key,
                poll_interval=settings.effective_poll_interval,
                timeout=settings.effective_auth_timeout,
            )
        case ProfileAuthType.XADES_PEM:
            pem_loader = (
                settings.runtime_overrides.pem_credentials_loader
                if settings.runtime_overrides
                and settings.runtime_overrides.pem_credentials_loader
                else load_pem_credentials
            )
            profile_cert = auth_config.cert if auth_config is not None else None
            profile_key = auth_config.key if auth_config is not None else None
            key_password_env = (
                auth_config.key_password_env if auth_config is not None else None
            )
            cert_path = settings.cert or profile_cert
            key_path = settings.key or profile_key
            if cert_path is None or key_path is None:
                fail("Both --cert and --key are required for PEM XAdES authentication.")

            cert, private_key = pem_loader(
                cert_path=cert_path,
                key_path=key_path,
                key_password=resolve_secret(
                    value=settings.key_password,
                    envvar=key_password_env,
                    label="PEM private key password",
                ),
            )
            return client.authentication.with_xades(
                nip=settings.nip,
                cert=cert,
                private_key=private_key,
                poll_interval=settings.effective_poll_interval,
                timeout=settings.effective_auth_timeout,
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


def select_auth_method(settings: Settings) -> ProfileAuthType | None:
    """Return the auth method requested by CLI flags, or None when the profile owns it."""

    has_pem = settings.cert is not None or settings.key is not None
    configured_methods: list[tuple[ProfileAuthType, bool]] = [
        (ProfileAuthType.TOKEN, settings.token is not None),
        (ProfileAuthType.TEST_CERTIFICATE, settings.test_certificate),
        (ProfileAuthType.XADES_P12, settings.p12 is not None),
        (ProfileAuthType.XADES_PEM, has_pem),
    ]
    selected: list[ProfileAuthType] = [
        name for name, enabled in configured_methods if enabled
    ]

    if len(selected) > 1:
        fail(
            "Provide only one auth method: --token, --test-cert, --cert/--key, or --p12."
        )

    return selected[0] if selected else None


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
