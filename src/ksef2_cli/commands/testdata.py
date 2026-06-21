"""TEST-environment data management command group."""

from datetime import date
from pathlib import Path
from shlex import quote
from typing import Annotated

import typer
from cryptography.hazmat.primitives import serialization
from ksef2 import Client
from ksef2.core.tools import NIP_WEIGHTS, generate_nip
from ksef2.core.xades import generate_test_certificate
from ksef2.domain.models.testdata import (
    AuthContextIdentifier,
    AuthContextIdentifierTypeEnum,
    Identifier,
    IdentifierTypeEnum,
    Permission,
    PermissionTypeEnum,
    SubjectTypeEnum,
    SubUnit,
)
from ksef2.domain.models.tokens import TokenPermissionEnum

from ksef2_cli.config import EnvironmentName
from ksef2_cli.context import get_settings, run_client, run_command, use_client
from ksef2_cli.io import SECRET_MODEL_FILE_MODE, write_bytes_file
from ksef2_cli.renderers import console, render
from ksef2_cli.results import (
    FocusedResult,
    TestAttachmentsEnabled,
    TestAttachmentsRevoked,
    TestContextAccessChanged,
    TestPermissionsGranted,
    TestPermissionsRevoked,
    TestPersonCreated,
    TestPersonDeleted,
    TestSandboxReady,
    TestSubjectCreated,
    TestSubjectDeleted,
)

app = typer.Typer(help="Manage TEST-environment test data.")

_SANDBOX_DEFAULT_TOKEN_PERMISSIONS = (
    TokenPermissionEnum.INVOICE_READ,
    TokenPermissionEnum.INVOICE_WRITE,
)


@app.command("sandbox")
def testdata_sandbox(
    ctx: typer.Context,
    nip: Annotated[
        str | None,
        typer.Option("--nip", help="Sandbox subject NIP. Defaults to a generated NIP."),
    ] = None,
    subject_type: Annotated[
        SubjectTypeEnum,
        typer.Option("--type", help="enforcement_authority, vat_group, or jst."),
    ] = SubjectTypeEnum.ENFORCEMENT_AUTHORITY,
    description: Annotated[
        str, typer.Option("--description", help="TEST subject description.")
    ] = "ksef2-cli sandbox",
    out_dir: Annotated[
        Path,
        typer.Option(
            "--out-dir",
            file_okay=False,
            help="Directory for generated certificate, key, and env files.",
        ),
    ] = Path(".ksef2-sandbox"),
    token_permission: Annotated[
        list[TokenPermissionEnum],
        typer.Option(
            "--token-permission",
            help="Token permission. Repeat for multiple permissions.",
        ),
    ] = [],
    token_description: Annotated[
        str, typer.Option("--token-description", help="Generated token description.")
    ] = "ksef2-cli sandbox token",
    hold: Annotated[
        bool,
        typer.Option(
            "--hold/--no-hold",
            help="Keep the temporal TEST subject alive until Enter is pressed.",
        ),
    ] = True,
) -> None:
    """Create a temporary TEST subject with credentials and cleanup on exit."""

    def operation() -> None:
        settings = get_settings(ctx)
        if settings.environment != EnvironmentName.test:
            raise ValueError("testdata sandbox requires --env test.")

        effective_nip = _sandbox_nip(nip or settings.nip)
        selected_permissions = token_permission or list(
            _SANDBOX_DEFAULT_TOKEN_PERMISSIONS
        )
        token_permissions = [permission.value for permission in selected_permissions]
        sandbox_dir = out_dir.expanduser().resolve() / effective_nip
        cert_file = sandbox_dir / "cert.pem"
        key_file = sandbox_dir / "private-key.pem"
        env_file = sandbox_dir / "env.sh"

        with use_client(ctx) as client:
            with client.testdata.temporal() as temporal:
                temporal.create_subject(
                    nip=effective_nip,
                    subject_type=subject_type.value,
                    description=description,
                )

                cert, private_key = generate_test_certificate(effective_nip)
                write_bytes_file(
                    cert_file,
                    cert.public_bytes(serialization.Encoding.PEM),
                )
                write_bytes_file(
                    key_file,
                    private_key.private_bytes(
                        encoding=serialization.Encoding.PEM,
                        format=serialization.PrivateFormat.PKCS8,
                        encryption_algorithm=serialization.NoEncryption(),
                    ),
                ).chmod(SECRET_MODEL_FILE_MODE)

                auth = client.authentication.with_xades(
                    nip=effective_nip,
                    cert=cert,
                    private_key=private_key,
                    poll_interval=settings.poll_interval,
                    max_poll_attempts=settings.max_poll_attempts,
                )
                token = auth.tokens.generate(
                    permissions=token_permissions,
                    description=token_description,
                    poll_interval=settings.poll_interval,
                    max_poll_attempts=settings.max_poll_attempts,
                )

                env_file.parent.mkdir(parents=True, exist_ok=True)
                env_file.write_text(
                    "\n".join(
                        (
                            "# ksef2-cli temporal TEST sandbox",
                            f"export KSEF2_NIP={quote(effective_nip)}",
                            f"export KSEF2_TOKEN={quote(token.token)}",
                            f"export KSEF2_CERT={quote(str(cert_file))}",
                            f"export KSEF2_KEY={quote(str(key_file))}",
                            "",
                        )
                    ),
                    encoding="utf-8",
                )
                env_file.chmod(SECRET_MODEL_FILE_MODE)

                result = TestSandboxReady(
                    nip=effective_nip,
                    subject_type=subject_type.value,
                    token=token.token,
                    reference_number=token.reference_number,
                    token_permissions=token_permissions,
                    sandbox_dir=sandbox_dir,
                    cert_file=cert_file,
                    key_file=key_file,
                    env_file=env_file,
                    source_command=f"source {quote(str(env_file))}",
                    token_send_command='ksef2 --env test --nip "$KSEF2_NIP" '
                    '--token "$KSEF2_TOKEN" invoices send invoice.xml --wait',
                    certificate_send_command='ksef2 --env test --nip "$KSEF2_NIP" '
                    '--cert "$KSEF2_CERT" --key "$KSEF2_KEY" invoices send '
                    "invoice.xml --wait",
                )
                render(ctx, result)

                if hold:
                    try:
                        console.input(
                            "Sandbox is active. Press Enter to clean up remote "
                            "TEST data."
                        )
                    except EOFError:
                        pass

    run_command(ctx, operation, render_result=False)


