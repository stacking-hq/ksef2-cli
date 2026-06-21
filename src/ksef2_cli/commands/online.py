"""Online invoice session command group."""

from pathlib import Path
from typing import Annotated

import typer
from ksef2.clients.authenticated import AuthenticatedClient
from ksef2.domain.models.invoices import SendInvoiceResponse
from ksef2.domain.models.session import (
    OnlineSessionState,
    SessionInvoicesResponse,
    SessionInvoiceStatusResponse,
    SessionStatusResponse,
)

from ksef2_cli.config import FORM_SCHEMA_NAMES, FormSchemaChoice
from ksef2_cli.context import run_authenticated, run_authenticated_command, run_command
from ksef2_cli.io import (
    SECRET_MODEL_FILE_MODE,
    read_model_file,
    write_bytes_file,
    write_model_file,
)
from ksef2_cli.results import (
    FocusedResult,
    OnlineSendItem,
    OnlineSendResult,
    OnlineSessionOpened,
    SavedFile,
    SessionClosed,
)

app = typer.Typer(help="Open, resume, and operate online invoice sessions.")

type OnlineSendResponse = SendInvoiceResponse | SessionInvoiceStatusResponse


@app.command("open")
def online_open(
    ctx: typer.Context,
    state_file: Annotated[
        Path | None, typer.Option("--state-file", dir_okay=False)
    ] = None,
    form: Annotated[
        FormSchemaChoice,
        typer.Option("--form", help=f"Form schema: {FORM_SCHEMA_NAMES}."),
    ] = FormSchemaChoice.FA3,
) -> None:
    """Open an online session and optionally save resumable state."""

    def operation() -> OnlineSessionOpened:
        def open_session(auth: AuthenticatedClient) -> OnlineSessionState:
            session = auth.online_session(form_code=form.form_schema)
            return session.get_state()

        state = run_authenticated(ctx, open_session)
        if state_file:
            write_model_file(state_file, state, file_mode=SECRET_MODEL_FILE_MODE)
        return OnlineSessionOpened(state_file=state_file, state=state)

    run_command(ctx, operation)


@app.command("send")
def online_send(
    ctx: typer.Context,
    invoice_paths: Annotated[list[Path], typer.Argument(exists=True, dir_okay=False)],
    state_file: Annotated[
        Path | None,
        typer.Option(
            "--state-file",
            exists=True,
            dir_okay=False,
            help="Resume an existing online session.",
        ),
    ] = None,
    save_state: Annotated[
        Path | None,
        typer.Option(
            "--save-state", dir_okay=False, help="Save opened/resumed session state."
        ),
    ] = None,
    form: Annotated[
        FormSchemaChoice,
        typer.Option("--form", help=f"Form schema: {FORM_SCHEMA_NAMES}."),
    ] = FormSchemaChoice.FA3,
    wait: Annotated[
        bool, typer.Option("--wait", help="Wait for each invoice to finish processing.")
    ] = False,
    keep_open: Annotated[
        bool, typer.Option("--keep-open", help="Leave the session open after sending.")
    ] = False,
    timeout: Annotated[float, typer.Option("--timeout", min=1.0)] = 60.0,
    poll_interval: Annotated[float, typer.Option("--poll-interval", min=0.1)] = 2.0,
) -> None:
    """Send one or more invoice XML files through an online session."""

    def operation() -> FocusedResult[OnlineSendResult, OnlineSendItem]:
        def send_invoices(
            auth: AuthenticatedClient,
        ) -> tuple[list[OnlineSendItem], OnlineSessionState]:
            if state_file:
                session = auth.resume_online_session(
                    read_model_file(state_file, OnlineSessionState)
                )
            else:
                session = auth.online_session(form_code=form.form_schema)
            try:
                results: list[OnlineSendItem] = []
                for invoice_path in invoice_paths:
                    xml = invoice_path.read_bytes()
                    result: OnlineSendResponse
                    if wait:
                        result = session.send_invoice_and_wait(
                            invoice_xml=xml,
                            timeout=timeout,
                            poll_interval=poll_interval,
                        )
                    else:
                        result = session.send_invoice(invoice_xml=xml)
                    results.append(OnlineSendItem(file=invoice_path, result=result))
                state = session.get_state()
                return results, state
            finally:
                if not keep_open:
                    session.close()

        results, state = run_authenticated(ctx, send_invoices)
        if save_state:
            write_model_file(save_state, state, file_mode=SECRET_MODEL_FILE_MODE)
        payload = OnlineSendResult(
            state_file=save_state, closed=not keep_open, results=results
        )
        return FocusedResult(payload=payload, items=results)

    run_command(ctx, operation)


