from conftest import FakeClient, FakeService, cli_args, fake_runtime, payload
from ksef2.domain.models.limits import SubjectLimits
from ksef2_cli.app import app
from ksef2_cli.config import (
    CliConfig,
    ProfileAuthConfig,
    ProfileAuthType,
    ProfileConfig,
    render_cli_config,
)


def test_auth_login_uses_configured_auth_method(runner) -> None:
    fake_client = FakeClient(
        authentication=FakeService(
            with_token=type("Auth", (), {"auth_tokens": {"access_token": "access"}})()
        )
    )

    result = runner.invoke(
        app,
        cli_args("--nip", "5261040828", "--token", "secret", "auth", "login"),
        obj=fake_runtime(client=fake_client),
    )

    assert payload(result) == {"access_token": "access"}
    assert fake_client.entered == 1


def test_auth_login_uses_active_profile(runner, tmp_path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        render_cli_config(
            CliConfig(
                active_profile="demo",
                profiles={
                    "demo": ProfileConfig(
                        environment="test",
                        nip="6880313213",
                        auth=ProfileAuthConfig(
                            type=ProfileAuthType.token,
                            token_env="KSEF2_PROFILE_TOKEN",
                            context_type="nip",
                        ),
                    )
                },
            )
        ),
        encoding="utf-8",
    )
    auth = FakeService(
        with_token=type("Auth", (), {"auth_tokens": {"access_token": "access"}})()
    )
    fake_client = FakeClient(authentication=auth)

    result = runner.invoke(
        app,
        ["--json", "--config", str(config_path), "auth", "login"],
        env={"KSEF2_PROFILE_TOKEN": "profile-token"},
        obj=fake_runtime(client=fake_client),
    )

    assert payload(result) == {"access_token": "access"}
    assert auth.called("with_token")["nip"] == "6880313213"
    assert auth.called("with_token")["ksef_token"] == "profile-token"


def test_auth_refresh_requires_and_uses_refresh_token(runner) -> None:
    client = FakeClient(authentication=FakeService(refresh={"access_token": "new"}))

    missing = runner.invoke(
        app, cli_args("auth", "refresh"), obj=fake_runtime(client=client)
    )
    assert missing.exit_code == 2

    result = runner.invoke(
        app,
        cli_args("auth", "refresh", "--refresh-token", "refresh"),
        obj=fake_runtime(client=client),
    )

    assert payload(result) == {"access_token": "new"}
    assert client.authentication.called("refresh")["refresh_token"] == "refresh"

    env_client = FakeClient(authentication=FakeService(refresh={"access_token": "new"}))
    result = runner.invoke(
        app,
        cli_args("auth", "refresh"),
        env={"KSEF2_REFRESH_TOKEN": "refresh-from-env"},
        obj=fake_runtime(client=env_client),
    )

    assert payload(result) == {"access_token": "new"}
    assert (
        env_client.authentication.called("refresh")["refresh_token"]
        == "refresh-from-env"
    )


def test_encryption_certificates_uses_public_client(runner) -> None:
    service = FakeService(get_certificates={"certificates": [{"public_key_id": "id"}]})
    client = FakeClient(encryption=service)

    result = runner.invoke(
        app,
        cli_args("encryption", "certificates", "--usage", "ksef_token_encryption"),
        obj=fake_runtime(client=client),
    )

    assert payload(result) == {"certificates": [{"public_key_id": "id"}]}
    assert service.called("get_certificates")["usage"] == ["ksef_token_encryption"]

    invalid = runner.invoke(
        app,
        cli_args("encryption", "certificates", "--usage", "invoice"),
        obj=fake_runtime(
            client=FakeClient(encryption=FakeService(get_certificates=[]))
        ),
    )
    assert invalid.exit_code == 2


def test_peppol_providers_query_and_all(runner) -> None:
    service = FakeService(
        query={"providers": [{"id": "p1"}]},
        all=lambda **kwargs: [{"id": "p1"}, {"id": "p2"}],
    )
    runtime = fake_runtime(client=FakeClient(peppol=service))

    result = runner.invoke(
        app, cli_args("peppol", "providers", "--page-size", "10"), obj=runtime
    )
    assert payload(result) == {"providers": [{"id": "p1"}]}
    assert service.called("query")["params"].page_size == 10

    result = runner.invoke(app, cli_args("peppol", "providers", "--all"), obj=runtime)
    assert payload(result) == [{"id": "p1"}, {"id": "p2"}]


