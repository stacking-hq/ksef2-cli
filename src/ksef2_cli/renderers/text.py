"""Plain-text rendering for CLI command results."""

import base64
import json
import os
import sys
from collections.abc import Mapping
from datetime import date, datetime
from enum import Enum
from functools import singledispatch
from pathlib import Path
from shutil import get_terminal_size
from typing import Callable, Iterable, TypeVar

from pydantic import BaseModel, SecretBytes, SecretStr
from rich.cells import cell_len

from ksef2_cli.renderers.json import json_renderer

# A terminal narrower than this would split output into one cell a line.
MINIMUM_WIDTH = 20
# Redirected output with no COLUMNS states no width, so fields keep the single line
# they have always had: a reader that wants a layout says so with COLUMNS.
UNBOUNDED_WIDTH = sys.maxsize
INDENT = "  "
# Two spaces separate fields on one status line, matching the pre-wrap layout.
SEPARATOR = "  "


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


def content_width() -> int:
    """Columns plain text should fit in, or ``UNBOUNDED_WIDTH`` when none is stated.

    A terminal decides for itself, and ``COLUMNS`` states the width of redirected
    output. Anything else knows nothing about the reader, so nothing is wrapped.
    """

    if sys.stdout.isatty():
        width = get_terminal_size((MINIMUM_WIDTH, 24)).columns
    else:
        declared = os.environ.get("COLUMNS", "").strip()
        if not declared.isdigit():
            return UNBOUNDED_WIDTH
        width = int(declared)
    return max(width, MINIMUM_WIDTH)


def format_fields(
    items: Iterable[tuple[str, object]], *, width: int | None = None
) -> str:
    """Render ``name: value`` lines, keeping every one of them inside the width.

    A value that no longer fits shares the line name and then continues below it,
    because a truncated reference or path is worse than an indented one.
    """

    limit = content_width() if width is None else width
    lines: list[str] = []
    for name, value in items:
        if value is None:
            continue
        cell = format_cell(value)
        if cell_len(f"{name}: {cell}") <= limit:
            lines.append(f"{name}: {cell}")
            continue
        lines.append(f"{name}:")
        lines.extend(break_long(cell, limit))
    return "\n".join(lines)


def format_row(items: Iterable[tuple[str, object]]) -> str:
    return " ".join(
        f"{name}={format_cell(value)}" for name, value in items if value is not None
    )


def format_status_line(
    status: str,
    subject: object,
    items: Iterable[tuple[str, object]],
    *,
    width: int | None = None,
) -> str:
    """Render one record as a status line, wrapped to the width instead of cut short."""

    limit = content_width() if width is None else width
    fields = [
        f"{name}={format_cell(value)}" for name, value in items if value is not None
    ]
    return "\n".join(_pack([status, format_cell(subject), *fields], limit))


def break_long(text: str, width: int) -> list[str]:
    """Break one over-long value into lines of ``width`` cells, each indented.

    Breaks land after a space, a separator or a path step, so compact JSON and file
    paths stay readable. Only the space that ends a line is dropped; every character
    of the value stays on the output.
    """

    limit = max(1, width - len(INDENT))
    lines: list[str] = []
    current = ""
    for atom in _atoms(text):
        if not current and not (atom := atom.lstrip()):
            continue  # Leading spaces would start a line with nothing on it.
        if current and cell_len(current) + cell_len(atom) > limit:
            lines.append(INDENT + current.rstrip())
            current = ""
        while cell_len(atom) > limit:
            head, atom = _cut(atom, limit)
            lines.append(INDENT + head.rstrip())
        current += atom
    if current or not lines:
        lines.append(INDENT + current.rstrip())
    return lines


def _pack(parts: Iterable[str], width: int) -> list[str]:
    """Put whole fields on as few lines as the width allows."""

    lines: list[str] = []
    current = ""
    for part in parts:
        if not part:
            continue
        if cell_len(INDENT + part) > width:
            # The field owns a line of its own, so its pieces can use the full width.
            if current:
                lines.append(current)
                current = ""
            lines.extend(break_long(part, width))
            continue
        candidate = f"{current}{SEPARATOR}{part}" if current else part
        if current and cell_len(candidate) > width:
            lines.append(current)
            current = INDENT + part
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines or [""]


def _atoms(text: str) -> list[str]:
    """Split a value after every space, separator and path step, keeping each one."""

    atoms: list[str] = []
    current = ""
    for char in text:
        current += char
        if char.isspace() or char in ",;/":
            atoms.append(current)
            current = ""
    if current:
        atoms.append(current)
    return atoms


def _cut(text: str, width: int) -> tuple[str, str]:
    """Split off the leading cells that fit, so no line can overflow."""

    head = ""
    for index, char in enumerate(text):
        if head and cell_len(head + char) > width:
            return text[:index], text[index:]
        head += char
    return text, ""


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
