"""Permission grant, query, and revoke command group."""

from collections.abc import Mapping
from enum import StrEnum
from pathlib import Path
from typing import Annotated

import typer
from ksef2.clients.authenticated import AuthenticatedClient
from ksef2.domain.models import KSeFBaseModel
from ksef2.domain.models.pagination import OffsetPaginationParams
from ksef2.domain.models.permissions import (
    AttachmentPermissionStatus,
    AuthorizationPermissionTypeEnum,
    AuthorizationPermissionsQueryResponse,
    AuthorizationSubjectIdentifierTypeEnum,
    EntityPermission,
    EntityPermissionTypeEnum,
    EntityPermissionsQueryResponse,
    EntityRolesResponse,
    EuEntityAdminContextIdentifierTypeEnum,
    EuEntityPermissionTypeEnum,
    EuEntityPermissionsQueryResponse,
    GrantPermissionsResponse,
    IndirectPermissionTypeEnum,
    IndirectTargetIdentifierTypeEnum,
    PermissionOperationStatusResponse,
    PersonalPermissionsQueryResponse,
    PersonPermissionsQueryResponse,
    SubordinateEntityRolesQueryResponse,
    SubunitIdentifierTypeEnum,
    SubunitPermissionsQueryResponse,
)

from ksef2_cli.context import read_model, run_authenticated, run_command

app = typer.Typer(help="Grant, query, and revoke permissions.")

type PermissionQueryResult = (
    AuthorizationPermissionsQueryResponse
    | EntityPermissionsQueryResponse
    | EuEntityPermissionsQueryResponse
    | PersonalPermissionsQueryResponse
    | PersonPermissionsQueryResponse
    | SubordinateEntityRolesQueryResponse
    | SubunitPermissionsQueryResponse
)


@app.command("attachment-status")
def permissions_attachment_status(ctx: typer.Context) -> None:
    """Read attachment permission status."""

    def operation() -> AttachmentPermissionStatus:
        return run_authenticated(
            ctx, lambda auth: auth.permissions.get_attachment_permission_status()
        )

    run_command(ctx, operation)


@app.command("operation-status")
def permissions_operation_status(
    ctx: typer.Context,
    reference_number: Annotated[str, typer.Option("--reference")],
) -> None:
    """Read async permission operation status."""

    def operation() -> PermissionOperationStatusResponse:
        return run_authenticated(
            ctx,
            lambda auth: auth.permissions.get_operation_status(
                reference_number=reference_number
            ),
        )

    run_command(ctx, operation)


@app.command("entity-roles")
def permissions_entity_roles(
    ctx: typer.Context,
    page_size: Annotated[int, typer.Option("--page-size", min=10, max=100)] = 10,
    page_offset: Annotated[int, typer.Option("--page-offset", min=0)] = 0,
) -> None:
    """List roles assigned to the authenticated entity."""

    def operation() -> EntityRolesResponse:
        params = OffsetPaginationParams(page_size=page_size, page_offset=page_offset)
        return run_authenticated(
            ctx,
            lambda auth: auth.permissions.get_entity_roles(params=params),
        )

    run_command(ctx, operation)


class CertificateSubjectIdentifierChoice(StrEnum):
    NIP = "nip"
    PESEL = "pesel"
    FINGERPRINT = "fingerprint"


class PersonPermissionScopeChoice(StrEnum):
    INVOICE_READ = "invoice_read"
    INVOICE_WRITE = "invoice_write"
    INTROSPECTION = "introspection"
    CREDENTIALS_READ = "credentials_read"
    CREDENTIALS_MANAGE = "credentials_manage"
    ENFORCEMENT_OPERATIONS = "enforcement_operations"
    SUBUNIT_MANAGE = "subunit_manage"


@app.command("grant-person")
def permissions_grant_person(
    ctx: typer.Context,
    subject_type: Annotated[
        CertificateSubjectIdentifierChoice,
        typer.Option("--subject-type", help="nip, pesel, or fingerprint."),
    ],
    subject_value: Annotated[str, typer.Option("--subject-value")],
    first_name: Annotated[str, typer.Option("--first-name")],
    last_name: Annotated[str, typer.Option("--last-name")],
    description: Annotated[str, typer.Option("--description")],
    permission: Annotated[
        list[PersonPermissionScopeChoice],
        typer.Option("--permission", help="Permission scope. Repeat."),
    ] = [],
) -> None:
    """Grant permissions directly to a person."""

    def operation() -> GrantPermissionsResponse:
        if not permission:
            raise ValueError("At least one --permission is required.")
        return run_authenticated(
            ctx,
            lambda auth: auth.permissions.grant_person(
                subject_type=subject_type.value,
                subject_value=subject_value,
                permissions=[item.value for item in permission],
                description=description,
                first_name=first_name,
                last_name=last_name,
            ),
        )

    run_command(ctx, operation)


