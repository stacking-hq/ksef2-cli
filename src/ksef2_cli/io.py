"""File helpers used by command modules."""

import json
import sys
from pathlib import Path
from typing import TypeVar

from ksef2.domain.models.batch import BatchSessionResumeState
from ksef2.domain.models.session import OnlineSessionResumeState
from pydantic import BaseModel

ModelT = TypeVar("ModelT", bound=BaseModel)
ResumeStateT = TypeVar(
    "ResumeStateT", OnlineSessionResumeState, BatchSessionResumeState
)
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


def read_resume_state_file(path: Path, model_type: type[ResumeStateT]) -> ResumeStateT:
    """Read an SDK session resume-state file written by ``write_resume_state_file``."""

    return model_type.from_dict(json.loads(path.read_text(encoding="utf-8")))


def write_resume_state_file(path: Path, state: ResumeStateT) -> Path:
    """Write SDK session resume state with its credentials readable again later.

    ``model_dump_json`` renders the AES key and IV as ``**********`` because they are
    ``SecretStr``, which silently corrupts a file that exists to be resumed from. The
    SDK's ``to_json`` is the opt-in export that says the payload holds key material, so
    the file is written 0600 like every other credential this CLI owns.
    """

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(state.to_json(indent=2) + "\n", encoding="utf-8")
    path.chmod(SECRET_MODEL_FILE_MODE)
    return path


def write_bytes_file(path: Path, content: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path
