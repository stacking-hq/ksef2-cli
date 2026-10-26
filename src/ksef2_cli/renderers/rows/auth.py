"""Plain-text handlers for authentication responses."""

from datetime import datetime

from ksef2.models import AuthTokens, RefreshedToken, TokenCredentials
from pydantic import BaseModel

from ksef2_cli.renderers.text import PlainTextRenderer, format_fields, register_text


class MaskedTokenCredentials(BaseModel):
    token: str = "**********"
    valid_until: datetime


class MaskedAuthTokens(BaseModel):
    access_token: MaskedTokenCredentials
    refresh_token: MaskedTokenCredentials
    hint: str = "Use auth login --save-state FILE to retain resumable credentials."


class MaskedRefreshedToken(BaseModel):
    access_token: MaskedTokenCredentials


def register() -> None:
    @register_text(MaskedTokenCredentials)
    @register_text(TokenCredentials)
    def _(value: TokenCredentials | MaskedTokenCredentials, renderer: PlainTextRenderer) -> str:
        return format_fields(
            (
                ("token", "**********"),
                ("valid_until", value.valid_until),
            )
        )

    @register_text(MaskedAuthTokens)
    @register_text(AuthTokens)
    def _(value: AuthTokens | MaskedAuthTokens, renderer: PlainTextRenderer) -> str:
        return format_fields(
            (
                ("access_token", "**********"),
                ("access_token_valid_until", value.access_token.valid_until),
                ("refresh_token", "**********"),
                ("refresh_token_valid_until", value.refresh_token.valid_until),
                ("hint", "Use auth login --save-state FILE to retain resumable credentials."),
            )
        )

    @register_text(MaskedRefreshedToken)
    @register_text(RefreshedToken)
    def _(value: RefreshedToken | MaskedRefreshedToken, renderer: PlainTextRenderer) -> str:
        return format_fields(
            (
                ("access_token", "**********"),
                ("access_token_valid_until", value.access_token.valid_until),
            )
        )
