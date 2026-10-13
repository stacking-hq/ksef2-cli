"""Collective invoice identifier command group."""

from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import typer
from ksef2.clients import AuthenticatedClient
from ksef2.models import (
    CollectiveIdentifierInvoice,
    CollectiveIdentifierInvoiceDetails,
    CollectiveIdentifierParams,
    CollectiveIdentifierReference,
    CollectiveIdentifierSummary,
    CollectiveIdentifiersQuery,
    GenerateCollectiveIdentifierResponse,
)
from pydantic import RootModel

from ksef2_cli.context import read_model, run_authenticated, run_command
from ksef2_cli.parsing import parse_iso_datetime, parse_optional_bool

app = typer.Typer(help="Generate and query collective invoice identifiers.")

_MAX_IDS_PER_INVOICE_QUERY = 10


class CollectiveIdentifierInvoiceList(RootModel[list[CollectiveIdentifierInvoice]]):
    """JSON array of invoices accepted by ``generate --invoices-file``."""


@app.command("generate")
def collective_generate(
    ctx: typer.Context,
    invoice: Annotated[
        list[str],
        typer.Option(
            "--invoice",
            help="KSeF number of an invoice to group. Repeat for multiple invoices.",
        ),
    ] = [],
    invoices_file: Annotated[
        Path | None,
        typer.Option(
            "--invoices-file",
            exists=True,
            dir_okay=False,
            help="JSON array of invoices; adds payment and description per invoice.",
        ),
    ] = None,
) -> None:
    """Generate a collective identifier for a set of invoices."""

    def operation() -> GenerateCollectiveIdentifierResponse:
        invoices = _generate_inputs(ctx, invoices_file, invoice)
        return run_authenticated(
            ctx,
            lambda auth: auth.collective_identifiers.generate(invoices=invoices),
        )

    run_command(ctx, operation)


@app.command("list")
def collective_list(
    ctx: typer.Context,
    created_from: Annotated[
        str,
        typer.Option("--date-from", help="Creation start, ISO datetime/date."),
    ],
    created_to: Annotated[
        str | None,
        typer.Option(
            "--date-to",
            help="Creation end, ISO datetime/date. Defaults to now.",
        ),
    ] = None,
    identifier_number: Annotated[
        str | None, typer.Option("--number", help="Exact identifier number.")
    ] = None,
    invoice_count_min: Annotated[
        int | None,
        typer.Option("--invoice-count-min", min=1, help="Minimum grouped invoices."),
    ] = None,
    invoice_count_max: Annotated[
        int | None,
        typer.Option("--invoice-count-max", min=1, help="Maximum grouped invoices."),
    ] = None,
    current_context: Annotated[
        str | None,
        typer.Option(
            "--current-context",
            help="Limit to identifiers created in this context: yes or no.",
        ),
    ] = None,
    page_size: Annotated[int, typer.Option("--page-size", min=10, max=200)] = 10,
    all_pages: Annotated[bool, typer.Option("--all", help="Fetch all pages.")] = False,
) -> None:
    """Query collective identifiers visible in the current context."""

    def operation() -> list[CollectiveIdentifierSummary]:
        filters = CollectiveIdentifiersQuery(
            date_created_from=parse_iso_datetime(
                created_from, option_name="--date-from"
            ),
            date_created_to=datetime.now(UTC)
            if created_to is None
            else parse_iso_datetime(created_to, option_name="--date-to"),
            collective_identifier_number=identifier_number,
            invoice_count_from=invoice_count_min,
            invoice_count_to=invoice_count_max,
            created_in_current_context=parse_optional_bool(
                current_context, option_name="--current-context"
            ),
        )

        def list_identifiers(
            auth: AuthenticatedClient,
        ) -> list[CollectiveIdentifierSummary]:
            pager = auth.collective_identifiers.list(
                filters, params=CollectiveIdentifierParams(page_size=page_size)
            )
            return list(pager) if all_pages else pager.first_page()

        return run_authenticated(ctx, list_identifiers)

    run_command(ctx, operation)


@app.command("list-for-invoice")
def collective_list_for_invoice(
    ctx: typer.Context,
    ksef_number: Annotated[str, typer.Option("--ksef-number")],
    page_size: Annotated[int, typer.Option("--page-size", min=10, max=200)] = 10,
    all_pages: Annotated[bool, typer.Option("--all", help="Fetch all pages.")] = False,
) -> None:
    """List collective identifiers that reference one KSeF invoice."""

    def operation() -> list[CollectiveIdentifierReference]:
        def list_references(
            auth: AuthenticatedClient,
        ) -> list[CollectiveIdentifierReference]:
            pager = auth.collective_identifiers.list_for_invoice(
                ksef_number, params=CollectiveIdentifierParams(page_size=page_size)
            )
            return list(pager) if all_pages else pager.first_page()

        return run_authenticated(ctx, list_references)

    run_command(ctx, operation)


@app.command("list-invoices")
def collective_list_invoices(
    ctx: typer.Context,
    numbers: Annotated[
        list[str],
        typer.Argument(help="Collective identifier number(s); up to 10 per request."),
    ],
    page_size: Annotated[int, typer.Option("--page-size", min=10, max=200)] = 10,
    all_pages: Annotated[bool, typer.Option("--all", help="Fetch all pages.")] = False,
) -> None:
    """List the invoices grouped under collective identifiers."""

    def operation() -> list[CollectiveIdentifierInvoiceDetails]:
        if len(numbers) > _MAX_IDS_PER_INVOICE_QUERY:
            raise ValueError(
                f"KSeF accepts at most {_MAX_IDS_PER_INVOICE_QUERY} collective "
                "identifier numbers per invoice listing; run separate commands "
                "for the rest."
            )

        def list_invoices(
            auth: AuthenticatedClient,
        ) -> list[CollectiveIdentifierInvoiceDetails]:
            pager = auth.collective_identifiers.list_invoices(
                numbers, params=CollectiveIdentifierParams(page_size=page_size)
            )
            return list(pager) if all_pages else pager.first_page()

        return run_authenticated(ctx, list_invoices)

    run_command(ctx, operation)


def _generate_inputs(
    ctx: typer.Context, invoices_file: Path | None, invoice: list[str]
) -> list[CollectiveIdentifierInvoice]:
    """Merge JSON-file invoices with repeated --invoice KSeF numbers."""

    from_file = (
        []
        if invoices_file is None
        else list(read_model(ctx, invoices_file, CollectiveIdentifierInvoiceList).root)
    )
    invoices = [
        *from_file,
        *(CollectiveIdentifierInvoice(ksef_number=value) for value in invoice),
    ]
    if not invoices:
        raise ValueError("Provide at least one --invoice or an --invoices-file.")
    return invoices
