"""Root Typer application and global option handling."""

from pathlib import Path
from typing import Annotated

import typer

from ksef2.domain.models.auth import ContextIdentifierTypeEnum

from ksef2_cli.commands import (
    auth,
    certificates,
    config as config_commands,
    encryption,
    limits,
    online,
    peppol,
    permissions,
    profile as profile_commands,
    sessions,
    testdata,
    tokens,
    batch,
)
from ksef2_cli.commands.invoices.group import app as invoices_app
from ksef2_cli.config import (
    EnvironmentName,
    OutputMode,
    RuntimeOverrides,
    resolve_settings,
)

app = typer.Typer(
    help="Command-line interface for Poland's KSeF v2 API using the ksef2 SDK.",
    context_settings={"help_option_names": ["-h", "--help"]},
    no_args_is_help=True,
)

app.add_typer(auth.app, name="auth")
app.add_typer(invoices_app, name="invoices")
app.add_typer(online.app, name="online")
app.add_typer(batch.app, name="batch")
app.add_typer(tokens.app, name="tokens")
app.add_typer(sessions.app, name="sessions")
app.add_typer(certificates.app, name="certificates")
app.add_typer(config_commands.app, name="config")
app.add_typer(profile_commands.app, name="profile")
app.add_typer(permissions.app, name="permissions")
app.add_typer(limits.app, name="limits")
app.add_typer(peppol.app, name="peppol")
app.add_typer(encryption.app, name="encryption")
app.add_typer(testdata.app, name="testdata")


@app.callback()
def root(
    context: typer.Context,
    environment: Annotated[
        EnvironmentName | None,
        typer.Option(
            "--env",
            "-e",
            help="KSeF environment. Defaults to the selected profile or production.",
            show_default=False,
        ),
    ] = None,
    output: Annotated[
        OutputMode | None,
        typer.Option(
            "--output",
            "-o",
            help="Output mode. Defaults to text.",
            show_default=False,
        ),
    ] = None,
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
        typer.Option("--no-config", help="Ignore local config profiles."),
    ] = False,
    profile: Annotated[
        str | None,
        typer.Option("--profile", help="Use a named profile for this invocation."),
    ] = None,
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
        ContextIdentifierTypeEnum | None,
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
        typer.Option(
            "--auth-poll-interval", min=0.1, help="Authentication polling interval."
        ),
    ] = None,
    max_poll_attempts: Annotated[
        int | None,
        typer.Option(
            "--auth-max-poll-attempts", min=1, help="Authentication polling attempts."
        ),
    ] = None,
) -> None:
    runtime_overrides = (
        context.obj if isinstance(context.obj, RuntimeOverrides) else None
    )

    try:
        context.obj = resolve_settings(
            environment=environment,
            output=output,
            json_output=json_output,
            verbose=verbose,
            config_file=config_file,
            no_config=no_config,
            profile=profile,
            nip=nip,
            token=token,
            context_type=context_type,
            test_certificate=test_certificate,
            cert=cert,
            key=key,
            key_password=key_password,
            p12=p12,
            p12_password=p12_password,
            poll_interval=poll_interval,
            max_poll_attempts=max_poll_attempts,
            runtime_overrides=runtime_overrides,
        )
    except (OSError, ValueError) as exc:
        raise typer.BadParameter(str(exc), param_hint="--config") from exc


def main() -> None:
    app()
