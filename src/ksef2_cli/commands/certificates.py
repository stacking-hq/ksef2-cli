"""Certificate management command group."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any

import typer

from ksef2_cli.context import run_authenticated, run_command
from ksef2_cli.rendering import _render
from ksef2_cli.sdk_models import _offset_params

app = typer.Typer(help='Manage MCU certificates.')


@app.command("limits")
def certificates_limits(ctx: typer.Context) -> None:
    """Read certificate enrollment and issuance limits."""

    def operation() -> Any:
        return run_authenticated(ctx, lambda auth: auth.certificates.get_limits())

    _render(ctx, run_command(ctx, operation))


@app.command("enrollment-data")
def certificates_enrollment_data(ctx: typer.Context) -> None:
    """Read subject data required for certificate enrollment CSR generation."""

    def operation() -> Any:
        return run_authenticated(ctx, lambda auth: auth.certificates.get_enrollment_data())

    _render(ctx, run_command(ctx, operation))


@app.command("enroll")
def certificates_enroll(
    ctx: typer.Context,
    name: Annotated[str, typer.Option("--name", help="Certificate name.")],
    csr_file: Annotated[Path, typer.Option("--csr-file", exists=True, dir_okay=False)],
    certificate_type: Annotated[str, typer.Option("--type", help="authentication or offline.")] = "authentication",
    valid_from: Annotated[str | None, typer.Option("--valid-from", help="ISO datetime.")] = None,
) -> None:
    """Request certificate enrollment with a base64-encoded CSR file."""

    def operation() -> Any:
        csr = csr_file.read_text(encoding="utf-8").strip()
        return run_authenticated(
            ctx,
            lambda auth: auth.certificates.enroll(
                certificate_name=name,
                certificate_type=certificate_type,
                csr=csr,
                valid_from=valid_from,
            ),
        )

    _render(ctx, run_command(ctx, operation))


@app.command("enrollment-status")
def certificates_enrollment_status(
    ctx: typer.Context,
    reference_number: Annotated[str, typer.Option("--reference")],
) -> None:
    """Fetch certificate enrollment status."""

    def operation() -> Any:
        return run_authenticated(
            ctx,
            lambda auth: auth.certificates.get_enrollment_status(reference_number=reference_number),
        )

    _render(ctx, run_command(ctx, operation))


@app.command("list")
def certificates_list(
    ctx: typer.Context,
    serial_number: Annotated[str | None, typer.Option("--serial-number")] = None,
    name: Annotated[str | None, typer.Option("--name")] = None,
    certificate_type: Annotated[str | None, typer.Option("--type")] = None,
    status: Annotated[str | None, typer.Option("--status")] = None,
    expires_after: Annotated[str | None, typer.Option("--expires-after", help="ISO datetime.")] = None,
    page_size: Annotated[int, typer.Option("--page-size", min=10, max=100)] = 10,
    page_offset: Annotated[int, typer.Option("--page-offset", min=0)] = 0,
    all_pages: Annotated[bool, typer.Option("--all", help="Fetch all pages.")] = False,
) -> None:
    """Query certificates."""

    def operation() -> Any:
        from ksef2.domain.models.certificates import validate_certificate_serial_number

        params = _offset_params(page_size, page_offset)
        serial = validate_certificate_serial_number(serial_number) if serial_number else None

        def list_certificates(auth: Any) -> Any:
            if all_pages:
                return list(
                    auth.certificates.all(
                        certificate_serial_number=serial,
                        name=name,
                        certificate_type=certificate_type,
                        status=status,
                        expires_after=expires_after,
                        params=params,
                    )
                )
            return auth.certificates.query(
                certificate_serial_number=serial,
                name=name,
                certificate_type=certificate_type,
                status=status,
                expires_after=expires_after,
                params=params,
            )

        return run_authenticated(ctx, list_certificates)

    _render(
        ctx,
        run_command(ctx, operation),
        items_key="certificates",
    )


@app.command("retrieve")
def certificates_retrieve(
    ctx: typer.Context,
    serial_numbers: Annotated[list[str], typer.Argument(help="Certificate serial number(s).")],
    output_dir: Annotated[
        Path | None,
        typer.Option("--out-dir", file_okay=False, help="Save certificates as PEM-ish text files."),
    ] = None,
) -> None:
    """Retrieve issued certificates by serial number."""

    def operation() -> Any:
        from ksef2.domain.models.certificates import validate_certificate_serial_number

        serials = [validate_certificate_serial_number(value) for value in serial_numbers]
        result = run_authenticated(
            ctx,
            lambda auth: auth.certificates.retrieve(certificate_serial_numbers=serials),
        )
        if output_dir:
            output_dir.mkdir(parents=True, exist_ok=True)
            for certificate in result.certificates:
                target = output_dir / f"{certificate.serial_number}.b64"
                target.write_text(certificate.base64_encoded_certificate + "\n", encoding="utf-8")
        return result

    _render(
        ctx,
        run_command(ctx, operation),
        items_key="certificates",
    )


@app.command("revoke")
def certificates_revoke(
    ctx: typer.Context,
    serial_number: Annotated[str, typer.Option("--serial-number")],
    reason: Annotated[str | None, typer.Option("--reason", help="unspecified, superseded, key_compromise.")] = None,
) -> None:
    """Revoke a certificate."""

    def operation() -> dict[str, str | None]:
        from ksef2.domain.models.certificates import validate_certificate_serial_number

        serial = validate_certificate_serial_number(serial_number)
        run_authenticated(
            ctx,
            lambda auth: auth.certificates.revoke(certificate_serial_number=serial, reason=reason),
        )
        return {"serial_number": serial_number, "reason": reason, "revoked": "true"}

    _render(ctx, run_command(ctx, operation))
