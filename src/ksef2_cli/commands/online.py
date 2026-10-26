"""Online invoice session command group."""

from pathlib import Path
from typing import Annotated

import typer
from ksef2.clients import AuthenticatedClient
from ksef2.models import (
    OnlineSessionResumeState,
    SendInvoiceResponse,
    SessionInvoicesResponse,
    SessionInvoiceStatusResponse,
    SessionStatusResponse,
)

from ksef2_cli.config import FORM_SCHEMA_NAMES, FormSchemaChoice
from ksef2_cli.context import run_authenticated, run_authenticated_command, run_command
from ksef2_cli.io import (
    SECRET_MODEL_FILE_MODE,
    read_model_file,
    read_invoice_xml,
    write_bytes_file,
    write_text_file,
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
        def open_session(auth: AuthenticatedClient) -> OnlineSessionResumeState:
            session = auth.online_session(form_code=form.form_schema)
            return session.resume_state()

        state = run_authenticated(ctx, open_session)
        if state_file:
            _ = write_text_file(
                state_file, state.to_json(indent=2), file_mode=SECRET_MODEL_FILE_MODE
            )
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
    close: Annotated[
        bool,
        typer.Option(
            "--close",
            help="Close the session after sending, including a resumed session.",
        ),
    ] = False,
    timeout: Annotated[
        float, typer.Option("--timeout", min=1.0, help="Maximum wait in seconds.")
    ] = 60.0,
    poll_interval: Annotated[
        float,
        typer.Option("--poll-interval", min=0.1, help="Seconds between status checks."),
    ] = 2.0,
) -> None:
    """Send invoice XML files. New sessions close; resumed sessions stay open by default."""

    def operation() -> FocusedResult[OnlineSendResult, OnlineSendItem]:
        if close and keep_open:
            raise ValueError("Use either --close or --keep-open, not both.")
        should_close = close or (state_file is None and not keep_open)
        invoices = [(path, read_invoice_xml(path)) for path in invoice_paths]

        def send_invoices(
            auth: AuthenticatedClient,
        ) -> tuple[list[OnlineSendItem], OnlineSessionResumeState]:
            if state_file:
                session = auth.online_session(
                    state=read_model_file(state_file, OnlineSessionResumeState)
                )
            else:
                session = auth.online_session(form_code=form.form_schema)
            try:
                results: list[OnlineSendItem] = []
                for invoice_path, xml in invoices:
                    submission = session.send_invoice(invoice_xml=xml)
                    result: OnlineSendResponse
                    if wait:
                        result = submission.wait(
                            timeout=timeout,
                            poll_interval=poll_interval,
                        )
                    else:
                        result = submission.response
                    results.append(OnlineSendItem(file=invoice_path, result=result))
                state = session.resume_state()
                return results, state
            finally:
                if should_close:
                    session.close()

        results, state = run_authenticated(ctx, send_invoices)
        if save_state:
            _ = write_text_file(
                save_state, state.to_json(indent=2), file_mode=SECRET_MODEL_FILE_MODE
            )
        payload = OnlineSendResult(
            state_file=save_state, closed=should_close, results=results
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
            return auth.online_session(
                state=read_model_file(state_file, OnlineSessionResumeState)
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
            session = auth.online_session(
                state=read_model_file(state_file, OnlineSessionResumeState)
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
    timeout: Annotated[
        float, typer.Option("--timeout", min=1.0, help="Maximum wait in seconds.")
    ] = 60.0,
    poll_interval: Annotated[
        float,
        typer.Option("--poll-interval", min=0.1, help="Seconds between status checks."),
    ] = 2.0,
) -> None:
    """Fetch or wait for one invoice status within an online session."""

    def operation() -> SessionInvoiceStatusResponse:
        def get_session_invoice_status(
            auth: AuthenticatedClient,
        ) -> SessionInvoiceStatusResponse:
            session = auth.online_session(
                state=read_model_file(state_file, OnlineSessionResumeState)
            )
            if wait:
                return session.submission(reference_number=invoice_reference).wait(
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
        session = auth.online_session(
            state=read_model_file(state_file, OnlineSessionResumeState)
        )
        if invoice_reference:
            content = session.download_invoice_upo(reference_number=invoice_reference)
        else:
            assert ksef_number is not None
            content = session.download_invoice_upo(ksef_number=ksef_number)
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
        state = read_model_file(state_file, OnlineSessionResumeState)
        run_authenticated(ctx, lambda auth: auth.online_session(state=state).close())
        return SessionClosed(reference_number=state.reference_number)

    run_command(ctx, operation)
