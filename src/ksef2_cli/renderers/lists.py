"""Command-scoped table specifications; SDK objects and JSON stay untouched."""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol, cast
from datetime import datetime
from shlex import quote

from ksef2.models import (
    AuthenticationSession,
    AuthorizationGrantDetail,
    CertificateInfo,
    CollectiveIdentifierInvoiceDetails,
    CollectiveIdentifierReference,
    CollectiveIdentifierSummary,
    EntityPermissionDetail,
    EntityRole,
    EuEntityPermission,
    InvoiceMetadata,
    PeppolProvider,
    PersonalPermissionDetail,
    PersonPermissionDetail,
    PublicKeyCertificate,
    QueryInvoicesMetadataResponse,
    SessionInvoiceStatusResponse,
    SessionInvoicesResponse,
    SessionSummary,
    SubordinateEntityRoleDetail,
    SubunitPermission,
)
from ksef2.models import TokenInfo

from ksef2_cli.results import InvoiceMetadataAllResult, ProfileListItem, ProfileListResult
from ksef2_cli.renderers.table import (
    Column as C,
    amount,
    calendar_date,
    clean,
    render_table,
    utc_datetime,
)


def _processing_status(code: int, description: str) -> str:
    # Only auth/session processing domains use this mapping, never token/cert states.
    if code == 100:
        return "in progress"
    if code == 200:
        return "ok"
    if 400 <= code < 600:
        return f"failed: {description}"
    return f"{code}: {description}"


@dataclass(frozen=True)
class ListSpec[T]:
    item_type: type[T]
    columns: tuple[C[T], ...]

    def render(self, rows: Sequence[object], width: int | None) -> str:
        return render_table(cast(Sequence[T], rows), self.columns, width=width)


