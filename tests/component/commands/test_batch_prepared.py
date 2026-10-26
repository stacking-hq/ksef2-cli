"""Preparing a batch once and uploading its parts more than once."""

from types import SimpleNamespace
from typing import Any

import pytest
from conftest import (
    PREPARED_PARTS,
    FakeService,
    batch_state,
    cli_args,
    fake_runtime,
    payload,
    plain,
    prepared_batch,
)
from ksef2 import KSeFBatchUploadError, KSeFExternalTransferError
from ksef2.models import BatchSessionResumeState, FormSchema, PreparedBatch
from datetime import UTC, datetime
from ksef2.models import SessionStatusResponse, StatusInfo

from ksef2_cli.app import app
from ksef2_cli.batch_artifact import MANIFEST_NAME, PARTS_DIR, write_prepared_batch


def _auth(batch_service: FakeService, session: FakeService) -> Any:
    """``auth.batch`` is a service and ``auth.batch_session`` a factory, so neither can
    come from FakeService's catch-all attribute lookup."""

    session.returns.setdefault("get_status", SessionStatusResponse(
        status=StatusInfo(code=100, description="open"),
        date_created=datetime(2026, 1, 1, tzinfo=UTC),
        date_updated=datetime(2026, 1, 1, tzinfo=UTC),
    ))
    return SimpleNamespace(
        batch=batch_service, batch_session=lambda **kwargs: session
    )


def _upload_error(prepared: PreparedBatch) -> KSeFBatchUploadError:
    """The error KSeF storage raises when it rejects one of the parts."""

    return KSeFBatchUploadError(
        transfer_error=KSeFExternalTransferError(
            operation="upload",
            host="storage.test",
            reference_number="batch-ref",
            part_ordinal=2,
            status_code=503,
        ),
        recovery_state=batch_state(),
        prepared_batch=prepared,
    )


def test_batch_prepare_stores_the_parts_it_built(runner, tmp_path) -> None:
    batch = prepared_batch(offline_mode=True)
    batch_service = FakeService(prepare=batch)
    runtime = fake_runtime(auth=_auth(batch_service, FakeService()))

    invoice = tmp_path / "invoice.xml"
    invoice.write_text("<invoice/>", encoding="utf-8")
    artifact = tmp_path / "prepared"

    result = payload(
        runner.invoke(
            app,
            cli_args(
                "batch",
                "prepare",
                str(invoice),
                "--out",
                str(artifact),
                "--offline",
                "--max-part-size",
                "100",
            ),
            obj=runtime,
        )
    )

    assert result == {
        "path": str(artifact),
        "digest": batch.recovery_digest(),
        "parts": 2,
        "invoices": 2,
    }
    assert (artifact / MANIFEST_NAME).exists()
    stored = artifact / PARTS_DIR / "part-0001.bin"
    assert stored.read_bytes() == batch.parts[0].content
    assert batch_service.called("prepare")["form_code"] is FormSchema.FA3
    assert batch_service.called("prepare")["offline_mode"] is True
    assert batch_service.called("prepare")["max_part_size"] == 100
    assert batch_service.calls[0][1] == ([invoice],)


def test_batch_prepare_without_max_part_size_keeps_the_sdk_default(
    runner, tmp_path
) -> None:
    batch_service = FakeService(prepare=prepared_batch())
    runtime = fake_runtime(auth=_auth(batch_service, FakeService()))

    invoice = tmp_path / "invoice.xml"
    invoice.write_text("<invoice/>", encoding="utf-8")

    result = runner.invoke(
        app,
        cli_args("batch", "prepare", str(invoice), "--out", str(tmp_path / "prepared")),
        obj=runtime,
    )

    assert result.exit_code == 0, result.output
    assert "max_part_size" not in batch_service.called("prepare")


