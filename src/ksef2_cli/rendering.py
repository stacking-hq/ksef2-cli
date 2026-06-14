"""Plain text and JSON rendering for command results."""

from __future__ import annotations

import base64
import json
import sys
from dataclasses import fields, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any

import typer
from pydantic import BaseModel
from rich.console import Console

from ksef2_cli.config import OutputMode, Settings

console = Console(stderr=True, highlight=False)


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
    items_key: str | None = None,
) -> None:
    data = _to_jsonable(value)
    if _settings(ctx).output is OutputMode.json:
        sys.stdout.write(json.dumps(data, ensure_ascii=False, indent=2))
        sys.stdout.write("\n")
        return

    if items_key and isinstance(data, dict):
        data = data.get(items_key, data)

    text = _plain_text(data)
    if text:
        sys.stdout.write(text)
        sys.stdout.write("\n")


def _plain_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, dict):
        return "\n".join(
            f"{key}: {_cell(item)}"
            for key, item in value.items()
            if item is not None
        )
    if isinstance(value, list):
        return "\n".join(_row_text(item) for item in value if item is not None)
    return _cell(value)


def _row_text(value: Any) -> str:
    if isinstance(value, dict):
        return " ".join(
            f"{key}={_cell(item)}"
            for key, item in value.items()
            if item is not None
        )
    return _cell(value)


def _cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return str(value)
