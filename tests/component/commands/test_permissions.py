from datetime import UTC, datetime

import pytest
from conftest import FakePager, FakeService, cli_args, fake_runtime, payload
from ksef2.models import (
    EntityRole,
    GrantPermissionsResponse,
    OperationStatus,
    PermissionOperationStatusResponse,
)

from ksef2_cli.app import app


class FakeOperation:
    """Stand-in for ``ksef2.clients.PermissionOperation``, the 1.0 grant/revoke handle.

    The handle exposes the fields of the old response and waits for the final
    status when ``wait()`` is called.
    """

    def __init__(self, reference_number: str) -> None:
        self.response = GrantPermissionsResponse(reference_number=reference_number)

    def wait(self) -> PermissionOperationStatusResponse:
        return PermissionOperationStatusResponse(
            status=OperationStatus(code=200, description="done")
        )


def _call(service: FakeService, name: str) -> tuple[tuple, dict]:
    """Return the positional and keyword arguments of the first call to ``name``."""

    for call_name, args, kwargs in service.calls:
        if call_name == name:
            return args, kwargs
    raise AssertionError(f"{name!r} was not called; calls={service.calls!r}")


def test_permission_status_and_list_commands(runner, tmp_path) -> None:
    service = FakeService(
        get_attachment_permission_status={"attachments": "enabled"},
        get_operation_status={"status": "done"},
        list_entity_roles=FakePager([{"role": "owner"}]),
        list_entities=FakePager([{"id": "p1"}]),
        revoke=FakeOperation("revoke-ref"),
        revoke_authorization=FakeOperation("authorization-ref"),
    )
    runtime = fake_runtime(
        auth=type("Auth", (), {"permissions": service})(),
        model_reader=lambda path, model_type: {"query": str(path)},
    )

    assert payload(
        runner.invoke(app, cli_args("permissions", "attachment-status"), obj=runtime)
    ) == {"attachments": "enabled"}
    assert payload(
        runner.invoke(
            app,
            cli_args("permissions", "operation-status", "--reference", "operation-ref"),
            obj=runtime,
        )
    ) == {"status": "done"}

    assert payload(
        runner.invoke(
            app,
            cli_args("permissions", "entity-roles", "--page-size", "20"),
            obj=runtime,
        )
    ) == [{"role": "owner"}]
    assert service.called("list_entity_roles")["params"].page_size == 20

    payload_file = tmp_path / "query.json"
    payload_file.write_text("{}", encoding="utf-8")
    assert payload(
        runner.invoke(
            app,
            cli_args(
                "permissions",
                "query",
                "entities",
                "--payload",
                str(payload_file),
                "--page-offset",
                "10",
            ),
            obj=runtime,
        )
    ) == [{"id": "p1"}]
    query_args, query_kwargs = _call(service, "list_entities")
    assert query_args[0] == {"query": str(payload_file)}
    assert query_kwargs["params"].page_offset == 10

    invalid = runner.invoke(
        app,
        cli_args("permissions", "query", "missing", "--payload", str(payload_file)),
        obj=runtime,
    )
    assert invalid.exit_code == 2
    assert "Invalid value" in invalid.output
    assert "missing" in invalid.output

    assert payload(
        runner.invoke(
            app,
            cli_args("permissions", "revoke-common", "--permission-id", "p1"),
            obj=runtime,
        )
    ) == {"reference_number": "revoke-ref"}
    assert service.called("revoke")["permission_id"] == "p1"
    assert payload(
        runner.invoke(
            app,
            cli_args("permissions", "revoke-authorization", "--permission-id", "p1"),
            obj=runtime,
        )
    ) == {"reference_number": "authorization-ref"}
    assert service.called("revoke_authorization")["permission_id"] == "p1"


# Each query kind and the 1.0 pager-returning method behind it.
QUERY_METHODS = {
    "authorizations": "list_authorizations",
    "entities": "list_entities",
    "eu-entities": "list_eu_entities",
    "personal": "list_personal",
    "persons": "list_persons",
    "subordinate-entities": "list_subordinate_entities",
    "subunits": "list_subunits",
}


