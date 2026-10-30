import base64
import json
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from rich.cells import cell_len

from ksef2 import KSeFInvoiceRejectedError, KSeFSessionError

from conftest import (
    FakeService,
    batch_state,
    cli_args,
    fake_runtime,
    online_state,
    payload,
    plain,
)
from ksef2.models import (
    BatchSessionResumeState,
    ExportResumeState,
    ExportStatusInfo,
    FormSchema,
    InvoiceExportStatusResponse,
    InvoiceMetadata,
    InvoicePackage,
    InvoiceStatusInfo,
    PackagePart,
    PartUploadRequest,
    SessionInvoiceStatusResponse,
    SessionInvoicesResponse,
    SessionStatusResponse,
    StatusInfo,
    Upo,
    UpoPage,
)
from ksef2.renderers import PDFPageSize

from ksef2_cli.app import app
from ksef2_cli.commands.invoices.models import InvoiceWorkflowReceipt
from ksef2_cli.config import RuntimeOverrides
from ksef2_cli.invoice_workflows import EXPORT_METADATA_FILE_NAME


class FakeSession(FakeService):
    def __exit__(self, *args: object) -> None:
        _ = self.close()


class FakeSubmission(FakeService):
    """Stand-in for ``InvoiceSubmission``, the handle ``send_invoice()`` returns."""

    def __init__(self, reference_number: str, **returns: Any) -> None:
        super().__init__(**returns)
        self.reference_number = reference_number


class FakeSearch:
    """Stand-in for ``InvoiceSearchPager``, what ``invoices.search()`` returns.

    Built with the pages a search would walk: ``first_response()`` reports the
    first page as a metadata response, ``responses()`` yields complete pages.
    """

    def __init__(self, *pages: list[Any]) -> None:
        self._pages = [list(page) for page in pages] or [[]]

    def first_response(self) -> dict[str, Any]:
        return {"invoices": list(self._pages[0])}

    def responses(self):
        for page in self._pages:
            yield SimpleNamespace(
                invoices=list(page), has_more=False, is_truncated=False,
                permanent_storage_hwm_date=None,
            )

    def __iter__(self) -> Iterator[Any]:
        return (item for page in self._pages for item in page)


class FakeExportJob(FakeService):
    """Stand-in for ``ExportJob``, the handle ``invoices.export()`` returns."""

    def __init__(self, state: ExportResumeState, **returns: Any) -> None:
        super().__init__(resume_state=state, **returns)
        self.reference_number = state.reference_number


class FakeExported:
    """Stand-in for ``ExportedInvoices``, the result of ``ExportJob.wait()``.

    ``save()`` writes a stub file for each name it was built with, the way extracting a
    real package into ``directory`` would, and ``metadata`` is the invoice list the real
    class reads back from the package's ``_metadata.json``.
    """

    def __init__(self, *names: str, metadata: list[Any] | None = None) -> None:
        self._names = list(names)
        self.metadata = metadata

    def save(self, directory: Path) -> list[Path]:
        target = Path(directory)
        target.mkdir(parents=True, exist_ok=True)
        paths: list[Path] = []
        for name in self._names:
            path = target / name
            path.write_text("<invoice/>", encoding="utf-8")
            paths.append(path)
        return paths


# The resume state validates that its key is Base64 of 32 raw bytes and the IV of 16.
_EXPORT_AES_KEY = base64.b64encode(b"aes-key-32-bytes" * 2).decode("ascii")
_EXPORT_IV = base64.b64encode(b"iv-16-bytes!!!!!").decode("ascii")


def _export_state(reference_number: str = "export-ref") -> ExportResumeState:
    return ExportResumeState(
        reference_number=reference_number, aes_key=_EXPORT_AES_KEY, iv=_EXPORT_IV
    )


def _last_called(service: FakeService, name: str) -> dict[str, Any]:
    """Return the keyword arguments of the most recent call to ``name``."""
    for call_name, _args, kwargs in reversed(service.calls):
        if call_name == name:
            return kwargs
    raise AssertionError(f"{name!r} was not called; calls={service.calls!r}")


def _export_status(
    package: InvoicePackage | None = None,
) -> InvoiceExportStatusResponse:
    return InvoiceExportStatusResponse(
        status=ExportStatusInfo(code=200, description="ready"),
        package=package,
    )


def _invoice_package() -> InvoicePackage:
    return InvoicePackage(
        invoice_count=1,
        size=1,
        parts=[
            PackagePart(
                ordinal_number=1,
                part_name="part-1",
                method="GET",
                url="https://example.invalid/part",
                part_size=1,
                part_hash="hash",
                encrypted_part_size=1,
                encrypted_part_hash="encrypted-hash",
                expiration_date=datetime(2026, 1, 1, tzinfo=UTC),
            )
        ],
        is_truncated=False,
    )


def _invoice_processing_status(
    reference_number: str = "invoice-ref",
    ksef_number: str | None = "ksef-1",
) -> SessionInvoiceStatusResponse:
    return SessionInvoiceStatusResponse(
        ordinal_number=1,
        ksef_number=ksef_number,
        reference_number=reference_number,
        invoice_hash="hash",
        invoicing_date=datetime(2026, 1, 1, tzinfo=UTC),
        status=InvoiceStatusInfo(
            code=200 if ksef_number else 150,
            description="ready" if ksef_number else "processing",
        ),
    )


def _batch_state_with_upload() -> BatchSessionResumeState:
    """Batch resume state as a live session reports it, presigned upload included."""

    return BatchSessionResumeState.from_encoded(
        reference_number="batch-ref",
        aes_key=b"aes-key-32-bytes" * 2,
        iv=b"iv-16-bytes!!!!!",
        form_code=FormSchema.FA3,
        part_upload_requests=[
            PartUploadRequest(
                ordinal_number=1,
                method="PUT",
                url="https://example.invalid/part/1",
                headers={"Content-Type": "application/octet-stream"},
            )
        ],
    )


def _batch_processing_status() -> SessionStatusResponse:
    return SessionStatusResponse(
        status=StatusInfo(code=200, description="completed"),
        date_created=datetime(2026, 1, 1, tzinfo=UTC),
        date_updated=datetime(2026, 1, 1, tzinfo=UTC),
        invoice_count=2,
        successful_invoice_count=2,
        failed_invoice_count=0,
        upo=Upo(
            pages=[
                UpoPage(
                    reference_number="upo-page-1",
                    download_url="https://example.invalid/upo/1",
                    download_url_expiration_date=datetime(2026, 1, 2, tzinfo=UTC),
                )
            ]
        ),
    )


def test_invoices_metadata_query_and_all(runner) -> None:
    service = FakeService(
        search=lambda **kwargs: FakeSearch(
            [{"ksef_number": "ksef-1"}], [{"ksef_number": "ksef-2"}]
        )
    )
    runtime = fake_runtime(auth=type("Auth", (), {"invoices": service})())

    result = runner.invoke(
        app,
        cli_args(
            "invoices",
            "metadata",
            "--date-from",
            "2026-01-01T00:00:00Z",
            "--date-to",
            "2026-01-02T00:00:00Z",
            "--currency",
            "PLN",
            "--invoice-type",
            "vat",
            "--form",
            "FA3",
            "--attachment",
            "yes",
            "--self-invoicing",
            "no",
        ),
        obj=runtime,
    )

    assert payload(result) == {"invoices": [{"ksef_number": "ksef-1"}]}
    assert service.called("search")["filters"].has_attachment is True
    assert service.called("search")["params"].page_size == 10

    result = runner.invoke(
        app,
        cli_args(
            "invoices",
            "metadata",
            "--date-from",
            "2026-01-01T00:00:00Z",
            "--date-to",
            "2026-01-02T00:00:00Z",
            "--all",
        ),
        obj=runtime,
    )
    assert payload(result) == {
        "invoices": [{"ksef_number": "ksef-1"}, {"ksef_number": "ksef-2"}],
        "has_more": False, "is_truncated": False,
        "permanent_storage_hwm_date": None, "page_count": 2,
    }


