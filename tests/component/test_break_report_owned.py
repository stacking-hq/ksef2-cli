"""Local regressions for root output and process termination contracts."""

import io
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import click
import pytest
from ksef2 import ExceptionCode, KSeFApiError
from pydantic import BaseModel, ValidationError
from rich.console import Console
from typer.testing import CliRunner

from ksef2_cli.app import app
from ksef2_cli.exceptions import (
    UnexpectedCliError,
    error_from_exception,
    render_cli_error,
)


@pytest.mark.parametrize(
    "options", [["--json"], ["--output", "json"], ["--output=json"], ["-o", "json"]]
)
@pytest.mark.parametrize(
    "arguments",
    [
        ["--env", "invalid", "config", "path"],
        ["unknown"],
        ["--profile", "missing", "config", "path"],
        ["--no-config", "auth", "login"],
    ],
)
def test_json_errors_use_stderr(runner, options, arguments):
    result = CliRunner(mix_stderr=False).invoke(app, options + arguments)
    assert result.exit_code in (1, 2)
    assert result.stdout == ""
    error = json.loads(result.stderr)["error"]
    assert error["code"]
    assert error["message"]
    assert "trace_id" in error and "ksef_code" in error


def test_version_precedes_config_resolution(runner, tmp_path):
    config = tmp_path / "bad.toml"
    config.write_text("not valid toml !")
    result = runner.invoke(app, ["--config", str(config), "--version"])
    assert result.exit_code == 0
    assert "ksef2-cli " in result.stdout
    assert "ksef2 " in result.stdout


def test_pydantic_error_has_field_without_documentation_url():
    class Payload(BaseModel):
        count: int

    with pytest.raises(ValidationError) as caught:
        Payload(count="bad")
    message = error_from_exception(caught.value).message
    assert "count:" in message
    assert "https://" not in message


def test_abort_is_expected():
    error = error_from_exception(click.Abort())
    assert not error.reportable
    assert error.message == "Aborted."


def test_api_metadata_printed_once():
    error = error_from_exception(
        KSeFApiError(
            450,
            ExceptionCode.UNKNOWN_ERROR,
            "Rejected",
            ksef_code=21405,
            trace_id="trace-example",
        )
    )
    stream = io.StringIO()
    render_cli_error(error, console=Console(file=stream, width=200))
    for value in ("450", "21405", "trace-example"):
        assert stream.getvalue().count(value) == 1


def test_bug_url_redacts_home():
    url = UnexpectedCliError(
        ValueError(os.path.expanduser("~/private")),
        command=["ksef2", os.path.expanduser("~/file")],
    ).report_url()
    body = parse_qs(urlparse(url).query)["body"][0]
    assert os.path.expanduser("~") not in body


