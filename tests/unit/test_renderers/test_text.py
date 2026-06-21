from datetime import UTC, datetime

import pytest
from ksef2.domain.models.auth import AuthTokens, RefreshedToken, TokenCredentials
from ksef2.domain.models.certificates import CertificateLimitsResponse
from ksef2.domain.models.invoices import ExportHandle
from ksef2.domain.models.peppol import ListPeppolProvidersResponse, PeppolProvider
from ksef2.domain.models.tokens import (
    GenerateTokenResponse,
    QueryTokensResponse,
    TokenAuthorIdentifier,
    TokenContextIdentifier,
    TokenInfo,
    TokenStatusResponse,
)
from pydantic import BaseModel

from ksef2_cli.commands.invoices.models import ExportHandleSaved, ExportPaths
from ksef2_cli.config import (
    CliConfig,
    ProfileAuthConfig,
    ProfileAuthType,
    ProfileConfig,
)
from ksef2_cli.renderers.text import plain_renderer
from ksef2_cli.results import (
    ActionResult,
    CertificateRevoked,
    ConfigInitialized,
    ConfigPathResult,
    ConfigShowResult,
    CurrentSessionTerminated,
    LimitReset,
    LimitUpdated,
    ProductionRateLimitsSet,
    SavedFile,
    SessionClosed,
)


def test_token_response_text_handlers() -> None:
    assert (
        plain_renderer.render(
            GenerateTokenResponse(reference_number="token-ref", token="secret")
        )
        == "reference_number: token-ref\ntoken: secret"
    )
    assert (
        plain_renderer.render(
            TokenStatusResponse(reference_number="token-ref", status="active")
        )
        == "reference_number: token-ref\nstatus: active"
    )


def test_token_list_text_uses_row_handlers_and_list_recursion() -> None:
    first = _token_info("token-1")
    second = _token_info("token-2")

    text = plain_renderer.render(
        QueryTokensResponse(continuation_token=None, tokens=[first, second])
    )

    assert text.splitlines() == [
        (
            "reference_number=token-1 status=active description=demo "
            "author_identifier=nip:5261040828 context_identifier=nip:5261040828 "
            "requested_permissions=invoice_read date_created=2026-01-02T00:00:00+00:00"
        ),
        (
            "reference_number=token-2 status=active description=demo "
            "author_identifier=nip:5261040828 context_identifier=nip:5261040828 "
            "requested_permissions=invoice_read date_created=2026-01-02T00:00:00+00:00"
        ),
    ]
    assert plain_renderer.render([first, second]) == text


def test_peppol_text_handlers() -> None:
    provider = PeppolProvider(
        id="PPL123456",
        name="Provider",
        date_created=datetime(2026, 1, 2, tzinfo=UTC),
    )

    assert plain_renderer.render(provider) == (
        "id=PPL123456 name=Provider date_created=2026-01-02T00:00:00+00:00"
    )
    assert plain_renderer.render(
        ListPeppolProvidersResponse(providers=[provider], has_more=False)
    ) == plain_renderer.render(provider)


def test_auth_text_handlers() -> None:
    refreshed = RefreshedToken(
        access_token=TokenCredentials(
            token="access",
            valid_until=datetime(2026, 1, 2, tzinfo=UTC),
        )
    )
    auth_tokens = AuthTokens(
        access_token=refreshed.access_token,
        refresh_token=TokenCredentials(
            token="refresh",
            valid_until=datetime(2026, 1, 3, tzinfo=UTC),
        ),
    )

    assert plain_renderer.render(refreshed) == (
        "access_token: access\naccess_token_valid_until: 2026-01-02T00:00:00+00:00"
    )
    assert plain_renderer.render(auth_tokens) == (
        "access_token: access\n"
        "access_token_valid_until: 2026-01-02T00:00:00+00:00\n"
        "refresh_token: refresh\n"
        "refresh_token_valid_until: 2026-01-03T00:00:00+00:00"
    )


def test_action_result_text_uses_yes_no() -> None:
    assert plain_renderer.render(
        ActionResult(reference_number="token-ref", revoked=True)
    ) == ("reference_number: token-ref\nrevoked: yes")


