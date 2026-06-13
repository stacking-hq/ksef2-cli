"""Rich table and JSON rendering for command results."""

from __future__ import annotations

import base64
import json
from dataclasses import fields, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any

import typer
from pydantic import BaseModel
from rich.console import Console
from rich.table import Table

from ksef2_cli.config import OutputMode, Settings

console = Console()


def _settings(ctx: typer.Context) -> Settings:
    if not isinstance(ctx.obj, Settings):
        raise RuntimeError("CLI settings were not initialized.")
    return ctx.obj


def _to_jsonable(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return _to_jsonable(value.model_dump(mode="python", exclude_none=False))
    if is_dataclass(value) and not isinstance(value, type):
        return {field.name: _to_jsonable(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, bytes):
        return base64.b64encode(value).decode("ascii")
    if isinstance(value, Enum):
        return value.name
    if isinstance(value, Path):
        return str(value)
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _to_jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_to_jsonable(item) for item in value]
    return value


def _render(
    ctx: typer.Context,
    value: Any,
    *,
    title: str | None = None,
    items_key: str | None = None,
    fields: list[str] | None = None,
) -> None:
    data = _to_jsonable(value)
    if _settings(ctx).output is OutputMode.json:
        console.print_json(json.dumps(data, ensure_ascii=False))
        return

    table_data = data
    if items_key and isinstance(data, dict):
        table_data = data.get(items_key, data)

    if isinstance(table_data, list):
        _render_list(table_data, title=title, preferred_fields=fields)
    elif isinstance(table_data, dict):
        list_key = _first_list_key(table_data)
        if list_key:
            _render_list(table_data[list_key], title=title or list_key.replace("_", " ").title(), preferred_fields=fields)
            rest = {key: value for key, value in table_data.items() if key != list_key}
            if rest:
                _render_mapping(rest, title="Metadata")
        else:
            _render_mapping(table_data, title=title)
    else:
        console.print(table_data)


def _first_list_key(data: dict[str, Any]) -> str | None:
    for key, value in data.items():
        if isinstance(value, list):
            return key
    return None


def _render_list(
    rows: list[Any],
    *,
    title: str | None,
    preferred_fields: list[str] | None,
) -> None:
    if not rows:
        console.print("[dim]No results.[/]")
        return

    normalized_rows = [row if isinstance(row, dict) else {"value": row} for row in rows]
    keys = _table_keys(normalized_rows, preferred_fields)
    table = Table(title=title)
    for key in keys:
        table.add_column(key.replace("_", " ").title(), overflow="fold")
    for row in normalized_rows:
        table.add_row(*[_cell(row.get(key)) for key in keys])
    console.print(table)


def _table_keys(rows: list[dict[str, Any]], preferred_fields: list[str] | None) -> list[str]:
    available = list(rows[0].keys())
    if preferred_fields:
        selected = [key for key in preferred_fields if key in rows[0]]
        if selected:
            return selected
    return available[:8]


def _render_mapping(data: dict[str, Any], *, title: str | None) -> None:
    table = Table(title=title, show_header=False)
    table.add_column("Key", style="bold")
    table.add_column("Value", overflow="fold")
    for key, value in data.items():
        table.add_row(key.replace("_", " ").title(), _cell(value))
    console.print(table)


def _cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)
