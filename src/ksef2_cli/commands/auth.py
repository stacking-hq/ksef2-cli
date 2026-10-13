"""Authentication command group."""

from pathlib import Path
from typing import Annotated

import typer
from ksef2 import Client
from ksef2.models import AuthTokens, RefreshedToken

from ksef2_cli.context import (
    authenticate_client,
    get_settings,
    run_client_command,
)
from ksef2_cli.runtime import (
    fail,
    read_resume_state,
    renew_resume_state,
    resume_authentication,
    save_resume_state,
)

app = typer.Typer(
    help="Authenticate, resume, and refresh KSeF access tokens.",
)

_SAVE_STATE_HELP = (
    "Write resumable auth state to this file. It holds bearer tokens in plain text."
)


@app.command("login")
def auth_login(
    ctx: typer.Context,
    save_state: Annotated[
        Path | None,
        typer.Option("--save-state", dir_okay=False, help=_SAVE_STATE_HELP),
    ] = None,
) -> None:
    """Authenticate with the configured method and print access/refresh tokens."""

    def command(client: Client) -> AuthTokens:
        state = authenticate_client(ctx, client).resume_state()
        if save_state is not None:
            _ = save_resume_state(save_state, state)
        return state.to_tokens()

    run_client_command(ctx, command)


@app.command("resume")
def auth_resume(
    ctx: typer.Context,
    state_file: Annotated[
        Path | None,
        typer.Option(
            "--state-file",
            exists=True,
            dir_okay=False,
            help="Saved auth state to reuse. Defaults to the global --auth-state.",
        ),
    ] = None,
    save_state: Annotated[
        Path | None,
        typer.Option(
            "--save-state",
            dir_okay=False,
            help="Write the resumed state, including any refreshed access token.",
        ),
    ] = None,
) -> None:
    """Reuse saved auth state, refreshing the access token when it expired."""

    def command(client: Client) -> AuthTokens:
        source = state_file or get_settings(ctx).auth_state
        if source is None:
            fail("Provide --state-file, --auth-state, or KSEF2_AUTH_STATE.")

        state = renew_resume_state(client, read_resume_state(source))
        # Building the authenticated branch is what proves the saved state still
        # rehydrates one; the SDK keeps refreshing its access token on later requests.
        resume_authentication(client, state)
        if save_state is not None:
            _ = save_resume_state(save_state, state)
        return state.to_tokens()

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
