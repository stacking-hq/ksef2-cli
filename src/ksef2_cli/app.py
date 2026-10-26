"""Root Typer application and global option handling."""

import sys
from contextvars import ContextVar
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Annotated, Any, Sequence

import click
import typer
from click.core import ParameterSource
from typer.main import get_command

from ksef2 import KSeFException
from ksef2.models import ContextIdentifierTypeEnum
from rich.console import Console
from typer.core import TyperGroup

from ksef2_cli.commands import (
    auth,
    batch,
    certificates,
    collective,
    encryption,
    fa3,
    limits,
    online,
    peppol,
    permissions,
    sessions,
    testdata,
    tokens,
)
from ksef2_cli.commands import (
    config as config_commands,
)
from ksef2_cli.commands import (
    profile as profile_commands,
)
from ksef2_cli.commands.invoices.group import app as invoices_app
from ksef2_cli.config import (
    AUTH_ENV_VARS,
    EnvironmentName,
    OutputMode,
    RuntimeOverrides,
    resolve_settings,
)
from ksef2_cli.exceptions import UsageError, error_from_exception, render_cli_error

_raw_argv: ContextVar[tuple[str, ...] | None] = ContextVar("raw_argv", default=None)

_json_requested: ContextVar[bool] = ContextVar("json_requested", default=False)


class CliGroup(TyperGroup):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._hide_none_defaults(self)

    @staticmethod
    def _hide_none_defaults(command: click.Command) -> None:
        for parameter in command.params:
            if isinstance(parameter, click.Option) and parameter.default is None:
                parameter.show_default = False
        if isinstance(command, click.Group):
            for child in command.commands.values():
                CliGroup._hide_none_defaults(child)

    def main(
        self,
        args: Sequence[str] | None = None,
        prog_name: str | None = None,
        complete_var: str | None = None,
        standalone_mode: bool = True,
        **extra: Any,
    ) -> Any:
        arguments = list(sys.argv[1:] if args is None else args)
        argv_token = _raw_argv.set(tuple(arguments))
        # Parse root options without callbacks or type conversion, so parse errors
        # still use the requested output mode. Click handles values and -ojson.
        context = click.Context(self, resilient_parsing=True)
        parser = self.make_parser(context)
        options, _, _ = parser.parse_args(arguments.copy())
        json_mode = bool(options.get("json_output")) or options.get("output") == "json"
        token = _json_requested.set(json_mode)
        try:
            try:
                result = super().main(
                    arguments, prog_name, complete_var, standalone_mode=False, **extra
                )
            except click.ClickException as exc:
                if not json_mode:
                    if not standalone_mode:
                        raise
                    exc.show()
                else:
                    render_cli_error(
                        UsageError(exc.format_message(), exit_code=exc.exit_code),
                        console=Console(stderr=True),
                    )
                result = exc.exit_code
            except click.Abort as exc:
                error = error_from_exception(exc)
                render_cli_error(error, console=Console(stderr=True))
                result = error.exit_code
            if standalone_mode:
                raise SystemExit(result if isinstance(result, int) else 0)
            return result
        finally:
            _json_requested.reset(token)
            _raw_argv.reset(argv_token)


def _show_version(value: bool) -> None:
    if value:
        versions = []
        for package in ("ksef2-cli", "ksef2"):
            try:
                installed = version(package)
            except PackageNotFoundError:
                installed = "unknown"
            versions.append(f"{package} {installed}")
        typer.echo("\n".join(versions))
        raise typer.Exit()


app = typer.Typer(
    cls=CliGroup,
    help="Command-line interface for Poland's KSeF v2 API using the ksef2 SDK.",
    context_settings={"help_option_names": ["-h", "--help"], "show_default": False},
    no_args_is_help=True,
)

app.add_typer(auth.app, name="auth")
app.add_typer(invoices_app, name="invoices")
app.add_typer(fa3.app, name="fa3")
app.add_typer(online.app, name="online")
app.add_typer(batch.app, name="batch")
app.add_typer(tokens.app, name="tokens")
app.add_typer(sessions.app, name="sessions")
app.add_typer(certificates.app, name="certificates")
app.add_typer(collective.app, name="collective")
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
    version_flag: Annotated[
        bool,
        typer.Option(
            "--version",
            callback=_show_version,
            is_eager=True,
            help="Show CLI and SDK versions.",
        ),
    ] = False,
    environment: Annotated[
        EnvironmentName | None,
        typer.Option(
            "--env",
            "-e",
            help="KSeF environment. Defaults to the selected profile or TEST.",
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
            help="Local config file. Defaults to ~/.config/ksef2/config.toml.",
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
    auth_state: Annotated[
        Path | None,
        typer.Option(
            "--auth-state",
            envvar="KSEF2_AUTH_STATE",
            exists=True,
            dir_okay=False,
            help="Reuse saved auth state from --save-state instead of authenticating.",
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
    auth_timeout: Annotated[
        float | None,
        typer.Option(
            "--auth-timeout",
            min=1.0,
            help="Seconds to wait for authentication to complete.",
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
            auth_state=auth_state,
            test_certificate=test_certificate,
            cert=cert,
            key=key,
            key_password=key_password,
            p12=p12,
            p12_password=p12_password,
            poll_interval=poll_interval,
            auth_timeout=auth_timeout,
            runtime_overrides=runtime_overrides,
            auth_env_params=frozenset(
                name
                for name in AUTH_ENV_VARS
                if context.get_parameter_source(name) is ParameterSource.ENVIRONMENT
            ),
        )
    except (OSError, ValueError, KSeFException) as exc:
        raise typer.BadParameter(str(exc), param_hint="--config") from exc


def _requests_json(argv: list[str]) -> bool:
    """Read global output flags without mistaking option values for commands."""
    parameters = {
        option: parameter
        for parameter in get_command(app).params
        for option in parameter.opts
    }
    json_output = False
    output = None
    index = 0
    while index < len(argv):
        argument = argv[index]
        if not argument.startswith("-") or argument == "--":
            break
        option, separator, value = argument.partition("=")
        parameter = parameters.get(option)
        if parameter is not None and not parameter.is_flag and not separator:
            index += 1
            value = argv[index] if index < len(argv) else ""
        if option == "--json":
            json_output = True
        elif option in {"--output", "-o"}:
            output = value
        index += 1
    return json_output or output == "json"


def main() -> None:
    if not _requests_json(sys.argv[1:]):
        app()
        return

    from ksef2_cli.exceptions import error_from_exception, UsageError, render_cli_error
    from ksef2_cli.renderers import console

    try:
        exit_code = app(standalone_mode=False)
    except (click.Abort, KeyboardInterrupt, EOFError) as exc:
        error = error_from_exception(exc)
        render_cli_error(error, console=console, json_output=True)
        raise SystemExit(error.exit_code) from exc
    except click.ClickException as exc:
        error = UsageError(exc.format_message(), exit_code=exc.exit_code)
        render_cli_error(error, console=console, json_output=True)
        raise SystemExit(exc.exit_code) from exc
    raise SystemExit(exit_code)
