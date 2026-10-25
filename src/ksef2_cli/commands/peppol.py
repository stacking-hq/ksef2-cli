"""Public PEPPOL provider command group."""

from typing import Annotated

import typer
from ksef2 import Client
from ksef2.models import OffsetPaginationParams, PeppolProvider

from ksef2_cli.context import run_client, run_command
from ksef2_cli.parsing import validate_offset_pagination

app = typer.Typer(help="Query public PEPPOL providers.")


@app.command("providers")
def peppol_providers(
    ctx: typer.Context,
    all_pages: Annotated[bool, typer.Option("--all", help="Fetch all pages.")] = False,
    page_size: Annotated[
        int,
        typer.Option(
            "--page-size",
            min=10,
            max=100,
            help="Items per API request, including with --all.",
        ),
    ] = 10,
    page_offset: Annotated[
        int,
        typer.Option(
            "--page-offset",
            min=0,
            help="Offset for a single page; must be 0 with --all.",
        ),
    ] = 0,
) -> None:
    """List PEPPOL providers."""

    def list_providers(client: Client) -> list[PeppolProvider]:
        params = OffsetPaginationParams(page_size=page_size, page_offset=page_offset)

        pager = client.peppol.list(params=params)
        if all_pages:
            return list(pager)
        return pager.first_page()

    def operation() -> list[PeppolProvider]:
        validate_offset_pagination(all_pages=all_pages, page_offset=page_offset)
        return run_client(ctx, list_providers)

    run_command(ctx, operation)
