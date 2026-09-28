import pytest
from ksef2 import Environment
from ksef2.core.exceptions import KSeFValidationError
from ksef2.profiles import (
    CliProfileConfig,
    ProfileAuthConfig,
    ProfileAuthType,
    ProfileConfig,
    render_profile_config,
)

from ksef2_cli.config import (
    PROFILE_ENV_VAR,
    load_cli_config,
    resolve_config_path,
    resolve_settings,
    write_cli_config,
)

CONFIG_FILE_MODE = 0o600


def test_cli_config_loads_profiles_and_resolves_active_settings(tmp_path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        """
        active_profile = "demo"

        [profiles.demo]
        environment = "test"
        nip = "6880313213"
        poll_interval = 1.5
        max_poll_attempts = 8

        [profiles.demo.auth]
        type = "xades_pem"
        cert = "~/cert.pem"
        key = "~/key.pem"
        key_password_env = "KSEF2_DEMO_KEY_PASSWORD"
        """,
        encoding="utf-8",
    )

    config = load_cli_config(config_path)
    settings = resolve_settings(config_file=config_path)

    assert config.active_profile == "demo"
    assert settings.profile_name == "demo"
    assert settings.environment is Environment.TEST
    assert settings.nip == "6880313213"
    assert settings.profile is not None
    assert str(settings.profile.auth.cert).endswith("cert.pem")
    assert str(settings.profile.auth.key).endswith("key.pem")
    assert settings.profile.auth.key_password_env == "KSEF2_DEMO_KEY_PASSWORD"
    assert settings.poll_interval is None
    assert settings.effective_poll_interval == 1.5
    assert settings.effective_auth_timeout == 12.0


def test_cli_config_defaults_to_production_without_a_profile(tmp_path) -> None:
    settings = resolve_settings(config_file=tmp_path / "missing.toml")

    assert settings.profile_name is None
    assert settings.profile is None
    assert settings.environment is Environment.PRODUCTION
    assert settings.effective_poll_interval == 1.0
    assert settings.effective_auth_timeout == 60.0


def test_profile_selection_uses_explicit_option_then_environment(tmp_path) -> None:
    config = CliProfileConfig(
        active_profile="demo",
        profiles={
            "demo": ProfileConfig(
                environment="test",
                nip="1111111111",
                auth=ProfileAuthConfig(type=ProfileAuthType.TEST_CERTIFICATE),
            ),
            "prod": ProfileConfig(
                environment="production",
                nip="2222222222",
                auth=ProfileAuthConfig(
                    type=ProfileAuthType.TOKEN,
                    token_env="KSEF2_PROD_TOKEN",
                    context_type="nip",
                ),
            ),
        },
    )
    config_path = tmp_path / "config.toml"
    write_cli_config(config_path, config)

    env_settings = resolve_settings(
        config_file=config_path,
        environ={PROFILE_ENV_VAR: "prod"},
    )
    explicit_settings = resolve_settings(
        config_file=config_path,
        profile="demo",
        environ={PROFILE_ENV_VAR: "prod"},
    )

    assert env_settings.profile_name == "prod"
    assert env_settings.environment is Environment.PRODUCTION
    assert env_settings.profile is not None
    assert env_settings.profile.auth.token_env == "KSEF2_PROD_TOKEN"
    assert explicit_settings.profile_name == "demo"
    assert explicit_settings.profile is not None
    assert explicit_settings.profile.auth.type is ProfileAuthType.TEST_CERTIFICATE


def test_command_auth_options_are_kept_apart_from_the_profile(tmp_path) -> None:
    config_path = tmp_path / "config.toml"
    cert_path = tmp_path / "cert.pem"
    key_path = tmp_path / "key.pem"
    cert_path.write_text("cert", encoding="utf-8")
    key_path.write_text("key", encoding="utf-8")
    write_cli_config(
        config_path,
        CliProfileConfig(
            active_profile="demo",
            profiles={
                "demo": ProfileConfig(
                    environment="demo",
                    nip="1111111111",
                    auth=ProfileAuthConfig(
                        type=ProfileAuthType.XADES_PEM,
                        cert=cert_path,
                        key=key_path,
                    ),
                )
            },
        ),
    )

    token_settings = resolve_settings(config_file=config_path, token="direct-token")
    pem_settings = resolve_settings(config_file=config_path, key_password="secret")

    assert token_settings.token == "direct-token"
    assert token_settings.cert is None
    assert token_settings.profile is not None
    assert token_settings.profile.auth.cert == cert_path
    assert pem_settings.key_password == "secret"
    assert pem_settings.profile is not None
    assert pem_settings.profile.auth.key == key_path


def test_cli_config_missing_file_returns_empty(tmp_path) -> None:
    assert load_cli_config(tmp_path / "missing.toml") == CliProfileConfig()


