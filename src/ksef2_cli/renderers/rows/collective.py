"""Plain-text handlers for collective identifier responses."""

from ksef2.models import (
    CollectiveIdentifierInvoiceDetails,
    CollectiveIdentifierReference,
    CollectiveIdentifierSummary,
    GenerateCollectiveIdentifierResponse,
)

from ksef2_cli.renderers.text import (
    PlainTextRenderer,
    format_fields,
    format_row,
    register_text,
)


def register() -> None:
    @register_text(GenerateCollectiveIdentifierResponse)
    def _(
        value: GenerateCollectiveIdentifierResponse, renderer: PlainTextRenderer
    ) -> str:
        return format_fields(
            (("collective_identifier_number", value.collective_identifier_number),)
        )

    @register_text(CollectiveIdentifierSummary)
    def _(value: CollectiveIdentifierSummary, renderer: PlainTextRenderer) -> str:
        return format_row(
            (
                ("identifier", value.collective_identifier_number),
                ("created", value.date_created),
                ("invoices", value.invoice_count),
                ("current_context", value.created_in_current_context),
            )
        )

    @register_text(CollectiveIdentifierReference)
    def _(value: CollectiveIdentifierReference, renderer: PlainTextRenderer) -> str:
        return format_row(
            (
                ("identifier", value.collective_identifier_number),
                ("created", value.date_created),
                ("current_context", value.created_in_current_context),
            )
        )

    @register_text(CollectiveIdentifierInvoiceDetails)
    def _(
        value: CollectiveIdentifierInvoiceDetails, renderer: PlainTextRenderer
    ) -> str:
        return format_row(
            (
                ("ksef_number", value.ksef_number),
                ("payment", value.payment),
                ("description", value.description),
                ("hidden", value.details_hidden),
            )
        )
