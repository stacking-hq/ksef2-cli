"""Component tests for the local ``fa3`` build, inspect and render commands.

These commands run the real SDK builder, parser and XSLT renderer on tiny
fixtures: nothing here talks to KSeF, so no client fake is needed.
"""

import inspect
import json
from pathlib import Path
from typing import Any

import pytest
from conftest import cli_args, payload, plain
from ksef2 import Environment
from ksef2.fa3 import InvoiceBuilder
from ksef2.renderers import InvoicePDFExporter
from rich.cells import cell_len
from typer.testing import CliRunner

from ksef2_cli import runtime
from ksef2_cli.app import app

DRAFT: dict[str, Any] = {
    "header": {"system_info": "ksef2-cli test"},
    "seller": {
        "name": "ACME sp. z o.o.",
        "tax_id": "5252222222",
        "address": {"country_code": "PL", "address_line_1": "ul. Przykladowa 10"},
    },
    "buyer": {
        "name": "XYZ sp. z o.o.",
        "tax_id": "9876543210",
        "address": {"country_code": "PL", "address_line_1": "ul. Odbiorcza 20"},
    },
    "body": {
        "currency": "PLN",
        "issue_date": "2026-04-09",
        "issue_place": "Warszawa",
        "invoice_number": "FV/2026/04/0001",
        "rows": [
            {
                "name": "Consulting service",
                "unit_of_measure": "h",
                "quantity": "10",
                "unit_price_net": "100.00",
                "vat_rate": "23",
            }
        ],
    },
}


@pytest.fixture
def draft_file(tmp_path: Path) -> Path:
    path = tmp_path / "draft.json"
    path.write_text(json.dumps(DRAFT), encoding="utf-8")
    return path


@pytest.fixture
def invoice_file(draft_file: Path, tmp_path: Path) -> Path:
    """FA(3) XML built straight from the draft fixture by the SDK builder."""

    xml = InvoiceBuilder.from_state_json(
        draft_file.read_text(encoding="utf-8")
    ).to_xml()
    path = tmp_path / "invoice.xml"
    path.write_text(xml, encoding="utf-8")
    return path


def test_build_writes_fa3_xml_file(runner, draft_file, tmp_path) -> None:
    out = tmp_path / "invoice.xml"

    result = runner.invoke(
        app, cli_args("fa3", "build", "--in", str(draft_file), "--out", str(out))
    )

    body = payload(result)
    assert body["path"] == str(out)
    assert body["bytes"] == out.stat().st_size
    xml = out.read_text(encoding="utf-8")
    assert "<Faktura" in xml
    assert "5252222222" in xml
    assert "FV/2026/04/0001" in xml


def test_build_prints_xml_to_stdout_when_out_is_omitted(runner, draft_file) -> None:
    result = runner.invoke(
        app, ["--no-config", "fa3", "build", "--in", str(draft_file)]
    )

    assert result.exit_code == 0
    assert result.output.startswith("<?xml")
    assert "<Naglowek>" in result.output


def test_build_reads_draft_from_stdin(runner, tmp_path) -> None:
    out = tmp_path / "invoice.xml"

    result = runner.invoke(
        app,
        cli_args("fa3", "build", "--in", "-", "--out", str(out)),
        input=json.dumps(DRAFT),
    )

    assert payload(result)["bytes"] > 0
    assert "9876543210" in out.read_text(encoding="utf-8")


def test_build_no_pretty_keeps_xml_on_one_line(runner, draft_file, tmp_path) -> None:
    out = tmp_path / "invoice.xml"

    result = runner.invoke(
        app,
        cli_args(
            "fa3",
            "build",
            "--in",
            str(draft_file),
            "--out",
            str(out),
            "--no-pretty",
            "--no-validate",
        ),
    )

    assert result.exit_code == 0
    lines = out.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2  # declaration plus document


def test_build_reports_invalid_draft(runner, tmp_path) -> None:
    draft = tmp_path / "draft.json"
    draft.write_text(json.dumps({"header": {"system_info": "x"}, "rows": []}), "utf-8")

    result = runner.invoke(app, cli_args("fa3", "build", "--in", str(draft)))

    assert result.exit_code == 2
    assert "Extra inputs are not permitted" in result.output


def test_build_reports_incomplete_draft(runner, tmp_path) -> None:
    draft = tmp_path / "draft.json"
    draft.write_text(json.dumps({"header": {"system_info": "x"}}), "utf-8")

    result = runner.invoke(app, cli_args("fa3", "build", "--in", str(draft)))

    assert result.exit_code == 1
    assert "seller is required" in result.output


def test_build_reports_missing_draft_file(runner, tmp_path) -> None:
    result = runner.invoke(
        app, cli_args("fa3", "build", "--in", str(tmp_path / "none.json"))
    )

    assert result.exit_code == 1
    assert "Can't access" in result.output


