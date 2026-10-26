"""Invoice export commands."""

from pathlib import Path
from functools import cache
from typing import Annotated

import typer
from ksef2.clients import AuthenticatedClient
from ksef2.models import ExportResumeState, InvoiceExportStatusResponse

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
    CompressionTypeChoice,
    ExportPaths,
    InvoiceAmountTypeChoice,
    InvoiceDateTypeChoice,
    InvoiceRoleChoice,
)
from ksef2_cli.config import PdfPageSizeChoice
from ksef2_cli.context import (
    get_settings,
    render_invoice_pdf,
    run_authenticated_command,
)
from ksef2_cli.runtime import create_pdf_exporter
from ksef2_cli.invoice_workflows import (
    InvoiceExportDownloadInput,
    InvoiceExportFetchInput,
    InvoiceExportInput,
    InvoiceExportPdfInput,
    download_invoice_export,
    export_invoices_to_pdf,
    fetch_invoice_export,
    get_invoice_export_status,
    schedule_invoice_export,
)
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
        CompressionTypeChoice | None,
        typer.Option(
            "--compression-type", help="Export archive format: zip or tar_gz."
        ),
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

    @cache
    def load_input() -> InvoiceExportInput:
        return InvoiceExportInput(
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
        Path, typer.Option("--handle-file", exists=True, dir_okay=False, help="Saved export handle containing the decryption state.")
    ],
    output_dir: Annotated[Path, typer.Option("--out-dir", file_okay=False, help="Directory for downloaded export files.")] = Path(
        "downloads"
    ),
    wait: Annotated[
        bool, typer.Option("--wait", help="Wait for the export package.")
    ] = False,
    timeout: Annotated[
        float, typer.Option("--timeout", min=1.0, help="Maximum wait in seconds.")
    ] = 120.0,
    poll_interval: Annotated[
        float,
        typer.Option("--poll-interval", min=0.1, help="Seconds between status checks."),
    ] = 2.0,
) -> None:
    """Fetch and decrypt an export package using a saved export handle."""

    @cache
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
    output_dir: Annotated[Path, typer.Option("--out-dir", file_okay=False, help="Directory for downloaded export files.")] = Path(
        "downloads"
    ),
    only_metadata: Annotated[bool, typer.Option("--only-metadata", help="Export metadata without invoice XML files.")] = False,
    compression_type: Annotated[
        CompressionTypeChoice | None,
        typer.Option(
            "--compression-type", help="Export archive format: zip or tar_gz."
        ),
    ] = None,
    timeout: Annotated[
        float, typer.Option("--timeout", min=1.0, help="Maximum wait in seconds.")
    ] = 120.0,
    poll_interval: Annotated[
        float,
        typer.Option("--poll-interval", min=0.1, help="Seconds between status checks."),
    ] = 2.0,
    handle_file: Annotated[
        Path | None, typer.Option("--handle-file", dir_okay=False, help="Save resumable export state to this protected file.")
    ] = None,
) -> None:
    """Schedule, wait for, download, and decrypt an invoice export."""

    @cache
    def load_input() -> InvoiceExportDownloadInput:
        return InvoiceExportDownloadInput(
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


def invoices_export_pdf(
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
    output_dir: Annotated[Path, typer.Option("--out-dir", file_okay=False, help="Directory for downloaded export files.")] = Path(
        "downloads"
    ),
    pdf_dir: Annotated[
        Path | None,
        typer.Option(
            "--pdf-dir",
            file_okay=False,
            help="Where to write PDFs. Defaults to --out-dir.",
        ),
    ] = None,
    paper_size: Annotated[
        PdfPageSizeChoice | None,
        typer.Option(
            "--paper-size",
            help="PDF paper size. Defaults to the stylesheet setting.",
        ),
    ] = None,
    only_metadata: Annotated[bool, typer.Option("--only-metadata", help="Export metadata without invoice XML files.")] = False,
    compression_type: Annotated[
        CompressionTypeChoice | None,
        typer.Option(
            "--compression-type", help="Export archive format: zip or tar_gz."
        ),
    ] = None,
    timeout: Annotated[
        float, typer.Option("--timeout", min=1.0, help="Maximum wait in seconds.")
    ] = 120.0,
    poll_interval: Annotated[
        float,
        typer.Option("--poll-interval", min=0.1, help="Seconds between status checks."),
    ] = 2.0,
    handle_file: Annotated[
        Path | None, typer.Option("--handle-file", dir_okay=False, help="Save resumable export state to this protected file.")
    ] = None,
) -> None:
    """Download an invoice export and render each invoice to PDF.

    Needs the optional pdf extra: install ``ksef2-cli[pdf]``, which pulls in WeasyPrint
    and its system libraries. The decrypted XML stays in --out-dir and each PDF is
    written beside it, or into --pdf-dir when given.
    """

    @cache
    def load_input() -> InvoiceExportPdfInput:
        return InvoiceExportPdfInput(
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
            output_dir=output_dir,
            pdf_dir=pdf_dir,
            only_metadata=only_metadata,
            compression_type=compression_type,
            timeout=timeout,
            poll_interval=poll_interval,
            handle_file=handle_file,
        )

    exporter = None

    def prepare() -> None:
        nonlocal exporter
        load_input()
        settings = get_settings(ctx)
        if not (
            settings.runtime_overrides
            and settings.runtime_overrides.invoice_pdf_renderer
        ):
            exporter = create_pdf_exporter(
                environment=settings.environment, page_size=pdf_page_size
            )

    # The renderer carries the paper size, so the workflow only hands it XML paths.
    pdf_page_size = paper_size.pdf_page_size if paper_size else None
    run_authenticated_command(
        ctx,
        lambda auth: export_invoices_to_pdf(
            auth,
            load_input(),
            lambda invoice_xml_path: (
                exporter.export_from_path(invoice_xml_path)
                if exporter is not None
                else render_invoice_pdf(ctx, invoice_xml_path, page_size=pdf_page_size)
            ),
        ),
        validate=prepare,
    )
