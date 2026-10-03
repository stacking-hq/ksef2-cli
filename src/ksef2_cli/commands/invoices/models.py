"""Invoice command-owned models."""

import base64
import json
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from ksef2.models import (
    OnlineSessionResumeState,
    SessionInvoiceStatusResponse,
    SessionStatusResponse,
)
from pydantic import Field

from ksef2_cli.results import CliResult, SavedFile

if TYPE_CHECKING:
    from ksef2.models import ExportHandle


InvoiceWorkflowMode = Literal["online", "batch"]
InvoiceWorkflowItemStatus = Literal["submitted", "accepted", "failed"]
InvoiceWorkflowBatchStatus = Literal["submitted", "completed", "failed"]


class OnlineInvoiceReceipt(CliResult):
    """Resumable receipt for one invoice sent through an online session."""

    file: Path
    session_state: OnlineSessionResumeState
    invoice_reference: str
    status: SessionInvoiceStatusResponse | None = None
    upo_file: Path | None = None


class BatchSessionStatus(CliResult):
    """Last known batch processing status recorded in a receipt file.

    The SDK response is not stored verbatim: its UPO pages carry capability-bearing
    download URLs that the SDK keeps out of every dump, and a receipt file has no use for
    them. Only what the CLI reports is kept, and the fields stay optional so receipts
    written by older CLI versions still load.
    """

    code: int | None = None
    description: str | None = None
    invoice_count: int | None = None
    successful_invoice_count: int | None = None
    failed_invoice_count: int | None = None
    upo_references: list[str] = Field(default_factory=list)

    @classmethod
    def from_status(cls, status: SessionStatusResponse) -> "BatchSessionStatus":
        upo_references: list[str] = (
            [] if status.upo is None else [page.reference_number for page in status.upo.pages]
        )
        return cls(
            code=status.status.code,
            description=status.status.description,
            invoice_count=status.invoice_count,
            successful_invoice_count=status.successful_invoice_count,
            failed_invoice_count=status.failed_invoice_count,
            upo_references=upo_references,
        )


class BatchInvoiceReceipt(CliResult):
    """Resumable receipt for one submitted batch session."""

    session_reference: str
    files: list[Path]
    status: BatchSessionStatus | None = None
    upo_files: list[Path] = Field(default_factory=list)


class InvoiceWorkflowReceipt(CliResult):
    """CLI-owned continuation file for high-level invoice workflows."""

    version: int = 1
    mode: InvoiceWorkflowMode
    submitted_files: list[Path]
    online: OnlineInvoiceReceipt | None = None
    batch: BatchInvoiceReceipt | None = None

    def to_resumable_json(self) -> str:
        """Serialize the receipt so its online session can still be resumed.

        ``model_dump_json`` masks the resume state's AES key and IV, which would save a
        receipt that can no longer resume its session, so the state is exported through
        the SDK's own credential export. The result is credential material: write it to a
        protected file only, never to command output.
        """
        data = self.model_dump(mode="json", by_alias=True, exclude_none=True)
        if self.online is not None:
            data["online"] = {
                **data["online"],
                "session_state": self.online.session_state.to_dict(mode="json"),
            }
        return json.dumps(data, indent=2)


class InvoiceWorkflowItem(CliResult):
    """One file handled by a high-level invoice workflow."""

    file: Path
    status: InvoiceWorkflowItemStatus
    invoice_reference: str | None = None
    ksef_number: str | None = None
    receipt_file: Path | None = None
    upo_file: Path | None = None
    error: str | None = None


class InvoiceWorkflowBatch(CliResult):
    """One batch handled by a high-level invoice workflow."""

    status: InvoiceWorkflowBatchStatus
    session_reference: str
    invoice_count: int
    successful_invoice_count: int | None = None
    failed_invoice_count: int | None = None
    receipt_file: Path | None = None
    upo_files: list[Path] = Field(default_factory=list)
    error: str | None = None


class InvoicesSendResult(CliResult):
    """Result for the high-level ``invoices send`` workflow."""

    mode: InvoiceWorkflowMode
    submitted: int
    succeeded: int
    failed: int
    items: list[InvoiceWorkflowItem] = Field(default_factory=list)
    batch: InvoiceWorkflowBatch | None = None
    receipt_files: list[Path] = Field(default_factory=list)
    upo_files: list[Path] = Field(default_factory=list)


class InvoicesStatusResult(CliResult):
    """Result for checking a high-level invoice workflow receipt."""

    mode: InvoiceWorkflowMode
    receipt_file: Path
    status: str
    status_code: int
    status_description: str
    session_reference: str
    file: Path | None = None
    invoice_reference: str | None = None
    ksef_number: str | None = None
    invoice_count: int | None = None
    successful_invoice_count: int | None = None
    failed_invoice_count: int | None = None
    receipt_updated: bool = True


class InvoicesUpoResult(CliResult):
    """Result for downloading UPO files from a high-level receipt."""

    mode: InvoiceWorkflowMode
    receipt_file: Path
    session_reference: str
    file: Path | None = None
    invoice_reference: str | None = None
    ksef_number: str | None = None
    upo_files: list[SavedFile] = Field(default_factory=list)
    receipt_updated: bool = True


class ExportHandleSaved(CliResult):
    """Export handle material printed or saved by export commands."""

    reference_number: str
    aes_key: str
    iv: str
    handle_file: Path | None = None

    @classmethod
    def from_handle(
        cls, handle: "ExportHandle", *, handle_file: Path | None = None
    ) -> "ExportHandleSaved":
        return cls(
            reference_number=handle.reference_number,
            aes_key=base64.b64encode(handle.aes_key).decode("ascii"),
            iv=base64.b64encode(handle.iv).decode("ascii"),
            handle_file=handle_file,
        )

    def to_handle(self) -> "ExportHandle":
        from ksef2.models import ExportHandle

        return ExportHandle(
            reference_number=self.reference_number,
            aes_key=base64.b64decode(self.aes_key),
            iv=base64.b64decode(self.iv),
        )


class ExportPaths(CliResult):
    """Paths written by an invoice export package fetch."""

    reference_number: str
    paths: list[Path]
    handle_file: Path | None = None


class InvoiceRoleChoice(StrEnum):
    SELLER = "seller"
    BUYER = "buyer"
    THIRD_SUBJECT = "third_subject"
    AUTHORIZED_SUBJECT = "authorized_subject"


class InvoiceDateTypeChoice(StrEnum):
    ISSUE_DATE = "issue_date"
    INVOICING_DATE = "invoicing_date"
    PERMANENT_STORAGE = "permanent_storage"


class InvoiceAmountTypeChoice(StrEnum):
    BRUTTO = "brutto"
    NETTO = "netto"
    VAT = "vat"


class InvoiceTypeChoice(StrEnum):
    VAT = "vat"
    ZAL = "zal"
    KOR = "kor"
    ROZ = "roz"
    UPR = "upr"
    KOR_ZAL = "kor_zal"
    KOR_ROZ = "kor_roz"
    VAT_PEF = "vat_pef"
    VAT_PEF_SP = "vat_pef_sp"
    KOR_PEF = "kor_pef"
    VAT_RR = "vat_rr"
    KOR_VAT_RR = "kor_vat_rr"


class InvoicingModeChoice(StrEnum):
    ONLINE = "online"
    OFFLINE = "offline"


class SortOrderChoice(StrEnum):
    ASC = "asc"
    DESC = "desc"


class InvoiceSendModeChoice(StrEnum):
    ONLINE = "online"
    BATCH = "batch"


class CompressionTypeChoice(StrEnum):
    ZIP = "zip"
    TAR_GZ = "tar_gz"
