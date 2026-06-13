"""JSON input and output file helpers used by command modules."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel

from ksef2_cli.rendering import _to_jsonable

T = TypeVar("T")


def _read_json(path: Path) -> Any:
    if str(path) == "-":
        return json.load(sys.stdin)
    return json.loads(path.read_text(encoding="utf-8"))


def _read_model(path: Path, model_type: type[T]) -> T:
    data = _read_json(path)
    if issubclass(model_type, BaseModel):
        return model_type.model_validate(data)  # type: ignore[return-value]
    return data


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_to_jsonable(value), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
