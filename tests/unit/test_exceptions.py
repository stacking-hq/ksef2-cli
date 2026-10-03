from io import StringIO

from ksef2 import ExceptionCode, KSeFApiError, KSeFAuthPollingTimeoutError
from rich.console import Console

from ksef2_cli.exceptions import (
    RemoteServiceError,
    UnexpectedCliError,
    UsageError,
    error_from_exception,
    redact_argv,
    render_cli_error,
)


def test_ksef_api_error_reports_the_rejection_instead_of_an_internal_error() -> None:
    error = error_from_exception(
        KSeFApiError(450, ExceptionCode.UNKNOWN_ERROR, "bledny token")
    )

    assert isinstance(error, RemoteServiceError)
    assert error.title == "KSeF rejected the request"
    assert error.message == "KSeF request failed with HTTP 450."
    assert any("bledny token" in detail for detail in error.details)
    assert any("450" in detail for detail in error.details)


def test_ksef_timeout_error_reports_the_failure_reason() -> None:
    error = error_from_exception(
        KSeFAuthPollingTimeoutError(reference_number="auth-ref", timeout=60.0)
    )

    assert isinstance(error, RemoteServiceError)
    assert error.title == "KSeF operation failed"
    assert error.exit_code == 1


def test_redact_argv_hides_secret_option_values() -> None:
    assert redact_argv(
        (
            "ksef2",
            "--token",
            "secret-token",
            "--key-password=secret-password",
            "auth",
            "login",
        )
    ) == (
        "ksef2",
        "--token",
        "<redacted>",
        "--key-password=<redacted>",
        "auth",
        "login",
    )


def test_render_cli_error_keeps_actionable_message_at_end() -> None:
    stream = StringIO()
    console = Console(file=stream, force_terminal=False, color_system=None)
    error = UsageError(
        "Can't write to file.txt.",
        title="File write failed",
        details=("Path: file.txt",),
        hints=("Make it writable with: chmod +w file.txt",),
    )

    render_cli_error(error, console=console)

    output = stream.getvalue()
    assert "Path: file.txt" in output
    assert "chmod +w file.txt" in output
    assert output.rstrip().endswith("Error: Can't write to file.txt.")


def test_unexpected_error_report_url_redacts_command() -> None:
    error = UnexpectedCliError(
        RuntimeError("boom"),
        command=("ksef2", "--token", "secret-token", "auth", "login"),
    )

    url = error.report_url()

    assert "secret-token" not in url
    assert "%3Credacted%3E" in url
    assert "Unexpected+CLI+error" in url
