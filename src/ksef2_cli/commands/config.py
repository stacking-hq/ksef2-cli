"""Local configuration command group."""

from typing import Annotated

import typer

from ksef2_cli.context import get_settings, run_command
from ksef2_cli.config import CliConfig, load_cli_config, write_cli_config
from ksef2_cli.results import ConfigInitialized, ConfigPathResult, ConfigShowResult

app = typer.Typer(help="Inspect and create the local CLI config file.")


@app.command("path")
def config_path(ctx: typer.Context) -> None:
    """Show the local config path used by this invocation."""

    def operation() -> ConfigPathResult:
        settings = get_settings(ctx)
        return ConfigPathResult(
            path=settings.config_file,
            exists=settings.config_file.exists(),
            loaded=settings.config_loaded,
        )

    run_command(ctx, operation)


@app.command("show")
def config_show(ctx: typer.Context) -> None:
    """Show local config values."""

    def operation() -> ConfigShowResult:
        settings = get_settings(ctx)
        config = load_cli_config(settings.config_file)
        return ConfigShowResult(
            path=settings.config_file,
            exists=settings.config_file.exists(),
            config=config,
        )

    run_command(ctx, operation)


@app.command("init")
def config_init(
    ctx: typer.Context,
    force: Annotated[
        bool, typer.Option("--force", help="Overwrite an existing config file.")
    ] = False,
) -> None:
    """Create an empty local config file."""

    def operation() -> ConfigInitialized:
        settings = get_settings(ctx)
        config = CliConfig()
        write_cli_config(settings.config_file, config, force=force)
        return ConfigInitialized(path=settings.config_file, mode="0600", config=config)

    run_command(ctx, operation)
