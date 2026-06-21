"""Plain-text fallback for SDK-owned response models."""

from ksef2.domain.models.base import KSeFBaseModel

from ksef2_cli.renderers.text import PlainTextRenderer, format_fields, register_text


def register() -> None:
    @register_text(KSeFBaseModel)
    def _(value: KSeFBaseModel, renderer: PlainTextRenderer) -> str:
        return format_fields(value.model_dump(mode="json", by_alias=True).items())
