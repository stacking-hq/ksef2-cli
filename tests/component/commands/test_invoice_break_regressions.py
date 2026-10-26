"""Local break-report regressions, including real SDK sessions over fake HTTP."""

import json
from datetime import UTC, datetime
from types import SimpleNamespace

import httpx
import pytest
from conftest import cli_args, fake_runtime, online_state, payload, plain
from ksef2.clients import OnlineSessionClient
from ksef2.fa3 import InvoiceBuilder
from ksef2_cli.app import app
from ksef2_cli.commands.fa3 import _EXAMPLE_DRAFT
from ksef2_cli.commands.invoices.filters import parse_invoice_dates
from ksef2_cli.io import validate_invoice_xml


@pytest.mark.parametrize(
    ("resumed", "flags", "closed"),
    [
        (True, [], False),
        (True, ["--close"], True),
        (True, ["--keep-open"], False),
        (False, [], True),
        (False, ["--keep-open"], False),
        (False, ["--close"], True),
    ],
)
def test_online_session_lifetime_real_sdk(runner, tmp_path, resumed, flags, closed):
    requests = []

    def respond(request):
        requests.append(request)
        if request.method == "GET":
            return httpx.Response(
                200,
                json={
                    "status": {"code": 100, "description": "open"},
                    "dateCreated": "2026-01-01T00:00:00Z",
                    "dateUpdated": "2026-01-01T00:00:00Z",
                },
            )
        if request.url.path.endswith("/close"):
            return httpx.Response(204)
        return httpx.Response(
            202, json={"referenceNumber": "00000000-0000-0000-0000-000000000001"}
        )

    state = online_state()
    state_file = tmp_path / "state.json"
    state_file.write_text(state.to_json(), encoding="utf-8")
    invoice = tmp_path / "invoice.xml"
    invoice.write_bytes(b"<invoice/>")
    with httpx.Client(
        base_url="https://local.invalid", transport=httpx.MockTransport(respond)
    ) as transport:
        middleware = SimpleNamespace(
            post=lambda path, **kwargs: transport.post(path, **kwargs),
            get=lambda path, **kwargs: transport.get(path, **kwargs),
        )
        session = OnlineSessionClient(middleware, state, resumed=resumed)
        runtime = fake_runtime(
            auth=SimpleNamespace(online_session=lambda **kwargs: session)
        )
        args = ["online", "send", str(invoice), *flags]
        if resumed:
            args.extend(["--state-file", str(state_file)])
        result = payload(runner.invoke(app, cli_args(*args), obj=runtime))
    assert result["closed"] is closed
    assert (
        result["results"][0]["result"]["reference_number"]
        == "00000000-0000-0000-0000-000000000001"
    )
    assert any(request.url.path.endswith("/close") for request in requests) is closed
    send = next(
        request
        for request in requests
        if request.method == "POST" and request.url.path.endswith("/invoices")
    )
    body = json.loads(send.content)
    assert body["invoiceSize"] == len(b"<invoice/>")
    assert body["encryptedInvoiceContent"]


def test_online_conflicting_close_choices_fail_locally(runner, tmp_path):
    invoice = tmp_path / "invoice.xml"
    invoice.write_bytes(b"<invoice/>")
    result = runner.invoke(
        app, cli_args("online", "send", str(invoice), "--close", "--keep-open")
    )
    assert result.exit_code == 2
    assert "Use either --close or --keep-open" in plain(result.output)


@pytest.mark.parametrize(
    "content,label",
    [
        (b"\xef\xbb\xbf<invoice/>", "UTF-8 BOM"),
        ("<invoice/>".encode("utf-16"), "UTF-16 LE BOM"),
        (b"\xfe\xff" + "<invoice/>".encode("utf-16-be"), "UTF-16 BE BOM"),
        (b" \n", "empty"),
    ],
)
@pytest.mark.parametrize(
    "command", [("invoices", "send"), ("online", "send"), ("fa3", "inspect", "--in")]
)
def test_encoding_rejected_before_authentication(
    runner, tmp_path, content, label, command
):
    invoice = tmp_path / "invoice.xml"
    invoice.write_bytes(content)
    result = runner.invoke(app, cli_args(*command, str(invoice)))
    assert result.exit_code == 2
    assert label in plain(result.output)
    assert "authentication" not in plain(result.output).lower()
    assert invoice.read_bytes() == content


def test_signed_bytes_are_not_changed():
    content = b'<?xml version="1.0" encoding="UTF-8"?>\r\n<invoice> signed </invoice>\n'
    assert validate_invoice_xml(content, source="signed.xml") is content


