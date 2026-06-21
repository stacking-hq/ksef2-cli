from conftest import cli_args, payload
from ksef2_cli.app import app
from ksef2_cli.config import (
    CONFIG_FILE_MODE,
    CliConfig,
    ProfileAuthConfig,
    ProfileAuthType,
    ProfileConfig,
    render_cli_config,
)


def test_config_show_renders_profile_config(runner, tmp_path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        render_cli_config(
            CliConfig(
                active_profile="demo",
                profiles={
                    "demo": ProfileConfig(
                        environment="test",
                        nip="5261040828",
                        auth=ProfileAuthConfig(
                            type=ProfileAuthType.token,
                            token_env="KSEF2_DEMO_TOKEN",
                            context_type="nip",
                        ),
                    )
                },
            )
        ),
        encoding="utf-8",
    )

    result = runner.invoke(
        app, ["--json", "--config", str(config_path), "config", "show"]
    )
    data = payload(result)

    assert data["path"] == str(config_path)
    assert data["exists"] is True
    assert data["config"]["active_profile"] == "demo"
    assert data["config"]["profiles"]["demo"]["nip"] == "5261040828"
    assert data["config"]["profiles"]["demo"]["auth"]["token_env"] == "KSEF2_DEMO_TOKEN"


def test_config_path_and_init(runner, tmp_path) -> None:
    config_path = tmp_path / "nested" / "config.toml"

    path_result = runner.invoke(
        app, cli_args("--config", str(config_path), "config", "path")
    )
    assert payload(path_result) == {
        "path": str(config_path),
        "exists": False,
        "loaded": False,
    }

    init_result = runner.invoke(
        app,
        cli_args("--config", str(config_path), "config", "init"),
    )
    init_data = payload(init_result)

    assert init_data["path"] == str(config_path)
    assert init_data["mode"] == "0600"
    assert init_data["config"]["profiles"] == {}
    assert oct(config_path.stat().st_mode & 0o777) == oct(CONFIG_FILE_MODE)


def test_profile_create_list_current_show_and_use(runner, tmp_path) -> None:
    config_path = tmp_path / "config.toml"

    create_result = runner.invoke(
        app,
        cli_args(
            "--config",
            str(config_path),
            "profile",
            "create",
            "demo",
            "--env",
            "test",
            "--nip",
            "5261040828",
            "--test-cert",
        ),
    )
    created = payload(create_result)

    assert created["name"] == "demo"
    assert created["active"] is True
    assert created["profile"]["environment"] == "test"
    assert created["profile"]["auth"]["type"] == "test_certificate"

    list_result = runner.invoke(
        app, cli_args("--config", str(config_path), "profile", "list")
    )
    assert payload(list_result)["profiles"] == [
        {
            "name": "demo",
            "active": True,
            "environment": "test",
            "nip": "5261040828",
            "auth": "test_certificate",
        }
    ]

    current_result = runner.invoke(
        app, cli_args("--config", str(config_path), "profile", "current")
    )
    assert payload(current_result)["name"] == "demo"

    show_result = runner.invoke(
        app, cli_args("--config", str(config_path), "profile", "show", "demo")
    )
    assert payload(show_result)["profile"]["nip"] == "5261040828"

    create_prod = runner.invoke(
        app,
        cli_args(
            "--config",
            str(config_path),
            "profile",
            "create",
            "prod",
            "--env",
            "production",
            "--nip",
            "1234567890",
            "--token-env",
            "KSEF2_PROD_TOKEN",
            "--no-activate",
        ),
    )
    assert payload(create_prod)["active"] is False

    use_result = runner.invoke(
        app, cli_args("--config", str(config_path), "profile", "use", "prod")
    )
    assert payload(use_result)["name"] == "prod"


def test_profile_create_validates_required_fields(runner, tmp_path) -> None:
    result = runner.invoke(
        app,
        cli_args(
            "--config",
            str(tmp_path / "config.toml"),
            "profile",
            "create",
            "demo",
            "--env",
            "test",
            "--nip",
            "5261040828",
        ),
    )

    assert result.exit_code == 1
    assert "Provide exactly one auth method" in result.output


def test_profile_create_refuses_replace_without_force(runner, tmp_path) -> None:
    config_path = tmp_path / "config.toml"
    args = cli_args(
        "--config",
        str(config_path),
        "profile",
        "create",
        "demo",
        "--env",
        "test",
        "--nip",
        "5261040828",
        "--test-cert",
    )

    assert runner.invoke(app, args).exit_code == 0
    second = runner.invoke(app, args)

    assert second.exit_code == 1
    assert "already exists" in second.output
