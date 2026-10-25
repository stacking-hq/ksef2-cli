"""Exercise table selection through CLI commands with real SDK model fixtures."""

import json
from datetime import datetime
from types import SimpleNamespace

import pytest
from conftest import FakeClient, FakePager, FakeService, fake_runtime, online_state
from ksef2.models import (
    AuthenticationSession,
    CertificateInfo,
    CollectiveIdentifierInvoiceDetails,
    CollectiveIdentifierReference,
    CollectiveIdentifierSummary,
    EntityRole,
    InvoiceMetadata,
    PeppolProvider,
    PublicKeyCertificate,
    QueryInvoicesMetadataResponse,
    SessionInvoiceStatusResponse,
    SessionInvoicesResponse,
    SessionSummary,
    TokenInfo,
    TokenStatusResponse,
)

from ksef2_cli.app import app
from ksef2_cli.renderers.lists import LIST_COMMANDS, PERMISSIONS, render_list

STAMP = datetime.fromisoformat("2026-01-02T03:04:05.678+02:00")
REFERENCE = "20260102-123456789012-ABCDEF1234-12"
KSEF = "5261040828-20260102-ABCDEF123456-AB"


def auth_session(**overrides):
    return AuthenticationSession(
        **{
            "reference_number": REFERENCE,
            "start_date": STAMP,
            "authentication_method": "token",
            "authentication_method_category": "token",
            "authentication_method_code": "Token",
            "authentication_method_display_name": "Token KSeF",
            "status_code": 200,
            "status_description": "Uwierzytelnianie zakończone sukcesem",
            "is_current": True,
            **overrides,
        }
    )


def metadata():
    return InvoiceMetadata(
        ksef_number=KSEF,
        invoice_number="FV/Żółć/2026",
        issue_date="2026-01-01",
        invoicing_date=STAMP,
        acquisition_date=STAMP,
        permanent_storage_date=STAMP,
        seller={
            "nip": "5261040828",
            "name": "Żółć spółka z ograniczoną odpowiedzialnością",
        },
        buyer={
            "identifier": {"type": "nip", "value": "1234567890"},
            "name": "Kupujący",
        },
        net_amount=1000,
        gross_amount=1230,
        vat_amount=230,
        currency="PLN",
        invoicing_mode="online",
        invoice_type="vat",
        form_code_system="FA (3)",
        form_code_version="1-0E",
        form_code_value="FA",
        is_self_invoicing=False,
        has_attachment=False,
        invoice_hash="hash",
    )


def session_invoice():
    return SessionInvoiceStatusResponse(
        ordinal_number=1,
        reference_number=REFERENCE,
        ksef_number=KSEF,
        invoice_number="FV/1",
        invoice_hash="hash",
        invoicing_date=STAMP,
        status={"code": 450, "description": "Błędna faktura"},
    )


def cases():
    """Each actual record-list family, with SDK rather than arbitrary dict rows."""
    return [
        ("sessions auth-list", [], "sessions", auth_session(), "REFERENCE"),
        (
            "sessions invoice-list",
            ["--type", "online"],
            "invoice_sessions",
            SessionSummary(
                reference_number=REFERENCE,
                date_created=STAMP,
                date_updated=STAMP,
                status={"code": 100, "description": "Przetwarzanie"},
                total_invoice_count=3,
                successful_invoice_count=1,
                failed_invoice_count=1,
            ),
            "REFERENCE",
        ),
        (
            "tokens list",
            [],
            "tokens",
            TokenInfo(
                reference_number=REFERENCE,
                author_identifier={"type": "nip", "value": "5261040828"},
                context_identifier={"type": "nip", "value": "5261040828"},
                description="Żółć\n\x1b[31mtest\x1b[0m\t\x00",
                requested_permissions=["invoice_read"],
                date_created=STAMP,
                status="active",
                last_use_date=None,
                status_details=None,
            ),
            "REFERENCE",
        ),
        (
            "certificates list",
            [],
            "certificates",
            CertificateInfo(
                serial_number="0123456789ABCDEF",
                name="Pieczęć Żółć",
                common_name="Common",
                type="authentication",
                status="active",
                subject_identifier={"type": "nip", "value": "5261040828"},
                valid_from=STAMP,
                valid_to=STAMP,
                request_date=STAMP,
            ),
            "SERIAL",
        ),
        (
            "collective list",
            ["--date-from", "2026-01-01"],
            "collective_identifiers",
            CollectiveIdentifierSummary(
                collective_identifier_number=REFERENCE,
                date_created=STAMP,
                invoice_count=2,
                created_in_current_context=True,
            ),
            "IDENTIFIER",
        ),
        (
            "collective list-for-invoice",
            ["--ksef-number", KSEF],
            "collective_identifiers",
            CollectiveIdentifierReference(
                collective_identifier_number=REFERENCE,
                date_created=STAMP,
                created_in_current_context=False,
            ),
            "IDENTIFIER",
        ),
        (
            "collective list-invoices",
            [REFERENCE],
            "collective_identifiers",
            CollectiveIdentifierInvoiceDetails(
                ksef_number=KSEF,
                payment={"amount": 1230, "currency": "PLN"},
                description="Zapłata",
                details_hidden=False,
            ),
            "KSEF NUMBER",
        ),
        (
            "peppol providers",
            [],
            "peppol",
            PeppolProvider(id=REFERENCE, name="Żółć", date_created=STAMP),
            "ID",
        ),
        (
            "encryption certificates",
            [],
            "encryption",
            PublicKeyCertificate(
                certificate="base64-body-not-a-table-cell",
                certificate_id=REFERENCE,
                public_key_id="public-key-id",
                valid_from=STAMP,
                valid_to=STAMP,
                usage=["ksef_token_encryption"],
            ),
            "CERTIFICATE ID",
        ),
        (
            "permissions entity-roles",
            [],
            "permissions",
            EntityRole(
                role="vat_group_unit",
                description="Grupa VAT",
                start_date=STAMP,
            ),
            "ROLE",
        ),
    ]


