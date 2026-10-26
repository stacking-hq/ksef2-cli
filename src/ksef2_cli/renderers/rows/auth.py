"""Plain-text handlers for authentication responses."""

from ksef2.models import AuthTokens, RefreshedToken, TokenCredentials

from ksef2_cli.renderers.auth import auth_token_fields
from ksef2_cli.results import AuthTokenOutput
from ksef2_cli.renderers.text import PlainTextRenderer, format_fields, register_text


def register() -> None:
    @register_text(AuthTokenOutput)
    def _(value: AuthTokenOutput, renderer: PlainTextRenderer) -> str:
        return format_fields(auth_token_fields(value).items())

    @register_text(TokenCredentials)
    def _(value: TokenCredentials, renderer: PlainTextRenderer) -> str:
        return format_fields(
            (
                ("token", "**********"),
                ("valid_until", value.valid_until),
            )
        )

    @register_text(AuthTokens)
    def _(value: AuthTokens, renderer: PlainTextRenderer) -> str:
        return format_fields(
            (
                ("access_token", "**********"),
                ("access_token_valid_until", value.access_token.valid_until),
                ("refresh_token", "**********"),
                ("refresh_token_valid_until", value.refresh_token.valid_until),
                (
                    "hint",
                    "Use auth login --save-state FILE to retain resumable credentials.",
                ),
            )
        )

    @register_text(RefreshedToken)
    def _(value: RefreshedToken, renderer: PlainTextRenderer) -> str:
        return format_fields(
            (
                ("access_token", "**********"),
                ("access_token_valid_until", value.access_token.valid_until),
            )
        )
