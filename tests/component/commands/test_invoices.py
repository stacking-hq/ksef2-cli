import json
from datetime import UTC, datetime
from pathlib import Path

from conftest import FakeService, cli_args, fake_runtime, payload
from ksef2 import FormSchema
from ksef2.domain.models.batch import BatchSessionState
from ksef2.domain.models.invoices import (
    ExportHandle,
    ExportStatusInfo,
    InvoiceExportStatusResponse,
    InvoicePackage,
    PackagePart,
    SendInvoiceResponse,
)
from ksef2.domain.models.session import (
    InvoiceStatusInfo,
    OnlineSessionState,
    SessionInvoiceStatusResponse,
    SessionStatusResponse,
    StatusInfo,
    Upo,
    UpoPage,
)
from ksef2_cli.app import app
from ksef2_cli.commands.invoices.models import ExportHandleSaved, InvoiceWorkflowReceipt


class FakeSession(FakeService):
    pass


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


def _online_state(reference_number: str = "online-ref") -> OnlineSessionState:
    return OnlineSessionState.from_encoded(
        reference_number=reference_number,
        aes_key=b"aes",
        iv=b"iv",
        access_token="access",
        valid_until=datetime(2026, 1, 1, tzinfo=UTC),
        form_code=FormSchema.FA3,
    )


