"""Shared invoice workflows used by CLI and TUI adapters."""

from datetime import datetime
from pathlib import Path
from typing import Self, cast

from ksef2.clients.authenticated import AuthenticatedClient
from ksef2.clients.online import OnlineSessionClient
from ksef2.domain.models.invoices import (
    InvoiceExportStatusResponse,
    InvoiceMetadata,
    InvoicesFilter,
    QueryInvoicesMetadataResponse,
    SendInvoiceResponse,
)
from ksef2.domain.models.pagination import InvoiceMetadataParams
from ksef2.domain.models.session import (
    FormSchema,
    SessionInvoiceStatusResponse,
    SessionStatusResponse,
)
from ksef2.domain.types import CurrencyCodes
from pydantic import BaseModel, Field, model_validator

from ksef2_cli.commands.invoices.models import (
    BatchInvoiceReceipt,
    CompressionTypeChoice,
    ExportHandleSaved,
    ExportPaths,
    InvoiceAmountTypeChoice,
    InvoiceDateTypeChoice,
    InvoiceRoleChoice,
    InvoiceSendModeChoice,
    InvoiceTypeChoice,
    InvoiceWorkflowBatch,
    InvoiceWorkflowItem,
    InvoiceWorkflowReceipt,
    InvoicesSendResult,
    InvoicingModeChoice,
    OnlineInvoiceReceipt,
    SortOrderChoice,
)
from ksef2_cli.config import FormSchemaChoice
from ksef2_cli.io import SECRET_MODEL_FILE_MODE, write_bytes_file, write_model_file
from ksef2_cli.parsing import parse_optional_bool
from ksef2_cli.results import FocusedResult, SavedFile


def _safe_filename(value: str, suffix: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in value)
    return safe if safe.endswith(suffix) else f"{safe}{suffix}"


def _online_receipt_path(
    *,
    invoice_path: Path,
    receipt_file: Path | None,
    receipt_dir: Path | None,
) -> Path | None:
    if receipt_file:
        return receipt_file
    if receipt_dir:
        return receipt_dir / _safe_filename(f"{invoice_path.stem}-receipt", ".json")
    return None


def _batch_receipt_path(
    *,
    reference_number: str,
    receipt_file: Path | None,
    receipt_dir: Path | None,
) -> Path | None:
    if receipt_file:
        return receipt_file
    if receipt_dir:
        return receipt_dir / _safe_filename(
            f"batch-{reference_number}-receipt", ".json"
        )
    return None


def _invoice_upo_path(upo_dir: Path, invoice_path: Path) -> Path:
    return upo_dir / _safe_filename(f"{invoice_path.stem}-upo", ".xml")


def _batch_upo_path(upo_dir: Path, session_reference: str, index: int) -> Path:
    return upo_dir / _safe_filename(f"batch-{session_reference}-upo-{index}", ".xml")


class InvoiceMetadataInput(BaseModel):
    date_from: str
    date_to: str | None = None
    role: InvoiceRoleChoice = InvoiceRoleChoice.SELLER
    date_type: InvoiceDateTypeChoice = InvoiceDateTypeChoice.ISSUE_DATE
    amount_type: InvoiceAmountTypeChoice = InvoiceAmountTypeChoice.BRUTTO
    currency: list[str] = Field(default_factory=list)
    invoice_type: list[InvoiceTypeChoice] = Field(default_factory=list)
    seller_nip: str | None = None
    buyer_nip: str | None = None
    buyer_vat_ue: str | None = None
    buyer_other_id: str | None = None
    invoice_number: str | None = None
    ksef_number: str | None = None
    amount_min: float | None = None
    amount_max: float | None = None
    form: FormSchemaChoice | None = None
    invoicing_mode: InvoicingModeChoice | None = None
    attachment: str | None = None
    self_invoicing: str | None = None
    page_size: int = Field(default=10, ge=10, le=250)
    page_offset: int = Field(default=0, ge=0)
    sort_order: SortOrderChoice = SortOrderChoice.ASC
    all_pages: bool = False


