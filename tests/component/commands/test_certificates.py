import base64
import json
from datetime import UTC, datetime

import pytest
from conftest import FakePager, FakeService, cli_args, fake_runtime, payload
from ksef2 import KSeFResponseValidationError
from ksef2.models import (
    Certificate,
    CertificateEnrollmentResponse,
    CertificateEnrollmentStatusResponse,
    CertificateLimitsResponse,
    RetrievedCertificatesList,
)
from pydantic import BaseModel, Base64Str, ValidationError
from typer.testing import CliRunner

from ksef2_cli.app import app


class _RetrieveResponse(BaseModel):
    """The retrieve response the SDK validates, reduced to the field that broke.

    ``Base64Str`` is Pydantic's base64 of a *string*, so the Base64 of the DER bytes
    KSeF returns for an issued certificate is rejected before the CLI sees it.
    """

    certificates: list[dict[str, Base64Str]]


def _unreadable_certificate_response() -> KSeFResponseValidationError:
    """The SDK error from the QA run, with the Pydantic rejection as its cause."""

    der_as_base64 = base64.b64encode(b"\x30\x82\x0c\xde\x00\x01\x02").decode("ascii")
    try:
        _RetrieveResponse.model_validate(
            {"certificates": [{"certificate": der_as_base64}]}
        )
    except ValidationError as error:
        try:
            raise KSeFResponseValidationError("Invalid response payload") from error
        except KSeFResponseValidationError as response_error:
            return response_error
    raise AssertionError("Base64 DER was accepted; the SDK model changed")


class FakeCertificateEnrollment:
    """Enrollment handle with SDK response models and recorded polling arguments."""

    def __init__(self) -> None:
        self.response = CertificateEnrollmentResponse(
            reference_number="enroll-ref",
            timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        )
        self.wait_calls: list[tuple[float, float]] = []

    def wait(
        self, *, timeout: float, poll_interval: float
    ) -> CertificateEnrollmentStatusResponse:
        self.wait_calls.append((timeout, poll_interval))
        return CertificateEnrollmentStatusResponse(
            request_date=datetime(2026, 1, 1, tzinfo=UTC),
            status_code=200,
            status_description="Certificate issued",
            certificate_serial_number="ABCDEF1234567890",
        )


def test_certificate_read_and_enrollment_commands(runner, tmp_path) -> None:
    handle = FakeCertificateEnrollment()
    service = FakeService(
        get_limits={"limits": "ok"},
        get_enrollment_data={"subject": "data"},
        enroll=handle,
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
    _ = csr.write_text("base64-csr\n", encoding="utf-8")
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
    ) == {"reference_number": "enroll-ref", "timestamp": "2026-01-01T00:00:00Z"}
    assert service.called("enroll") == {
        "certificate_name": "demo",
        "certificate_type": "offline",
        "csr": "base64-csr",
        "valid_from": "2026-01-01T00:00:00Z",
    }
    assert handle.wait_calls == []

    assert payload(
        runner.invoke(
            app,
            cli_args("certificates", "enrollment-status", "--reference", "enroll-ref"),
            obj=runtime,
        )
    ) == {"status": "ready"}


@pytest.mark.parametrize("wait", [False, True])
@pytest.mark.parametrize("json_output", [False, True])
def test_certificate_enroll_renders_response_or_waited_status(
    runner, tmp_path, wait, json_output
) -> None:
    handle = FakeCertificateEnrollment()
    service = FakeService(enroll=handle)
    runtime = fake_runtime(auth=type("Auth", (), {"certificates": service})())
    csr = tmp_path / "request.csr"
    _ = csr.write_text("base64-csr\n", encoding="utf-8")
    args = ["--no-config"]
    if json_output:
        args.append("--json")
    args.extend(["certificates", "enroll", "--name", "demo", "--csr-file", str(csr)])
    if wait:
        args.append("--wait")

    result = runner.invoke(app, args, obj=runtime)

    assert result.exit_code == 0, result.output
    if json_output:
        expected = (
            {
                "request_date": "2026-01-01T00:00:00Z",
                "status_code": 200,
                "status_description": "Certificate issued",
                "status_details": None,
                "certificate_serial_number": "ABCDEF1234567890",
            }
            if wait
            else {"reference_number": "enroll-ref", "timestamp": "2026-01-01T00:00:00Z"}
        )
        assert payload(result) == expected
    elif wait:
        assert "status_code: 200" in result.output
        assert "certificate_serial_number: ABCDEF1234567890" in result.output
    else:
        assert "reference_number: enroll-ref" in result.output
        assert "timestamp: 2026-01-01T00:00:00Z" in result.output
    assert handle.wait_calls == ([(60.0, 1.0)] if wait else [])


