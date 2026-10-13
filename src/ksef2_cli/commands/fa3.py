"""Local FA(3) invoice commands: build XML, inspect it, and render it.

These commands never contact KSeF. They wrap the SDK's public builder and
renderer APIs so a draft JSON file can become schema-valid FA(3) XML, and that
XML can become HTML or PDF, without an authenticated client.
"""

import sys
from pathlib import Path
from typing import Annotated

import typer
from ksef2.fa3 import FA3InvoiceBuilder, parse_invoice_xml
from ksef2.renderers import InvoicePDFExporter, InvoiceXSLTRenderer

from ksef2_cli.context import run_command
from ksef2_cli.exceptions import CliError
from ksef2_cli.io import write_text_file
from ksef2_cli.results import SavedFile

app = typer.Typer(
    help="Build, inspect, and render FA(3) invoices locally, without KSeF access."
)

PDF_INSTALL_HINT = (
    "Install the optional PDF dependencies: pip install 'ksef2[pdf]' "
    "or uv add 'ksef2[pdf]'."
)

# Hand-written instead of dumped from the builder, so it stays a readable starting
# point. test_draft_example_round_trips_through_build keeps it SDK-acceptable.
_EXAMPLE_DRAFT = """{
  "header": {
    "generation_timestamp": "2026-04-09T10:15:00+02:00",
    "system_info": "ksef2-cli"
  },
  "seller": {
    "name": "ACME sp. z o.o.",
    "tax_id": "5252222222",
    "address": {
      "country_code": "PL",
      "address_line_1": "ul. Przykladowa 10",
      "address_line_2": "00-001 Warszawa"
    }
  },
  "buyer": {
    "name": "XYZ sp. z o.o.",
    "tax_id": "9876543210",
    "address": {
      "country_code": "PL",
      "address_line_1": "ul. Odbiorcza 20",
      "address_line_2": "00-950 Warszawa"
    }
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
        "vat_rate": "23"
      }
    ]
  }
}"""


@app.command("build")
def fa3_build(
    ctx: typer.Context,
    draft_file: Annotated[
        Path,
        typer.Option(
            "--in",
            "-i",
            help="Invoice draft JSON file, or - to read the draft from stdin.",
        ),
    ],
    out: Annotated[
        Path | None,
        typer.Option(
            "--out",
            "-o",
            dir_okay=False,
            help="Where to write FA(3) XML. Defaults to stdout.",
        ),
    ] = None,
    pretty: Annotated[
        bool,
        typer.Option("--pretty/--no-pretty", help="Indent the generated XML."),
    ] = True,
    validate: Annotated[
        bool,
        typer.Option(
            "--validate/--no-validate",
            help="Check the XML against the FA(3) schema before writing it.",
        ),
    ] = True,
) -> None:
    """Build FA(3) XML from a JSON invoice draft."""

    def operation() -> object:
        builder = FA3InvoiceBuilder.from_state_json(_read_draft(draft_file))
        xml = builder.to_xml(pretty_print=pretty, validate=validate)
        return xml if out is None else _write(out, xml)

    run_command(ctx, operation)


@app.command("inspect")
def fa3_inspect(
    ctx: typer.Context,
    invoice_file: Annotated[
        Path,
        typer.Option(
            "--in", "-i", exists=True, dir_okay=False, help="FA(3) invoice XML file."
        ),
    ],
) -> None:
    """Read invoice XML and print the invoice it describes."""

    def operation() -> object:
        return parse_invoice_xml(invoice_file.read_bytes())

    run_command(ctx, operation)


@app.command("render")
def fa3_render(
    ctx: typer.Context,
    invoice_file: Annotated[
        Path,
        typer.Option(
            "--in", "-i", exists=True, dir_okay=False, help="FA(3) invoice XML file."
        ),
    ],
    out: Annotated[
        Path | None,
        typer.Option(
            "--out",
            "-o",
            dir_okay=False,
            help="Where to write HTML. Defaults to stdout when --pdf is not used.",
        ),
    ] = None,
    pdf: Annotated[
        Path | None,
        typer.Option(
            "--pdf",
            dir_okay=False,
            help="Also write PDF here. Needs the optional ksef2[pdf] dependencies.",
        ),
    ] = None,
    code_lookups: Annotated[
        bool,
        typer.Option(
            "--code-lookups/--no-code-lookups",
            help=(
                "Let the bundled stylesheet read local files and URLs so coded values "
                "print as names. Use it only with invoice XML you trust."
            ),
        ),
    ] = False,
) -> None:
    """Render invoice XML to HTML, and optionally to PDF."""

    def operation() -> object:
        # The exporter is built first so a missing optional extra fails before the
        # command has written anything the user has to clean up.
        exporter = _pdf_exporter(code_lookups) if pdf is not None else None
        renderer = InvoiceXSLTRenderer(enable_code_lookups=code_lookups)

        if out is None and pdf is None:
            return renderer.render_from_string(invoice_file.read_text("utf-8"))

        saved: list[SavedFile] = []
        if out is not None:
            html = renderer.render_from_string(invoice_file.read_text("utf-8"))
            saved.append(_write(out, html))
        if exporter is not None and pdf is not None:
            target = exporter.export_to_file(invoice_file, pdf)
            saved.append(SavedFile(path=target, size=target.stat().st_size))
        return saved[0] if len(saved) == 1 else saved

    run_command(ctx, operation)


@app.command("draft-example")
def fa3_draft_example(
    ctx: typer.Context,
    out: Annotated[
        Path | None,
        typer.Option(
            "--out",
            "-o",
            dir_okay=False,
            help="Where to write the draft. Defaults to stdout.",
        ),
    ] = None,
) -> None:
    """Print a minimal invoice draft that fa3 build accepts."""

    def operation() -> object:
        return _EXAMPLE_DRAFT if out is None else _write(out, _EXAMPLE_DRAFT)

    run_command(ctx, operation)


def _read_draft(path: Path) -> str:
    return sys.stdin.read() if str(path) == "-" else path.read_text(encoding="utf-8")


def _pdf_exporter(code_lookups: bool) -> InvoicePDFExporter:
    """Build the optional WeasyPrint exporter, naming the missing extra when absent."""

    try:
        return InvoicePDFExporter(enable_code_lookups=code_lookups)
    except ImportError as exc:
        raise CliError(
            "PDF rendering needs dependencies that are not installed.",
            title="Optional dependency missing",
            details=(str(exc),),
            hints=(PDF_INSTALL_HINT,),
        ) from exc


def _write(path: Path, content: str) -> SavedFile:
    """Report the size the file really has, newline from the writer included."""

    target = write_text_file(path, content)
    return SavedFile(path=target, size=target.stat().st_size)
