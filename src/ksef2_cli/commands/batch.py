"""Batch session command group."""

from pathlib import Path
from typing import Annotated, Self

import typer
from ksef2 import KSeFBatchUploadError, KSeFValidationError
from ksef2.clients import AuthenticatedClient, BatchSessionClient
from ksef2.models import (
    BatchSessionResumeState,
    PreparedBatch,
    SessionInvoicesResponse,
    SessionStatusResponse,
)
from pydantic import BaseModel, ValidationError, model_validator

from ksef2_cli.batch_artifact import read_prepared_batch, write_prepared_batch
from ksef2_cli.config import FORM_SCHEMA_NAMES, FormSchemaChoice
from ksef2_cli.context import run_authenticated, run_command
from ksef2_cli.exceptions import RemoteServiceError, UsageError
from ksef2_cli.io import (
    SECRET_MODEL_FILE_MODE,
    read_model_file,
    write_bytes_file,
    write_text_file,
)
from ksef2_cli.results import BatchPrepared, BatchSubmitted, SavedFile

app = typer.Typer(help="Submit and inspect batch invoice sessions.")


def _status_or_wait(
    session: BatchSessionClient, *, wait: bool, timeout: float, poll_interval: float
) -> SessionStatusResponse | None:
    """Wait when the command asked for it, otherwise report no status yet."""

    return (
        session.wait(timeout=timeout, poll_interval=poll_interval) if wait else None
    )


def _submit_inputs(
    invoice_paths: list[Path] | None, prepared: Path | None
) -> list[Path] | PreparedBatch:
    """Pick what ``submit`` sends: the invoices to prepare, or the stored package."""

    if prepared is not None and invoice_paths:
        raise UsageError(
            "Pass invoice files or --prepared, not both: a prepared package is "
            "uploaded as it was built.",
            title="Conflicting batch input",
        )
    if prepared is not None:
        return read_prepared_batch(prepared)
    if not invoice_paths:
        raise UsageError(
            "Pass the invoice files to submit, or --prepared with a directory "
            "written by batch prepare.",
            title="Nothing to submit",
        )
    return invoice_paths


def _read_session_state(path: Path, *, prepared: Path) -> BatchSessionResumeState:
    """Load a batch session state file, rejecting one that cannot resume anything.

    ``BatchSessionResumeState`` masks its key material in ordinary Pydantic dumps, so a
    hand-edited or redacted file reads as a wall of validation errors instead.
    """

    try:
        return read_model_file(path, BatchSessionResumeState)
    except (ValidationError, KSeFValidationError) as error:
        raise UsageError(
            f"{path} does not hold resumable batch session state.",
            title="Batch session state cannot be resumed",
            details=(str(error),),
            hints=(
                f"Re-create it with: ksef2 batch submit --prepared {prepared} "
                f"--state-file {path}",
            ),
        ) from error


def _upload_failure(
    error: KSeFBatchUploadError,
    *,
    state_file: Path | None,
    prepared: Path | None,
) -> RemoteServiceError:
    """Turn a rejected upload into an error that names the retry, saving what it left.

    The SDK keeps the state of the interrupted session on the error and it is the only
    way back to those presigned upload URLs, so a requested ``--state-file`` captures it
    before the CLI reports the failure.
    """

    hints: list[str] = []
    if state_file is not None:
        _ = write_text_file(
            state_file,
            error.recovery_state().to_json(indent=2),
            file_mode=SECRET_MODEL_FILE_MODE,
        )
        hints.append(
            f"Saved the state of session {error.reference_number} to {state_file}."
        )
    if prepared is not None:
        retry = (
            f"ksef2 batch upload --prepared {prepared} --state-file {state_file}"
            if state_file is not None
            else f"ksef2 batch submit --prepared {prepared}"
        )
        hints.append(f"Retry the same parts without rebuilding them: {retry}")
    else:
        hints.append(
            "Prepare the invoices once with ksef2 batch prepare --out DIR, then retry "
            "with ksef2 batch submit --prepared DIR to skip rebuilding the parts."
        )
    return RemoteServiceError(
        str(error.args[0]) if error.args else str(error),
        title="Batch upload failed",
        hints=tuple(hints),
    )


