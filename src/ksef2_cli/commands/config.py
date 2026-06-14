"""Local configuration command group."""

from __future__ import annotations

from typing import Annotated

import typer

from ksef2_cli.context import fail, get_settings, run_and_render
from ksef2_cli.config import LocalConfig, load_local_config, write_local_config

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

    run_and_render(ctx, operation)


@app.command("show")
def config_show(ctx: typer.Context) -> None:
    """Show local config values."""

    def operation() -> dict[str, object]:
        settings = get_settings(ctx)
        config = load_local_config(settings.config_file)
        return {
            "path": str(settings.config_file),
            "exists": settings.config_file.exists(),
            "auth": config.model_dump(mode="json", exclude_none=False),
        }

    run_and_render(ctx, operation)


@app.command("init")
def config_init(
    ctx: typer.Context,
    nip: Annotated[str | None, typer.Option("--nip", help="Default taxpayer/context NIP.")] = None,
    context_type: Annotated[str, typer.Option("--context-type", help="Default token-auth context type.")] = "nip",
    force: Annotated[bool, typer.Option("--force", help="Overwrite an existing config file.")] = False,
) -> None:
    """Create a local config file with non-secret defaults."""

    def operation() -> dict[str, object]:
        settings = get_settings(ctx)
        if not nip:
            fail("Provide --nip.")
        config = LocalConfig(nip=nip, context_type=context_type)
        write_local_config(settings.config_file, config, force=force)
        return {
            "path": str(settings.config_file),
            "mode": "0600",
            "auth": config.model_dump(mode="json", exclude_none=False),
        }

    run_and_render(ctx, operation)