def test_write_cli_config_refuses_overwrite_without_force(tmp_path) -> None:
    config_path = tmp_path / "config.toml"
    write_cli_config(config_path, CliProfileConfig())

    with pytest.raises(FileExistsError):
        write_cli_config(config_path, CliProfileConfig(active_profile=None))

    config = CliProfileConfig(
        active_profile="demo",
        profiles={
            "demo": ProfileConfig(
                environment="test",
                nip="5261040828",
                auth=ProfileAuthConfig(type=ProfileAuthType.TEST_CERTIFICATE),
            )
        },
    )
    write_cli_config(config_path, config, force=True)
    assert 'active_profile = "demo"' in config_path.read_text(encoding="utf-8")
    assert oct(config_path.stat().st_mode & 0o777) == oct(CONFIG_FILE_MODE)


def test_rendered_profile_config_round_trips_through_the_loader(tmp_path) -> None:
    config = CliProfileConfig(
        active_profile="demo",
        profiles={
            "demo": ProfileConfig(
                environment="test",
                nip="5261040828",
                auth=ProfileAuthConfig(type=ProfileAuthType.TEST_CERTIFICATE),
            )
        },
    )
    rendered = render_profile_config(config)

    assert 'active_profile = "demo"' in rendered
    assert "[profiles.demo]" in rendered
    assert "[profiles.demo.auth]" in rendered
    assert 'type = "test_certificate"' in rendered

    config_path = tmp_path / "config.toml"
    config_path.write_text(rendered, encoding="utf-8")
    assert load_cli_config(config_path) == config


def test_invalid_profile_config_shapes_raise_validation_errors(tmp_path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text('active_profile = "missing"\n', encoding="utf-8")
    with pytest.raises(KSeFValidationError, match="Active profile"):
        load_cli_config(config_path)

    config_path.write_text(
        """
        [profiles.demo]
        nip = "5261040828"

        [profiles.demo.auth]
        type = "test_certificate"
        """,
        encoding="utf-8",
    )
    with pytest.raises(KSeFValidationError, match="Field required"):
        load_cli_config(config_path)

    config_path.write_text(
        """
        [profiles.demo]
        environment = "test"
        nip = "5261040828"

        [profiles.demo.auth]
        type = "token"
        """,
        encoding="utf-8",
    )
    with pytest.raises(KSeFValidationError, match="token_env"):
        load_cli_config(config_path)

    config_path.write_text(
        """
        [profiles.demo]
        environment = "test"
        nip = "5261040828"
        poll_interval = 0

        [profiles.demo.auth]
        type = "test_certificate"
        """,
        encoding="utf-8",
    )
    with pytest.raises(KSeFValidationError, match="greater than or equal to 0.1"):
        load_cli_config(config_path)


def test_resolve_settings_rejects_unknown_profile_and_no_config_profile(
    tmp_path,
) -> None:
    config_path = tmp_path / "config.toml"
    write_cli_config(config_path, CliProfileConfig())

    with pytest.raises(KSeFValidationError, match="is not defined"):
        resolve_settings(config_file=config_path, profile="missing")

    with pytest.raises(ValueError, match="--profile cannot be used"):
        resolve_settings(config_file=config_path, no_config=True, profile="missing")


def test_resolve_settings_ignores_profiles_with_no_config(tmp_path) -> None:
    config_path = tmp_path / "config.toml"
    write_cli_config(
        config_path,
        CliProfileConfig(
            active_profile="demo",
            profiles={
                "demo": ProfileConfig(
                    environment="demo",
                    nip="1111111111",
                    auth=ProfileAuthConfig(type=ProfileAuthType.TEST_CERTIFICATE),
                )
            },
        ),
    )

    settings = resolve_settings(
        config_file=config_path,
        no_config=True,
        environ={PROFILE_ENV_VAR: "demo"},
    )

    assert settings.profile_name is None
    assert settings.profile is None
    assert settings.environment is Environment.PRODUCTION


def test_config_path_resolution(tmp_path, monkeypatch) -> None:
    explicit = tmp_path / "explicit.toml"
    assert resolve_config_path(explicit) == explicit

    monkeypatch.setenv("KSEF2_CONFIG", str(tmp_path / "from-env.toml"))
    assert resolve_config_path(None) == tmp_path / "from-env.toml"

    monkeypatch.delenv("KSEF2_CONFIG")
    xdg_home = tmp_path / "xdg"
    monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg_home))
    assert resolve_config_path(None) == xdg_home / "ksef2" / "config.toml"

    legacy_dir = xdg_home / "ksef2-cli"
    legacy_dir.mkdir(parents=True)
    legacy_config = legacy_dir / "config.toml"
    legacy_config.write_text("", encoding="utf-8")
    assert resolve_config_path(None) == legacy_config
