"""Batch regressions through the installed SDK and an in-memory HTTP transport."""

import base64
import hashlib
import json

import httpx
import pytest
from ksef2 import Environment
from ksef2.clients import AuthenticatedClient

from conftest import auth_state, batch_state, cli_args, fake_runtime, payload, prepared_batch
from ksef2_cli.app import app
from ksef2_cli.batch_artifact import write_prepared_batch

DATE = "2026-01-01T00:00:00Z"


class ContractTransport:
    def __init__(self, files=(), *, interrupt=False, code=200):
        self.calls = []
        self.files = files
        self.interrupt = interrupt
        self.code = code

    def request(self, method, path, **kwargs):
        self.calls.append((method, path, kwargs))
        if method == "POST" and path == "/sessions/batch":
            data = {"referenceNumber": "00000000-0000-0000-0000-000000000001", "partUploadRequests": [
                {"ordinalNumber": n, "method": "PUT", "url": f"https://storage.invalid/{n}", "headers": {}}
                for n in (1, 2)
            ]}
        elif method == "GET" and path == "/sessions/00000000-0000-0000-0000-000000000001":
            if self.interrupt:
                raise KeyboardInterrupt()
            data = {
                "status": {"code": self.code, "description": "completed"},
                "dateCreated": DATE, "dateUpdated": DATE,
                "invoiceCount": 2, "successfulInvoiceCount": 1, "failedInvoiceCount": 1,
                "upo": {"pages": [{"referenceNumber": "00000000-0000-0000-0000-000000000002", "downloadUrl": "https://storage.invalid/upo", "downloadUrlExpirationDate": DATE}]},
            }
        elif method == "GET" and path.endswith("/upo/00000000-0000-0000-0000-000000000002"):
            return httpx.Response(200, content=b"<upo/>")
        elif method == "GET" and (path.endswith("/invoices") or path.endswith("/invoices/failed")):
            token = (kwargs.get("headers") or {}).get("x-continuation-token")
            index = 1 if token else 0
            file = self.files[index] if self.files else None
            invoice = {
                "ordinalNumber": index + 1, "referenceNumber": f"00000000-0000-0000-0000-00000000001{index}",
                "invoiceHash": base64.b64encode(hashlib.sha256(file.read_bytes() if file else b"xml").digest()).decode(),
                "invoicingDate": DATE,
                "status": {"code": 440 if index else 200, "description": "duplicate" if index else "accepted", "details": ["already submitted"] if index else []},
            }
            if not index:
                invoice["ksefNumber"] = "5261040828-20260101-000000000000-00"
            data = {"invoices": [invoice], "continuationToken": None if index else "next"}
        else:
            assert method in ("POST", "PUT"), (method, path)
            return httpx.Response(204)
        return httpx.Response(200, json=data)

    def get(self, path, **kwargs):
        return self.request("GET", path, **kwargs)

    def post(self, path, **kwargs):
        return self.request("POST", path, **kwargs)

    def put(self, path, **kwargs):
        return self.request("PUT", path, **kwargs)


def authenticated(transport):
    return AuthenticatedClient(transport, auth_state().to_tokens(), None, environment=Environment.TEST)


@pytest.mark.parametrize("command,extra", [
    ("status", []), ("status", ["--wait"]), ("list", []), ("list", ["--failed"]),
])
def test_reference_read_commands_use_real_sdk(runner, command, extra):
    transport = ContractTransport()
    result = runner.invoke(app, cli_args("batch", command, "--reference", "00000000-0000-0000-0000-000000000001", *extra), obj=fake_runtime(auth=authenticated(transport)))
    data = payload(result)
    assert data["status"]["code"] == 200 if command == "status" else data["invoices"][0]["reference_number"] == "00000000-0000-0000-0000-000000000010"
    assert all(method == "GET" for method, _, _ in transport.calls)


def test_reference_upo_uses_real_sdk(runner, tmp_path):
    transport = ContractTransport()
    output = tmp_path / "upo.xml"
    payload(runner.invoke(app, cli_args("batch", "upo", "--reference", "00000000-0000-0000-0000-000000000001", "--upo-reference", "00000000-0000-0000-0000-000000000002", "--out", str(output)), obj=fake_runtime(auth=authenticated(transport))))
    assert output.read_bytes() == b"<upo/>"
    assert [(method, path) for method, path, _ in transport.calls] == [("GET", "/sessions/00000000-0000-0000-0000-000000000001/upo/00000000-0000-0000-0000-000000000002")]


@pytest.mark.parametrize("with_upo", [False, True])
def test_high_level_batch_lists_all_invoice_outcomes(runner, tmp_path, monkeypatch, with_upo):
    files = [tmp_path / "a.xml", tmp_path / "b.xml"]
    for n, file in enumerate(files):
        file.write_text(f"<invoice>{n}</invoice>")
    transport = ContractTransport(files)
    auth = authenticated(transport)
    monkeypatch.setattr(auth.batch, "prepare", lambda *args, **kwargs: prepared_batch())
    receipt = tmp_path / "receipt.json"
    args = ["invoices", "send", *map(str, files), "--mode", "batch", "--wait", "--receipt", str(receipt)]
    if with_upo:
        args += ["--upo-dir", str(tmp_path / "upos")]
    result = runner.invoke(app, cli_args(*args), obj=fake_runtime(auth=auth))
    # Partial rejection may produce a nonzero CLI exit while retaining the result.
    data = json.loads(result.output)
    assert data["items"][0]["ksef_number"] == "5261040828-20260101-000000000000-00", result.output
    assert data["items"][1]["status"] == "failed"
    assert data["items"][1]["error"] == "duplicate; already submitted"
    assert data["succeeded"] == 1 and data["failed"] == 1
    assert json.loads(receipt.read_text())["batch"]["session_reference"] == "00000000-0000-0000-0000-000000000001"
    assert bool(data["upo_files"]) == with_upo


