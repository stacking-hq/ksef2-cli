from __future__ import annotations

from conftest import FakeService, cli_args, fake_runtime, payload
from ksef2_cli.app import app


def test_permission_status_and_query_commands(runner, tmp_path) -> None:
    service = FakeService(
        get_attachment_permission_status={"attachments": "enabled"},
        get_operation_status={"status": "done"},
        get_entity_roles={"roles": [{"role": "owner"}]},
        query_entities={"permissions": [{"id": "p1"}]},
        revoke_common={"revoked": "common"},
        revoke_authorization={"revoked": "authorization"},
    )
    runtime = fake_runtime(
        auth=type("Auth", (), {"permissions": service})(),
        model_reader=lambda path, model_type: {"query": str(path)},
    )

    assert payload(runner.invoke(app, cli_args("permissions", "attachment-status"), obj=runtime)) == {
        "attachments": "enabled"
    }
    assert payload(
        runner.invoke(app, cli_args("permissions", "operation-status", "--reference", "operation-ref"), obj=runtime)
    ) == {"status": "done"}
    assert payload(runner.invoke(app, cli_args("permissions", "entity-roles"), obj=runtime)) == {
        "roles": [{"role": "owner"}]
    }

    payload_file = tmp_path / "query.json"
    payload_file.write_text("{}", encoding="utf-8")
    assert payload(
        runner.invoke(app, cli_args("permissions", "query", "entities", "--payload", str(payload_file)), obj=runtime)
    ) == {"permissions": [{"id": "p1"}]}
    assert service.called("query_entities")["query"] == {"query": str(payload_file)}

    invalid = runner.invoke(app, cli_args("permissions", "query", "missing", "--payload", str(payload_file)), obj=runtime)
    assert invalid.exit_code == 1
    assert "Unsupported query kind" in invalid.output

    assert payload(runner.invoke(app, cli_args("permissions", "revoke-common", "--permission-id", "p1"), obj=runtime)) == {
        "revoked": "common"
    }
    assert payload(
        runner.invoke(app, cli_args("permissions", "revoke-authorization", "--permission-id", "p1"), obj=runtime)
    ) == {"revoked": "authorization"}


def test_permission_grant_person_entity_and_authorization(runner) -> None:
    service = FakeService(
        grant_person={"reference_number": "person-ref"},
        grant_entity={"reference_number": "entity-ref"},
        grant_authorization={"reference_number": "auth-ref"},
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
                "invoice_read",
                "--entity-name",
                "Entity",
                "--description",
                "demo",
            ),
            obj=runtime,
        )
    ) == {"reference_number": "auth-ref"}


def test_permission_grant_indirect_subunit_and_eu(runner) -> None:
    service = FakeService(
        grant_indirect={"reference_number": "indirect-ref"},
        grant_subunit={"reference_number": "subunit-ref"},
        grant_eu_entity={"reference_number": "eu-ref"},
        grant_eu_entity_administration={"reference_number": "eu-admin-ref"},
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
