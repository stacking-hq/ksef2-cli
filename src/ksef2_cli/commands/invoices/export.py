"""Invoice export commands."""

from pathlib import Path
from typing import Annotated

import typer
from ksef2.clients.authenticated import AuthenticatedClient
from ksef2.domain.models.invoices import InvoiceExportStatusResponse

from ksef2_cli.commands.invoices.models import (
    CompressionTypeChoice,
    ExportHandleSaved,
    ExportPaths,
    InvoiceAmountTypeChoice,
    InvoiceDateTypeChoice,
    InvoiceRoleChoice,
)
from ksef2_cli.context import read_model, run_authenticated_command
from ksef2_cli.invoice_workflows import (
    InvoiceExportDownloadInput,
    InvoiceExportFetchInput,
    InvoiceExportInput,
    download_invoice_export,
    fetch_invoice_export,
    get_invoice_export_status,
    schedule_invoice_export,
)
from ksef2_cli.results import FocusedResult


def invoices_export(
    ctx: typer.Context,
    date_from: Annotated[
        str, typer.Option("--date-from", help="Start datetime/date, ISO format.")
    ],
    date_to: Annotated[
        str | None, typer.Option("--date-to", help="End datetime/date, ISO format.")
    ] = None,
    role: Annotated[
        InvoiceRoleChoice, typer.Option("--role")
    ] = InvoiceRoleChoice.SELLER,
    date_type: Annotated[
        InvoiceDateTypeChoice, typer.Option("--date-type")
    ] = InvoiceDateTypeChoice.ISSUE_DATE,
    amount_type: Annotated[
        InvoiceAmountTypeChoice, typer.Option("--amount-type")
    ] = InvoiceAmountTypeChoice.BRUTTO,
    only_metadata: Annotated[
        bool, typer.Option("--only-metadata", help="Export only metadata.")
    ] = False,
    compression_type: Annotated[
        CompressionTypeChoice | None, typer.Option("--compression-type")
    ] = None,
    handle_file: Annotated[
        Path | None,
        typer.Option(
            "--handle-file",
            dir_okay=False,
            help="Save export handle needed for later fetch.",
        ),
    ] = None,
) -> None:
    """Schedule an invoice export and print/save the decryption handle."""

    inputs = InvoiceExportInput(
        date_from=date_from,
        date_to=date_to,
        role=role,
        date_type=date_type,
        amount_type=amount_type,
        only_metadata=only_metadata,
        compression_type=compression_type,
        handle_file=handle_file,
    )
    run_authenticated_command(ctx, lambda auth: schedule_invoice_export(auth, inputs))


def invoices_export_status(
    ctx: typer.Context,
    reference_number: Annotated[
        str, typer.Option("--reference", help="Export reference number.")
    ],
) -> None:
    """Fetch invoice export status."""

    def work(auth: AuthenticatedClient) -> InvoiceExportStatusResponse:
        return get_invoice_export_status(auth, reference_number)

    run_authenticated_command(ctx, work)


def invoices_export_fetch(
    ctx: typer.Context,
    handle_file: Annotated[
        Path, typer.Option("--handle-file", exists=True, dir_okay=False)
    ],
    output_dir: Annotated[Path, typer.Option("--out-dir", file_okay=False)] = Path(
        "downloads"
    ),
    wait: Annotated[
        bool, typer.Option("--wait", help="Wait for the export package.")
    ] = False,
    timeout: Annotated[float, typer.Option("--timeout", min=1.0)] = 120.0,
    poll_interval: Annotated[float, typer.Option("--poll-interval", min=0.1)] = 2.0,
) -> None:
    """Fetch and decrypt an export package using a saved export handle."""

    def load_input() -> InvoiceExportFetchInput:
        return InvoiceExportFetchInput(
            handle=read_model(ctx, handle_file, ExportHandleSaved),
            output_dir=output_dir,
            wait=wait,
            timeout=timeout,
            poll_interval=poll_interval,
        )

    def work(auth: AuthenticatedClient) -> FocusedResult[ExportPaths, str]:
        return fetch_invoice_export(auth, load_input())

    run_authenticated_command(ctx, work, validate=load_input)


def invoices_export_download(
    ctx: typer.Context,
    date_from: Annotated[
        str, typer.Option("--date-from", help="Start datetime/date, ISO format.")
    ],
    date_to: Annotated[
        str | None, typer.Option("--date-to", help="End datetime/date, ISO format.")
    ] = None,
    role: Annotated[
        InvoiceRoleChoice, typer.Option("--role")
    ] = InvoiceRoleChoice.SELLER,
    date_type: Annotated[
        InvoiceDateTypeChoice, typer.Option("--date-type")
    ] = InvoiceDateTypeChoice.ISSUE_DATE,
    amount_type: Annotated[
        InvoiceAmountTypeChoice, typer.Option("--amount-type")
    ] = InvoiceAmountTypeChoice.BRUTTO,
    output_dir: Annotated[Path, typer.Option("--out-dir", file_okay=False)] = Path(
        "downloads"
    ),
    only_metadata: Annotated[bool, typer.Option("--only-metadata")] = False,
    compression_type: Annotated[
        CompressionTypeChoice | None, typer.Option("--compression-type")
    ] = None,
    timeout: Annotated[float, typer.Option("--timeout", min=1.0)] = 120.0,
    poll_interval: Annotated[float, typer.Option("--poll-interval", min=0.1)] = 2.0,
    handle_file: Annotated[
        Path | None, typer.Option("--handle-file", dir_okay=False)
    ] = None,
) -> None:
    """Schedule, wait for, download, and decrypt an invoice export."""

    inputs = InvoiceExportDownloadInput(
        date_from=date_from,
        date_to=date_to,
        role=role,
        date_type=date_type,
        amount_type=amount_type,
        output_dir=output_dir,
        only_metadata=only_metadata,
        compression_type=compression_type,
        timeout=timeout,
        poll_interval=poll_interval,
        handle_file=handle_file,
    )
    run_authenticated_command(ctx, lambda auth: download_invoice_export(auth, inputs))