def runtime_for(command, service_name, rows):
    method = {
        "collective list-for-invoice": "list_for_invoice",
        "collective list-invoices": "list_invoices",
        "encryption certificates": "get_certificates",
        "permissions entity-roles": "list_entity_roles",
    }.get(command, "list")
    service = FakeService(
        **{method: rows if method == "get_certificates" else FakePager(rows)}
    )
    if service_name in ("peppol", "encryption"):
        return fake_runtime(client=FakeClient(**{service_name: service}))
    return fake_runtime(auth=SimpleNamespace(**{service_name: service}))


@pytest.mark.parametrize(
    "command,options,service_name,item,header",
    cases(),
    ids=lambda v: v if isinstance(v, str) else None,
)
def test_list_command_inventory(runner, command, options, service_name, item, header):
    runtime = runtime_for(command, service_name, [item])
    args = [*command.split(), *options]
    result = runner.invoke(app, ["--no-config", *args], obj=runtime)
    assert result.exit_code == 0, result.output
    assert result.output.startswith(header)
    assert len(result.output.splitlines()) == 2
    assert "\x1b" not in result.output and "\x00" not in result.output
    assert "=" not in result.output
    # The entire serialized SDK row, including optional nulls, is unchanged.
    result_json = runner.invoke(app, ["--no-config", "--json", *args], obj=runtime)
    assert result_json.exit_code == 0, result_json.output
    assert json.loads(result_json.output) == [
        item.model_dump(mode="json", by_alias=True)
    ]
    empty = runner.invoke(
        app, ["--no-config", *args], obj=runtime_for(command, service_name, [])
    )
    assert empty.output == "No results.\n"


def test_auth_alignment_and_json_contract(runner):
    runtime = runtime_for("sessions auth-list", "sessions", [auth_session()])
    result = runner.invoke(app, ["--no-config", "sessions", "auth-list"], obj=runtime)
    assert result.output == (
        "REFERENCE                            STARTED (UTC)        METHOD      STATUS  CURRENT\n"
        "20260102-123456789012-ABCDEF1234-12  2026-01-02 01:04:05  Token KSeF  ok      yes\n"
    )
    actual = runner.invoke(
        app, ["--no-config", "--json", "sessions", "auth-list"], obj=runtime
    )
    assert json.loads(actual.output) == [
        {
            "reference_number": REFERENCE,
            "start_date": "2026-01-02T03:04:05.678000+02:00",
            "authentication_method": "token",
            "authentication_method_category": "token",
            "authentication_method_code": "Token",
            "authentication_method_display_name": "Token KSeF",
            "status_code": 200,
            "status_description": "Uwierzytelnianie zakończone sukcesem",
            "status_details": None,
            "is_token_redeemed": None,
            "last_token_refresh_date": None,
            "refresh_token_valid_until": None,
            "is_current": True,
        }
    ]


