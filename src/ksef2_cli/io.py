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


def write_text_file(path: Path, content: str, *, file_mode: int | None = None) -> Path:
    """Write text the caller already serialized, optionally tightening file mode.

    SDK session resume state masks its AES key and IV in ``model_dump_json``, so state
    files go through this helper with the model's own credential export instead.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content + "\n", encoding="utf-8")
    if file_mode is not None:
        path.chmod(file_mode)
    return path


def write_bytes_file(
    path: Path, content: bytes, *, file_mode: int | None = None
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    if file_mode is not None:
        path.chmod(file_mode)
    return path


def validate_invoice_xml(content: bytes, *, source: object) -> bytes:
    """Reject unsupported encodings without changing potentially signed bytes."""
    if not content.strip():
        raise ValueError(f"Invoice XML from {source} is empty.")
    for marker, encoding in (
        (b"\xef\xbb\xbf", "UTF-8 BOM"),
        (b"\xff\xfe", "UTF-16 LE BOM"),
        (b"\xfe\xff", "UTF-16 BE BOM"),
    ):
        if content.startswith(marker):
            raise ValueError(
                f"Invoice XML from {source} uses {encoding}. Provide UTF-8 XML without "
                "a BOM. Re-export from the source system before signing; changing "
                "signed XML can invalidate its signature. No bytes were changed."
            )
    try:
        content.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ValueError(
            f"Invoice XML from {source} must be UTF-8. Re-export it as UTF-8 before signing."
        ) from error
    return content


def read_invoice_xml(path: Path) -> bytes:
    return validate_invoice_xml(path.read_bytes(), source=path)


def read_stdin_invoice_xml() -> bytes:
    """Read one invoice from stdin, preserving the original bytes in memory."""
    return validate_invoice_xml(sys.stdin.buffer.read(), source="stdin.xml")