class InvoiceSendInput(BaseModel):
    invoice_paths: list[Path]
    mode: InvoiceSendModeChoice = InvoiceSendModeChoice.ONLINE
    recursive: bool = False
    wait: bool = False
    upo_dir: Path | None = None
    receipt_file: Path | None = None
    receipt_dir: Path | None = None
    form: FormSchemaChoice = FormSchemaChoice.FA3
    offline_mode: bool = False
    max_part_size: int | None = Field(default=None, ge=1)
    timeout: float = Field(default=120.0, ge=1.0)
    poll_interval: float = Field(default=2.0, ge=0.1)
    invoice_files: list[Path] = Field(default_factory=list)

    @property
    def form_schema(self) -> FormSchema:
        return self.form.form_schema

    @model_validator(mode="after")
    def validate_options(self) -> Self:
        invoice_files: list[Path] = []
        for path in self.invoice_paths:
            if path.is_dir():
                matches = path.rglob("*.xml") if self.recursive else path.glob("*.xml")
                invoice_files.extend(sorted(item for item in matches if item.is_file()))
                continue
            if path.suffix.lower() != ".xml":
                raise ValueError(f"{path} is not an .xml file.")
            invoice_files.append(path)

        if not invoice_files:
            raise ValueError("No XML invoice files found.")
        if self.upo_dir is not None and not self.wait:
            raise ValueError("--upo-dir requires --wait.")
        if self.receipt_file is not None and self.receipt_dir is not None:
            raise ValueError("Use either --receipt or --receipt-dir, not both.")
        if (
            self.mode is InvoiceSendModeChoice.ONLINE
            and len(invoice_files) > 1
            and self.receipt_file is not None
        ):
            raise ValueError(
                "Use --receipt-dir when writing receipts for multiple files."
            )
        if self.mode is InvoiceSendModeChoice.ONLINE:
            if self.offline_mode:
                raise ValueError("--offline requires --mode batch.")
            if self.max_part_size is not None:
                raise ValueError("--max-part-size requires --mode batch.")

        self.invoice_files = invoice_files
        return self


class InvoiceExportInput(BaseModel):
    date_from: str
    date_to: str | None = None
    role: InvoiceRoleChoice = InvoiceRoleChoice.SELLER
    date_type: InvoiceDateTypeChoice = InvoiceDateTypeChoice.ISSUE_DATE
    amount_type: InvoiceAmountTypeChoice = InvoiceAmountTypeChoice.BRUTTO
    only_metadata: bool = False
    compression_type: CompressionTypeChoice | None = None
    handle_file: Path | None = None


class InvoiceExportFetchInput(BaseModel):
    handle: ExportHandleSaved
    output_dir: Path = Path("downloads")
    wait: bool = False
    timeout: float = Field(default=120.0, ge=1.0)
    poll_interval: float = Field(default=2.0, ge=0.1)


class InvoiceExportDownloadInput(BaseModel):
    date_from: str
    date_to: str | None = None
    role: InvoiceRoleChoice = InvoiceRoleChoice.SELLER
    date_type: InvoiceDateTypeChoice = InvoiceDateTypeChoice.ISSUE_DATE
    amount_type: InvoiceAmountTypeChoice = InvoiceAmountTypeChoice.BRUTTO
    output_dir: Path = Path("downloads")
    only_metadata: bool = False
    compression_type: CompressionTypeChoice | None = None
    timeout: float = Field(default=120.0, ge=1.0)
    poll_interval: float = Field(default=2.0, ge=0.1)
    handle_file: Path | None = None