@app.command("prepare")
def batch_prepare(
    ctx: typer.Context,
    invoice_paths: Annotated[list[Path], typer.Argument(exists=True, dir_okay=False)],
    output_dir: Annotated[
        Path,
        typer.Option("--out", "-o", file_okay=False, help="Artifact directory."),
    ],
    form: Annotated[
        FormSchemaChoice,
        typer.Option("--form", help=f"Form schema: {FORM_SCHEMA_NAMES}."),
    ] = FormSchemaChoice.FA3,
    offline_mode: Annotated[
        bool, typer.Option("--offline", help="Declare offline invoicing mode.")
    ] = False,
    max_part_size: Annotated[int | None, typer.Option("--max-part-size", min=1)] = None,
) -> None:
    """Build and encrypt batch parts, then store them for a later submit.

    The parts depend on the KSeF encryption key rather than on a session, so preparing
    ahead of submitting lets a rejected upload retry without packing and encrypting the
    invoices again. The artifact holds a session key and invoice payloads, so keep it
    as protected as a credential file.
    """

    def operation() -> BatchPrepared:
        def prepare_package(auth: AuthenticatedClient) -> PreparedBatch:
            if max_part_size is None:
                return auth.batch.prepare(
                    invoice_paths,
                    form_code=form.form_schema,
                    offline_mode=offline_mode,
                )
            return auth.batch.prepare(
                invoice_paths,
                form_code=form.form_schema,
                offline_mode=offline_mode,
                max_part_size=max_part_size,
            )

        batch = run_authenticated(ctx, prepare_package)
        path = write_prepared_batch(output_dir, batch)
        return BatchPrepared(
            path=path,
            digest=batch.recovery_digest(),
            parts=len(batch.parts),
            invoices=len(batch.invoices),
        )

    run_command(ctx, operation)


