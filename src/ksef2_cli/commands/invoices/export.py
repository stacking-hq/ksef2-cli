"""Invoice export commands."""

from pathlib import Path
from typing import Annotated

import typer
from ksef2.clients import AuthenticatedClient
from ksef2.models import ExportResumeState, InvoiceExportStatusResponse

from ksef2_cli.commands.invoices.filters import (
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
    CompressionTypeChoice,
    ExportPaths,
    InvoiceAmountTypeChoice,
    InvoiceDateTypeChoice,
    InvoiceRoleChoice,
)
from ksef2_cli.context import run_authenticated_command
from ksef2_cli.invoice_workflows import (
    InvoiceExportDownloadInput,
    InvoiceExportFetchInput,
    InvoiceExportInput,
    download_invoice_export,
    fetch_invoice_export,
    get_invoice_export_status,
    schedule_invoice_export,
)
from ksef2_cli.parsing import parse_iso_datetime
from ksef2_cli.results import FocusedResult


def invoices_export(
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
    """Schedule an invoice export and optionally save its resumable state."""

    def load_input() -> InvoiceExportInput:
        return InvoiceExportInput(
            date_from=parse_iso_datetime(date_from, option_name="--date-from"),
            date_to=None
            if date_to is None
            else parse_iso_datetime(date_to, option_name="--date-to"),
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
            only_metadata=only_metadata,
            compression_type=compression_type,
            handle_file=handle_file,
        )

    run_authenticated_command(
        ctx,
        lambda auth: schedule_invoice_export(auth, load_input()),
        validate=load_input,
    )


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
            handle=ExportResumeState.from_json(handle_file.read_text(encoding="utf-8")),
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

    def load_input() -> InvoiceExportDownloadInput:
        return InvoiceExportDownloadInput(
            date_from=parse_iso_datetime(date_from, option_name="--date-from"),
            date_to=None
            if date_to is None
            else parse_iso_datetime(date_to, option_name="--date-to"),
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
            output_dir=output_dir,
            only_metadata=only_metadata,
            compression_type=compression_type,
            timeout=timeout,
            poll_interval=poll_interval,
            handle_file=handle_file,
        )

    run_authenticated_command(
        ctx,
        lambda auth: download_invoice_export(auth, load_input()),
        validate=load_input,
    )