class OnlineInvoiceHandler:
    def __init__(
        self,
        *,
        auth: AuthenticatedClient,
        inputs: InvoiceSendInput,
    ) -> None:
        self.auth = auth
        self.inputs = inputs

    def send(self) -> InvoicesSendResult:
        with self.auth.online_session(form_code=self.inputs.form_schema) as session:
            items: list[InvoiceWorkflowItem] = []

            for invoice_path in self.inputs.invoice_files:
                items.append(self.send_one(session=session, invoice_path=invoice_path))

            failed = sum(1 for item in items if item.status == "failed")
            receipt_files = [
                item.receipt_file for item in items if item.receipt_file is not None
            ]
            upo_files = [item.upo_file for item in items if item.upo_file is not None]
            return InvoicesSendResult(
                mode="online",
                submitted=len(self.inputs.invoice_files),
                succeeded=len(items) - failed,
                failed=failed,
                items=items,
                receipt_files=receipt_files,
                upo_files=upo_files,
            )

    def send_one(
        self,
        *,
        session: OnlineSessionClient,
        invoice_path: Path,
    ) -> InvoiceWorkflowItem:
        invoice_reference: str | None = None
        ksef_number: str | None = None
        online_receipt_file: Path | None = None
        upo_file: Path | None = None
        status: SessionInvoiceStatusResponse | None = None
        item_status: str = "submitted"
        error: str | None = None

        try:
            result: SendInvoiceResponse | SessionInvoiceStatusResponse
            if self.inputs.wait:
                status = session.send_invoice_and_wait(
                    invoice_xml=invoice_path.read_bytes(),
                    timeout=self.inputs.timeout,
                    poll_interval=self.inputs.poll_interval,
                )
                result = status
                ksef_number = status.ksef_number
                if status.status.code >= 400:
                    item_status = "failed"
                    error = status.status.description
                else:
                    item_status = "accepted"
            else:
                result = session.send_invoice(invoice_xml=invoice_path.read_bytes())

            invoice_reference = result.reference_number

            if self.inputs.wait and self.inputs.upo_dir is not None and error is None:
                content = session.get_invoice_upo_by_reference(
                    invoice_reference_number=invoice_reference
                )
                upo_file = write_bytes_file(
                    _invoice_upo_path(self.inputs.upo_dir, invoice_path),
                    content,
                )

            online_receipt_file = _online_receipt_path(
                invoice_path=invoice_path,
                receipt_file=self.inputs.receipt_file,
                receipt_dir=self.inputs.receipt_dir,
            )
            if online_receipt_file is not None:
                write_model_file(
                    online_receipt_file,
                    InvoiceWorkflowReceipt(
                        mode="online",
                        submitted_files=[invoice_path],
                        online=OnlineInvoiceReceipt(
                            file=invoice_path,
                            session_state=session.get_state(),
                            invoice_reference=invoice_reference,
                            status=status,
                            upo_file=upo_file,
                        ),
                    ),
                    file_mode=SECRET_MODEL_FILE_MODE,
                )
        except Exception as exc:
            item_status = "failed"
            error = str(exc) or type(exc).__name__

        return InvoiceWorkflowItem(
            file=invoice_path,
            status=item_status,
            invoice_reference=invoice_reference,
            ksef_number=ksef_number,
            receipt_file=online_receipt_file,
            upo_file=upo_file,
            error=error,
        )


class BatchInvoiceHandler:
    def __init__(
        self,
        *,
        auth: AuthenticatedClient,
        inputs: InvoiceSendInput,
    ) -> None:
        self.auth = auth
        self.inputs = inputs

    def send(self) -> InvoicesSendResult:
        batch_client = self.auth.batch
        inputs = self.inputs

        if inputs.max_part_size is None:
            prepared = batch_client.prepare_batch_from_paths(
                invoice_paths=inputs.invoice_files,
                form_code=inputs.form_schema,
                offline_mode=inputs.offline_mode,
            )
        else:
            prepared = batch_client.prepare_batch_from_paths(
                invoice_paths=inputs.invoice_files,
                form_code=inputs.form_schema,
                offline_mode=inputs.offline_mode,
                max_part_size=inputs.max_part_size,
            )

        state = batch_client.submit_prepared_batch(prepared_batch=prepared)
        status = (
            batch_client.wait_for_completion(
                session=state,
                timeout=inputs.timeout,
                poll_interval=inputs.poll_interval,
            )
            if inputs.wait
            else None
        )
        saved_upos = (
            download_batch_upos(
                auth=self.auth,
                session_reference=state.reference_number,
                status=status,
                upo_dir=inputs.upo_dir,
            )
            if inputs.upo_dir is not None
            else []
        )
        upo_files = [saved.path for saved in saved_upos]

        batch_receipt_file = _batch_receipt_path(
            reference_number=state.reference_number,
            receipt_file=inputs.receipt_file,
            receipt_dir=inputs.receipt_dir,
        )
        if batch_receipt_file is not None:
            write_model_file(
                batch_receipt_file,
                InvoiceWorkflowReceipt(
                    mode="batch",
                    submitted_files=inputs.invoice_files,
                    batch=BatchInvoiceReceipt(
                        session_reference=state.reference_number,
                        files=inputs.invoice_files,
                        status=status,
                        upo_files=upo_files,
                    ),
                ),
                file_mode=SECRET_MODEL_FILE_MODE,
            )

        batch_status = "submitted"
        if status is not None:
            batch_status = "failed" if status.status.code >= 400 else "completed"

        invoice_count = len(inputs.invoice_files)
        successful_invoice_count: int | None = None
        failed_invoice_count: int | None = None
        if status is not None:
            if status.invoice_count is not None:
                invoice_count = status.invoice_count
            successful_invoice_count = status.successful_invoice_count
            failed_invoice_count = status.failed_invoice_count

        failed = failed_invoice_count if failed_invoice_count is not None else 0
        succeeded = (
            successful_invoice_count
            if successful_invoice_count is not None
            else len(inputs.invoice_files)
        )
        receipt_files = []
        if batch_receipt_file is not None:
            receipt_files = [batch_receipt_file]

        batch = InvoiceWorkflowBatch(
            status=batch_status,
            session_reference=state.reference_number,
            invoice_count=invoice_count,
            successful_invoice_count=successful_invoice_count,
            failed_invoice_count=failed_invoice_count,
            receipt_file=batch_receipt_file,
            upo_files=upo_files,
        )
        return InvoicesSendResult(
            mode="batch",
            submitted=len(inputs.invoice_files),
            succeeded=succeeded,
            failed=failed,
            batch=batch,
            receipt_files=receipt_files,
            upo_files=upo_files,
        )


