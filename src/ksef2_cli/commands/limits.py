"""KSeF limits command group."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any

import typer
from pydantic import BaseModel

from ksef2_cli.context import read_model, run_authenticated, run_and_render

app = typer.Typer(help='Read and manage effective KSeF limits.')


@app.command("get")
def limits_get(
    ctx: typer.Context,
    kind: Annotated[str, typer.Argument(help="api, context, or subject.")],
) -> None:
    """Read effective limits."""

    def operation() -> Any:
        def read_limits(auth: Any) -> Any:
            if kind == "api":
                return auth.limits.get_api_rate_limits()
            if kind == "context":
                return auth.limits.get_context_limits()
            if kind == "subject":
                return auth.limits.get_subject_limits()
            raise ValueError("kind must be one of: api, context, subject.")

        return run_authenticated(ctx, read_limits)

    run_and_render(ctx, operation)


@app.command("set")
def limits_set(
    ctx: typer.Context,
    kind: Annotated[str, typer.Argument(help="api, context, or subject.")],
    payload_file: Annotated[Path, typer.Option("--payload", exists=True, dir_okay=False, help="JSON limits payload.")],
) -> None:
    """Set TEST-environment override limits from JSON."""

    from ksef2.domain.models.limits import ApiRateLimits, ContextLimits, SubjectLimits

    model_map: dict[str, tuple[type[BaseModel], str]] = {
        "api": (ApiRateLimits, "set_api_rate_limits"),
        "context": (ContextLimits, "set_session_limits"),
        "subject": (SubjectLimits, "set_subject_limits"),
    }

    def operation() -> dict[str, str]:
        try:
            model_type, method_name = model_map[kind]
        except KeyError as exc:
            raise ValueError("kind must be one of: api, context, subject.") from exc
        limits = read_model(ctx, payload_file, model_type)
        run_authenticated(
            ctx,
            lambda auth: getattr(auth.limits, method_name)(limits=limits),
        )
        return {"kind": kind, "updated": "true"}

    run_and_render(ctx, operation)


@app.command("reset")
def limits_reset(
    ctx: typer.Context,
    kind: Annotated[str, typer.Argument(help="api, session, or subject.")],
) -> None:
    """Reset TEST-environment override limits."""

    def operation() -> dict[str, str]:
        def reset_limits(auth: Any) -> None:
            if kind == "api":
                auth.limits.reset_api_rate_limits()
            elif kind == "session":
                auth.limits.reset_session_limits()
            elif kind == "subject":
                auth.limits.reset_subject_limits()
            else:
                raise ValueError("kind must be one of: api, session, subject.")

        run_authenticated(ctx, reset_limits)
        return {"kind": kind, "reset": "true"}

    run_and_render(ctx, operation)


@app.command("production-rate-limits")
def limits_production_rate_limits(ctx: typer.Context) -> None:
    """Set TEST API rate limits to production-like values."""

    def operation() -> dict[str, str]:
        run_authenticated(ctx, lambda auth: auth.limits.set_production_rate_limits())
        return {"api_rate_limits": "production"}

    run_and_render(ctx, operation)
