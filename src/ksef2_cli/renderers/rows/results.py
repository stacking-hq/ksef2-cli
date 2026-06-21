"""Plain-text handlers for CLI-owned result models."""

import json

from ksef2_cli.renderers.text import (
    PlainTextRenderer,
    format_fields,
    format_row,
    format_status_line,
    register_text,
)
from ksef2_cli.commands.invoices.models import (
    ExportHandleSaved,
    ExportPaths,
    InvoiceWorkflowBatch,
    InvoiceWorkflowItem,
    InvoicesSendResult,
    InvoicesStatusResult,
    InvoicesUpoResult,
)
from ksef2_cli.results import (
    ActionResult,
    BatchSubmitted,
    CertificateRevoked,
    ConfigInitialized,
    ConfigPathResult,
    ConfigShowResult,
    CurrentSessionTerminated,
    FocusedResult,
    LimitReset,
    LimitUpdated,
    OnlineSendItem,
    OnlineSendResult,
    ProfileCurrent,
    ProfileListItem,
    ProfileListResult,
    ProfileSaved,
    ProfileSelected,
    OnlineSessionOpened,
    ProductionRateLimitsSet,
    SavedFile,
    SessionClosed,
    TestSandboxReady,
)


def register() -> None:
    @register_text(FocusedResult)
    def _(value: FocusedResult, renderer: PlainTextRenderer) -> str:
        return renderer.render(value.items)

    @register_text(ActionResult)
    def _(value: ActionResult, renderer: PlainTextRenderer) -> str:
        return format_fields(
            (
                ("reference_number", value.reference_number),
                ("revoked", value.revoked),
            )
        )

    @register_text(LimitUpdated)
    def _(value: LimitUpdated, renderer: PlainTextRenderer) -> str:
        return format_fields((("kind", value.kind), ("updated", value.updated)))

    @register_text(LimitReset)
    def _(value: LimitReset, renderer: PlainTextRenderer) -> str:
        return format_fields((("kind", value.kind), ("reset", value.reset)))

    @register_text(ProductionRateLimitsSet)
    def _(value: ProductionRateLimitsSet, renderer: PlainTextRenderer) -> str:
        return format_fields((("api_rate_limits", value.api_rate_limits),))

    @register_text(SessionClosed)
    def _(value: SessionClosed, renderer: PlainTextRenderer) -> str:
        return format_fields(
            (("reference_number", value.reference_number), ("closed", value.closed))
        )

    @register_text(CurrentSessionTerminated)
    def _(value: CurrentSessionTerminated, renderer: PlainTextRenderer) -> str:
        return format_fields((("terminated_current", value.terminated_current),))

    @register_text(CertificateRevoked)
    def _(value: CertificateRevoked, renderer: PlainTextRenderer) -> str:
        return format_fields(
            (
                ("serial_number", value.serial_number),
                ("reason", value.reason),
                ("revoked", value.revoked),
            )
        )

    @register_text(ConfigPathResult)
    def _(value: ConfigPathResult, renderer: PlainTextRenderer) -> str:
        return format_fields(
            (("path", value.path), ("exists", value.exists), ("loaded", value.loaded))
        )

    @register_text(ConfigShowResult)
    def _(value: ConfigShowResult, renderer: PlainTextRenderer) -> str:
        return format_fields(
            (("path", value.path), ("exists", value.exists), ("config", value.config))
        )

    @register_text(ConfigInitialized)
    def _(value: ConfigInitialized, renderer: PlainTextRenderer) -> str:
        return format_fields(
            (("path", value.path), ("mode", value.mode), ("config", value.config))
        )

    @register_text(ProfileListResult)
    def _(value: ProfileListResult, renderer: PlainTextRenderer) -> str:
        return renderer.render(value.profiles)

    @register_text(ProfileListItem)
    def _(value: ProfileListItem, renderer: PlainTextRenderer) -> str:
        active = "*" if value.active else "-"
        return format_row(
            (
                ("active", active),
                ("name", value.name),
                ("env", value.environment),
                ("nip", value.nip),
                ("auth", value.auth),
            )
        )

    @register_text(ProfileSaved)
    def _(value: ProfileSaved, renderer: PlainTextRenderer) -> str:
        return format_fields(
            (
                ("name", value.name),
                ("active", value.active),
                ("environment", value.profile.environment.value),
                ("nip", value.profile.nip),
                ("auth", value.profile.auth.type.value),
            )
        )

    @register_text(ProfileSelected)
    def _(value: ProfileSelected, renderer: PlainTextRenderer) -> str:
        return format_fields(
            (
                ("name", value.name),
                ("environment", value.profile.environment.value),
                ("nip", value.profile.nip),
                ("auth", value.profile.auth.type.value),
            )
        )

    @register_text(ProfileCurrent)
    def _(value: ProfileCurrent, renderer: PlainTextRenderer) -> str:
        if value.name is None or value.profile is None:
            return "active_profile: none"
        return format_fields(
            (
                ("name", value.name),
                ("environment", value.profile.environment.value),
                ("nip", value.profile.nip),
                ("auth", value.profile.auth.type.value),
            )
        )

    @register_text(OnlineSessionOpened)
    def _(value: OnlineSessionOpened, renderer: PlainTextRenderer) -> str:
        return format_fields((("state_file", value.state_file), ("state", value.state)))

    @register_text(BatchSubmitted)
    def _(value: BatchSubmitted, renderer: PlainTextRenderer) -> str:
        return format_fields(
            (
                ("state_file", value.state_file),
                ("state", value.state),
                ("status", value.status),
            )
        )

    @register_text(OnlineSendResult)
    def _(value: OnlineSendResult, renderer: PlainTextRenderer) -> str:
        return renderer.render(value.results)

    @register_text(OnlineSendItem)
    def _(value: OnlineSendItem, renderer: PlainTextRenderer) -> str:
        return format_row((("file", value.file), ("result", value.result)))

    @register_text(InvoicesSendResult)
    def _(value: InvoicesSendResult, renderer: PlainTextRenderer) -> str:
        if value.mode == "batch" and value.batch is not None:
            return renderer.render(value.batch)
        return renderer.render(value.items)

    @register_text(InvoiceWorkflowItem)
    def _(value: InvoiceWorkflowItem, renderer: PlainTextRenderer) -> str:
        fields: list[tuple[str, object]] = []
        if value.status == "submitted":
            fields.append(("invoice_ref", value.invoice_reference))
        if value.status == "accepted":
            fields.append(("ksef", value.ksef_number))
        if value.invoice_reference and value.status != "submitted":
            fields.append(("invoice_ref", value.invoice_reference))
        fields.extend(
            (
                ("upo", value.upo_file),
                ("receipt", value.receipt_file),
                ("error", _quoted_error(value.error)),
            )
        )
        return format_status_line(value.status, value.file, fields)

    @register_text(InvoiceWorkflowBatch)
    def _(value: InvoiceWorkflowBatch, renderer: PlainTextRenderer) -> str:
        return format_status_line(
            value.status,
            "batch",
            (
                ("session", value.session_reference),
                ("invoices", value.invoice_count),
                ("successful", value.successful_invoice_count),
                ("failed", value.failed_invoice_count),
                ("upos", len(value.upo_files) if value.upo_files else None),
                ("receipt", value.receipt_file),
                ("error", _quoted_error(value.error)),
            ),
        )

    @register_text(InvoicesStatusResult)
    def _(value: InvoicesStatusResult, renderer: PlainTextRenderer) -> str:
        subject = value.file if value.mode == "online" and value.file else "batch"
        fields: list[tuple[str, object]] = [
            ("session", value.session_reference),
            ("invoice_ref", value.invoice_reference),
            ("ksef", value.ksef_number),
            ("invoices", value.invoice_count),
            ("successful", value.successful_invoice_count),
            ("failed", value.failed_invoice_count),
            ("receipt", value.receipt_file),
        ]
        return format_status_line(value.status, subject, fields)

    @register_text(InvoicesUpoResult)
    def _(value: InvoicesUpoResult, renderer: PlainTextRenderer) -> str:
        subject = value.file if value.mode == "online" and value.file else "batch"
        return "\n".join(
            format_status_line(
                "saved",
                subject,
                (
                    ("session", value.session_reference),
                    ("invoice_ref", value.invoice_reference),
                    ("ksef", value.ksef_number),
                    ("upo", upo.path),
                    ("bytes", upo.size),
                    ("receipt", value.receipt_file),
                ),
            )
            for upo in value.upo_files
        )

    @register_text(SavedFile)
    def _(value: SavedFile, renderer: PlainTextRenderer) -> str:
        return format_fields(
            (
                ("path", value.path),
                ("bytes", value.size),
            )
        )

    @register_text(TestSandboxReady)
    def _(value: TestSandboxReady, renderer: PlainTextRenderer) -> str:
        return format_fields(
            (
                ("nip", value.nip),
                ("subject_type", value.subject_type),
                ("token", value.token),
                ("reference_number", value.reference_number),
                ("token_permissions", value.token_permissions),
                ("sandbox_dir", value.sandbox_dir),
                ("cert_file", value.cert_file),
                ("key_file", value.key_file),
                ("env_file", value.env_file),
                ("source", value.source_command),
                ("send_with_token", value.token_send_command),
                ("send_with_certificate", value.certificate_send_command),
                ("cleanup", value.cleanup),
            )
        )

    @register_text(ExportHandleSaved)
    def _(value: ExportHandleSaved, renderer: PlainTextRenderer) -> str:
        return format_fields(
            (
                ("reference_number", value.reference_number),
                ("aes_key", value.aes_key),
                ("iv", value.iv),
                ("handle_file", value.handle_file),
            )
        )

    @register_text(ExportPaths)
    def _(value: ExportPaths, renderer: PlainTextRenderer) -> str:
        return "\n".join(str(path) for path in value.paths)


def _quoted_error(value: str | None) -> str | None:
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False)
