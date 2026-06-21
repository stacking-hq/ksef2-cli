"""Command result rendering entry point."""

import sys

import typer
from rich.console import Console

from ksef2_cli.config import OutputMode
from ksef2_cli.renderers.json import json_renderer
from ksef2_cli.renderers.text import plain_renderer
from ksef2_cli.renderers.rows import register_all

console = Console(stderr=True, highlight=False)
register_all()


def render(ctx: typer.Context, result: object) -> None:
    """Render a command result to stdout according to CLI settings."""

    from ksef2_cli.context import get_settings

    settings = get_settings(ctx)
    text = render_text(settings.output, result)
    if text:
        sys.stdout.write(text)
        sys.stdout.write("\n")


def render_text(output: OutputMode, result: object) -> str:
    """Render a command result according to an explicit output mode."""

    renderer = json_renderer if output is OutputMode.json else plain_renderer
    return renderer.render(result)
