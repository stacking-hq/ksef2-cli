"""Invoice command group."""

import typer

from ksef2_cli.commands.invoices.export import (
    invoices_export,
    invoices_export_download,
    invoices_export_fetch,
    invoices_export_status,
)
from ksef2_cli.commands.invoices.metadata import (
    invoices_download,
    invoices_metadata,
)
from ksef2_cli.commands.invoices.receipts import invoices_status, invoices_upo
from ksef2_cli.commands.invoices.send import invoices_send

app = typer.Typer(help="Send, confirm, query, download, and export invoices.")

app.command("send")(invoices_send)
app.command("status")(invoices_status)
app.command("upo")(invoices_upo)
app.command("metadata")(invoices_metadata)
app.command("download")(invoices_download)
app.command("export")(invoices_export)
app.command("export-status")(invoices_export_status)
app.command("export-fetch")(invoices_export_fetch)
app.command("export-download")(invoices_export_download)