@pytest.mark.parametrize("high_level", [False, True])
def test_interrupted_wait_preserves_reference(runner, tmp_path, monkeypatch, high_level):
    file = tmp_path / "invoice.xml"
    file.write_text("<invoice/>")
    transport = ContractTransport(interrupt=True)
    auth = authenticated(transport)
    monkeypatch.setattr(auth.batch, "prepare", lambda *args, **kwargs: prepared_batch())
    saved = tmp_path / "recovery.json"
    args = (["invoices", "send", str(file), "--mode", "batch", "--receipt", str(saved)] if high_level else ["batch", "submit", str(file), "--state-file", str(saved)])
    result = runner.invoke(app, cli_args(*args, "--wait"), obj=fake_runtime(auth=auth))
    assert result.exit_code == 130, result.output
    assert "00000000-0000-0000-0000-000000000001" in result.output
    data = json.loads(saved.read_text())
    assert (data["batch"]["session_reference"] if high_level else data["reference_number"]) == "00000000-0000-0000-0000-000000000001"
    assert len([1 for method, path, _ in transport.calls if method == "POST" and path == "/sessions/batch"]) == 1


def test_upload_retry_does_not_upload_to_processing_session(runner, tmp_path):
    transport = ContractTransport(code=150)
    auth = authenticated(transport)
    artifact = tmp_path / "prepared"
    write_prepared_batch(artifact, prepared_batch())
    state = tmp_path / "state.json"
    batch = prepared_batch()
    resumed = batch_state("00000000-0000-0000-0000-000000000001").model_copy(
        update={"prepared_batch_digest": batch.recovery_digest()}
    )
    state.write_text(resumed.to_json())
    payload(runner.invoke(app, cli_args("batch", "upload", "--prepared", str(artifact), "--state-file", str(state)), obj=fake_runtime(auth=auth)))
    assert all(method == "GET" for method, _, _ in transport.calls)


@pytest.mark.parametrize("command,extra", [
    ("status", []), ("status", ["--wait"]),
    ("upo", ["--wait"]),
])
def test_batch_receipt_reference_contract(runner, tmp_path, command, extra):
    """Cross-owner contract: receipt commands must not invent resume crypto state."""
    from ksef2_cli.commands.invoices.models import BatchInvoiceReceipt, InvoiceWorkflowReceipt

    receipt = tmp_path / "receipt.json"
    receipt.write_text(InvoiceWorkflowReceipt(
        mode="batch", submitted_files=[],
        batch=BatchInvoiceReceipt(
            session_reference="00000000-0000-0000-0000-000000000001", files=[],
        ),
    ).to_resumable_json())
    transport = ContractTransport()
    args = ["invoices", command, "--receipt", str(receipt), *extra]
    if command == "upo":
        args += ["--upo-dir", str(tmp_path / "upos")]
    data = payload(runner.invoke(app, cli_args(*args), obj=fake_runtime(auth=authenticated(transport))))
    assert data["session_reference"] == "00000000-0000-0000-0000-000000000001"
    if command == "upo":
        assert (tmp_path / "upos" / "batch-00000000-0000-0000-0000-000000000001-upo-1.xml").read_bytes() == b"<upo/>"
    assert all(method == "GET" for method, _, _ in transport.calls)


@pytest.mark.parametrize("command", ["status", "list"])
def test_state_file_reads_keep_real_sdk_support(runner, tmp_path, command):
    transport = ContractTransport()
    state = tmp_path / "state.json"
    state.write_text(batch_state("00000000-0000-0000-0000-000000000001").to_json())
    result = runner.invoke(app, cli_args("batch", command, "--state-file", str(state)), obj=fake_runtime(auth=authenticated(transport)))
    data = payload(result)
    if command == "status":
        assert data["status"]["code"] == 200
    else:
        assert data["invoices"][0]["ksef_number"] == "5261040828-20260101-000000000000-00"
    assert all(method == "GET" for method, _, _ in transport.calls)


def test_open_upload_retry_reuses_exact_parts_and_session(runner, tmp_path):
    transport = ContractTransport(code=100)
    auth = authenticated(transport)
    batch = prepared_batch()
    artifact = tmp_path / "prepared"
    write_prepared_batch(artifact, batch)
    state = tmp_path / "state.json"
    opened = auth.batch_session(prepared_batch=batch)
    state.write_text(opened.resume_state().to_json())
    transport.calls.clear()
    payload(runner.invoke(app, cli_args("batch", "upload", "--prepared", str(artifact), "--state-file", str(state)), obj=fake_runtime(auth=auth)))
    uploads = [kwargs["content"] for method, _, kwargs in transport.calls if method == "PUT"]
    assert uploads == [part.content for part in batch.parts]
    assert [(method, path) for method, path, _ in transport.calls if method == "POST"] == [
        ("POST", "/sessions/batch/00000000-0000-0000-0000-000000000001/close")
    ]
