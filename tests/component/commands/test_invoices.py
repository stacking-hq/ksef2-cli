import base64
import json
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

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
    ExportResumeState,
    ExportStatusInfo,
    FormSchema,
    InvoiceExportStatusResponse,
    InvoicePackage,
    InvoiceStatusInfo,
    PackagePart,
    SessionInvoiceStatusResponse,
    SessionStatusResponse,
    StatusInfo,
    Upo,
    UpoPage,
)
from ksef2.renderers import PDFPageSize

from ksef2_cli.app import app
from ksef2_cli.commands.invoices.models import InvoiceWorkflowReceipt
from ksef2_cli.config import RuntimeOverrides


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
    first page as a metadata response, iterating yields every item.
    """

    def __init__(self, *pages: list[Any]) -> None:
        self._pages = [list(page) for page in pages] or [[]]

    def first_response(self) -> dict[str, Any]:
        return {"invoices": list(self._pages[0])}

    def __iter__(self) -> Iterator[Any]:
        return (item for page in self._pages for item in page)


class FakeExportJob(FakeService):
    """Stand-in for ``ExportJob``, the handle ``invoices.export()`` returns."""

    def __init__(self, state: ExportResumeState, **returns: Any) -> None:
        super().__init__(resume_state=state, **returns)
        self.reference_number = state.reference_number


class FakeExported:
    """Stand-in for ``ExportedInvoices``, the result of ``ExportJob.wait()``.

    ``save()`` writes a stub invoice XML for each name it was built with, the way
    extracting a real package into ``directory`` would.
    """

    def __init__(self, *names: str) -> None:
        self._names = list(names)

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
    assert payload(result) == [{"ksef_number": "ksef-1"}, {"ksef_number": "ksef-2"}]


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
    assert reversed_range.exit_code == 1
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
    submitted = FakeService(
        resume_state=batch_state(), wait=_batch_processing_status()
    )
    # `submit()` hands back the closed session; UPO pages come from a reopened one.
    upo_session = FakeService(download_upo=[b"<batch-upo/>"])
    runtime = fake_runtime(
        auth=SimpleNamespace(
            batch=FakeService(submit=submitted),
            batch_session=lambda **kwargs: upo_session,
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

    # Pages pair with the status' UPO references by position, so a session that
    # returns a different number of pages fails instead of writing a wrong UPO.
    mismatched = FakeService(download_upo=[b"<a/>", b"<b/>"])
    mismatch_runtime = fake_runtime(
        auth=SimpleNamespace(
            batch=FakeService(
                submit=FakeService(
                    resume_state=batch_state(), wait=_batch_processing_status()
                )
            ),
            batch_session=lambda **kwargs: mismatched,
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
        obj=mismatch_runtime,
    )
    assert failed.exit_code == 1
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

    # Status polling and UPO pages both come from a session client reopened from
    # the receipt's reference number.
    receipt_session = FakeService(
        wait=_batch_processing_status(),
        get_status=_batch_processing_status(),
        download_upo=[b"<batch-upo/>"],
    )
    runtime = fake_runtime(
        auth=SimpleNamespace(batch_session=lambda **kwargs: receipt_session)
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
        invoice_pdf_renderer=lambda _path, *, page_size: b"%PDF-1.4",
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


def _export_pdf_runtime(
    *, with_fake_renderer: bool = True
) -> tuple[RuntimeOverrides, list[tuple[Path, PDFPageSize | None]]]:
    """Runtime whose export writes two invoice XML files and whose PDF renderer is a spy.

    ``with_fake_renderer=False`` leaves the real exporter path in place so a test can
    exercise the missing-extra error.
    """

    rendered: list[tuple[Path, PDFPageSize | None]] = []

    def fake_render(invoice_xml_path: Path, *, page_size: PDFPageSize | None) -> bytes:
        rendered.append((invoice_xml_path, page_size))
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
        (out_dir / "invoice-one.xml", PDFPageSize.A3_LANDSCAPE),
        (out_dir / "invoice-two.xml", PDFPageSize.A3_LANDSCAPE),
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
    assert [page_size for _, page_size in rendered] == [None, None]


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