AUTH = ListSpec(
    AuthenticationSession,
    (
        C("REFERENCE", lambda r: r.reference_number),
        C("STARTED (UTC)", lambda r: utc_datetime(r.start_date)),
        C(
            "METHOD",
            lambda r: r.authentication_method_display_name,
            maximum=26,
            shrink_priority=2,
        ),
        C(
            "STATUS",
            lambda r: _processing_status(r.status_code, r.status_description),
            maximum=48,
            minimum=20,
        ),
        C("CURRENT", lambda r: r.is_current),
    ),
)
SESSIONS = ListSpec(
    SessionSummary,
    (
        C("REFERENCE", lambda r: r.reference_number),
        C("CREATED (UTC)", lambda r: utc_datetime(r.date_created)),
        C(
            "STATUS",
            lambda r: _processing_status(r.status.code, r.status.description),
            maximum=48,
            minimum=20,
        ),
        C("TOTAL", lambda r: r.total_invoice_count, right=True),
        C("OK", lambda r: r.successful_invoice_count, right=True),
        C("FAILED", lambda r: r.failed_invoice_count, right=True),
    ),
)
SESSION_INVOICES = ListSpec(
    SessionInvoiceStatusResponse,
    (
        C("REFERENCE", lambda r: r.reference_number),
        C("KSEF NUMBER", lambda r: r.ksef_number),
        C(
            "INVOICE NO",
            lambda r: r.invoice_number,
            maximum=24,
            shrink_priority=2,
            drop_priority=1,
        ),
        C(
            "STATUS",
            lambda r: _processing_status(r.status.code, r.status.description),
            maximum=48,
            minimum=20,
        ),
        C("INVOICED (UTC)", lambda r: utc_datetime(r.invoicing_date), drop_priority=2),
    ),
)
METADATA = ListSpec(
    InvoiceMetadata,
    (
        C("KSEF NUMBER", lambda r: r.ksef_number),
        C("INVOICE NO", lambda r: r.invoice_number, maximum=26, shrink_priority=1),
        C("ISSUED", lambda r: calendar_date(r.issue_date)),
        C(
            "SELLER",
            lambda r: r.seller.name or r.seller.nip,
            maximum=30,
            shrink_priority=3,
            drop_priority=2,
        ),
        C(
            "BUYER",
            lambda r: r.buyer.name or r.buyer.identifier.value,
            maximum=30,
            shrink_priority=3,
            drop_priority=1,
        ),
        C("GROSS", lambda r: amount(r.gross_amount, r.currency), right=True),
        C("TYPE", lambda r: r.invoice_type),
    ),
)
TOKENS = ListSpec(
    TokenInfo,
    (
        C("REFERENCE", lambda r: r.reference_number),
        C("STATUS", lambda r: r.status),
        C(
            "DESCRIPTION",
            lambda r: r.description,
            maximum=36,
            shrink_priority=3,
            drop_priority=2,
        ),
        C(
            "PERMISSIONS",
            lambda r: r.requested_permissions,
            maximum=40,
            shrink_priority=2,
            drop_priority=1,
        ),
        C("CREATED (UTC)", lambda r: utc_datetime(r.date_created)),
    ),
)
CERTIFICATES = ListSpec(
    CertificateInfo,
    (
        C("SERIAL", lambda r: r.serial_number),
        C("NAME", lambda r: r.name, maximum=30, shrink_priority=2, drop_priority=1),
        C("TYPE", lambda r: r.type),
        C("STATUS", lambda r: r.status),
        C("VALID FROM", lambda r: calendar_date(r.valid_from)),
        C("VALID TO", lambda r: calendar_date(r.valid_to)),
    ),
)
COLLECTIVE = ListSpec(
    CollectiveIdentifierSummary,
    (
        C("IDENTIFIER", lambda r: r.collective_identifier_number),
        C("CREATED (UTC)", lambda r: utc_datetime(r.date_created)),
        C("INVOICES", lambda r: r.invoice_count, right=True),
        C("CURRENT CONTEXT", lambda r: r.created_in_current_context),
    ),
)
REFERENCES = ListSpec(
    CollectiveIdentifierReference,
    (
        C("IDENTIFIER", lambda r: r.collective_identifier_number),
        C("CREATED (UTC)", lambda r: utc_datetime(r.date_created)),
        C("CURRENT CONTEXT", lambda r: r.created_in_current_context),
    ),
)
COLLECTIVE_INVOICES = ListSpec(
    CollectiveIdentifierInvoiceDetails,
    (
        C("KSEF NUMBER", lambda r: r.ksef_number),
        C(
            "PAYMENT",
            lambda r: amount(r.payment.amount, r.payment.currency)
            if r.payment
            else None,
            right=True,
        ),
        C("DESCRIPTION", lambda r: r.description, maximum=48, shrink_priority=2),
        C("HIDDEN", lambda r: r.details_hidden),
    ),
)
PROFILES = ListSpec(
    ProfileListItem,
    (
        C("NAME", lambda r: r.name),
        C("ACTIVE", lambda r: r.active),
        C("ENVIRONMENT", lambda r: r.environment),
        C("NIP", lambda r: r.nip),
        C("AUTH", lambda r: r.auth),
    ),
)
PROVIDERS = ListSpec(
    PeppolProvider,
    (
        C("ID", lambda r: r.id),
        C("NAME", lambda r: r.name, maximum=48, shrink_priority=2),
        C("CREATED (UTC)", lambda r: utc_datetime(r.date_created)),
    ),
)
ENCRYPTION = ListSpec(
    PublicKeyCertificate,
    (
        C("CERTIFICATE ID", lambda r: r.certificate_id),
        C("PUBLIC KEY ID", lambda r: r.public_key_id),
        C("USAGE", lambda r: r.usage),
        C("VALID FROM", lambda r: calendar_date(r.valid_from)),
        C("VALID TO", lambda r: calendar_date(r.valid_to)),
    ),
)


class PermissionRow(Protocol):
    @property
    def description(self) -> str: ...

    @property
    def start_date(self) -> datetime: ...


def _permission_spec[T: PermissionRow](model: type[T], *columns: C[T]) -> ListSpec[T]:
    return ListSpec(
        model,
        (
            *columns,
            C(
                "DESCRIPTION",
                lambda r: r.description,
                maximum=40,
                shrink_priority=3,
                drop_priority=1,
            ),
            C("STARTED (UTC)", lambda r: utc_datetime(r.start_date)),
        ),
    )


