"""Permission grant, query, and revoke command group."""

from enum import StrEnum
from pathlib import Path
from typing import Annotated

import typer
from ksef2.clients import AuthenticatedClient, PermissionOperation
from ksef2.models import (
    AttachmentPermissionStatus,
    AuthorizationGrantDetail,
    AuthorizationPermissionTypeEnum,
    AuthorizationSubjectIdentifierTypeEnum,
    EntityPermission,
    EntityPermissionDetail,
    EntityPermissionTypeEnum,
    EntityRole,
    EuEntityAdminContextIdentifierTypeEnum,
    EuEntityPermission,
    EuEntityPermissionTypeEnum,
    GrantPermissionsResponse,
    IndirectPermissionTypeEnum,
    IndirectTargetIdentifierTypeEnum,
    OffsetPaginationParams,
    PermissionOperationStatusResponse,
    PersonalPermissionDetail,
    PersonPermissionDetail,
    SubordinateEntityRoleDetail,
    SubunitIdentifierTypeEnum,
    SubunitPermission,
)

from ksef2_cli.context import read_model, run_authenticated, run_command
from ksef2_cli.parsing import validate_offset_pagination

app = typer.Typer(help="Grant, query, and revoke permissions.")

# One list item returned by a ``list_*`` pager, across every permission listing.
type PermissionListItem = (
    AuthorizationGrantDetail
    | EntityPermissionDetail
    | EntityRole
    | EuEntityPermission
    | PersonalPermissionDetail
    | PersonPermissionDetail
    | SubordinateEntityRoleDetail
    | SubunitPermission
)
type PermissionQueryResult = list[PermissionListItem]
type PermissionOperationResult = (
    GrantPermissionsResponse | PermissionOperationStatusResponse
)


