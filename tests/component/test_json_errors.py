import json
import sys
from urllib.parse import parse_qs, urlsplit

import click
import pytest
from click.testing import CliRunner as ClickRunner
from ksef2 import KSeFPermissionDeniedError
from typer.testing import CliRunner

from conftest import FakeClient, FakeService, fake_runtime
from ksef2_cli.app import app, main


@pytest.fixture
def separate_runner():
    return CliRunner(mix_stderr=False)


def error_payload(result, exit_code=1):
    assert result.exit_code == exit_code, result.stderr
    assert result.stdout == ""
    assert result.stderr.count("\n") == 1
    assert "\x1b" not in result.stderr
    return json.loads(result.stderr)["error"]


def test_permission_denied_json(separate_runner):
    client = FakeClient(
        authentication=FakeService(
            with_token=KSeFPermissionDeniedError(
                403,
                "Permission denied",
                ksef_code=21301,
                trace_id="trace-403",
                details=["Missing permission"],
            )
        )
    )
    result = separate_runner.invoke(
        app,
        [
            "--no-config",
            "--json",
            "--nip",
            "1234567890",
            "--token",
            "secret",
            "auth",
            "login",
        ],
        obj=fake_runtime(client=client),
    )
    error = error_payload(result)
    assert error["type"] == "AuthenticationConfigError"
    assert error["title"] == "KSeF denied permission for this operation"
    assert error["hints"] == [
        "Check that the authenticated identity has the required KSeF permissions for this context."
    ]
    assert error["ksef"] == {
        "status_code": 403,
        "exception_code": 21301,
        "message": "Permission denied",
        "ksef_code": 21301,
        "trace_id": "trace-403",
        "details": ["Missing permission"],
    }


def test_conflicting_auth_json(separate_runner):
    result = separate_runner.invoke(
        app,
        [
            "--no-config",
            "--json",
            "--env",
            "test",
            "--nip",
            "1234567890",
            "--token",
            "secret",
            "--test-cert",
            "auth",
            "login",
        ],
    )
    assert error_payload(result) == {
        "type": "AuthenticationConfigError",
        "title": "Command failed",
        "message": "Provide only one auth method: token (--token), test certificate (--test-cert).",
        "details": [],
        "hints": [],
        "exit_code": 1,
    }


@pytest.mark.parametrize("verbose", [False, True])
def test_unexpected_json_redacts_secrets(separate_runner, verbose):
    secret = 'sensitive-password/with spaces"'
    client = FakeClient(authentication=FakeService(with_token=RuntimeError(secret)))
    result = separate_runner.invoke(
        app,
        [
            "--no-config",
            "--json",
            *(["--verbose"] if verbose else []),
            "--nip",
            "1234567890",
            "--token",
            secret,
            "auth",
            "login",
        ],
        obj=fake_runtime(client=client),
    )
    error = error_payload(result)
    assert error["type"] == "UnexpectedCliError"
    assert error["details"] == ["Exception: RuntimeError: <redacted>"]
    report = parse_qs(urlsplit(error["report_url"]).query)["body"][0]
    assert secret not in report
    assert "<redacted>" in report
    assert ("traceback" in error) is verbose
    if verbose:
        assert "RuntimeError: <redacted>" in error["traceback"]
        assert "Traceback (most recent call last)" in error["traceback"]
    assert "ksef" not in error


def invoke_main(monkeypatch, args):
    monkeypatch.setattr(sys, "argv", ["ksef2", *args])
    return ClickRunner(mix_stderr=False).invoke(click.Command("ksef2", callback=main))


@pytest.mark.parametrize(
    "flags",
    [
        ["--json"],
        ["--output", "json"],
        ["--output=json"],
        ["-o", "json"],
        ["--nip", "1234567890", "--json"],
    ],
)
@pytest.mark.parametrize(
    "command,message",
    [
        (["auth", "login", "--token"], "No such option: --token"),
        (["auth", "refresh"], "Missing option"),
        (["--env", "invalid", "auth", "login"], "Invalid value"),
    ],
)
def test_click_usage_json(monkeypatch, flags, command, message):
    result = invoke_main(monkeypatch, ["--no-config", *flags, *command])
    error = error_payload(result, 2)
    assert error["type"] == "UsageError"
    assert error["exit_code"] == 2
    assert message in error["message"]


def test_click_text_is_unchanged(monkeypatch, separate_runner):
    args = ["--no-config", "auth", "login", "--token"]
    # Click includes __main__.__package__ in the implicit program name under pytest.
    monkeypatch.setattr(sys.modules["__main__"], "__package__", None)
    expected = separate_runner.invoke(app, args, prog_name="ksef2")
    result = invoke_main(monkeypatch, args)
    assert result.exit_code == expected.exit_code == 2
    assert result.stdout == expected.stdout == ""
    assert result.stderr == expected.stderr
    assert "No such option" in result.stderr


def test_text_error_regression(separate_runner):
    result = separate_runner.invoke(
        app,
        [
            "--no-config",
            "--env",
            "test",
            "--nip",
            "1234567890",
            "--token",
            "secret",
            "--test-cert",
            "auth",
            "login",
        ],
        env={"COLUMNS": "120", "NO_COLOR": "1", "FORCE_COLOR": None},
    )
    assert result.exit_code == 1
    assert result.stdout == ""
    assert result.stderr == (
        "Error: Provide only one auth method: token (--token), test certificate (--test-cert).\n"
    )


def test_click_usage_redacts_argv_secret(monkeypatch):
    result = invoke_main(
        monkeypatch,
        [
            "--json",
            "--output",
            "password-value",
            "--key-password=password-value",
            "auth",
            "login",
        ],
    )
    error = error_payload(result, 2)
    assert "password-value" not in result.stderr
    assert "<redacted>" in error["message"]


@pytest.mark.parametrize(
    "args",
    [
        ["auth", "login", "--json"],
        ["--token", "--json", "auth", "login", "--unknown"],
        ["--output", "json", "--output", "text", "auth", "login", "--token"],
    ],
)
def test_json_must_be_a_global_output_option(monkeypatch, args):
    result = invoke_main(monkeypatch, ["--no-config", *args])
    assert result.exit_code == 2
    assert "Usage:" in result.stderr
    assert not result.stderr.startswith('{"error":')


def test_main_json_preserves_success_and_error_exit_codes(monkeypatch):
    result = invoke_main(monkeypatch, ["--no-config", "--json", "config", "path"])
    assert result.exit_code == 0
    assert result.stderr == ""
    assert json.loads(result.stdout)

    result = invoke_main(
        monkeypatch,
        [
            "--no-config",
            "--json",
            "--nip",
            "1234567890",
            "--token",
            "secret",
            "--test-cert",
            "auth",
            "login",
        ],
    )
    assert error_payload(result)["type"] == "AuthenticationConfigError"
