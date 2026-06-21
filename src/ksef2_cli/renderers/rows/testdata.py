"""Plain-text handlers for TEST data command results."""

from ksef2.domain.models.testdata import Permission

from ksef2_cli.renderers.text import (
    PlainTextRenderer,
    format_fields,
    format_row,
    register_text,
)
from ksef2_cli.results import (
    TestAttachmentsEnabled,
    TestAttachmentsRevoked,
    TestContextAccessChanged,
    TestPermissionsGranted,
    TestPermissionsRevoked,
    TestPersonCreated,
    TestPersonDeleted,
    TestSubjectCreated,
    TestSubjectDeleted,
)


def register() -> None:
    @register_text(TestSubjectCreated)
    def _(value: TestSubjectCreated, renderer: PlainTextRenderer) -> str:
        return format_fields((("nip", value.nip), ("created", value.created)))

    @register_text(TestSubjectDeleted)
    def _(value: TestSubjectDeleted, renderer: PlainTextRenderer) -> str:
        return format_fields((("nip", value.nip), ("deleted", value.deleted)))

    @register_text(TestPersonCreated)
    def _(value: TestPersonCreated, renderer: PlainTextRenderer) -> str:
        return format_fields(
            (("nip", value.nip), ("pesel", value.pesel), ("created", value.created))
        )

    @register_text(TestPersonDeleted)
    def _(value: TestPersonDeleted, renderer: PlainTextRenderer) -> str:
        return format_fields((("nip", value.nip), ("deleted", value.deleted)))

    @register_text(TestAttachmentsEnabled)
    def _(value: TestAttachmentsEnabled, renderer: PlainTextRenderer) -> str:
        return format_fields((("nip", value.nip), ("attachments", value.attachments)))

    @register_text(TestAttachmentsRevoked)
    def _(value: TestAttachmentsRevoked, renderer: PlainTextRenderer) -> str:
        return format_fields(
            (
                ("nip", value.nip),
                ("expected_end_date", value.expected_end_date),
                ("attachments", value.attachments),
            )
        )

    @register_text(TestContextAccessChanged)
    def _(value: TestContextAccessChanged, renderer: PlainTextRenderer) -> str:
        return format_fields(
            (
                ("context_type", value.context_type),
                ("context_value", value.context_value),
                ("blocked", value.blocked),
            )
        )

    @register_text(TestPermissionsGranted)
    def _(value: TestPermissionsGranted, renderer: PlainTextRenderer) -> str:
        return renderer.render(value.permissions)

    @register_text(Permission)
    def _(value: Permission, renderer: PlainTextRenderer) -> str:
        return format_row((("type", value.type), ("description", value.description)))

    @register_text(TestPermissionsRevoked)
    def _(value: TestPermissionsRevoked, renderer: PlainTextRenderer) -> str:
        return format_fields(
            (
                ("revoke_from", value.revoke_from),
                ("in_context_of", value.in_context_of),
                ("revoked", value.revoked),
            )
        )
