"""Permission grant, query, and revoke command group."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any

import typer
from pydantic import BaseModel

from ksef2_cli.context import read_model, run_authenticated, run_command
from ksef2_cli.rendering import _render
from ksef2_cli.sdk_models import _offset_params

app = typer.Typer(help='Grant, query, and revoke permissions.')


@app.command("attachment-status")
def permissions_attachment_status(ctx: typer.Context) -> None:
    """Read attachment permission status."""

    def operation() -> Any:
        return run_authenticated(ctx, lambda auth: auth.permissions.get_attachment_permission_status())

    _render(ctx, run_command(ctx, operation))


@app.command("operation-status")
def permissions_operation_status(
    ctx: typer.Context,
    reference_number: Annotated[str, typer.Option("--reference")],
) -> None:
    """Read async permission operation status."""

    def operation() -> Any:
        return run_authenticated(
            ctx,
            lambda auth: auth.permissions.get_operation_status(reference_number=reference_number),
        )

    _render(ctx, run_command(ctx, operation))


@app.command("entity-roles")
def permissions_entity_roles(
    ctx: typer.Context,
    page_size: Annotated[int, typer.Option("--page-size", min=10, max=100)] = 10,
    page_offset: Annotated[int, typer.Option("--page-offset", min=0)] = 0,
) -> None:
    """List roles assigned to the authenticated entity."""

    def operation() -> Any:
        return run_authenticated(
            ctx,
            lambda auth: auth.permissions.get_entity_roles(params=_offset_params(page_size, page_offset)),
        )

    _render(ctx, run_command(ctx, operation), items_key="roles")


@app.command("grant-person")
def permissions_grant_person(
    ctx: typer.Context,
    subject_type: Annotated[str, typer.Option("--subject-type", help="nip, pesel, or fingerprint.")],
    subject_value: Annotated[str, typer.Option("--subject-value")],
    first_name: Annotated[str, typer.Option("--first-name")],
    last_name: Annotated[str, typer.Option("--last-name")],
    description: Annotated[str, typer.Option("--description")],
    permission: Annotated[list[str], typer.Option("--permission", help="Permission scope. Repeat.")] = [],
) -> None:
    """Grant permissions directly to a person."""

    def operation() -> Any:
        if not permission:
            raise ValueError("At least one --permission is required.")
        return run_authenticated(
            ctx,
            lambda auth: auth.permissions.grant_person(
                subject_type=subject_type,
                subject_value=subject_value,
                permissions=permission,
                description=description,
                first_name=first_name,
                last_name=last_name,
            ),
        )

    _render(ctx, run_command(ctx, operation))


@app.command("grant-entity")
def permissions_grant_entity(
    ctx: typer.Context,
    subject_value: Annotated[str, typer.Option("--subject-value", help="Entity NIP.")],
    entity_name: Annotated[str, typer.Option("--entity-name")],
    description: Annotated[str, typer.Option("--description")],
    permission: Annotated[list[str], typer.Option("--permission", help="invoice_read or invoice_write. Repeat.")] = [],
    can_delegate: Annotated[bool, typer.Option("--can-delegate", help="Apply delegation to all permission scopes.")] = False,
) -> None:
    """Grant permissions to an entity."""

    def operation() -> Any:
        if not permission:
            raise ValueError("At least one --permission is required.")
        from ksef2.domain.models.permissions import EntityPermission

        permissions = [EntityPermission(type=item, can_delegate=can_delegate) for item in permission]
        return run_authenticated(
            ctx,
            lambda auth: auth.permissions.grant_entity(
                subject_value=subject_value,
                permissions=permissions,
                description=description,
                entity_name=entity_name,
            ),
        )

    _render(ctx, run_command(ctx, operation))


@app.command("grant-authorization")
def permissions_grant_authorization(
    ctx: typer.Context,
    subject_type: Annotated[str, typer.Option("--subject-type", help="nip or peppol_id.")],
    subject_value: Annotated[str, typer.Option("--subject-value")],
    permission: Annotated[str, typer.Option("--permission")],
    entity_name: Annotated[str, typer.Option("--entity-name")],
    description: Annotated[str, typer.Option("--description")],
) -> None:
    """Grant invoice authorization rights to an entity."""

    def operation() -> Any:
        return run_authenticated(
            ctx,
            lambda auth: auth.permissions.grant_authorization(
                subject_type=subject_type,
                subject_value=subject_value,
                permission=permission,
                description=description,
                entity_name=entity_name,
            ),
        )

    _render(ctx, run_command(ctx, operation))


@app.command("grant-indirect")
def permissions_grant_indirect(
    ctx: typer.Context,
    subject_type: Annotated[str, typer.Option("--subject-type", help="nip, pesel, or fingerprint.")],
    subject_value: Annotated[str, typer.Option("--subject-value")],
    first_name: Annotated[str, typer.Option("--first-name")],
    last_name: Annotated[str, typer.Option("--last-name")],
    description: Annotated[str, typer.Option("--description")],
    permission: Annotated[list[str], typer.Option("--permission", help="invoice_read or invoice_write. Repeat.")] = [],
    target_type: Annotated[str | None, typer.Option("--target-type")] = None,
    target_value: Annotated[str | None, typer.Option("--target-value")] = None,
) -> None:
    """Grant indirect permissions."""

    def operation() -> Any:
        if not permission:
            raise ValueError("At least one --permission is required.")
        return run_authenticated(
            ctx,
            lambda auth: auth.permissions.grant_indirect(
                subject_type=subject_type,
                subject_value=subject_value,
                permissions=permission,
                description=description,
                first_name=first_name,
                last_name=last_name,
                target_type=target_type,
                target_value=target_value,
            ),
        )

    _render(ctx, run_command(ctx, operation))


@app.command("grant-subunit")
def permissions_grant_subunit(
    ctx: typer.Context,
    subject_type: Annotated[str, typer.Option("--subject-type", help="nip, pesel, or fingerprint.")],
    subject_value: Annotated[str, typer.Option("--subject-value")],
    context_type: Annotated[str, typer.Option("--context-type", help="nip or internal_id.")],
    context_value: Annotated[str, typer.Option("--context-value")],
    first_name: Annotated[str, typer.Option("--first-name")],
    last_name: Annotated[str, typer.Option("--last-name")],
    description: Annotated[str, typer.Option("--description")],
    subunit_name: Annotated[str | None, typer.Option("--subunit-name")] = None,
) -> None:
    """Grant subunit permissions."""

    def operation() -> Any:
        return run_authenticated(
            ctx,
            lambda auth: auth.permissions.grant_subunit(
                subject_type=subject_type,
                subject_value=subject_value,
                context_type=context_type,
                context_value=context_value,
                description=description,
                first_name=first_name,
                last_name=last_name,
                subunit_name=subunit_name,
            ),
        )

    _render(ctx, run_command(ctx, operation))


@app.command("grant-eu-entity")
def permissions_grant_eu_entity(
    ctx: typer.Context,
    subject_value: Annotated[str, typer.Option("--subject-value", help="Fingerprint identifier.")],
    description: Annotated[str, typer.Option("--description")],
    permission: Annotated[list[str], typer.Option("--permission", help="invoice_read or invoice_write. Repeat.")] = [],
) -> None:
    """Grant permissions to an EU entity."""

    def operation() -> Any:
        if not permission:
            raise ValueError("At least one --permission is required.")
        return run_authenticated(
            ctx,
            lambda auth: auth.permissions.grant_eu_entity(
                subject_value=subject_value,
                permissions=permission,
                description=description,
            ),
        )

    _render(ctx, run_command(ctx, operation))


@app.command("grant-eu-admin")
def permissions_grant_eu_admin(
    ctx: typer.Context,
    subject_value: Annotated[str, typer.Option("--subject-value", help="Fingerprint identifier.")],
    context_value: Annotated[str, typer.Option("--context-value", help="VAT UE context value.")],
    eu_entity_name: Annotated[str, typer.Option("--eu-entity-name")],
    description: Annotated[str, typer.Option("--description")],
    context_type: Annotated[str, typer.Option("--context-type")] = "nip_vat_ue",
) -> None:
    """Grant EU-entity administration rights."""

    def operation() -> Any:
        return run_authenticated(
            ctx,
            lambda auth: auth.permissions.grant_eu_entity_administration(
                subject_value=subject_value,
                context_type=context_type,
                context_value=context_value,
                description=description,
                eu_entity_name=eu_entity_name,
            ),
        )

    _render(ctx, run_command(ctx, operation))


@app.command("query")
def permissions_query(
    ctx: typer.Context,
    kind: Annotated[
        str,
        typer.Argument(help="entities, persons, authorizations, personal, eu-entities, subordinate-entities, or subunits."),
    ],
    payload_file: Annotated[Path, typer.Option("--payload", exists=True, dir_okay=False, help="JSON payload for the SDK query model.")],
    page_size: Annotated[int, typer.Option("--page-size", min=10, max=100)] = 10,
    page_offset: Annotated[int, typer.Option("--page-offset", min=0)] = 0,
) -> None:
    """Run a permission query from a JSON payload."""

    from ksef2.domain.models.permissions import (
        AuthorizationPermissionsQuery,
        EntityPermissionsQuery,
        EuEntityPermissionsQuery,
        PersonalPermissionsQuery,
        PersonPermissionsQuery,
        SubordinateEntityRolesQuery,
        SubunitPermissionsQuery,
    )

    query_map: dict[str, tuple[type[BaseModel], str, str]] = {
        "entities": (EntityPermissionsQuery, "query_entities", "permissions"),
        "persons": (PersonPermissionsQuery, "query_persons", "permissions"),
        "authorizations": (AuthorizationPermissionsQuery, "query_authorizations", "authorization_grants"),
        "personal": (PersonalPermissionsQuery, "query_personal", "permissions"),
        "eu-entities": (EuEntityPermissionsQuery, "query_eu_entities", "permissions"),
        "subordinate-entities": (SubordinateEntityRolesQuery, "query_subordinate_entities", "roles"),
        "subunits": (SubunitPermissionsQuery, "query_subunits", "permissions"),
    }

    def operation() -> Any:
        try:
            model_type, method_name, _items_key = query_map[kind]
        except KeyError as exc:
            raise ValueError(f"Unsupported query kind: {kind}") from exc
        query = read_model(ctx, payload_file, model_type)
        return run_authenticated(
            ctx,
            lambda auth: getattr(auth.permissions, method_name)(
                query=query,
                params=_offset_params(page_size, page_offset),
            ),
        )

    items_key = query_map.get(kind, (None, None, None))[2]
    _render(ctx, run_command(ctx, operation), items_key=items_key)


@app.command("revoke-common")
def permissions_revoke_common(
    ctx: typer.Context,
    permission_id: Annotated[str, typer.Option("--permission-id")],
) -> None:
    """Revoke a common permission grant."""

    def operation() -> Any:
        return run_authenticated(
            ctx,
            lambda auth: auth.permissions.revoke_common(permission_id=permission_id),
        )

    _render(ctx, run_command(ctx, operation))


@app.command("revoke-authorization")
def permissions_revoke_authorization(
    ctx: typer.Context,
    permission_id: Annotated[str, typer.Option("--permission-id")],
) -> None:
    """Revoke an authorization permission grant."""

    def operation() -> Any:
        return run_authenticated(
            ctx,
            lambda auth: auth.permissions.revoke_authorization(permission_id=permission_id),
        )

    _render(ctx, run_command(ctx, operation))