def _operation_result(
    handle: PermissionOperation, *, wait: bool
) -> PermissionOperationResult:
    """Return the accepted operation response, or the final status when waiting."""

    return handle.wait() if wait else handle.response


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
    page_size: Annotated[
        int,
        typer.Option(
            "--page-size",
            min=10,
            max=100,
            help="Items per API request, including with --all.",
        ),
    ] = 10,
    page_offset: Annotated[
        int,
        typer.Option(
            "--page-offset",
            min=0,
            help="Offset for a single page; must be 0 with --all.",
        ),
    ] = 0,
    all_pages: Annotated[bool, typer.Option("--all", help="Fetch all pages.")] = False,
) -> None:
    """List roles assigned to the authenticated entity."""

    def operation() -> PermissionQueryResult:
        validate_offset_pagination(all_pages=all_pages, page_offset=page_offset)
        params = OffsetPaginationParams(page_size=page_size, page_offset=page_offset)

        def list_roles(auth: AuthenticatedClient) -> PermissionQueryResult:
            pager = auth.permissions.list_entity_roles(params=params)
            return list(pager) if all_pages else pager.first_page()

        return run_authenticated(ctx, list_roles)

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
    wait: Annotated[
        bool, typer.Option("--wait", help="Wait for the operation to finish.")
    ] = False,
) -> None:
    """Grant permissions directly to a person."""

    def operation() -> PermissionOperationResult:
        if not permission:
            raise ValueError("At least one --permission is required.")
        return run_authenticated(
            ctx,
            lambda auth: _operation_result(
                auth.permissions.grant_person(
                    subject_type=subject_type.value,
                    subject_value=subject_value,
                    permissions=[item.value for item in permission],
                    description=description,
                    first_name=first_name,
                    last_name=last_name,
                ),
                wait=wait,
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
    wait: Annotated[
        bool, typer.Option("--wait", help="Wait for the operation to finish.")
    ] = False,
) -> None:
    """Grant permissions to an entity."""

    def operation() -> PermissionOperationResult:
        if not permission:
            raise ValueError("At least one --permission is required.")

        permissions = [
            EntityPermission(type=item.value, can_delegate=can_delegate)
            for item in permission
        ]
        return run_authenticated(
            ctx,
            lambda auth: _operation_result(
                auth.permissions.grant_entity(
                    subject_value=subject_value,
                    permissions=permissions,
                    description=description,
                    entity_name=entity_name,
                ),
                wait=wait,
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
    wait: Annotated[
        bool, typer.Option("--wait", help="Wait for the operation to finish.")
    ] = False,
) -> None:
    """Grant invoice authorization rights to an entity."""

    def operation() -> PermissionOperationResult:
        return run_authenticated(
            ctx,
            lambda auth: _operation_result(
                auth.permissions.grant_authorization(
                    subject_type=subject_type.value,
                    subject_value=subject_value,
                    permission=permission.value,
                    description=description,
                    entity_name=entity_name,
                ),
                wait=wait,
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
    wait: Annotated[
        bool, typer.Option("--wait", help="Wait for the operation to finish.")
    ] = False,
) -> None:
    """Grant indirect permissions."""

    def operation() -> PermissionOperationResult:
        if not permission:
            raise ValueError("At least one --permission is required.")
        return run_authenticated(
            ctx,
            lambda auth: _operation_result(
                auth.permissions.grant_indirect(
                    subject_type=subject_type.value,
                    subject_value=subject_value,
                    permissions=[item.value for item in permission],
                    description=description,
                    first_name=first_name,
                    last_name=last_name,
                    target_type=target_type.value if target_type else None,
                    target_value=target_value,
                ),
                wait=wait,
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
    wait: Annotated[
        bool, typer.Option("--wait", help="Wait for the operation to finish.")
    ] = False,
) -> None:
    """Grant subunit permissions."""

    def operation() -> PermissionOperationResult:
        return run_authenticated(
            ctx,
            lambda auth: _operation_result(
                auth.permissions.grant_subunit(
                    subject_type=subject_type.value,
                    subject_value=subject_value,
                    context_type=context_type.value,
                    context_value=context_value,
                    description=description,
                    first_name=first_name,
                    last_name=last_name,
                    subunit_name=subunit_name,
                ),
                wait=wait,
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
    wait: Annotated[
        bool, typer.Option("--wait", help="Wait for the operation to finish.")
    ] = False,
) -> None:
    """Grant permissions to an EU entity."""

    def operation() -> PermissionOperationResult:
        if not permission:
            raise ValueError("At least one --permission is required.")
        return run_authenticated(
            ctx,
            lambda auth: _operation_result(
                auth.permissions.grant_eu_entity(
                    subject_value=subject_value,
                    permissions=[item.value for item in permission],
                    description=description,
                ),
                wait=wait,
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
    wait: Annotated[
        bool, typer.Option("--wait", help="Wait for the operation to finish.")
    ] = False,
) -> None:
    """Grant EU-entity administration rights."""

    def operation() -> PermissionOperationResult:
        return run_authenticated(
            ctx,
            lambda auth: _operation_result(
                auth.permissions.grant_eu_entity_administration(
                    subject_value=subject_value,
                    context_type=context_type.value,
                    context_value=context_value,
                    description=description,
                    eu_entity_name=eu_entity_name,
                ),
                wait=wait,
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
    page_size: Annotated[
        int,
        typer.Option(
            "--page-size",
            min=10,
            max=100,
            help="Items per API request, including with --all.",
        ),
    ] = 10,
    page_offset: Annotated[
        int,
        typer.Option(
            "--page-offset",
            min=0,
            help="Offset for a single page; must be 0 with --all.",
        ),
    ] = 0,
    all_pages: Annotated[bool, typer.Option("--all", help="Fetch all pages.")] = False,
) -> None:
    """Run a permission query from a JSON payload."""

    from ksef2.models import (
        AuthorizationPermissionsQuery,
        EntityPermissionsQuery,
        EuEntityPermissionsQuery,
        PersonalPermissionsQuery,
        PersonPermissionsQuery,
        SubordinateEntityRolesQuery,
        SubunitPermissionsQuery,
    )

    def operation() -> PermissionQueryResult:
        validate_offset_pagination(all_pages=all_pages, page_offset=page_offset)
        params = OffsetPaginationParams(page_size=page_size, page_offset=page_offset)

        def list_permissions(auth: AuthenticatedClient) -> PermissionQueryResult:
            match kind:
                case PermissionQueryKindChoice.ENTITIES:
                    query = read_model(ctx, payload_file, EntityPermissionsQuery)
                    pager = auth.permissions.list_entities(query, params=params)
                case PermissionQueryKindChoice.PERSONS:
                    query = read_model(ctx, payload_file, PersonPermissionsQuery)
                    pager = auth.permissions.list_persons(query, params=params)
                case PermissionQueryKindChoice.AUTHORIZATIONS:
                    query = read_model(ctx, payload_file, AuthorizationPermissionsQuery)
                    pager = auth.permissions.list_authorizations(query, params=params)
                case PermissionQueryKindChoice.PERSONAL:
                    query = read_model(ctx, payload_file, PersonalPermissionsQuery)
                    pager = auth.permissions.list_personal(query, params=params)
                case PermissionQueryKindChoice.EU_ENTITIES:
                    query = read_model(ctx, payload_file, EuEntityPermissionsQuery)
                    pager = auth.permissions.list_eu_entities(query, params=params)
                case PermissionQueryKindChoice.SUBORDINATE_ENTITIES:
                    query = read_model(ctx, payload_file, SubordinateEntityRolesQuery)
                    pager = auth.permissions.list_subordinate_entities(
                        query, params=params
                    )
                case PermissionQueryKindChoice.SUBUNITS:
                    query = read_model(ctx, payload_file, SubunitPermissionsQuery)
                    pager = auth.permissions.list_subunits(query, params=params)
                case _:
                    raise ValueError(f"Unsupported permission query kind: {kind}")

            return list(pager) if all_pages else pager.first_page()

        return run_authenticated(ctx, list_permissions)

    run_command(ctx, operation)


@app.command("revoke-common")
def permissions_revoke_common(
    ctx: typer.Context,
    permission_id: Annotated[str, typer.Option("--permission-id")],
    wait: Annotated[
        bool, typer.Option("--wait", help="Wait for the operation to finish.")
    ] = False,
) -> None:
    """Revoke a common permission grant."""

    def operation() -> PermissionOperationResult:
        return run_authenticated(
            ctx,
            lambda auth: _operation_result(
                auth.permissions.revoke(permission_id=permission_id), wait=wait
            ),
        )

    run_command(ctx, operation)


@app.command("revoke-authorization")
def permissions_revoke_authorization(
    ctx: typer.Context,
    permission_id: Annotated[str, typer.Option("--permission-id")],
    wait: Annotated[
        bool, typer.Option("--wait", help="Wait for the operation to finish.")
    ] = False,
) -> None:
    """Revoke an authorization permission grant."""

    def operation() -> PermissionOperationResult:
        return run_authenticated(
            ctx,
            lambda auth: _operation_result(
                auth.permissions.revoke_authorization(permission_id=permission_id),
                wait=wait,
            ),
        )

    run_command(ctx, operation)
