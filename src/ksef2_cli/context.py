"""Typer adapters for SDK-backed command execution."""

from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Callable, TypeVar

import typer
from ksef2 import Client
from ksef2.clients.authenticated import AuthenticatedClient
from pydantic import BaseModel

from ksef2_cli.config import AuthenticatedRuntime, Settings
from ksef2_cli.exceptions import CliError, error_from_exception, render_cli_error
from ksef2_cli.renderers import console, render
from ksef2_cli.runtime import (
    AuthMethod,
    AuthenticatedContext,
    CertificateLoader,
    CredentialSource,
    ENVIRONMENT_MAPPING,
    P12ArchiveLoader,
    PrivateKeyLoader,
    authenticate_client as authenticate_runtime_client,
    create_client as create_runtime_client,
    fail,
    get_authenticated_client as get_runtime_authenticated_client,
    load_p12_credentials,
    load_pem_credentials,
    password_bytes,
    read_model as read_runtime_model,
    run_authenticated as run_runtime_authenticated,
    run_client as run_runtime_client,
    select_auth_method,
    use_client as use_runtime_client,
)

T = TypeVar("T")
ModelT = TypeVar("ModelT", bound=BaseModel)


def get_settings(ctx: typer.Context) -> Settings:
    """Return global CLI settings stored by the root callback."""

    if not isinstance(ctx.obj, Settings):
        raise RuntimeError("CLI settings were not initialized.")
    return ctx.obj


def create_client(ctx: typer.Context) -> Client:
    """Create a root SDK client for the selected KSeF environment."""

    return create_runtime_client(get_settings(ctx))


@contextmanager
def use_client(ctx: typer.Context) -> Generator[Client]:
    """Create a root SDK client and manage its context lifecycle."""

    with use_runtime_client(get_settings(ctx)) as client:
        yield client


def run_client(ctx: typer.Context, operation: Callable[[Client], T]) -> T:
    """Run SDK client work inside the client's context manager."""

    return run_runtime_client(get_settings(ctx), operation)


def run_client_command(
    ctx: typer.Context,
    work: Callable[[Client], object],
) -> None:
    """Run SDK client work with command error handling and result rendering."""

    run_command(ctx, lambda: run_client(ctx, work))


def run_authenticated_command(
    ctx: typer.Context,
    work: Callable[[AuthenticatedClient], object],
    *,
    validate: Callable[[], object] | None = None,
) -> None:
    """Run authenticated SDK work with command error handling and rendering."""

    def operation() -> object:
        if validate is not None:
            validate()
        return run_authenticated(ctx, work)

    run_command(ctx, operation)


def run_command(
    ctx: typer.Context,
    operation: Callable[[], object],
    *,
    render_result: bool = True,
    exit_code_from_result: Callable[[object], int] | None = None,
) -> None:
    """Run command work with consistent error formatting and result rendering."""

    try:
        result = operation()
        if render_result:
            render(ctx, result)
        if exit_code_from_result is not None:
            exit_code = exit_code_from_result(result)
            if exit_code:
                raise typer.Exit(exit_code)
    except CliError as exc:
        render_cli_error(exc, console=console, verbose=get_settings(ctx).verbose)
        raise typer.Exit(exc.exit_code) from exc
    except typer.Exit:
        raise
    except Exception as exc:
        error = error_from_exception(exc)
        render_cli_error(error, console=console, verbose=get_settings(ctx).verbose)
        raise typer.Exit(error.exit_code) from exc


def authenticate_client(ctx: typer.Context, client: Client) -> AuthenticatedClient:
    """Authenticate an SDK client using the configured auth method."""

    return authenticate_runtime_client(get_settings(ctx), client)


def get_authenticated_client(ctx: typer.Context) -> AuthenticatedRuntime:
    """Create and authenticate an SDK client for one command operation."""

    return get_runtime_authenticated_client(get_settings(ctx))


def run_authenticated(
    ctx: typer.Context, operation: Callable[[AuthenticatedClient], T]
) -> T:
    """Run authenticated SDK work inside the client's context manager."""

    return run_runtime_authenticated(get_settings(ctx), operation)


def read_model(ctx: typer.Context, path: Path, model_type: type[ModelT]) -> ModelT:
    """Read a model payload, using a runtime fake when supplied by tests."""

    return read_runtime_model(get_settings(ctx), path, model_type)
