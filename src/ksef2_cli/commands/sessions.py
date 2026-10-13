"""Authentication and invoice-session inspection command group."""

from enum import StrEnum
from typing import Annotated

import typer
from ksef2.clients import AuthenticatedClient
from ksef2.models import (
    AuthenticationSession,
    SessionSummary,
)

from ksef2_cli.context import run_authenticated, run_authenticated_command, run_command
from ksef2_cli.results import CurrentSessionTerminated, SessionClosed

app = typer.Typer(help="Inspect authentication and historical invoice sessions.")


@app.command("auth-list")
def sessions_auth_list(
    ctx: typer.Context,
    page_size: Annotated[
        int | None, typer.Option("--page-size", min=10, max=100)
    ] = None,
    continuation_token: Annotated[
        str | None,
        typer.Option(
            "--continuation-token",
            help="Unsupported since ksef2 1.0; paging is handled internally.",
        ),
    ] = None,
    all_pages: Annotated[bool, typer.Option("--all", help="Fetch all pages.")] = False,
) -> None:
    """List active authentication sessions."""

    def validate() -> None:
        if continuation_token:
            raise ValueError(
                "--continuation-token is no longer supported; ksef2 1.0 pages "
                "sessions internally. Use --page-size and --all instead."
            )

    def list_sessions(
        auth: AuthenticatedClient,
    ) -> list[AuthenticationSession]:
        pager = auth.sessions.list(page_size=page_size)
        if all_pages:
            return list(pager)
        return pager.first_page()

    run_authenticated_command(ctx, list_sessions, validate=validate)


@app.command("auth-close")
def sessions_auth_close(
    ctx: typer.Context,
    reference_number: Annotated[str, typer.Option("--reference")],
) -> None:
    """Close an authentication session by reference number."""

    def operation() -> SessionClosed:
        run_authenticated(
            ctx,
            lambda auth: auth.sessions.terminate(reference_number=reference_number),
        )
        return SessionClosed(reference_number=reference_number)

    run_command(ctx, operation)


@app.command("auth-terminate-current")
def sessions_auth_terminate_current(ctx: typer.Context) -> None:
    """Terminate the current authentication session."""

    def operation() -> CurrentSessionTerminated:
        run_authenticated(ctx, lambda auth: auth.sessions.terminate_current())
        return CurrentSessionTerminated()

    run_command(ctx, operation)


class SessionTypeChoice(StrEnum):
    ONLINE = "online"
    BATCH = "batch"


class SessionStatusChoice(StrEnum):
    IN_PROGRESS = "in_progress"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


@app.command("invoice-list")
def sessions_invoice_list(
    ctx: typer.Context,
    session_type: Annotated[
        SessionTypeChoice, typer.Option("--type", help="online or batch.")
    ],
    status: Annotated[
        list[SessionStatusChoice],
        typer.Option("--status", help="Session status filter. Repeat for multiple."),
    ] = [],
    reference_number: Annotated[str | None, typer.Option("--reference")] = None,
    page_size: Annotated[int, typer.Option("--page-size", min=10, max=100)] = 10,
    all_pages: Annotated[bool, typer.Option("--all", help="Fetch all pages.")] = False,
) -> None:
    """List historical online or batch invoice sessions."""

    def operation() -> list[SessionSummary]:
        from ksef2.models import ListSessionsQuery

        params = ListSessionsQuery(
            session_type=session_type.value,
            reference_number=reference_number,
            statuses=[item.value for item in status] or None,
            page_size=page_size,
        )

        def list_invoice_sessions(
            auth: AuthenticatedClient,
        ) -> list[SessionSummary]:
            pager = auth.invoice_sessions.list(
                session_type=session_type.value, params=params
            )
            if all_pages:
                return list(pager)
            return pager.first_page()

        return run_authenticated(ctx, list_invoice_sessions)

    run_command(ctx, operation)
