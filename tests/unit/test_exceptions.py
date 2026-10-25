from datetime import UTC, datetime
from io import StringIO

import pytest
from ksef2 import (
    ExceptionCode,
    KSeFApiError,
    KSeFArgumentError,
    KSeFAuthError,
    KSeFAuthPollingTimeoutError,
    KSeFAuthTokenRedemptionError,
    KSeFAuthenticationExpiredError,
    KSeFBatchSessionTimeoutError,
    KSeFBatchUploadError,
    KSeFCertificateEnrollmentFailedError,
    KSeFCertificateEnrollmentTimeoutError,
    KSeFClientClosedError,
    KSeFExportFailedError,
    KSeFExportTimeoutError,
    KSeFExternalTransferError,
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
    KSeFSessionError,
    KSeFTokenStatusTimeoutError,
    KSeFUnsupportedEnvironmentError,
    KSeFValidationError,
)
from ksef2.models import InvoiceStatusInfo, SessionInvoiceStatusResponse
from rich.console import Console

from ksef2_cli.exceptions import (
    AuthenticationConfigError,
    CliError,
    ConfigError,
    RemoteServiceError,
    UnexpectedCliError,
    UsageError,
    error_from_exception,
    redact_argv,
    render_cli_error,
)


def _rejected_invoice_status() -> SessionInvoiceStatusResponse:
    return SessionInvoiceStatusResponse(
        ordinal_number=1,
        reference_number="invoice-ref",
        invoice_hash="hash",
        invoicing_date=datetime(2026, 1, 1, tzinfo=UTC),
        status=InvoiceStatusInfo(code=450, description="rejected"),
    )


def _batch_upload_error() -> KSeFBatchUploadError:
    return KSeFBatchUploadError(
        transfer_error=KSeFExternalTransferError(
            operation="upload",
            host="storage.example.invalid",
            reference_number="batch-ref",
            part_ordinal=1,
            status_code=403,
        ),
        recovery_state=None,
    )


_NOT_READY = KSeFNotReadyError(
    404,
    ExceptionCode.NOT_PROCESSED_YET,
    "Invoice is not available for download yet",
    ksef_code=21165,
    trace_id="trace-not-ready",
)
_AUTH_REJECTION = KSeFAuthError(
    403,
    "Brak uprawnień do operacji",
    ksef_code=21301,
    trace_id="trace-auth",
)


_ERROR_MESSAGE = "sdk message"


def _case(
    sdk_error: Exception,
    cli_error: type[CliError],
    title: str,
    *,
    hinted: bool,
    message: str = _ERROR_MESSAGE,
) -> "pytest.ParameterSet":
    """One mapping row: SDK error, CLI error, title, whether a hint is set, expected message."""

    return pytest.param(
        sdk_error,
        cli_error,
        title,
        hinted,
        message,
        id=type(sdk_error).__name__,
    )