@pytest.mark.parametrize(
    "code,description,expected",
    [
        (100, "Przetwarzanie", "in progress"),
        (200, "Długi opis sukcesu", "ok"),
        (450, "Błędna pieczęć", "failed: Błędna pieczęć"),
        (500, "Awaria", "failed: Awaria"),
        (777, "Nieznany", "777: Nieznany"),
    ],
)
def test_auth_statuses(runner, code, description, expected):
    runtime = runtime_for(
        "sessions auth-list",
        "sessions",
        [auth_session(status_code=code, status_description=description)],
    )
    result = runner.invoke(app, ["--no-config", "sessions", "auth-list"], obj=runtime)
    assert result.exit_code == 0
    assert expected in result.output


def test_narrow_terminal_preserves_identifiers_and_status(runner, monkeypatch):
    import ksef2_cli.renderers.table as table

    # CliRunner replaces stdout, so patch the size selection at the formatter boundary.
    original = table.render_table
    monkeypatch.setattr(
        "ksef2_cli.renderers.lists.render_table",
        lambda rows, cols, width=None: original(rows, cols, width=72),
    )
    runtime = runtime_for(
        "sessions auth-list",
        "sessions",
        [
            auth_session(
                authentication_method="qualified_seal",
                authentication_method_display_name="Pieczęć kwalifikowana",
                status_code=450,
                status_description="Błędna pieczęć " * 10,
            )
        ],
    )
    result = runner.invoke(app, ["--no-config", "sessions", "auth-list"], obj=runtime)
    assert result.exit_code == 0
    assert REFERENCE in result.output
    assert "failed: Błędna" in result.output and "…" in result.output
    assert len(result.output.splitlines()) == 2


@pytest.mark.parametrize("command", ["online", "batch"])
def test_session_invoice_tables_and_pagination(runner, tmp_path, command):
    response = SessionInvoicesResponse(
        continuation_token="page-2", invoices=[session_invoice()]
    )
    session = FakeService(list_invoices=response, list_failed_invoices=response)

    # Batch handles are context managers; online handles are used directly.
    class Session(FakeService):
        def __enter__(self):
            return session

        def __exit__(self, *args):
            return False

    auth = SimpleNamespace(
        **{
            f"{command}_session": lambda **kwargs: session
            if command == "online"
            else Session()
        }
    )
    if command == "online":
        path = tmp_path / "state.json"
        path.write_text(online_state().to_json())
        options = ["--state-file", str(path)]
    else:
        options = ["--reference", REFERENCE]
    args = [command, "list", *options]
    runtime = fake_runtime(auth=auth)
    for extra in ([], ["--failed"]):
        result = runner.invoke(app, ["--no-config", *args, *extra], obj=runtime)
        assert result.exit_code == 0, result.output
        assert REFERENCE in result.output and KSEF in result.output
        assert "failed: Błędna faktura" in result.output
        assert result.output.endswith("Next page: --continuation-token page-2\n")
        actual_json = runner.invoke(
            app, ["--no-config", "--json", *args, *extra], obj=runtime
        )
        assert json.loads(actual_json.output) == response.model_dump(
            mode="json", by_alias=True
        )


def test_metadata_table_and_envelope(runner):
    invoice = metadata()
    response = QueryInvoicesMetadataResponse(
        invoices=[invoice],
        has_more=True,
        is_truncated=True,
        permanent_storage_hwm_date=STAMP,
    )

    class Search(FakePager):
        def first_response(self):
            return response

    service = FakeService(search=Search([invoice]))
    runtime = fake_runtime(auth=SimpleNamespace(invoices=service))
    args = [
        "invoices",
        "metadata",
        "--date-from",
        "2026-01-01",
        "--date-to",
        "2026-01-02",
    ]
    result = runner.invoke(app, ["--no-config", *args], obj=runtime)
    assert result.exit_code == 0, result.output
    assert KSEF in result.output and "FV/Żółć/2026" in result.output
    assert "1230.00 PLN" in result.output and "2026-01-01" in result.output
    assert "More results: yes" in result.output and "Truncated: yes" in result.output
    assert "Permanent storage HWM (UTC): 2026-01-02 01:04:05" in result.output
    result_json = runner.invoke(app, ["--no-config", "--json", *args], obj=runtime)
    assert json.loads(result_json.output) == response.model_dump(
        mode="json", by_alias=True
    )
    all_pages = runner.invoke(app, ["--no-config", *args, "--all"], obj=runtime)
    assert all_pages.exit_code == 0
    assert len(all_pages.output.splitlines()) == 2
    assert "More results" not in all_pages.output
    # Wide output retains every approved column; narrow output gives names space first.
    wide = render_list("invoices metadata", [invoice], width=240)
    assert "SELLER" in wide and "BUYER" in wide and "Żółć spółka" in wide
    narrow = render_list("invoices metadata", [invoice], width=80)
    assert KSEF in narrow and "1230.00 PLN" in narrow
    assert "…" in result.output


