"""Human-oriented CLI exceptions and rendering helpers."""

import json
import re
import os
import sys
import traceback
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Iterable, Sequence
from urllib.parse import quote, quote_plus, urlencode

import click
from ksef2 import (
    KSeFApiError,
    KSeFArgumentError,
    KSeFAuthenticationExpiredError,
    KSeFAuthError,
    KSeFAuthPollingTimeoutError,
    KSeFAuthTokenRedemptionError,
    KSeFBatchSessionTimeoutError,
    KSeFBatchUploadError,
    KSeFCertificateEnrollmentFailedError,
    KSeFCertificateEnrollmentTimeoutError,
    KSeFClientClosedError,
    KSeFException,
    KSeFExportFailedError,
    KSeFExportTimeoutError,
    KSeFInvoiceDownloadTimeoutError,
    KSeFInvoiceProcessingTimeoutError,
    KSeFInvoiceQueryTimeoutError,
    KSeFInvoiceRejectedError,
    KSeFInvoiceRenderingError,
    KSeFNotReadyError,
    KSeFOnlineSessionTimeoutError,
    KSeFPermissionDeniedError,
    KSeFPermissionOperationFailedError,
    KSeFPermissionOperationTimeoutError,
    KSeFRateLimitError,
    KSeFResponseValidationError,
    KSeFTokenStatusTimeoutError,
    KSeFUnsupportedEnvironmentError,
    KSeFValidationError,
)
from pydantic import ValidationError
from rich.console import Console
from rich.markup import escape

BUG_REPORT_URL = "https://github.com/stacking-hq/ksef2-cli/issues/new"

# Both PDF commands (`invoices export-pdf` and `fa3 render --pdf`) render with
# WeasyPrint, which arrives as an optional extra. One message for both, so the
# install command a user sees matches the package they installed.
PDF_INSTALL_HINT = (
    'Install the extra with: uv tool install "ksef2-cli[pdf]" or '
    'pip install "ksef2-cli[pdf]". In a project that depends on the SDK directly: '
    "uv add 'ksef2[pdf]'."
)
PDF_SYSTEM_LIBS_HINT = (
    "On Linux, WeasyPrint needs system libraries: libpango-1.0-0, libharfbuzz0b, "
    "libpangoft2-1.0-0, and libharfbuzz-subset0."
)
PDF_MACOS_LIBS_HINT = (
    "On macOS, install WeasyPrint's libraries with Homebrew: brew install pango. If "
    "they are installed and the load still fails, run the command through the dyld "
    "fallback path: DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib ksef2 ... "
    "(/usr/local/lib on Intel Macs)."
)


def pdf_system_libs_hint() -> str:
    """The native-library hint for the platform this command runs on.

    The Linux package names mean nothing on macOS, where the usual fix is Homebrew plus
    a dyld fallback path, so each platform gets the hint its user can act on.
    """

    return PDF_MACOS_LIBS_HINT if sys.platform == "darwin" else PDF_SYSTEM_LIBS_HINT


SECRET_OPTIONS = {
    "--key-password",
    "--ksef-token",
    "--p12-password",
    "--refresh-token",
    "--token",
}

# SDK exceptions that mean the user can redo the call with different arguments.
_USAGE_SDK_ERRORS = (KSeFArgumentError, KSeFUnsupportedEnvironmentError)

# SDK exceptions for authentication that started but never reached a usable session.
_AUTH_INCOMPLETE_SDK_ERRORS = (
    KSeFAuthPollingTimeoutError,
    KSeFAuthTokenRedemptionError,
)

# SDK exceptions raised when a KSeF job outlived the deadline set on the command.
_POLLING_TIMEOUT_SDK_ERRORS = (
    KSeFExportTimeoutError,
    KSeFInvoiceProcessingTimeoutError,
    KSeFOnlineSessionTimeoutError,
    KSeFBatchSessionTimeoutError,
    KSeFTokenStatusTimeoutError,
    KSeFPermissionOperationTimeoutError,
    KSeFCertificateEnrollmentTimeoutError,
    KSeFInvoiceQueryTimeoutError,
    KSeFInvoiceDownloadTimeoutError,
)

# SDK exceptions carrying KSeF's own account of a job that finished badly.
_REPORTED_FAILURE_SDK_ERRORS = (
    KSeFExportFailedError,
    KSeFPermissionOperationFailedError,
    KSeFCertificateEnrollmentFailedError,
    KSeFInvoiceRejectedError,
    KSeFBatchUploadError,
)


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
        self.status_code: int | None = None
        self.ksef_code: int | None = None
        self.trace_id: str | None = None
        self.code = type(self).__name__
        self.message = message
        self.title = title
        self.details = tuple(details)
        self.hints = tuple(hints)
        self.exit_code = exit_code
        self.reportable = reportable
        self.show_traceback = show_traceback