def test_draft_example_is_buildable(runner, tmp_path) -> None:
    printed = runner.invoke(app, ["--no-config", "fa3", "draft-example"])
    assert printed.exit_code == 0

    draft = tmp_path / "draft.json"
    draft.write_text(printed.output, encoding="utf-8")
    out = tmp_path / "invoice.xml"

    built = runner.invoke(
        app, cli_args("fa3", "build", "--in", str(draft), "--out", str(out))
    )

    assert payload(built)["bytes"] > 0
    assert "<Faktura" in out.read_text(encoding="utf-8")


def test_draft_example_writes_file(runner, tmp_path) -> None:
    out = tmp_path / "draft.json"

    result = runner.invoke(app, cli_args("fa3", "draft-example", "--out", str(out)))

    body = payload(result)
    assert body["path"] == str(out)
    assert json.loads(out.read_text(encoding="utf-8"))["body"]["invoice_number"]


def test_inspect_reads_invoice_back_from_xml(runner, invoice_file) -> None:
    result = runner.invoke(app, cli_args("fa3", "inspect", "--in", str(invoice_file)))

    body = payload(result)
    assert body["seller"]["tax_id"] == "5252222222"
    assert body["body"]["invoice_number"] == "FV/2026/04/0001"


def test_inspect_plain_text_fits_the_declared_width(runner, invoice_file) -> None:
    # Every section of an invoice is nested groups, so this is where a plain record
    # that ignores the terminal width shows up first.
    result = runner.invoke(
        app,
        ["--no-config", "fa3", "inspect", "--in", str(invoice_file)],
        env={"COLUMNS": "80", "NO_COLOR": "1", "FORCE_COLOR": None},
    )

    assert result.exit_code == 0, result.output
    assert max(cell_len(line) for line in result.output.splitlines()) <= 80

    # The wrap only moved text onto continuation lines: the record is still complete.
    flat = "".join(result.output.split())
    for value in ("5252222222", "FV/2026/04/0001", "ACME sp. z o.o.", "2026-04-09"):
        assert "".join(value.split()) in flat


def test_inspect_reports_non_fa3_xml(runner, tmp_path) -> None:
    xml = tmp_path / "other.xml"
    xml.write_text("<html>not an invoice</html>", encoding="utf-8")

    result = runner.invoke(app, cli_args("fa3", "inspect", "--in", str(xml)))

    assert result.exit_code == 2
    assert "Expected a Faktura root" in result.output


def test_render_writes_html_file(runner, invoice_file, tmp_path) -> None:
    out = tmp_path / "invoice.html"

    result = runner.invoke(
        app,
        cli_args("fa3", "render", "--in", str(invoice_file), "--out", str(out)),
    )

    body = payload(result)
    assert body["path"] == str(out)
    assert body["bytes"] == out.stat().st_size
    html = out.read_text(encoding="utf-8")
    assert "<html" in html
    assert "FV/2026/04/0001" in html


def test_render_prints_html_when_no_output_requested(runner, invoice_file) -> None:
    result = runner.invoke(
        app, ["--no-config", "fa3", "render", "--in", str(invoice_file)]
    )

    assert result.exit_code == 0
    assert "<html" in result.output


def test_render_rejects_missing_invoice_file(runner, tmp_path) -> None:
    result = runner.invoke(
        app, cli_args("fa3", "render", "--in", str(tmp_path / "none.xml"))
    )

    assert result.exit_code == 2
    assert "does not exist" in result.output


class FakePdfExporter:
    def __init__(
        self,
        *,
        verification_environment: Environment,
        page_size: object | None = None,
        enable_code_lookups: bool = False,
    ) -> None:
        self.page_size = page_size
        self.enable_code_lookups = enable_code_lookups

    def export_to_file(
        self,
        invoice_xml_path: Path,
        output_pdf_path: Path,
        *,
        ksef_number: str | None = None,
    ) -> Path:
        output_pdf_path.parent.mkdir(parents=True, exist_ok=True)
        output_pdf_path.write_bytes(b"%PDF-1.4 fake")
        return output_pdf_path


def test_render_writes_html_and_pdf(
    runner, invoice_file, tmp_path, monkeypatch
) -> None:
    monkeypatch.setattr(runtime, "InvoicePDFExporter", FakePdfExporter)
    html = tmp_path / "invoice.html"
    pdf = tmp_path / "invoice.pdf"

    result = runner.invoke(
        app,
        cli_args(
            "fa3",
            "render",
            "--in",
            str(invoice_file),
            "--out",
            str(html),
            "--pdf",
            str(pdf),
        ),
    )

    files = payload(result)
    assert [item["path"] for item in files] == [str(html), str(pdf)]
    assert "<html" in html.read_text(encoding="utf-8")
    assert pdf.read_bytes().startswith(b"%PDF")