@app.command("grant-entity")
def permissions_grant_entity(
    ctx: typer.Context,
    subject_value: Annotated[str, typer.Option("--subject-value", help="Entity NIP.")],
    entity_name: Annotated[str, typer.Option("--entity-name")],
    description: Annotated[str, typer.Option("--description")],
    permission: Annotated[
        list[EntityPermissionTypeEnum],
        typer.Option("--permission", help="invoice_read or invoice_write. Repeat."),
    ] = [],
    can_delegate: Annotated[
        bool,
        typer.Option(
            "--can-delegate", help="Apply delegation to all permission scopes."
        ),
    ] = False,
) -> None:
    """Grant permissions to an entity."""

    def operation() -> GrantPermissionsResponse:
        if not permission:
            raise ValueError("At least one --permission is required.")

        permissions = [
            EntityPermission(type=item.value, can_delegate=can_delegate)
            for item in permission
        ]
        return run_authenticated(
            ctx,
            lambda auth: auth.permissions.grant_entity(
                subject_value=subject_value,
                permissions=permissions,
                description=description,
                entity_name=entity_name,
            ),
        )

    run_command(ctx, operation)


@app.command("grant-authorization")
def permissions_grant_authorization(
    ctx: typer.Context,
    subject_type: Annotated[
        AuthorizationSubjectIdentifierTypeEnum,
        typer.Option("--subject-type", help="nip or peppol_id."),
    ],
    subject_value: Annotated[str, typer.Option("--subject-value")],
    permission: Annotated[
        AuthorizationPermissionTypeEnum, typer.Option("--permission")
    ],
    entity_name: Annotated[str, typer.Option("--entity-name")],
    description: Annotated[str, typer.Option("--description")],
) -> None:
    """Grant invoice authorization rights to an entity."""

    def operation() -> GrantPermissionsResponse:
        return run_authenticated(
            ctx,
            lambda auth: auth.permissions.grant_authorization(
                subject_type=subject_type.value,
                subject_value=subject_value,
                permission=permission.value,
                description=description,
                entity_name=entity_name,
            ),
        )

    run_command(ctx, operation)


@app.command("grant-indirect")
def permissions_grant_indirect(
    ctx: typer.Context,
    subject_type: Annotated[
        CertificateSubjectIdentifierChoice,
        typer.Option("--subject-type", help="nip, pesel, or fingerprint."),
    ],
    subject_value: Annotated[str, typer.Option("--subject-value")],
    first_name: Annotated[str, typer.Option("--first-name")],
    last_name: Annotated[str, typer.Option("--last-name")],
    description: Annotated[str, typer.Option("--description")],
    permission: Annotated[
        list[IndirectPermissionTypeEnum],
        typer.Option("--permission", help="invoice_read or invoice_write. Repeat."),
    ] = [],
    target_type: Annotated[
        IndirectTargetIdentifierTypeEnum | None, typer.Option("--target-type")
    ] = None,
    target_value: Annotated[str | None, typer.Option("--target-value")] = None,
) -> None:
    """Grant indirect permissions."""

    def operation() -> GrantPermissionsResponse:
        if not permission:
            raise ValueError("At least one --permission is required.")
        return run_authenticated(
            ctx,
            lambda auth: auth.permissions.grant_indirect(
                subject_type=subject_type.value,
                subject_value=subject_value,
                permissions=[item.value for item in permission],
                description=description,
                first_name=first_name,
                last_name=last_name,
                target_type=target_type.value if target_type else None,
                target_value=target_value,
            ),
        )

    run_command(ctx, operation)


@app.command("grant-subunit")
def permissions_grant_subunit(
    ctx: typer.Context,
    subject_type: Annotated[
        CertificateSubjectIdentifierChoice,
        typer.Option("--subject-type", help="nip, pesel, or fingerprint."),
    ],
    subject_value: Annotated[str, typer.Option("--subject-value")],
    context_type: Annotated[
        SubunitIdentifierTypeEnum,
        typer.Option("--context-type", help="nip or internal_id."),
    ],
    context_value: Annotated[str, typer.Option("--context-value")],
    first_name: Annotated[str, typer.Option("--first-name")],
    last_name: Annotated[str, typer.Option("--last-name")],
    description: Annotated[str, typer.Option("--description")],
    subunit_name: Annotated[str | None, typer.Option("--subunit-name")] = None,
) -> None:
    """Grant subunit permissions."""

    def operation() -> GrantPermissionsResponse:
        return run_authenticated(
            ctx,
            lambda auth: auth.permissions.grant_subunit(
                subject_type=subject_type.value,
                subject_value=subject_value,
                context_type=context_type.value,
                context_value=context_value,
                description=description,
                first_name=first_name,
                last_name=last_name,
                subunit_name=subunit_name,
            ),
        )

    run_command(ctx, operation)


@app.command("grant-eu-entity")
def permissions_grant_eu_entity(
    ctx: typer.Context,
    subject_value: Annotated[
        str, typer.Option("--subject-value", help="Fingerprint identifier.")
    ],
    description: Annotated[str, typer.Option("--description")],
    permission: Annotated[
        list[EuEntityPermissionTypeEnum],
        typer.Option("--permission", help="invoice_read or invoice_write. Repeat."),
    ] = [],
) -> None:
    """Grant permissions to an EU entity."""

    def operation() -> GrantPermissionsResponse:
        if not permission:
            raise ValueError("At least one --permission is required.")
        return run_authenticated(
            ctx,
            lambda auth: auth.permissions.grant_eu_entity(
                subject_value=subject_value,
                permissions=[item.value for item in permission],
                description=description,
            ),
        )

    run_command(ctx, operation)


