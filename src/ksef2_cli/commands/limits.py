"""KSeF limits command group."""

from enum import StrEnum
from pathlib import Path
from typing import Annotated

import typer
from ksef2.clients.authenticated import AuthenticatedClient
from ksef2.domain.models.limits import ApiRateLimits, ContextLimits, SubjectLimits

from ksef2_cli.context import (
    read_model,
    run_authenticated,
    run_authenticated_command,
    run_command,
)
from ksef2_cli.results import LimitReset, LimitUpdated, ProductionRateLimitsSet

app = typer.Typer(help="Read and manage effective KSeF limits.")


class LimitKindChoice(StrEnum):
    API = "api"
    CONTEXT = "context"
    SUBJECT = "subject"


@app.command("get")
def limits_get(
    ctx: typer.Context,
    kind: Annotated[LimitKindChoice, typer.Argument(help="api, context, or subject.")],
) -> None:
    """Read effective limits."""

    def read_limits(
        auth: AuthenticatedClient,
    ) -> ApiRateLimits | ContextLimits | SubjectLimits:
        match kind:
            case LimitKindChoice.API:
                return auth.limits.get_api_rate_limits()

            case LimitKindChoice.CONTEXT:
                return auth.limits.get_context_limits()

            case _:
                return auth.limits.get_subject_limits()

    run_authenticated_command(ctx, read_limits)


@app.command("set")
def limits_set(
    ctx: typer.Context,
    kind: Annotated[LimitKindChoice, typer.Argument(help="api, context, or subject.")],
    payload_file: Annotated[
        Path,
        typer.Option(
            "--payload", exists=True, dir_okay=False, help="JSON limits payload."
        ),
    ],
) -> None:
    """Set TEST-environment override limits from JSON."""

    def operation() -> LimitUpdated:
        def set_limits(auth: AuthenticatedClient) -> None:
            match kind:
                case LimitKindChoice.API:
                    auth.limits.set_api_rate_limits(
                        limits=read_model(ctx, payload_file, ApiRateLimits)
                    )

                case LimitKindChoice.CONTEXT:
                    auth.limits.set_session_limits(
                        limits=read_model(ctx, payload_file, ContextLimits)
                    )

                case _:
                    auth.limits.set_subject_limits(
                        limits=read_model(ctx, payload_file, SubjectLimits)
                    )

        run_authenticated(ctx, set_limits)
        return LimitUpdated(kind=kind.value)

    run_command(ctx, operation)


class ResetLimitKindChoice(StrEnum):
    API = "api"
    SESSION = "session"
    SUBJECT = "subject"


@app.command("reset")
def limits_reset(
    ctx: typer.Context,
    kind: Annotated[
        ResetLimitKindChoice, typer.Argument(help="api, session, or subject.")
    ],
) -> None:
    """Reset TEST-environment override limits."""

    def operation() -> LimitReset:
        def reset_limits(auth: AuthenticatedClient) -> None:
            match kind:
                case ResetLimitKindChoice.API:
                    auth.limits.reset_api_rate_limits()
                case ResetLimitKindChoice.SESSION:
                    auth.limits.reset_session_limits()
                case _:
                    auth.limits.reset_subject_limits()

        run_authenticated(ctx, reset_limits)
        return LimitReset(kind=kind.value)

    run_command(ctx, operation)


@app.command("production-rate-limits")
def limits_production_rate_limits(ctx: typer.Context) -> None:
    """Set TEST API rate limits to production-like values."""

    def operation() -> ProductionRateLimitsSet:
        def set_limits(auth: AuthenticatedClient) -> None:
            auth.limits.set_production_rate_limits()

        run_authenticated(ctx, set_limits)
        return ProductionRateLimitsSet()

    run_command(ctx, operation)