_MAPPING_CASES = [
    _case(
        _NOT_READY,
        RemoteServiceError,
        "KSeF has not finished processing yet",
        hinted=True,
        message="KSeF has not finished processing the request (HTTP 404).",
    ),
    _case(
        KSeFAuthenticationExpiredError(),
        AuthenticationConfigError,
        "Authentication expired",
        hinted=True,
    ),
    _case(
        _AUTH_REJECTION,
        AuthenticationConfigError,
        "KSeF rejected the authentication",
        hinted=False,
        message="KSeF request failed with HTTP 403.",
    ),
    _case(
        KSeFAuthPollingTimeoutError(reference_number="auth-ref", timeout=60.0),
        AuthenticationConfigError,
        "Authentication did not complete",
        hinted=True,
    ),
    _case(
        KSeFAuthTokenRedemptionError(),
        AuthenticationConfigError,
        "Authentication did not complete",
        hinted=True,
    ),
    _case(
        KSeFExportTimeoutError("export-ref", 120.0),
        RemoteServiceError,
        "Timed out waiting for KSeF",
        hinted=True,
    ),
    _case(
        KSeFInvoiceProcessingTimeoutError("invoice-ref", 120.0),
        RemoteServiceError,
        "Timed out waiting for KSeF",
        hinted=True,
    ),
    _case(
        KSeFOnlineSessionTimeoutError("session-ref", 120.0),
        RemoteServiceError,
        "Timed out waiting for KSeF",
        hinted=True,
    ),
    _case(
        KSeFBatchSessionTimeoutError("batch-ref", 120.0),
        RemoteServiceError,
        "Timed out waiting for KSeF",
        hinted=True,
    ),
    _case(
        KSeFTokenStatusTimeoutError("token-ref", 120.0),
        RemoteServiceError,
        "Timed out waiting for KSeF",
        hinted=True,
    ),
    _case(
        KSeFPermissionOperationTimeoutError("permission-ref", 120.0),
        RemoteServiceError,
        "Timed out waiting for KSeF",
        hinted=True,
    ),
    _case(
        KSeFCertificateEnrollmentTimeoutError("enrollment-ref", 120.0),
        RemoteServiceError,
        "Timed out waiting for KSeF",
        hinted=True,
    ),
    _case(
        KSeFInvoiceQueryTimeoutError(120.0),
        RemoteServiceError,
        "Timed out waiting for KSeF",
        hinted=True,
    ),
    _case(
        KSeFInvoiceDownloadTimeoutError("ksef-number", 120.0),
        RemoteServiceError,
        "Timed out waiting for KSeF",
        hinted=True,
    ),
    _case(
        KSeFExportFailedError("export-ref", 415, "expired", ["too old"]),
        RemoteServiceError,
        "KSeF reported a failure",
        hinted=False,
    ),
    _case(
        KSeFPermissionOperationFailedError("permission-ref", 420, "rejected"),
        RemoteServiceError,
        "KSeF reported a failure",
        hinted=False,
    ),
    _case(
        KSeFCertificateEnrollmentFailedError("enrollment-ref", 400, "rejected"),
        RemoteServiceError,
        "KSeF reported a failure",
        hinted=False,
    ),
    _case(
        KSeFInvoiceRejectedError("invoice-ref", _rejected_invoice_status()),
        RemoteServiceError,
        "KSeF reported a failure",
        hinted=False,
    ),
    _case(
        _batch_upload_error(),
        RemoteServiceError,
        "KSeF reported a failure",
        hinted=False,
    ),
    _case(
        KSeFArgumentError("Pass exactly one of form_code or state."),
        UsageError,
        "Command failed",
        hinted=False,
    ),
    _case(
        KSeFUnsupportedEnvironmentError("Available only in TEST."),
        UsageError,
        "Command failed",
        hinted=False,
    ),
    _case(
        KSeFClientClosedError("Client is closed."),
        UnexpectedCliError,
        "Unexpected error",
        hinted=True,
        message="Unexpected internal error. Re-run with --verbose for a traceback.",
    ),
]


@pytest.mark.parametrize(
    ("sdk_error", "cli_error", "title", "hinted", "message"), _MAPPING_CASES
)
def test_each_sdk_exception_maps_to_its_own_cli_error(
    sdk_error: Exception,
    cli_error: type[CliError],
    title: str,
    hinted: bool,
    message: str | None,
) -> None:
    error = error_from_exception(sdk_error)

    assert type(error) is cli_error
    assert error.title == title
    assert bool(error.hints) is hinted
    assert error.exit_code == (2 if cli_error is UsageError else 1)
    expected = sdk_error.args[0] if message is _ERROR_MESSAGE else message
    assert error.message == expected


@pytest.mark.parametrize(
    ("sdk_error", "status_code", "ksef_code", "trace_id"),
    [
        pytest.param(_NOT_READY, 404, 21165, "trace-not-ready", id="KSeFNotReadyError"),
        pytest.param(_AUTH_REJECTION, 403, 21301, "trace-auth", id="KSeFAuthError"),
        pytest.param(
            KSeFApiError(
                450,
                ExceptionCode.VALIDATION_ERROR,
                "Nieprawidłowy dokument",
                ksef_code=21405,
                trace_id="trace-api",
            ),
            450,
            21405,
            "trace-api",
            id="KSeFApiError",
        ),
    ],
)
def test_api_error_details_survive_the_mapping(
    sdk_error: Exception,
    status_code: int,
    ksef_code: int,
    trace_id: str,
) -> None:
    error = error_from_exception(sdk_error)

    assert f"HTTP status: {status_code}" in error.details
    assert f"KSeF code: {ksef_code}" in error.details
    assert f"Trace ID: {trace_id}" in error.details


