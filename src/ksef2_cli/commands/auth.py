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
    run_command,
    use_client,
)
from ksef2_cli.results import AuthStateRemoved
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
_STATE_FILE_HELP = "Saved auth state to reuse. Defaults to the global --auth-state."


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
            "--auth-state",
            exists=True,
            dir_okay=False,
            help=_STATE_FILE_HELP,
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


@app.command("logout")
def auth_logout(
    ctx: typer.Context,
    state_file: Annotated[
        Path | None,
        typer.Option(
            "--state-file",
            "--auth-state",
            exists=True,
            dir_okay=False,
            help=_STATE_FILE_HELP,
        ),
    ] = None,
) -> None:
    """End the saved session and remove its auth state file."""

    def operation() -> AuthStateRemoved:
        source = state_file or get_settings(ctx).auth_state
        if source is None:
            fail("Provide --state-file, --auth-state, or KSEF2_AUTH_STATE.")

        # The state file names whose session to end, so it is resumed on its own instead
        # of going through the auth method in settings: that method may be a profile or a
        # token, and it would leave `logout` terminating some other subject's session.
        # Nothing is written back here, because these tokens are the ones being retired.
        with use_client(ctx) as client:
            auth = resume_authentication(client, read_resume_state(source))
            auth.sessions.terminate_current()

        # Only after KSeF confirmed the session ended: a failed call leaves a credential
        # that still works, and deleting it would strand that session.
        source.unlink(missing_ok=True)
        return AuthStateRemoved(path=source)

    run_command(ctx, operation)


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
