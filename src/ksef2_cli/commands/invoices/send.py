"""High-level invoice send workflow command."""

from pathlib import Path
from typing import Annotated

import typer

from ksef2_cli.commands.invoices.models import InvoiceSendModeChoice, InvoicesSendResult
from ksef2_cli.config import FORM_SCHEMA_NAMES, FormSchemaChoice
from ksef2_cli.context import run_authenticated, run_command
from ksef2_cli.invoice_workflows import InvoiceSendInput, send_invoices


def invoices_send(
    ctx: typer.Context,
    invoice_paths: Annotated[
        list[Path],
        typer.Argument(
            exists=True,
            help="Invoice XML files or directories containing invoice XML files.",
        ),
    ],
    mode: Annotated[
        InvoiceSendModeChoice,
        typer.Option("--mode", help="online or batch."),
    ] = InvoiceSendModeChoice.ONLINE,
    recursive: Annotated[
        bool,
        typer.Option("--recursive", help="Include XML files in nested directories."),
    ] = False,
    wait: Annotated[
        bool, typer.Option("--wait", help="Wait for final processing status.")
    ] = False,
    upo_dir: Annotated[
        Path | None,
        typer.Option("--upo-dir", file_okay=False, help="Directory for UPO XML files."),
    ] = None,
    receipt_file: Annotated[
        Path | None,
        typer.Option("--receipt", dir_okay=False, help="Write one receipt file."),
    ] = None,
    receipt_dir: Annotated[
        Path | None,
        typer.Option(
            "--receipt-dir", file_okay=False, help="Directory for receipt files."
        ),
    ] = None,
    form: Annotated[
        FormSchemaChoice,
        typer.Option("--form", help=f"Form schema: {FORM_SCHEMA_NAMES}."),
    ] = FormSchemaChoice.FA3,
    offline_mode: Annotated[
        bool,
        typer.Option("--offline", help="Declare batch offline invoicing mode."),
    ] = False,
    max_part_size: Annotated[int | None, typer.Option("--max-part-size", min=1)] = None,
    timeout: Annotated[float, typer.Option("--timeout", min=1.0)] = 120.0,
    poll_interval: Annotated[float, typer.Option("--poll-interval", min=0.1)] = 2.0,
) -> None:
    """Send one or more invoice XML files through an online or batch workflow."""

    def operation() -> InvoicesSendResult:
        inputs = InvoiceSendInput(
            invoice_paths=invoice_paths,
            mode=mode,
            recursive=recursive,
            wait=wait,
            upo_dir=upo_dir,
            receipt_file=receipt_file,
            receipt_dir=receipt_dir,
            form=form,
            offline_mode=offline_mode,
            max_part_size=max_part_size,
            timeout=timeout,
            poll_interval=poll_interval,
        )
        return run_authenticated(ctx, lambda auth: send_invoices(auth, inputs))

    run_command(
        ctx,
        operation,
        exit_code_from_result=lambda result: (
            1 if isinstance(result, InvoicesSendResult) and result.failed > 0 else 0
        ),
    )