def test_invoices_metadata_parses_date_options(runner) -> None:
    service = FakeService(search=lambda **kwargs: FakeSearch([]))
    runtime = fake_runtime(auth=type("Auth", (), {"invoices": service})())

    result = runner.invoke(
        app,
        cli_args(
            "invoices",
            "metadata",
            "--date-from",
            "2026-01-01T00:00:00Z",
            "--date-to",
            "2026-01-02T00:00:00Z",
        ),
        obj=runtime,
    )

    assert payload(result) == {"invoices": []}
    filters = service.called("search")["filters"]
    assert filters.date_from == datetime(2026, 1, 1, tzinfo=UTC)
    assert filters.date_to == datetime(2026, 1, 2, tzinfo=UTC)

    bad_date = runner.invoke(
        app,
        cli_args("invoices", "metadata", "--date-from", "yesterday"),
        obj=runtime,
    )
    assert bad_date.exit_code == 2
    assert "must be a date like" in bad_date.output

    reversed_range = runner.invoke(
        app,
        cli_args(
            "invoices",
            "metadata",
            "--date-from",
            "2026-02-01",
            "--date-to",
            "2026-01-01",
        ),
        obj=runtime,
    )
    assert reversed_range.exit_code == 2
    assert "date_from must be less than or equal to date_to" in plain(
        reversed_range.output
    )


def test_invoices_metadata_polish_dates_match_iso_filters(runner) -> None:
    service = FakeService(search=lambda **kwargs: FakeSearch([]))
    runtime = fake_runtime(auth=type("Auth", (), {"invoices": service})())

    for date_from, date_to in (
        ("01.10.2026", "15.10.2026"),
        ("2026-10-01", "2026-10-15"),
    ):
        result = runner.invoke(
            app,
            cli_args(
                "invoices", "metadata", "--date-from", date_from, "--date-to", date_to
            ),
            obj=runtime,
        )
        assert payload(result) == {"invoices": []}

    filters = [kwargs["filters"] for name, _, kwargs in service.calls if name == "search"]
    assert len(filters) == 2
    assert filters[0].date_from == filters[1].date_from
    assert filters[0].date_to == filters[1].date_to


def test_invoice_download_writes_xml(runner, tmp_path) -> None:
    def download(
        *,
        ksef_number: str,
        timeout: float | None = None,
        poll_interval: float = 2.0,
    ) -> bytes:
        return b"<waited/>" if timeout is not None else b"<invoice/>"

    service = FakeService(download=download)
    runtime = fake_runtime(auth=type("Auth", (), {"invoices": service})())

    target = tmp_path / "invoice.xml"
    result = runner.invoke(
        app,
        cli_args(
            "invoices", "download", "--ksef-number", "ksef/1", "--out", str(target)
        ),
        obj=runtime,
    )

    assert payload(result) == {"path": str(target), "bytes": len(b"<invoice/>")}
    assert target.read_bytes() == b"<invoice/>"

    result = runner.invoke(
        app,
        cli_args(
            "invoices",
            "download",
            "--ksef-number",
            "ksef/2",
            "--out",
            str(target),
            "--wait",
        ),
        obj=runtime,
    )
    assert payload(result)["bytes"] == len(b"<waited/>")
    # One call serves both modes: `download()` polls when it is given a timeout.
    downloads = [kwargs for name, _, kwargs in service.calls if name == "download"]
    assert downloads[0] == {
        "ksef_number": "ksef/1",
        "timeout": None,
        "poll_interval": 2.0,
    }
    assert downloads[1] == {
        "ksef_number": "ksef/2",
        "timeout": 120.0,
        "poll_interval": 2.0,
    }


def test_invoices_send_online_wait_downloads_upo_and_writes_receipt(
    runner, tmp_path
) -> None:
    submission = FakeSubmission(
        "invoice-ref", wait=_invoice_processing_status(), download_upo=b"<upo/>"
    )
    session = FakeSession(
        resume_state=online_state(),
        send_invoice=lambda **kwargs: submission,
        close=None,
    )
    runtime = fake_runtime(auth=FakeService(online_session=session))
    invoice = tmp_path / "invoice.xml"
    invoice.write_text("<invoice/>", encoding="utf-8")
    receipt_file = tmp_path / "receipt.json"
    upo_dir = tmp_path / "upos"

    result = runner.invoke(
        app,
        [
            "--no-config",
            "invoices",
            "send",
            str(invoice),
            "--wait",
            "--upo-dir",
            str(upo_dir),
            "--receipt",
            str(receipt_file),
        ],
        obj=runtime,
    )

    assert result.exit_code == 0, result.output
    assert f"accepted  {invoice}  ksef=ksef-1  invoice_ref=invoice-ref" in result.output
    upo_file = upo_dir / "invoice-upo.xml"
    assert upo_file.read_bytes() == b"<upo/>"
    # The submission handle, not the session, waits for the invoice and fetches its UPO.
    assert submission.called("wait")["timeout"] == 120.0
    assert [name for name, _, _ in submission.calls] == ["wait", "download_upo"]
    session_calls = [name for name, _, _ in session.calls]
    assert session_calls[:2] == ["send_invoice", "resume_state"]
    receipt = InvoiceWorkflowReceipt.model_validate_json(
        receipt_file.read_text(encoding="utf-8")
    )
    assert receipt.mode == "online"
    assert receipt.online is not None
    assert receipt.online.invoice_reference == "invoice-ref"
    assert receipt.online.status is not None
    assert receipt.online.status.ksef_number == "ksef-1"
    assert receipt_file.stat().st_mode & 0o777 == 0o600


def test_invoices_send_online_directory_expansion(runner, tmp_path) -> None:
    root_invoice = tmp_path / "a.xml"
    root_invoice.write_text("<a/>", encoding="utf-8")
    nested_dir = tmp_path / "nested"
    nested_dir.mkdir()
    nested_invoice = nested_dir / "b.xml"
    nested_invoice.write_text("<b/>", encoding="utf-8")

    first_session = FakeSession(
        resume_state=online_state(),
        send_invoice=lambda **kwargs: FakeSubmission("invoice-ref"),
        close=None,
    )
    first_runtime = fake_runtime(auth=FakeService(online_session=first_session))
    first = payload(
        runner.invoke(
            app,
            cli_args("invoices", "send", str(tmp_path)),
            obj=first_runtime,
        )
    )
    assert first["submitted"] == 1
    assert first_session.called("send_invoice")["invoice_xml"] == b"<a/>"

    second_session = FakeSession(
        resume_state=online_state(),
        send_invoice=lambda **kwargs: FakeSubmission("invoice-ref"),
        close=None,
    )
    second_runtime = fake_runtime(auth=FakeService(online_session=second_session))
    second = payload(
        runner.invoke(
            app,
            cli_args("invoices", "send", str(tmp_path), "--recursive"),
            obj=second_runtime,
        )
    )
    assert second["submitted"] == 2
    send_calls = [call for call in second_session.calls if call[0] == "send_invoice"]
    assert len(send_calls) == 2