@pytest.mark.parametrize(
    "poll_override, expected", [(None, (12.0, 1.5)), (0.5, (4.0, 0.5))]
)
def test_certificate_enroll_wait_uses_profile_and_poll_override(
    runner, tmp_path, poll_override, expected
) -> None:
    config = tmp_path / "config.toml"
    _ = config.write_text(
        'active_profile = "demo"\n'
        '[profiles.demo]\nenvironment = "test"\nnip = "5261040828"\n'
        'poll_interval = 1.5\nmax_poll_attempts = 8\n'
        '[profiles.demo.auth]\ntype = "test_certificate"\n',
        encoding="utf-8",
    )
    csr = tmp_path / "request.csr"
    _ = csr.write_text("base64-csr\n", encoding="utf-8")
    handle = FakeCertificateEnrollment()
    runtime = fake_runtime(
        auth=type("Auth", (), {"certificates": FakeService(enroll=handle)})()
    )
    args = ["--config", str(config), "--profile", "demo", "--json"]
    if poll_override is not None:
        args.extend(["--auth-poll-interval", str(poll_override)])
    args.extend(
        ["certificates", "enroll", "--name", "demo", "--csr-file", str(csr), "--wait"]
    )

    result = runner.invoke(app, args, obj=runtime)

    assert payload(result)["status_code"] == 200
    assert handle.wait_calls == [expected]


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
        list=FakePager([{"serial_number": serial}]),
        retrieve=result,
        revoke=None,
    )
    runtime = fake_runtime(auth=type("Auth", (), {"certificates": service})())

    assert payload(
        runner.invoke(
            app, cli_args("certificates", "list", "--page-size", "10"), obj=runtime
        )
    ) == [{"serial_number": serial}]
    assert service.called("list")["params"].page_size == 10

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


def test_certificate_retrieve_writes_the_certificate_ksef_returned(
    runner, tmp_path
) -> None:
    """A real DER payload, Base64-encoded, must reach the file untouched."""

    serial = "014AA06A66BE5720"
    der_as_base64 = base64.b64encode(bytes(range(256))).decode("ascii")
    service = FakeService(
        retrieve=RetrievedCertificatesList(
            certificates=[
                Certificate(
                    serial_number=serial,
                    base64_encoded_certificate=der_as_base64,
                    name="qa-admin",
                    certificate_type="authentication",
                )
            ]
        )
    )
    runtime = fake_runtime(auth=type("Auth", (), {"certificates": service})())
    output_dir = tmp_path / "issued"

    retrieved = payload(
        runner.invoke(
            app,
            cli_args("certificates", "retrieve", serial, "--out-dir", str(output_dir)),
            obj=runtime,
        )
    )

    assert service.called("retrieve")["certificate_serial_numbers"] == [serial]
    assert retrieved["certificates"][0]["base64_encoded_certificate"] == der_as_base64
    assert (
        (output_dir / f"{serial}.b64").read_text(encoding="utf-8")
        == der_as_base64 + "\n"
    )


def test_certificate_retrieve_reports_which_response_field_broke() -> None:
    """An unreadable KSeF response is a remote problem the CLI has to explain."""

    service = FakeService(retrieve=_unreadable_certificate_response())
    runtime = fake_runtime(auth=type("Auth", (), {"certificates": service})())

    result = CliRunner(mix_stderr=False).invoke(
        app,
        cli_args("certificates", "retrieve", "014AA06A66BE5720"),
        obj=runtime,
    )

    assert result.exit_code == 1
    assert result.stdout == ""
    error = json.loads(result.stderr)["error"]
    assert error["type"] == "RemoteServiceError"
    assert error["title"] == "KSeF response could not be parsed"
    assert error["details"][0].startswith("certificates.0.certificate: ")
    assert any("uv tool upgrade" in hint for hint in error["hints"])
    assert any("--verbose" in hint for hint in error["hints"])
