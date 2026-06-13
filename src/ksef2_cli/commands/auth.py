"""Authentication command group."""

from __future__ import annotations

from typing import Annotated, Any

import typer

from ksef2_cli.context import authenticate_client, create_client, fail, run_command
from ksef2_cli.rendering import _render

app = typer.Typer(help='Authenticate and refresh KSeF access tokens.')


@app.command("login")
def auth_login(ctx: typer.Context) -> None:
    """Authenticate with the configured method and print access/refresh tokens."""

    def operation() -> Any:
        with create_client(ctx) as client:
            auth = authenticate_client(ctx, client)
            return auth.auth_tokens

    _render(ctx, run_command(ctx, operation), title="Auth Tokens")


@app.command("refresh")
def auth_refresh(
    ctx: typer.Context,
    refresh_token: Annotated[
        str | None,
        typer.Option("--refresh-token", envvar="KSEF2_REFRESH_TOKEN", help="Refresh token."),
    ] = None,
) -> None:
    """Exchange a refresh token for a new access token."""

    def operation() -> Any:
        if not refresh_token:
            fail("Provide --refresh-token or KSEF2_REFRESH_TOKEN.")
        with create_client(ctx) as client:
            return client.authentication.refresh(refresh_token=refresh_token)

    _render(ctx, run_command(ctx, operation), title="Refreshed Token")