@pytest.mark.parametrize(
    "kind,fields",
    [
        (
            "entities",
            {
                "id": "12345678-1234-1234-1234-123456789012",
                "context_type": "nip",
                "context_value": "5261040828",
                "permission_type": "invoice_read",
                "can_delegate": True,
            },
        ),
        (
            "persons",
            {
                "id": "12345678-1234-1234-1234-123456789012",
                "permission_type": "invoice_read",
                "permission_state": "active",
                "can_delegate": False,
            },
        ),
        (
            "authorizations",
            {
                "id": "12345678-1234-1234-1234-123456789012",
                "authorized_entity_type": "nip",
                "authorized_entity_value": "5261040828",
                "authorizing_entity_type": "nip",
                "authorizing_entity_value": "1234567890",
                "authorization_scope": "self_invoicing",
            },
        ),
        (
            "personal",
            {
                "id": "12345678-1234-1234-1234-123456789012",
                "permission_type": "invoice_read",
                "permission_state": "active",
                "can_delegate": False,
            },
        ),
        (
            "eu-entities",
            {
                "id": "12345678-1234-1234-1234-123456789012",
                "author_type": "nip",
                "author_value": "5261040828",
                "vat_ue_identifier": "PL5261040828",
                "eu_entity_name": "Firma",
                "authorized_fingerprint_identifier": "fingerprint",
                "permission_type": "invoice_read",
            },
        ),
        (
            "subordinate-entities",
            {
                "subordinate_entity_type": "nip",
                "subordinate_entity_value": "5261040828",
                "role": "vat_group_sub_unit",
            },
        ),
        (
            "subunits",
            {
                "id": "12345678-1234-1234-1234-123456789012",
                "authorized_type": "nip",
                "authorized_value": "5261040828",
                "subunit_type": "internal_id",
                "subunit_value": "subunit-id",
                "author_type": "nip",
                "author_value": "5261040828",
                "permission_type": "invoice_read",
            },
        ),
    ],
)
def test_permission_query_inventory(runner, tmp_path, kind, fields):
    item = PERMISSIONS[kind].item_type(
        **fields, description="Uprawnienie Żółć", start_date=STAMP
    )
    method = "list_" + kind.replace("-", "_")
    service = FakeService(**{method: FakePager([item])})
    query = tmp_path / "query.json"
    query.write_text("{}")
    runtime = fake_runtime(
        auth=SimpleNamespace(permissions=service), model_reader=lambda *args: {}
    )
    args = ["permissions", "query", kind, "--payload", str(query)]
    result = runner.invoke(app, ["--no-config", *args], obj=runtime)
    assert result.exit_code == 0, result.output
    assert "2026-01-02 01:04:05" in result.output
    assert "Uprawnienie Żółć" in result.output
    identifier = fields.get("id", fields.get("subordinate_entity_value"))
    assert identifier in result.output
    actual_json = runner.invoke(app, ["--no-config", "--json", *args], obj=runtime)
    assert json.loads(actual_json.output) == [
        item.model_dump(mode="json", by_alias=True)
    ]


def test_profile_list_and_single_record_regression(runner, tmp_path):
    config = tmp_path / "profiles.toml"
    config.write_text(
        '[profiles.demo]\nenvironment = "test"\nnip = "5261040828"\n[profiles.demo.auth]\ntype = "test_certificate"\n'
    )
    result = runner.invoke(app, ["--config", str(config), "profile", "list"])
    assert result.exit_code == 0, result.output
    assert result.output == (
        "NAME  ACTIVE  ENVIRONMENT  NIP         AUTH\n"
        "demo  no      test         5261040828  test_certificate\n"
    )
    runtime = fake_runtime(
        auth=SimpleNamespace(
            tokens=FakeService(
                get_status=TokenStatusResponse(
                    reference_number=REFERENCE, status="active"
                ),
            )
        )
    )
    result = runner.invoke(
        app, ["--no-config", "tokens", "status", "--reference", REFERENCE], obj=runtime
    )
    assert result.output == f"reference_number: {REFERENCE}\nstatus: active\n"


def test_inventory_is_explicit():
    assert set(LIST_COMMANDS) == {
        "sessions auth-list",
        "sessions invoice-list",
        "online list",
        "batch list",
        "invoices metadata",
        "tokens list",
        "certificates list",
        "collective list",
        "collective list-for-invoice",
        "collective list-invoices",
        "profile list",
        "peppol providers",
        "encryption certificates",
        "permissions entity-roles",
    }
    assert render_list("online send", [session_invoice()]) is None