class Aborted(CliError):
    """The user interrupted the command."""


class UsageError(CliError):
    """The command is valid, but the user supplied incomplete or conflicting input."""

    def __init__(
        self,
        message: str,
        *,
        title: str = "Command failed",
        details: Iterable[str] = (),
        hints: Iterable[str] = (),
        exit_code: int = 2,
        reportable: bool = False,
        show_traceback: bool = False,
    ) -> None:
        super().__init__(
            message,
            title=title,
            details=details,
            hints=hints,
            exit_code=exit_code,
            reportable=reportable,
            show_traceback=show_traceback,
        )


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


class MissingOptionalDependencyError(CliError):
    """A command needs an install extra that is not present in this environment."""


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
        body = redact_local_paths(body)
        return f"{BUG_REPORT_URL}?{urlencode({'title': title, 'body': body})}"


def error_from_exception(error: Exception) -> CliError:
    """Map common Python exceptions into the CLI error hierarchy."""

    if isinstance(error, (click.Abort, KeyboardInterrupt, EOFError)):
        interrupted = isinstance(error, KeyboardInterrupt) or isinstance(
            error.__cause__ or error.__context__, KeyboardInterrupt
        )
        return Aborted(
            "Interrupted." if interrupted else "Aborted.",
            exit_code=130 if interrupted else 1,
        )
    if isinstance(error, ValidationError):
        return UsageError(format_validation_error(error))
    if isinstance(error, CliError):
        return error
    if isinstance(error, KSeFClientClosedError):
        # The CLI keeps one client open for the whole command, so this is our bug.
        return UnexpectedCliError(error)
    if isinstance(error, _USAGE_SDK_ERRORS):
        return UsageError(_sdk_message(error))
    if isinstance(error, KSeFInvoiceRenderingError):
        return _from_rendering_error(error)
    if isinstance(error, KSeFResponseValidationError):
        # Subclass of KSeFValidationError: the remote payload, not local config.
        return RemoteServiceError(
            "KSeF answered with a body the installed SDK could not read.",
            title="KSeF response could not be parsed",
            details=_response_validation_details(error),
            hints=(
                "Update the CLI together with the SDK it installs, whose response "
                'models follow the KSeF schema: uv tool upgrade "ksef2-cli".',
                "Re-run with --verbose to capture the SDK traceback, and report the "
                f"field errors above at {BUG_REPORT_URL} when they point at a "
                "response KSeF should have returned.",
            ),
            show_traceback=True,
        )
    if isinstance(error, KSeFValidationError):
        validation = error.validation_error
        if isinstance(validation, ValidationError):
            return ConfigError(format_validation_error(validation))
        return ConfigError(_sdk_message(error))
    if isinstance(error, KSeFAuthenticationExpiredError):
        return AuthenticationConfigError(
            _sdk_message(error),
            title="Authentication expired",
            hints=("Authenticate again with: ksef2 auth login --save-state PATH",),
        )
    if isinstance(error, KSeFAuthError):
        return _from_api_error(
            error,
            cli_error=AuthenticationConfigError,
            title="KSeF rejected the authentication",
        )
    if isinstance(error, KSeFPermissionDeniedError):
        return _from_api_error(
            error,
            cli_error=AuthenticationConfigError,
            title="KSeF denied permission for this operation",
            hints=(
                "Check that the authenticated identity has the required KSeF permissions "
                "for this context.",
            ),
        )
    if isinstance(error, KSeFNotReadyError):
        return _from_api_error(
            error,
            cli_error=RemoteServiceError,
            title="KSeF has not finished processing yet",
            message=f"KSeF has not finished processing the request (HTTP {error.status_code}).",
            hints=("Retry the same command later.",),
        )
    if isinstance(error, KSeFRateLimitError):
        hints = (
            f"Wait at least {error.retry_after} seconds before retrying."
            if error.retry_after is not None
            else "Wait before retrying the same command."
        )
        return _from_api_error(
            error,
            cli_error=RemoteServiceError,
            title="KSeF rate limit exceeded",
            message=_sdk_message(error),
            hints=(hints,),
        )
    if isinstance(error, _AUTH_INCOMPLETE_SDK_ERRORS):
        return AuthenticationConfigError(
            _sdk_message(error),
            title="Authentication did not complete",
            hints=("Raise --auth-timeout, or check that the credentials are valid.",),
        )
    if isinstance(error, _POLLING_TIMEOUT_SDK_ERRORS):
        return RemoteServiceError(
            _sdk_message(error),
            title="Timed out waiting for KSeF",
            hints=(
                "KSeF is still working, so check the status later or raise --timeout "
                "where the command has one.",
            ),
        )
    if isinstance(error, _REPORTED_FAILURE_SDK_ERRORS):
        return RemoteServiceError(_sdk_message(error), title="KSeF reported a failure")
    if isinstance(error, KSeFApiError):
        return _from_api_error(
            error,
            cli_error=RemoteServiceError,
            title="KSeF rejected the request",
        )
    if isinstance(error, KSeFException):
        return RemoteServiceError(_sdk_message(error), title="KSeF operation failed")
    if isinstance(error, ValueError):
        return UsageError(_without_validation_urls(str(error)))
    if isinstance(error, OSError):
        return FileCliError.from_os_error(error)
    return UnexpectedCliError(error)


