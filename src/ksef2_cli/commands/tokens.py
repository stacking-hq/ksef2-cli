"""KSeF authorization token command group."""

from typing import Annotated

import typer
from ksef2.clients import AuthenticatedClient
from ksef2.models import (
    TokenAuthorIdentifierTypeEnum,
    TokenInfo,
    TokenListParams,
    TokenPermissionEnum,
    TokenStatus,
    TokenStatusEnum,
    TokenStatusResponse,
)

from ksef2_cli.context import get_settings, run_authenticated_command
from ksef2_cli.results import ActionResult, GeneratedToken

app = typer.Typer(help="Manage KSeF authorization tokens.")


@app.command("generate")
def tokens_generate(
    ctx: typer.Context,
    description: Annotated[
        str, typer.Option("--description", help="Token description.")
    ],
    permissions: Annotated[
        list[TokenPermissionEnum],
        typer.Option(
            "--permission",
            "--permissions",
            help="Permission to grant. Repeat for multiple permissions.",
        ),
    ] = [],
    wait: Annotated[
        bool,
        typer.Option("--wait", help="Wait for the token to become active."),
    ] = False,
) -> None:
    """Generate a new KSeF authorization token."""

    def validate() -> None:
        if not permissions:
            raise ValueError("At least one --permission is required.")

    def generate_token(auth: AuthenticatedClient) -> GeneratedToken:
        # KSeF shows the token value only once, so it is read off the handle
        # before any polling that can fail.
        generated = auth.tokens.generate(
            permissions=[permission.value for permission in permissions],
            description=description,
        )
        status: TokenStatus | None = None
        if wait:
            settings = get_settings(ctx)
            status = generated.wait(
                timeout=settings.effective_auth_timeout,
                poll_interval=settings.effective_poll_interval,
            ).status
        return GeneratedToken(
            reference_number=generated.reference_number,
            token=generated.token,
            status=status,
        )

    run_authenticated_command(
        ctx,
        generate_token,
        validate=validate,
    )


@app.command("list")
def tokens_list(
    ctx: typer.Context,
    status: Annotated[
        list[TokenStatusEnum],
        typer.Option("--status", help="Token status filter. Repeat for multiple."),
    ] = [],
    description: Annotated[str | None, typer.Option("--description")] = None,
    author_identifier: Annotated[
        str | None, typer.Option("--author-identifier")
    ] = None,
    author_identifier_type: Annotated[
        TokenAuthorIdentifierTypeEnum | None, typer.Option("--author-identifier-type")
    ] = None,
    page_size: Annotated[int, typer.Option("--page-size", min=10, max=100)] = 10,
    all_pages: Annotated[bool, typer.Option("--all", help="Fetch all pages.")] = False,
) -> None:
    """List KSeF authorization tokens."""

    def list_tokens(auth: AuthenticatedClient) -> list[TokenInfo]:
        params = TokenListParams(
            status=[item.value for item in status] or None,
            description=description,
            author_identifier=author_identifier,
            author_identifier_type=author_identifier_type.value
            if author_identifier_type
            else None,
            page_size=page_size,
        )
        pager = auth.tokens.list(params=params)
        if all_pages:
            return list(pager)
        return pager.first_page()

    run_authenticated_command(ctx, list_tokens)


@app.command("status")
def tokens_status(
    ctx: typer.Context,
    reference_number: Annotated[str, typer.Option("--reference")],
) -> None:
    """Fetch token status."""

    def get_status(auth: AuthenticatedClient) -> TokenStatusResponse:
        return auth.tokens.get_status(reference_number=reference_number)

    run_authenticated_command(ctx, get_status)


@app.command("revoke")
def tokens_revoke(
    ctx: typer.Context,
    reference_number: Annotated[str, typer.Option("--reference")],
) -> None:
    """Revoke a KSeF authorization token."""

    def revoke_token(auth: AuthenticatedClient) -> ActionResult:
        auth.tokens.revoke(reference_number=reference_number)
        return ActionResult(reference_number=reference_number, revoked=True)

    run_authenticated_command(ctx, revoke_token)