@pytest.mark.parametrize("entry", ["main", "installed"])
@pytest.mark.parametrize(
    ("action", "expected"),
    [
        ("signal.raise_signal(signal.SIGINT)", 130),
        ("raise EOFError()", 1),
        ("raise click.Abort()", 1),
    ],
)
def test_process_exit_through_typer(entry, action, expected):
    script = f"""
import signal, click, runpy
from ksef2_cli.app import app, main
@app.command('interrupt-regression')
def interrupt_regression():
    {action}
"""
    if entry == "main":
        script += "\nmain()\n"
    else:
        installed = shutil.which("ksef2", path=str(Path(sys.executable).parent))
        assert installed
        script += f'\nrunpy.run_path({installed!r}, run_name="__main__")\n'
    result = subprocess.run(
        [sys.executable, "-c", script, "--no-config", "interrupt-regression"],
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == expected, result.stderr
    assert "Report:" not in result.stderr


def test_help_hides_none_defaults(runner):
    for arguments in (["--help"], ["auth", "login", "--help"]):
        result = runner.invoke(app, arguments)
        assert result.exit_code == 0
        assert "default: None" not in result.output


@pytest.mark.parametrize(
    ("options", "json_mode"),
    [
        (["-ojson"], True),
        (["--output=json", "--output=text"], False),
        (["--output=text", "--output=json"], True),
        (["--json", "--output=text"], True),
        (["--profile", "--json"], False),
        (["--token", "--json"], False),
        ([], False),
    ],
)
def test_root_output_grammar(options, json_mode):
    result = CliRunner(mix_stderr=False).invoke(app, options + ["unknown", "--json"])
    assert result.exit_code != 0
    assert result.stdout == ""
    if json_mode:
        assert json.loads(result.stderr)["error"]["message"]
    else:
        assert not result.stderr.startswith('{"error":')


def test_rate_limit_keeps_metadata():
    from ksef2 import KSeFRateLimitError

    error = error_from_exception(
        KSeFRateLimitError(
            30,
            "Too many requests",
            ksef_code=42901,
            trace_id="rate-trace",
            details=["Quota exceeded"],
        )
    )
    assert error.status_code == 429
    assert error.ksef_code == 42901
    assert error.trace_id == "rate-trace"
    assert "Quota exceeded" in error.details
    assert "30 seconds" in error.hints[0]


def test_not_ready_preserves_actionable_message():
    from ksef2 import KSeFNotReadyError

    error = error_from_exception(
        KSeFNotReadyError(
            425,
            ExceptionCode.UNKNOWN_ERROR,
            "SDK detail",
            trace_id="pending-trace",
        )
    )
    stream = io.StringIO()
    render_cli_error(error, console=Console(file=stream, width=200))
    text = stream.getvalue()
    assert "Error: KSeF has not finished processing the request (HTTP 425)." in text
    assert text.count("425") == 1
    assert text.count("SDK detail") == 1


def test_wrapped_sdk_validation_has_readable_fields():
    from ksef2 import KSeFValidationError
    from ksef2.models import InvoicesFilter

    with pytest.raises(KSeFValidationError) as caught:
        InvoicesFilter(role="invalid", date_type="issue_date", date_from="bad")
    message = error_from_exception(caught.value).message
    assert "role:" in message
    assert "https://errors.pydantic.dev" not in message


def test_malformed_resume_state_has_readable_fields(tmp_path):
    from ksef2_cli.exceptions import AuthenticationConfigError
    from ksef2_cli.runtime import read_resume_state

    path = tmp_path / "state.json"
    path.write_text('{"access_token_valid_until": "bad"}')
    with pytest.raises(AuthenticationConfigError) as caught:
        read_resume_state(path)
    assert "access_token_valid_until:" in caught.value.details[0]
    assert "https://errors.pydantic.dev" not in str(caught.value.details)


def test_sigint_during_run_command_confirmation():
    script = """
import click, signal, typer
from ksef2_cli.app import app, main
from ksef2_cli.context import run_command
@app.command('confirm-interrupt')
def command(ctx: typer.Context):
    def interrupt(*args, **kwargs):
        signal.raise_signal(signal.SIGINT)
    click.termui.visible_prompt_func = interrupt
    run_command(ctx, lambda: click.confirm('Continue?', abort=True))
main()
"""
    result = subprocess.run(
        [sys.executable, "-c", script, "--no-config", "confirm-interrupt"],
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 130, result.stderr
    assert "Interrupted." in result.stderr
    assert "Report:" not in result.stderr


def test_sdk_validation_without_structured_error_removes_urls():
    from ksef2 import KSeFValidationError
    from ksef2.models import InvoicesFilter

    with pytest.raises(KSeFValidationError) as caught:
        InvoicesFilter(role="invalid", date_type="issue_date", date_from="bad")
    unstructured = KSeFValidationError(str(caught.value.validation_error))
    message = error_from_exception(unstructured).message
    assert "role" in message
    assert "https://errors.pydantic.dev" not in message


def test_separator_prevents_json_option_detection():
    result = CliRunner(mix_stderr=False).invoke(app, ["--", "unknown", "--json"])
    assert result.exit_code == 2
    assert not result.stderr.startswith('{"error":')
