"""JSON rendering for CLI command results."""

import json

from pydantic import TypeAdapter

from ksef2_cli.commands.invoices.models import ExportHandleSaved, ExportPaths
from ksef2_cli.results import FocusedResult

_JSON_VALUE = TypeAdapter(object)


class JsonRenderer:
    """Render typed command results as formatted JSON."""

    def render(self, value: object) -> str:
        return json.dumps(
            self.to_jsonable(value),
            ensure_ascii=False,
            indent=2,
        )

    def to_jsonable(self, value: object) -> object:
        if isinstance(value, FocusedResult):
            value = value.payload
        if isinstance(value, (ExportHandleSaved, ExportPaths)):
            value = value.model_dump(mode="json", by_alias=True, exclude_none=True)
        return _JSON_VALUE.dump_python(value, mode="json", by_alias=True)


json_renderer = JsonRenderer()