def test_invoices_send_online_directory_without_xml_errors(runner, tmp_path) -> None:
    runtime = fake_runtime(auth=FakeService())
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()

    result = runner.invoke(
        app,
        cli_args("invoices", "send", str(empty_dir)),
        obj=runtime,
    )

    assert result.exit_code == 2
    assert "No XML invoice files found" in result.output


def test_invoices_send_online_multiple_files_require_receipt_dir(
    runner, tmp_path
) -> None:
    first = tmp_path / "a.xml"
    second = tmp_path / "b.xml"
    first.write_text("<a/>", encoding="utf-8")
    second.write_text("<b/>", encoding="utf-8")
    receipt_file = tmp_path / "receipt.json"
    runtime = fake_runtime(auth=FakeService())

    result = runner.invoke(
        app,
        cli_args(
            "invoices",
            "send",
            str(first),
            str(second),
            "--receipt",
            str(receipt_file),
        ),
        obj=runtime,
    )

    assert result.exit_code == 2
    assert (
        "Use --receipt-dir when writing receipts for multiple files." in result.output
    )


def test_invoices_send_online_continues_after_invoice_failure(runner, tmp_path) -> None:
    first = tmp_path / "a.xml"
    second = tmp_path / "b.xml"
    first.write_text("<a/>", encoding="utf-8")
    second.write_text("<b/>", encoding="utf-8")

    def send_invoice(*, invoice_xml: bytes) -> FakeSubmission:
        if invoice_xml == b"<b/>":
            raise ValueError("rejected")
        return FakeSubmission("invoice-ref")

    session = FakeSession(
        resume_state=online_state(),
        send_invoice=send_invoice,
        close=None,
    )
    runtime = fake_runtime(auth=FakeService(online_session=session))

    result = runner.invoke(
        app,
        cli_args("invoices", "send", str(first), str(second)),
        obj=runtime,
    )

    assert result.exit_code == 1
    data = json.loads(result.output)
    assert data["submitted"] == 2
    assert data["succeeded"] == 1
    assert data["failed"] == 1
    assert [item["status"] for item in data["items"]] == ["submitted", "failed"]
    assert data["items"][1]["error"] == "rejected"


@pytest.mark.parametrize("raises", [False, True])
@pytest.mark.parametrize("receipt_option", ["--receipt", "--receipt-dir"])
def test_invoices_send_online_wait_marks_failed_status_from_session(
    runner, tmp_path, raises, receipt_option
) -> None:
    invoice = tmp_path / "invoice.xml"
    _ = invoice.write_text("<invoice/>", encoding="utf-8")
    rejected = SessionInvoiceStatusResponse(
        ordinal_number=1,
        reference_number="invoice-ref",
        invoice_hash="hash",
        invoicing_date=datetime(2026, 1, 1, tzinfo=UTC),
        status=InvoiceStatusInfo(code=400, description="rejected"),
    )
    submission = FakeSubmission(
        "invoice-ref",
        wait=KSeFInvoiceRejectedError("invoice-ref", rejected) if raises else rejected,
    )
    session = FakeSession(
        resume_state=online_state(),
        send_invoice=lambda **kwargs: submission,
        close=None,
    )
    if receipt_option == "--receipt":
        receipt_target = tmp_path / "receipt.json"
        receipt_file = receipt_target
    else:
        receipt_target = tmp_path
        receipt_file = tmp_path / "invoice-receipt.json"
    runtime = fake_runtime(auth=FakeService(online_session=session))

    result = runner.invoke(
        app,
        cli_args(
            "invoices", "send", str(invoice), "--wait",
            receipt_option, str(receipt_target),
            "--upo-dir", str(tmp_path / "upos"),
        ),
        obj=runtime,
    )

    assert result.exit_code == 1
    data = json.loads(result.output)
    assert data["failed"] == 1
    assert data["items"][0]["status"] == "failed"
    assert data["items"][0]["error"] == "rejected"

    assert data["receipt_files"] == [str(receipt_file)]
    receipt = InvoiceWorkflowReceipt.model_validate_json(receipt_file.read_text())
    assert receipt.online is not None
    assert receipt.online.invoice_reference == "invoice-ref"
    assert receipt.online.status == rejected
    assert receipt_file.stat().st_mode & 0o777 == 0o600
    assert [name for name, _, _ in submission.calls] == ["wait"]