def _sandbox_nip(value: str | None) -> str:
    if value is None:
        return generate_nip()
    if not _valid_nip(value):
        raise ValueError("--nip must be a valid 10-digit NIP.")
    return value


def _valid_nip(value: str) -> bool:
    if len(value) != 10 or not value.isdecimal():
        return False
    digits = [int(digit) for digit in value]
    if digits[0] == 0 or digits[1:3] == [0, 0]:
        return False
    checksum = (
        sum(weight * digit for weight, digit in zip(NIP_WEIGHTS, digits[:9])) % 11
    )
    return checksum == digits[9]


@app.command("create-subject")
def testdata_create_subject(
    ctx: typer.Context,
    nip: Annotated[str, typer.Option("--nip")],
    subject_type: Annotated[
        SubjectTypeEnum,
        typer.Option("--type", help="enforcement_authority, vat_group, or jst."),
    ],
    description: Annotated[str, typer.Option("--description")],
    subunit: Annotated[
        list[str],
        typer.Option(
            "--subunit", help="Subunit as NIP:description. Repeat for multiple."
        ),
    ] = [],
) -> None:
    """Create a TEST subject."""

    def operation() -> TestSubjectCreated:
        subunits = []
        for item in subunit:
            try:
                subject_nip, subunit_description = item.split(":", 1)
            except ValueError as exc:
                raise ValueError("--subunit must use NIP:description format.") from exc
            subunits.append(
                SubUnit(subject_nip=subject_nip, description=subunit_description)
            )

        def create_subject(client: Client) -> None:
            client.testdata.create_subject(
                nip=nip,
                subject_type=subject_type.value,
                description=description,
                subunits=subunits or None,
            )

        run_client(ctx, create_subject)
        return TestSubjectCreated(nip=nip)

    run_command(ctx, operation)


@app.command("delete-subject")
def testdata_delete_subject(
    ctx: typer.Context,
    nip: Annotated[str, typer.Option("--nip")],
) -> None:
    """Delete a TEST subject."""

    def operation() -> TestSubjectDeleted:
        def delete_subject(client: Client) -> None:
            client.testdata.delete_subject(nip=nip)

        run_client(ctx, delete_subject)
        return TestSubjectDeleted(nip=nip)

    run_command(ctx, operation)


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

    def operation() -> TestPersonCreated:
        def create_person(client: Client) -> None:
            client.testdata.create_person(
                nip=nip,
                pesel=pesel,
                description=description,
                is_bailiff=is_bailiff,
                is_deceased=is_deceased,
            )

        run_client(ctx, create_person)
        return TestPersonCreated(nip=nip, pesel=pesel)

    run_command(ctx, operation)


@app.command("delete-person")
def testdata_delete_person(
    ctx: typer.Context,
    nip: Annotated[str, typer.Option("--nip")],
) -> None:
    """Delete a TEST person."""

    def operation() -> TestPersonDeleted:
        def delete_person(client: Client) -> None:
            client.testdata.delete_person(nip=nip)

        run_client(ctx, delete_person)
        return TestPersonDeleted(nip=nip)

    run_command(ctx, operation)


@app.command("enable-attachments")
def testdata_enable_attachments(
    ctx: typer.Context,
    nip: Annotated[str, typer.Option("--nip")],
) -> None:
    """Enable attachments for a TEST subject."""

    def operation() -> TestAttachmentsEnabled:
        def enable_attachments(client: Client) -> None:
            client.testdata.enable_attachments(nip=nip)

        run_client(ctx, enable_attachments)
        return TestAttachmentsEnabled(nip=nip)

    run_command(ctx, operation)


