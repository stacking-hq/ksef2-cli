"""Factories and loaders for SDK models used by multiple commands."""

from __future__ import annotations

import base64
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ksef2_cli.io import _read_json
from ksef2_cli.parsing import _parse_form_schema

if TYPE_CHECKING:
    from ksef2.domain.models.invoices import ExportHandle


def _export_handle_to_dict(handle: ExportHandle) -> dict[str, str]:
    return {
        "reference_number": handle.reference_number,
        "aes_key": base64.b64encode(handle.aes_key).decode("ascii"),
        "iv": base64.b64encode(handle.iv).decode("ascii"),
    }


def _load_export_handle(path: Path) -> Any:
    from ksef2.domain.models.invoices import ExportHandle

    data = _read_json(path)
    return ExportHandle(
        reference_number=data["reference_number"],
        aes_key=base64.b64decode(data["aes_key"]),
        iv=base64.b64decode(data["iv"]),
    )


def _build_invoice_filter(
    *,
    role: str,
    date_type: str,
    date_from: str,
    date_to: str | None,
    amount_type: str,
    currency_codes: list[str],
    invoice_types: list[str],
    seller_nip: str | None,
    buyer_nip: str | None,
    buyer_vat_ue: str | None,
    buyer_other_id: str | None,
    invoice_number: str | None,
    ksef_number: str | None,
    amount_min: float | None,
    amount_max: float | None,
    invoice_schema: str | None,
    invoicing_mode: str | None,
    has_attachment: bool | None,
    is_self_invoicing: bool | None,
) -> Any:
    from ksef2.domain.models.invoices import InvoicesFilter

    payload: dict[str, Any] = {
        "role": role,
        "date_type": date_type,
        "date_from": date_from,
        "amount_type": amount_type,
    }
    optional_values = {
        "date_to": date_to,
        "seller_nip": seller_nip,
        "buyer_nip": buyer_nip,
        "buyer_vat_ue": buyer_vat_ue,
        "buyer_other_id": buyer_other_id,
        "invoice_number": invoice_number,
        "ksef_number": ksef_number,
        "amount_min": amount_min,
        "amount_max": amount_max,
        "invoicing_mode": invoicing_mode,
        "has_attachment": has_attachment,
        "is_self_invoicing": is_self_invoicing,
    }
    payload.update({key: value for key, value in optional_values.items() if value is not None})
    if currency_codes:
        payload["currency_codes"] = currency_codes
    if invoice_types:
        payload["invoice_types"] = invoice_types
    if invoice_schema:
        payload["invoice_schema"] = _parse_form_schema(invoice_schema)
    return InvoicesFilter(**payload)


def _invoice_metadata_params(page_size: int, page_offset: int, sort_order: str) -> Any:
    from ksef2.domain.models.pagination import InvoiceMetadataParams

    return InvoiceMetadataParams(
        page_size=page_size,
        page_offset=page_offset,
        sort_order=sort_order,
    )


def _offset_params(page_size: int, page_offset: int) -> Any:
    from ksef2.domain.models.pagination import OffsetPaginationParams

    return OffsetPaginationParams(page_size=page_size, page_offset=page_offset)


def _state_from_file(path: Path) -> Any:
    from ksef2.domain.models.session import OnlineSessionState

    return OnlineSessionState.model_validate(_read_json(path))


def _batch_state_from_file(path: Path) -> Any:
    from ksef2.domain.models.batch import BatchSessionState

    return BatchSessionState.model_validate(_read_json(path))


def _batch_session_ref(reference: str | None, state_file: Path | None) -> Any:
    if reference and state_file:
        raise ValueError("Use either --reference or --state-file, not both.")
    if reference:
        return reference
    if state_file:
        return _batch_state_from_file(state_file)
    raise ValueError("Provide --reference or --state-file.")