@app.command("status")
def online_status(
    ctx: typer.Context,
    state_file: Annotated[
        Path, typer.Option("--state-file", exists=True, dir_okay=False)
    ],
) -> None:
    """Fetch current status for a resumed online session."""

    def operation() -> SessionStatusResponse:
        def get_status(auth: AuthenticatedClient) -> SessionStatusResponse:
            return auth.resume_online_session(
                read_model_file(state_file, OnlineSessionState)
            ).get_status()

        return run_authenticated(ctx, get_status)

    run_command(ctx, operation)


@app.command("list")
def online_list(
    ctx: typer.Context,
    state_file: Annotated[
        Path, typer.Option("--state-file", exists=True, dir_okay=False)
    ],
    page_size: Annotated[int, typer.Option("--page-size", min=10, max=1000)] = 10,
    continuation_token: Annotated[
        str | None, typer.Option("--continuation-token")
    ] = None,
    failed: Annotated[
        bool, typer.Option("--failed", help="List failed invoices only.")
    ] = False,
) -> None:
    """List invoices submitted in an online session."""

    def operation() -> SessionInvoicesResponse:
        def list_session_invoices(auth: AuthenticatedClient) -> SessionInvoicesResponse:
            session = auth.resume_online_session(
                read_model_file(state_file, OnlineSessionState)
            )
            if failed:
                return session.list_failed_invoices(
                    page_size=page_size, continuation_token=continuation_token
                )
            return session.list_invoices(
                page_size=page_size, continuation_token=continuation_token
            )

        return run_authenticated(ctx, list_session_invoices)

    run_command(ctx, operation)


@app.command("invoice-status")
def online_invoice_status(
    ctx: typer.Context,
    state_file: Annotated[
        Path, typer.Option("--state-file", exists=True, dir_okay=False)
    ],
    invoice_reference: Annotated[str, typer.Option("--invoice-reference")],
    wait: Annotated[bool, typer.Option("--wait", help="Poll until ready.")] = False,
    timeout: Annotated[float, typer.Option("--timeout", min=1.0)] = 60.0,
    poll_interval: Annotated[float, typer.Option("--poll-interval", min=0.1)] = 2.0,
) -> None:
    """Fetch or wait for one invoice status within an online session."""

    def operation() -> SessionInvoiceStatusResponse:
        def get_session_invoice_status(
            auth: AuthenticatedClient,
        ) -> SessionInvoiceStatusResponse:
            session = auth.resume_online_session(
                read_model_file(state_file, OnlineSessionState)
            )
            if wait:
                return session.wait_for_invoice_ready(
                    invoice_reference_number=invoice_reference,
                    timeout=timeout,
                    poll_interval=poll_interval,
                )
            return session.get_invoice_status(
                invoice_reference_number=invoice_reference
            )

        return run_authenticated(ctx, get_session_invoice_status)

    run_command(ctx, operation)


@app.command("upo")
def online_upo(
    ctx: typer.Context,
    state_file: Annotated[
        Path, typer.Option("--state-file", exists=True, dir_okay=False)
    ],
    output_file: Annotated[Path, typer.Option("--out", "-o", dir_okay=False)],
    invoice_reference: Annotated[
        str | None, typer.Option("--invoice-reference")
    ] = None,
    ksef_number: Annotated[str | None, typer.Option("--ksef-number")] = None,
) -> None:
    """Download invoice UPO by invoice reference or KSeF number."""

    def validate() -> None:
        if bool(invoice_reference) == bool(ksef_number):
            raise ValueError(
                "Provide exactly one of --invoice-reference or --ksef-number."
            )

    def get_upo(auth: AuthenticatedClient) -> SavedFile:
        session = auth.resume_online_session(
            read_model_file(state_file, OnlineSessionState)
        )
        if invoice_reference:
            content = session.get_invoice_upo_by_reference(
                invoice_reference_number=invoice_reference
            )
        else:
            assert ksef_number is not None
            content = session.get_invoice_upo_by_ksef_number(ksef_number=ksef_number)
        return SavedFile(path=write_bytes_file(output_file, content), size=len(content))

    run_authenticated_command(ctx, get_upo, validate=validate)


@app.command("close")
def online_close(
    ctx: typer.Context,
    state_file: Annotated[
        Path, typer.Option("--state-file", exists=True, dir_okay=False)
    ],
) -> None:
    """Close a resumed online session."""

    def operation() -> SessionClosed:
        state = read_model_file(state_file, OnlineSessionState)
        run_authenticated(ctx, lambda auth: auth.resume_online_session(state).close())
        return SessionClosed(reference_number=state.reference_number)

    run_command(ctx, operation)
