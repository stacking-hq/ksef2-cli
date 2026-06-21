"""Invoice metadata and download commands."""

from pathlib import Path
from typing import Annotated

import typer
from ksef2.clients.authenticated import AuthenticatedClient

from ksef2_cli.commands.invoices.models import (
    InvoiceAmountTypeChoice,
    InvoiceDateTypeChoice,
    InvoiceRoleChoice,
    InvoiceTypeChoice,
    InvoicingModeChoice,
    SortOrderChoice,
)
from ksef2_cli.config import FORM_SCHEMA_NAMES, FormSchemaChoice
from ksef2_cli.context import run_authenticated_command
from ksef2_cli.invoice_workflows import (
    InvoiceMetadataInput,
    download_invoice,
    query_invoice_metadata,
)
from ksef2_cli.results import SavedFile


def invoices_metadata(
    ctx: typer.Context,
    date_from: Annotated[
        str, typer.Option("--date-from", help="Start datetime/date, ISO format.")
    ],
    date_to: Annotated[
        str | None, typer.Option("--date-to", help="End datetime/date, ISO format.")
    ] = None,
    role: Annotated[
        InvoiceRoleChoice,
        typer.Option(
            "--role", help="buyer, seller, third_subject, authorized_subject."
        ),
    ] = InvoiceRoleChoice.SELLER,
    date_type: Annotated[
        InvoiceDateTypeChoice,
        typer.Option(
            "--date-type", help="issue_date, invoicing_date, permanent_storage."
        ),
    ] = InvoiceDateTypeChoice.ISSUE_DATE,
    amount_type: Annotated[
        InvoiceAmountTypeChoice,
        typer.Option("--amount-type", help="brutto, netto, or vat."),
    ] = InvoiceAmountTypeChoice.BRUTTO,
    currency: Annotated[
        list[str],
        typer.Option("--currency", help="Currency code. Repeat for multiple."),
    ] = [],
    invoice_type: Annotated[
        list[InvoiceTypeChoice],
        typer.Option("--invoice-type", help="Invoice type. Repeat for multiple."),
    ] = [],
    seller_nip: Annotated[str | None, typer.Option("--seller-nip")] = None,
    buyer_nip: Annotated[str | None, typer.Option("--buyer-nip")] = None,
    buyer_vat_ue: Annotated[str | None, typer.Option("--buyer-vat-ue")] = None,
    buyer_other_id: Annotated[str | None, typer.Option("--buyer-other-id")] = None,
    invoice_number: Annotated[str | None, typer.Option("--invoice-number")] = None,
    ksef_number: Annotated[str | None, typer.Option("--ksef-number")] = None,
    amount_min: Annotated[float | None, typer.Option("--amount-min")] = None,
    amount_max: Annotated[float | None, typer.Option("--amount-max")] = None,
    form: Annotated[
        FormSchemaChoice | None,
        typer.Option("--form", help=f"Form schema: {FORM_SCHEMA_NAMES}."),
    ] = None,
    invoicing_mode: Annotated[
        InvoicingModeChoice | None,
        typer.Option("--invoicing-mode", help="online or offline."),
    ] = None,
    attachment: Annotated[
        str | None,
        typer.Option("--attachment", help="Filter by attachment presence: yes or no."),
    ] = None,
    self_invoicing: Annotated[
        str | None,
        typer.Option(
            "--self-invoicing", help="Filter by self-invoicing flag: yes or no."
        ),
    ] = None,
    page_size: Annotated[int, typer.Option("--page-size", min=10, max=250)] = 10,
    page_offset: Annotated[int, typer.Option("--page-offset", min=0)] = 0,
    sort_order: Annotated[
        SortOrderChoice, typer.Option("--sort-order", help="asc or desc.")
    ] = SortOrderChoice.ASC,
    all_pages: Annotated[
        bool, typer.Option("--all", help="Fetch all metadata items.")
    ] = False,
) -> None:
    """Query invoice metadata."""

    inputs = InvoiceMetadataInput(
        date_from=date_from,
        date_to=date_to,
        role=role,
        date_type=date_type,
        amount_type=amount_type,
        currency=currency,
        invoice_type=invoice_type,
        seller_nip=seller_nip,
        buyer_nip=buyer_nip,
        buyer_vat_ue=buyer_vat_ue,
        buyer_other_id=buyer_other_id,
        invoice_number=invoice_number,
        ksef_number=ksef_number,
        amount_min=amount_min,
        amount_max=amount_max,
        form=form,
        invoicing_mode=invoicing_mode,
        attachment=attachment,
        self_invoicing=self_invoicing,
        page_size=page_size,
        page_offset=page_offset,
        sort_order=sort_order,
        all_pages=all_pages,
    )

    run_authenticated_command(ctx, lambda auth: query_invoice_metadata(auth, inputs))


def invoices_download(
    ctx: typer.Context,
    ksef_number: Annotated[
        str, typer.Option("--ksef-number", help="KSeF invoice number.")
    ],
    output_file: Annotated[
        Path | None,
        typer.Option("--out", "-o", dir_okay=False, help="Target XML file."),
    ] = None,
    wait: Annotated[
        bool, typer.Option("--wait", help="Poll until the invoice can be downloaded.")
    ] = False,
    timeout: Annotated[float, typer.Option("--timeout", min=1.0)] = 120.0,
    poll_interval: Annotated[float, typer.Option("--poll-interval", min=0.1)] = 2.0,
) -> None:
    """Download processed invoice XML by KSeF number."""

    def work(auth: AuthenticatedClient) -> SavedFile:
        return download_invoice(
            auth,
            ksef_number=ksef_number,
            output_file=output_file,
            wait=wait,
            timeout=timeout,
            poll_interval=poll_interval,
        )

    run_authenticated_command(ctx, work)
