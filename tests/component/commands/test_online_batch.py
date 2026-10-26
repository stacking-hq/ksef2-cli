import json
from dataclasses import replace
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any, NoReturn

import pytest
from conftest import (
    FakeClient,
    FakeService,
    batch_state,
    cli_args,
    fake_runtime,
    online_state,
    payload,
)
from ksef2 import ExceptionCode, KSeFNotReadyError, KSeFValidationError
from ksef2.models import (
    BatchSessionResumeState,
    OnlineSessionResumeState,
    SendInvoiceResponse,
    SessionStatusResponse,
    StatusInfo,
    Upo,
    UpoPage,
)

from ksef2_cli.app import app


class FakeSession(FakeService):
    pass


class FakeSubmission(FakeService):
    """Stand-in for ``InvoiceSubmission``, the handle ``send_invoice()`` returns."""

    def __init__(self, reference_number: str, **returns: Any) -> None:
        super().__init__(**returns)
        self.reference_number = reference_number
        self.response = SendInvoiceResponse(reference_number=reference_number)


def _last_called(service: FakeService, name: str) -> dict[str, Any]:
    """Return the keyword arguments of the most recent call to ``name``."""
    for call_name, _args, kwargs in reversed(service.calls):
        if call_name == name:
            return kwargs
    raise AssertionError(f"{name!r} was not called; calls={service.calls!r}")


def _session_status(
    description: str,
    *,
    code: int = 200,
    upo_references: list[str] | None = None,
) -> SessionStatusResponse:
    upo = (
        Upo(
            pages=[
                UpoPage(
                    reference_number=reference,
                    download_url="https://example.test/upo",
                    download_url_expiration_date=datetime(2026, 1, 1, tzinfo=UTC),
                )
                for reference in upo_references
            ]
        )
        if upo_references
        else None
    )
    return SessionStatusResponse(
        status=StatusInfo(code=code, description=description),
        date_created=datetime(2026, 1, 1, tzinfo=UTC),
        date_updated=datetime(2026, 1, 1, tzinfo=UTC),
        upo=upo,
    )


def test_online_open_and_send(runner, tmp_path) -> None:
    sent_handle = FakeSubmission("invoice-ref")
    waited_handle = FakeSubmission(
        "invoice-ref", wait={"reference_number": "invoice-ready"}
    )
    submissions = iter([sent_handle, waited_handle])
    session = FakeSession(
        resume_state=online_state(),
        send_invoice=lambda **kwargs: next(submissions),
        close=None,
    )
    auth_service = FakeService(online_session=session)
    runtime = fake_runtime(auth=auth_service)

    state_file = tmp_path / "online-state.json"
    opened = payload(
        runner.invoke(
            app,
            cli_args(
                "online", "open", "--state-file", str(state_file), "--form", "FA3"
            ),
            obj=runtime,
        )
    )
    assert opened["state_file"] == str(state_file)
    assert opened["state"]["reference_number"] == "online-ref"
    assert state_file.exists()
    # A state file that masks its key material cannot resume anything, so the saved JSON
    # has to validate back into the exact state the session reported.
    assert (
        OnlineSessionResumeState.model_validate_json(
            state_file.read_text(encoding="utf-8")
        )
        == online_state()
    )
    assert (state_file.stat().st_mode & 0o777) == 0o600

    invoice = tmp_path / "invoice.xml"
    invoice.write_text("<invoice/>", encoding="utf-8")
    save_state = tmp_path / "saved-state.json"
    sent = payload(
        runner.invoke(
            app,
            cli_args("online", "send", str(invoice), "--save-state", str(save_state)),
            obj=runtime,
        )
    )
    assert sent["closed"] is True
    assert sent["results"][0]["result"] == {"reference_number": "invoice-ref"}
    assert save_state.exists()
    assert session.called("send_invoice")["invoice_xml"] == b"<invoice/>"
    # Without --wait the submission response is reported as sent; nothing polls.
    assert [name for name, _, _ in sent_handle.calls] == []

    waited_result = payload(
        runner.invoke(
            app,
            cli_args("online", "send", str(invoice), "--wait", "--keep-open"),
            obj=runtime,
        )
    )
    assert waited_result["closed"] is False
    assert waited_result["results"][0]["result"] == {
        "reference_number": "invoice-ready"
    }
    # The submission handle, not the session, does the waiting.
    assert waited_handle.called("wait")["timeout"] == 60.0


