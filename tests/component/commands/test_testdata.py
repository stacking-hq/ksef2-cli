from __future__ import annotations

from conftest import FakeClient, FakeService, cli_args, fake_runtime, payload
from ksef2_cli.app import app


def test_testdata_subject_and_person_commands(runner) -> None:
    service = FakeService(
        create_subject=None,
        delete_subject=None,
        create_person=None,
        delete_person=None,
    )
    runtime = fake_runtime(client=FakeClient(testdata=service))

    assert payload(
        runner.invoke(
            app,
            cli_args(
                "testdata",
                "create-subject",
                "--nip",
                "5261040828",
                "--type",
                "jst",
                "--description",
                "demo",
                "--subunit",
                "1234567890:Subunit",
            ),
            obj=runtime,
        )
    ) == {"nip": "5261040828", "created": "true"}
    assert service.called("create_subject")["subunits"][0].subject_nip == "1234567890"

    invalid = runner.invoke(
        app,
        cli_args(
            "testdata",
            "create-subject",
            "--nip",
            "5261040828",
            "--type",
            "jst",
            "--description",
            "demo",
            "--subunit",
            "bad-format",
        ),
        obj=runtime,
    )
    assert invalid.exit_code == 1
    assert "NIP:description" in invalid.output

    assert payload(runner.invoke(app, cli_args("testdata", "delete-subject", "--nip", "5261040828"), obj=runtime)) == {
        "nip": "5261040828",
        "deleted": "true",
    }
    assert payload(
        runner.invoke(
            app,
            cli_args(
                "testdata",
                "create-person",
                "--nip",
                "5261040828",
                "--pesel",
                "12345678901",
                "--description",
                "demo",
                "--bailiff",
                "--deceased",
            ),
            obj=runtime,
        )
    ) == {"nip": "5261040828", "pesel": "12345678901", "created": "true"}
    assert service.called("create_person")["is_bailiff"] is True
    assert payload(runner.invoke(app, cli_args("testdata", "delete-person", "--nip", "5261040828"), obj=runtime)) == {
        "nip": "5261040828",
        "deleted": "true",
    }


def test_testdata_attachment_and_context_commands(runner) -> None:
    service = FakeService(
        enable_attachments=None,
        revoke_attachments=None,
        block_context=None,
        unblock_context=None,
    )
    runtime = fake_runtime(client=FakeClient(testdata=service))

    assert payload(runner.invoke(app, cli_args("testdata", "enable-attachments", "--nip", "5261040828"), obj=runtime)) == {
        "nip": "5261040828",
        "attachments": "enabled",
    }
    assert payload(
        runner.invoke(
            app,
            cli_args(
                "testdata",
                "revoke-attachments",
                "--nip",
                "5261040828",
                "--expected-end-date",
                "2026-01-02",
            ),
            obj=runtime,
        )
    ) == {"nip": "5261040828", "expected_end_date": "2026-01-02", "attachments": "revoked"}
    assert service.called("revoke_attachments")["expected_end_date"].isoformat() == "2026-01-02"

    assert payload(
        runner.invoke(
            app,
            cli_args(
                "testdata",
                "block-context",
                "--context-type",
                "nip",
                "--context-value",
                "5261040828",
            ),
            obj=runtime,
        )
    ) == {"context_type": "nip", "context_value": "5261040828", "blocked": "true"}
    assert service.called("block_context")["context"].type == "nip"

    assert payload(
        runner.invoke(
            app,
            cli_args(
                "testdata",
                "unblock-context",
                "--context-type",
                "nip",
                "--context-value",
                "5261040828",
            ),
            obj=runtime,
        )
    ) == {"context_type": "nip", "context_value": "5261040828", "blocked": "false"}


def test_testdata_permission_commands(runner) -> None:
    service = FakeService(grant_permissions=None, revoke_permissions=None)
    runtime = fake_runtime(client=FakeClient(testdata=service))

    missing = runner.invoke(
        app,
        cli_args(
            "testdata",
            "grant-permissions",
            "--grant-to-type",
            "nip",
            "--grant-to-value",
            "5261040828",
            "--context-type",
            "nip",
            "--context-value",
            "1234567890",
        ),
        obj=runtime,
    )
    assert missing.exit_code == 1
    assert "At least one --permission" in missing.output

    granted = payload(
        runner.invoke(
            app,
            cli_args(
                "testdata",
                "grant-permissions",
                "--grant-to-type",
                "nip",
                "--grant-to-value",
                "5261040828",
                "--context-type",
                "nip",
                "--context-value",
                "1234567890",
                "--permission",
                "invoice_read",
                "--description",
                "demo",
            ),
            obj=runtime,
        )
    )
    assert granted["grant_to"]["value"] == "5261040828"
    assert granted["permissions"][0]["description"] == "demo"

    revoked = payload(
        runner.invoke(
            app,
            cli_args(
                "testdata",
                "revoke-permissions",
                "--revoke-from-type",
                "nip",
                "--revoke-from-value",
                "5261040828",
                "--context-type",
                "nip",
                "--context-value",
                "1234567890",
            ),
            obj=runtime,
        )
    )
    assert revoked["revoke_from"]["value"] == "5261040828"
    assert revoked["revoked"] == "true"
