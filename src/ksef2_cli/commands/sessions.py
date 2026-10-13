"""Authentication and invoice-session inspection command group."""

from datetime import datetime
from enum import StrEnum
from typing import Annotated

import typer
from ksef2.clients import AuthenticatedClient
from ksef2.models import (
    AuthenticationSession,
    ListSessionsQuery,
    SessionSummary,
)

from ksef2_cli.context import run_authenticated, run_authenticated_command, run_command
from ksef2_cli.parsing import parse_iso_datetime
from ksef2_cli.results import CurrentSessionTerminated, SessionClosed


def _session_date(value: str | None, option_name: str) -> datetime | None:
    """Parse one optional session-date option, e.g. ``2026-01-01T00:00:00Z``."""
    return None if value is None else parse_iso_datetime(value, option_name=option_name)


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
        # The auth-session listing takes a page size only: ksef2 has no date or status
        # filters on it, unlike `invoice_sessions.list()` with its `ListSessionsQuery`.
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
    created_from: Annotated[
        str | None,
        typer.Option("--created-from", help="Created at or after, ISO datetime/date."),
    ] = None,
    created_to: Annotated[
        str | None,
        typer.Option("--created-to", help="Created at or before, ISO datetime/date."),
    ] = None,
    closed_from: Annotated[
        str | None,
        typer.Option("--closed-from", help="Closed at or after, ISO datetime/date."),
    ] = None,
    closed_to: Annotated[
        str | None,
        typer.Option("--closed-to", help="Closed at or before, ISO datetime/date."),
    ] = None,
    modified_from: Annotated[
        str | None,
        typer.Option(
            "--modified-from", help="Modified at or after, ISO datetime/date."
        ),
    ] = None,
    modified_to: Annotated[
        str | None,
        typer.Option(
            "--modified-to", help="Modified at or before, ISO datetime/date."
        ),
    ] = None,
    page_size: Annotated[int, typer.Option("--page-size", min=10, max=100)] = 10,
    all_pages: Annotated[bool, typer.Option("--all", help="Fetch all pages.")] = False,
) -> None:
    """List historical online or batch invoice sessions."""

    def operation() -> list[SessionSummary]:
        params = ListSessionsQuery(
            session_type=session_type.value,
            reference_number=reference_number,
            statuses=[item.value for item in status] or None,
            page_size=page_size,
            date_created_from=_session_date(created_from, "--created-from"),
            date_created_to=_session_date(created_to, "--created-to"),
            date_closed_from=_session_date(closed_from, "--closed-from"),
            date_closed_to=_session_date(closed_to, "--closed-to"),
            date_modified_from=_session_date(modified_from, "--modified-from"),
            date_modified_to=_session_date(modified_to, "--modified-to"),
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
