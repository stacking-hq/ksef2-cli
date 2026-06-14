"""Root Typer application and global option handling."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from ksef2_cli.commands import (
    auth,
    batch,
    certificates,
    config as config_commands,
    encryption,
    invoices,
    limits,
    online,
    peppol,
    permissions,
    sessions,
    testdata,
    tokens,
)
from ksef2_cli.config import EnvironmentName, OutputMode, RuntimeOverrides, Settings
from ksef2_cli.local_config import load_local_config, resolve_config_path, secret_value

app = typer.Typer(
    help="Command-line interface for Poland's KSeF v2 API using the ksef2 SDK.",
    context_settings={"help_option_names": ["-h", "--help"]},
    no_args_is_help=True,
)

app.add_typer(auth.app, name="auth")
app.add_typer(invoices.app, name="invoices")
app.add_typer(online.app, name="online")
app.add_typer(batch.app, name="batch")
app.add_typer(tokens.app, name="tokens")
app.add_typer(sessions.app, name="sessions")
app.add_typer(certificates.app, name="certificates")
app.add_typer(config_commands.app, name="config")
app.add_typer(permissions.app, name="permissions")
app.add_typer(limits.app, name="limits")
app.add_typer(peppol.app, name="peppol")
app.add_typer(encryption.app, name="encryption")
app.add_typer(testdata.app, name="testdata")


@app.callback()
def root(
    ctx: typer.Context,
    environment: Annotated[
        EnvironmentName,
        typer.Option("--env", "-e", help="KSeF environment."),
    ] = EnvironmentName.production,
    output: Annotated[
        OutputMode,
        typer.Option("--output", "-o", help="Output mode."),
    ] = OutputMode.table,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Shortcut for --output json."),
    ] = False,
    verbose: Annotated[
        bool,
        typer.Option("--verbose", "-v", help="Show tracebacks for CLI errors."),
    ] = False,
    config_file: Annotated[
        Path | None,
        typer.Option(
            "--config",
            envvar="KSEF2_CONFIG",
            dir_okay=False,
            help="Local config file. Defaults to ~/.config/ksef2-cli/config.toml.",
        ),
    ] = None,
    no_config: Annotated[
        bool,
        typer.Option("--no-config", help="Ignore local config file defaults."),
    ] = False,
    nip: Annotated[
        str | None,
        typer.Option("--nip", envvar="KSEF2_NIP", help="Taxpayer/context NIP."),
    ] = None,
    token: Annotated[
        str | None,
        typer.Option(
            "--token",
            "--ksef-token",
            envvar="KSEF2_TOKEN",
            help="KSeF authorization token for token authentication.",
        ),
    ] = None,
    context_type: Annotated[
        str | None,
        typer.Option(
            "--context-type",
            envvar="KSEF2_CONTEXT_TYPE",
            help="Token-auth context type.",
        ),
    ] = None,
    test_certificate: Annotated[
        bool,
        typer.Option(
            "--test-cert",
            envvar="KSEF2_TEST_CERT",
            help="Authenticate with an SDK-generated TEST certificate.",
        ),
    ] = False,
    cert: Annotated[
        Path | None,
        typer.Option(
            "--cert",
            envvar="KSEF2_CERT",
            exists=True,
            dir_okay=False,
            help="PEM certificate for XAdES authentication.",
        ),
    ] = None,
    key: Annotated[
        Path | None,
        typer.Option(
            "--key",
            envvar="KSEF2_KEY",
            exists=True,
            dir_okay=False,
            help="PEM private key for XAdES authentication.",
        ),
    ] = None,
    key_password: Annotated[
        str | None,
        typer.Option(
            "--key-password",
            envvar="KSEF2_KEY_PASSWORD",
            help="Password for an encrypted PEM private key.",
        ),
    ] = None,
    p12: Annotated[
        Path | None,
        typer.Option(
            "--p12",
            envvar="KSEF2_P12",
            exists=True,
            dir_okay=False,
            help="PKCS#12/PFX archive for XAdES authentication.",
        ),
    ] = None,
    p12_password: Annotated[
        str | None,
        typer.Option(
            "--p12-password",
            envvar="KSEF2_P12_PASSWORD",
            help="Password for a PKCS#12/PFX archive.",
        ),
    ] = None,
    poll_interval: Annotated[
        float | None,
        typer.Option("--auth-poll-interval", min=0.1, help="Authentication polling interval."),
    ] = None,
    max_poll_attempts: Annotated[
        int | None,
        typer.Option("--auth-max-poll-attempts", min=1, help="Authentication polling attempts."),
    ] = None,
) -> None:
    runtime_overrides = ctx.obj if isinstance(ctx.obj, RuntimeOverrides) else None
    resolved_config_file = resolve_config_path(config_file)
    try:
        local_config = load_local_config(resolved_config_file) if not no_config else None
    except (OSError, ValueError) as exc:
        raise typer.BadParameter(str(exc), param_hint="--config") from exc
    ctx.obj = Settings(
        config_file=resolved_config_file,
        config_loaded=bool(local_config and resolved_config_file.exists()),
        environment=environment,
        output=OutputMode.json if json_output else output,
        verbose=verbose,
        nip=nip or (local_config.nip if local_config else None),
        token=token or (secret_value(local_config.token) if local_config else None),
        context_type=context_type or (local_config.context_type if local_config else None) or "nip",
        test_certificate=test_certificate,
        cert=cert or (local_config.cert if local_config else None),
        key=key or (local_config.key if local_config else None),
        key_password=key_password or (secret_value(local_config.key_password) if local_config else None),
        p12=p12 or (local_config.p12 if local_config else None),
        p12_password=p12_password or (secret_value(local_config.p12_password) if local_config else None),
        poll_interval=poll_interval or (local_config.poll_interval if local_config else None) or 1.0,
        max_poll_attempts=max_poll_attempts or (local_config.max_poll_attempts if local_config else None) or 60,
        runtime_overrides=runtime_overrides,
    )


def main() -> None:
    app()