ROLES = _permission_spec(
    EntityRole,
    C("ROLE", lambda r: r.role),
    C("PARENT", lambda r: r.parent_entity_id_value),
)
PERMISSIONS = {
    "entities": _permission_spec(
        EntityPermissionDetail,
        C("ID", lambda r: r.id),
        C("CONTEXT", lambda r: r.context_value),
        C("PERMISSION", lambda r: r.permission_type),
        C("DELEGATE", lambda r: r.can_delegate),
    ),
    "persons": _permission_spec(
        PersonPermissionDetail,
        C("ID", lambda r: r.id),
        C("AUTHORIZED", lambda r: r.authorized_value),
        C("PERMISSION", lambda r: r.permission_type),
        C("STATE", lambda r: r.permission_state),
    ),
    "authorizations": _permission_spec(
        AuthorizationGrantDetail,
        C("ID", lambda r: r.id),
        C("AUTHORIZED", lambda r: r.authorized_entity_value),
        C("AUTHORIZING", lambda r: r.authorizing_entity_value),
        C("SCOPE", lambda r: r.authorization_scope),
    ),
    "personal": _permission_spec(
        PersonalPermissionDetail,
        C("ID", lambda r: r.id),
        C("CONTEXT", lambda r: r.context_value),
        C("PERMISSION", lambda r: r.permission_type),
        C("STATE", lambda r: r.permission_state),
    ),
    "eu-entities": _permission_spec(
        EuEntityPermission,
        C("ID", lambda r: r.id),
        C("VAT UE", lambda r: r.vat_ue_identifier),
        C("PERMISSION", lambda r: r.permission_type),
    ),
    "subordinate-entities": _permission_spec(
        SubordinateEntityRoleDetail,
        C("ENTITY", lambda r: r.subordinate_entity_value),
        C("ROLE", lambda r: r.role),
    ),
    "subunits": _permission_spec(
        SubunitPermission,
        C("ID", lambda r: r.id),
        C("AUTHORIZED", lambda r: r.authorized_value),
        C("SUBUNIT", lambda r: r.subunit_value),
        C("PERMISSION", lambda r: r.permission_type),
    ),
}

LIST_COMMANDS = {
    "sessions auth-list": AUTH,
    "sessions invoice-list": SESSIONS,
    "online list": SESSION_INVOICES,
    "batch list": SESSION_INVOICES,
    "invoices metadata": METADATA,
    "tokens list": TOKENS,
    "certificates list": CERTIFICATES,
    "collective list": COLLECTIVE,
    "collective list-for-invoice": REFERENCES,
    "collective list-invoices": COLLECTIVE_INVOICES,
    "profile list": PROFILES,
    "peppol providers": PROVIDERS,
    "encryption certificates": ENCRYPTION,
    "permissions entity-roles": ROLES,
}


def render_list(
    command: str, result: object, *, kind: str = "", width: int | None = None
) -> str | None:
    spec = (
        PERMISSIONS.get(kind)
        if command == "permissions query"
        else LIST_COMMANDS.get(command)
    )
    if spec is None:
        return None
    footer = []
    if isinstance(result, QueryInvoicesMetadataResponse):
        rows = result.invoices
        footer.extend(
            (
                f"More results: {clean(result.has_more)}",
                f"Truncated: {clean(result.is_truncated)}",
            )
        )
        if result.has_more:
            footer.append("Fetch all pages with --all.")
        if result.permanent_storage_hwm_date is not None:
            footer.append(
                "Permanent storage HWM (UTC): "
                + utc_datetime(result.permanent_storage_hwm_date)
            )
    elif isinstance(result, InvoiceMetadataAllResult):
        rows = result.invoices
    elif isinstance(result, SessionInvoicesResponse):
        rows = result.invoices
        if result.continuation_token is not None:
            footer.append(
                "Next page: --continuation-token "
                + quote(clean(result.continuation_token))
            )
    elif isinstance(result, ProfileListResult):
        rows = result.profiles
    else:
        rows = cast(Sequence[object], result)
    return "\n".join([spec.render(rows, width), *footer])