def test_limits_get_set_reset_and_production(runner, tmp_path) -> None:
    service = FakeService(
        get_api_rate_limits={"kind": "api"},
        get_context_limits={"kind": "context"},
        get_subject_limits={"kind": "subject"},
        set_api_rate_limits=None,
        reset_session_limits=None,
        set_production_rate_limits=None,
    )
    auth_obj = type("Auth", (), {"limits": service})()
    runtime = fake_runtime(auth=auth_obj)

    assert payload(
        runner.invoke(app, cli_args("limits", "get", "api"), obj=runtime)
    ) == {"kind": "api"}
    assert payload(
        runner.invoke(app, cli_args("limits", "get", "context"), obj=runtime)
    ) == {"kind": "context"}
    assert payload(
        runner.invoke(app, cli_args("limits", "get", "subject"), obj=runtime)
    ) == {"kind": "subject"}

    invalid = runner.invoke(app, cli_args("limits", "get", "missing"), obj=runtime)
    assert invalid.exit_code == 2
    assert "Invalid value" in invalid.output
    assert "missing" in invalid.output

    payload_file = tmp_path / "limits.json"
    payload_file.write_text('{"certificate":{"max_certificates":1}}', encoding="utf-8")
    assert payload(
        runner.invoke(
            app,
            cli_args("limits", "set", "subject", "--payload", str(payload_file)),
            obj=runtime,
        )
    ) == {
        "kind": "subject",
        "updated": True,
    }
    assert service.called("set_subject_limits")["limits"] == SubjectLimits(
        certificate={"max_certificates": 1}
    )

    assert payload(
        runner.invoke(app, cli_args("limits", "reset", "session"), obj=runtime)
    ) == {
        "kind": "session",
        "reset": True,
    }
    assert payload(
        runner.invoke(app, cli_args("limits", "production-rate-limits"), obj=runtime)
    ) == {"api_rate_limits": "production"}


def test_tokens_commands(runner) -> None:
    service = FakeService(
        generate={"token": "secret"},
        list_page={"tokens": [{"reference_number": "r1"}]},
        list_all=lambda **kwargs: [
            type("Page", (), {"tokens": [{"reference_number": "r1"}]})()
        ],
        status={"status": "active"},
        revoke=None,
    )
    runtime = fake_runtime(auth=type("Auth", (), {"tokens": service})())

    missing = runner.invoke(
        app, cli_args("tokens", "generate", "--description", "demo"), obj=runtime
    )
    assert missing.exit_code == 1
    assert "At least one --permission" in missing.output

    assert payload(
        runner.invoke(
            app,
            cli_args(
                "tokens",
                "generate",
                "--description",
                "demo",
                "--permission",
                "invoice_read",
            ),
            obj=runtime,
        )
    ) == {"token": "secret"}
    assert service.called("generate")["permissions"] == ["invoice_read"]

    invalid = runner.invoke(
        app,
        cli_args("tokens", "generate", "--description", "demo", "--permission", "bad"),
        obj=runtime,
    )
    assert invalid.exit_code == 2

    assert payload(
        runner.invoke(
            app, cli_args("tokens", "list", "--status", "active"), obj=runtime
        )
    ) == {"tokens": [{"reference_number": "r1"}]}
    assert service.called("list_page")["params"].status == ["active"]
    assert payload(
        runner.invoke(app, cli_args("tokens", "list", "--all"), obj=runtime)
    ) == [{"reference_number": "r1"}]
    assert payload(
        runner.invoke(
            app, cli_args("tokens", "status", "--reference", "r1"), obj=runtime
        )
    ) == {"status": "active"}
    assert payload(
        runner.invoke(
            app, cli_args("tokens", "revoke", "--reference", "r1"), obj=runtime
        )
    ) == {
        "reference_number": "r1",
        "revoked": True,
    }


def test_sessions_commands(runner) -> None:
    session_service = FakeService(
        query={"items": [{"reference_number": "auth-ref"}]},
        all=lambda **kwargs: [
            type("Page", (), {"items": [{"reference_number": "auth-ref"}]})()
        ],
        close=None,
        terminate_current=None,
    )
    invoice_service = FakeService(
        query={"sessions": [{"reference_number": "invoice-ref"}]},
        all=lambda **kwargs: [
            type("Page", (), {"sessions": [{"reference_number": "invoice-ref"}]})()
        ],
    )
    auth_obj = type(
        "Auth",
        (),
        {"sessions": session_service, "invoice_sessions": invoice_service},
    )()
    runtime = fake_runtime(auth=auth_obj)

    assert payload(
        runner.invoke(app, cli_args("sessions", "auth-list"), obj=runtime)
    ) == {"items": [{"reference_number": "auth-ref"}]}
    assert payload(
        runner.invoke(app, cli_args("sessions", "auth-list", "--all"), obj=runtime)
    ) == [{"reference_number": "auth-ref"}]
    assert payload(
        runner.invoke(
            app,
            cli_args("sessions", "auth-close", "--reference", "auth-ref"),
            obj=runtime,
        )
    ) == {
        "reference_number": "auth-ref",
        "closed": True,
    }
    assert payload(
        runner.invoke(app, cli_args("sessions", "auth-terminate-current"), obj=runtime)
    ) == {"terminated_current": True}
    assert payload(
        runner.invoke(
            app, cli_args("sessions", "invoice-list", "--type", "online"), obj=runtime
        )
    ) == {"sessions": [{"reference_number": "invoice-ref"}]}
    assert payload(
        runner.invoke(
            app,
            cli_args("sessions", "invoice-list", "--type", "batch", "--all"),
            obj=runtime,
        )
    ) == [{"reference_number": "invoice-ref"}]
    assert invoice_service.called("all")["session_type"] == "batch"
