import json

import pytest
from pydantic import BaseModel

from ksef2_cli.io import (
    SECRET_MODEL_FILE_MODE,
    read_model_file,
    write_bytes_file,
    write_model_file,
)
from ksef2_cli.parsing import parse_optional_bool


class DemoModel(BaseModel):
    name: str


def test_optional_bool_parser_accepts_common_values() -> None:
    assert parse_optional_bool(None, option_name="--x") is None
    assert parse_optional_bool("yes", option_name="--x") is True
    assert parse_optional_bool("false", option_name="--x") is False
    assert parse_optional_bool("on", option_name="--x") is True
    assert parse_optional_bool("0", option_name="--x") is False


def test_optional_bool_parser_rejects_unknown_value() -> None:
    with pytest.raises(ValueError, match="--x must be yes or no"):
        parse_optional_bool("maybe", option_name="--x")


def test_model_file_helpers_read_and_write_json(tmp_path) -> None:
    path = tmp_path / "payload.json"
    path.write_text('{"name": "demo"}', encoding="utf-8")

    assert read_model_file(path, DemoModel) == DemoModel(name="demo")

    target = tmp_path / "nested" / "out.json"
    assert write_model_file(target, DemoModel(name="written")) == target
    data = json.loads(target.read_text(encoding="utf-8"))
    assert data == {"name": "written"}

    secret_target = tmp_path / "nested" / "secret.json"
    assert (
        write_model_file(
            secret_target,
            DemoModel(name="secret"),
            file_mode=SECRET_MODEL_FILE_MODE,
        )
        == secret_target
    )
    assert secret_target.stat().st_mode & 0o777 == SECRET_MODEL_FILE_MODE

    binary_target = tmp_path / "nested" / "file.bin"
    assert write_bytes_file(binary_target, b"abc") == binary_target
    assert binary_target.read_bytes() == b"abc"
