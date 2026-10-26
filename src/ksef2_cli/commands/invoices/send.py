"""High-level invoice send workflow command."""

from pathlib import Path
from typing import Annotated

import typer

from ksef2_cli.commands.invoices.models import InvoiceSendModeChoice, InvoicesSendResult
from ksef2_cli.config import FORM_SCHEMA_NAMES, FormSchemaChoice
from ksef2_cli.context import run_authenticated, run_command
from ksef2_cli.io import read_invoice_xml, read_stdin_invoice_xml
from ksef2_cli.invoice_workflows import InvoiceSendInput, send_invoices


def invoices_send(
    ctx: typer.Context,
    invoice_paths: Annotated[
        list[Path],
        typer.Argument(
            help="Invoice XML files, directories, or - for one invoice from stdin.",
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
    max_part_size: Annotated[
        int | None,
        typer.Option(
            "--max-part-size",
            min=1,
            help="Maximum encrypted batch part size in bytes. Batch mode only.",
        ),
    ] = None,
    timeout: Annotated[
        float,
        typer.Option("--timeout", min=1.0, help="Maximum processing wait in seconds."),
    ] = 120.0,
    poll_interval: Annotated[
        float,
        typer.Option(
            "--poll-interval", min=0.1, help="Seconds between processing status checks."
        ),
    ] = 2.0,
) -> None:
    """Send one or more invoice XML files through an online or batch workflow."""

    for path in invoice_paths:
        if path != Path("-") and not path.exists():
            raise typer.BadParameter(
                f"Path '{path}' does not exist.", param_hint="invoice_paths"
            )

    def operation() -> InvoicesSendResult:
        if invoice_paths.count(Path("-")) > 1:
            raise ValueError("Provide - only once for stdin.")
        contents: dict[Path, bytes] = {}
        if Path("-") in invoice_paths:
            names = {path.name for path in invoice_paths}
            for path in invoice_paths:
                if path.is_dir():
                    matches = path.rglob("*.xml") if recursive else path.glob("*.xml")
                    names.update(item.name for item in matches)
            source = Path("stdin.xml")
            index = 2
            while source.name in names:
                source = Path(f"stdin-{index}.xml")
                index += 1
            contents[source] = read_stdin_invoice_xml()
        inputs = InvoiceSendInput(
            invoice_paths=[path for path in invoice_paths if path != Path("-")],
            invoice_contents=contents,
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
        for path in inputs.invoice_files:
            if path not in inputs.invoice_contents:
                read_invoice_xml(path)
        return run_authenticated(ctx, lambda auth: send_invoices(auth, inputs))

    run_command(
        ctx,
        operation,
        exit_code_from_result=lambda result: (
            1 if isinstance(result, InvoicesSendResult) and result.failed > 0 else 0
        ),
    )
