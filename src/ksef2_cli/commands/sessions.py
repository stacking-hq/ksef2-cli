"""Authentication and invoice-session inspection command group."""

from enum import StrEnum
from typing import Annotated

import typer
from ksef2.clients.authenticated import AuthenticatedClient
from ksef2.domain.models.auth import (
    AuthenticationSession,
    AuthenticationSessionsResponse,
)
from ksef2.domain.models.session import ListSessionsResponse, SessionSummary

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
        str | None, typer.Option("--continuation-token")
    ] = None,
    all_pages: Annotated[bool, typer.Option("--all", help="Fetch all pages.")] = False,
) -> None:
    """List active authentication sessions."""

    def list_sessions(
        auth: AuthenticatedClient,
    ) -> AuthenticationSessionsResponse | list[AuthenticationSession]:
        if all_pages:
            pages = list(auth.sessions.all(page_size=page_size))
            return [item for page in pages for item in page.items]
        return auth.sessions.query(
            page_size=page_size, continuation_token=continuation_token
        )

    run_authenticated_command(ctx, list_sessions)


@app.command("auth-close")
def sessions_auth_close(
    ctx: typer.Context,
    reference_number: Annotated[str, typer.Option("--reference")],
) -> None:
    """Close an authentication session by reference number."""

    def operation() -> SessionClosed:
        run_authenticated(
            ctx,
            lambda auth: auth.sessions.close(reference_number=reference_number),
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

    def operation() -> ListSessionsResponse | list[SessionSummary]:
        from ksef2.domain.models.pagination import ListSessionsQuery

        params = ListSessionsQuery(
            session_type=session_type.value,
            reference_number=reference_number,
            statuses=[item.value for item in status] or None,
            page_size=page_size,
        )

        def list_invoice_sessions(
            auth: AuthenticatedClient,
        ) -> ListSessionsResponse | list[SessionSummary]:
            if all_pages:
                pages = list(
                    auth.invoice_sessions.all(
                        session_type=session_type.value, params=params
                    )
                )
                return [session for page in pages for session in page.sessions]
            return auth.invoice_sessions.query(
                session_type=session_type.value, params=params
            )

        return run_authenticated(ctx, list_invoice_sessions)

    run_command(ctx, operation)