@pytest.mark.parametrize("environment", [None, "demo"])
def test_render_pdf_passes_environment_to_sdk_constructor(
    runner, invoice_file, tmp_path, monkeypatch, environment
) -> None:
    environments = []

    class SignatureCheckedExporter(FakePdfExporter):
        def __init__(self, *args, **kwargs):
            inspect.signature(InvoicePDFExporter.__init__).bind(self, *args, **kwargs)
            environments.append(kwargs["verification_environment"])
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(runtime, "InvoicePDFExporter", SignatureCheckedExporter)
    args = ["--config", str(tmp_path / "missing-config.json")]
    if environment is not None:
        args.extend(["--env", environment])
    pdf = tmp_path / "invoice.pdf"
    result = runner.invoke(
        app, args + ["fa3", "render", "--in", str(invoice_file), "--pdf", str(pdf)]
    )

    assert result.exit_code == 0, result.output
    assert pdf.read_bytes().startswith(b"%PDF")
    assert environments == [
        Environment.PRODUCTION if environment is None else Environment.DEMO
    ]


def test_render_pdf_passes_ksef_number_to_the_exporter(
    runner, invoice_file, tmp_path, monkeypatch
) -> None:
    """`--ksef-number` is what makes the SDK draw the verification QR in the PDF."""

    numbers: list[str | None] = []

    class RecordingExporter(FakePdfExporter):
        def export_to_file(
            self,
            invoice_xml_path: Path,
            output_pdf_path: Path,
            *,
            ksef_number: str | None = None,
        ) -> Path:
            inspect.signature(InvoicePDFExporter.export_to_file).bind(
                self, invoice_xml_path, output_pdf_path, ksef_number=ksef_number
            )
            numbers.append(ksef_number)
            return super().export_to_file(
                invoice_xml_path, output_pdf_path, ksef_number=ksef_number
            )

    monkeypatch.setattr(runtime, "InvoicePDFExporter", RecordingExporter)
    pdf = tmp_path / "invoice.pdf"
    number = "5261040828-20260101-ABCDEF123456-AB"

    without = runner.invoke(
        app,
        cli_args(
            "fa3", "render", "--in", str(invoice_file), "--pdf", str(pdf)
        ),
    )
    with_number = runner.invoke(
        app,
        cli_args(
            "fa3",
            "render",
            "--in",
            str(invoice_file),
            "--pdf",
            str(pdf),
            "--ksef-number",
            number,
        ),
    )

    assert payload(without) is not None
    assert payload(with_number) is not None
    assert numbers == [None, number]


def test_render_ksef_number_without_pdf_is_a_usage_error(
    runner, invoice_file, tmp_path
) -> None:
    """The QR lives in the PDF, so a number with no --pdf is a mistake, not a no-op."""

    result = runner.invoke(
        app,
        cli_args(
            "fa3",
            "render",
            "--in",
            str(invoice_file),
            "--out",
            str(tmp_path / "invoice.html"),
            "--ksef-number",
            "5252222222-20260409-ABCDEF123456-AB",
        ),
    )

    assert result.exit_code == 2
    assert "--ksef-number needs --pdf" in plain(result.output)
    assert not (tmp_path / "invoice.html").exists()


def test_render_pdf_keeps_dependency_noise_off_stdout(
    invoice_file, tmp_path, monkeypatch
) -> None:
    """WeasyPrint's own import banner must not land on the stream carrying results.

    Under --json stdout stays machine-readable, so the banner and the JSON error both
    belong on stderr.
    """

    def noisy_missing_libraries(*_args: object, **_kwargs: object) -> None:
        # What WeasyPrint itself does when its native libraries will not load.
        print("WeasyPrint could not import some external libraries.")
        raise OSError("cannot load library 'libgobject-2.0-0'")

    monkeypatch.setattr(runtime, "InvoicePDFExporter", noisy_missing_libraries)

    result = CliRunner(mix_stderr=False).invoke(
        app,
        cli_args(
            "fa3",
            "render",
            "--in",
            str(invoice_file),
            "--pdf",
            str(tmp_path / "out.pdf"),
        ),
    )

    assert result.exit_code == 1
    assert result.stdout == ""
    assert "could not import some external libraries" in result.stderr
    reported = next(
        json.loads(line)
        for line in result.stderr.splitlines()
        if line.startswith("{")
    )
    assert reported["error"]["type"] == "MissingOptionalDependencyError"


def test_render_pdf_names_the_missing_extra(
    runner, invoice_file, tmp_path, monkeypatch
) -> None:
    def missing_extra(*args: object, **kwargs: object) -> None:
        raise ImportError("InvoicePDFExporter requires the optional PDF dependencies.")

    monkeypatch.setattr(runtime, "InvoicePDFExporter", missing_extra)
    html = tmp_path / "invoice.html"

    result = runner.invoke(
        app,
        cli_args(
            "fa3",
            "render",
            "--in",
            str(invoice_file),
            "--out",
            str(html),
            "--pdf",
            str(tmp_path / "invoice.pdf"),
        ),
    )

    assert result.exit_code == 1
    assert "ksef2[pdf]" in plain(result.output)
    assert not html.exists()