def test_cli_action_models_text_use_yes_no() -> None:
    assert plain_renderer.render(LimitUpdated(kind="api")) == "kind: api\nupdated: yes"
    assert (
        plain_renderer.render(LimitReset(kind="session")) == "kind: session\nreset: yes"
    )
    assert (
        plain_renderer.render(ProductionRateLimitsSet())
        == "api_rate_limits: production"
    )
    assert plain_renderer.render(SessionClosed(reference_number="session-ref")) == (
        "reference_number: session-ref\nclosed: yes"
    )
    assert (
        plain_renderer.render(CurrentSessionTerminated()) == "terminated_current: yes"
    )
    assert plain_renderer.render(
        CertificateRevoked(serial_number="ABCDEF1234567890", reason="superseded")
    ) == ("serial_number: ABCDEF1234567890\nreason: superseded\nrevoked: yes")


def test_config_result_models_text(tmp_path) -> None:
    config = CliConfig(
        active_profile="demo",
        profiles={
            "demo": ProfileConfig(
                environment="test",
                nip="5261040828",
                auth=ProfileAuthConfig(type=ProfileAuthType.test_certificate),
            )
        },
    )

    assert plain_renderer.render(
        ConfigPathResult(path=tmp_path / "config.toml", exists=False, loaded=False)
    ) == (f"path: {tmp_path / 'config.toml'}\nexists: no\nloaded: no")
    assert plain_renderer.render(
        ConfigShowResult(path=tmp_path / "config.toml", exists=True, config=config)
    ).startswith(f"path: {tmp_path / 'config.toml'}\nexists: yes\nconfig: ")
    assert plain_renderer.render(
        ConfigInitialized(path=tmp_path / "config.toml", mode="0600", config=config)
    ).startswith(f"path: {tmp_path / 'config.toml'}\nmode: 0600\nconfig: ")


def test_saved_file_text_uses_path_and_bytes(tmp_path) -> None:
    assert plain_renderer.render(SavedFile(path=tmp_path / "upo.xml", size=42)) == (
        f"path: {tmp_path / 'upo.xml'}\nbytes: 42"
    )


def test_export_handle_text_includes_saved_handle_path(tmp_path) -> None:
    handle = ExportHandle(reference_number="export-ref", aes_key=b"abc", iv=b"def")

    assert plain_renderer.render(
        ExportHandleSaved.from_handle(handle, handle_file=tmp_path / "handle.json")
    ) == (
        "reference_number: export-ref\n"
        "aes_key: YWJj\n"
        "iv: ZGVm\n"
        f"handle_file: {tmp_path / 'handle.json'}"
    )


def test_export_paths_text_lists_paths_only(tmp_path) -> None:
    assert (
        plain_renderer.render(
            ExportPaths(
                reference_number="export-ref",
                paths=[tmp_path / "first.xml", tmp_path / "second.xml"],
            )
        )
        == f"{tmp_path / 'first.xml'}\n{tmp_path / 'second.xml'}"
    )


def test_mapping_cell_text_uses_explicit_json_conversions() -> None:
    assert plain_renderer.render(
        {"nested": {"created_at": datetime(2026, 1, 2, tzinfo=UTC)}}
    ) == ('nested: {"created_at":"2026-01-02T00:00:00Z"}')


def test_sdk_model_text_uses_field_fallback() -> None:
    result = CertificateLimitsResponse(
        can_request=True,
        enrollment_limit=10,
        enrollment_remaining=9,
        certificate_limit=5,
        certificate_remaining=4,
    )

    assert plain_renderer.render(result) == (
        "can_request: yes\n"
        "enrollment_limit: 10\n"
        "enrollment_remaining: 9\n"
        "certificate_limit: 5\n"
        "certificate_remaining: 4"
    )


def test_unregistered_pydantic_model_has_no_plain_text_fallback() -> None:
    class UnknownResult(BaseModel):
        name: str

    with pytest.raises(TypeError, match="No plain-text renderer registered"):
        plain_renderer.render(UnknownResult(name="demo"))


def _token_info(reference_number: str) -> TokenInfo:
    return TokenInfo(
        reference_number=reference_number,
        author_identifier=TokenAuthorIdentifier(type="nip", value="5261040828"),
        context_identifier=TokenContextIdentifier(type="nip", value="5261040828"),
        description="demo",
        requested_permissions=["invoice_read"],
        date_created=datetime(2026, 1, 2, tzinfo=UTC),
        last_use_date=None,
        status="active",
        status_details=None,
    )
