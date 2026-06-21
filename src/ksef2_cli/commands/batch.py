"""Batch session command group."""

from pathlib import Path
from typing import Annotated, Self

import typer
from pydantic import BaseModel, model_validator

from ksef2.clients.authenticated import AuthenticatedClient
from ksef2.domain.models.batch import BatchSessionState
from ksef2.domain.models.session import SessionInvoicesResponse, SessionStatusResponse

from ksef2_cli.config import FORM_SCHEMA_NAMES, FormSchemaChoice
from ksef2_cli.context import run_authenticated, run_authenticated_command, run_command
from ksef2_cli.io import (
    SECRET_MODEL_FILE_MODE,
    read_model_file,
    write_bytes_file,
    write_model_file,
)
from ksef2_cli.results import BatchSubmitted, SavedFile

app = typer.Typer(help="Submit and inspect batch invoice sessions.")


@app.command("submit")
def batch_submit(
    ctx: typer.Context,
    invoice_paths: Annotated[list[Path], typer.Argument(exists=True, dir_okay=False)],
    state_file: Annotated[
        Path | None, typer.Option("--state-file", dir_okay=False)
    ] = None,
    form: Annotated[
        FormSchemaChoice,
        typer.Option("--form", help=f"Form schema: {FORM_SCHEMA_NAMES}."),
    ] = FormSchemaChoice.FA3,
    offline_mode: Annotated[
        bool, typer.Option("--offline", help="Declare offline invoicing mode.")
    ] = False,
    max_part_size: Annotated[int | None, typer.Option("--max-part-size", min=1)] = None,
    wait: Annotated[
        bool, typer.Option("--wait", help="Wait for batch processing completion.")
    ] = False,
    timeout: Annotated[float, typer.Option("--timeout", min=1.0)] = 120.0,
    poll_interval: Annotated[float, typer.Option("--poll-interval", min=0.1)] = 2.0,
) -> None:
    """Prepare, upload, close, and optionally wait for a batch session."""

    def operation() -> BatchSubmitted:
        def submit_batch(
            auth: AuthenticatedClient,
        ) -> tuple[BatchSessionState, SessionStatusResponse | None]:
            if max_part_size is None:
                prepared = auth.batch.prepare_batch_from_paths(
                    invoice_paths=invoice_paths,
                    form_code=form.form_schema,
                    offline_mode=offline_mode,
                )
            else:
                prepared = auth.batch.prepare_batch_from_paths(
                    invoice_paths=invoice_paths,
                    form_code=form.form_schema,
                    offline_mode=offline_mode,
                    max_part_size=max_part_size,
                )
            state = auth.batch.submit_prepared_batch(prepared_batch=prepared)
            status = (
                auth.batch.wait_for_completion(
                    session=state,
                    timeout=timeout,
                    poll_interval=poll_interval,
                )
                if wait
                else None
            )
            return state, status

        state, status = run_authenticated(ctx, submit_batch)
        if state_file:
            write_model_file(state_file, state, file_mode=SECRET_MODEL_FILE_MODE)
        return BatchSubmitted(state_file=state_file, state=state, status=status)

    run_command(ctx, operation)


class BatchSendInput(BaseModel):
    reference: str | None
    state_file: Path | None

    @model_validator(mode="after")
    def validate_options(self) -> Self:
        if self.reference and self.state_file:
            raise ValueError("Use either --reference or --state-file, not both.")

        if not self.reference and not self.state_file:
            raise ValueError("Provide --reference or --state-file.")

        return self

    @property
    def session_reference(self) -> str | BatchSessionState:
        if self.reference:
            return self.reference

        if self.state_file:
            return read_model_file(self.state_file, BatchSessionState)

        raise ValueError("Either reference or statefile has to be passed.")


@app.command("status")
def batch_status(
    ctx: typer.Context,
    reference: Annotated[str | None, typer.Option("--reference")] = None,
    state_file: Annotated[
        Path | None, typer.Option("--state-file", exists=True, dir_okay=False)
    ] = None,
    wait: Annotated[bool, typer.Option("--wait", help="Wait for completion.")] = False,
    timeout: Annotated[float, typer.Option("--timeout", min=1.0)] = 120.0,
    poll_interval: Annotated[float, typer.Option("--poll-interval", min=0.1)] = 2.0,
) -> None:
    """Fetch or wait for batch session status."""

    inputs = BatchSendInput(reference=reference, state_file=state_file)

    def operation() -> SessionStatusResponse:
        def get_batch_status(auth: AuthenticatedClient) -> SessionStatusResponse:
            if wait:
                return auth.batch.wait_for_completion(
                    session=inputs.session_reference,
                    timeout=timeout,
                    poll_interval=poll_interval,
                )
            return auth.batch.get_status(session=inputs.session_reference)

        return run_authenticated(ctx, get_batch_status)

    run_command(ctx, operation)


@app.command("list")
def batch_list(
    ctx: typer.Context,
    reference: Annotated[str | None, typer.Option("--reference")] = None,
    state_file: Annotated[
        Path | None, typer.Option("--state-file", exists=True, dir_okay=False)
    ] = None,
    page_size: Annotated[int, typer.Option("--page-size", min=10, max=1000)] = 10,
    continuation_token: Annotated[
        str | None, typer.Option("--continuation-token")
    ] = None,
    failed: Annotated[
        bool, typer.Option("--failed", help="List failed invoices only.")
    ] = False,
) -> None:
    """List invoices submitted in a batch session."""

    inputs = BatchSendInput(reference=reference, state_file=state_file)

    def operation() -> SessionInvoicesResponse:
        def list_batch_invoices(auth: AuthenticatedClient) -> SessionInvoicesResponse:
            if failed:
                return auth.batch.list_failed_invoices(
                    session=inputs.session_reference,
                    page_size=page_size,
                    continuation_token=continuation_token,
                )
            return auth.batch.list_invoices(
                session=inputs.session_reference,
                page_size=page_size,
                continuation_token=continuation_token,
            )

        return run_authenticated(ctx, list_batch_invoices)

    run_command(ctx, operation)


@app.command("upo")
def batch_upo(
    ctx: typer.Context,
    upo_reference: Annotated[str, typer.Option("--upo-reference")],
    output_file: Annotated[Path, typer.Option("--out", "-o", dir_okay=False)],
    reference: Annotated[str | None, typer.Option("--reference")] = None,
    state_file: Annotated[
        Path | None, typer.Option("--state-file", exists=True, dir_okay=False)
    ] = None,
) -> None:
    """Download a collective UPO page for a batch session."""

    inputs = BatchSendInput(reference=reference, state_file=state_file)

    def get_upo(auth: AuthenticatedClient) -> SavedFile:
        content = auth.batch.get_upo(
            session=inputs.session_reference,
            upo_reference_number=upo_reference,
        )
        return SavedFile(path=write_bytes_file(output_file, content), size=len(content))

    run_authenticated_command(ctx, get_upo)