def query_invoice_metadata(
    auth: AuthenticatedClient, inputs: InvoiceMetadataInput
) -> QueryInvoicesMetadataResponse | list[InvoiceMetadata]:
    effective_date_to = inputs.date_to if inputs.date_to is not None else datetime.now()
    filters = InvoicesFilter(
        role=inputs.role.value,
        date_type=inputs.date_type.value,
        date_from=inputs.date_from,
        date_to=effective_date_to,
        amount_type=inputs.amount_type.value,
        currency_codes=cast(list[CurrencyCodes], inputs.currency)
        if inputs.currency
        else None,
        invoice_types=[item.value for item in inputs.invoice_type] or None,
        seller_nip=inputs.seller_nip,
        buyer_nip=inputs.buyer_nip,
        buyer_vat_ue=inputs.buyer_vat_ue,
        buyer_other_id=inputs.buyer_other_id,
        invoice_number=inputs.invoice_number,
        ksef_number=inputs.ksef_number,
        amount_min=inputs.amount_min,
        amount_max=inputs.amount_max,
        invoice_schema=inputs.form.form_schema if inputs.form else None,
        invoicing_mode=inputs.invoicing_mode.value if inputs.invoicing_mode else None,
        has_attachment=parse_optional_bool(inputs.attachment, option_name="--attachment"),
        is_self_invoicing=parse_optional_bool(
            inputs.self_invoicing, option_name="--self-invoicing"
        ),
    )
    params = InvoiceMetadataParams(
        page_size=inputs.page_size,
        page_offset=inputs.page_offset,
        sort_order=inputs.sort_order.value,
    )

    if inputs.all_pages:
        return list(auth.invoices.all_metadata(filters=filters, params=params))
    return auth.invoices.query_metadata(filters=filters, params=params)


def download_invoice(
    auth: AuthenticatedClient,
    *,
    ksef_number: str,
    output_file: Path | None = None,
    wait: bool = False,
    timeout: float = 120.0,
    poll_interval: float = 2.0,
) -> SavedFile:
    if wait:
        content = auth.invoices.wait_for_invoice_download(
            ksef_number=ksef_number,
            timeout=timeout,
            poll_interval=poll_interval,
        )
    else:
        content = auth.invoices.download_invoice(ksef_number=ksef_number)
    target = output_file or Path(_safe_filename(ksef_number, ".xml"))
    return SavedFile(path=write_bytes_file(target, content), size=len(content))


def send_invoices(auth: AuthenticatedClient, inputs: InvoiceSendInput) -> InvoicesSendResult:
    match inputs.mode:
        case InvoiceSendModeChoice.ONLINE:
            return OnlineInvoiceHandler(auth=auth, inputs=inputs).send()
        case InvoiceSendModeChoice.BATCH:
            return BatchInvoiceHandler(auth=auth, inputs=inputs).send()


