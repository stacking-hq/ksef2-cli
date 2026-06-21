"""Public PEPPOL provider command group."""

from typing import Annotated

import typer
from ksef2 import Client
from ksef2.domain.models.pagination import OffsetPaginationParams
from ksef2.domain.models.peppol import ListPeppolProvidersResponse, PeppolProvider

from ksef2_cli.context import run_client_command

app = typer.Typer(help="Query public PEPPOL providers.")


@app.command("providers")
def peppol_providers(
    ctx: typer.Context,
    all_pages: Annotated[bool, typer.Option("--all", help="Fetch all pages.")] = False,
    page_size: Annotated[int, typer.Option("--page-size", min=10, max=100)] = 10,
    page_offset: Annotated[int, typer.Option("--page-offset", min=0)] = 0,
) -> None:
    """List PEPPOL providers."""

    def query_providers(
        client: Client,
    ) -> ListPeppolProvidersResponse | list[PeppolProvider]:
        params = OffsetPaginationParams(page_size=page_size, page_offset=page_offset)

        if all_pages:
            return list(client.peppol.all(params=params))
        return client.peppol.query(params=params)

    run_client_command(ctx, query_providers)
