from io import StringIO

from rich.console import Console

from ksef2_cli.exceptions import (
    UnexpectedCliError,
    UsageError,
    redact_argv,
    render_cli_error,
)


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
