from pathlib import Path

import pytest

from ksef2_cli.config import (
    CONFIG_FILE_MODE,
    PROFILE_ENV_VAR,
    CliConfig,
    ProfileAuthConfig,
    ProfileAuthType,
    ProfileConfig,
    default_config_path,
    load_cli_config,
    render_cli_config,
    resolve_config_path,
    resolve_settings,
    write_cli_config,
)


def test_cli_config_loads_profiles_and_resolves_active_settings(tmp_path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        """
        active_profile = "demo"

        [profiles.demo]
        environment = "test"
        nip = "6880313213"
        poll_interval = 1.5
        max_poll_attempts = 12

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
    assert settings.environment == "test"
    assert settings.nip == "6880313213"
    assert str(settings.cert).endswith("cert.pem")
    assert str(settings.key).endswith("key.pem")
    assert settings.key_password_env == "KSEF2_DEMO_KEY_PASSWORD"
    assert settings.poll_interval == 1.5
    assert settings.max_poll_attempts == 12


def test_profile_selection_uses_explicit_option_then_environment(tmp_path) -> None:
    config = CliConfig(
        active_profile="demo",
        profiles={
            "demo": ProfileConfig(
                environment="test",
                nip="1111111111",
                auth=ProfileAuthConfig(type=ProfileAuthType.test_certificate),
            ),
            "prod": ProfileConfig(
                environment="production",
                nip="2222222222",
                auth=ProfileAuthConfig(
                    type=ProfileAuthType.token,
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
    assert env_settings.token_env == "KSEF2_PROD_TOKEN"
    assert explicit_settings.profile_name == "demo"
    assert explicit_settings.test_certificate is True


def test_command_options_override_profile_auth(tmp_path) -> None:
    config_path = tmp_path / "config.toml"
    cert_path = tmp_path / "cert.pem"
    key_path = tmp_path / "key.pem"
    cert_path.write_text("cert", encoding="utf-8")
    key_path.write_text("key", encoding="utf-8")
    write_cli_config(
        config_path,
        CliConfig(
            active_profile="demo",
            profiles={
                "demo": ProfileConfig(
                    environment="test",
                    nip="1111111111",
                    auth=ProfileAuthConfig(
                        type=ProfileAuthType.xades_pem,
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
    assert token_settings.key is None
    assert pem_settings.cert == cert_path
    assert pem_settings.key == key_path
    assert pem_settings.key_password == "secret"


def test_cli_config_missing_file_returns_empty(tmp_path) -> None:
    assert load_cli_config(tmp_path / "missing.toml") == CliConfig()


def test_write_cli_config_refuses_overwrite_without_force(tmp_path) -> None:
    config_path = tmp_path / "config.toml"
    write_cli_config(config_path, CliConfig())

    with pytest.raises(FileExistsError):
        write_cli_config(config_path, CliConfig(active_profile=None))

    config = CliConfig(
        active_profile="demo",
        profiles={
            "demo": ProfileConfig(
                environment="test",
                nip="5261040828",
                auth=ProfileAuthConfig(type=ProfileAuthType.test_certificate),
            )
        },
    )
    write_cli_config(config_path, config, force=True)
    assert 'active_profile = "demo"' in config_path.read_text(encoding="utf-8")
    assert oct(config_path.stat().st_mode & 0o777) == oct(CONFIG_FILE_MODE)


def test_render_cli_config_uses_profile_shape() -> None:
    config = CliConfig(
        active_profile="demo",
        profiles={
            "demo": ProfileConfig(
                environment="test",
                nip="5261040828",
                auth=ProfileAuthConfig(type=ProfileAuthType.test_certificate),
            )
        },
    )

    rendered = render_cli_config(config)

    assert 'active_profile = "demo"' in rendered
    assert "[profiles.demo]" in rendered
    assert "[profiles.demo.auth]" in rendered
    assert 'type = "test_certificate"' in rendered


def test_invalid_profile_config_shapes_raise_value_error(tmp_path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text('active_profile = "missing"\n', encoding="utf-8")
    with pytest.raises(ValueError, match="Active profile"):
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
    with pytest.raises(ValueError, match="Field required"):
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
    with pytest.raises(ValueError, match="token_env"):
        load_cli_config(config_path)

    config_path.write_text(
        """
        [profiles.demo]
        environment = "test"
        nip = 123

        [profiles.demo.auth]
        type = "test_certificate"
        """,
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="Input should be a valid string"):
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
    with pytest.raises(ValueError, match="greater than or equal to 0.1"):
        load_cli_config(config_path)


def test_resolve_settings_rejects_unknown_profile_and_no_config_profile(tmp_path) -> None:
    config_path = tmp_path / "config.toml"
    write_cli_config(config_path, CliConfig())

    with pytest.raises(ValueError, match="not defined"):
        resolve_settings(config_file=config_path, profile="missing")

    with pytest.raises(ValueError, match="--profile cannot be used"):
        resolve_settings(config_file=config_path, no_config=True, profile="missing")


def test_config_path_resolution(tmp_path) -> None:
    env_path = tmp_path / "from-env.toml"
    assert default_config_path({"KSEF2_CONFIG": str(env_path)}) == env_path

    explicit = tmp_path / "explicit.toml"
    assert resolve_config_path(explicit) == explicit

    assert default_config_path({"XDG_CONFIG_HOME": str(tmp_path / "xdg")}) == (
        tmp_path / "xdg" / "ksef2-cli" / "config.toml"
    )
