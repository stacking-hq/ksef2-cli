from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from conftest import FakeService, cli_args, fake_runtime, payload
from ksef2_cli.app import app
from ksef2_cli.commands import invoices


@dataclass
class ExportHandle:
    reference_number: str
    aes_key: bytes
    iv: bytes


@dataclass
class ExportStatus:
    package: str | None


def test_invoices_metadata_query_and_all(runner) -> None:
    service = FakeService(
        query_metadata={"invoices": [{"ksef_number": "ksef-1"}]},
        all_metadata=lambda **kwargs: [{"ksef_number": "ksef-1"}, {"ksef_number": "ksef-2"}],
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
        cli_args("invoices", "metadata", "--date-from", "2026-01-01T00:00:00Z", "--all"),
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
        cli_args("invoices", "download", "--ksef-number", "ksef/1", "--out", str(target)),
        obj=runtime,
    )

    assert payload(result) == {"path": str(target), "bytes": len(b"<invoice/>")}
    assert target.read_bytes() == b"<invoice/>"

    result = runner.invoke(
        app,
        cli_args("invoices", "download", "--ksef-number", "ksef/2", "--out", str(target), "--wait"),
        obj=runtime,
    )
    assert payload(result)["bytes"] == len(b"<waited/>")
    assert service.called("wait_for_invoice_download")["ksef_number"] == "ksef/2"


def test_invoice_export_status_fetch_and_download(runner, tmp_path) -> None:
    handle = ExportHandle(reference_number="export-ref", aes_key=b"abc", iv=b"def")
    service = FakeService(
        schedule_export=handle,
        get_export_status=ExportStatus(package="package"),
        wait_for_export_package="waited-package",
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
    assert json.loads(handle_file.read_text(encoding="utf-8"))["reference_number"] == "export-ref"

    assert payload(runner.invoke(app, cli_args("invoices", "export-status", "--reference", "export-ref"), obj=runtime)) == {
        "package": "package"
    }

    fetch_dir = tmp_path / "fetch"
    result = runner.invoke(
        app,
        cli_args("invoices", "export-fetch", "--handle-file", str(handle_file), "--out-dir", str(fetch_dir)),
        obj=runtime,
    )
    assert payload(result) == {
        "reference_number": "export-ref",
        "paths": [str(fetch_dir / "out.xml")],
    }
    assert service.called("fetch_package")["package"] == "package"

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
    handle_file.write_text(json.dumps(invoices._export_handle_to_dict(handle)), encoding="utf-8")
    service = FakeService(get_export_status=ExportStatus(package=None))
    runtime = fake_runtime(auth=type("Auth", (), {"invoices": service})())

    result = runner.invoke(app, cli_args("invoices", "export-fetch", "--handle-file", str(handle_file)), obj=runtime)

    assert result.exit_code == 1
    assert "Export package is not ready" in result.output
