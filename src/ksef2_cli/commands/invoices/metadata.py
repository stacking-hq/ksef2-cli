"""Invoice metadata and download commands."""

from pathlib import Path
from functools import cache
from typing import Annotated

import typer
from ksef2.clients import AuthenticatedClient

from ksef2_cli.commands.invoices.filters import (
    parse_invoice_dates,
    AmountMaxOption,
    AmountMinOption,
    AmountTypeOption,
    AttachmentOption,
    BuyerNipOption,
    BuyerOtherIdOption,
    BuyerVatUeOption,
    CurrencyOption,
    DateFromOption,
    DateToOption,
    DateTypeOption,
    FormOption,
    InvoiceNumberOption,
    InvoiceTypeOption,
    InvoicingModeOption,
    KsefNumberOption,
    PermanentStorageHwmOption,
    RoleOption,
    SellerNipOption,
    SelfInvoicingOption,
)
from ksef2_cli.commands.invoices.models import (
    InvoiceAmountTypeChoice,
    InvoiceDateTypeChoice,
    InvoiceRoleChoice,
    SortOrderChoice,
)
from ksef2_cli.context import run_authenticated_command
from ksef2_cli.invoice_workflows import (
    InvoiceMetadataInput,
    download_invoice,
    query_invoice_metadata,
)
from ksef2_cli.results import SavedFile


def invoices_metadata(
    ctx: typer.Context,
    date_from: DateFromOption,
    date_to: DateToOption = None,
    role: RoleOption = InvoiceRoleChoice.SELLER,
    date_type: DateTypeOption = InvoiceDateTypeChoice.ISSUE_DATE,
    amount_type: AmountTypeOption = InvoiceAmountTypeChoice.BRUTTO,
    restrict_hwm: PermanentStorageHwmOption = False,
    currency: CurrencyOption = [],
    invoice_type: InvoiceTypeOption = [],
    seller_nip: SellerNipOption = None,
    buyer_nip: BuyerNipOption = None,
    buyer_vat_ue: BuyerVatUeOption = None,
    buyer_other_id: BuyerOtherIdOption = None,
    invoice_number: InvoiceNumberOption = None,
    ksef_number: KsefNumberOption = None,
    amount_min: AmountMinOption = None,
    amount_max: AmountMaxOption = None,
    form: FormOption = None,
    invoicing_mode: InvoicingModeOption = None,
    attachment: AttachmentOption = None,
    self_invoicing: SelfInvoicingOption = None,
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

    @cache
    def load_input() -> InvoiceMetadataInput:
        return InvoiceMetadataInput(
            **parse_invoice_dates(date_from, date_to),
            role=role,
            date_type=date_type,
            amount_type=amount_type,
            restrict_to_permanent_storage_hwm_date=restrict_hwm,
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

    run_authenticated_command(
        ctx,
        lambda auth: query_invoice_metadata(auth, load_input()),
        validate=load_input,
    )


def invoices_download(
    ctx: typer.Context,
    ksef_number: Annotated[
        str | None,
        typer.Option(
            "--ksef-number",
            help="KSeF invoice number. Alternative to the positional number.",
        ),
    ] = None,
    output_file: Annotated[
        Path | None,
        typer.Option("--out", "-o", dir_okay=False, help="Target XML file."),
    ] = None,
    wait: Annotated[
        bool, typer.Option("--wait", help="Poll until the invoice can be downloaded.")
    ] = False,
    timeout: Annotated[
        float, typer.Option("--timeout", min=1.0, help="Maximum wait in seconds.")
    ] = 120.0,
    poll_interval: Annotated[
        float,
        typer.Option("--poll-interval", min=0.1, help="Seconds between status checks."),
    ] = 2.0,
    number: Annotated[str | None, typer.Argument(help="KSeF invoice number.")] = None,
) -> None:
    """Download processed invoice XML by KSeF number."""

    def validate() -> None:
        if (ksef_number is None) == (number is None):
            raise ValueError(
                "Provide one KSeF number, either positionally or with --ksef-number."
            )

    def work(auth: AuthenticatedClient) -> SavedFile:
        return download_invoice(
            auth,
            ksef_number=ksef_number or number,
            output_file=output_file,
            wait=wait,
            timeout=timeout,
            poll_interval=poll_interval,
        )

    run_authenticated_command(ctx, work, validate=validate)