def test_batch_submit_from_prepared_uploads_the_stored_parts(runner, tmp_path) -> None:
    batch = prepared_batch()
    artifact = tmp_path / "prepared"
    _ = write_prepared_batch(artifact, batch)

    submitted = FakeService(resume_state=batch_state())
    batch_service = FakeService(submit=submitted)
    runtime = fake_runtime(auth=_auth(batch_service, FakeService()))
    state_file = tmp_path / "batch-state.json"

    result = payload(
        runner.invoke(
            app,
            cli_args(
                "batch",
                "submit",
                "--prepared",
                str(artifact),
                "--state-file",
                str(state_file),
            ),
            obj=runtime,
        )
    )

    assert result["state_file"] == str(state_file)
    assert result["state"]["reference_number"] == "batch-ref"
    # The payload is the stored one, byte for byte, and carries no build options.
    sent = batch_service.calls[-1][1][0]
    assert isinstance(sent, PreparedBatch)
    assert sent.recovery_digest() == batch.recovery_digest()
    assert batch_service.called("submit") == {}
    assert [name for name, _, _ in submitted.calls] == ["resume_state"]


@pytest.mark.parametrize(
    ("args", "expected"),
    [
        ([], "Pass the invoice files to submit"),
        (["--prepared", "missing"], "not a prepared batch artifact"),
    ],
)
def test_batch_submit_needs_invoices_or_a_usable_artifact(
    runner, tmp_path, args: list[str], expected: str
) -> None:
    runtime = fake_runtime(auth=_auth(FakeService(), FakeService()))

    result = runner.invoke(app, cli_args("batch", "submit", *args), obj=runtime)

    assert result.exit_code == 1
    assert expected in result.output
    assert "batch prepare" in result.output


def test_batch_submit_rejects_invoices_together_with_an_artifact(
    runner, tmp_path
) -> None:
    invoice = tmp_path / "invoice.xml"
    invoice.write_text("<invoice/>", encoding="utf-8")
    artifact = tmp_path / "prepared"
    _ = write_prepared_batch(artifact, prepared_batch())
    runtime = fake_runtime(auth=_auth(FakeService(), FakeService()))

    result = runner.invoke(
        app,
        cli_args("batch", "submit", str(invoice), "--prepared", str(artifact)),
        obj=runtime,
    )

    assert result.exit_code == 1
    assert "not both" in result.output


def test_failed_submit_keeps_the_state_a_retry_needs(runner, tmp_path) -> None:
    batch = prepared_batch()
    artifact = tmp_path / "prepared"
    _ = write_prepared_batch(artifact, batch)

    batch_service = FakeService(submit=_upload_error(batch))
    runtime = fake_runtime(auth=_auth(batch_service, FakeService()))
    state_file = tmp_path / "retry-state.json"

    result = runner.invoke(
        app,
        cli_args(
            "batch",
            "submit",
            "--prepared",
            str(artifact),
            "--state-file",
            str(state_file),
        ),
        obj=runtime,
    )

    assert result.exit_code == 1
    assert "storage upload failed" in result.output
    assert "batch upload" in result.output
    resumed = BatchSessionResumeState.model_validate_json(
        state_file.read_text(encoding="utf-8")
    )
    assert resumed.reference_number == "batch-ref"


def test_batch_upload_sends_the_stored_parts_to_a_resumed_session(
    runner, tmp_path
) -> None:
    batch = prepared_batch()
    artifact = tmp_path / "prepared"
    _ = write_prepared_batch(artifact, batch)
    state_file = tmp_path / "retry-state.json"
    _ = state_file.write_text(batch_state().to_json(indent=2), encoding="utf-8")

    session = FakeService(resume_state=batch_state("retry-ref"), upload_parts=None)
    auth_service = _auth(FakeService(), session)
    opened: list[dict[str, Any]] = []
    auth_service.batch_session = lambda **kwargs: (opened.append(kwargs), session)[1]
    runtime = fake_runtime(auth=auth_service)

    result = payload(
        runner.invoke(
            app,
            cli_args(
                "batch",
                "upload",
                "--prepared",
                str(artifact),
                "--state-file",
                str(state_file),
            ),
            obj=runtime,
        )
    )

    assert result["state"]["reference_number"] == "retry-ref"
    assert [name for name, _, _ in session.calls] == ["get_status", "upload_parts", "resume_state"]
    assert opened[0]["prepared_batch"].recovery_digest() == batch.recovery_digest()
    assert opened[0]["state"].reference_number == "batch-ref"


