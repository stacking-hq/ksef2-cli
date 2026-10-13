from datetime import UTC, datetime

from conftest import FakePager, FakeService, cli_args, fake_runtime, payload
from ksef2.models import (
    Certificate,
    CertificateInfo,
    CertificateLimitsResponse,
    RetrievedCertificatesList,
)

from ksef2_cli.app import app


def _certificate_info(serial_number: str) -> CertificateInfo:
    return CertificateInfo(
        serial_number=serial_number,
        name="Demo",
        common_name="Demo CN",
        type="authentication",
        status="active",
        subject_identifier={"type": "nip", "value": "5261040828"},
        valid_from=datetime(2026, 1, 1, tzinfo=UTC),
        valid_to=datetime(2026, 12, 31, tzinfo=UTC),
        request_date=datetime(2026, 1, 1, tzinfo=UTC),
    )


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
        list=FakePager(
            [{"serial_number": serial}], [{"serial_number": "FEDCBA0987654321"}]
        ),
        retrieve=result,
        revoke=None,
    )
    runtime = fake_runtime(auth=type("Auth", (), {"certificates": service})())

    # Without --all the command prints only the pager's first page.
    assert payload(
        runner.invoke(
            app, cli_args("certificates", "list", "--page-size", "10"), obj=runtime
        )
    ) == [{"serial_number": serial}]
    assert service.called("list")["params"].page_size == 10

    assert payload(
        runner.invoke(app, cli_args("certificates", "list", "--all"), obj=runtime)
    ) == [{"serial_number": serial}, {"serial_number": "FEDCBA0987654321"}]

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


def test_certificate_list_filters_reach_the_pager(runner) -> None:
    service = FakeService(list=FakePager([]))
    runtime = fake_runtime(auth=type("Auth", (), {"certificates": service})())

    assert (
        payload(
            runner.invoke(
                app,
                cli_args(
                    "certificates",
                    "list",
                    "--serial-number",
                    "ABCDEF1234567890",
                    "--name",
                    "Demo",
                    "--type",
                    "offline",
                    "--status",
                    "active",
                    "--expires-after",
                    "2026-01-01T00:00:00Z",
                    "--page-offset",
                    "10",
                ),
                obj=runtime,
            )
        )
        == []
    )
    kwargs = service.called("list")
    assert kwargs["certificate_serial_number"] == "ABCDEF1234567890"
    assert kwargs["name"] == "Demo"
    assert kwargs["certificate_type"] == "offline"
    assert kwargs["status"] == "active"
    assert kwargs["expires_after"] == "2026-01-01T00:00:00Z"
    assert kwargs["params"].page_offset == 10


def test_certificate_list_items_render_in_default_text_mode(runner) -> None:
    # Both modes hand the renderer a plain list of CertificateInfo.
    service = FakeService(
        list=FakePager(
            [_certificate_info("ABCDEF1234567890")],
            [_certificate_info("FEDCBA0987654321")],
        )
    )
    runtime = fake_runtime(auth=type("Auth", (), {"certificates": service})())

    first_page = runner.invoke(
        app, ["--no-config", "certificates", "list"], obj=runtime
    )
    assert first_page.exit_code == 0, first_page.output
    assert "serial_number: ABCDEF1234567890" in first_page.output
    assert "FEDCBA0987654321" not in first_page.output

    all_pages = runner.invoke(
        app, ["--no-config", "certificates", "list", "--all"], obj=runtime
    )
    assert "serial_number: FEDCBA0987654321" in all_pages.output
