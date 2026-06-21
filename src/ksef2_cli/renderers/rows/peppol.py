"""Plain-text handlers for PEPPOL provider responses."""

from ksef2.domain.models.peppol import ListPeppolProvidersResponse, PeppolProvider

from ksef2_cli.renderers.text import PlainTextRenderer, format_row, register_text


def register() -> None:
    @register_text(ListPeppolProvidersResponse)
    def _(value: ListPeppolProvidersResponse, renderer: PlainTextRenderer) -> str:
        return renderer.render(value.providers)

    @register_text(PeppolProvider)
    def _(value: PeppolProvider, renderer: PlainTextRenderer) -> str:
        return format_row(
            (
                ("id", value.id),
                ("name", value.name),
                ("date_created", value.date_created),
            )
        )