@pytest.mark.parametrize(
    ("sdk_error", "cli_error", "title", "hint"),
    [
        pytest.param(
            KSeFInvoiceRenderingError("FA(3) schema is missing"),
            UsageError,
            "Command failed",
            None,
            id="rendering",
        ),
        pytest.param(
            KSeFRateLimitError(30, "Za dużo zapytań"),
            RemoteServiceError,
            "KSeF rate limit exceeded",
            "Wait at least 30 seconds before retrying.",
            id="rate-limit",
        ),
        pytest.param(
            KSeFValidationError("NIP is invalid"),
            ConfigError,
            "Command failed",
            None,
            id="validation",
        ),
        pytest.param(
            KSeFSessionError("invoice sent on a closed session"),
            RemoteServiceError,
            "KSeF operation failed",
            None,
            id="generic-ksef-error",
        ),
    ],
)
def test_branches_that_predate_the_1_0_mapping_keep_working(
    sdk_error: Exception,
    cli_error: type[CliError],
    title: str,
    hint: str | None,
) -> None:
    error = error_from_exception(sdk_error)

    assert type(error) is cli_error
    assert error.title == title
    assert error.message == sdk_error.args[0]
    assert error.hints == (() if hint is None else (hint,))


def test_client_closed_error_stays_reportable() -> None:
    error = error_from_exception(KSeFClientClosedError("Client is closed."))

    assert isinstance(error, UnexpectedCliError)
    assert error.reportable


def test_ksef_api_error_reports_the_rejection_instead_of_an_internal_error() -> None:
    error = error_from_exception(
        KSeFApiError(450, ExceptionCode.UNKNOWN_ERROR, "bledny token")
    )

    assert isinstance(error, RemoteServiceError)
    assert error.title == "KSeF rejected the request"
    assert error.message == "KSeF request failed with HTTP 450."
    assert any("bledny token" in detail for detail in error.details)
    assert any("450" in detail for detail in error.details)


def test_ksef_auth_timeout_names_the_reason_for_the_failure() -> None:
    error = error_from_exception(
        KSeFAuthPollingTimeoutError(reference_number="auth-ref", timeout=60.0)
    )

    assert isinstance(error, AuthenticationConfigError)
    assert error.title == "Authentication did not complete"
    assert "Authentication auth-ref not ready after 60.0s" in error.message
    assert any("--auth-timeout" in hint for hint in error.hints)
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


@pytest.mark.parametrize(
    ("sdk_error", "cli_error", "title", "hinted", "message"), _MAPPING_CASES
)
def test_sdk_hints_for_python_callers_stay_out_of_cli_errors(
    sdk_error: Exception,
    cli_error: type[CliError],
    title: str,
    hinted: bool,
    message: str | None,
) -> None:
    error = error_from_exception(sdk_error)

    shown = [error.message, *error.details]
    assert not any("Hint:" in line for line in shown), shown


def test_permission_denied_reports_required_permissions() -> None:
    error = error_from_exception(
        KSeFPermissionDeniedError(
            403,
            "Brak uprawnień do operacji",
            ksef_code=21301,
            trace_id="trace-permission",
        )
    )

    assert isinstance(error, AuthenticationConfigError)
    assert error.title == "KSeF denied permission for this operation"
    assert error.hints == (
        "Check that the authenticated identity has the required KSeF permissions for this context.",
    )


def test_usage_error_defaults_to_two_and_preserves_explicit_override() -> None:
    assert UsageError("Invalid input").exit_code == 2
    assert UsageError("Explicit status", exit_code=1).exit_code == 1
    assert CliError("Runtime failure").exit_code == 1
