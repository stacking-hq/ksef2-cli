"""KSeF authorization token command group."""

from __future__ import annotations

from typing import Annotated, Any

import typer

from ksef2_cli.context import run_authenticated, run_command
from ksef2_cli.rendering import _render

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
        return run_authenticated(
            ctx,
            lambda auth: auth.tokens.generate(permissions=permission, description=description),
        )

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
        def list_tokens(auth: Any) -> Any:
            if all_pages:
                pages = list(auth.tokens.list_all(params=params))
                return [token for page in pages for token in page.tokens]
            return auth.tokens.list_page(params=params)

        return run_authenticated(ctx, list_tokens)

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
        return run_authenticated(
            ctx,
            lambda auth: auth.tokens.status(reference_number=reference_number),
        )

    _render(ctx, run_command(ctx, operation), title="Token Status")


@app.command("revoke")
def tokens_revoke(
    ctx: typer.Context,
    reference_number: Annotated[str, typer.Option("--reference")],
) -> None:
    """Revoke a KSeF authorization token."""

    def operation() -> dict[str, str]:
        run_authenticated(
            ctx,
            lambda auth: auth.tokens.revoke(reference_number=reference_number),
        )
        return {"reference_number": reference_number, "revoked": "true"}

    _render(ctx, run_command(ctx, operation), title="Revoked Token")