@app.command("submit")
def batch_submit(
    ctx: typer.Context,
    invoice_paths: Annotated[
        list[Path] | None,
        typer.Argument(
            exists=True,
            dir_okay=False,
            help=(
                "Invoice XML files to prepare and submit. Leave them out with "
                "--prepared."
            ),
        ),
    ] = None,
    prepared: Annotated[
        Path | None,
        typer.Option(
            "--prepared",
            file_okay=False,
            help="Artifact directory written by batch prepare. Its parts are uploaded "
            "as they are, and --form, --offline, and --max-part-size do not apply.",
        ),
    ] = None,
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
    """Prepare, upload, close, and optionally wait for a batch session.

    Pass invoice files to prepare them in one go, or --prepared to upload a package that
    batch prepare stored, which is the retry path after a failed upload.
    """

    def operation() -> BatchSubmitted:
        batch = _submit_inputs(invoice_paths, prepared)

        def submit_batch(
            auth: AuthenticatedClient,
        ) -> tuple[BatchSessionResumeState, SessionStatusResponse | None]:
            if isinstance(batch, PreparedBatch):
                session = auth.batch.submit(batch)
            elif max_part_size is None:
                session = auth.batch.submit(
                    batch,
                    form_code=form.form_schema,
                    offline_mode=offline_mode,
                )
            else:
                session = auth.batch.submit(
                    batch,
                    form_code=form.form_schema,
                    offline_mode=offline_mode,
                    max_part_size=max_part_size,
                )
            state = session.resume_state()
            status = _status_or_wait(
                session, wait=wait, timeout=timeout, poll_interval=poll_interval
            )
            return state, status

        try:
            state, status = run_authenticated(ctx, submit_batch)
        except KSeFBatchUploadError as error:
            raise _upload_failure(
                error, state_file=state_file, prepared=prepared
            ) from error
        if state_file:
            _ = write_text_file(
                state_file, state.to_json(indent=2), file_mode=SECRET_MODEL_FILE_MODE
            )
        return BatchSubmitted(state_file=state_file, state=state, status=status)

    run_command(ctx, operation)


@app.command("upload")
def batch_upload(
    ctx: typer.Context,
    prepared: Annotated[
        Path,
        typer.Option(
            "--prepared",
            exists=True,
            file_okay=False,
            help="Artifact directory written by batch prepare.",
        ),
    ],
    state_file: Annotated[
        Path,
        typer.Option(
            "--state-file",
            exists=True,
            dir_okay=False,
            help="Batch session state left behind by a failed submit or written by "
            "any command that reports session state.",
        ),
    ],
    wait: Annotated[
        bool, typer.Option("--wait", help="Wait for batch processing completion.")
    ] = False,
    timeout: Annotated[float, typer.Option("--timeout", min=1.0)] = 120.0,
    poll_interval: Annotated[float, typer.Option("--poll-interval", min=0.1)] = 2.0,
) -> None:
    """Send the stored parts again to a batch session whose upload failed.

    The state file carries the session reference, keys, and upload instructions, while
    the artifact carries the exact parts KSeF expects, so recovering needs neither new
    invoices nor a new package.
    """

    def operation() -> BatchSubmitted:
        batch = read_prepared_batch(prepared)
        state = _read_session_state(state_file, prepared=prepared)

        def upload(
            auth: AuthenticatedClient,
        ) -> tuple[BatchSessionResumeState, SessionStatusResponse | None]:
            with auth.batch_session(state=state, prepared_batch=batch) as session:
                session.upload_parts()
                resumed = session.resume_state()
            # Leaving the with block closed the session, which is what lets KSeF start
            # processing and lets wait() run at all.
            status = _status_or_wait(
                session, wait=wait, timeout=timeout, poll_interval=poll_interval
            )
            return resumed, status

        try:
            resumed, status = run_authenticated(ctx, upload)
        except KSeFBatchUploadError as error:
            raise _upload_failure(
                error, state_file=state_file, prepared=prepared
            ) from error
        return BatchSubmitted(state_file=state_file, state=resumed, status=status)

    run_command(ctx, operation)


class BatchSendInput(BaseModel):
    reference: str | None
    state_file: Path | None

    @model_validator(mode="after")
    def validate_options(self) -> Self:
        if self.reference and self.state_file:
            raise UsageError("Use either --reference or --state-file, not both.")

        if not self.reference and not self.state_file:
            raise UsageError("Provide --reference or --state-file.")

        return self

    @property
    def session_reference(self) -> str | BatchSessionResumeState:
        if self.reference:
            return self.reference

        if self.state_file:
            return read_model_file(self.state_file, BatchSessionResumeState)

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

    def operation() -> SessionStatusResponse:
        inputs = BatchSendInput(reference=reference, state_file=state_file)

        def get_batch_status(auth: AuthenticatedClient) -> SessionStatusResponse:
            with auth.batch_session(state=inputs.session_reference) as session:
                if wait:
                    return session.wait(
                        timeout=timeout,
                        poll_interval=poll_interval,
                    )
                return session.get_status()

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

    def operation() -> SessionInvoicesResponse:
        inputs = BatchSendInput(reference=reference, state_file=state_file)

        def list_batch_invoices(auth: AuthenticatedClient) -> SessionInvoicesResponse:
            with auth.batch_session(state=inputs.session_reference) as session:
                if failed:
                    return session.list_failed_invoices(
                        page_size=page_size,
                        continuation_token=continuation_token,
                    )
                return session.list_invoices(
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

    def operation() -> SavedFile:
        inputs = BatchSendInput(reference=reference, state_file=state_file)
        state = inputs.session_reference
        session_reference = (
            state.reference_number if isinstance(state, BatchSessionResumeState) else state
        )

        def get_upo(auth: AuthenticatedClient) -> bytes:
            return auth.invoice_sessions.download_upo(
                session_reference, upo_reference_number=upo_reference
            )

        content = run_authenticated(ctx, get_upo)
        return SavedFile(path=write_bytes_file(output_file, content), size=len(content))

    run_command(ctx, operation)
