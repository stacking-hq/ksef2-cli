"""High-level invoice receipt continuation commands."""

from pathlib import Path
from typing import Annotated

import typer
from ksef2.clients.authenticated import AuthenticatedClient

from ksef2_cli.context import read_model, run_authenticated, run_command
from ksef2_cli.io import SECRET_MODEL_FILE_MODE, write_bytes_file, write_model_file
from ksef2_cli.results import SavedFile

from ksef2_cli.commands.invoices.models import (
    InvoiceWorkflowReceipt,
    InvoicesStatusResult,
    InvoicesUpoResult,
)
from ksef2_cli.invoice_workflows import download_batch_upos


def _safe_filename(value: str, suffix: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in value)
    return safe if safe.endswith(suffix) else f"{safe}{suffix}"


def _invoice_upo_path(upo_dir: Path, invoice_path: Path) -> Path:
    return upo_dir / _safe_filename(f"{invoice_path.stem}-upo", ".xml")


def invoices_status(
    ctx: typer.Context,
    receipt_file: Annotated[
        Path,
        typer.Option("--receipt", exists=True, dir_okay=False, help="Receipt file."),
    ],
    wait: Annotated[bool, typer.Option("--wait", help="Wait for completion.")] = False,
    timeout: Annotated[float, typer.Option("--timeout", min=1.0)] = 120.0,
    poll_interval: Annotated[float, typer.Option("--poll-interval", min=0.1)] = 2.0,
) -> None:
    """Check status for a high-level invoice workflow receipt."""

    def operation() -> InvoicesStatusResult:
        receipt = read_model(ctx, receipt_file, InvoiceWorkflowReceipt)

        def check_status(auth: AuthenticatedClient) -> InvoicesStatusResult:
            if receipt.mode == "online":
                online = receipt.online
                if online is None:
                    raise ValueError("Receipt does not contain online invoice data.")
                session = auth.resume_online_session(online.session_state)
                status = (
                    session.wait_for_invoice_ready(
                        invoice_reference_number=online.invoice_reference,
                        timeout=timeout,
                        poll_interval=poll_interval,
                    )
                    if wait
                    else session.get_invoice_status(
                        invoice_reference_number=online.invoice_reference
                    )
                )
                write_model_file(
                    receipt_file,
                    receipt.model_copy(
                        update={"online": online.model_copy(update={"status": status})}
                    ),
                    file_mode=SECRET_MODEL_FILE_MODE,
                )
                status_label = "accepted" if status.ksef_number else "processing"
                if status.status.code >= 400:
                    status_label = "failed"
                return InvoicesStatusResult(
                    mode="online",
                    receipt_file=receipt_file,
                    status=status_label,
                    status_code=status.status.code,
                    status_description=status.status.description,
                    session_reference=online.session_state.reference_number,
                    file=online.file,
                    invoice_reference=online.invoice_reference,
                    ksef_number=status.ksef_number,
                )

            batch = receipt.batch
            if batch is None:
                raise ValueError("Receipt does not contain batch data.")
            status = (
                auth.batch.wait_for_completion(
                    session=batch.session_reference,
                    timeout=timeout,
                    poll_interval=poll_interval,
                )
                if wait
                else auth.batch.get_status(session=batch.session_reference)
            )
            write_model_file(
                receipt_file,
                receipt.model_copy(
                    update={"batch": batch.model_copy(update={"status": status})}
                ),
                file_mode=SECRET_MODEL_FILE_MODE,
            )
            status_label = "completed" if status.status.code >= 200 else "processing"
            if status.status.code >= 400:
                status_label = "failed"
            return InvoicesStatusResult(
                mode="batch",
                receipt_file=receipt_file,
                status=status_label,
                status_code=status.status.code,
                status_description=status.status.description,
                session_reference=batch.session_reference,
                invoice_count=status.invoice_count,
                successful_invoice_count=status.successful_invoice_count,
                failed_invoice_count=status.failed_invoice_count,
            )

        return run_authenticated(ctx, check_status)

    run_command(ctx, operation)


