from __future__ import annotations

import pytest

from ksef2_cli.config import secret_value, LocalConfig, default_config_path, resolve_config_path, load_local_config, \
    write_local_config, render_local_config


def test_local_config_loads_auth_defaults(tmp_path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        """
        [auth]
        nip = "5261040828"
        token = "secret-token"
        context_type = "nip"
        cert = "~/cert.pem"
        key = "~/key.pem"
        key_password = "secret"
        p12 = "~/auth.p12"
        p12_password = "p12-secret"
        poll_interval = 1.5
        max_poll_attempts = 12
        """,
        encoding="utf-8",
    )

    config = load_local_config(config_path)

    assert config.nip == "5261040828"
    assert config.token is not None
    assert secret_value(config.token) == "secret-token"
    assert config.context_type == "nip"
    assert str(config.cert).endswith("cert.pem")
    assert str(config.key).endswith("key.pem")
    assert str(config.p12).endswith("auth.p12")
    assert config.key_password is not None
    assert secret_value(config.key_password) == "secret"
    assert config.p12_password is not None
    assert secret_value(config.p12_password) == "p12-secret"
    assert config.poll_interval == 1.5
    assert config.max_poll_attempts == 12


def test_local_config_serializes_secret_values() -> None:
    config = LocalConfig(
        nip="5261040828",
        token="secret-token",
        key_password="key-secret",
        p12_password="p12-secret",
    )

    assert str(config.token) == "**********"

    data = config.model_dump(mode="json", exclude_none=True)
    assert data["token"] == "**********"
    assert data["key_password"] == "**********"
    assert data["p12_password"] == "**********"

    rendered = render_local_config(config)
    assert 'token = "**********"' in rendered
    assert 'key_password = "**********"' in rendered
    assert 'p12_password = "**********"' in rendered
    assert "secret-token" not in rendered
    assert "key-secret" not in rendered
    assert "p12-secret" not in rendered


def test_local_config_missing_file_returns_empty(tmp_path) -> None:
    assert load_local_config(tmp_path / "missing.toml") == LocalConfig()


def test_write_local_config_refuses_overwrite_without_force(tmp_path) -> None:
    config_path = tmp_path / "config.toml"
    write_local_config(config_path, LocalConfig(nip="1"))

    with pytest.raises(FileExistsError):
        write_local_config(config_path, LocalConfig(nip="2"))

    write_local_config(config_path, LocalConfig(nip="2"), force=True)
    assert "nip = \"2\"" in config_path.read_text(encoding="utf-8")


def test_invalid_config_shapes_raise_value_error(tmp_path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text("[auth]\nnip = 123\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Input should be a valid string"):
        load_local_config(config_path)

    config_path.write_text("[auth]\ntoken = 123\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Input should be a valid string"):
        load_local_config(config_path)

    config_path.write_text("auth = 123\n", encoding="utf-8")
    with pytest.raises(ValueError, match="must be a table"):
        load_local_config(config_path)

    config_path.write_text("[auth]\nmax_poll_attempts = 1.2\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Input should be a valid integer"):
        load_local_config(config_path)


def test_config_path_resolution(tmp_path) -> None:
    env_path = tmp_path / "from-env.toml"
    assert default_config_path({"KSEF2_CONFIG": str(env_path)}) == env_path

    explicit = tmp_path / "explicit.toml"
    assert resolve_config_path(explicit) == explicit

    assert default_config_path({"XDG_CONFIG_HOME": str(tmp_path / "xdg")}) == (
        tmp_path / "xdg" / "ksef2-cli" / "config.toml"
    )
