"""In-memory invoice sources and recovery after an interrupted online wait."""

import json
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest
from conftest import (
    FakeService,
    batch_state,
    cli_args,
    fake_runtime,
    online_state,
    payload,
)
from ksef2.models import BatchInvoice
from ksef2_cli.app import app

XML = b'<?xml version="1.0"?>\r\n<invoice> signed \xc5\x82 </invoice>\r\n'


def services(mode, *, wait=None):
    submission = SimpleNamespace(reference_number="invoice-ref", wait=wait)
    session = FakeService(
        send_invoice=submission,
        resume_state=online_state() if mode == "online" else batch_state(),
    )
    session.reference_number = "online-ref"
    batch = FakeService(submit=session)
    auth = SimpleNamespace(online_session=lambda **kwargs: session, batch=batch)
    return fake_runtime(auth=auth), session, batch


@pytest.mark.parametrize("mode", ["online", "batch"])
@pytest.mark.parametrize("mixed", [False, True])
def test_stdin_exact_bytes_and_receipts(runner, tmp_path, monkeypatch, mode, mixed):
    monkeypatch.chdir(tmp_path)
    runtime, session, batch = services(mode)
    args = ["invoices", "send", "-", "--mode", mode, "--receipt-dir", "receipts"]
    if mixed:
        Path("stdin.xml").write_bytes(b"<disk/>\n")
        args.append("stdin.xml")
    original_read = Path.read_bytes

    def disk_read(path):
        assert path != Path("stdin-2.xml")
        if not mixed:
            assert path != Path("stdin.xml")
        return original_read(path)

    monkeypatch.setattr(Path, "read_bytes", disk_read)
    result = payload(runner.invoke(app, cli_args(*args), input=XML, obj=runtime))
    assert result["submitted"] == (2 if mixed else 1)
    virtual = "stdin-2.xml" if mixed else "stdin.xml"
    if mode == "online":
        sent = [
            kwargs["invoice_xml"]
            for name, _, kwargs in session.calls
            if name == "send_invoice"
        ]
        assert sent == ([b"<disk/>\n", XML] if mixed else [XML])
        receipt = json.loads(
            Path(f"receipts/{Path(virtual).stem}-receipt.json").read_text()
        )
        assert receipt["online"]["invoice_reference"] == "invoice-ref"
    else:
        calls = [args for name, args, _ in batch.calls if name == "submit"]
        assert len(calls) == 1
        invoices = calls[0][0]
        assert isinstance(invoices[-1], BatchInvoice)
        assert invoices[-1].file_name == virtual
        assert invoices[-1].content == XML
        if mixed:
            assert invoices[0] == Path("stdin.xml")
        receipt = json.loads(Path("receipts/batch-batch-ref-receipt.json").read_text())
        assert receipt["batch"]["session_reference"] == "batch-ref"
    assert virtual in receipt["submitted_files"]
    assert sorted(str(p) for p in tmp_path.glob("*.xml")) == (
        [str(tmp_path / "stdin.xml")] if mixed else []
    )


@pytest.mark.parametrize("mode", ["online", "batch"])
@pytest.mark.parametrize(
    "content,label",
    [
        (b" \n", "empty"),
        (b"\xef\xbb\xbf<x/>", "UTF-8 BOM"),
        (b"\xff\xfe<x/>", "UTF-16 LE BOM"),
        (b"\xff", "must be UTF-8"),
    ],
)
def test_stdin_validation_before_auth(runner, mode, content, label):
    def authenticate():
        pytest.fail("validation must precede authentication")

    runtime = replace(fake_runtime(), authenticated_client_factory=authenticate)
    result = runner.invoke(
        app,
        cli_args("invoices", "send", "-", "--mode", mode),
        input=content,
        obj=runtime,
    )
    assert result.exit_code == 1
    assert label in json.loads(result.output)["error"]["message"]


@pytest.mark.parametrize("mode", ["online", "batch"])
def test_duplicate_stdin_and_missing_file_fail_locally(runner, tmp_path, mode):
    def authenticate():
        pytest.fail("validation must precede authentication")

    runtime = replace(fake_runtime(), authenticated_client_factory=authenticate)
    duplicate = runner.invoke(
        app, cli_args("invoices", "send", "-", "-", "--mode", mode), obj=runtime
    )
    assert duplicate.exit_code == 1
    assert "only once" in json.loads(duplicate.output)["error"]["message"]
    missing = runner.invoke(
        app,
        cli_args(
            "invoices", "send", "-", str(tmp_path / "missing.xml"), "--mode", mode
        ),
        input=XML,
        obj=runtime,
    )
    assert missing.exit_code == 2
    assert "does not exist" in missing.output


@pytest.mark.parametrize("failure", [KeyboardInterrupt, TimeoutError])
def test_online_receipt_saved_before_wait_and_no_resend(runner, tmp_path, failure):
    receipt = tmp_path / "receipt.json"

    def wait(**kwargs):
        saved = json.loads(receipt.read_text())
        assert saved["online"]["invoice_reference"] == "invoice-ref"
        assert saved["online"]["session_state"]["reference_number"] == "online-ref"
        raise failure()

    runtime, session, _ = services("online", wait=wait)
    result = runner.invoke(
        app,
        cli_args("invoices", "send", "-", "--wait", "--receipt", str(receipt)),
        input=XML,
        obj=runtime,
    )
    assert result.exit_code == (130 if failure is KeyboardInterrupt else 1), (
        result.output
    )
    message = json.loads(result.output)["error"]["message"]
    assert "invoice-ref" in message
    assert "online-ref" in message
    assert "do not submit" in message
    assert len([name for name, _, _ in session.calls if name == "send_invoice"]) == 1
    assert receipt.exists()


@pytest.mark.parametrize("mode", ["online", "batch"])
def test_directory_and_stdin_keep_distinct_receipt_names(runner, tmp_path, mode):
    directory = tmp_path / "invoices"
    directory.mkdir()
    (directory / "stdin.xml").write_bytes(b"<disk/>")
    nested = directory / "nested"
    nested.mkdir()
    (nested / "stdin-2.xml").write_bytes(b"<nested/>")
    runtime, session, batch = services(mode)
    result = payload(
        runner.invoke(
            app,
            cli_args(
                "invoices",
                "send",
                str(directory),
                "-",
                "--recursive",
                "--mode",
                mode,
                "--receipt-dir",
                str(tmp_path / "receipts"),
            ),
            input=XML,
            obj=runtime,
        )
    )
    assert result["submitted"] == 3
    assert result["items"][-1]["file"] == "stdin-3.xml"
    if mode == "online":
        assert session.called("send_invoice")["invoice_xml"] == b"<nested/>"
        assert len(list((tmp_path / "receipts").glob("*.json"))) == 3
    else:
        invoices = next(args[0] for name, args, _ in batch.calls if name == "submit")
        assert invoices[-1].file_name == "stdin-3.xml"
        assert invoices[-1].content == XML
