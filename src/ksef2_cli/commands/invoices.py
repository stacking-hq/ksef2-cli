"""Invoice query, download, and export command group."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Annotated, Any

import typer
from pydantic import BaseModel

from ksef2_cli.config import FORM_SCHEMA_NAMES
from ksef2_cli.context import get_authenticated_client, run_command
from ksef2_cli.io import _read_model, _write_json
from ksef2_cli.parsing import _parse_form_schema, _parse_optional_bool, _safe_filename
from ksef2_cli.rendering import _render
from ksef2_cli.sdk_models import (
    _batch_session_ref,
    _build_invoice_filter,
    _export_handle_to_dict,
    _invoice_metadata_params,
    _load_export_handle,
    _offset_params,
    _state_from_file,
)

app = typer.Typer(help='Query, download, and export invoices.')


@app.command("metadata")
def invoices_metadata(
    ctx: typer.Context,
    date_from: Annotated[str, typer.Option("--date-from", help="Start datetime/date, ISO format.")],
    date_to: Annotated[str | None, typer.Option("--date-to", help="End datetime/date, ISO format.")] = None,
    role: Annotated[str, typer.Option("--role", help="buyer, seller, third_subject, authorized_subject.")] = "seller",
    date_type: Annotated[str, typer.Option("--date-type", help="issue_date, invoicing_date, permanent_storage.")] = "issue_date",
    amount_type: Annotated[str, typer.Option("--amount-type", help="brutto, netto, or vat.")] = "brutto",
    currency: Annotated[list[str], typer.Option("--currency", help="Currency code. Repeat for multiple.")] = [],
    invoice_type: Annotated[list[str], typer.Option("--invoice-type", help="Invoice type. Repeat for multiple.")] = [],
    seller_nip: Annotated[str | None, typer.Option("--seller-nip")] = None,
    buyer_nip: Annotated[str | None, typer.Option("--buyer-nip")] = None,
    buyer_vat_ue: Annotated[str | None, typer.Option("--buyer-vat-ue")] = None,
    buyer_other_id: Annotated[str | None, typer.Option("--buyer-other-id")] = None,
    invoice_number: Annotated[str | None, typer.Option("--invoice-number")] = None,
    ksef_number: Annotated[str | None, typer.Option("--ksef-number")] = None,
    amount_min: Annotated[float | None, typer.Option("--amount-min")] = None,
    amount_max: Annotated[float | None, typer.Option("--amount-max")] = None,
    form: Annotated[str | None, typer.Option("--form", help=f"Form schema: {FORM_SCHEMA_NAMES}.")] = None,
    invoicing_mode: Annotated[str | None, typer.Option("--invoicing-mode", help="online or offline.")] = None,
    attachment: Annotated[
        str | None,
        typer.Option("--attachment", help="Filter by attachment presence: yes or no."),
    ] = None,
    self_invoicing: Annotated[
        str | None,
        typer.Option("--self-invoicing", help="Filter by self-invoicing flag: yes or no."),
    ] = None,
    page_size: Annotated[int, typer.Option("--page-size", min=10, max=250)] = 10,
    page_offset: Annotated[int, typer.Option("--page-offset", min=0)] = 0,
    sort_order: Annotated[str, typer.Option("--sort-order", help="asc or desc.")] = "asc",
    all_pages: Annotated[bool, typer.Option("--all", help="Fetch all metadata items.")] = False,
) -> None:
    """Query invoice metadata."""

    def operation() -> Any:
        filters = _build_invoice_filter(
            role=role,
            date_type=date_type,
            date_from=date_from,
            date_to=date_to,
            amount_type=amount_type,
            currency_codes=currency,
            invoice_types=invoice_type,
            seller_nip=seller_nip,
            buyer_nip=buyer_nip,
            buyer_vat_ue=buyer_vat_ue,
            buyer_other_id=buyer_other_id,
            invoice_number=invoice_number,
            ksef_number=ksef_number,
            amount_min=amount_min,
            amount_max=amount_max,
            invoice_schema=form,
            invoicing_mode=invoicing_mode,
            has_attachment=_parse_optional_bool(attachment, option_name="--attachment"),
            is_self_invoicing=_parse_optional_bool(self_invoicing, option_name="--self-invoicing"),
        )
        params = _invoice_metadata_params(page_size, page_offset, sort_order)
        runtime = get_authenticated_client(ctx)
        client, auth = runtime.client, runtime.auth
        with client:
            if all_pages:
                return list(auth.invoices.all_metadata(filters=filters, params=params))
            return auth.invoices.query_metadata(filters=filters, params=params)

    _render(
        ctx,
        run_command(ctx, operation),
        title="Invoices",
        items_key="invoices",
        fields=["ksef_number", "invoice_number", "issue_date", "seller", "buyer", "gross_amount", "currency"],
    )


@app.command("download")
def invoices_download(
    ctx: typer.Context,
    ksef_number: Annotated[str, typer.Option("--ksef-number", help="KSeF invoice number.")],
    output_file: Annotated[
        Path | None,
        typer.Option("--out", "-o", dir_okay=False, help="Target XML file."),
    ] = None,
    wait: Annotated[bool, typer.Option("--wait", help="Poll until the invoice can be downloaded.")] = False,
    timeout: Annotated[float, typer.Option("--timeout", min=1.0)] = 120.0,
    poll_interval: Annotated[float, typer.Option("--poll-interval", min=0.1)] = 2.0,
) -> None:
    """Download processed invoice XML by KSeF number."""

    def operation() -> dict[str, Any]:
        runtime = get_authenticated_client(ctx)
        client, auth = runtime.client, runtime.auth
        with client:
            if wait:
                content = auth.invoices.wait_for_invoice_download(
                    ksef_number=ksef_number,
                    timeout=timeout,
                    poll_interval=poll_interval,
                )
            else:
                content = auth.invoices.download_invoice(ksef_number=ksef_number)
        target = output_file or Path(_safe_filename(ksef_number, ".xml"))
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        return {"path": str(target), "bytes": len(content)}

    _render(ctx, run_command(ctx, operation), title="Downloaded Invoice")


@app.command("export")
def invoices_export(
    ctx: typer.Context,
    date_from: Annotated[str, typer.Option("--date-from", help="Start datetime/date, ISO format.")],
    date_to: Annotated[str | None, typer.Option("--date-to", help="End datetime/date, ISO format.")] = None,
    role: Annotated[str, typer.Option("--role")] = "seller",
    date_type: Annotated[str, typer.Option("--date-type")] = "issue_date",
    amount_type: Annotated[str, typer.Option("--amount-type")] = "brutto",
    only_metadata: Annotated[bool, typer.Option("--only-metadata", help="Export only metadata.")] = False,
    compression_type: Annotated[str | None, typer.Option("--compression-type")] = None,
    handle_file: Annotated[
        Path | None,
        typer.Option("--handle-file", dir_okay=False, help="Save export handle needed for later fetch."),
    ] = None,
) -> None:
    """Schedule an invoice export and print/save the decryption handle."""

    def operation() -> dict[str, str]:
        filters = _build_invoice_filter(
            role=role,
            date_type=date_type,
            date_from=date_from,
            date_to=date_to,
            amount_type=amount_type,
            currency_codes=[],
            invoice_types=[],
            seller_nip=None,
            buyer_nip=None,
            buyer_vat_ue=None,
            buyer_other_id=None,
            invoice_number=None,
            ksef_number=None,
            amount_min=None,
            amount_max=None,
            invoice_schema=None,
            invoicing_mode=None,
            has_attachment=None,
            is_self_invoicing=None,
        )
        runtime = get_authenticated_client(ctx)
        client, auth = runtime.client, runtime.auth
        with client:
            handle = auth.invoices.schedule_export(
                filters=filters,
                only_metadata=only_metadata,
                compression_type=compression_type,
            )
        payload = _export_handle_to_dict(handle)
        if handle_file:
            _write_json(handle_file, payload)
            payload["handle_file"] = str(handle_file)
        return payload

    _render(ctx, run_command(ctx, operation), title="Export Handle")


@app.command("export-status")
def invoices_export_status(
    ctx: typer.Context,
    reference_number: Annotated[str, typer.Option("--reference", help="Export reference number.")],
) -> None:
    """Fetch invoice export status."""

    def operation() -> Any:
        runtime = get_authenticated_client(ctx)
        client, auth = runtime.client, runtime.auth
        with client:
            return auth.invoices.get_export_status(reference_number=reference_number)

    _render(ctx, run_command(ctx, operation), title="Export Status")


@app.command("export-fetch")
def invoices_export_fetch(
    ctx: typer.Context,
    handle_file: Annotated[Path, typer.Option("--handle-file", exists=True, dir_okay=False)],
    output_dir: Annotated[Path, typer.Option("--out-dir", file_okay=False)] = Path("downloads"),
    wait: Annotated[bool, typer.Option("--wait", help="Wait for the export package.")] = False,
    timeout: Annotated[float, typer.Option("--timeout", min=1.0)] = 120.0,
    poll_interval: Annotated[float, typer.Option("--poll-interval", min=0.1)] = 2.0,
) -> None:
    """Fetch and decrypt an export package using a saved export handle."""

    def operation() -> dict[str, Any]:
        handle = _load_export_handle(handle_file)
        runtime = get_authenticated_client(ctx)
        client, auth = runtime.client, runtime.auth
        with client:
            if wait:
                package = auth.invoices.wait_for_export_package(
                    reference_number=handle.reference_number,
                    timeout=timeout,
                    poll_interval=poll_interval,
                )
            else:
                status = auth.invoices.get_export_status(reference_number=handle.reference_number)
                if status.package is None:
                    raise ValueError("Export package is not ready. Re-run with --wait or check export-status.")
                package = status.package
            paths = auth.invoices.fetch_package(
                package=package,
                export=handle,
                target_directory=output_dir,
            )
        return {
            "reference_number": handle.reference_number,
            "paths": [str(path) for path in paths],
        }

    _render(ctx, run_command(ctx, operation), title="Fetched Export", items_key="paths")


@app.command("export-download")
def invoices_export_download(
    ctx: typer.Context,
    date_from: Annotated[str, typer.Option("--date-from", help="Start datetime/date, ISO format.")],
    date_to: Annotated[str | None, typer.Option("--date-to", help="End datetime/date, ISO format.")] = None,
    role: Annotated[str, typer.Option("--role")] = "seller",
    date_type: Annotated[str, typer.Option("--date-type")] = "issue_date",
    amount_type: Annotated[str, typer.Option("--amount-type")] = "brutto",
    output_dir: Annotated[Path, typer.Option("--out-dir", file_okay=False)] = Path("downloads"),
    only_metadata: Annotated[bool, typer.Option("--only-metadata")] = False,
    compression_type: Annotated[str | None, typer.Option("--compression-type")] = None,
    timeout: Annotated[float, typer.Option("--timeout", min=1.0)] = 120.0,
    poll_interval: Annotated[float, typer.Option("--poll-interval", min=0.1)] = 2.0,
    handle_file: Annotated[Path | None, typer.Option("--handle-file", dir_okay=False)] = None,
) -> None:
    """Schedule, wait for, download, and decrypt an invoice export."""

    def operation() -> dict[str, Any]:
        filters = _build_invoice_filter(
            role=role,
            date_type=date_type,
            date_from=date_from,
            date_to=date_to,
            amount_type=amount_type,
            currency_codes=[],
            invoice_types=[],
            seller_nip=None,
            buyer_nip=None,
            buyer_vat_ue=None,
            buyer_other_id=None,
            invoice_number=None,
            ksef_number=None,
            amount_min=None,
            amount_max=None,
            invoice_schema=None,
            invoicing_mode=None,
            has_attachment=None,
            is_self_invoicing=None,
        )
        runtime = get_authenticated_client(ctx)
        client, auth = runtime.client, runtime.auth
        with client:
            handle = auth.invoices.schedule_export(
                filters=filters,
                only_metadata=only_metadata,
                compression_type=compression_type,
            )
            if handle_file:
                _write_json(handle_file, _export_handle_to_dict(handle))
            package = auth.invoices.wait_for_export_package(
                reference_number=handle.reference_number,
                timeout=timeout,
                poll_interval=poll_interval,
            )
            paths = auth.invoices.fetch_package(
                package=package,
                export=handle,
                target_directory=output_dir,
            )
        return {
            "reference_number": handle.reference_number,
            "handle_file": str(handle_file) if handle_file else None,
            "paths": [str(path) for path in paths],
        }

    _render(ctx, run_command(ctx, operation), title="Downloaded Export", items_key="paths")
