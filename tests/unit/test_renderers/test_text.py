from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from ksef2.models import (
    AuthTokens,
    CertificateLimitsResponse,
    ExportResumeState,
    ListPeppolProvidersResponse,
    PeppolProvider,
    QueryTokensResponse,
    RefreshedToken,
    TokenAuthorIdentifier,
    TokenContextIdentifier,
    TokenCredentials,
    TokenInfo,
    TokenStatusResponse,
)
from pydantic import BaseModel
from rich.cells import cell_len

from ksef2_cli.commands.invoices.models import (
    ExportHandleSaved,
    ExportPaths,
    InvoicesStatusResult,
)
from ksef2.profiles import (
    CliProfileConfig,
    ProfileAuthConfig,
    ProfileAuthType,
    ProfileConfig,
)
from ksef2_cli.renderers import text as text_renderer
from ksef2_cli.renderers.text import (
    MINIMUM_WIDTH,
    UNBOUNDED_WIDTH,
    content_width,
    format_cell,
    format_fields,
    format_status_line,
    plain_renderer,
)
from ksef2_cli.results import (
    ActionResult,
    CertificateRevoked,
    ConfigInitialized,
    ConfigPathResult,
    ConfigShowResult,
    CurrentSessionTerminated,
    GeneratedToken,
    LimitReset,
    LimitUpdated,
    ProductionRateLimitsSet,
    SavedFile,
    SessionClosed,
)


