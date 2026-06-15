"""Plain text and JSON rendering for command results."""

from __future__ import annotations

import base64
import json
import sys
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, fields, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any, TypeVar

import typer
from pydantic import BaseModel, SecretBytes, SecretStr
from rich.console import Console

from ksef2_cli.config import OutputMode, Settings

console = Console(stderr=True, highlight=False)
T = TypeVar("T")


@dataclass(frozen=True)
class Collection:
    """Result whose text output should focus on a collection inside the payload."""

    payload: Any
    items: Iterable[Any]


def collection(payload: T, items: Iterable[Any]) -> Collection:
    """Keep full JSON payload while rendering only selected items as text."""

    return Collection(payload=payload, items=items)


def _settings(ctx: typer.Context) -> Settings:
    if not isinstance(ctx.obj, Settings):
        raise RuntimeError("CLI settings were not initialized.")
    return ctx.obj


def _to_jsonable(value: Any) -> Any:
    if isinstance(value, Collection):
        return _to_jsonable(value.payload)
    if isinstance(value, (SecretStr, SecretBytes)):
        return str(value)
    if isinstance(value, BaseModel):
        return {
            name: _to_jsonable(getattr(value, name))
            for name in value.__class__.model_fields
        }
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
    if isinstance(value, Mapping):
        return {str(key): _to_jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_to_jsonable(item) for item in value]
    return value


def render(ctx: typer.Context, value: Any) -> None:
    """Render a command result to stdout according to the selected output mode."""

    if _settings(ctx).output is OutputMode.json:
        sys.stdout.write(json.dumps(_to_jsonable(value), ensure_ascii=False, indent=2))
        sys.stdout.write("\n")
        return

    text = _plain_text(_text_value(value))
    if text:
        sys.stdout.write(text)
        sys.stdout.write("\n")


def _text_value(value: Any) -> Any:
    if isinstance(value, Collection):
        return value.items
    primary = _primary_collection(value)
    return value if primary is None else primary


def _primary_collection(value: Any) -> Any | None:
    if isinstance(value, Mapping):
        return None

    members = _field_items(value)
    if members is None:
        return None

    collections = [
        item
        for _name, item in members
        if isinstance(item, (list, tuple, set))
    ]
    if len(collections) == 1:
        return collections[0]
    return None


def _plain_text(value: Any) -> str:
    if value is None:
        return ""
    members = _field_items(value)
    if members is not None:
        return "\n".join(
            f"{key}: {_cell(item)}"
            for key, item in members
            if item is not None
        )
    if isinstance(value, (list, tuple, set)):
        return "\n".join(_row_text(item) for item in value if item is not None)
    return _cell(value)


def _row_text(value: Any) -> str:
    members = _field_items(value)
    if members is not None:
        return " ".join(
            f"{key}={_cell(item)}"
            for key, item in members
            if item is not None
        )
    return _cell(value)


def _cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, (SecretStr, SecretBytes)):
        return str(value)
    if isinstance(value, bytes):
        return base64.b64encode(value).decode("ascii")
    if isinstance(value, Enum):
        return value.name
    if isinstance(value, Path):
        return str(value)
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if _field_items(value) is not None or isinstance(value, (list, tuple, set)):
        return json.dumps(_to_jsonable(value), ensure_ascii=False, separators=(",", ":"))
    return str(value)


def _field_items(value: Any) -> list[tuple[str, Any]] | None:
    if isinstance(value, BaseModel):
        return [
            (name, getattr(value, name))
            for name in value.__class__.model_fields
        ]
    if is_dataclass(value) and not isinstance(value, type):
        return [(field.name, getattr(value, field.name)) for field in fields(value)]
    if isinstance(value, Mapping):
        return [(str(key), item) for key, item in value.items()]
    return None