def _batch_state(reference_number: str = "batch-ref") -> BatchSessionState:
    return BatchSessionState.from_encoded(
        reference_number=reference_number,
        aes_key=b"aes",
        iv=b"iv",
        access_token="access",
        form_code=FormSchema.FA3,
        part_upload_requests=[],
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
        query_metadata={"invoices": [{"ksef_number": "ksef-1"}]},
        all_metadata=lambda **kwargs: [
            {"ksef_number": "ksef-1"},
            {"ksef_number": "ksef-2"},
        ],
    )
    runtime = fake_runtime(auth=type("Auth", (), {"invoices": service})())

    result = runner.invoke(
        app,
        cli_args(
            "invoices",
            "metadata",
            "--date-from",
            "2026-01-01T00:00:00Z",
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
    assert service.called("query_metadata")["filters"].has_attachment is True

    result = runner.invoke(
        app,
        cli_args(
            "invoices", "metadata", "--date-from", "2026-01-01T00:00:00Z", "--all"
        ),
        obj=runtime,
    )
    assert payload(result) == [{"ksef_number": "ksef-1"}, {"ksef_number": "ksef-2"}]


def test_invoice_download_writes_xml(runner, tmp_path) -> None:
    service = FakeService(
        download_invoice=b"<invoice/>",
        wait_for_invoice_download=b"<waited/>",
    )
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
    assert service.called("wait_for_invoice_download")["ksef_number"] == "ksef/2"


def test_invoices_send_online_wait_downloads_upo_and_writes_receipt(
    runner, tmp_path
) -> None:
    session = FakeSession(
        get_state=_online_state(),
        send_invoice_and_wait=_invoice_processing_status(),
        get_invoice_upo_by_reference=b"<upo/>",
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
        get_state=_online_state(),
        send_invoice=SendInvoiceResponse(reference_number="invoice-ref"),
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
        get_state=_online_state(),
        send_invoice=SendInvoiceResponse(reference_number="invoice-ref"),
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

    assert result.exit_code == 1
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

    assert result.exit_code == 1
    assert (
        "Use --receipt-dir when writing receipts for multiple files." in result.output
    )


def test_invoices_send_online_continues_after_invoice_failure(runner, tmp_path) -> None:
    first = tmp_path / "a.xml"
    second = tmp_path / "b.xml"
    first.write_text("<a/>", encoding="utf-8")
    second.write_text("<b/>", encoding="utf-8")

    def send_invoice(*, invoice_xml: bytes) -> SendInvoiceResponse:
        if invoice_xml == b"<b/>":
            raise ValueError("rejected")
        return SendInvoiceResponse(reference_number="invoice-ref")

    session = FakeSession(
        get_state=_online_state(),
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


def test_invoices_send_online_wait_marks_failed_status_from_session(
    runner, tmp_path
) -> None:
    invoice = tmp_path / "invoice.xml"
    invoice.write_text("<invoice/>", encoding="utf-8")
    session = FakeSession(
        get_state=_online_state(),
        send_invoice_and_wait=SessionInvoiceStatusResponse(
            ordinal_number=1,
            ksef_number=None,
            reference_number="invoice-ref",
            invoice_hash="hash",
            invoicing_date=datetime(2026, 1, 1, tzinfo=UTC),
            status=InvoiceStatusInfo(code=400, description="rejected"),
        ),
        close=None,
    )
    runtime = fake_runtime(auth=FakeService(online_session=session))

    result = runner.invoke(
        app,
        cli_args("invoices", "send", str(invoice), "--wait"),
        obj=runtime,
    )

    assert result.exit_code == 1
    data = json.loads(result.output)
    assert data["failed"] == 1
    assert data["items"][0]["status"] == "failed"
    assert data["items"][0]["error"] == "rejected"


def test_invoices_status_and_upo_from_online_receipt(runner, tmp_path) -> None:
    invoice = tmp_path / "invoice.xml"
    invoice.write_text("<invoice/>", encoding="utf-8")
    receipt_file = tmp_path / "receipt.json"
    send_session = FakeSession(
        get_state=_online_state(),
        send_invoice=SendInvoiceResponse(reference_number="invoice-ref"),
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

    resume_session = FakeSession(
        wait_for_invoice_ready=_invoice_processing_status(),
        get_invoice_upo_by_reference=b"<upo/>",
    )
    resume_runtime = fake_runtime(
        auth=FakeService(resume_online_session=resume_session)
    )
    status = payload(
        runner.invoke(
            app,
            cli_args("invoices", "status", "--receipt", str(receipt_file), "--wait"),
            obj=resume_runtime,
        )
    )
    assert status["status"] == "accepted"
    assert status["ksef_number"] == "ksef-1"

    out = tmp_path / "upo.xml"
    upo = payload(
        runner.invoke(
            app,
            cli_args(
                "invoices",
                "upo",
                "--receipt",
                str(receipt_file),
                "--out",
                str(out),
            ),
            obj=resume_runtime,
        )
    )
    assert upo["upo_files"] == [{"path": str(out), "bytes": len(b"<upo/>")}]
    assert out.read_bytes() == b"<upo/>"


def test_invoices_send_batch_wait_downloads_upo_and_writes_receipt(
    runner, tmp_path
) -> None:
    first = tmp_path / "a.xml"
    second = tmp_path / "b.xml"
    first.write_text("<a/>", encoding="utf-8")
    second.write_text("<b/>", encoding="utf-8")
    service = FakeService(
        prepare_batch_from_paths={"prepared": True},
        submit_prepared_batch=_batch_state(),
        wait_for_completion=_batch_processing_status(),
        get_upo=b"<batch-upo/>",
    )
    runtime = fake_runtime(auth=type("Auth", (), {"batch": service})())
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
    receipt = InvoiceWorkflowReceipt.model_validate_json(
        receipt_file.read_text(encoding="utf-8")
    )
    assert receipt.batch is not None
    assert receipt.batch.session_reference == "batch-ref"


def test_invoices_status_and_upo_from_batch_receipt(runner, tmp_path) -> None:
    invoice = tmp_path / "invoice.xml"
    invoice.write_text("<invoice/>", encoding="utf-8")
    receipt_file = tmp_path / "batch-receipt.json"
    submit_service = FakeService(
        prepare_batch_from_paths={"prepared": True},
        submit_prepared_batch=_batch_state(),
    )
    submit_runtime = fake_runtime(auth=type("Auth", (), {"batch": submit_service})())
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

    service = FakeService(
        wait_for_completion=_batch_processing_status(),
        get_upo=b"<batch-upo/>",
    )
    runtime = fake_runtime(auth=type("Auth", (), {"batch": service})())
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
    handle = ExportHandle(reference_number="export-ref", aes_key=b"abc", iv=b"def")
    package = _invoice_package()
    service = FakeService(
        schedule_export=handle,
        get_export_status=_export_status(package),
        wait_for_export_package=package,
        fetch_package=lambda **kwargs: [Path(kwargs["target_directory"]) / "out.xml"],
    )
    runtime = fake_runtime(auth=type("Auth", (), {"invoices": service})())

    handle_file = tmp_path / "handle.json"
    result = runner.invoke(
        app,
        cli_args(
            "invoices",
            "export",
            "--date-from",
            "2026-01-01T00:00:00Z",
            "--handle-file",
            str(handle_file),
        ),
        obj=runtime,
    )
    data = payload(result)
    assert data["reference_number"] == "export-ref"
    assert data["handle_file"] == str(handle_file)
    assert json.loads(handle_file.read_text(encoding="utf-8")) == {
        "reference_number": "export-ref",
        "aes_key": "YWJj",
        "iv": "ZGVm",
    }

    assert payload(
        runner.invoke(
            app,
            cli_args("invoices", "export-status", "--reference", "export-ref"),
            obj=runtime,
        )
    )["package"] == {
        "invoice_count": 1,
        "size": 1,
        "parts": [
            {
                "ordinal_number": 1,
                "part_name": "part-1",
                "method": "GET",
                "url": "https://example.invalid/part",
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
    assert service.called("fetch_package")["package"] == package

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
    assert service.called("wait_for_export_package")["reference_number"] == "export-ref"

    download_dir = tmp_path / "download"
    download_handle = tmp_path / "download-handle.json"
    result = runner.invoke(
        app,
        cli_args(
            "invoices",
            "export-download",
            "--date-from",
            "2026-01-01T00:00:00Z",
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


def test_invoice_export_fetch_requires_ready_package(runner, tmp_path) -> None:
    handle = ExportHandle(reference_number="export-ref", aes_key=b"abc", iv=b"def")
    handle_file = tmp_path / "handle.json"
    handle_file.write_text(
        json.dumps(
            ExportHandleSaved.from_handle(handle).model_dump(
                mode="json",
                by_alias=True,
                exclude_none=True,
            )
        ),
        encoding="utf-8",
    )
    service = FakeService(get_export_status=_export_status())
    runtime = fake_runtime(auth=type("Auth", (), {"invoices": service})())

    result = runner.invoke(
        app,
        cli_args("invoices", "export-fetch", "--handle-file", str(handle_file)),
        obj=runtime,
    )

    assert result.exit_code == 1
    assert "Export package is not ready" in result.output