def schedule_invoice_export(
    auth: AuthenticatedClient, inputs: InvoiceExportInput
) -> ExportHandleSaved:
    effective_date_to = inputs.date_to if inputs.date_to is not None else datetime.now()
    filters = InvoicesFilter(
        role=inputs.role.value,
        date_type=inputs.date_type.value,
        date_from=inputs.date_from,
        date_to=effective_date_to,
        amount_type=inputs.amount_type.value,
    )
    handle = auth.invoices.schedule_export(
        filters=filters,
        only_metadata=inputs.only_metadata,
        compression_type=inputs.compression_type.value
        if inputs.compression_type
        else None,
    )
    saved = ExportHandleSaved.from_handle(handle)
    if inputs.handle_file:
        write_model_file(inputs.handle_file, saved)
    return ExportHandleSaved.from_handle(handle, handle_file=inputs.handle_file)


def get_invoice_export_status(
    auth: AuthenticatedClient, reference_number: str
) -> InvoiceExportStatusResponse:
    return auth.invoices.get_export_status(reference_number=reference_number)


def fetch_invoice_export(
    auth: AuthenticatedClient, inputs: InvoiceExportFetchInput
) -> FocusedResult[ExportPaths, str]:
    handle = inputs.handle.to_handle()

    if inputs.wait:
        package = auth.invoices.wait_for_export_package(
            reference_number=handle.reference_number,
            timeout=inputs.timeout,
            poll_interval=inputs.poll_interval,
        )
    else:
        status = auth.invoices.get_export_status(reference_number=handle.reference_number)
        if status.package is None:
            raise ValueError(
                "Export package is not ready. Re-run with --wait or check export-status."
            )
        package = status.package
    paths = auth.invoices.fetch_package(
        package=package,
        export=handle,
        target_directory=inputs.output_dir,
    )
    return FocusedResult(
        payload=ExportPaths(
            reference_number=handle.reference_number,
            paths=paths,
        ),
        items=[str(path) for path in paths],
    )


def download_invoice_export(
    auth: AuthenticatedClient, inputs: InvoiceExportDownloadInput
) -> FocusedResult[ExportPaths, str]:
    effective_date_to = inputs.date_to if inputs.date_to is not None else datetime.now()
    filters = InvoicesFilter(
        role=inputs.role.value,
        date_type=inputs.date_type.value,
        date_from=inputs.date_from,
        date_to=effective_date_to,
        amount_type=inputs.amount_type.value,
    )
    handle = auth.invoices.schedule_export(
        filters=filters,
        only_metadata=inputs.only_metadata,
        compression_type=inputs.compression_type.value
        if inputs.compression_type
        else None,
    )
    saved = ExportHandleSaved.from_handle(handle)
    if inputs.handle_file:
        write_model_file(inputs.handle_file, saved)
    package = auth.invoices.wait_for_export_package(
        reference_number=handle.reference_number,
        timeout=inputs.timeout,
        poll_interval=inputs.poll_interval,
    )
    paths = auth.invoices.fetch_package(
        package=package,
        export=handle,
        target_directory=inputs.output_dir,
    )
    return FocusedResult(
        payload=ExportPaths(
            reference_number=handle.reference_number,
            handle_file=inputs.handle_file,
            paths=paths,
        ),
        items=[str(path) for path in paths],
    )


def download_batch_upos(
    *,
    auth: AuthenticatedClient,
    session_reference: str,
    status: SessionStatusResponse | None,
    upo_dir: Path,
) -> list[SavedFile]:
    if status is None:
        raise ValueError("--upo-dir requires a completed batch status.")
    if status.status.code >= 400:
        raise ValueError(
            "Batch processing failed: "
            f"{session_reference} ({status.status.code}: {status.status.description})"
        )
    if status.upo is None or not status.upo.pages:
        raise ValueError("Batch UPO is not ready. Re-run with --wait.")

    saved: list[SavedFile] = []
    for index, page in enumerate(status.upo.pages, start=1):
        content = auth.batch.get_upo(
            session=session_reference,
            upo_reference_number=page.reference_number,
        )
        target = _batch_upo_path(
            upo_dir=upo_dir, session_reference=session_reference, index=index
        )
        saved.append(
            SavedFile(path=write_bytes_file(target, content), size=len(content))
        )
    return saved
