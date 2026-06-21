from conftest import FakeService, cli_args, fake_runtime, payload
from ksef2.domain.models.certificates import (
    Certificate,
    CertificateLimitsResponse,
    RetrievedCertificatesList,
)
from ksef2_cli.app import app


def test_certificate_read_and_enrollment_commands(runner, tmp_path) -> None:
    service = FakeService(
        get_limits={"limits": "ok"},
        get_enrollment_data={"subject": "data"},
        enroll={"reference_number": "enroll-ref"},
        get_enrollment_status={"status": "ready"},
    )
    runtime = fake_runtime(auth=type("Auth", (), {"certificates": service})())

    assert payload(
        runner.invoke(app, cli_args("certificates", "limits"), obj=runtime)
    ) == {"limits": "ok"}
    assert payload(
        runner.invoke(app, cli_args("certificates", "enrollment-data"), obj=runtime)
    ) == {"subject": "data"}

    csr = tmp_path / "request.csr"
    csr.write_text("base64-csr\n", encoding="utf-8")
    assert payload(
        runner.invoke(
            app,
            cli_args(
                "certificates",
                "enroll",
                "--name",
                "demo",
                "--csr-file",
                str(csr),
                "--type",
                "offline",
                "--valid-from",
                "2026-01-01T00:00:00Z",
            ),
            obj=runtime,
        )
    ) == {"reference_number": "enroll-ref"}
    assert service.called("enroll")["csr"] == "base64-csr"

    assert payload(
        runner.invoke(
            app,
            cli_args("certificates", "enrollment-status", "--reference", "enroll-ref"),
            obj=runtime,
        )
    ) == {"status": "ready"}


def test_certificate_limits_render_in_default_text_mode(runner) -> None:
    service = FakeService(
        get_limits=CertificateLimitsResponse(
            can_request=True,
            enrollment_limit=10,
            enrollment_remaining=9,
            certificate_limit=5,
            certificate_remaining=4,
        )
    )
    runtime = fake_runtime(auth=type("Auth", (), {"certificates": service})())

    result = runner.invoke(app, ["--no-config", "certificates", "limits"], obj=runtime)

    assert result.exit_code == 0
    assert "can_request: yes" in result.output
    assert "certificate_remaining: 4" in result.output


def test_certificate_list_retrieve_and_revoke(runner, tmp_path) -> None:
    serial = "ABCDEF1234567890"
    result = RetrievedCertificatesList(
        certificates=[
            Certificate(
                serial_number=serial,
                base64_encoded_certificate="CERT",
                name="Demo",
                certificate_type="authentication",
            )
        ]
    )
    service = FakeService(
        query={"certificates": [{"serial_number": serial}]},
        all=lambda **kwargs: [{"serial_number": serial}],
        retrieve=result,
        revoke=None,
    )
    runtime = fake_runtime(auth=type("Auth", (), {"certificates": service})())

    assert payload(
        runner.invoke(
            app, cli_args("certificates", "list", "--page-size", "10"), obj=runtime
        )
    ) == {"certificates": [{"serial_number": serial}]}
    assert service.called("query")["params"].page_size == 10

    assert payload(
        runner.invoke(app, cli_args("certificates", "list", "--all"), obj=runtime)
    ) == [{"serial_number": serial}]

    output_dir = tmp_path / "certs"
    retrieved = payload(
        runner.invoke(
            app,
            cli_args("certificates", "retrieve", serial, "--out-dir", str(output_dir)),
            obj=runtime,
        )
    )
    assert retrieved["certificates"][0]["serial_number"] == serial
    assert (output_dir / f"{serial}.b64").read_text(encoding="utf-8") == "CERT\n"

    revoked = payload(
        runner.invoke(
            app,
            cli_args(
                "certificates",
                "revoke",
                "--serial-number",
                serial,
                "--reason",
                "superseded",
            ),
            obj=runtime,
        )
    )
    assert revoked == {
        "serial_number": serial,
        "reason": "superseded",
        "revoked": True,
    }
    assert service.called("revoke")["reason"] == "superseded"
