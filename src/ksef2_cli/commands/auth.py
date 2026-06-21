"""Authentication command group."""

from typing import Annotated

import typer
from ksef2 import Client
from ksef2.domain.models.auth import AuthTokens, RefreshedToken

from ksef2_cli.context import authenticate_client, run_client_command

app = typer.Typer(help="Authenticate and refresh KSeF access tokens.")


@app.command("login")
def auth_login(ctx: typer.Context) -> None:
    """Authenticate with the configured method and print access/refresh tokens."""

    def command(client: Client) -> AuthTokens:
        return authenticate_client(ctx, client).auth_tokens

    run_client_command(ctx, command)


@app.command("refresh")
def auth_refresh(
    ctx: typer.Context,
    refresh_token: Annotated[
        str,
        typer.Option(
            "--refresh-token", envvar="KSEF2_REFRESH_TOKEN", help="Refresh token."
        ),
    ],
) -> None:
    """Exchange a refresh token for a new access token."""

    def command(client: Client) -> RefreshedToken:
        return client.authentication.refresh(refresh_token=refresh_token)

    run_client_command(ctx, command)
