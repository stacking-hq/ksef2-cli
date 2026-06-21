"""Public encryption certificate command group."""

from typing import Annotated

import typer
from ksef2 import Client
from ksef2.domain.models.encryption import (
    CertUsage,
    CertUsageEnum,
    PublicKeyCertificate,
)

from ksef2_cli.context import run_client_command

app = typer.Typer(help="Read public KSeF encryption certificates.")


@app.command("certificates")
def encryption_certificates(
    ctx: typer.Context,
    usage: Annotated[
        list[CertUsageEnum],
        typer.Option(
            "--usage", help="Certificate usage filter. Repeat for multiple usages."
        ),
    ] = [],
) -> None:
    """List public KSeF encryption certificates."""

    requested_usage: list[CertUsage] | None = (
        [value.value for value in usage] if usage else None
    )

    def list_certificates(client: Client) -> list[PublicKeyCertificate]:
        return client.encryption.get_certificates(usage=requested_usage)

    run_client_command(ctx, list_certificates)