# The bundled FA(3) stylesheet reads its code lists from the network when code
# lookups are on, so libxslt reports an unreachable list as a transform failure.
_UNRESOLVED_URI = "Cannot resolve URI"


def _from_rendering_error(error: KSeFInvoiceRenderingError) -> CliError:
    """Keep the stylesheet's own reason visible on a rendering failure.

    The SDK message names only the transformation step, so a run that asked for code
    lookups fails with no clue that a code list is what could not be read.
    """

    cause = error.__cause__
    if cause is None:
        return UsageError(_sdk_message(error))
    reason = " ".join(str(cause).split())
    hints: tuple[str, ...] = ()
    if _UNRESOLVED_URI in reason:
        hints = (
            "Re-run without code lookups: the stylesheet then prints coded values as "
            "codes and reads no code list from the network.",
        )
    return UsageError(
        _sdk_message(error), details=(f"Stylesheet error: {reason}",), hints=hints
    )


def _sdk_message(error: KSeFException) -> str:
    """Return the SDK message without the ``Hint:`` line ``str(error)`` appends.

    SDK hints name Python calls such as ``wait()`` or ``with_token()``, which
    mean nothing on the command line; the CLI error carries its own hints.
    """

    return _without_validation_urls(str(error.args[0]) if error.args else str(error))


# One malformed field can reject every item in a list; the first few explain it.
_MAX_REJECTED_FIELDS = 8


def _response_validation_details(error: KSeFResponseValidationError) -> tuple[str, ...]:
    """Name the response fields the SDK model rejected.

    ``KSeFResponseValidationError`` says only ``Invalid response payload``. Pydantic
    knows which field broke: the SDK hands it over through ``errors()`` when it
    attached it, and keeps it as the raised error's cause otherwise.
    """

    errors = list(error.errors())
    cause = error.__cause__
    if not errors and isinstance(cause, ValidationError):
        errors = list(cause.errors())
    if not errors:
        return (f"Exception: {type(error).__name__}: {error}",)
    shown = errors[:_MAX_REJECTED_FIELDS]
    details = [
        "{}: {}".format(
            ".".join(str(part) for part in item.get("loc", ())) or "body",
            item.get("msg", "rejected"),
        )
        for item in shown
    ]
    if len(errors) > len(shown):
        details.append(f"... and {len(errors) - len(shown)} more.")
    return (*details, f"Rejected fields: {len(errors)}.")


def _from_api_error(
    error: KSeFApiError,
    *,
    cli_error: type[CliError],
    title: str,
    message: str | None = None,
    hints: Iterable[str] = (),
) -> CliError:
    """Build a CLI error that keeps the HTTP status, KSeF code and trace ID of an API error."""

    result = cli_error(
        message or f"KSeF request failed with HTTP {error.status_code}.",
        title=title,
        details=(
            _sdk_message(error),
            *error.details,
            f"HTTP status: {error.status_code}",
            *(
                (f"KSeF code: {error.ksef_code}",)
                if error.ksef_code is not None
                else ()
            ),
            *((f"Trace ID: {error.trace_id}",) if error.trace_id else ()),
        ),
        hints=tuple(hints),
    )
    result.status_code = error.status_code
    result.ksef_code = error.ksef_code
    result.trace_id = error.trace_id
    result.code = error.code
    return result