@app.command("revoke-attachments")
def testdata_revoke_attachments(
    ctx: typer.Context,
    nip: Annotated[str, typer.Option("--nip")],
    expected_end_date: Annotated[
        str | None, typer.Option("--expected-end-date", help="YYYY-MM-DD.")
    ] = None,
) -> None:
    """Revoke attachments for a TEST subject."""

    def operation() -> TestAttachmentsRevoked:
        parsed_date = (
            date.fromisoformat(expected_end_date) if expected_end_date else None
        )

        def revoke_attachments(client: Client) -> None:
            client.testdata.revoke_attachments(nip=nip, expected_end_date=parsed_date)

        run_client(ctx, revoke_attachments)
        return TestAttachmentsRevoked(nip=nip, expected_end_date=expected_end_date)

    run_command(ctx, operation)


@app.command("block-context")
def testdata_block_context(
    ctx: typer.Context,
    context_type: Annotated[
        AuthContextIdentifierTypeEnum, typer.Option("--context-type")
    ],
    context_value: Annotated[str, typer.Option("--context-value")],
) -> None:
    """Block a TEST auth context."""

    def operation() -> TestContextAccessChanged:
        context = AuthContextIdentifier(type=context_type.value, value=context_value)

        def block_context(client: Client) -> None:
            client.testdata.block_context(context=context)

        run_client(ctx, block_context)
        return TestContextAccessChanged(
            context_type=context_type.value, context_value=context_value, blocked=True
        )

    run_command(ctx, operation)


@app.command("unblock-context")
def testdata_unblock_context(
    ctx: typer.Context,
    context_type: Annotated[
        AuthContextIdentifierTypeEnum, typer.Option("--context-type")
    ],
    context_value: Annotated[str, typer.Option("--context-value")],
) -> None:
    """Unblock a TEST auth context."""

    def operation() -> TestContextAccessChanged:
        context = AuthContextIdentifier(type=context_type.value, value=context_value)

        def unblock_context(client: Client) -> None:
            client.testdata.unblock_context(context=context)

        run_client(ctx, unblock_context)
        return TestContextAccessChanged(
            context_type=context_type.value, context_value=context_value, blocked=False
        )

    run_command(ctx, operation)


@app.command("grant-permissions")
def testdata_grant_permissions(
    ctx: typer.Context,
    grant_to_type: Annotated[IdentifierTypeEnum, typer.Option("--grant-to-type")],
    grant_to_value: Annotated[str, typer.Option("--grant-to-value")],
    context_type: Annotated[IdentifierTypeEnum, typer.Option("--context-type")],
    context_value: Annotated[str, typer.Option("--context-value")],
    permission: Annotated[
        list[PermissionTypeEnum],
        typer.Option("--permission", help="Permission type. Repeat."),
    ] = [],
    description: Annotated[str, typer.Option("--description")] = "Granted by ksef2-cli",
) -> None:
    """Grant TEST permissions."""

    def operation() -> FocusedResult[TestPermissionsGranted, Permission]:
        if not permission:
            raise ValueError("At least one --permission is required.")

        permissions = [
            Permission(type=item.value, description=description) for item in permission
        ]
        grant_to = Identifier(type=grant_to_type.value, value=grant_to_value)
        in_context_of = Identifier(type=context_type.value, value=context_value)

        def grant_permissions(client: Client) -> None:
            client.testdata.grant_permissions(
                permissions=permissions,
                grant_to=grant_to,
                in_context_of=in_context_of,
            )

        run_client(ctx, grant_permissions)
        payload = TestPermissionsGranted(
            grant_to=grant_to,
            in_context_of=in_context_of,
            permissions=permissions,
        )
        return FocusedResult(
            payload=payload,
            items=permissions,
        )

    run_command(ctx, operation)


@app.command("revoke-permissions")
def testdata_revoke_permissions(
    ctx: typer.Context,
    revoke_from_type: Annotated[IdentifierTypeEnum, typer.Option("--revoke-from-type")],
    revoke_from_value: Annotated[str, typer.Option("--revoke-from-value")],
    context_type: Annotated[IdentifierTypeEnum, typer.Option("--context-type")],
    context_value: Annotated[str, typer.Option("--context-value")],
) -> None:
    """Revoke TEST permissions."""

    def operation() -> TestPermissionsRevoked:
        revoke_from = Identifier(type=revoke_from_type.value, value=revoke_from_value)
        in_context_of = Identifier(type=context_type.value, value=context_value)

        def revoke_permissions(client: Client) -> None:
            client.testdata.revoke_permissions(
                revoke_from=revoke_from,
                in_context_of=in_context_of,
            )

        run_client(ctx, revoke_permissions)
        return TestPermissionsRevoked(
            revoke_from=revoke_from, in_context_of=in_context_of
        )

    run_command(ctx, operation)
