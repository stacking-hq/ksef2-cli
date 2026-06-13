"""Public encryption certificate command group."""

from __future__ import annotations

from typing import Annotated, Any

import typer

from ksef2_cli.context import run_client, run_command
from ksef2_cli.rendering import _render

app = typer.Typer(help='Read public KSeF encryption certificates.')


@app.command("certificates")
def encryption_certificates(
    ctx: typer.Context,
    usage: Annotated[
        list[str],
        typer.Option("--usage", help="Certificate usage filter. Repeat for multiple usages."),
    ] = [],
) -> None:
    """List public KSeF encryption certificates."""

    def operation() -> Any:
        return run_client(
            ctx,
            lambda client: client.encryption.get_certificates(usage=usage or None),
        )

    _render(
        ctx,
        run_command(ctx, operation),
        title="Encryption Certificates",
        fields=["public_key_id", "usage", "valid_from", "valid_to"],
    )
