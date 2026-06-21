"""Plain-text rendering for CLI command results."""

import base64
import json
from collections.abc import Mapping
from datetime import date, datetime
from enum import Enum
from functools import singledispatch
from pathlib import Path
from typing import Callable, Iterable, TypeVar

from pydantic import BaseModel, SecretBytes, SecretStr

from ksef2_cli.renderers.json import json_renderer


RenderValueT = TypeVar("RenderValueT")


type RenderHandler[RenderValueT] = Callable[[RenderValueT, "PlainTextRenderer"], str]
type RenderDecorator[RenderValueT] = Callable[
    [RenderHandler[RenderValueT]], RenderHandler[RenderValueT]
]


class PlainTextRenderer:
    """Render typed command results as human-readable text."""

    def render(self, value: object) -> str:
        return _to_text(value, self)


@singledispatch
def _to_text(value: object, renderer: PlainTextRenderer) -> str:
    raise TypeError(f"No plain-text renderer registered for {type(value).__name__}.")


def register_text(value_type: type[RenderValueT]) -> RenderDecorator[RenderValueT]:
    return _to_text.register(value_type)


@register_text(type(None))
def _(value: None, renderer: PlainTextRenderer) -> str:
    return ""


@register_text(str)
def _(value: str, renderer: PlainTextRenderer) -> str:
    return value


@register_text(list)
def _(value: list[object], renderer: PlainTextRenderer) -> str:
    results: list[str] = []
    for item in value:
        if item is None:
            continue
        if isinstance(item, Mapping):
            text = format_row(item.items())
        else:
            text = renderer.render(item)
        if text:
            results.append(text)
    return "\n".join(results)


@register_text(tuple)
def _(value: tuple, renderer: PlainTextRenderer) -> str:
    return renderer.render(list(value))


@register_text(set)
def _(value: set, renderer: PlainTextRenderer) -> str:
    return renderer.render(list(value))


@register_text(Mapping)
def _(value: Mapping, renderer: PlainTextRenderer) -> str:
    return format_fields(value.items())


def format_fields(items: Iterable[tuple[str, object]]) -> str:
    return "\n".join(
        f"{name}: {format_cell(value)}" for name, value in items if value is not None
    )


def format_row(items: Iterable[tuple[str, object]]) -> str:
    return " ".join(
        f"{name}={format_cell(value)}" for name, value in items if value is not None
    )


def format_status_line(
    status: str, subject: object, items: Iterable[tuple[str, object]]
) -> str:
    fields = [
        f"{name}={format_cell(value)}" for name, value in items if value is not None
    ]
    return "  ".join((status, format_cell(subject), *fields))


def format_cell(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, (SecretStr, SecretBytes)):
        return str(value)
    if isinstance(value, bytes):
        return base64.b64encode(value).decode("ascii")
    if isinstance(value, Enum):
        return str(value.value)
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (date, datetime)):
        return str(value.isoformat())
    if isinstance(value, (list, tuple, set)):
        return ", ".join(format_cell(item) for item in value)
    if isinstance(value, Mapping):
        return json.dumps(
            json_renderer.to_jsonable(value), ensure_ascii=False, separators=(",", ":")
        )
    if isinstance(value, BaseModel):
        return json.dumps(
            value.model_dump(mode="json", by_alias=True),
            ensure_ascii=False,
            separators=(",", ":"),
        )
    return str(value)


plain_renderer = PlainTextRenderer()
