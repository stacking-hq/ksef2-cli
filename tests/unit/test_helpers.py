from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from datetime import date
from enum import Enum

import pytest
from pydantic import BaseModel

from conftest import settings
from ksef2_cli.config import LocalConfig, OutputMode
from ksef2_cli.io import _read_json, _read_model, _write_json
from ksef2_cli.parsing import _parse_form_schema, _parse_optional_bool, _safe_filename
from ksef2_cli.rendering import (
    _cell,
    _plain_text,
    _to_jsonable,
    collection,
    render,
)
from ksef2_cli.sdk_models import (
    _batch_session_ref,
    _build_invoice_filter,
    _export_handle_to_dict,
    _invoice_metadata_params,
    _load_export_handle,
    _offset_params,
)


class DemoEnum(Enum):
    value = "value"


class DemoModel(BaseModel):
    name: str


class DemoPage(BaseModel):
    rows: list[DemoModel]
    has_more: bool


@dataclass
class DemoDataclass:
    payload: bytes


def test_optional_bool_parser_accepts_common_values() -> None:
    assert _parse_optional_bool(None, option_name="--x") is None
    assert _parse_optional_bool("yes", option_name="--x") is True
    assert _parse_optional_bool("false", option_name="--x") is False
    assert _parse_optional_bool("on", option_name="--x") is True
    assert _parse_optional_bool("0", option_name="--x") is False


def test_optional_bool_parser_rejects_unknown_value() -> None:
    with pytest.raises(ValueError, match="--x must be yes or no"):
        _parse_optional_bool("maybe", option_name="--x")


def test_form_schema_parser_and_safe_filename() -> None:
    assert _parse_form_schema("fa3").name == "FA3"
    assert _safe_filename("abc/123", ".xml") == "abc_123.xml"
    assert _safe_filename("ready.xml", ".xml") == "ready.xml"

    with pytest.raises(ValueError, match="Invalid form schema"):
        _parse_form_schema("missing")


def test_json_helpers_read_models_and_write_json(tmp_path) -> None:
    path = tmp_path / "payload.json"
    path.write_text('{"name": "demo"}', encoding="utf-8")

    assert _read_json(path) == {"name": "demo"}
    assert _read_model(path, DemoModel) == DemoModel(name="demo")

    target = tmp_path / "nested" / "out.json"
    _write_json(target, {"date": date(2026, 1, 2), "bytes": b"abc"})
    data = json.loads(target.read_text(encoding="utf-8"))
    assert data == {"date": "2026-01-02", "bytes": base64.b64encode(b"abc").decode("ascii")}


def test_rendering_converts_supported_types(capsys, tmp_path) -> None:
    value = _to_jsonable(
        {
            "model": DemoModel(name="demo"),
            "dataclass": DemoDataclass(payload=b"abc"),
            "enum": DemoEnum.value,
            "path": tmp_path / "file.txt",
            "date": date(2026, 1, 2),
            "config": LocalConfig(nip="5261040828", token="secret-token"),
        }
    )

    assert value["model"] == {"name": "demo"}
    assert value["dataclass"] == {"payload": base64.b64encode(b"abc").decode("ascii")}
    assert value["enum"] == "value"
    assert value["path"].endswith("file.txt")
    assert value["date"] == "2026-01-02"
    assert value["config"]["token"] == "**********"

    ctx = type("Ctx", (), {"obj": settings(output=OutputMode.text)})()
    render(ctx, {"rows": [{"name": "a", "extra": "b"}], "count": 1})
    render(ctx, {"name": "demo"})
    render(ctx, "plain")
    output = capsys.readouterr().out
    assert "Rows" not in output
    assert "rows: " in output
    assert "name: demo" in output
    assert "plain" in output


def test_rendering_small_helpers() -> None:
    assert _plain_text({"name": "demo", "empty": None}) == "name: demo"
    assert _plain_text([{"name": "a", "extra": "b"}, "plain"]) == "name=a extra=b\nplain"
    assert _plain_text([]) == ""
    assert _cell(None) == ""
    assert _cell(True) == "yes"
    assert _cell(False) == "no"
    assert _cell({"a": 1}) == '{"a":1}'


def test_rendering_uses_typed_collection_shape(capsys) -> None:
    ctx = type("Ctx", (), {"obj": settings(output=OutputMode.text)})()

    render(ctx, DemoPage(rows=[DemoModel(name="a")], has_more=False))
    render(ctx, collection({"rows": [{"name": "b"}], "count": 1}, [{"name": "b"}]))

    assert capsys.readouterr().out == "name=a\nname=b\n"


def test_invoice_filter_and_pagination_models() -> None:
    filters = _build_invoice_filter(
        role="seller",
        date_type="issue_date",
        date_from="2026-01-01T00:00:00Z",
        date_to=None,
        amount_type="brutto",
        currency_codes=["PLN"],
        invoice_types=["vat"],
        seller_nip=None,
        buyer_nip=None,
        buyer_vat_ue=None,
        buyer_other_id=None,
        invoice_number=None,
        ksef_number=None,
        amount_min=None,
        amount_max=None,
        invoice_schema="FA3",
        invoicing_mode="online",
        has_attachment=True,
        is_self_invoicing=False,
    )

    assert filters.role == "seller"
    assert filters.invoice_schema.name == "FA3"
    assert filters.has_attachment is True
    assert filters.is_self_invoicing is False
    assert _invoice_metadata_params(10, 0, "asc").page_size == 10
    assert _offset_params(10, 0).page_offset == 0


def test_export_handle_and_batch_reference_helpers(tmp_path) -> None:
    from ksef2.domain.models.invoices import ExportHandle

    handle = ExportHandle(reference_number="ref", aes_key=b"abc", iv=b"def")
    payload = _export_handle_to_dict(handle)

    assert payload == {
        "reference_number": "ref",
        "aes_key": base64.b64encode(b"abc").decode("ascii"),
        "iv": base64.b64encode(b"def").decode("ascii"),
    }

    handle_file = tmp_path / "handle.json"
    handle_file.write_text(json.dumps(payload), encoding="utf-8")
    loaded = _load_export_handle(handle_file)
    assert loaded.reference_number == "ref"
    assert loaded.aes_key == b"abc"

    assert _batch_session_ref("session-ref", None) == "session-ref"
    with pytest.raises(ValueError, match="either --reference or --state-file"):
        _batch_session_ref("session-ref", tmp_path / "state.json")
    with pytest.raises(ValueError, match="Provide --reference or --state-file"):
        _batch_session_ref(None, None)
