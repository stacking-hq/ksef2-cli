"""Plain-text handlers for authentication responses."""

from ksef2.domain.models.auth import AuthTokens, RefreshedToken, TokenCredentials

from ksef2_cli.renderers.text import PlainTextRenderer, format_fields, register_text


def register() -> None:
    @register_text(TokenCredentials)
    def _(value: TokenCredentials, renderer: PlainTextRenderer) -> str:
        return format_fields(
            (
                ("token", value.token),
                ("valid_until", value.valid_until),
            )
        )

    @register_text(AuthTokens)
    def _(value: AuthTokens, renderer: PlainTextRenderer) -> str:
        return format_fields(
            (
                ("access_token", value.access_token.token),
                ("access_token_valid_until", value.access_token.valid_until),
                ("refresh_token", value.refresh_token.token),
                ("refresh_token_valid_until", value.refresh_token.valid_until),
            )
        )

    @register_text(RefreshedToken)
    def _(value: RefreshedToken, renderer: PlainTextRenderer) -> str:
        return format_fields(
            (
                ("access_token", value.access_token.token),
                ("access_token_valid_until", value.access_token.valid_until),
            )
        )