def render_cli_error(
    error: CliError,
    *,
    console: Console,
    verbose: bool = False,
    json_output: bool = False,
    source: Exception | None = None,
    secrets: Iterable[str] = (),
) -> None:
    """Render errors on stderr, with one JSON envelope in JSON mode.

    JSON retains the typed error fields and nested SDK metadata, plus stable
    code, ksef_code, and trace_id fields. Usage errors use code USAGE_ERROR.
    Credentials and local home/virtualenv paths are redacted in every mode.
    """

    from ksef2_cli.app import _json_requested, _raw_argv

    ctx = click.get_current_context(silent=True)
    settings = ctx.find_root().obj if ctx is not None else None
    json_output = (
        json_output
        or _json_requested.get()
        or getattr(settings, "output", None) == "json"
    )
    command = _raw_argv.get()
    if command is None:
        command = error.command if isinstance(error, UnexpectedCliError) else sys.argv
    secret_values = set(secrets)
    for original, redacted in zip(command, redact_argv(command)):
        if original != redacted:
            secret_values.add(
                original if redacted == "<redacted>" else original.partition("=")[2]
            )
    for option in SECRET_OPTIONS:
        value = os.environ.get("KSEF2_" + option[2:].replace("-", "_").upper())
        if value:
            secret_values.add(value)

    def redact(value: object) -> object:
        if isinstance(value, str):
            for secret in sorted(filter(None, secret_values), key=len, reverse=True):
                for form in {secret, quote(secret, safe=""), quote_plus(secret)}:
                    value = value.replace(form, "<redacted>")
            return redact_local_paths(value)
        if isinstance(value, list):
            return [redact(item) for item in value]
        if isinstance(value, dict):
            return {key: redact(item) for key, item in value.items()}
        return value

    if json_output:
        payload: dict[str, object] = {
            "code": "USAGE_ERROR" if error.exit_code == 2 else error.code,
            "ksef_code": error.ksef_code,
            "trace_id": error.trace_id,
            "type": type(error).__name__,
            "title": error.title,
            "message": error.message,
            "details": list(error.details),
            "hints": list(error.hints),
            "exit_code": error.exit_code,
        }
        if error.status_code is not None:
            payload["status_code"] = error.status_code
        if isinstance(source, KSeFApiError):
            ksef: dict[str, object] = {
                "status_code": source.status_code,
                "exception_code": source.exception_code.value,
                "message": _sdk_message(source),
            }
            for name in ("ksef_code", "trace_id", "details"):
                value = getattr(source, name)
                if value is not None and value != [] and value != "":
                    ksef[name] = value
            if source.response is not None:
                ksef["response"] = source.response.model_dump(mode="json")
            payload["ksef"] = ksef
        if error.reportable and isinstance(error, UnexpectedCliError):
            payload["report_url"] = error.report_url()
        if verbose and error.show_traceback:
            original = error.error if isinstance(error, UnexpectedCliError) else error
            payload["traceback"] = "".join(traceback.format_exception(original))

        print(
            json.dumps(
                {
                    "error": {
                        key: value if key in {"type", "exit_code"} else redact(value)
                        for key, value in payload.items()
                    }
                },
                ensure_ascii=False,
            ),
            file=sys.stderr,
            flush=True,
        )
        return

    if verbose and error.show_traceback:
        original = source or (
            error.error if isinstance(error, UnexpectedCliError) else error
        )
        console.print(
            escape(str(redact("".join(traceback.format_exception(original)))))
        )

    message = error.message
    details = error.details
    if error.status_code is not None:
        if message == f"KSeF request failed with HTTP {error.status_code}." and details:
            message = details[0]
        details = tuple(
            detail
            for detail in dict.fromkeys(details)
            if detail != message
            and not (
                detail.startswith("HTTP status:")
                and f"HTTP {error.status_code}" in message
                or detail.startswith("KSeF code:")
                and f"KSeF code {error.ksef_code}" in message
                or detail.startswith("Trace ID:")
                and detail in message
            )
        )
    if details:
        for detail in details:
            console.print(escape(str(redact(detail))))

    if error.hints:
        console.print("[bold]Try:[/]")
        for hint in error.hints:
            console.print(f"  - {escape(str(redact(hint)))}")

    if error.reportable and isinstance(error, UnexpectedCliError):
        console.print(f"Report: {redact(error.report_url())}")

    console.print(f"[red]Error:[/] {escape(str(redact(message)))}")


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


def format_validation_error(error: ValidationError | KSeFValidationError) -> str:
    if isinstance(error, KSeFValidationError):
        if isinstance(error.validation_error, ValidationError):
            error = error.validation_error
        else:
            return _sdk_message(error)
    return "\n".join(
        f"{'.'.join(map(str, item['loc'])) or 'value'}: {item['msg']}"
        for item in error.errors(include_url=False, include_input=False)
    )


def redact_local_paths(value: str) -> str:
    value = value.replace(str(Path.home()), "<home>")
    if sys.prefix != sys.base_prefix:
        value = value.replace(sys.prefix, "<venv>")
    return re.sub(r"(?:/[^/\s\"']+)+/\.venv(?=/|\b)", "<venv>", value)


def _without_validation_urls(message: str) -> str:
    return re.sub(
        r"\n[ \t]*For further information visit https://errors\.pydantic\.dev/[^\s]+",
        "",
        message,
    )