def test_example_timestamp_is_current_aware_utc(runner):
    before = datetime.now(UTC)
    result = runner.invoke(app, ["--no-config", "fa3", "draft-example"])
    assert result.exit_code == 0, result.output
    timestamp = datetime.fromisoformat(
        json.loads(result.output)["header"]["generation_timestamp"]
    )
    assert timestamp.utcoffset().total_seconds() == 0
    assert before <= timestamp <= datetime.now(UTC)


def test_inspect_positional_readable_and_json_compatible(runner, tmp_path):
    invoice = tmp_path / "invoice.xml"
    invoice.write_text(
        InvoiceBuilder.from_state_json(_EXAMPLE_DRAFT).to_xml(), encoding="utf-8"
    )
    result = runner.invoke(app, ["--no-config", "fa3", "inspect", str(invoice)])
    assert result.exit_code == 0, result.output
    assert "seller: ACME sp. z o.o." in result.output
    assert "invoice_number: FV/2026/04/0001" in result.output
    assert "name=Consulting service" in result.output
    assert '"tax_id"' not in result.output
    assert (
        payload(runner.invoke(app, cli_args("fa3", "inspect", "--in", str(invoice))))[
            "seller"
        ]["tax_id"]
        == "5252222222"
    )


@pytest.mark.parametrize(
    "command", ["metadata", "export", "export-download", "export-pdf"]
)
def test_invalid_dates_show_values_and_zone_before_auth(runner, command):
    result = runner.invoke(
        app,
        cli_args(
            "invoices",
            command,
            "--date-from",
            "2026-02-02",
            "--date-to",
            "2026-02-01T12:00:00+02:00",
        ),
    )
    assert result.exit_code == 2
    output = plain(result.output)
    assert "--date-from=2026-02-02T00:00:00 [Europe/Warsaw]" in output
    assert "--date-to=2026-02-01T12:00:00+02:00" in output


def test_invalid_dates_include_implicit_now():
    with pytest.raises(ValueError, match="implicit now UTC") as error:
        parse_invoice_dates("2100-01-01", None)
    assert datetime.now(UTC).date().isoformat() in str(error.value)


def test_date_normalization_uses_real_sdk_warsaw_rules():
    dates = parse_invoice_dates("2026-04-01", "2026-04-02")
    assert dates == {
        "date_from": datetime(2026, 3, 31, 22, tzinfo=UTC),
        "date_to": datetime(2026, 4, 1, 22, tzinfo=UTC),
    }


def test_pdf_dependencies_checked_before_auth_or_download(
    runner, tmp_path, monkeypatch
):
    from ksef2_cli import runtime

    def unavailable(**kwargs):
        raise ImportError("WeasyPrint unavailable")

    monkeypatch.setattr(runtime, "InvoicePDFExporter", unavailable)
    result = runner.invoke(
        app,
        cli_args(
            "invoices",
            "export-pdf",
            "--date-from",
            "2026-01-01",
            "--date-to",
            "2026-01-02",
            "--out-dir",
            str(tmp_path / "out"),
        ),
    )
    assert result.exit_code == 1
    assert "PDF rendering needs dependencies" in plain(result.output)
    assert not (tmp_path / "out").exists()


def test_real_local_pdf_smoke_when_dependencies_available(runner, tmp_path):
    from ksef2 import Environment
    from ksef2_cli.exceptions import MissingOptionalDependencyError
    from ksef2_cli.runtime import create_pdf_exporter

    try:
        create_pdf_exporter(environment=Environment.TEST)
    except MissingOptionalDependencyError as error:
        pytest.skip(str(error))
    invoice = tmp_path / "invoice.xml"
    invoice.write_text(
        InvoiceBuilder.from_state_json(_EXAMPLE_DRAFT).to_xml(), encoding="utf-8"
    )
    pdf = tmp_path / "invoice.pdf"
    result = runner.invoke(
        app, cli_args("fa3", "render", "--in", str(invoice), "--pdf", str(pdf))
    )
    assert result.exit_code == 0, result.output
    assert pdf.read_bytes().startswith(b"%PDF-")
    assert pdf.stat().st_size > 1000


@pytest.mark.parametrize("use_option", [False, True])
def test_download_accepts_positional_and_existing_option(runner, tmp_path, use_option):
    from conftest import FakeService

    invoices = FakeService(download=b"<downloaded/>")
    runtime = fake_runtime(auth=SimpleNamespace(invoices=invoices))
    number = "5261040828-20260101-AAAAAAAAAAAA-01"
    out = tmp_path / "download.xml"
    args = ["invoices", "download"]
    if use_option:
        args.append("--ksef-number")
    args.extend([number, "--out", str(out)])
    result = payload(runner.invoke(app, cli_args(*args), obj=runtime))
    assert result["path"] == str(out)
    assert out.read_bytes() == b"<downloaded/>"
    assert invoices.called("download")["ksef_number"] == number