def test_invoices_status_plain_text_fits_the_declared_width(runner, tmp_path) -> None:
    # The record behind `invoices status` is identifiers and a receipt path, and none
    # of them can be shortened to fit a terminal.
    receipts = tmp_path / "receipts" / "with-a-name-long-enough-to-overflow-a-line"
    receipts.mkdir(parents=True)
    receipt_file = receipts / "invoice-workflow-receipt.json"
    invoice = tmp_path / "invoice.xml"
    invoice.write_text("<invoice/>", encoding="utf-8")
    reference = "5926ad107b01e605f9ebb4cbca0080fea655114b8ca67168543dc7ca3bb2eeee"
    _ = receipt_file.write_text(
        json.dumps(
            {
                "version": 1,
                "mode": "online",
                "submitted_files": [str(invoice)],
                "online": {
                    "file": str(invoice),
                    "session_state": online_state().to_dict(mode="json"),
                    "invoice_reference": reference,
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    submission = FakeSubmission(
        reference,
        get_status=_invoice_processing_status(
            reference_number=reference, ksef_number="ksef-612701234567-2411BF0003"
        ),
    )
    session = FakeSession(
        submission=lambda **kwargs: submission,
        close=KSeFSessionError("status must not close the resumed session"),
    )
    runtime = fake_runtime(auth=FakeService(online_session=session))

    result = runner.invoke(
        app,
        ["--no-config", "invoices", "status", "--receipt", str(receipt_file)],
        obj=runtime,
        env={"COLUMNS": "80", "NO_COLOR": "1", "FORCE_COLOR": None},
    )

    assert result.exit_code == 0, result.output
    assert max(cell_len(line) for line in result.output.splitlines()) <= 80
    # The identifiers arrive whole, spread over the lines the width allowed.
    assert reference in "".join(result.output.split())
    assert "ksef-612701234567-2411BF0003" in "".join(result.output.split())


@pytest.mark.parametrize("wait_for_upo", [False, True])
@pytest.mark.parametrize("wait_for_status", [False, True])
def test_invoices_status_and_upo_from_online_receipt(
    runner, tmp_path, wait_for_upo, wait_for_status
) -> None:
    invoice = tmp_path / "invoice.xml"
    invoice.write_text("<invoice/>", encoding="utf-8")
    receipt_file = tmp_path / "receipt.json"
    send_session = FakeSession(
        resume_state=online_state(),
        send_invoice=lambda **kwargs: FakeSubmission("invoice-ref"),
        close=None,
    )
    send_runtime = fake_runtime(auth=FakeService(online_session=send_session))
    assert (
        runner.invoke(
            app,
            cli_args(
                "invoices",
                "send",
                str(invoice),
                "--receipt",
                str(receipt_file),
            ),
            obj=send_runtime,
        ).exit_code
        == 0
    )

    resume_submission = FakeSubmission(
        "invoice-ref",
        wait=_invoice_processing_status(),
        get_status=_invoice_processing_status(),
        download_upo=b"<upo/>",
    )
    resume_session = FakeSession(
        submission=lambda **kwargs: resume_submission,
        close=KSeFSessionError("resumed session must not be closed"),
    )
    invoice_sessions = FakeService(download_upo=b"<upo/>")
    resume_runtime = fake_runtime(
        auth=SimpleNamespace(
            online_session=lambda **kwargs: resume_session,
            invoice_sessions=invoice_sessions,
        )
    )
    status_args = cli_args("invoices", "status", "--receipt", str(receipt_file))
    if wait_for_status:
        status_args.append("--wait")
    status = payload(runner.invoke(app, status_args, obj=resume_runtime))
    assert status["status"] == "accepted"
    assert status["ksef_number"] == "ksef-1"

    out = tmp_path / "upo.xml"
    upo_args = cli_args(
        "invoices", "upo", "--receipt", str(receipt_file), "--out", str(out)
    )
    if wait_for_upo:
        upo_args.append("--wait")
    upo = payload(runner.invoke(app, upo_args, obj=resume_runtime))
    assert upo["upo_files"] == [{"path": str(out), "bytes": len(b"<upo/>")}]
    assert out.read_bytes() == b"<upo/>"

    assert invoice_sessions.called("download_upo") == {
        "session_reference_number": "online-ref",
        "invoice_reference_number": "invoice-ref",
    }
    assert all(name != "close" for name, _, _ in resume_session.calls)
    assert all(name != "download_upo" for name, _, _ in resume_submission.calls)
    assert [name for name, _, _ in resume_session.calls] == (
        ["submission", "submission"] if wait_for_upo else ["submission"]
    )


@pytest.mark.parametrize("raises", [False, True])
@pytest.mark.parametrize("with_upo", [False, True])
def test_invoices_send_batch_rejection_writes_receipt(
    runner, tmp_path, raises, with_upo
) -> None:
    invoice = tmp_path / "invoice.xml"
    _ = invoice.write_text("<invoice/>")
    rejected = SessionStatusResponse(
        status=StatusInfo(code=400, description="batch rejected"),
        date_created=datetime(2026, 1, 1, tzinfo=UTC),
        date_updated=datetime(2026, 1, 1, tzinfo=UTC),
        invoice_count=1,
        successful_invoice_count=0,
        failed_invoice_count=1,
    )
    session = FakeService(
        resume_state=batch_state(),
        wait=KSeFSessionError("batch rejected") if raises else rejected,
        get_status=rejected,
    )
    runtime = fake_runtime(auth=SimpleNamespace(batch=FakeService(submit=session)))
    receipt_file = tmp_path / "receipt.json"
    args = cli_args(
        "invoices", "send", str(invoice), "--mode", "batch", "--wait",
        "--receipt", str(receipt_file),
    )
    if with_upo:
        args.extend(["--upo-dir", str(tmp_path / "upos")])
    result = runner.invoke(app, args, obj=runtime)
    assert result.exit_code == 1
    data = json.loads(result.output)
    assert data["batch"]["status"] == "failed"
    assert data["failed"] == 1
    assert data["succeeded"] == 0
    assert data["receipt_files"] == [str(receipt_file)]
    assert data["upo_files"] == []
    receipt = InvoiceWorkflowReceipt.model_validate_json(receipt_file.read_text())
    assert receipt.batch is not None
    assert receipt.batch.session_reference == "batch-ref"
    assert receipt.batch.status is not None
    assert receipt.batch.status.code == 400
    assert receipt.batch.status.description == "batch rejected"
    assert receipt_file.stat().st_mode & 0o777 == 0o600
    assert [name for name, _, _ in session.calls] == (
        ["resume_state", "wait", "get_status"] if raises else ["resume_state", "wait"]
    )


def test_invoices_send_batch_wait_downloads_upo_and_writes_receipt(
    runner, tmp_path
) -> None:
    first = tmp_path / "a.xml"
    second = tmp_path / "b.xml"
    first.write_text("<a/>", encoding="utf-8")
    second.write_text("<b/>", encoding="utf-8")
    state = _batch_state_with_upload()
    submitted = FakeService(
        resume_state=state, wait=_batch_processing_status(),
        list_invoices=SessionInvoicesResponse(invoices=[]),
    )
    upo_session = FakeService(download_upo=b"<batch-upo/>")
    runtime = fake_runtime(
        auth=SimpleNamespace(
            batch=FakeService(submit=submitted),
            invoice_sessions=upo_session,
        )
    )
    receipt_file = tmp_path / "batch-receipt.json"
    upo_dir = tmp_path / "upos"

    sent = payload(
        runner.invoke(
            app,
            cli_args(
                "invoices",
                "send",
                str(first),
                str(second),
                "--mode",
                "batch",
                "--wait",
                "--upo-dir",
                str(upo_dir),
                "--receipt",
                str(receipt_file),
            ),
            obj=runtime,
        )
    )

    upo_file = upo_dir / "batch-batch-ref-upo-1.xml"
    assert sent["batch"]["status"] == "completed"
    assert sent["batch"]["session_reference"] == "batch-ref"
    assert sent["batch"]["upo_files"] == [str(upo_file)]
    assert upo_file.read_bytes() == b"<batch-upo/>"
    assert submitted.called("wait")["poll_interval"] == 2.0
    # One download pass covers every UPO page the session status reported.
    assert [name for name, _, _ in upo_session.calls] == ["download_upo"]
    receipt = InvoiceWorkflowReceipt.model_validate_json(
        receipt_file.read_text(encoding="utf-8")
    )
    assert receipt.batch is not None
    assert receipt.batch.session_reference == "batch-ref"

    assert receipt.batch.session_state == state
    saved_state = json.loads(receipt_file.read_text())["batch"]["session_state"]
    assert BatchSessionResumeState.from_json(json.dumps(saved_state)) == state
    assert saved_state["part_upload_requests"][0]["url"] == "https://example.invalid/part/1"
    assert state.aes_key.get_secret_value() not in json.dumps(sent)

    assert upo_session.calls == [
        ("download_upo", ("batch-ref",), {"upo_reference_number": "upo-page-1"})
    ]

    # A failed reference download must fail the command.
    failed_download = FakeService(download_upo=ValueError("Cannot download upo-page-1"))
    failed_download_runtime = fake_runtime(
        auth=SimpleNamespace(
            batch=FakeService(
                submit=FakeService(
                    resume_state=batch_state(), wait=_batch_processing_status(),
                    list_invoices=SessionInvoicesResponse(invoices=[]),
                )
            ),
            invoice_sessions=failed_download,
        )
    )
    failed = runner.invoke(
        app,
        cli_args(
            "invoices",
            "send",
            str(first),
            str(second),
            "--mode",
            "batch",
            "--wait",
            "--upo-dir",
            str(tmp_path / "mismatch"),
        ),
        obj=failed_download_runtime,
    )
    # The SDK reports the refused download as a ValueError, which the CLI maps to a
    # usage error and its exit code.
    assert failed.exit_code == 2, failed.output
    assert "upo-page-1" in failed.output


def test_invoices_status_and_upo_from_batch_receipt(runner, tmp_path) -> None:
    invoice = tmp_path / "invoice.xml"
    invoice.write_text("<invoice/>", encoding="utf-8")
    receipt_file = tmp_path / "batch-receipt.json"
    submit_runtime = fake_runtime(
        auth=SimpleNamespace(
            batch=FakeService(submit=FakeService(resume_state=batch_state()))
        )
    )
    assert (
        runner.invoke(
            app,
            cli_args(
                "invoices",
                "send",
                str(invoice),
                "--mode",
                "batch",
                "--receipt",
                str(receipt_file),
            ),
            obj=submit_runtime,
        ).exit_code
        == 0
    )

    batch = FakeService(
        wait_for_completion=_batch_processing_status(),
        get_status=_batch_processing_status(),
    )
    invoice_sessions = FakeService(download_upo=b"<batch-upo/>")
    runtime = fake_runtime(
        auth=SimpleNamespace(batch=batch, invoice_sessions=invoice_sessions)
    )
    status = payload(
        runner.invoke(
            app,
            cli_args("invoices", "status", "--receipt", str(receipt_file), "--wait"),
            obj=runtime,
        )
    )
    assert status["status"] == "completed"
    assert status["invoice_count"] == 2
    assert batch.calls == [
        ("wait_for_completion", (), {
            "session": "batch-ref", "timeout": 120.0, "poll_interval": 2.0,
        })
    ]

    upo_dir = tmp_path / "upos"
    upo = payload(
        runner.invoke(
            app,
            cli_args(
                "invoices",
                "upo",
                "--receipt",
                str(receipt_file),
                "--upo-dir",
                str(upo_dir),
            ),
            obj=runtime,
        )
    )
    assert upo["upo_files"][0]["path"] == str(upo_dir / "batch-batch-ref-upo-1.xml")
    assert (upo_dir / "batch-batch-ref-upo-1.xml").read_bytes() == b"<batch-upo/>"
    assert len(batch.calls) == 1  # UPO uses the status cached in the receipt.
    assert invoice_sessions.calls == [
        ("download_upo", ("batch-ref",), {"upo_reference_number": "upo-page-1"})
    ]

    # `--wait` polls for a fresh status instead of trusting the cached one.
    waited_dir = tmp_path / "waited-upos"
    waited = payload(
        runner.invoke(
            app,
            cli_args(
                "invoices",
                "upo",
                "--receipt",
                str(receipt_file),
                "--upo-dir",
                str(waited_dir),
                "--wait",
            ),
            obj=runtime,
        )
    )
    assert waited["upo_files"][0]["path"] == str(
        waited_dir / "batch-batch-ref-upo-1.xml"
    )
    assert len(batch.calls) == 2
    assert batch.calls[-1][0] == "wait_for_completion"


def test_invoices_status_and_upo_support_legacy_batch_receipt(
    runner, tmp_path
) -> None:
    """Old receipts still support reference reads without reopening a session."""

    invoice = tmp_path / "invoice.xml"
    invoice.write_text("<invoice/>", encoding="utf-8")
    receipt_file = tmp_path / "batch-receipt.json"
    sent = payload(
        runner.invoke(
            app,
            cli_args(
                "invoices",
                "send",
                str(invoice),
                "--mode",
                "batch",
                "--receipt",
                str(receipt_file),
            ),
            obj=fake_runtime(
                auth=SimpleNamespace(
                    batch=FakeService(submit=FakeService(resume_state=batch_state()))
                )
            ),
        )
    )
    assert sent["batch"]["session_reference"] == "batch-ref"

    # Rewrite it the way older CLI versions wrote it: the reference number only.
    legacy = json.loads(receipt_file.read_text(encoding="utf-8"))
    del legacy["batch"]["session_state"]
    receipt_file.write_text(json.dumps(legacy), encoding="utf-8")

    batch = FakeService(get_status=_batch_processing_status())
    invoice_sessions = FakeService(download_upo=b"<legacy-upo/>")
    runtime = fake_runtime(auth=SimpleNamespace(
        batch=batch, invoice_sessions=invoice_sessions,
    ))

    status = runner.invoke(
        app, cli_args("invoices", "status", "--receipt", str(receipt_file)), obj=runtime
    )
    upo = runner.invoke(
        app,
        cli_args(
            "invoices",
            "upo",
            "--receipt",
            str(receipt_file),
            "--upo-dir",
            str(tmp_path / "upos"),
        ),
        obj=runtime,
    )

    assert status.exit_code == 0, status.output
    assert upo.exit_code == 0, upo.output
    assert (tmp_path / "upos" / "batch-batch-ref-upo-1.xml").read_bytes() == b"<legacy-upo/>"
    assert batch.called("get_status")["session"] == "batch-ref"


def test_invoice_export_status_fetch_and_download(runner, tmp_path) -> None:
    state = _export_state()
    package = _invoice_package()
    # One job handle per command run, so each command's use of it stays visible.
    jobs: list[FakeExportJob] = []

    def export(**_kwargs: Any) -> FakeExportJob:
        job = FakeExportJob(
            state,
            get_status=_export_status(package),
            wait=FakeExported("out.xml"),
        )
        jobs.append(job)
        return job

    service = FakeService(export=export)
    runtime = fake_runtime(auth=type("Auth", (), {"invoices": service})())

    handle_file = tmp_path / "handle.json"
    result = runner.invoke(
        app,
        cli_args(
            "invoices",
            "export",
            "--date-from",
            "2026-01-01T00:00:00Z",
            "--date-to",
            "2026-01-02T00:00:00Z",
            "--handle-file",
            str(handle_file),
        ),
        obj=runtime,
    )
    data = payload(result)
    assert data["state"] == {
        "format_version": "1",
        "reference_number": "export-ref",
        "aes_key": "**********",
        "iv": "**********",
    }
    assert data["handle_file"] == str(handle_file)
    assert json.loads(handle_file.read_text(encoding="utf-8")) == {
        "format_version": "1",
        "reference_number": "export-ref",
        "aes_key": _EXPORT_AES_KEY,
        "iv": _EXPORT_IV,
    }
    # The handle file holds the decryption key, so it must not be world-readable.
    assert (handle_file.stat().st_mode & 0o777) == 0o600
    assert _last_called(service, "export")["filters"].date_from is not None
    assert [name for name, _, _ in jobs[0].calls] == ["resume_state"]

    status_body = payload(
        runner.invoke(
            app,
            cli_args("invoices", "export-status", "--reference", "export-ref"),
            obj=runtime,
        )
    )["package"]
    assert status_body == {
        "compression_type": "zip",
        "invoice_count": 1,
        "size": 1,
        "parts": [
            {
                "ordinal_number": 1,
                "part_name": "part-1",
                "method": "GET",
                "part_size": 1,
                "part_hash": "hash",
                "encrypted_part_size": 1,
                "encrypted_part_hash": "encrypted-hash",
                "expiration_date": "2026-01-01T00:00:00Z",
            }
        ],
        "is_truncated": False,
        "last_issue_date": None,
        "last_invoicing_date": None,
        "last_permanent_storage_date": None,
        "permanent_storage_hwm_date": None,
    }
    # Presigned part URLs are capability material and stay out of command output;
    # ``invoices export-fetch``/``invoices export-download`` download them instead.
    assert "url" not in status_body["parts"][0]
    # Status needs only the reference number, so this resumes the job without keys.
    assert _last_called(service, "export")["state"].reference_number == "export-ref"
    assert [name for name, _, _ in jobs[1].calls] == ["get_status"]

    fetch_dir = tmp_path / "fetch"
    result = runner.invoke(
        app,
        cli_args(
            "invoices",
            "export-fetch",
            "--handle-file",
            str(handle_file),
            "--out-dir",
            str(fetch_dir),
        ),
        obj=runtime,
    )
    assert payload(result) == {
        "reference_number": "export-ref",
        "paths": [str(fetch_dir / "out.xml")],
    }
    # The saved handle carries the real key material back into the job.
    assert _last_called(service, "export")["state"] == state
    assert [name for name, _, _ in jobs[2].calls] == ["get_status", "wait"]

    wait_dir = tmp_path / "wait"
    result = runner.invoke(
        app,
        cli_args(
            "invoices",
            "export-fetch",
            "--handle-file",
            str(handle_file),
            "--out-dir",
            str(wait_dir),
            "--wait",
        ),
        obj=runtime,
    )
    assert payload(result)["paths"] == [str(wait_dir / "out.xml")]
    assert jobs[3].called("wait")["timeout"] == 120.0
    # With --wait the job polls on its own; no separate status check comes first.
    assert [name for name, _, _ in jobs[3].calls] == ["wait"]

    download_dir = tmp_path / "download"
    download_handle = tmp_path / "download-handle.json"
    result = runner.invoke(
        app,
        cli_args(
            "invoices",
            "export-download",
            "--date-from",
            "2026-01-01T00:00:00Z",
            "--date-to",
            "2026-01-02T00:00:00Z",
            "--out-dir",
            str(download_dir),
            "--handle-file",
            str(download_handle),
        ),
        obj=runtime,
    )
    assert payload(result) == {
        "reference_number": "export-ref",
        "handle_file": str(download_handle),
        "paths": [str(download_dir / "out.xml")],
    }
    assert ExportResumeState.from_json(download_handle.read_text(encoding="utf-8")) == state
    assert (download_handle.stat().st_mode & 0o777) == 0o600
    assert _EXPORT_AES_KEY not in result.output
    assert _EXPORT_IV not in result.output
    assert _last_called(service, "export")["filters"] is not None
    assert jobs[4].called("wait")["poll_interval"] == 2.0


# The filters `invoices metadata` accepts; export commands send the same InvoicesFilter.
_INVOICE_FILTER_ARGS = (
    "--date-to",
    "2026-01-31T00:00:00Z",
    "--currency",
    "PLN",
    "--currency",
    "EUR",
    "--invoice-type",
    "vat",
    "--invoice-type",
    "kor",
    "--seller-nip",
    "5261040828",
    "--buyer-nip",
    "5261040555",
    "--invoice-number",
    "FA/1/2026",
    "--ksef-number",
    "5261040828-20260101-ABCDEF123456-AB",
    "--amount-min",
    "10",
    "--amount-max",
    "100",
    "--form",
    "FA3",
    "--invoicing-mode",
    "offline",
    "--attachment",
    "yes",
    "--self-invoicing",
    "no",
    "--restrict-hwm",
)


def test_invoices_metadata_permanent_storage_high_water_mark(runner) -> None:
    service = FakeService(search=lambda **kwargs: FakeSearch([]))
    runtime = fake_runtime(auth=type("Auth", (), {"invoices": service})())

    unrestricted = runner.invoke(
        app,
        cli_args(
            "invoices",
            "metadata",
            "--date-from",
            "2026-01-01T00:00:00Z",
            "--date-to",
            "2026-01-02T00:00:00Z",
        ),
        obj=runtime,
    )
    assert payload(unrestricted) == {"invoices": []}
    # KSeF does not restrict without this flag and false asks it not to, so an unset
    # flag leaves the field out of the filter instead of sending false.
    unrestricted_filters = _last_called(service, "search")["filters"]
    assert unrestricted_filters.restrict_to_permanent_storage_hwm_date is None

    restricted = runner.invoke(
        app,
        cli_args(
            "invoices",
            "metadata",
            "--date-from",
            "2026-01-01T00:00:00Z",
            "--date-to",
            "2026-01-02T00:00:00Z",
            "--restrict-to-permanent-storage-hwm-date",
        ),
        obj=runtime,
    )
    assert payload(restricted) == {"invoices": []}
    restricted_filters = _last_called(service, "search")["filters"]
    assert restricted_filters.restrict_to_permanent_storage_hwm_date is True


def test_invoice_export_sends_metadata_filters(runner, tmp_path) -> None:
    """``invoices export``, ``export-download`` and ``export-pdf`` accept the metadata filters."""
    service = FakeService(
        export=lambda **_kwargs: FakeExportJob(
            _export_state(),
            get_status=_export_status(_invoice_package()),
            wait=FakeExported("out.xml"),
        )
    )
    runtime = fake_runtime(
        auth=type("Auth", (), {"invoices": service})(),
        invoice_pdf_renderer=lambda _path, *, page_size, ksef_number=None: b"%PDF-1.4",
    )

    export = payload(
        runner.invoke(
            app,
            cli_args(
                "invoices",
                "export",
                "--date-from",
                "2026-01-01T00:00:00Z",
                *_INVOICE_FILTER_ARGS,
            ),
            obj=runtime,
        )
    )
    assert export["state"]["reference_number"] == "export-ref"
    export_filters = _last_called(service, "export")["filters"]

    download_dir = tmp_path / "download"
    download = payload(
        runner.invoke(
            app,
            cli_args(
                "invoices",
                "export-download",
                "--date-from",
                "2026-01-01T00:00:00Z",
                *_INVOICE_FILTER_ARGS,
                "--out-dir",
                str(download_dir),
            ),
            obj=runtime,
        )
    )
    assert download["reference_number"] == "export-ref"
    download_filters = _last_called(service, "export")["filters"]

    pdf_dir = tmp_path / "pdfs"
    rendered_pdf = payload(
        runner.invoke(
            app,
            cli_args(
                "invoices",
                "export-pdf",
                "--date-from",
                "2026-01-01T00:00:00Z",
                *_INVOICE_FILTER_ARGS,
                "--out-dir",
                str(tmp_path / "pdf-xml"),
                "--pdf-dir",
                str(pdf_dir),
            ),
            obj=runtime,
        )
    )
    assert rendered_pdf["reference_number"] == "export-ref"
    pdf_filters = _last_called(service, "export")["filters"]

    for filters in (export_filters, download_filters, pdf_filters):
        assert filters.date_to == datetime(2026, 1, 31, tzinfo=UTC)
        assert filters.currency_codes == ["PLN", "EUR"]
        assert filters.invoice_types == ["vat", "kor"]
        assert filters.seller_nip == "5261040828"
        assert filters.buyer_nip == "5261040555"
        assert filters.invoice_number == "FA/1/2026"
        assert filters.ksef_number == "5261040828-20260101-ABCDEF123456-AB"
        assert filters.amount_min == 10.0
        assert filters.amount_max == 100.0
        assert filters.invoice_schema is FormSchema.FA3
        assert filters.invoicing_mode == "offline"
        assert filters.has_attachment is True
        assert filters.is_self_invoicing is False
        assert filters.restrict_to_permanent_storage_hwm_date is True

    # KSeF accepts one buyer identifier at a time, so the other two go separately.
    buyer_ids = [
        ("--buyer-vat-ue", "buyer_vat_ue", "PL1234567890"),
        ("--buyer-other-id", "buyer_other_id", "other-id"),
    ]
    for option, field, value in buyer_ids:
        payload(
            runner.invoke(
                app,
                cli_args(
                    "invoices",
                    "export",
                    "--date-from",
                    "2026-01-01T00:00:00Z",
                    "--date-to",
                    "2026-01-02T00:00:00Z",
                    option,
                    value,
                ),
                obj=runtime,
            )
        )
        filters = _last_called(service, "export")["filters"]
        assert getattr(filters, field) == value


def test_invoice_export_fetch_requires_ready_package(runner, tmp_path) -> None:
    handle_file = tmp_path / "handle.json"
    handle_file.write_text(
        _export_state().to_json(indent=2),
        encoding="utf-8",
    )
    job = FakeExportJob(_export_state(), get_status=_export_status())
    invoices = FakeService(export=job)
    runtime = fake_runtime(auth=type("Auth", (), {"invoices": invoices})())

    result = runner.invoke(
        app,
        cli_args("invoices", "export-fetch", "--handle-file", str(handle_file)),
        obj=runtime,
    )

    assert result.exit_code == 1
    assert "Export package is not ready" in result.output
    assert [name for name, _, _ in job.calls] == ["get_status"]


@pytest.mark.parametrize("json_output", [False, True])
@pytest.mark.parametrize("save_handle", [False, True])
def test_invoice_export_redacts_stdout(runner, tmp_path, json_output, save_handle) -> None:
    state = _export_state()
    invoices = FakeService(export=FakeExportJob(state))
    runtime = fake_runtime(auth=type("Auth", (), {"invoices": invoices})())
    args = ["--no-config"]
    if json_output:
        args.append("--json")
    args.extend([
        "invoices", "export", "--date-from", "2026-01-01T00:00:00Z",
        "--date-to", "2026-01-02T00:00:00Z",
    ])
    handle_file = tmp_path / "handle.json"
    if save_handle:
        handle_file.write_text("old handle", encoding="utf-8")
        handle_file.chmod(0o644)
        args.extend(["--handle-file", str(handle_file)])

    result = runner.invoke(app, args, obj=runtime)

    assert result.exit_code == 0, result.output
    assert _EXPORT_AES_KEY not in result.output
    assert _EXPORT_IV not in result.output
    assert "**********" in result.output
    assert "export-ref" in result.output
    if save_handle:
        assert ExportResumeState.from_json(handle_file.read_text(encoding="utf-8")) == state
        assert (handle_file.stat().st_mode & 0o777) == 0o600


# A KSeF number, as the export manifest and the invoice file name both report it.
_INVOICE_KSEF_ONE = "5261040828-20260101-ABCDEF123456-AB"


def _export_metadata(ksef_numbers: list[str]) -> list[InvoiceMetadata]:
    """The invoice list a package's ``_metadata.json`` reports for these KSeF numbers."""

    return [
        InvoiceMetadata(
            ksef_number=ksef_number,
            invoice_number="FV/1/2026",
            issue_date="2026-01-01",
            invoicing_date=datetime(2026, 1, 1, tzinfo=UTC),
            acquisition_date=datetime(2026, 1, 1, tzinfo=UTC),
            permanent_storage_date=datetime(2026, 1, 1, tzinfo=UTC),
            seller={"nip": "5261040828"},
            buyer={"identifier": {"type": "nip", "value": "5261040555"}},
            net_amount=100.0,
            gross_amount=123.0,
            vat_amount=23.0,
            currency="PLN",
            invoicing_mode="online",
            invoice_type="vat",
            form_code_system="FA (3)",
            form_code_version="1-0E",
            form_code_value="FA",
            is_self_invoicing=False,
            has_attachment=False,
            invoice_hash="hash",
        )
        for ksef_number in ksef_numbers
    ]


def _export_pdf_runtime(
    *, with_fake_renderer: bool = True
) -> tuple[RuntimeOverrides, list[tuple[Path, PDFPageSize | None, str | None]]]:
    """Runtime whose export writes two invoice XML files and whose PDF renderer is a spy.

    The fake reports no manifest metadata, so these invoices render without a KSeF
    number. ``with_fake_renderer=False`` leaves the real exporter path in place so a
    test can exercise the missing-extra error.
    """

    rendered: list[tuple[Path, PDFPageSize | None, str | None]] = []

    def fake_render(
        invoice_xml_path: Path,
        *,
        page_size: PDFPageSize | None,
        ksef_number: str | None = None,
    ) -> bytes:
        rendered.append((invoice_xml_path, page_size, ksef_number))
        return b"%PDF-1.4 " + invoice_xml_path.name.encode()

    service = FakeService(
        export=lambda **_kwargs: FakeExportJob(
            _export_state(),
            get_status=_export_status(_invoice_package()),
            wait=FakeExported("invoice-one.xml", "invoice-two.xml"),
        )
    )
    runtime = fake_runtime(
        auth=type("Auth", (), {"invoices": service})(),
        invoice_pdf_renderer=fake_render if with_fake_renderer else None,
    )
    return runtime, rendered


def test_invoices_export_pdf_renders_each_downloaded_invoice(runner, tmp_path) -> None:
    runtime, rendered = _export_pdf_runtime()
    out_dir = tmp_path / "xml"
    pdf_dir = tmp_path / "pdfs"

    data = payload(
        runner.invoke(
            app,
            cli_args(
                "invoices",
                "export-pdf",
                "--date-from",
                "2026-01-01T00:00:00Z",
                "--date-to",
                "2026-01-02T00:00:00Z",
                "--out-dir",
                str(out_dir),
                "--pdf-dir",
                str(pdf_dir),
                "--paper-size",
                "a3-landscape",
            ),
            obj=runtime,
        )
    )

    assert data["reference_number"] == "export-ref"
    assert [pdf["path"] for pdf in data["pdfs"]] == [
        str(pdf_dir / "invoice-one.pdf"),
        str(pdf_dir / "invoice-two.pdf"),
    ]
    assert data["invoice_xml_files"] == [
        str(out_dir / "invoice-one.xml"),
        str(out_dir / "invoice-two.xml"),
    ]
    assert (pdf_dir / "invoice-one.pdf").read_bytes() == b"%PDF-1.4 invoice-one.xml"
    # The renderer must be handed the decrypted XML, not the encrypted package, and
    # each PDF must be built for the paper size the command asked for.
    assert rendered == [
        (out_dir / "invoice-one.xml", PDFPageSize.A3_LANDSCAPE, None),
        (out_dir / "invoice-two.xml", PDFPageSize.A3_LANDSCAPE, None),
    ]


def test_invoices_export_pdf_defaults_to_the_out_dir(runner, tmp_path) -> None:
    runtime, rendered = _export_pdf_runtime()
    out_dir = tmp_path / "invoices"

    data = payload(
        runner.invoke(
            app,
            cli_args(
                "invoices",
                "export-pdf",
                "--date-from",
                "2026-01-01T00:00:00Z",
                "--date-to",
                "2026-01-02T00:00:00Z",
                "--out-dir",
                str(out_dir),
            ),
            obj=runtime,
        )
    )

    assert [pdf["path"] for pdf in data["pdfs"]] == [
        str(out_dir / "invoice-one.pdf"),
        str(out_dir / "invoice-two.pdf"),
    ]
    assert (out_dir / "invoice-two.pdf").exists()
    # Without --handle-file there is no handle to report, so the key stays out of the JSON.
    assert "handle_file" not in data
    # Without --paper-size the stylesheet decides the paper, so nothing is overridden.
    assert [page_size for _, page_size, _number in rendered] == [None, None]


def test_invoices_export_pdf_renders_invoices_and_passes_their_ksef_numbers(
    runner, tmp_path
) -> None:
    """A package holds `_metadata.json` beside the invoices, and only invoices render.

    The manifest is KSeF's own listing, not invoice XML: feeding it to the renderer used
    to abort the whole command with a Faktura root-element error after the first PDF.
    """

    rendered: list[tuple[Path, str | None]] = []
    service = FakeService(
        export=lambda **_kwargs: FakeExportJob(
            _export_state(),
            get_status=_export_status(_invoice_package()),
            wait=FakeExported(
                f"{_INVOICE_KSEF_ONE}.xml",
                EXPORT_METADATA_FILE_NAME,
                "invoice-without-a-number.xml",
                metadata=_export_metadata([_INVOICE_KSEF_ONE]),
            ),
        )
    )

    def fake_render(
        invoice_xml_path: Path,
        *,
        page_size: PDFPageSize | None,
        ksef_number: str | None = None,
    ) -> bytes:
        rendered.append((invoice_xml_path, ksef_number))
        return b"%PDF-1.4"

    runtime = fake_runtime(
        auth=type("Auth", (), {"invoices": service})(),
        invoice_pdf_renderer=fake_render,
    )
    out_dir = tmp_path / "xml"

    data = payload(
        runner.invoke(
            app,
            cli_args(
                "invoices",
                "export-pdf",
                "--date-from",
                "2026-01-01T00:00:00Z",
                "--date-to",
                "2026-01-02T00:00:00Z",
                "--out-dir",
                str(out_dir),
            ),
            obj=runtime,
        )
    )

    # The manifest is still downloaded and an invoice the manifest does not describe is
    # still rendered, but only the manifest never reaches the renderer.
    assert (out_dir / EXPORT_METADATA_FILE_NAME).exists()
    assert rendered == [
        (out_dir / f"{_INVOICE_KSEF_ONE}.xml", _INVOICE_KSEF_ONE),
        (out_dir / "invoice-without-a-number.xml", None),
    ]
    assert data["invoice_xml_files"] == [
        str(out_dir / f"{_INVOICE_KSEF_ONE}.xml"),
        str(out_dir / "invoice-without-a-number.xml"),
    ]
    assert [pdf["path"] for pdf in data["pdfs"]] == [
        str(out_dir / f"{_INVOICE_KSEF_ONE}.pdf"),
        str(out_dir / "invoice-without-a-number.pdf"),
    ]


def test_invoices_export_pdf_saves_a_readable_handle_privately(runner, tmp_path) -> None:
    """The export handle holds the package key, so it is written 0600 and never printed."""

    runtime, _ = _export_pdf_runtime()
    handle_file = tmp_path / "handle.json"

    result = runner.invoke(
        app,
        cli_args(
            "invoices",
            "export-pdf",
            "--date-from",
            "2026-01-01T00:00:00Z",
            "--date-to",
            "2026-01-02T00:00:00Z",
            "--out-dir",
            str(tmp_path / "out"),
            "--handle-file",
            str(handle_file),
        ),
        obj=runtime,
    )

    data = payload(result)
    assert data["handle_file"] == str(handle_file)
    assert ExportResumeState.from_json(handle_file.read_text(encoding="utf-8")) == (
        _export_state()
    )
    assert (handle_file.stat().st_mode & 0o777) == 0o600
    assert _EXPORT_AES_KEY not in result.output
    assert _EXPORT_IV not in result.output


@pytest.mark.parametrize(
    "missing",
    [
        # The pdf extra is absent.
        ModuleNotFoundError("No module named 'weasyprint'", name="weasyprint"),
        # The extra is installed but WeasyPrint's native Pango/GLib libraries are not.
        OSError("cannot load library 'libgobject-2.0-0': dlopen: no such file"),
    ],
    ids=["no-extra", "no-system-libraries"],
)
def test_invoices_export_pdf_reports_a_missing_pdf_extra(
    runner, tmp_path, monkeypatch, missing
) -> None:
    """Without a working renderer the user needs the install hint, not a bug-report URL."""

    import ksef2_cli.runtime as runtime_module

    def exporter_that_cannot_start(*_args: Any, **_kwargs: Any) -> None:
        raise missing

    monkeypatch.setattr(
        runtime_module, "InvoicePDFExporter", exporter_that_cannot_start
    )
    runtime, _ = _export_pdf_runtime(with_fake_renderer=False)

    result = runner.invoke(
        app,
        cli_args(
            "invoices",
            "export-pdf",
            "--date-from",
            "2026-01-01T00:00:00Z",
            "--date-to",
            "2026-01-02T00:00:00Z",
            "--out-dir",
            str(tmp_path / "out"),
        ),
        obj=runtime,
    )

    assert result.exit_code == 1
    assert "PDF rendering needs dependencies that are not installed" in plain(
        result.output
    )
    assert 'ksef2-cli[pdf]' in plain(result.output)
    assert "issues/new" not in result.output


@pytest.mark.parametrize(
    "option,field",
    [("--attachment", "has_attachment"), ("--self-invoicing", "is_self_invoicing")],
)
@pytest.mark.parametrize(
    "value,expected",
    [
        ("yes", True), ("true", True), ("1", True), ("y", True), ("on", True),
        ("no", False), ("false", False), ("0", False), ("n", False), ("off", False),
    ],
)
def test_metadata_boolean_aliases_reach_search(runner, option, field, value, expected):
    service = FakeService(search=FakeSearch([]))
    result = runner.invoke(
        app,
        cli_args(
            "invoices", "metadata", "--date-from", "2026-10-20",
            "--date-to", "2026-10-21", option, value,
        ),
        obj=fake_runtime(auth=SimpleNamespace(invoices=service)),
    )
    assert payload(result) == {"invoices": []}
    assert getattr(service.called("search")["filters"], field) is expected


@pytest.mark.parametrize(
    "code,message",
    [(150, "UPO is not ready."), (450, "Invoice processing failed:")],
)
def test_invoice_upo_operational_errors_keep_exit_one(runner, tmp_path, code, message):
    receipt_file = tmp_path / "receipt.json"
    receipt_file.write_text("{}", encoding="utf-8")
    status = _invoice_processing_status(ksef_number=None)
    status.status.code = code
    receipt = SimpleNamespace(
        mode="online",
        online=SimpleNamespace(status=status, invoice_reference="invoice-ref"),
    )
    service = FakeService()
    result = runner.invoke(
        app,
        cli_args(
            "invoices", "upo", "--receipt", str(receipt_file),
            "--out", str(tmp_path / "upo.xml"),
        ),
        obj=fake_runtime(auth=service, model_reader=lambda *_: receipt),
    )
    assert result.exit_code == 1
    error = json.loads(result.output)["error"]
    assert error["exit_code"] == 1
    assert message in error["message"]
    assert service.calls == []
