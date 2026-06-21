from typing import Any

from conftest import FakeClient, FakeService, cli_args, fake_runtime, payload
from ksef2.domain.models.tokens import GenerateTokenResponse
from ksef2_cli.app import app


class FakeTemporalTestData:
    def __init__(self) -> None:
        self.entered = 0
        self.exited = 0
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def __enter__(self) -> "FakeTemporalTestData":
        self.entered += 1
        return self

    def __exit__(self, *args: object) -> None:
        self.exited += 1

    def create_subject(self, **kwargs: Any) -> None:
        self.calls.append(("create_subject", kwargs))

    def called(self, name: str) -> dict[str, Any]:
        for call_name, kwargs in self.calls:
            if call_name == name:
                return kwargs
        raise AssertionError(f"{name!r} was not called; calls={self.calls!r}")


def test_testdata_sandbox_creates_temporary_subject_credentials_and_token(
    runner, tmp_path
) -> None:
    temporal = FakeTemporalTestData()
    tokens = FakeService(
        generate=GenerateTokenResponse(
            reference_number="token-reference",
            token="sandbox-token",
        )
    )
    auth = type("Auth", (), {"tokens": tokens})()
    authentication = FakeService(with_xades=auth)
    runtime = fake_runtime(
        client=FakeClient(
            testdata=FakeService(temporal=temporal),
            authentication=authentication,
        )
    )

    result = payload(
        runner.invoke(
            app,
            cli_args(
                "--env",
                "test",
                "testdata",
                "sandbox",
                "--description",
                "demo sandbox",
                "--out-dir",
                str(tmp_path / "sandbox"),
                "--no-hold",
            ),
            obj=runtime,
        )
    )

    generated_nip = result["nip"]
    sandbox_dir = (tmp_path / "sandbox" / generated_nip).resolve()
    cert_file = sandbox_dir / "cert.pem"
    key_file = sandbox_dir / "private-key.pem"
    env_file = sandbox_dir / "env.sh"

    assert generated_nip.isdecimal()
    assert len(generated_nip) == 10
    assert result["subject_type"] == "enforcement_authority"
    assert result["token"] == "sandbox-token"
    assert result["reference_number"] == "token-reference"
    assert result["token_permissions"] == ["invoice_read", "invoice_write"]
    assert result["cert_file"] == str(cert_file)
    assert result["key_file"] == str(key_file)
    assert result["env_file"] == str(env_file)
    assert result["cleanup"] == "remote_test_data_on_exit"
    assert result["token_send_command"].startswith("ksef2 --env test")
    assert result["certificate_send_command"].startswith("ksef2 --env test")

    assert temporal.entered == 1
    assert temporal.exited == 1
    assert temporal.called("create_subject") == {
        "nip": generated_nip,
        "subject_type": "enforcement_authority",
        "description": "demo sandbox",
    }
    assert authentication.called("with_xades")["nip"] == generated_nip
    assert tokens.called("generate")["permissions"] == ["invoice_read", "invoice_write"]

    assert cert_file.read_text(encoding="utf-8").startswith("-----BEGIN CERTIFICATE")
    assert key_file.read_text(encoding="utf-8").startswith("-----BEGIN PRIVATE KEY")
    assert (key_file.stat().st_mode & 0o777) == 0o600
    assert (env_file.stat().st_mode & 0o777) == 0o600
    assert f"export KSEF2_NIP={generated_nip}" in env_file.read_text(encoding="utf-8")
    assert "export KSEF2_TOKEN=sandbox-token" in env_file.read_text(encoding="utf-8")


def test_testdata_sandbox_requires_test_environment(runner) -> None:
    result = runner.invoke(
        app,
        cli_args(
            "testdata",
            "sandbox",
            "--nip",
            "5261040828",
            "--no-hold",
        ),
        obj=fake_runtime(),
    )

    assert result.exit_code == 1
    assert "requires --env test" in result.output


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
    ) == {"nip": "5261040828", "created": True}
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

    assert payload(
        runner.invoke(
            app,
            cli_args("testdata", "delete-subject", "--nip", "5261040828"),
            obj=runtime,
        )
    ) == {
        "nip": "5261040828",
        "deleted": True,
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
    ) == {"nip": "5261040828", "pesel": "12345678901", "created": True}
    assert service.called("create_person")["is_bailiff"] is True
    assert payload(
        runner.invoke(
            app,
            cli_args("testdata", "delete-person", "--nip", "5261040828"),
            obj=runtime,
        )
    ) == {
        "nip": "5261040828",
        "deleted": True,
    }


def test_testdata_attachment_and_context_commands(runner) -> None:
    service = FakeService(
        enable_attachments=None,
        revoke_attachments=None,
        block_context=None,
        unblock_context=None,
    )
    runtime = fake_runtime(client=FakeClient(testdata=service))

    assert payload(
        runner.invoke(
            app,
            cli_args("testdata", "enable-attachments", "--nip", "5261040828"),
            obj=runtime,
        )
    ) == {
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
    ) == {
        "nip": "5261040828",
        "expected_end_date": "2026-01-02",
        "attachments": "revoked",
    }
    assert (
        service.called("revoke_attachments")["expected_end_date"].isoformat()
        == "2026-01-02"
    )

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
    ) == {"context_type": "nip", "context_value": "5261040828", "blocked": True}
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
    ) == {"context_type": "nip", "context_value": "5261040828", "blocked": False}


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
    assert revoked["revoked"] is True
