"""KSeF authorization token command group."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Annotated, Any

import typer
from pydantic import BaseModel

from ksef2_cli.config import FORM_SCHEMA_NAMES
from ksef2_cli.context import get_authenticated_client, run_command
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

app = typer.Typer(help='Manage KSeF authorization tokens.')


@app.command("generate")
def tokens_generate(
    ctx: typer.Context,
    description: Annotated[str, typer.Option("--description", help="Token description.")],
    permission: Annotated[
        list[str],
        typer.Option("--permission", help="Permission to grant. Repeat for multiple permissions."),
    ] = [],
) -> None:
    """Generate a new KSeF authorization token."""

    def operation() -> Any:
        if not permission:
            raise ValueError("At least one --permission is required.")
        runtime = get_authenticated_client(ctx)
        client, auth = runtime.client, runtime.auth
        with client:
            return auth.tokens.generate(permissions=permission, description=description)

    _render(ctx, run_command(ctx, operation), title="Generated Token")


@app.command("list")
def tokens_list(
    ctx: typer.Context,
    status: Annotated[list[str], typer.Option("--status", help="Token status filter. Repeat for multiple.")] = [],
    description: Annotated[str | None, typer.Option("--description")] = None,
    author_identifier: Annotated[str | None, typer.Option("--author-identifier")] = None,
    author_identifier_type: Annotated[str | None, typer.Option("--author-identifier-type")] = None,
    page_size: Annotated[int, typer.Option("--page-size", min=10, max=100)] = 10,
    all_pages: Annotated[bool, typer.Option("--all", help="Fetch all pages.")] = False,
) -> None:
    """List KSeF authorization tokens."""

    def operation() -> Any:
        from ksef2.domain.models.pagination import TokenListParams

        params = TokenListParams(
            status=status or None,
            description=description,
            author_identifier=author_identifier,
            author_identifier_type=author_identifier_type,
            page_size=page_size,
        )
        runtime = get_authenticated_client(ctx)
        client, auth = runtime.client, runtime.auth
        with client:
            if all_pages:
                pages = list(auth.tokens.list_all(params=params))
                return [token for page in pages for token in page.tokens]
            return auth.tokens.list_page(params=params)

    _render(
        ctx,
        run_command(ctx, operation),
        title="Tokens",
        items_key="tokens",
        fields=["reference_number", "status", "description", "date_created", "last_use_date"],
    )


@app.command("status")
def tokens_status(
    ctx: typer.Context,
    reference_number: Annotated[str, typer.Option("--reference")],
) -> None:
    """Fetch token status."""

    def operation() -> Any:
        runtime = get_authenticated_client(ctx)
        client, auth = runtime.client, runtime.auth
        with client:
            return auth.tokens.status(reference_number=reference_number)

    _render(ctx, run_command(ctx, operation), title="Token Status")


@app.command("revoke")
def tokens_revoke(
    ctx: typer.Context,
    reference_number: Annotated[str, typer.Option("--reference")],
) -> None:
    """Revoke a KSeF authorization token."""

    def operation() -> dict[str, str]:
        runtime = get_authenticated_client(ctx)
        client, auth = runtime.client, runtime.auth
        with client:
            auth.tokens.revoke(reference_number=reference_number)
        return {"reference_number": reference_number, "revoked": "true"}

    _render(ctx, run_command(ctx, operation), title="Revoked Token")
