"""Online invoice session command group."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any

import typer

from ksef2_cli.config import FORM_SCHEMA_NAMES
from ksef2_cli.context import get_authenticated_client, run_command
from ksef2_cli.io import _write_json
from ksef2_cli.parsing import _parse_form_schema
from ksef2_cli.rendering import _render
from ksef2_cli.sdk_models import (
    _state_from_file,
)

app = typer.Typer(help='Open, resume, and operate online invoice sessions.')


@app.command("open")
def online_open(
    ctx: typer.Context,
    state_file: Annotated[Path | None, typer.Option("--state-file", dir_okay=False)] = None,
    form: Annotated[str, typer.Option("--form", help=f"Form schema: {FORM_SCHEMA_NAMES}.")] = "FA3",
) -> None:
    """Open an online session and optionally save resumable state."""

    def operation() -> Any:
        runtime = get_authenticated_client(ctx)
        client, auth = runtime.client, runtime.auth
        with client:
            session = auth.online_session(form_code=_parse_form_schema(form))
            state = session.get_state()
        if state_file:
            _write_json(state_file, state)
        return {"state_file": str(state_file) if state_file else None, "state": state}

    _render(ctx, run_command(ctx, operation), title="Online Session")


@app.command("send")
def online_send(
    ctx: typer.Context,
    invoice_paths: Annotated[list[Path], typer.Argument(exists=True, dir_okay=False)],
    state_file: Annotated[
        Path | None,
        typer.Option("--state-file", exists=True, dir_okay=False, help="Resume an existing online session."),
    ] = None,
    save_state: Annotated[
        Path | None,
        typer.Option("--save-state", dir_okay=False, help="Save opened/resumed session state."),
    ] = None,
    form: Annotated[str, typer.Option("--form", help=f"Form schema: {FORM_SCHEMA_NAMES}.")] = "FA3",
    wait: Annotated[bool, typer.Option("--wait", help="Wait for each invoice to finish processing.")] = False,
    keep_open: Annotated[bool, typer.Option("--keep-open", help="Leave the session open after sending.")] = False,
    timeout: Annotated[float, typer.Option("--timeout", min=1.0)] = 60.0,
    poll_interval: Annotated[float, typer.Option("--poll-interval", min=0.1)] = 2.0,
) -> None:
    """Send one or more invoice XML files through an online session."""

    def operation() -> dict[str, Any]:
        runtime = get_authenticated_client(ctx)
        client, auth = runtime.client, runtime.auth
        with client:
            if state_file:
                session = auth.resume_online_session(_state_from_file(state_file))
            else:
                session = auth.online_session(form_code=_parse_form_schema(form))
            try:
                results = []
                for invoice_path in invoice_paths:
                    xml = invoice_path.read_bytes()
                    if wait:
                        result = session.send_invoice_and_wait(
                            invoice_xml=xml,
                            timeout=timeout,
                            poll_interval=poll_interval,
                        )
                    else:
                        result = session.send_invoice(invoice_xml=xml)
                    results.append({"file": str(invoice_path), "result": result})
                state = session.get_state()
                if save_state:
                    _write_json(save_state, state)
            finally:
                if not keep_open:
                    session.close()
        return {
            "state_file": str(save_state) if save_state else None,
            "closed": not keep_open,
            "results": results,
        }

    _render(ctx, run_command(ctx, operation), title="Sent Invoices", items_key="results")


@app.command("status")
def online_status(
    ctx: typer.Context,
    state_file: Annotated[Path, typer.Option("--state-file", exists=True, dir_okay=False)],
) -> None:
    """Fetch current status for a resumed online session."""

    def operation() -> Any:
        runtime = get_authenticated_client(ctx)
        client, auth = runtime.client, runtime.auth
        with client:
            return auth.resume_online_session(_state_from_file(state_file)).get_status()

    _render(ctx, run_command(ctx, operation), title="Online Session Status")


@app.command("list")
def online_list(
    ctx: typer.Context,
    state_file: Annotated[Path, typer.Option("--state-file", exists=True, dir_okay=False)],
    page_size: Annotated[int, typer.Option("--page-size", min=10, max=1000)] = 10,
    continuation_token: Annotated[str | None, typer.Option("--continuation-token")] = None,
    failed: Annotated[bool, typer.Option("--failed", help="List failed invoices only.")] = False,
) -> None:
    """List invoices submitted in an online session."""

    def operation() -> Any:
        runtime = get_authenticated_client(ctx)
        client, auth = runtime.client, runtime.auth
        with client:
            session = auth.resume_online_session(_state_from_file(state_file))
            if failed:
                return session.list_failed_invoices(page_size=page_size, continuation_token=continuation_token)
            return session.list_invoices(page_size=page_size, continuation_token=continuation_token)

    _render(
        ctx,
        run_command(ctx, operation),
        title="Session Invoices",
        items_key="invoices",
        fields=["reference_number", "ksef_number", "invoice_number", "status"],
    )


@app.command("invoice-status")
def online_invoice_status(
    ctx: typer.Context,
    state_file: Annotated[Path, typer.Option("--state-file", exists=True, dir_okay=False)],
    invoice_reference: Annotated[str, typer.Option("--invoice-reference")],
    wait: Annotated[bool, typer.Option("--wait", help="Poll until ready.")] = False,
    timeout: Annotated[float, typer.Option("--timeout", min=1.0)] = 60.0,
    poll_interval: Annotated[float, typer.Option("--poll-interval", min=0.1)] = 2.0,
) -> None:
    """Fetch or wait for one invoice status within an online session."""

    def operation() -> Any:
        runtime = get_authenticated_client(ctx)
        client, auth = runtime.client, runtime.auth
        with client:
            session = auth.resume_online_session(_state_from_file(state_file))
            if wait:
                return session.wait_for_invoice_ready(
                    invoice_reference_number=invoice_reference,
                    timeout=timeout,
                    poll_interval=poll_interval,
                )
            return session.get_invoice_status(invoice_reference_number=invoice_reference)

    _render(ctx, run_command(ctx, operation), title="Invoice Status")


@app.command("upo")
def online_upo(
    ctx: typer.Context,
    state_file: Annotated[Path, typer.Option("--state-file", exists=True, dir_okay=False)],
    output_file: Annotated[Path, typer.Option("--out", "-o", dir_okay=False)],
    invoice_reference: Annotated[str | None, typer.Option("--invoice-reference")] = None,
    ksef_number: Annotated[str | None, typer.Option("--ksef-number")] = None,
) -> None:
    """Download invoice UPO by invoice reference or KSeF number."""

    def operation() -> dict[str, Any]:
        if bool(invoice_reference) == bool(ksef_number):
            raise ValueError("Provide exactly one of --invoice-reference or --ksef-number.")
        runtime = get_authenticated_client(ctx)
        client, auth = runtime.client, runtime.auth
        with client:
            session = auth.resume_online_session(_state_from_file(state_file))
            if invoice_reference:
                content = session.get_invoice_upo_by_reference(invoice_reference_number=invoice_reference)
            else:
                assert ksef_number is not None
                content = session.get_invoice_upo_by_ksef_number(ksef_number=ksef_number)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_bytes(content)
        return {"path": str(output_file), "bytes": len(content)}

    _render(ctx, run_command(ctx, operation), title="Downloaded UPO")


@app.command("close")
def online_close(
    ctx: typer.Context,
    state_file: Annotated[Path, typer.Option("--state-file", exists=True, dir_okay=False)],
) -> None:
    """Close a resumed online session."""

    def operation() -> dict[str, str]:
        runtime = get_authenticated_client(ctx)
        client, auth = runtime.client, runtime.auth
        state = _state_from_file(state_file)
        with client:
            auth.resume_online_session(state).close()
        return {"reference_number": state.reference_number, "closed": "true"}

    _render(ctx, run_command(ctx, operation), title="Closed Online Session")
