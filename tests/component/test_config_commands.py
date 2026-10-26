from conftest import cli_args, payload, plain
from ksef2.profiles import (
    CliProfileConfig,
    ProfileAuthConfig,
    ProfileAuthType,
    ProfileConfig,
    load_profile_config,
    render_profile_config,
)

from ksef2_cli.app import app

CONFIG_FILE_MODE = 0o600


def test_config_show_renders_profile_config(runner, tmp_path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        render_profile_config(
            CliProfileConfig(
                active_profile="demo",
                profiles={
                    "demo": ProfileConfig(
                        environment="test",
                        nip="5261040828",
                        auth=ProfileAuthConfig(
                            type=ProfileAuthType.TOKEN,
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
        app, ["--json", "--config", str(config_path), "profile", "current"]
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
            "6880313213",
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


def test_profile_create_writes_sdk_polling_fields(runner, tmp_path) -> None:
    config_path = tmp_path / "config.toml"

    result = runner.invoke(
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
            "--poll-interval",
            "2.0",
            "--max-poll-attempts",
            "90",
        ),
    )
    created = payload(result)

    assert created["profile"]["poll_interval"] == 2.0
    assert created["profile"]["max_poll_attempts"] == 90

    saved = config_path.read_text(encoding="utf-8")
    assert "poll_interval = 2.0" in saved
    assert "max_poll_attempts = 90" in saved

    show_result = runner.invoke(
        app, ["--config", str(config_path), "profile", "show", "demo"]
    )
    assert "poll_interval: 2.0" in show_result.output
    assert "max_poll_attempts: 90" in show_result.output


def test_profile_create_leaves_polling_fields_unset_by_default(
    runner, tmp_path
) -> None:
    config_path = tmp_path / "config.toml"

    result = runner.invoke(
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
    created = payload(result)

    assert created["profile"]["poll_interval"] is None
    assert created["profile"]["max_poll_attempts"] is None
    assert "poll_interval" not in config_path.read_text(encoding="utf-8")


def test_profile_create_rejects_polling_values_below_sdk_minimums(
    runner, tmp_path
) -> None:
    for option, value in (("--poll-interval", "0.05"), ("--max-poll-attempts", "0")):
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
                "--test-cert",
                option,
                value,
            ),
        )

        assert result.exit_code == 2
        assert f"Invalid value for '{option}'" in plain(result.output)


def test_profile_delete_removes_an_inactive_profile_with_yes(runner, tmp_path) -> None:
    config_path = tmp_path / "config.toml"
    _create_profile(runner, config_path, "demo")
    _create_profile(runner, config_path, "spare", "--no-activate")

    result = runner.invoke(
        app,
        cli_args("--config", str(config_path), "profile", "delete", "spare", "--yes"),
    )

    assert payload(result) == {"name": "spare", "deleted": True, "was_active": False}
    assert _saved_profile_names(config_path) == ["demo"]
    assert _active_profile(config_path) == "demo"


def test_profile_delete_clears_the_active_profile(runner, tmp_path) -> None:
    config_path = tmp_path / "config.toml"
    _create_profile(runner, config_path, "demo")

    result = runner.invoke(
        app,
        cli_args("--config", str(config_path), "profile", "delete", "demo", "--yes"),
    )

    assert payload(result) == {"name": "demo", "deleted": True, "was_active": True}
    assert _saved_profile_names(config_path) == []
    assert _active_profile(config_path) is None

    current = runner.invoke(
        app, ["--json", "--config", str(config_path), "profile", "current"]
    )
    assert payload(current) == {"name": None, "profile": None}


def test_profile_delete_asks_before_removing_in_text_mode(
    runner, tmp_path, monkeypatch
) -> None:
    config_path = tmp_path / "config.toml"
    _create_profile(runner, config_path, "demo")
    args = ["--config", str(config_path), "profile", "delete", "demo"]

    monkeypatch.setattr("click.testing._NamedTextIOWrapper.isatty", lambda self: True)
    declined = runner.invoke(app, args, input="n\n")

    assert declined.exit_code == 0
    assert "Delete profile 'demo'?" in plain(declined.output)
    assert "deleted: no" in plain(declined.output)
    assert _saved_profile_names(config_path) == ["demo"]

    accepted = runner.invoke(app, args, input="y\n")

    assert accepted.exit_code == 0
    assert "deleted: yes" in plain(accepted.output)
    assert "was_active: yes" in plain(accepted.output)
    assert _saved_profile_names(config_path) == []


def test_profile_delete_needs_yes_in_json_mode(runner, tmp_path) -> None:
    config_path = tmp_path / "config.toml"
    _create_profile(runner, config_path, "demo")

    result = runner.invoke(
        app, cli_args("--config", str(config_path), "profile", "delete", "demo")
    )

    assert result.exit_code == 1
    assert "needs --yes" in plain(result.output)
    assert _saved_profile_names(config_path) == ["demo"]


def test_profile_delete_reports_unknown_profile_as_config_error(
    runner, tmp_path
) -> None:
    config_path = tmp_path / "config.toml"
    _create_profile(runner, config_path, "demo")

    result = runner.invoke(
        app,
        cli_args("--config", str(config_path), "profile", "delete", "ghost", "--yes"),
    )

    assert result.exit_code == 1
    assert "profile 'ghost' is not defined" in plain(result.output)
    # The 80-column console can break the long temp path across lines, so the
    # config path is compared with its wrapping removed.
    assert str(config_path) in "".join(plain(result.output).split())
    assert _saved_profile_names(config_path) == ["demo"]


def _create_profile(runner, config_path, name: str, *extra: str) -> None:
    result = runner.invoke(
        app,
        cli_args(
            "--config",
            str(config_path),
            "profile",
            "create",
            name,
            "--env",
            "test",
            "--nip",
            "5261040828",
            "--test-cert",
            *extra,
        ),
    )
    assert result.exit_code == 0, result.output


def _saved_profile_names(config_path) -> list[str]:
    return sorted(load_profile_config(config_path).profiles)


def _active_profile(config_path):
    return load_profile_config(config_path).active_profile


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
