"""Display authentication tokens without changing SDK or saved credentials."""

from ksef2.models import AuthTokens

from ksef2_cli.results import AuthTokenOutput


def mask_token(token: str) -> str:
    """Show only the first eight and last four characters of a bearer token."""
    return f"{token[:8]}…{token[-4:]}" if len(token) > 8 else "**********"


def auth_token_fields(value: AuthTokenOutput) -> dict[str, object]:
    """Build the common text and JSON auth output fields."""
    show = value.show_tokens and value.state_file is None
    tokens = value.tokens
    fields: dict[str, object] = {
        "access_token": tokens.access_token.token
        if show
        else mask_token(tokens.access_token.token),
        "access_token_valid_until": tokens.access_token.valid_until,
    }
    if isinstance(tokens, AuthTokens):
        fields["refresh_token"] = (
            tokens.refresh_token.token
            if show
            else mask_token(tokens.refresh_token.token)
        )
        fields["refresh_token_valid_until"] = tokens.refresh_token.valid_until
    if value.state_file is not None:
        fields["state_file"] = value.state_file
    return fields
