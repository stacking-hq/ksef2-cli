from datetime import UTC, datetime

from conftest import FakeService, cli_args, fake_runtime, payload
from ksef2 import FormSchema
from ksef2.domain.models.batch import BatchSessionState
from ksef2.domain.models.session import (
    OnlineSessionState,
    SessionStatusResponse,
    StatusInfo,
)
from ksef2_cli.app import app


class FakeSession(FakeService):
    pass


def _online_state(reference_number: str = "online-ref") -> OnlineSessionState:
    return OnlineSessionState.from_encoded(
        reference_number=reference_number,
        aes_key=b"aes",
        iv=b"iv",
        access_token="access",
        valid_until=datetime(2026, 1, 1, tzinfo=UTC),
        form_code=FormSchema.FA3,
    )


def _batch_state(reference_number: str = "batch-ref") -> BatchSessionState:
    return BatchSessionState.from_encoded(
        reference_number=reference_number,
        aes_key=b"aes",
        iv=b"iv",
        access_token="access",
        form_code=FormSchema.FA3,
        part_upload_requests=[],
    )


def _session_status(description: str) -> SessionStatusResponse:
    return SessionStatusResponse(
        status=StatusInfo(code=200, description=description),
        date_created=datetime(2026, 1, 1, tzinfo=UTC),
        date_updated=datetime(2026, 1, 1, tzinfo=UTC),
    )


def test_online_open_and_send(runner, tmp_path) -> None:
    session = FakeSession(
        get_state=_online_state(),
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
    state_file.write_text(
        """
        {
          "reference_number": "online-ref",
          "aes_key": "aes",
          "iv": "iv",
          "access_token": "access",
          "form_code": "FA3",
          "valid_until": "2026-01-01T00:00:00Z"
        }
        """,
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


def test_batch_submit_status_list_and_upo(runner, tmp_path) -> None:
    service = FakeService(
        prepare_batch_from_paths={"prepared": True},
        submit_prepared_batch=_batch_state(),
        wait_for_completion=_session_status("completed"),
        get_status={"status": "processing"},
        list_invoices={"invoices": [{"reference_number": "invoice-ref"}]},
        list_failed_invoices={"invoices": [{"reference_number": "failed-ref"}]},
        get_upo=b"batch-upo",
    )
    runtime = fake_runtime(auth=type("Auth", (), {"batch": service})())

    invoice = tmp_path / "invoice.xml"
    invoice.write_text("<invoice/>", encoding="utf-8")
    state_file = tmp_path / "batch-state.json"

    submitted = payload(
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
    assert submitted["state_file"] == str(state_file)
    assert submitted["status"]["status"]["description"] == "completed"
    assert state_file.exists()
    assert service.called("prepare_batch_from_paths")["offline_mode"] is True

    assert payload(
        runner.invoke(
            app, cli_args("batch", "status", "--reference", "batch-ref"), obj=runtime
        )
    ) == {"status": "processing"}
    waited_status = payload(
        runner.invoke(
            app,
            cli_args("batch", "status", "--reference", "batch-ref", "--wait"),
            obj=runtime,
        )
    )
    assert waited_status["status"]["description"] == "completed"
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
