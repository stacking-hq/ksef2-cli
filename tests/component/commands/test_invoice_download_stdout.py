"""File and raw stdout contracts for the invoice download CLI."""

import json
from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

from conftest import FakeService, fake_runtime, plain
from ksef2_cli.app import app
from ksef2_cli.config import RuntimeOverrides


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner(mix_stderr=False)


@pytest.mark.parametrize("option", ["--out", "-o"])
@pytest.mark.parametrize("wait", [False, True])
@pytest.mark.parametrize("encoding", ["utf-8", "utf-16"])
def test_download_stdout_preserves_bytes(
    runner, tmp_path, monkeypatch, option, wait, encoding
):
    monkeypatch.chdir(tmp_path)
    xml = (
        f'<?xml version="1.0" encoding="{encoding}"?><invoice>Zażółć €</invoice>'
    ).encode(encoding)
    service = FakeService(download=xml)
    args = [
        "--no-config", "invoices", "download", "--ksef-number", "dummy-number",
        option, "-",
    ]
    if wait:
        args += ["--wait", "--timeout", "17", "--poll-interval", "0.7"]

    result = runner.invoke(
        app, args, obj=fake_runtime(auth=SimpleNamespace(invoices=service))
    )

    assert result.exit_code == 0, result.stderr
    assert result.stdout_bytes == xml
    assert result.stderr_bytes == b""
    assert list(tmp_path.iterdir()) == []
    assert service.called("download") == {
        "ksef_number": "dummy-number",
        "timeout": 17.0 if wait else None,
        "poll_interval": 0.7 if wait else 2.0,
    }


@pytest.mark.parametrize("explicit", [False, True])
@pytest.mark.parametrize("json_output", [False, True])
def test_download_file_output_unchanged(
    runner, tmp_path, monkeypatch, explicit, json_output
):
    monkeypatch.chdir(tmp_path)
    xml = b"<invoice>\xc5\xbc</invoice>"
    target = "chosen.xml" if explicit else "dummy-number.xml"
    service = FakeService(download=xml)
    args = ["--no-config"] + (["--json"] if json_output else [])
    args += ["invoices", "download", "--ksef-number", "dummy-number"]
    if explicit:
        args += ["--out", target]

    result = runner.invoke(
        app, args, obj=fake_runtime(auth=SimpleNamespace(invoices=service))
    )

    assert result.exit_code == 0, result.stderr
    assert (tmp_path / target).read_bytes() == xml
    assert list(tmp_path.iterdir()) == [tmp_path / target]
    if json_output:
        assert json.loads(result.stdout) == {"path": target, "bytes": len(xml)}
    else:
        assert result.stdout == f"path: {target}\nbytes: {len(xml)}\n"
    assert result.stderr_bytes == b""


@pytest.mark.parametrize(
    "global_options", [["--json"], ["--output", "json"], ["-o", "json"]]
)
@pytest.mark.parametrize("option", ["--out", "-o"])
def test_download_stdout_rejects_json_before_auth(
    runner, tmp_path, monkeypatch, global_options, option
):
    monkeypatch.chdir(tmp_path)
    calls = []

    def unexpected_auth():
        calls.append("auth/network")
        raise AssertionError("JSON conflict must be rejected before authentication")

    runtime = RuntimeOverrides(
        client_factory=unexpected_auth, authenticated_client_factory=unexpected_auth
    )
    result = runner.invoke(
        app,
        [
            "--no-config", *global_options, "invoices", "download",
            "--ksef-number", "dummy-number", option, "-",
        ],
        obj=runtime,
    )

    assert result.exit_code == 2
    assert result.stdout_bytes == b""
    error = json.loads(result.stderr)["error"]
    assert error["type"] == "UsageError"
    assert error["exit_code"] == 2
    assert "--out - cannot be combined with global JSON output" in error["message"]
    assert calls == []
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("failure", ["auth", "download", "pipe"])
def test_download_stdout_failures_use_stderr(runner, tmp_path, monkeypatch, failure):
    monkeypatch.chdir(tmp_path)
    service = FakeService(
        download=OSError("dummy download failure")
        if failure == "download" else b"<invoice/>"
    )
    runtime = fake_runtime(auth=SimpleNamespace(invoices=service))
    if failure == "auth":

        def fail_auth():
            raise OSError("dummy auth failure")

        runtime = RuntimeOverrides(authenticated_client_factory=fail_auth)
    elif failure == "pipe":
        import ksef2_cli.commands.invoices.metadata as command

        class BrokenStream:
            def write(self, _content):
                raise BrokenPipeError("dummy closed pipe")

        monkeypatch.setattr(
            command.click, "get_binary_stream", lambda _name: BrokenStream()
        )

    result = runner.invoke(
        app,
        [
            "--no-config", "invoices", "download", "--ksef-number", "dummy-number",
            "--out", "-",
        ],
        obj=runtime,
    )

    assert result.exit_code == 1
    assert result.stdout_bytes == b""
    assert "Error:" in plain(result.stderr)
    assert "Traceback" not in result.stderr
    assert list(tmp_path.iterdir()) == []
    if failure == "auth":
        assert service.calls == []