def test_online_resume_commands(runner, tmp_path) -> None:
    state_file = tmp_path / "state.json"
    _ = state_file.write_text(
        online_state().to_json(indent=2),
        encoding="utf-8",
    )

    submission = FakeSubmission("i1", wait={"status": "ready"})

    def download_invoice_upo(**kwargs: Any) -> bytes:
        return b"upo-ksef" if kwargs.get("ksef_number") else b"upo-reference"

    session = FakeSession(
        get_status={"status": "open"},
        list_invoices={"invoices": [{"reference_number": "invoice-ref"}]},
        list_failed_invoices={"invoices": [{"reference_number": "failed-ref"}]},
        get_invoice_status={"status": "processing"},
        submission=lambda **kwargs: submission,
        download_invoice_upo=download_invoice_upo,
        close=None,
    )
    auth_service = FakeService(online_session=session)
    runtime = fake_runtime(auth=auth_service)

    assert payload(
        runner.invoke(
            app,
            cli_args("online", "status", "--state-file", str(state_file)),
            obj=runtime,
        )
    ) == {"status": "open"}
    assert payload(
        runner.invoke(
            app,
            cli_args("online", "list", "--state-file", str(state_file)),
            obj=runtime,
        )
    ) == {"invoices": [{"reference_number": "invoice-ref"}]}
    assert payload(
        runner.invoke(
            app,
            cli_args("online", "list", "--state-file", str(state_file), "--failed"),
            obj=runtime,
        )
    ) == {"invoices": [{"reference_number": "failed-ref"}]}
    assert payload(
        runner.invoke(
            app,
            cli_args(
                "online",
                "invoice-status",
                "--state-file",
                str(state_file),
                "--invoice-reference",
                "i1",
            ),
            obj=runtime,
        )
    ) == {"status": "processing"}
    assert payload(
        runner.invoke(
            app,
            cli_args(
                "online",
                "invoice-status",
                "--state-file",
                str(state_file),
                "--invoice-reference",
                "i1",
                "--wait",
            ),
            obj=runtime,
        )
    ) == {"status": "ready"}
    # --wait goes through the invoice's submission handle.
    assert submission.called("wait")["poll_interval"] == 2.0

    out = tmp_path / "upo.xml"
    assert payload(
        runner.invoke(
            app,
            cli_args(
                "online",
                "upo",
                "--state-file",
                str(state_file),
                "--out",
                str(out),
                "--invoice-reference",
                "i1",
            ),
            obj=runtime,
        )
    ) == {"path": str(out), "bytes": len(b"upo-reference")}
    assert out.read_bytes() == b"upo-reference"
    assert session.called("download_invoice_upo")["reference_number"] == "i1"

    out = tmp_path / "upo-ksef.xml"
    assert payload(
        runner.invoke(
            app,
            cli_args(
                "online",
                "upo",
                "--state-file",
                str(state_file),
                "--out",
                str(out),
                "--ksef-number",
                "ksef-1",
            ),
            obj=runtime,
        )
    ) == {"path": str(out), "bytes": len(b"upo-ksef")}
    assert _last_called(session, "download_invoice_upo")["ksef_number"] == "ksef-1"

    invalid = runner.invoke(
        app,
        cli_args("online", "upo", "--state-file", str(state_file), "--out", str(out)),
        obj=runtime,
    )
    assert invalid.exit_code == 2
    assert "Provide exactly one" in invalid.output

    assert payload(
        runner.invoke(
            app,
            cli_args("online", "close", "--state-file", str(state_file)),
            obj=runtime,
        )
    ) == {
        "reference_number": "online-ref",
        "closed": True,
    }


