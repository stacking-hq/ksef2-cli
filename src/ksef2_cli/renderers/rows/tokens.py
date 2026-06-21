"""Plain-text handlers for token responses."""

from ksef2.domain.models.tokens import (
    GenerateTokenResponse,
    QueryTokensResponse,
    TokenAuthorIdentifier,
    TokenContextIdentifier,
    TokenInfo,
    TokenStatusResponse,
)

from ksef2_cli.renderers.text import (
    PlainTextRenderer,
    format_fields,
    format_row,
    register_text,
)


def register() -> None:
    @register_text(GenerateTokenResponse)
    def _(value: GenerateTokenResponse, renderer: PlainTextRenderer) -> str:
        return format_fields(
            (
                ("reference_number", value.reference_number),
                ("token", value.token),
            )
        )

    @register_text(TokenStatusResponse)
    def _(value: TokenStatusResponse, renderer: PlainTextRenderer) -> str:
        return format_fields(
            (
                ("reference_number", value.reference_number),
                ("status", value.status),
            )
        )

    @register_text(QueryTokensResponse)
    def _(value: QueryTokensResponse, renderer: PlainTextRenderer) -> str:
        return renderer.render(value.tokens)

    @register_text(TokenInfo)
    def _(value: TokenInfo, renderer: PlainTextRenderer) -> str:
        return format_row(
            (
                ("reference_number", value.reference_number),
                ("status", value.status),
                ("description", value.description),
                ("author_identifier", _identifier(value.author_identifier)),
                ("context_identifier", _identifier(value.context_identifier)),
                ("requested_permissions", value.requested_permissions),
                ("date_created", value.date_created),
                ("last_use_date", value.last_use_date),
                ("status_details", value.status_details),
            )
        )


def _identifier(value: TokenAuthorIdentifier | TokenContextIdentifier) -> str:
    return f"{value.type}:{value.value}"
