"""Public PEPPOL provider command group."""

from __future__ import annotations

from typing import Annotated, Any

import typer

from ksef2_cli.context import run_client, run_command
from ksef2_cli.rendering import _render
from ksef2_cli.sdk_models import (
    _offset_params,
)

app = typer.Typer(help='Query public PEPPOL providers.')


@app.command("providers")
def peppol_providers(
    ctx: typer.Context,
    all_pages: Annotated[bool, typer.Option("--all", help="Fetch all pages.")] = False,
    page_size: Annotated[int, typer.Option("--page-size", min=10, max=100)] = 10,
    page_offset: Annotated[int, typer.Option("--page-offset", min=0)] = 0,
) -> None:
    """List PEPPOL providers."""

    def operation() -> Any:
        params = _offset_params(page_size, page_offset)

        def query_providers(client: Any) -> Any:
            if all_pages:
                return list(client.peppol.all(params=params))
            return client.peppol.query(params=params)

        return run_client(ctx, query_providers)

    _render(
        ctx,
        run_command(ctx, operation),
        title="PEPPOL Providers",
        items_key="providers",
        fields=["id", "name", "date_created"],
    )