def test_online_status_reads_state_written_by_older_cli(runner, tmp_path) -> None:
    """CLI 0.0.1 wrote a bearer token into resume state; reading it must still work."""
    legacy_state = online_state().to_dict(mode="json")
    legacy_state["access_token"] = "access"
    state_file = tmp_path / "legacy-state.json"
    _ = state_file.write_text(json.dumps(legacy_state), encoding="utf-8")

    session = FakeSession(get_status={"status": "open"})
    auth_service = FakeService(online_session=session)

    with pytest.warns(DeprecationWarning, match="access_token.*deprecated"):
        assert payload(
            runner.invoke(
                app,
                cli_args("online", "status", "--state-file", str(state_file)),
                obj=fake_runtime(auth=auth_service),
            )
        ) == {"status": "open"}


def _reopen_batch_session(reopened: list[Any], session: FakeService) -> Any:
    """Build an ``auth.batch_session`` stand-in that reads its ``state`` the SDK way.

    ``AuthenticatedClient.batch_session`` parses a string as ``BatchSessionResumeState``
    JSON, so a stand-in that accepted anything would hide the one mistake these commands
    must not make: passing a bare session reference. Each accepted call is recorded.
    """

    def batch_session(**kwargs: Any) -> FakeService:
        state = kwargs["state"]
        if isinstance(state, str):
            _ = BatchSessionResumeState.from_json(state)
        reopened.append(state)
        return session

    return batch_session


def test_batch_submit_status_list_and_upo(runner, tmp_path) -> None:
    """`submit` hands back a closed session client; the rest reopen one from state."""
    submitted = FakeService(
        resume_state=batch_state(),
        wait=_session_status("completed"),
    )
    batch_service = FakeService(submit=submitted)
    session = FakeService(
        get_status=_session_status("completed", upo_references=["upo-ref"]),
        wait=_session_status("completed"),
        list_invoices={"invoices": [{"reference_number": "invoice-ref"}]},
        list_failed_invoices={"invoices": [{"reference_number": "failed-ref"}]},
    )
    reopened: list[Any] = []
    # ``auth.batch`` is a service object and ``auth.batch_session`` a factory, so
    # neither can come from FakeService's catch-all attribute lookup.
    invoice_sessions = FakeService(download_upo=b"batch-upo")
    auth_service = SimpleNamespace(
        batch=batch_service,
        batch_session=_reopen_batch_session(reopened, session),
        invoice_sessions=invoice_sessions,
    )
    runtime = fake_runtime(auth=auth_service)

    invoice = tmp_path / "invoice.xml"
    invoice.write_text("<invoice/>", encoding="utf-8")
    state_file = tmp_path / "batch-state.json"

    submitted_result = payload(
        runner.invoke(
            app,
            cli_args(
                "batch",
                "submit",
                str(invoice),
                "--state-file",
                str(state_file),
                "--offline",
                "--max-part-size",
                "100",
                "--wait",
            ),
            obj=runtime,
        )
    )
    assert submitted_result["state_file"] == str(state_file)
    assert submitted_result["status"]["status"]["description"] == "completed"
    assert state_file.exists()
    assert (
        BatchSessionResumeState.model_validate_json(
            state_file.read_text(encoding="utf-8")
        )
        == batch_state()
    )
    assert (state_file.stat().st_mode & 0o777) == 0o600
    assert batch_service.called("submit")["offline_mode"] is True
    assert batch_service.called("submit")["max_part_size"] == 100
    assert submitted.called("wait")["poll_interval"] == 2.0

    # Without --max-part-size the SDK default applies and without --wait nothing polls.
    unwaited = payload(
        runner.invoke(app, cli_args("batch", "submit", str(invoice)), obj=runtime)
    )
    assert unwaited["state_file"] is None
    assert unwaited["status"] is None
    assert batch_service.calls[-1][2].get("max_part_size") is None
    assert [name for name, _, _ in submitted.calls] == [
        "resume_state",
        "wait",
        "resume_state",
    ]

    # Status and listing reopen the session, which only the state file allows.
    assert (
        payload(
            runner.invoke(
                app,
                cli_args("batch", "status", "--state-file", str(state_file)),
                obj=runtime,
            )
        )["status"]["description"]
        == "completed"
    )
    waited_status = payload(
        runner.invoke(
            app,
            cli_args("batch", "status", "--state-file", str(state_file), "--wait"),
            obj=runtime,
        )
    )
    assert waited_status["status"]["description"] == "completed"
    assert session.called("wait")["timeout"] == 120.0
    assert payload(
        runner.invoke(
            app,
            cli_args("batch", "list", "--state-file", str(state_file)),
            obj=runtime,
        )
    ) == {"invoices": [{"reference_number": "invoice-ref"}]}
    assert payload(
        runner.invoke(
            app,
            cli_args("batch", "list", "--state-file", str(state_file), "--failed"),
            obj=runtime,
        )
    ) == {"invoices": [{"reference_number": "failed-ref"}]}
    assert session.called("list_invoices")["page_size"] == 10
    # Every reopening got the resume state itself, never the reference string.
    assert reopened == [batch_state()] * 4

    out = tmp_path / "batch-upo.xml"
    assert payload(
        runner.invoke(
            app,
            cli_args(
                "batch",
                "upo",
                "--reference",
                "batch-ref",
                "--upo-reference",
                "upo-ref",
                "--out",
                str(out),
            ),
            obj=runtime,
        )
    ) == {"path": str(out), "bytes": len(b"batch-upo")}
    assert out.read_bytes() == b"batch-upo"

    assert invoice_sessions.calls == [
        ("download_upo", ("batch-ref",), {"upo_reference_number": "upo-ref"})
    ]


