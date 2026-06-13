"""Local configuration command group."""

from __future__ import annotations

from typing import Annotated

import typer

from ksef2_cli.context import fail, get_settings, run_command
from ksef2_cli.local_config import LocalConfig, load_local_config, write_local_config
from ksef2_cli.rendering import _render

app = typer.Typer(help="Inspect and create local CLI defaults.")


@app.command("path")
def config_path(ctx: typer.Context) -> None:
    """Show the local config path used by this invocation."""

    def operation() -> dict[str, object]:
        settings = get_settings(ctx)
        return {
            "path": str(settings.config_file),
            "exists": settings.config_file.exists(),
            "loaded": settings.config_loaded,
        }

    _render(ctx, run_command(ctx, operation), title="Config Path")


@app.command("show")
def config_show(
    ctx: typer.Context,
    reveal_token: Annotated[
        bool,
        typer.Option("--reveal-token", help="Print token and credential passwords instead of redacting them."),
    ] = False,
) -> None:
    """Show local config values."""

    def operation() -> dict[str, object]:
        settings = get_settings(ctx)
        config = load_local_config(settings.config_file)
        return {
            "path": str(settings.config_file),
            "exists": settings.config_file.exists(),
            "auth": config.as_dict(redact_token=not reveal_token),
        }

    _render(ctx, run_command(ctx, operation), title="Config")


@app.command("init")
def config_init(
    ctx: typer.Context,
    nip: Annotated[str | None, typer.Option("--nip", help="Default taxpayer/context NIP.")] = None,
    token: Annotated[str | None, typer.Option("--token", help="Default KSeF authorization token.")] = None,
    context_type: Annotated[str, typer.Option("--context-type", help="Default token-auth context type.")] = "nip",
    force: Annotated[bool, typer.Option("--force", help="Overwrite an existing config file.")] = False,
) -> None:
    """Create a local config file with auth defaults."""

    def operation() -> dict[str, object]:
        settings = get_settings(ctx)
        if not nip and not token:
            fail("Provide at least --nip or --token.")
        config = LocalConfig(nip=nip, token=token, context_type=context_type)
        write_local_config(settings.config_file, config, force=force)
        return {
            "path": str(settings.config_file),
            "mode": "0600",
            "auth": config.as_dict(),
        }

    _render(ctx, run_command(ctx, operation), title="Created Config")
