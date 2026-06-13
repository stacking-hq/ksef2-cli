"""Authentication command group."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Annotated, Any

import typer
from pydantic import BaseModel

from ksef2_cli.config import FORM_SCHEMA_NAMES
from ksef2_cli.context import authenticate_client, create_client, fail, run_command
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

app = typer.Typer(help='Authenticate and refresh KSeF access tokens.')


@app.command("login")
def auth_login(ctx: typer.Context) -> None:
    """Authenticate with the configured method and print access/refresh tokens."""

    def operation() -> Any:
        with create_client(ctx) as client:
            auth = authenticate_client(ctx, client)
            return auth.auth_tokens

    _render(ctx, run_command(ctx, operation), title="Auth Tokens")


@app.command("refresh")
def auth_refresh(
    ctx: typer.Context,
    refresh_token: Annotated[
        str | None,
        typer.Option("--refresh-token", envvar="KSEF2_REFRESH_TOKEN", help="Refresh token."),
    ] = None,
) -> None:
    """Exchange a refresh token for a new access token."""

    def operation() -> Any:
        if not refresh_token:
            fail("Provide --refresh-token or KSEF2_REFRESH_TOKEN.")
        with create_client(ctx) as client:
            return client.authentication.refresh(refresh_token=refresh_token)

    _render(ctx, run_command(ctx, operation), title="Refreshed Token")
