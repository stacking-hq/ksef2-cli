"""File helpers used by command modules."""

import sys
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel

ModelT = TypeVar("ModelT", bound=BaseModel)
SECRET_MODEL_FILE_MODE = 0o600


def read_model_file(path: Path, model_type: type[ModelT]) -> ModelT:
    if str(path) == "-":
        return model_type.model_validate_json(sys.stdin.read())
    return model_type.model_validate_json(path.read_text(encoding="utf-8"))


def write_model_file(
    path: Path, value: BaseModel, *, file_mode: int | None = None
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        value.model_dump_json(indent=2, by_alias=True, exclude_none=True) + "\n",
        encoding="utf-8",
    )
    if file_mode is not None:
        path.chmod(file_mode)
    return path


def write_bytes_file(path: Path, content: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path
