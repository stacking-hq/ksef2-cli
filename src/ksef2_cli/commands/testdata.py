"""TEST-environment data management command group."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Annotated, Any

import typer
from pydantic import BaseModel

from ksef2_cli.config import FORM_SCHEMA_NAMES
from ksef2_cli.context import create_client, run_command
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

app = typer.Typer(help='Manage TEST-environment test data.')


@app.command("create-subject")
def testdata_create_subject(
    ctx: typer.Context,
    nip: Annotated[str, typer.Option("--nip")],
    subject_type: Annotated[str, typer.Option("--type", help="enforcement_authority, vat_group, or jst.")],
    description: Annotated[str, typer.Option("--description")],
    subunit: Annotated[
        list[str],
        typer.Option("--subunit", help="Subunit as NIP:description. Repeat for multiple."),
    ] = [],
) -> None:
    """Create a TEST subject."""

    def operation() -> dict[str, str]:
        from ksef2.domain.models.testdata import SubUnit

        subunits = []
        for item in subunit:
            try:
                subject_nip, subunit_description = item.split(":", 1)
            except ValueError as exc:
                raise ValueError("--subunit must use NIP:description format.") from exc
            subunits.append(SubUnit(subject_nip=subject_nip, description=subunit_description))
        with create_client(ctx) as client:
            client.testdata.create_subject(
                nip=nip,
                subject_type=subject_type,
                description=description,
                subunits=subunits or None,
            )
        return {"nip": nip, "created": "true"}

    _render(ctx, run_command(ctx, operation), title="Created Test Subject")


@app.command("delete-subject")
def testdata_delete_subject(
    ctx: typer.Context,
    nip: Annotated[str, typer.Option("--nip")],
) -> None:
    """Delete a TEST subject."""

    def operation() -> dict[str, str]:
        with create_client(ctx) as client:
            client.testdata.delete_subject(nip=nip)
        return {"nip": nip, "deleted": "true"}

    _render(ctx, run_command(ctx, operation), title="Deleted Test Subject")


@app.command("create-person")
def testdata_create_person(
    ctx: typer.Context,
    nip: Annotated[str, typer.Option("--nip")],
    pesel: Annotated[str, typer.Option("--pesel")],
    description: Annotated[str, typer.Option("--description")],
    is_bailiff: Annotated[bool, typer.Option("--bailiff")] = False,
    is_deceased: Annotated[bool, typer.Option("--deceased")] = False,
) -> None:
    """Create a TEST person."""

    def operation() -> dict[str, str]:
        with create_client(ctx) as client:
            client.testdata.create_person(
                nip=nip,
                pesel=pesel,
                description=description,
                is_bailiff=is_bailiff,
                is_deceased=is_deceased,
            )
        return {"nip": nip, "pesel": pesel, "created": "true"}

    _render(ctx, run_command(ctx, operation), title="Created Test Person")


@app.command("delete-person")
def testdata_delete_person(
    ctx: typer.Context,
    nip: Annotated[str, typer.Option("--nip")],
) -> None:
    """Delete a TEST person."""

    def operation() -> dict[str, str]:
        with create_client(ctx) as client:
            client.testdata.delete_person(nip=nip)
        return {"nip": nip, "deleted": "true"}

    _render(ctx, run_command(ctx, operation), title="Deleted Test Person")


@app.command("enable-attachments")
def testdata_enable_attachments(
    ctx: typer.Context,
    nip: Annotated[str, typer.Option("--nip")],
) -> None:
    """Enable attachments for a TEST subject."""

    def operation() -> dict[str, str]:
        with create_client(ctx) as client:
            client.testdata.enable_attachments(nip=nip)
        return {"nip": nip, "attachments": "enabled"}

    _render(ctx, run_command(ctx, operation), title="Enabled Attachments")


@app.command("revoke-attachments")
def testdata_revoke_attachments(
    ctx: typer.Context,
    nip: Annotated[str, typer.Option("--nip")],
    expected_end_date: Annotated[str | None, typer.Option("--expected-end-date", help="YYYY-MM-DD.")] = None,
) -> None:
    """Revoke attachments for a TEST subject."""

    def operation() -> dict[str, str | None]:
        parsed_date = date.fromisoformat(expected_end_date) if expected_end_date else None
        with create_client(ctx) as client:
            client.testdata.revoke_attachments(nip=nip, expected_end_date=parsed_date)
        return {"nip": nip, "expected_end_date": expected_end_date, "attachments": "revoked"}

    _render(ctx, run_command(ctx, operation), title="Revoked Attachments")


@app.command("block-context")
def testdata_block_context(
    ctx: typer.Context,
    context_type: Annotated[str, typer.Option("--context-type")],
    context_value: Annotated[str, typer.Option("--context-value")],
) -> None:
    """Block a TEST auth context."""

    def operation() -> dict[str, str]:
        from ksef2.domain.models.testdata import AuthContextIdentifier

        context = AuthContextIdentifier(type=context_type, value=context_value)
        with create_client(ctx) as client:
            client.testdata.block_context(context=context)
        return {"context_type": context_type, "context_value": context_value, "blocked": "true"}

    _render(ctx, run_command(ctx, operation), title="Blocked Context")


@app.command("unblock-context")
def testdata_unblock_context(
    ctx: typer.Context,
    context_type: Annotated[str, typer.Option("--context-type")],
    context_value: Annotated[str, typer.Option("--context-value")],
) -> None:
    """Unblock a TEST auth context."""

    def operation() -> dict[str, str]:
        from ksef2.domain.models.testdata import AuthContextIdentifier

        context = AuthContextIdentifier(type=context_type, value=context_value)
        with create_client(ctx) as client:
            client.testdata.unblock_context(context=context)
        return {"context_type": context_type, "context_value": context_value, "blocked": "false"}

    _render(ctx, run_command(ctx, operation), title="Unblocked Context")


@app.command("grant-permissions")
def testdata_grant_permissions(
    ctx: typer.Context,
    grant_to_type: Annotated[str, typer.Option("--grant-to-type")],
    grant_to_value: Annotated[str, typer.Option("--grant-to-value")],
    context_type: Annotated[str, typer.Option("--context-type")],
    context_value: Annotated[str, typer.Option("--context-value")],
    permission: Annotated[list[str], typer.Option("--permission", help="Permission type. Repeat.")] = [],
    description: Annotated[str, typer.Option("--description")] = "Granted by ksef2-cli",
) -> None:
    """Grant TEST permissions."""

    def operation() -> dict[str, Any]:
        if not permission:
            raise ValueError("At least one --permission is required.")
        from ksef2.domain.models.testdata import Identifier, Permission

        permissions = [Permission(type=item, description=description) for item in permission]
        grant_to = Identifier(type=grant_to_type, value=grant_to_value)
        in_context_of = Identifier(type=context_type, value=context_value)
        with create_client(ctx) as client:
            client.testdata.grant_permissions(
                permissions=permissions,
                grant_to=grant_to,
                in_context_of=in_context_of,
            )
        return {"grant_to": grant_to, "in_context_of": in_context_of, "permissions": permissions}

    _render(ctx, run_command(ctx, operation), title="Granted Test Permissions", items_key="permissions")


@app.command("revoke-permissions")
def testdata_revoke_permissions(
    ctx: typer.Context,
    revoke_from_type: Annotated[str, typer.Option("--revoke-from-type")],
    revoke_from_value: Annotated[str, typer.Option("--revoke-from-value")],
    context_type: Annotated[str, typer.Option("--context-type")],
    context_value: Annotated[str, typer.Option("--context-value")],
) -> None:
    """Revoke TEST permissions."""

    def operation() -> dict[str, Any]:
        from ksef2.domain.models.testdata import Identifier

        revoke_from = Identifier(type=revoke_from_type, value=revoke_from_value)
        in_context_of = Identifier(type=context_type, value=context_value)
        with create_client(ctx) as client:
            client.testdata.revoke_permissions(
                revoke_from=revoke_from,
                in_context_of=in_context_of,
            )
        return {"revoke_from": revoke_from, "in_context_of": in_context_of, "revoked": "true"}

    _render(ctx, run_command(ctx, operation), title="Revoked Test Permissions")