def invoices_upo(
    ctx: typer.Context,
    receipt_file: Annotated[
        Path,
        typer.Option("--receipt", exists=True, dir_okay=False, help="Receipt file."),
    ],
    output_file: Annotated[
        Path | None,
        typer.Option("--out", "-o", dir_okay=False, help="Target UPO XML file."),
    ] = None,
    upo_dir: Annotated[
        Path | None,
        typer.Option("--upo-dir", file_okay=False, help="Directory for UPO XML files."),
    ] = None,
    wait: Annotated[
        bool, typer.Option("--wait", help="Wait for UPO readiness.")
    ] = False,
    timeout: Annotated[float, typer.Option("--timeout", min=1.0)] = 120.0,
    poll_interval: Annotated[float, typer.Option("--poll-interval", min=0.1)] = 2.0,
) -> None:
    """Download UPO XML files for a high-level invoice workflow receipt."""

    def operation() -> InvoicesUpoResult:
        if output_file and upo_dir:
            raise ValueError("Use either --out or --upo-dir, not both.")
        if not output_file and not upo_dir:
            raise ValueError("Provide --out or --upo-dir.")
        receipt = read_model(ctx, receipt_file, InvoiceWorkflowReceipt)
        if receipt.mode == "batch" and output_file:
            raise ValueError("--out can only be used with online invoice receipts.")

        def download_upo(auth: AuthenticatedClient) -> InvoicesUpoResult:
            if receipt.mode == "online":
                online = receipt.online
                if online is None:
                    raise ValueError("Receipt does not contain online invoice data.")
                session = auth.resume_online_session(online.session_state)
                status = online.status
                if wait:
                    status = session.wait_for_invoice_ready(
                        invoice_reference_number=online.invoice_reference,
                        timeout=timeout,
                        poll_interval=poll_interval,
                    )
                elif status is None:
                    status = session.get_invoice_status(
                        invoice_reference_number=online.invoice_reference
                    )

                if status.status.code >= 400:
                    raise ValueError(
                        "Invoice processing failed: "
                        f"{online.invoice_reference} ({status.status.code}: {status.status.description})"
                    )
                if not status.ksef_number:
                    raise ValueError("UPO is not ready. Re-run with --wait.")

                if output_file is not None:
                    target = output_file
                else:
                    assert upo_dir is not None
                    target = _invoice_upo_path(upo_dir, online.file)
                content = session.get_invoice_upo_by_reference(
                    invoice_reference_number=online.invoice_reference
                )
                saved = SavedFile(
                    path=write_bytes_file(target, content), size=len(content)
                )
                write_model_file(
                    receipt_file,
                    receipt.model_copy(
                        update={
                            "online": online.model_copy(
                                update={"status": status, "upo_file": saved.path}
                            )
                        }
                    ),
                    file_mode=SECRET_MODEL_FILE_MODE,
                )
                return InvoicesUpoResult(
                    mode="online",
                    receipt_file=receipt_file,
                    session_reference=online.session_state.reference_number,
                    file=online.file,
                    invoice_reference=online.invoice_reference,
                    ksef_number=status.ksef_number,
                    upo_files=[saved],
                )

            batch = receipt.batch
            if batch is None:
                raise ValueError("Receipt does not contain batch data.")
            target_dir = upo_dir
            if target_dir is None:
                raise ValueError("Provide --upo-dir.")
            status = (
                auth.batch.wait_for_completion(
                    session=batch.session_reference,
                    timeout=timeout,
                    poll_interval=poll_interval,
                )
                if wait
                else (
                    auth.batch.get_status(session=batch.session_reference)
                    if batch.status is None or batch.status.upo is None
                    else batch.status
                )
            )
            saved_upos = download_batch_upos(
                auth=auth,
                session_reference=batch.session_reference,
                status=status,
                upo_dir=target_dir,
            )
            write_model_file(
                receipt_file,
                receipt.model_copy(
                    update={
                        "batch": batch.model_copy(
                            update={
                                "status": status,
                                "upo_files": [saved.path for saved in saved_upos],
                            }
                        )
                    }
                ),
                file_mode=SECRET_MODEL_FILE_MODE,
            )
            return InvoicesUpoResult(
                mode="batch",
                receipt_file=receipt_file,
                session_reference=batch.session_reference,
                upo_files=saved_upos,
            )

        return run_authenticated(ctx, download_upo)

    run_command(ctx, operation)
