from __future__ import annotations

from conftest import cli_args, payload
from ksef2_cli.app import app
from ksef2_cli.local_config import CONFIG_FILE_MODE, LocalConfig, render_local_config


def test_config_show_redacts_token(runner, tmp_path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        render_local_config(
            LocalConfig(nip="5261040828", token="very-secret-token", context_type="nip")
        ),
        encoding="utf-8",
    )

    result = runner.invoke(app, ["--json", "--config", str(config_path), "config", "show"])
    data = payload(result)

    assert data["path"] == str(config_path)
    assert data["exists"] is True
    assert data["auth"]["nip"] == "5261040828"
    assert data["auth"]["token"] == "very...oken"


def test_config_show_can_reveal_token(runner, tmp_path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        render_local_config(LocalConfig(token="very-secret-token")),
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        ["--json", "--config", str(config_path), "config", "show", "--reveal-token"],
    )

    assert payload(result)["auth"]["token"] == "very-secret-token"


def test_config_path_and_init(runner, tmp_path) -> None:
    config_path = tmp_path / "nested" / "config.toml"

    path_result = runner.invoke(app, cli_args("--config", str(config_path), "config", "path"))
    assert payload(path_result) == {
        "path": str(config_path),
        "exists": False,
        "loaded": False,
    }

    init_result = runner.invoke(
        app,
        cli_args("--config", str(config_path), "config", "init", "--nip", "5261040828"),
    )
    init_data = payload(init_result)

    assert init_data["path"] == str(config_path)
    assert init_data["mode"] == "0600"
    assert oct(config_path.stat().st_mode & 0o777) == oct(CONFIG_FILE_MODE)


def test_config_init_requires_value(runner, tmp_path) -> None:
    result = runner.invoke(
        app,
        cli_args("--config", str(tmp_path / "config.toml"), "config", "init"),
    )

    assert result.exit_code == 1
    assert "Provide at least --nip or --token" in result.output
