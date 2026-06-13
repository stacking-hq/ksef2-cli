"""Authentication and invoice-session inspection command group."""

from __future__ import annotations

from typing import Annotated, Any

import typer

from ksef2_cli.context import get_authenticated_client, run_command
from ksef2_cli.rendering import _render

app = typer.Typer(help='Inspect authentication and historical invoice sessions.')


@app.command("auth-list")
def sessions_auth_list(
    ctx: typer.Context,
    page_size: Annotated[int | None, typer.Option("--page-size", min=10, max=100)] = None,
    continuation_token: Annotated[str | None, typer.Option("--continuation-token")] = None,
    all_pages: Annotated[bool, typer.Option("--all", help="Fetch all pages.")] = False,
) -> None:
    """List active authentication sessions."""

    def operation() -> Any:
        runtime = get_authenticated_client(ctx)
        client, auth = runtime.client, runtime.auth
        with client:
            if all_pages:
                pages = list(auth.sessions.all(page_size=page_size))
                return [item for page in pages for item in page.items]
            return auth.sessions.query(page_size=page_size, continuation_token=continuation_token)

    _render(
        ctx,
        run_command(ctx, operation),
        title="Authentication Sessions",
        items_key="items",
        fields=["reference_number", "authentication_method", "is_current", "date_created"],
    )


@app.command("auth-close")
def sessions_auth_close(
    ctx: typer.Context,
    reference_number: Annotated[str, typer.Option("--reference")],
) -> None:
    """Close an authentication session by reference number."""

    def operation() -> dict[str, str]:
        runtime = get_authenticated_client(ctx)
        client, auth = runtime.client, runtime.auth
        with client:
            auth.sessions.close(reference_number=reference_number)
        return {"reference_number": reference_number, "closed": "true"}

    _render(ctx, run_command(ctx, operation), title="Closed Authentication Session")


@app.command("auth-terminate-current")
def sessions_auth_terminate_current(ctx: typer.Context) -> None:
    """Terminate the current authentication session."""

    def operation() -> dict[str, str]:
        runtime = get_authenticated_client(ctx)
        client, auth = runtime.client, runtime.auth
        with client:
            auth.sessions.terminate_current()
        return {"terminated_current": "true"}

    _render(ctx, run_command(ctx, operation), title="Terminated Current Session")


@app.command("invoice-list")
def sessions_invoice_list(
    ctx: typer.Context,
    session_type: Annotated[str, typer.Option("--type", help="online or batch.")],
    status: Annotated[list[str], typer.Option("--status", help="Session status filter. Repeat for multiple.")] = [],
    reference_number: Annotated[str | None, typer.Option("--reference")] = None,
    page_size: Annotated[int, typer.Option("--page-size", min=10, max=100)] = 10,
    all_pages: Annotated[bool, typer.Option("--all", help="Fetch all pages.")] = False,
) -> None:
    """List historical online or batch invoice sessions."""

    def operation() -> Any:
        from ksef2.domain.models.pagination import ListSessionsQuery

        params = ListSessionsQuery(
            session_type=session_type,
            reference_number=reference_number,
            statuses=status or None,
            page_size=page_size,
        )
        runtime = get_authenticated_client(ctx)
        client, auth = runtime.client, runtime.auth
        with client:
            if all_pages:
                pages = list(auth.invoice_sessions.all(session_type=session_type, params=params))
                return [session for page in pages for session in page.sessions]
            return auth.invoice_sessions.query(session_type=session_type, params=params)

    _render(
        ctx,
        run_command(ctx, operation),
        title="Invoice Sessions",
        items_key="sessions",
        fields=["reference_number", "status", "date_created", "total_invoice_count", "successful_invoice_count", "failed_invoice_count"],
    )
