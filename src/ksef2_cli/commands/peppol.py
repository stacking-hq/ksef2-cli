"""Public PEPPOL provider command group."""

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
        with create_client(ctx) as client:
            params = _offset_params(page_size, page_offset)
            if all_pages:
                return list(client.peppol.all(params=params))
            return client.peppol.query(params=params)

    _render(
        ctx,
        run_command(ctx, operation),
        title="PEPPOL Providers",
        items_key="providers",
        fields=["id", "name", "date_created"],
    )