@pytest.mark.parametrize(("kind", "method"), sorted(QUERY_METHODS.items()))
def test_permission_query_calls_the_list_method(
    runner, tmp_path, kind: str, method: str
) -> None:
    payload_file = tmp_path / "query.json"
    payload_file.write_text("{}", encoding="utf-8")
    service = FakeService(**{method: FakePager([{"id": "p1"}])})
    runtime = fake_runtime(
        auth=type("Auth", (), {"permissions": service})(),
        model_reader=lambda path, model_type: {},
    )

    assert payload(
        runner.invoke(
            app,
            cli_args("permissions", "query", kind, "--payload", str(payload_file)),
            obj=runtime,
        )
    ) == [{"id": "p1"}]
    assert service.called(method)["params"].page_size == 10


def test_permission_query_all_pages_prints_every_item(runner, tmp_path) -> None:
    pager = FakePager([{"id": "p1"}, {"id": "p2"}], [{"id": "p3"}])
    service = FakeService(
        list_persons=pager,
        list_entity_roles=FakePager([{"role": "owner"}], [{"role": "bookkeeper"}]),
    )
    runtime = fake_runtime(
        auth=type("Auth", (), {"permissions": service})(),
        model_reader=lambda path, model_type: {},
    )
    payload_file = tmp_path / "query.json"
    payload_file.write_text("{}", encoding="utf-8")

    assert payload(
        runner.invoke(
            app,
            cli_args("permissions", "query", "persons", "--payload", str(payload_file)),
            obj=runtime,
        )
    ) == [{"id": "p1"}, {"id": "p2"}]
    assert payload(
        runner.invoke(
            app,
            cli_args(
                "permissions",
                "query",
                "persons",
                "--payload",
                str(payload_file),
                "--all",
            ),
            obj=runtime,
        )
    ) == [{"id": "p1"}, {"id": "p2"}, {"id": "p3"}]
    assert payload(
        runner.invoke(
            app, cli_args("permissions", "entity-roles", "--all"), obj=runtime
        )
    ) == [{"role": "owner"}, {"role": "bookkeeper"}]


def test_permission_list_items_render_in_default_text_mode(runner, tmp_path) -> None:
    service = FakeService(
        list_entity_roles=FakePager(
            [
                EntityRole(
                    role="vat_group_unit",
                    description="VAT group",
                    start_date=datetime(2026, 1, 1, tzinfo=UTC),
                )
            ]
        )
    )
    runtime = fake_runtime(auth=type("Auth", (), {"permissions": service})())

    result = runner.invoke(
        app, ["--no-config", "permissions", "entity-roles"], obj=runtime
    )

    assert result.exit_code == 0, result.output
    assert "role: vat_group_unit" in result.output
    assert "description: VAT group" in result.output


def test_permission_grant_waits_for_the_final_status(runner) -> None:
    service = FakeService(
        grant_person=FakeOperation("person-ref"),
        revoke=FakeOperation("revoke-ref"),
    )
    runtime = fake_runtime(auth=type("Auth", (), {"permissions": service})())

    grant = [
        "permissions",
        "grant-person",
        "--subject-type",
        "nip",
        "--subject-value",
        "5261040828",
        "--first-name",
        "A",
        "--last-name",
        "B",
        "--description",
        "demo",
        "--permission",
        "invoice_read",
    ]
    assert payload(runner.invoke(app, cli_args(*grant), obj=runtime)) == {
        "reference_number": "person-ref"
    }
    assert payload(runner.invoke(app, cli_args(*grant, "--wait"), obj=runtime)) == {
        "status": {"code": 200, "description": "done"}
    }

    revoke = ["permissions", "revoke-common", "--permission-id", "p1"]
    assert payload(runner.invoke(app, cli_args(*revoke, "--wait"), obj=runtime)) == {
        "status": {"code": 200, "description": "done"}
    }


