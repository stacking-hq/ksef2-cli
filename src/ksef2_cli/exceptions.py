"""Human-oriented CLI exceptions and rendering helpers."""

import sys
import traceback
from importlib.metadata import PackageNotFoundError, version
from typing import Iterable, Sequence
from urllib.parse import urlencode

from rich.console import Console
from rich.markup import escape

BUG_REPORT_URL = "https://github.com/stacking-hq/ksef2-cli/issues/new"
SECRET_OPTIONS = {
    "--key-password",
    "--ksef-token",
    "--p12-password",
    "--refresh-token",
    "--token",
}


class CliError(Exception):
    """Base class for expected, human-actionable CLI errors."""

    def __init__(
        self,
        message: str,
        *,
        title: str = "Command failed",
        details: Iterable[str] = (),
        hints: Iterable[str] = (),
        exit_code: int = 1,
        reportable: bool = False,
        show_traceback: bool = False,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.title = title
        self.details = tuple(details)
        self.hints = tuple(hints)
        self.exit_code = exit_code
        self.reportable = reportable
        self.show_traceback = show_traceback


class UsageError(CliError):
    """The command is valid, but the user supplied incomplete or conflicting input."""


class ConfigError(CliError):
    """The local CLI configuration is missing, malformed, or contradictory."""


class FileCliError(CliError):
    """A local file operation failed and can likely be fixed by the user."""

    @classmethod
    def from_os_error(
        cls,
        error: OSError,
        *,
        action: str = "access",
        path: str | None = None,
    ) -> "FileCliError":
        target = path or getattr(error, "filename", None)
        details = [f"Path: {target}"] if target else []
        hints = _file_hints(action=action, path=target)
        return cls(
            f"Can't {action} {target or 'the requested file'}: {error.strerror or error}",
            title="File operation failed",
            details=details,
            hints=hints,
        )


class AuthenticationConfigError(CliError):
    """Authentication settings are absent, incomplete, or mutually exclusive."""


class RemoteServiceError(CliError):
    """The KSeF service rejected or could not complete a request."""


class UnexpectedCliError(CliError):
    """An internal failure that should be reported as a bug."""

    def __init__(
        self, error: BaseException, *, command: Sequence[str] | None = None
    ) -> None:
        self.error = error
        self.command = tuple(command or sys.argv)
        error_type = type(error).__name__
        super().__init__(
            "Unexpected internal error. Re-run with --verbose for a traceback.",
            title="Unexpected error",
            details=(f"Exception: {error_type}: {error}",),
            hints=(
                "Re-run the same command with --verbose to capture the traceback.",
                "Open a bug report with the pre-filled URL below if this keeps happening.",
            ),
            reportable=True,
            show_traceback=True,
        )

    def report_url(self) -> str:
        title = f"Unexpected CLI error: {type(self.error).__name__}"
        body = "\n".join(
            [
                "## What happened",
                "",
                str(self.error),
                "",
                "## Command",
                "",
                f"`{' '.join(redact_argv(self.command))}`",
                "",
                "## Version",
                "",
                _package_version(),
                "",
                "## Traceback",
                "",
                "```text",
                "".join(
                    traceback.format_exception(
                        type(self.error), self.error, self.error.__traceback__
                    )
                ),
                "```",
            ]
        )
        return f"{BUG_REPORT_URL}?{urlencode({'title': title, 'body': body})}"


def error_from_exception(error: Exception) -> CliError:
    """Map common Python exceptions into the CLI error hierarchy."""

    if isinstance(error, CliError):
        return error
    if isinstance(error, ValueError):
        return UsageError(str(error))
    if isinstance(error, OSError):
        return FileCliError.from_os_error(error)
    return UnexpectedCliError(error)


def render_cli_error(
    error: CliError, *, console: Console, verbose: bool = False
) -> None:
    """Render a concise, actionable error message."""

    if verbose and error.show_traceback:
        console.print_exception()

    if error.details:
        for detail in error.details:
            console.print(escape(detail))

    if error.hints:
        console.print("[bold]Try:[/]")
        for hint in error.hints:
            console.print(f"  - {escape(hint)}")

    if error.reportable and isinstance(error, UnexpectedCliError):
        console.print(f"Report: {error.report_url()}")

    console.print(f"[red]Error:[/] {escape(error.message)}")


def redact_argv(argv: Sequence[str]) -> tuple[str, ...]:
    """Remove likely secret values from a command before logging or reporting it."""

    redacted: list[str] = []
    redact_next = False
    for arg in argv:
        if redact_next:
            redacted.append("<redacted>")
            redact_next = False
            continue

        option, separator, value = arg.partition("=")
        if option in SECRET_OPTIONS:
            if separator:
                redacted.append(f"{option}=<redacted>")
            else:
                redacted.append(arg)
                redact_next = True
            continue

        redacted.append(arg)

    return tuple(redacted)


def _file_hints(*, action: str, path: str | None) -> tuple[str, ...]:
    if not path:
        return ()
    if action in {"write", "create"}:
        return (
            f"Check that the parent directory exists and is writable: {path}",
            f"If the file exists, check permissions with: ls -l {path}",
        )
    return (f"Check that the file exists and is readable: {path}",)


def _package_version() -> str:
    try:
        return version("ksef2-cli")
    except PackageNotFoundError:
        return "unknown"