@pytest.mark.parametrize("command", ["status", "list", "upo"])
@pytest.mark.parametrize("conflicting", [False, True])
def test_batch_session_flags_fail_before_authentication(
    runner, tmp_path, command, conflicting
) -> None:
    state_file = tmp_path / "state.json"
    _ = state_file.write_text(batch_state().to_json(), encoding="utf-8")
    runtime = fake_runtime()
    authenticated: list[bool] = []

    def authenticate() -> NoReturn:
        authenticated.append(True)
        raise AssertionError("Invalid flags must fail before authentication")

    runtime = replace(runtime, authenticated_client_factory=authenticate)
    args = ["batch", command]
    if command == "upo":
        args.extend(["--upo-reference", "upo-2", "--out", str(tmp_path / "upo.xml")])
    if conflicting:
        args.extend(["--reference", "batch-ref", "--state-file", str(state_file)])

    result = runner.invoke(app, cli_args(*args), obj=runtime)

    assert result.exit_code == 2
    assert json.loads(result.output)["error"]["type"] == "UsageError"
    assert (
        "Use either --reference or --state-file, not both."
        if conflicting
        else "Provide --reference or --state-file."
    ) in result.output
    assert "Traceback" not in result.output
    assert authenticated == []


@pytest.mark.parametrize("command", ["status", "list"])
def test_batch_status_and_list_refuse_a_bare_reference(runner, command) -> None:
    """A reference number is not resumable state, so it is refused rather than parsed.

    Both commands used to hand the reference to ``auth.batch_session(state=...)``, which
    reads a string as serialized state in JSON, so they authenticated first and failed
    with ``Invalid JSON`` afterwards.
    """

    reopened: list[Any] = []
    session = FakeService(get_status=_session_status("completed"))
    client = FakeClient()
    runtime = fake_runtime(
        client=client,
        auth=SimpleNamespace(batch_session=_reopen_batch_session(reopened, session)),
    )

    result = runner.invoke(
        app, cli_args("batch", command, "--reference", "batch-ref"), obj=runtime
    )

    assert result.exit_code == 2
    error = json.loads(result.output)["error"]
    assert error["type"] == "UsageError"
    assert error["title"] == "Batch session state required"
    assert f"batch {command} cannot reopen session batch-ref" in error["message"]
    assert "reference number alone" in error["message"]
    assert "Invalid JSON" not in result.output
    assert any("--state-file FILE" in hint for hint in error["hints"])
    assert any("batch submit --state-file" in hint for hint in error["hints"])
    # The handle was rejected up front: no session was reopened and none was requested.
    assert reopened == []
    assert client.entered == 0


