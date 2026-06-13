"""Runtime context helpers for SDK-backed commands."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Literal, TypeVar

import typer

from ksef2_cli.config import ENVIRONMENT_MEMBERS, Settings
from ksef2_cli.rendering import console

AuthMethod = Literal["token", "test_certificate", "p12", "pem"]
T = TypeVar("T")


@dataclass(frozen=True)
class AuthenticatedContext:
    """An SDK client paired with its authenticated SDK facade."""

    client: Any
    auth: Any


def get_settings(ctx: typer.Context) -> Settings:
    """Return global CLI settings stored by the root callback."""

    if not isinstance(ctx.obj, Settings):
        raise RuntimeError("CLI settings were not initialized.")
    return ctx.obj


def create_client(ctx: typer.Context) -> Any:
    """Create a root SDK client for the selected KSeF environment."""

    settings = get_settings(ctx)
    if settings.runtime_overrides and settings.runtime_overrides.client_factory:
        return settings.runtime_overrides.client_factory()

    from ksef2 import Client, Environment

    environment = getattr(Environment, ENVIRONMENT_MEMBERS[settings.environment])
    return Client(environment=environment)


def fail(message: str, *, code: int = 1) -> None:
    """Print a user-facing error and exit."""

    console.print(f"[red]Error:[/] {message}")
    raise typer.Exit(code)


def run_command(ctx: typer.Context, operation: Callable[[], T]) -> T:
    """Run command work with consistent CLI error formatting."""

    try:
        return operation()
    except typer.Exit:
        raise
    except Exception as exc:
        if get_settings(ctx).verbose:
            console.print_exception()
        else:
            console.print(f"[red]Error:[/] {exc}")
        raise typer.Exit(1) from exc


def authenticate_client(ctx: typer.Context, client: Any) -> Any:
    """Authenticate an SDK client using the configured auth method."""

    settings = get_settings(ctx)
    method = select_auth_method(settings)

    if method == "token":
        return client.authentication.with_token(
            ksef_token=settings.token,
            nip=settings.nip,
            context_type=settings.context_type,
            poll_interval=settings.poll_interval,
            max_poll_attempts=settings.max_poll_attempts,
        )

    if method == "test_certificate":
        return client.authentication.with_test_certificate(
            nip=settings.nip,
            poll_interval=settings.poll_interval,
            max_poll_attempts=settings.max_poll_attempts,
        )

    if method == "p12":
        p12_loader = (
            settings.runtime_overrides.p12_credentials_loader
            if settings.runtime_overrides and settings.runtime_overrides.p12_credentials_loader
            else load_p12_credentials
        )
        cert, private_key = p12_loader(
            settings.p12,
            password=settings.p12_password,
        )
        return client.authentication.with_xades(
            nip=settings.nip,
            cert=cert,
            private_key=private_key,
            poll_interval=settings.poll_interval,
            max_poll_attempts=settings.max_poll_attempts,
        )

    pem_loader = (
        settings.runtime_overrides.pem_credentials_loader
        if settings.runtime_overrides and settings.runtime_overrides.pem_credentials_loader
        else load_pem_credentials
    )
    cert, private_key = pem_loader(
        cert_path=settings.cert,
        key_path=settings.key,
        key_password=settings.key_password,
    )
    return client.authentication.with_xades(
        nip=settings.nip,
        cert=cert,
        private_key=private_key,
        poll_interval=settings.poll_interval,
        max_poll_attempts=settings.max_poll_attempts,
    )


def get_authenticated_client(ctx: typer.Context) -> AuthenticatedContext:
    """Create and authenticate an SDK client for one command operation."""

    settings = get_settings(ctx)
    if settings.runtime_overrides and settings.runtime_overrides.authenticated_client_factory:
        return settings.runtime_overrides.authenticated_client_factory()

    client = create_client(ctx)
    return AuthenticatedContext(client=client, auth=authenticate_client(ctx, client))


def read_model(ctx: typer.Context, path: Any, model_type: type[Any]) -> Any:
    """Read a model payload, using a runtime fake when supplied by tests."""

    settings = get_settings(ctx)
    if settings.runtime_overrides and settings.runtime_overrides.model_reader:
        return settings.runtime_overrides.model_reader(path, model_type)

    from ksef2_cli.io import _read_model

    return _read_model(path, model_type)


def select_auth_method(settings: Settings) -> AuthMethod:
    """Validate auth settings and return the configured auth method."""

    if not settings.nip:
        fail("Authentication requires --nip, KSEF2_NIP, or config auth.nip.")

    has_pem = settings.cert is not None or settings.key is not None
    configured_methods = [
        ("token", settings.token is not None),
        ("test_certificate", settings.test_certificate),
        ("p12", settings.p12 is not None),
        ("pem", has_pem),
    ]
    selected = [name for name, enabled in configured_methods if enabled]

    if not selected:
        fail("Provide one auth method: --token, --test-cert, --cert/--key, or --p12.")
    if len(selected) > 1:
        fail("Provide only one auth method: --token, --test-cert, --cert/--key, or --p12.")

    method = selected[0]
    if method == "pem" and (settings.cert is None or settings.key is None):
        fail("Both --cert and --key are required for PEM XAdES authentication.")

    return method


def load_p12_credentials(path: Any, *, password: str | None, loader: Any | None = None) -> tuple[Any, Any]:
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
    cert_path: Any,
    key_path: Any,
    key_password: str | None,
    cert_loader: Any | None = None,
    key_loader: Any | None = None,
) -> tuple[Any, Any]:
    """Load certificate and private key from PEM files."""

    if cert_loader is None or key_loader is None:
        from ksef2.core.xades import load_certificate_from_pem, load_private_key_from_pem

        cert_loader = cert_loader or load_certificate_from_pem
        key_loader = key_loader or load_private_key_from_pem

    return (
        cert_loader(cert_path),
        key_loader(key_path, password=password_bytes(key_password)),
    )


def password_bytes(value: str | None) -> bytes | None:
    """Encode optional password text for SDK credential loaders."""

    return value.encode("utf-8") if value else None