def test_permission_grant_person_entity_and_authorization(runner) -> None:
    service = FakeService(
        grant_person=FakeOperation("person-ref"),
        grant_entity=FakeOperation("entity-ref"),
        grant_authorization=FakeOperation("auth-ref"),
    )
    runtime = fake_runtime(auth=type("Auth", (), {"permissions": service})())

    missing = runner.invoke(
        app,
        cli_args(
            "permissions",
            "grant-person",
            "--subject-type",
            "nip",
            "--subject-value",
            "5261040828",
            "--first-name",
            "A",
            "--last-name",
            "B",
            "--description",
            "demo",
        ),
        obj=runtime,
    )
    assert missing.exit_code == 1
    assert "At least one --permission" in missing.output

    assert payload(
        runner.invoke(
            app,
            cli_args(
                "permissions",
                "grant-person",
                "--subject-type",
                "nip",
                "--subject-value",
                "5261040828",
                "--first-name",
                "A",
                "--last-name",
                "B",
                "--description",
                "demo",
                "--permission",
                "invoice_read",
            ),
            obj=runtime,
        )
    ) == {"reference_number": "person-ref"}
    assert service.called("grant_person")["subject_type"] == "nip"
    assert service.called("grant_person")["permissions"] == ["invoice_read"]

    assert payload(
        runner.invoke(
            app,
            cli_args(
                "permissions",
                "grant-entity",
                "--subject-value",
                "5261040828",
                "--entity-name",
                "Entity",
                "--description",
                "demo",
                "--permission",
                "invoice_write",
                "--can-delegate",
            ),
            obj=runtime,
        )
    ) == {"reference_number": "entity-ref"}
    assert service.called("grant_entity")["permissions"][0].can_delegate is True

    assert payload(
        runner.invoke(
            app,
            cli_args(
                "permissions",
                "grant-authorization",
                "--subject-type",
                "nip",
                "--subject-value",
                "5261040828",
                "--permission",
                "self_invoicing",
                "--entity-name",
                "Entity",
                "--description",
                "demo",
            ),
            obj=runtime,
        )
    ) == {"reference_number": "auth-ref"}
    assert service.called("grant_authorization")["subject_type"] == "nip"
    assert service.called("grant_authorization")["permission"] == "self_invoicing"


def test_permission_grant_indirect_subunit_and_eu(runner) -> None:
    service = FakeService(
        grant_indirect=FakeOperation("indirect-ref"),
        grant_subunit=FakeOperation("subunit-ref"),
        grant_eu_entity=FakeOperation("eu-ref"),
        grant_eu_entity_administration=FakeOperation("eu-admin-ref"),
    )
    runtime = fake_runtime(auth=type("Auth", (), {"permissions": service})())

    assert payload(
        runner.invoke(
            app,
            cli_args(
                "permissions",
                "grant-indirect",
                "--subject-type",
                "nip",
                "--subject-value",
                "5261040828",
                "--first-name",
                "A",
                "--last-name",
                "B",
                "--description",
                "demo",
                "--permission",
                "invoice_read",
                "--target-type",
                "nip",
                "--target-value",
                "1234567890",
            ),
            obj=runtime,
        )
    ) == {"reference_number": "indirect-ref"}
    assert service.called("grant_indirect")["subject_type"] == "nip"
    assert service.called("grant_indirect")["permissions"] == ["invoice_read"]
    assert service.called("grant_indirect")["target_type"] == "nip"

    assert payload(
        runner.invoke(
            app,
            cli_args(
                "permissions",
                "grant-subunit",
                "--subject-type",
                "nip",
                "--subject-value",
                "5261040828",
                "--context-type",
                "nip",
                "--context-value",
                "1234567890",
                "--first-name",
                "A",
                "--last-name",
                "B",
                "--description",
                "demo",
                "--subunit-name",
                "Subunit",
            ),
            obj=runtime,
        )
    ) == {"reference_number": "subunit-ref"}
    assert service.called("grant_subunit")["subject_type"] == "nip"
    assert service.called("grant_subunit")["context_type"] == "nip"

    assert payload(
        runner.invoke(
            app,
            cli_args(
                "permissions",
                "grant-eu-entity",
                "--subject-value",
                "fingerprint",
                "--description",
                "demo",
                "--permission",
                "invoice_read",
            ),
            obj=runtime,
        )
    ) == {"reference_number": "eu-ref"}
    assert service.called("grant_eu_entity")["permissions"] == ["invoice_read"]

    assert payload(
        runner.invoke(
            app,
            cli_args(
                "permissions",
                "grant-eu-admin",
                "--subject-value",
                "fingerprint",
                "--context-value",
                "PL1234567890",
                "--eu-entity-name",
                "EU Entity",
                "--description",
                "demo",
            ),
            obj=runtime,
        )
    ) == {"reference_number": "eu-admin-ref"}
    assert (
        service.called("grant_eu_entity_administration")["context_type"] == "nip_vat_ue"
    )