@pytest.mark.parametrize("command", ["status", "list"])
def test_batch_status_and_list_reject_a_state_file_without_keys(
    runner, tmp_path, command
) -> None:
    """An ordinary dump of a session masks its keys, and is named as such."""

    state_file = tmp_path / "state.json"
    _ = state_file.write_text(batch_state().model_dump_json(indent=2), encoding="utf-8")
    reopened: list[Any] = []
    session = FakeService(get_status=_session_status("completed"))
    client = FakeClient()
    runtime = fake_runtime(
        client=client,
        auth=SimpleNamespace(batch_session=_reopen_batch_session(reopened, session)),
    )

    result = runner.invoke(
        app, cli_args("batch", command, "--state-file", str(state_file)), obj=runtime
    )

    assert result.exit_code == 2
    error = json.loads(result.output)["error"]
    assert error["title"] == "Batch session state cannot be resumed"
    unreadable = f"{state_file} does not hold resumable batch session state."
    assert unreadable in error["message"]
    assert any("masks its key material" in hint for hint in error["hints"])
    assert reopened == []
    assert client.entered == 0


def test_batch_session_state_cannot_be_a_reference_number() -> None:
    """What makes the two handles different: the SDK reads a string as state JSON."""

    with pytest.raises(KSeFValidationError, match="Invalid JSON"):
        _ = BatchSessionResumeState.from_json("batch-ref")


@pytest.mark.parametrize("use_state_file", [False, True])
def test_batch_upo_downloads_only_requested_page(runner, tmp_path, use_state_file) -> None:
    state_file = tmp_path / "state.json"
    _ = state_file.write_text(batch_state().to_json(), encoding="utf-8")
    # Only the direct endpoint is available: opening a batch session or fetching
    # its status and all pages would fail this invocation.
    invoice_sessions = FakeService(download_upo=b"second-upo-page")
    runtime = fake_runtime(auth=SimpleNamespace(invoice_sessions=invoice_sessions))
    output = tmp_path / "upo.xml"
    session_args = (
        ["--state-file", str(state_file)]
        if use_state_file
        else ["--reference", "batch-ref"]
    )

    result = runner.invoke(
        app,
        cli_args(
            "batch",
            "upo",
            *session_args,
            "--upo-reference",
            "upo-2",
            "--out",
            str(output)
        ),
        obj=runtime,
    )

    assert payload(result) == {"path": str(output), "bytes": len(b"second-upo-page")}
    assert output.read_bytes() == b"second-upo-page"
    assert invoice_sessions.calls == [
        ("download_upo", ("batch-ref",), {"upo_reference_number": "upo-2"})
    ]


def test_batch_upo_reports_endpoint_failure_without_writing_file(runner, tmp_path) -> None:
    invoice_sessions = FakeService(
        download_upo=KSeFNotReadyError(
            404,
            ExceptionCode.NOT_PROCESSED_YET,
            "UPO page upo-2 is not ready for batch-ref",
        )
    )
    output = tmp_path / "upo.xml"
    result = runner.invoke(
        app,
        cli_args(
            "batch",
            "upo",
            "--reference",
            "batch-ref",
            "--upo-reference",
            "upo-2",
            "--out",
            str(output),
        ),
        obj=fake_runtime(auth=SimpleNamespace(invoice_sessions=invoice_sessions)),
    )

    assert result.exit_code == 1
    assert "UPO page upo-2 is not ready for batch-ref" in result.output
    assert not output.exists()
