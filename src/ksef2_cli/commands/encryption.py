"""Public encryption certificate command group."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Annotated, Any

import typer
from pydantic import BaseModel

from ksef2_cli.config import FORM_SCHEMA_NAMES
from ksef2_cli.context import create_client, run_command
from ksef2_cli.io import _read_model, _write_json
from ksef2_cli.parsing import _parse_form_schema, _parse_optional_bool, _safe_filename
from ksef2_cli.rendering import _render
from ksef2_cli.sdk_models import (
    _batch_session_ref,
    _build_invoice_filter,
    _export_handle_to_dict,
    _invoice_metadata_params,
    _load_export_handle,
    _offset_params,
    _state_from_file,
)

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
        with create_client(ctx) as client:
            return client.encryption.get_certificates(usage=usage or None)

    _render(
        ctx,
        run_command(ctx, operation),
        title="Encryption Certificates",
        fields=["public_key_id", "usage", "valid_from", "valid_to"],
    )