def test_token_response_text_handlers() -> None:
    assert (
        plain_renderer.render(
            GeneratedToken(reference_number="token-ref", token="secret")
        )
        == "reference_number: token-ref\ntoken: secret"
    )
    assert (
        plain_renderer.render(
            TokenStatusResponse(reference_number="token-ref", status="active")
        )
        == "reference_number: token-ref\nstatus: active"
    )
    assert (
        plain_renderer.render(
            GeneratedToken(
                reference_number="token-ref", token="secret", status="active"
            )
        )
        == "reference_number: token-ref\ntoken: secret\nstatus: active"
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
    config = CliProfileConfig(
        active_profile="demo",
        profiles={
            "demo": ProfileConfig(
                environment="test",
                nip="5261040828",
                auth=ProfileAuthConfig(type=ProfileAuthType.TEST_CERTIFICATE),
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


def test_export_handle_text_redacts_secrets_and_includes_saved_handle_path(tmp_path) -> None:
    state = ExportResumeState(
        reference_number="export-ref",
        aes_key="AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=",
        iv="AAAAAAAAAAAAAAAAAAAAAA==",
    )
    assert plain_renderer.render(
        ExportHandleSaved(state=state, handle_file=tmp_path / "handle.json")
    ) == (
        'state: {"format_version":"1","reference_number":"export-ref",'
        '"aes_key":"**********","iv":"**********"}\n'
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


# A record is one line per field only while it fits. The QA run that found the overflow
# measured the two widest shapes it met: a status line whose receipt path and
# identifiers cannot be shortened, and an inspector section of nested groups.
_STATUS_FIELDS = [
    (
        "reference_number",
        "5926ad107b01e605f9ebb4cbca0080fea655114b8ca67168543dc7ca3bb2eeee",
    ),
    ("ksef_number", "ksef-612701234567-2411BF0003"),
    ("status_code", 200),
    ("status_description", "ready"),
    (
        "invoice_hash",
        "611794e076930544b7f61ce0bd861007284bcabf915ec19b8fcad4668aac5606",
    ),
]
_STATUS_RECEIPT = Path("/tmp/ksef2-cli-qa/qa-artifacts/local_invoices/status-80.json")
_BODY = {
    "invoice_number": "FV/2026/04/0001",
    "invoice_type": "Faktura podstawowa",
    "summary_overrides": {"base_rate_net_total": "1000.00", "total_gross": "1230.00"},
    "rows": [
        {
            "name": "Usługa konsultingowa, której nazwa nie mieści się w wierszu",
            "gross_amount": "12299999987700.00",
            "vat_classification": {"treatment": "taxable", "rate": "23"},
        }
    ],
}


@pytest.mark.parametrize("width", [20, 40, 60, 80, 120, 200])
def test_status_line_fits_the_width_it_was_given(width: int) -> None:
    text = format_status_line("accepted", _STATUS_RECEIPT, _STATUS_FIELDS, width=width)

    assert max(cell_len(line) for line in text.splitlines()) <= width
    assert _whole(text) == _whole(_unwrapped_status_line())


@pytest.mark.parametrize("width", [20, 40, 60, 80, 120, 200])
def test_fields_fit_the_width_they_were_given(width: int) -> None:
    text = format_fields(
        [("body", _BODY), ("path", _STATUS_RECEIPT), ("narrow", "日本語の文字")],
        width=width,
    )

    assert max(cell_len(line) for line in text.splitlines()) <= width
    unwrapped = (
        f"body: {format_cell(_BODY)}\npath: {_STATUS_RECEIPT}\nnarrow: 日本語の文字"
    )
    assert _whole(text) == _whole(unwrapped)


def test_a_record_that_fits_is_still_one_line_per_field() -> None:
    receipt = Path("/tmp/receipt.json")

    assert format_status_line("accepted", receipt, _STATUS_FIELDS[:1], width=200) == (
        f"accepted  {receipt}  reference_number={_STATUS_FIELDS[0][1]}"
    )


def test_a_long_value_starts_on_the_line_after_its_name() -> None:
    text = format_fields([("receipt_file", _STATUS_RECEIPT)], width=40)

    assert text.splitlines() == [
        "receipt_file:",
        "  /tmp/ksef2-cli-qa/qa-artifacts/",
        "  local_invoices/status-80.json",
    ]


def test_a_missing_subject_leaves_no_gap_in_the_record() -> None:
    # An empty subject used to leave the separator that held it, and a run of spaces
    # in the middle of the record.
    assert format_status_line("submitted", "", [("invoice_ref", "ref-1")]) == (
        "submitted  invoice_ref=ref-1"
    )


def test_a_value_that_starts_with_spaces_keeps_its_words() -> None:
    note = "   plain text that needs more than one line"
    text = format_fields([("note", note)], width=24)

    assert text.splitlines() == [
        "note:",
        "  plain text that needs",
        "  more than one line",
    ]


def test_an_unavailable_width_leaves_the_record_unwrapped() -> None:
    # A pipe that says nothing about its width gets the layout it always had, so the
    # one record on a line stays one record on a line.
    assert (
        format_status_line("accepted", _STATUS_RECEIPT, _STATUS_FIELDS)
        == _unwrapped_status_line()
    )


def test_invoices_status_result_stays_inside_eighty_columns(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("COLUMNS", "80")
    result = InvoicesStatusResult(
        mode="online",
        receipt_file=tmp_path / "receipts" / "invoice-workflow-receipt.json",
        status="accepted",
        status_code=200,
        status_description="ready",
        session_reference="2411BF0003",
        file=tmp_path / "invoice.xml",
        invoice_reference=(
            "5926ad107b01e605f9ebb4cbca0080fea655114b8ca67168543dc7ca3bb2eeee"
        ),
        ksef_number="ksef-612701234567-2411BF0003",
    )

    text = plain_renderer.render(result)

    assert max(cell_len(line) for line in text.splitlines()) <= 80
    reference = "5926ad107b01e605f9ebb4cbca0080fea655114b8ca67168543dc7ca3bb2eeee"
    assert reference in "".join(text.split())


def test_columns_states_the_width_of_redirected_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _as_pipe(monkeypatch)
    monkeypatch.setenv("COLUMNS", "80")

    assert content_width() == 80


def test_a_terminal_states_its_own_width(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        text_renderer.sys, "stdout", SimpleNamespace(isatty=lambda: True)
    )
    monkeypatch.setattr(
        text_renderer, "get_terminal_size", lambda fallback: SimpleNamespace(columns=42)
    )

    assert content_width() == 42


@pytest.mark.parametrize("declared", ["", "  ", "wide", "-8"])
def test_nothing_useful_declared_leaves_the_record_unwrapped(
    monkeypatch: pytest.MonkeyPatch, declared: str
) -> None:
    _as_pipe(monkeypatch)
    monkeypatch.setenv("COLUMNS", declared)

    assert content_width() == UNBOUNDED_WIDTH


def test_a_width_below_the_floor_still_breaks_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _as_pipe(monkeypatch)
    monkeypatch.setenv("COLUMNS", "4")

    assert content_width() == MINIMUM_WIDTH


def _unwrapped_status_line() -> str:
    fields = "  ".join(f"{name}={format_cell(value)}" for name, value in _STATUS_FIELDS)
    return f"accepted  {_STATUS_RECEIPT}  {fields}"


def _whole(text: str) -> str:
    """Every character the output carries, so wrapping cannot hide a lost one."""

    return "".join(text.split())


def _as_pipe(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        text_renderer.sys, "stdout", SimpleNamespace(isatty=lambda: False)
    )