@app.command("grant-eu-admin")
def permissions_grant_eu_admin(
    ctx: typer.Context,
    subject_value: Annotated[
        str, typer.Option("--subject-value", help="Fingerprint identifier.")
    ],
    context_value: Annotated[
        str, typer.Option("--context-value", help="VAT UE context value.")
    ],
    eu_entity_name: Annotated[str, typer.Option("--eu-entity-name")],
    description: Annotated[str, typer.Option("--description")],
    context_type: Annotated[
        EuEntityAdminContextIdentifierTypeEnum, typer.Option("--context-type")
    ] = EuEntityAdminContextIdentifierTypeEnum.NIP_VAT_UE,
) -> None:
    """Grant EU-entity administration rights."""

    def operation() -> GrantPermissionsResponse:
        return run_authenticated(
            ctx,
            lambda auth: auth.permissions.grant_eu_entity_administration(
                subject_value=subject_value,
                context_type=context_type.value,
                context_value=context_value,
                description=description,
                eu_entity_name=eu_entity_name,
            ),
        )

    run_command(ctx, operation)


class PermissionQueryKindChoice(StrEnum):
    ENTITIES = "entities"
    PERSONS = "persons"
    AUTHORIZATIONS = "authorizations"
    PERSONAL = "personal"
    EU_ENTITIES = "eu-entities"
    SUBORDINATE_ENTITIES = "subordinate-entities"
    SUBUNITS = "subunits"


@app.command("query")
def permissions_query(
    ctx: typer.Context,
    kind: Annotated[
        PermissionQueryKindChoice,
        typer.Argument(
            help="entities, persons, authorizations, personal, eu-entities, subordinate-entities, or subunits."
        ),
    ],
    payload_file: Annotated[
        Path,
        typer.Option(
            "--payload",
            exists=True,
            dir_okay=False,
            help="JSON payload for the SDK query model.",
        ),
    ],
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

    def operation() -> PermissionQueryResult:
        params = OffsetPaginationParams(page_size=page_size, page_offset=page_offset)

        def query_permissions(auth: AuthenticatedClient) -> PermissionQueryResult:
            match kind:
                case PermissionQueryKindChoice.ENTITIES:
                    query = read_model(ctx, payload_file, EntityPermissionsQuery)
                    return auth.permissions.query_entities(query=query, params=params)
                case PermissionQueryKindChoice.PERSONS:
                    query = read_model(ctx, payload_file, PersonPermissionsQuery)
                    return auth.permissions.query_persons(query=query, params=params)
                case PermissionQueryKindChoice.AUTHORIZATIONS:
                    query = read_model(ctx, payload_file, AuthorizationPermissionsQuery)
                    return auth.permissions.query_authorizations(
                        query=query, params=params
                    )
                case PermissionQueryKindChoice.PERSONAL:
                    query = read_model(ctx, payload_file, PersonalPermissionsQuery)
                    return auth.permissions.query_personal(query=query, params=params)
                case PermissionQueryKindChoice.EU_ENTITIES:
                    query = read_model(ctx, payload_file, EuEntityPermissionsQuery)
                    return auth.permissions.query_eu_entities(
                        query=query, params=params
                    )
                case PermissionQueryKindChoice.SUBORDINATE_ENTITIES:
                    query = read_model(ctx, payload_file, SubordinateEntityRolesQuery)
                    return auth.permissions.query_subordinate_entities(
                        query=query, params=params
                    )
                case PermissionQueryKindChoice.SUBUNITS:
                    query = read_model(ctx, payload_file, SubunitPermissionsQuery)
                    return auth.permissions.query_subunits(query=query, params=params)
                case _:
                    raise ValueError(f"Unsupported permission query kind: {kind}")

        return run_authenticated(
            ctx,
            query_permissions,
        )

    run_command(ctx, operation)


@app.command("revoke-common")
def permissions_revoke_common(
    ctx: typer.Context,
    permission_id: Annotated[str, typer.Option("--permission-id")],
) -> None:
    """Revoke a common permission grant."""

    def operation() -> GrantPermissionsResponse:
        return run_authenticated(
            ctx,
            lambda auth: auth.permissions.revoke_common(permission_id=permission_id),
        )

    run_command(ctx, operation)


@app.command("revoke-authorization")
def permissions_revoke_authorization(
    ctx: typer.Context,
    permission_id: Annotated[str, typer.Option("--permission-id")],
) -> None:
    """Revoke an authorization permission grant."""

    def operation() -> GrantPermissionsResponse:
        return run_authenticated(
            ctx,
            lambda auth: auth.permissions.revoke_authorization(
                permission_id=permission_id
            ),
        )

    run_command(ctx, operation)
