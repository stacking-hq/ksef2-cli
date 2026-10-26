"""Authentication command group."""

from pathlib import Path
from typing import Annotated

import typer
from ksef2 import Client
from ksef2.models import AuthenticationResumeState, AuthTokens
from pydantic import SecretStr

from ksef2_cli.context import (
    authenticate_client,
    get_settings,
    run_client_command,
    run_command,
    use_client,
)
from ksef2_cli.renderers.rows.auth import (
    MaskedAuthTokens,
    MaskedRefreshedToken,
    MaskedTokenCredentials,
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
    """Authenticate and show masked tokens. Use --save-state to retain credentials."""

    def command(client: Client) -> MaskedAuthTokens:
        state = authenticate_client(ctx, client).resume_state()
        if save_state is not None:
            _ = save_resume_state(save_state, state)
        return _masked_tokens(state.to_tokens())

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

    def command(client: Client) -> MaskedAuthTokens:
        source = state_file or get_settings(ctx).auth_state
        if source is None:
            fail("Provide --state-file, --auth-state, or KSEF2_AUTH_STATE.")

        state = renew_resume_state(client, read_resume_state(source))
        # Building the authenticated branch is what proves the saved state still
        # rehydrates one; the SDK keeps refreshing its access token on later requests.
        resume_authentication(client, state)
        _ = save_resume_state(save_state or source, state)
        return _masked_tokens(state.to_tokens())

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
        str | None,
        typer.Option(
            "--refresh-token",
            envvar="KSEF2_REFRESH_TOKEN",
            help="Refresh token. Prefer --auth-state to avoid tokens in process arguments.",
        ),
    ] = None,
    state_file: Annotated[
        Path | None,
        typer.Option(
            "--auth-state", "--state-file", exists=True, dir_okay=False,
            help=_STATE_FILE_HELP,
        ),
    ] = None,
    save_state: Annotated[
        Path | None,
        typer.Option("--save-state", dir_okay=False, help=_SAVE_STATE_HELP),
    ] = None,
) -> None:
    """Refresh access using saved state or an explicit refresh token; mask output."""

    def command(client: Client) -> MaskedRefreshedToken:
        source = state_file or get_settings(ctx).auth_state
        if source is not None and refresh_token is not None:
            fail("Provide only one of --auth-state and --refresh-token.")
        if source is None and refresh_token is None:
            fail("Provide --auth-state or --refresh-token (or KSEF2_REFRESH_TOKEN).")
        if save_state is not None and source is None:
            fail("--save-state requires --auth-state to preserve refresh-token expiry.")
        state = read_resume_state(source) if source is not None else None
        token = state.refresh_token.get_secret_value() if state else refresh_token
        assert token is not None
        refreshed = client.authentication.refresh(refresh_token=token)
        if state is not None:
            updated = AuthenticationResumeState(
                access_token=SecretStr(refreshed.access_token.token),
                access_token_valid_until=refreshed.access_token.valid_until,
                refresh_token=state.refresh_token,
                refresh_token_valid_until=state.refresh_token_valid_until,
            )
            assert source is not None
            _ = save_resume_state(save_state or source, updated)
        return MaskedRefreshedToken(
            access_token=MaskedTokenCredentials(
                valid_until=refreshed.access_token.valid_until
            )
        )

    run_client_command(ctx, command)


def _masked_tokens(tokens: AuthTokens) -> MaskedAuthTokens:
    return MaskedAuthTokens(
        access_token=MaskedTokenCredentials(valid_until=tokens.access_token.valid_until),
        refresh_token=MaskedTokenCredentials(valid_until=tokens.refresh_token.valid_until),
    )