@pytest.mark.parametrize(
    "command",
    [
        ["invoices", "download", "number-a", "--ksef-number", "number-b"],
        ["invoices", "download"],
        ["fa3", "inspect"],
    ],
)
def test_missing_or_conflicting_aliases_fail_locally(runner, command):
    result = runner.invoke(app, cli_args(*command))
    assert result.exit_code == 2
    assert "Provide one" in plain(result.output)


def test_stdin_invoice_reads_once_without_persistence(monkeypatch):
    import io
    import sys
    from ksef2_cli.io import read_stdin_invoice_xml

    class SingleRead(io.BytesIO):
        reads = 0

        def read(self, *args):
            self.reads += 1
            assert self.reads == 1
            return super().read(*args)

    stream = SingleRead(b"<invoice> original bytes </invoice>\r\n")
    monkeypatch.setattr(sys, "stdin", SimpleNamespace(buffer=stream))
    assert read_stdin_invoice_xml() == b"<invoice> original bytes </invoice>\r\n"
    assert stream.reads == 1


def test_stdin_invoice_rejects_empty_content(monkeypatch):
    import io
    import sys
    from ksef2_cli.io import read_stdin_invoice_xml

    monkeypatch.setattr(sys, "stdin", SimpleNamespace(buffer=io.BytesIO(b" \n")))
    with pytest.raises(ValueError, match="stdin.xml is empty"):
        read_stdin_invoice_xml()


@pytest.mark.parametrize("width", [40, 80, 160])
def test_missing_invoice_message_survives_terminal_wrapping(runner, tmp_path, width):
    missing = tmp_path / "a-long-missing-invoice-file-name.xml"
    result = runner.invoke(
        app, cli_args("fa3", "render", "--in", str(missing)), terminal_width=width
    )
    assert result.exit_code == 2
    assert "does not exist" in plain(result.output)


def test_export_pdf_preflight_preserves_manifest_ksef_numbers(
    runner, tmp_path, monkeypatch
):
    from ksef2_cli import invoice_workflows
    from ksef2_cli.commands.invoices import export
    from ksef2_cli.commands.invoices.models import ExportPaths

    number = "5261040828-20260102-ABCDEF123456-AB"
    invoice = tmp_path / f"{number}.xml"
    unknown = tmp_path / "draft.xml"
    metadata = tmp_path / "_metadata.json"
    calls = []
    constructors = []

    def render(path, *, ksef_number):
        calls.append((path, ksef_number))
        return b"%PDF-1.4 test"

    def create(**kwargs):
        constructors.append(kwargs)
        return SimpleNamespace(export_from_path=render)

    monkeypatch.setattr(export, "create_pdf_exporter", create)
    monkeypatch.setattr(
        invoice_workflows,
        "_download_export_package",
        lambda auth, inputs: (
            ExportPaths(reference_number="export-ref", paths=[invoice, metadata, unknown]),
            SimpleNamespace(metadata=[SimpleNamespace(ksef_number=number)]),
        ),
    )
    result = runner.invoke(
        app,
        cli_args(
            "invoices", "export-pdf", "--date-from", "2026-01-01",
            "--date-to", "2026-01-02", "--out-dir", str(tmp_path),
        ),
        obj=fake_runtime(auth=SimpleNamespace()),
    )
    data = payload(result)
    assert len(constructors) == 1
    assert calls == [(invoice, number), (unknown, None)]
    assert data["invoice_xml_files"] == [str(invoice), str(unknown)]
    assert invoice.with_suffix(".pdf").read_bytes() == b"%PDF-1.4 test"
    assert unknown.with_suffix(".pdf").read_bytes() == b"%PDF-1.4 test"


def test_metadata_only_pdf_export_needs_no_pdf_dependencies(
    runner, tmp_path, monkeypatch
):
    from ksef2_cli import invoice_workflows
    from ksef2_cli.commands.invoices import export
    from ksef2_cli.commands.invoices.models import ExportPaths

    def unavailable(**kwargs):
        pytest.fail("Metadata-only exports must not initialize a PDF exporter")

    monkeypatch.setattr(export, "create_pdf_exporter", unavailable)
    monkeypatch.setattr(
        invoice_workflows,
        "_download_export_package",
        lambda auth, inputs: (
            ExportPaths(reference_number="export-ref", paths=[tmp_path / "_metadata.json"]),
            SimpleNamespace(metadata=[]),
        ),
    )
    result = runner.invoke(
        app,
        cli_args(
            "invoices", "export-pdf", "--date-from", "2026-01-01",
            "--date-to", "2026-01-02", "--out-dir", str(tmp_path), "--only-metadata",
        ),
        obj=fake_runtime(auth=SimpleNamespace()),
    )
    data = payload(result)
    assert data["pdfs"] == []
    assert data["invoice_xml_files"] == []
    assert not list(tmp_path.glob("*.pdf"))
