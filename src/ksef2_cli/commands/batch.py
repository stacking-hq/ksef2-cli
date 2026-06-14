"""Batch session command group."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any

import typer

from ksef2_cli.config import FORM_SCHEMA_NAMES
from ksef2_cli.context import run_authenticated, run_and_render
from ksef2_cli.io import _write_json
from ksef2_cli.parsing import _parse_form_schema
from ksef2_cli.sdk_models import _batch_session_ref

app = typer.Typer(help='Submit and inspect batch invoice sessions.')


@app.command("submit")
def batch_submit(
    ctx: typer.Context,
    invoice_paths: Annotated[list[Path], typer.Argument(exists=True, dir_okay=False)],
    state_file: Annotated[Path | None, typer.Option("--state-file", dir_okay=False)] = None,
    form: Annotated[str, typer.Option("--form", help=f"Form schema: {FORM_SCHEMA_NAMES}.")] = "FA3",
    offline_mode: Annotated[bool, typer.Option("--offline", help="Declare offline invoicing mode.")] = False,
    max_part_size: Annotated[int | None, typer.Option("--max-part-size", min=1)] = None,
    wait: Annotated[bool, typer.Option("--wait", help="Wait for batch processing completion.")] = False,
    timeout: Annotated[float, typer.Option("--timeout", min=1.0)] = 120.0,
    poll_interval: Annotated[float, typer.Option("--poll-interval", min=0.1)] = 2.0,
) -> None:
    """Prepare, upload, close, and optionally wait for a batch session."""

    def operation() -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "invoice_paths": invoice_paths,
            "form_code": _parse_form_schema(form),
            "offline_mode": offline_mode,
        }
        if max_part_size is not None:
            kwargs["max_part_size"] = max_part_size

        def submit_batch(auth: Any) -> tuple[Any, Any]:
            prepared = auth.batch.prepare_batch_from_paths(**kwargs)
            state = auth.batch.submit_prepared_batch(prepared_batch=prepared)
            status = (
                auth.batch.wait_for_completion(
                    session=state,
                    timeout=timeout,
                    poll_interval=poll_interval,
                )
                if wait
                else None
            )
            return state, status

        state, status = run_authenticated(ctx, submit_batch)
        if state_file:
            _write_json(state_file, state)
        return {"state_file": str(state_file) if state_file else None, "state": state, "status": status}

    run_and_render(ctx, operation)


@app.command("status")
def batch_status(
    ctx: typer.Context,
    reference: Annotated[str | None, typer.Option("--reference")] = None,
    state_file: Annotated[Path | None, typer.Option("--state-file", exists=True, dir_okay=False)] = None,
    wait: Annotated[bool, typer.Option("--wait", help="Wait for completion.")] = False,
    timeout: Annotated[float, typer.Option("--timeout", min=1.0)] = 120.0,
    poll_interval: Annotated[float, typer.Option("--poll-interval", min=0.1)] = 2.0,
) -> None:
    """Fetch or wait for batch session status."""

    def operation() -> Any:
        session_ref = _batch_session_ref(reference, state_file)

        def get_batch_status(auth: Any) -> Any:
            if wait:
                return auth.batch.wait_for_completion(
                    session=session_ref,
                    timeout=timeout,
                    poll_interval=poll_interval,
                )
            return auth.batch.get_status(session=session_ref)

        return run_authenticated(ctx, get_batch_status)

    run_and_render(ctx, operation)


@app.command("list")
def batch_list(
    ctx: typer.Context,
    reference: Annotated[str | None, typer.Option("--reference")] = None,
    state_file: Annotated[Path | None, typer.Option("--state-file", exists=True, dir_okay=False)] = None,
    page_size: Annotated[int, typer.Option("--page-size", min=10, max=1000)] = 10,
    continuation_token: Annotated[str | None, typer.Option("--continuation-token")] = None,
    failed: Annotated[bool, typer.Option("--failed", help="List failed invoices only.")] = False,
) -> None:
    """List invoices submitted in a batch session."""

    def operation() -> Any:
        session_ref = _batch_session_ref(reference, state_file)

        def list_batch_invoices(auth: Any) -> Any:
            if failed:
                return auth.batch.list_failed_invoices(
                    session=session_ref,
                    page_size=page_size,
                    continuation_token=continuation_token,
                )
            return auth.batch.list_invoices(
                session=session_ref,
                page_size=page_size,
                continuation_token=continuation_token,
            )

        return run_authenticated(ctx, list_batch_invoices)

    run_and_render(ctx, operation, items_key="invoices")


@app.command("upo")
def batch_upo(
    ctx: typer.Context,
    upo_reference: Annotated[str, typer.Option("--upo-reference")],
    output_file: Annotated[Path, typer.Option("--out", "-o", dir_okay=False)],
    reference: Annotated[str | None, typer.Option("--reference")] = None,
    state_file: Annotated[Path | None, typer.Option("--state-file", exists=True, dir_okay=False)] = None,
) -> None:
    """Download a collective UPO page for a batch session."""

    def operation() -> dict[str, Any]:
        session_ref = _batch_session_ref(reference, state_file)
        content = run_authenticated(
            ctx,
            lambda auth: auth.batch.get_upo(session=session_ref, upo_reference_number=upo_reference),
        )
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_bytes(content)
        return {"path": str(output_file), "bytes": len(content)}

    run_and_render(ctx, operation)
