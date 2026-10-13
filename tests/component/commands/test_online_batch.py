import json
from datetime import UTC, datetime
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
from ksef2.models import (
    BatchSessionResumeState,
    OnlineSessionResumeState,
    SessionStatusResponse,
    StatusInfo,
    Upo,
    UpoPage,
)

from ksef2_cli.app import app


class FakeSession(FakeService):
    pass


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
    session = FakeSession(
        get_state=online_state(),
        send_invoice={"reference_number": "invoice-ref"},
        send_invoice_and_wait={"reference_number": "invoice-ready"},
        close=None,
    )
    auth_service = FakeService(online_session=session, resume_online_session=session)
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

    waited = payload(
        runner.invoke(
            app,
            cli_args("online", "send", str(invoice), "--wait", "--keep-open"),
            obj=runtime,
        )
    )
    assert waited["closed"] is False
    assert waited["results"][0]["result"] == {"reference_number": "invoice-ready"}


def test_online_resume_commands(runner, tmp_path) -> None:
    state_file = tmp_path / "state.json"
    _ = state_file.write_text(
        online_state().to_json(indent=2),
        encoding="utf-8",
    )

    session = FakeSession(
        get_status={"status": "open"},
        list_invoices={"invoices": [{"reference_number": "invoice-ref"}]},
        list_failed_invoices={"invoices": [{"reference_number": "failed-ref"}]},
        get_invoice_status={"status": "processing"},
        wait_for_invoice_ready={"status": "ready"},
        get_invoice_upo_by_reference=b"upo-reference",
        get_invoice_upo_by_ksef_number=b"upo-ksef",
        close=None,
    )
    auth_service = FakeService(resume_online_session=session)
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

    invalid = runner.invoke(
        app,
        cli_args("online", "upo", "--state-file", str(state_file), "--out", str(out)),
        obj=runtime,
    )
    assert invalid.exit_code == 1
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
    auth_service = FakeService(resume_online_session=session)

    with pytest.warns(DeprecationWarning, match="access_token.*deprecated"):
        assert payload(
            runner.invoke(
                app,
                cli_args("online", "status", "--state-file", str(state_file)),
                obj=fake_runtime(auth=auth_service),
            )
        ) == {"status": "open"}


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
        download_upo=[b"batch-upo"],
    )
    # ``auth.batch`` is a service object and ``auth.batch_session`` a factory, so
    # neither can come from FakeService's catch-all attribute lookup.
    auth_service = SimpleNamespace(
        batch=batch_service, batch_session=lambda **kwargs: session
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

    assert (
        payload(
            runner.invoke(
                app,
                cli_args("batch", "status", "--reference", "batch-ref"),
                obj=runtime,
            )
        )["status"]["description"]
        == "completed"
    )
    waited_status = payload(
        runner.invoke(
            app,
            cli_args("batch", "status", "--reference", "batch-ref", "--wait"),
            obj=runtime,
        )
    )
    assert waited_status["status"]["description"] == "completed"
    assert session.called("wait")["timeout"] == 120.0
    # The state file written by `submit` is the other way back into the session.
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
    assert payload(
        runner.invoke(
            app, cli_args("batch", "list", "--reference", "batch-ref"), obj=runtime
        )
    ) == {"invoices": [{"reference_number": "invoice-ref"}]}
    assert payload(
        runner.invoke(
            app,
            cli_args("batch", "list", "--reference", "batch-ref", "--failed"),
            obj=runtime,
        )
    ) == {"invoices": [{"reference_number": "failed-ref"}]}
    assert session.called("list_invoices")["page_size"] == 10

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

    unknown = runner.invoke(
        app,
        cli_args(
            "batch",
            "upo",
            "--reference",
            "batch-ref",
            "--upo-reference",
            "nope",
            "--out",
            str(out),
        ),
        obj=runtime,
    )
    assert unknown.exit_code == 1
    assert "upo-ref" in unknown.output
