"""Local profile command group."""

from pathlib import Path
from typing import Annotated

import typer
from ksef2.domain.models.auth import ContextIdentifierTypeEnum

from ksef2_cli.config import (
    CliConfig,
    EnvironmentName,
    ProfileAuthConfig,
    ProfileAuthType,
    ProfileConfig,
    load_cli_config,
    write_cli_config,
)
from ksef2_cli.context import fail, get_settings, run_command
from ksef2_cli.results import (
    ProfileCurrent,
    ProfileListItem,
    ProfileListResult,
    ProfileSaved,
    ProfileSelected,
)

app = typer.Typer(help="Create, inspect, and select local CLI profiles.")


@app.command("create")
def profile_create(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Profile name.")],
    environment: Annotated[
        EnvironmentName | None,
        typer.Option(
            "--env",
            "-e",
            help="KSeF environment for this profile.",
            show_default=False,
        ),
    ] = None,
    nip: Annotated[
        str | None,
        typer.Option("--nip", help="Taxpayer/context NIP.", show_default=False),
    ] = None,
    token_env: Annotated[
        str | None,
        typer.Option(
            "--token-env",
            help="Environment variable containing a KSeF token.",
            show_default=False,
        ),
    ] = None,
    context_type: Annotated[
        ContextIdentifierTypeEnum | None,
        typer.Option(
            "--context-type", help="Token-auth context type.", show_default=False
        ),
    ] = None,
    test_certificate: Annotated[
        bool,
        typer.Option("--test-cert", help="Use SDK-generated TEST certificate auth."),
    ] = False,
    cert: Annotated[
        Path | None,
        typer.Option(
            "--cert",
            exists=True,
            dir_okay=False,
            help="PEM certificate.",
            show_default=False,
        ),
    ] = None,
    key: Annotated[
        Path | None,
        typer.Option(
            "--key",
            exists=True,
            dir_okay=False,
            help="PEM private key.",
            show_default=False,
        ),
    ] = None,
    key_password_env: Annotated[
        str | None,
        typer.Option(
            "--key-password-env",
            help="Environment variable containing the PEM key password.",
            show_default=False,
        ),
    ] = None,
    p12: Annotated[
        Path | None,
        typer.Option(
            "--p12",
            exists=True,
            dir_okay=False,
            help="PKCS#12/PFX archive.",
            show_default=False,
        ),
    ] = None,
    p12_password_env: Annotated[
        str | None,
        typer.Option(
            "--p12-password-env",
            help="Environment variable containing the PKCS#12/PFX password.",
            show_default=False,
        ),
    ] = None,
    activate: Annotated[
        bool,
        typer.Option(
            "--activate/--no-activate",
            help="Select this profile after saving it.",
        ),
    ] = True,
    force: Annotated[
        bool, typer.Option("--force", help="Replace an existing profile.")
    ] = False,
) -> None:
    """Create a profile and optionally select it."""

    def operation() -> ProfileSaved:
        if environment is None:
            fail("Provide --env.")
        if not nip:
            fail("Provide --nip.")

        auth = _profile_auth(
            token_env=token_env,
            context_type=context_type,
            test_certificate=test_certificate,
            cert=cert,
            key=key,
            key_password_env=key_password_env,
            p12=p12,
            p12_password_env=p12_password_env,
        )
        profile = ProfileConfig(environment=environment, nip=nip, auth=auth)
        config = _load_config(ctx)
        if name in config.profiles and not force:
            fail(
                f"Profile {name!r} already exists. "
                "Re-run with --force to replace it."
            )

        config.profiles[name] = profile
        if activate:
            config.active_profile = name
        _write_config(ctx, config)
        return ProfileSaved(
            name=name, active=config.active_profile == name, profile=profile
        )

    run_command(ctx, operation)


@app.command("list")
def profile_list(ctx: typer.Context) -> None:
    """List configured profiles."""

    def operation() -> ProfileListResult:
        config = _load_config(ctx)
        profiles = [
            ProfileListItem(
                name=name,
                active=name == config.active_profile,
                environment=profile.environment.value,
                nip=profile.nip,
                auth=profile.auth.type.value,
            )
            for name, profile in sorted(config.profiles.items())
        ]
        return ProfileListResult(profiles=profiles)

    run_command(ctx, operation)


@app.command("current")
def profile_current(ctx: typer.Context) -> None:
    """Show the active profile."""

    def operation() -> ProfileCurrent:
        config = _load_config(ctx)
        if config.active_profile is None:
            return ProfileCurrent()
        return ProfileCurrent(
            name=config.active_profile,
            profile=config.profiles[config.active_profile],
        )

    run_command(ctx, operation)


@app.command("show")
def profile_show(
    ctx: typer.Context,
    name: Annotated[str | None, typer.Argument(help="Profile name.")] = None,
) -> None:
    """Show one profile, or the active profile when no name is provided."""

    def operation() -> ProfileCurrent:
        config = _load_config(ctx)
        profile_name = name or config.active_profile
        if profile_name is None:
            fail("No active profile is selected.")
        profile = config.profiles.get(profile_name)
        if profile is None:
            fail(f"Profile {profile_name!r} is not defined.")
        return ProfileCurrent(name=profile_name, profile=profile)

    run_command(ctx, operation)


@app.command("use")
def profile_use(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Profile name.")],
) -> None:
    """Select the active profile."""

    def operation() -> ProfileSelected:
        config = _load_config(ctx)
        profile = config.profiles.get(name)
        if profile is None:
            fail(f"Profile {name!r} is not defined.")
        config.active_profile = name
        _write_config(ctx, config)
        return ProfileSelected(name=name, profile=profile)

    run_command(ctx, operation)


def _profile_auth(
    *,
    token_env: str | None,
    context_type: ContextIdentifierTypeEnum | None,
    test_certificate: bool,
    cert: Path | None,
    key: Path | None,
    key_password_env: str | None,
    p12: Path | None,
    p12_password_env: str | None,
) -> ProfileAuthConfig:
    selected = [
        token_env is not None,
        test_certificate,
        p12 is not None,
        cert is not None or key is not None,
    ]
    if selected.count(True) != 1:
        fail(
            "Provide exactly one auth method: "
            "--token-env, --test-cert, --cert/--key, or --p12."
        )

    if token_env is not None:
        return ProfileAuthConfig(
            type=ProfileAuthType.token,
            token_env=token_env,
            context_type=context_type,
        )
    if test_certificate:
        return ProfileAuthConfig(type=ProfileAuthType.test_certificate)
    if p12 is not None:
        return ProfileAuthConfig(
            type=ProfileAuthType.xades_p12,
            p12=p12,
            p12_password_env=p12_password_env,
        )
    return ProfileAuthConfig(
        type=ProfileAuthType.xades_pem,
        cert=cert,
        key=key,
        key_password_env=key_password_env,
    )


def _load_config(ctx: typer.Context) -> CliConfig:
    settings = get_settings(ctx)
    return load_cli_config(settings.config_file)


def _write_config(ctx: typer.Context, config: CliConfig) -> None:
    settings = get_settings(ctx)
    write_cli_config(settings.config_file, config, force=True)
