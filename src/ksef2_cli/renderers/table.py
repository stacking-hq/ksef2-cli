"""Plain aligned tables with explicit, reusable column policies."""

import re
import sys
import unicodedata
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from shutil import get_terminal_size

from rich.cells import cell_len

from ksef2_cli.renderers.text import format_cell

_ANSI = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)")


def clean(value: object) -> str:
    """Keep each cell on one terminal line, including untrusted SDK text."""
    text = _ANSI.sub("", format_cell(value))
    return "".join(
        " " if unicodedata.category(char).startswith("C") or char.isspace() else char
        for char in text
    )


def utc_datetime(value: datetime | None) -> str:
    if value is None:
        return ""
    # SDK auth models also accept naive datetimes; interpret those as API UTC.
    return (
        value.replace(tzinfo=value.tzinfo or UTC)
        .astimezone(UTC)
        .strftime("%Y-%m-%d %H:%M:%S")
    )


def calendar_date(value: date | None) -> str:
    return "" if value is None else value.strftime("%Y-%m-%d")


def amount(value: float, currency: object) -> str:
    return f"{Decimal(str(value)):.2f} {format_cell(currency)}"


@dataclass(frozen=True)
class Column[T]:
    header: str
    value: Callable[[T], object]
    # A missing maximum protects identifiers and short facts from truncation.
    maximum: int | None = None
    minimum: int = 8
    shrink_priority: int = 0
    drop_priority: int = 0
    right: bool = False


def _clip(text: str, width: int) -> str:
    if cell_len(text) <= width:
        return text
    prefix = ""
    for char in text:
        if cell_len(prefix + char) > width - 1:
            break
        prefix += char
    return prefix + "…"


def render_table[T](
    rows: Sequence[T], columns: Sequence[Column[T]], *, width: int | None = None
) -> str:
    if not rows:
        return "No results."
    if width is None:
        width = get_terminal_size((120, 24)).columns if sys.stdout.isatty() else 120
    cells = [[clean(column.value(row)) for column in columns] for row in rows]
    active = list(range(len(columns)))
    widths = [
        max(
            cell_len(column.header),
            min(
                max(cell_len(row[index]) for row in cells),
                column.maximum if column.maximum is not None else sys.maxsize,
            ),
        )
        for index, column in enumerate(columns)
    ]

    preferred_widths = widths.copy()

    def total() -> int:
        return sum(widths[index] for index in active) + 2 * (len(active) - 1)

    # Free text shrinks before optional columns disappear. Facts and IDs overflow.
    for index in sorted(active, key=lambda i: columns[i].shrink_priority, reverse=True):
        column = columns[index]
        if column.maximum is not None:
            minimum = min(widths[index], max(cell_len(column.header), column.minimum))
            widths[index] = max(minimum, widths[index] - max(0, total() - width))
    for index in sorted(active, key=lambda i: columns[i].drop_priority, reverse=True):
        if total() <= width:
            break
        if columns[index].drop_priority:
            active.remove(index)

    for index in sorted(active, key=lambda i: columns[i].shrink_priority):
        widths[index] += min(
            preferred_widths[index] - widths[index], max(0, width - total())
        )

    def line(values: Sequence[str]) -> str:
        parts = []
        for index in active:
            text = _clip(values[index], widths[index])
            padding = " " * (widths[index] - cell_len(text))
            parts.append(padding + text if columns[index].right else text + padding)
        return "  ".join(parts).rstrip()

    return "\n".join([line([c.header for c in columns]), *(line(row) for row in cells)])