def test_batch_upload_reports_an_artifact_that_does_not_fit_the_session(
    runner, tmp_path
) -> None:
    artifact = tmp_path / "prepared"
    _ = write_prepared_batch(artifact, prepared_batch())
    (artifact / PARTS_DIR / "part-0001.bin").write_bytes(b"x" * len(PREPARED_PARTS[0]))
    state_file = tmp_path / "retry-state.json"
    _ = state_file.write_text(batch_state().to_json(indent=2), encoding="utf-8")

    runtime = fake_runtime(auth=_auth(FakeService(), FakeService()))
    result = runner.invoke(
        app,
        cli_args(
            "batch",
            "upload",
            "--prepared",
            str(artifact),
            "--state-file",
            str(state_file),
        ),
        obj=runtime,
    )

    assert result.exit_code == 1
    assert "no longer match the package" in plain(result.output)


@pytest.mark.parametrize("missing", ["--prepared", "--state-file"])
def test_batch_upload_needs_the_artifact_and_the_session_state(
    runner, tmp_path, missing: str
) -> None:
    artifact = tmp_path / "prepared"
    _ = write_prepared_batch(artifact, prepared_batch())
    state_file = tmp_path / "retry-state.json"
    _ = state_file.write_text(batch_state().to_json(indent=2), encoding="utf-8")

    args = {"--prepared": ["--state-file", str(state_file)]}.get(missing) or [
        "--prepared",
        str(artifact),
    ]
    runtime = fake_runtime(auth=_auth(FakeService(), FakeService()))
    result = runner.invoke(app, cli_args("batch", "upload", *args), obj=runtime)

    assert result.exit_code == 2
    assert missing in plain(result.output)


def test_all_in_one_submit_failure_points_at_prepare(runner, tmp_path) -> None:
    """With no artifact to re-upload, the hint says what to build first."""

    invoice = tmp_path / "invoice.xml"
    invoice.write_text("<invoice/>", encoding="utf-8")
    batch_service = FakeService(submit=_upload_error(prepared_batch()))
    runtime = fake_runtime(auth=_auth(batch_service, FakeService()))

    result = runner.invoke(app, cli_args("batch", "submit", str(invoice)), obj=runtime)

    assert result.exit_code == 1
    assert "batch prepare --out DIR" in result.output


def test_batch_upload_reports_a_second_rejected_upload(runner, tmp_path) -> None:
    batch = prepared_batch()
    artifact = tmp_path / "prepared"
    _ = write_prepared_batch(artifact, batch)
    state_file = tmp_path / "retry-state.json"
    _ = state_file.write_text(batch_state().to_json(indent=2), encoding="utf-8")

    session = FakeService(upload_parts=_upload_error(batch))
    runtime = fake_runtime(auth=_auth(FakeService(), session))

    result = runner.invoke(
        app,
        cli_args(
            "batch",
            "upload",
            "--prepared",
            str(artifact),
            "--state-file",
            str(state_file),
        ),
        obj=runtime,
    )

    assert result.exit_code == 1
    assert "External storage upload failed" in result.output
    assert "batch upload --prepared" in result.output


def test_batch_prepare_reports_the_artifact_in_plain_text(runner, tmp_path) -> None:
    batch = prepared_batch()
    runtime = fake_runtime(auth=_auth(FakeService(prepare=batch), FakeService()))

    invoice = tmp_path / "invoice.xml"
    invoice.write_text("<invoice/>", encoding="utf-8")
    artifact = tmp_path / "prepared"
    result = runner.invoke(
        app,
        ["--no-config", "batch", "prepare", str(invoice), "--out", str(artifact)],
        obj=runtime,
    )

    assert result.exit_code == 0, result.output
    assert f"path: {artifact}" in result.output
    assert f"digest: {batch.recovery_digest()}" in result.output
    assert "invoices: 2" in result.output


def test_batch_upload_rejects_state_it_cannot_resume(runner, tmp_path) -> None:
    artifact = tmp_path / "prepared"
    _ = write_prepared_batch(artifact, prepared_batch())
    state_file = tmp_path / "retry-state.json"
    _ = state_file.write_text('{"reference_number": "batch-ref"}', encoding="utf-8")

    runtime = fake_runtime(auth=_auth(FakeService(), FakeService()))
    result = runner.invoke(
        app,
        cli_args(
            "batch",
            "upload",
            "--prepared",
            str(artifact),
            "--state-file",
            str(state_file),
        ),
        obj=runtime,
    )

    assert result.exit_code == 1
    assert "not hold resumable" in result.output
    assert "batch submit" in result.output
