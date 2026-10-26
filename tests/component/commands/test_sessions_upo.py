from types import SimpleNamespace

import pytest
from conftest import FakeClient, FakeService, cli_args, fake_runtime, payload, plain
from ksef2 import ExceptionCode, KSeFNotReadyError
from typer.main import get_command

from ksef2_cli.app import app


@pytest.mark.parametrize(
    ("option", "sdk_argument"),
    [
        ("--ksef-number", "ksef_number"),
        ("--invoice-reference", "invoice_reference_number"),
        ("--upo-reference", "upo_reference_number"),
    ],
)
def test_sessions_upo_downloads_by_reference(runner, tmp_path, option, sdk_argument) -> None:
    invoice_sessions = FakeService(download_upo=b"<UPO>accepted</UPO>")
    output = tmp_path / "nested" / "upo.xml"
    _ = output.parent.mkdir()
    _ = output.write_bytes(b"old UPO")
    result = runner.invoke(
        app,
        cli_args(
            "sessions",
            "upo",
            "--session",
            "session-ref",
            option,
            "identifier",
            "--out",
            str(output),
        ),
        obj=fake_runtime(auth=SimpleNamespace(invoice_sessions=invoice_sessions)),
    )

    assert payload(result) == {"path": str(output), "bytes": len(b"<UPO>accepted</UPO>")}
    assert output.read_bytes() == b"<UPO>accepted</UPO>"
    expected = {
        "ksef_number": None,
        "invoice_reference_number": None,
        "upo_reference_number": None,
    }
    expected[sdk_argument] = "identifier"
    assert invoice_sessions.calls == [("download_upo", ("session-ref",), expected)]


@pytest.mark.parametrize(
    "options",
    [
        [],
        ["--ksef-number", "n", "--invoice-reference", "r"],
        ["--ksef-number", "n", "--upo-reference", "u"],
        ["--invoice-reference", "r", "--upo-reference", "u"],
        ["--ksef-number", "n", "--invoice-reference", "r", "--upo-reference", "u"],
    ],
)
def test_sessions_upo_requires_one_identifier_before_authentication(
    runner, tmp_path, options
) -> None:
    client = FakeClient()
    output = tmp_path / "upo.xml"
    result = runner.invoke(
        app,
        cli_args(
            "sessions",
            "upo",
            "--session",
            "session-ref",
            "--out",
            str(output),
            *options,
        ),
        obj=fake_runtime(client=client),
    )

    assert result.exit_code == 2
    assert (
        "Provide exactly one of --ksef-number, --invoice-reference, or --upo-reference."
        in plain(result.output)
    )
    assert client.entered == 0
    assert not output.exists()


def test_sessions_upo_requires_output_before_authentication(runner) -> None:
    client = FakeClient()
    result = runner.invoke(
        app,
        cli_args("sessions", "upo", "--session", "session-ref", "--ksef-number", "n"),
        obj=fake_runtime(client=client),
    )

    assert result.exit_code == 2
    assert "--out" in plain(result.output)
    assert client.entered == 0


def test_sessions_upo_not_ready_preserves_existing_file(runner, tmp_path) -> None:
    invoice_sessions = FakeService(
        download_upo=KSeFNotReadyError(
            404, ExceptionCode.NOT_PROCESSED_YET, "UPO is not ready for session-ref"
        )
    )
    output = tmp_path / "upo.xml"
    _ = output.write_bytes(b"previous UPO")
    result = runner.invoke(
        app,
        cli_args(
            "sessions",
            "upo",
            "--session",
            "session-ref",
            "--invoice-reference",
            "invoice-ref",
            "--out",
            str(output),
        ),
        obj=fake_runtime(auth=SimpleNamespace(invoice_sessions=invoice_sessions)),
    )

    assert result.exit_code == 1
    message = plain(result.output)
    assert "KSeF has not finished processing the request" in message
    assert "Retry the same command later." in message
    assert "UPO is not ready for session-ref" in message
    assert "Internal error" not in message
    assert output.read_bytes() == b"previous UPO"


def test_sessions_upo_is_registered() -> None:
    command = get_command(app)
    assert "upo" in command.commands["sessions"].commands
