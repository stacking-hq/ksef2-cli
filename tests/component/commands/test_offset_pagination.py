import json
from types import SimpleNamespace

import pytest
from conftest import FakeClient, FakePager, FakeService, fake_runtime, payload, plain

from ksef2_cli.app import app
from ksef2_cli.config import RuntimeOverrides


COMMANDS = [
    "invoices metadata",
    "certificates list",
    "permissions entity-roles",
    "permissions query",
    "peppol providers",
]


@pytest.fixture(params=COMMANDS)
def pagination_command(request, tmp_path):
    args = request.param.split()
    if request.param == "invoices metadata":
        args += ["--date-from", "2026-01-01", "--date-to", "2026-01-02"]
    elif request.param == "permissions query":
        query = tmp_path / "query.json"
        query.write_text("{}", encoding="utf-8")
        args += ["personal", "--payload", str(query)]
    return request.param, args


@pytest.mark.parametrize("output_flags", [[], ["--json"], ["-o", "json"]])
def test_all_nonzero_offset_fails_before_auth_or_client(
    runner, pagination_command, output_flags
):
    _, args = pagination_command
    callbacks = []

    def unexpected_callback():
        callbacks.append(True)
        raise AssertionError("Invalid pagination must fail before auth or network work")

    runtime = RuntimeOverrides(
        client_factory=unexpected_callback,
        authenticated_client_factory=unexpected_callback,
        model_reader=unexpected_callback,
    )
    result = runner.invoke(
        app,
        ["--no-config", *output_flags, *args, "--all", "--page-offset", "1"],
        obj=runtime,
    )

    assert result.exit_code == 2, result.output
    assert callbacks == []
    message = (
        "--all cannot be combined with a nonzero --page-offset. "
        "Omit --page-offset or use --page-offset 0."
    )
    if output_flags:
        error = json.loads(result.output)["error"]
        assert error["type"] == "UsageError"
        assert error["exit_code"] == 2
        assert error["message"] == message
    else:
        assert message in plain(result.output)


class MetadataPager(FakePager):
    def first_response(self):
        return {"invoices": self.first_page()}


@pytest.mark.parametrize(
    "flags,all_pages,offset",
    [
        (["--all"], True, 0),
        (["--all", "--page-offset", "0"], True, 0),
        ([], False, 0),
        (["--page-offset", "3"], False, 3),
    ],
)
def test_pagination_preserves_page_size_and_single_page_offset(
    runner, pagination_command, flags, all_pages, offset
):
    command, args = pagination_command
    first_page = [{"id": index} for index in range(12)]
    second_page = [{"id": 12}]
    pager = MetadataPager(first_page, second_page)
    method = {
        "invoices metadata": "search",
        "certificates list": "list",
        "permissions entity-roles": "list_entity_roles",
        "permissions query": "list_personal",
        "peppol providers": "list",
    }[command]
    service = FakeService(**{method: pager})
    runtime = fake_runtime(
        auth=SimpleNamespace(
            invoices=service, certificates=service, permissions=service
        ),
        client=FakeClient(peppol=service),
    )
    result = runner.invoke(
        app,
        ["--no-config", "--json", *args, "--page-size", "12", *flags],
        obj=runtime,
    )

    expected = first_page + second_page if all_pages else first_page
    if command == "invoices metadata" and not all_pages:
        expected = {"invoices": expected}
    assert payload(result) == expected
    params = service.called(method)["params"]
    assert params.page_size == 12
    assert params.page_offset == offset
    assert len(service.calls) == 1


@pytest.mark.parametrize(
    "flags",
    [["--page-offset", "-1"], ["--page-size", "9"], ["--page-size", "251"]],
)
def test_pagination_ranges_still_fail_before_client(runner, pagination_command, flags):
    command, args = pagination_command
    if flags == ["--page-size", "251"] and command != "invoices metadata":
        flags = ["--page-size", "101"]
    callbacks = []

    def unexpected_callback():
        callbacks.append(True)
        raise AssertionError("Invalid ranges must fail before auth or network work")

    result = runner.invoke(
        app,
        ["--no-config", *args, "--all", *flags],
        obj=RuntimeOverrides(
            client_factory=unexpected_callback,
            authenticated_client_factory=unexpected_callback,
        ),
    )
    assert result.exit_code == 2, result.output
    assert "Invalid value" in plain(result.output)
    assert callbacks == []
