from datetime import UTC, datetime

from conftest import (
    FakeAuthenticated,
    FakeClient,
    FakePager,
    FakeService,
    FakeTokenHandle,
    auth_state,
    cli_args,
    fake_runtime,
    payload,
)
from ksef2.models import RefreshedToken, SubjectLimits, TokenCredentials, TokenInfo
from ksef2.profiles import (
    CliProfileConfig,
    ProfileAuthConfig,
    ProfileAuthType,
    ProfileConfig,
    render_profile_config,
)

from ksef2_cli.app import app


def test_auth_login_uses_configured_auth_method(runner) -> None:
    state = auth_state(
        access_valid_until=datetime(2026, 2, 1, tzinfo=UTC),
        refresh_valid_until=datetime(2026, 2, 2, tzinfo=UTC),
    )
    fake_client = FakeClient(
        authentication=FakeService(with_token=FakeAuthenticated(state))
    )

    result = runner.invoke(
        app,
        cli_args("--nip", "5261040828", "--token", "secret", "auth", "login"),
        obj=fake_runtime(client=fake_client),
    )

    assert payload(result) == {
        "access_token": "access-t…oken",
        "access_token_valid_until": "2026-02-01T00:00:00Z",
        "refresh_token": "refresh-…oken",
        "refresh_token_valid_until": "2026-02-02T00:00:00Z",
    }
    assert fake_client.entered == 1


def test_auth_login_uses_active_profile(runner, tmp_path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        render_profile_config(
            CliProfileConfig(
                active_profile="demo",
                profiles={
                    "demo": ProfileConfig(
                        environment="test",
                        nip="6880313213",
                        auth=ProfileAuthConfig(
                            type=ProfileAuthType.TOKEN,
                            token_env="KSEF2_PROFILE_TOKEN",
                            context_type="nip",
                        ),
                    )
                },
            )
        ),
        encoding="utf-8",
    )
    auth = FakeService(with_profile=FakeAuthenticated(auth_state()))
    fake_client = FakeClient(authentication=auth)

    result = runner.invoke(
        app,
        ["--json", "--config", str(config_path), "auth", "login"],
        env={"KSEF2_PROFILE_TOKEN": "profile-token"},
        obj=fake_runtime(client=fake_client),
    )

    assert set(payload(result)) == {
        "access_token",
        "access_token_valid_until",
        "refresh_token",
        "refresh_token_valid_until",
    }
    method, args, kwargs = auth.calls[-1]
    assert method == "with_profile"
    assert args == ("demo",)
    assert kwargs["config_path"] == config_path
    assert kwargs["timeout"] is None
    assert kwargs["poll_interval"] is None


def test_auth_refresh_requires_and_uses_refresh_token(runner) -> None:
    refreshed = RefreshedToken(
        access_token=TokenCredentials(
            token="new-access-token", valid_until=datetime(2026, 2, 1, tzinfo=UTC)
        )
    )
    client = FakeClient(authentication=FakeService(refresh=refreshed))

    missing = runner.invoke(
        app, cli_args("auth", "refresh"), obj=fake_runtime(client=client)
    )
    assert missing.exit_code == 2

    result = runner.invoke(
        app,
        cli_args("auth", "refresh", "--refresh-token", "refresh"),
        obj=fake_runtime(client=client),
    )

    assert payload(result) == {
        "access_token": "new-acce…oken",
        "access_token_valid_until": "2026-02-01T00:00:00Z",
    }
    assert client.authentication.called("refresh")["refresh_token"] == "refresh"

    env_client = FakeClient(authentication=FakeService(refresh=refreshed))
    result = runner.invoke(
        app,
        cli_args("auth", "refresh"),
        env={"KSEF2_REFRESH_TOKEN": "refresh-from-env"},
        obj=fake_runtime(client=env_client),
    )

    assert payload(result) == {
        "access_token": "new-acce…oken",
        "access_token_valid_until": "2026-02-01T00:00:00Z",
    }
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


def test_peppol_providers_list_and_all(runner) -> None:
    service = FakeService(
        list=FakePager([{"id": "p1"}], [{"id": "p2"}]),
    )
    runtime = fake_runtime(client=FakeClient(peppol=service))

    result = runner.invoke(
        app, cli_args("peppol", "providers", "--page-size", "10"), obj=runtime
    )
    assert payload(result) == [{"id": "p1"}]
    assert service.called("list")["params"].page_size == 10

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
    handle = FakeTokenHandle(reference_number="token-ref", token="secret")
    service = FakeService(
        generate=handle,
        list=FakePager(
            [{"reference_number": "r1"}],
            [{"reference_number": "r2"}],
        ),
        get_status={"status": "active"},
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
    ) == {"reference_number": "token-ref", "token": "secret", "status": None}
    assert service.called("generate")["permissions"] == ["invoice_read"]
    assert handle.wait_calls == []

    assert payload(
        runner.invoke(
            app,
            cli_args(
                "--auth-timeout",
                "30",
                "--auth-poll-interval",
                "0.5",
                "tokens",
                "generate",
                "--description",
                "demo",
                "--permission",
                "invoice_read",
                "--wait",
            ),
            obj=runtime,
        )
    ) == {"reference_number": "token-ref", "token": "secret", "status": "active"}
    assert handle.wait_calls == [{"timeout": 30.0, "poll_interval": 0.5}]

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
    ) == [{"reference_number": "r1"}]
    assert service.called("list")["params"].status == ["active"]
    assert payload(
        runner.invoke(
            app,
            cli_args("tokens", "list", "--all", "--page-size", "50"),
            obj=runtime,
        )
    ) == [{"reference_number": "r1"}, {"reference_number": "r2"}]
    list_params = [
        kwargs["params"] for name, _, kwargs in service.calls if name == "list"
    ]
    assert [params.page_size for params in list_params] == [10, 50]
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


def _token_info(reference_number: str) -> TokenInfo:
    return TokenInfo(
        reference_number=reference_number,
        author_identifier={"type": "nip", "value": "5261040828"},
        context_identifier={"type": "nip", "value": "5261040828"},
        description="demo",
        requested_permissions=["invoice_read"],
        date_created=datetime(2026, 1, 2, tzinfo=UTC),
        last_use_date=None,
        status="active",
        status_details=None,
    )


def test_tokens_list_text_mode_renders_token_rows(runner) -> None:
    # The 1.0 pager has no continuation token, so both modes hand the renderer a
    # plain list of TokenInfo.
    service = FakeService(list=FakePager([_token_info("t1")], [_token_info("t2")]))
    runtime = fake_runtime(auth=type("Auth", (), {"tokens": service})())

    first_page = runner.invoke(app, ["--no-config", "tokens", "list"], obj=runtime)
    assert [line.split()[0] for line in first_page.output.splitlines()] == [
        "reference_number=t1"
    ]

    all_pages = runner.invoke(
        app, ["--no-config", "tokens", "list", "--all"], obj=runtime
    )
    assert [line.split()[0] for line in all_pages.output.splitlines()] == [
        "reference_number=t1",
        "reference_number=t2",
    ]


def test_sessions_commands(runner) -> None:
    session_service = FakeService(
        list=FakePager(
            [{"reference_number": "auth-ref"}], [{"reference_number": "auth-ref-2"}]
        ),
        terminate=None,
        terminate_current=None,
    )
    invoice_service = FakeService(
        list=FakePager([{"reference_number": "invoice-ref"}]),
    )
    auth_obj = type(
        "Auth",
        (),
        {"sessions": session_service, "invoice_sessions": invoice_service},
    )()
    runtime = fake_runtime(auth=auth_obj)

    assert payload(
        runner.invoke(app, cli_args("sessions", "auth-list"), obj=runtime)
    ) == [{"reference_number": "auth-ref"}]
    assert payload(
        runner.invoke(app, cli_args("sessions", "auth-list", "--all"), obj=runtime)
    ) == [{"reference_number": "auth-ref"}, {"reference_number": "auth-ref-2"}]

    # ksef2 1.0 pages auth sessions internally; the cursor is rejected loudly.
    cursor = runner.invoke(
        app,
        cli_args("sessions", "auth-list", "--continuation-token", "ct"),
        obj=runtime,
    )
    assert cursor.exit_code == 1
    assert "--continuation-token" in cursor.output

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
    assert session_service.called("terminate")["reference_number"] == "auth-ref"
    assert payload(
        runner.invoke(app, cli_args("sessions", "auth-terminate-current"), obj=runtime)
    ) == {"terminated_current": True}
    assert payload(
        runner.invoke(
            app, cli_args("sessions", "invoice-list", "--type", "online"), obj=runtime
        )
    ) == [{"reference_number": "invoice-ref"}]
    assert payload(
        runner.invoke(
            app,
            cli_args("sessions", "invoice-list", "--type", "batch", "--all"),
            obj=runtime,
        )
    ) == [{"reference_number": "invoice-ref"}]
    list_types = [
        kwargs["session_type"]
        for name, _, kwargs in invoice_service.calls
        if name == "list"
    ]
    assert list_types == ["online", "batch"]


def test_sessions_invoice_list_date_filters(runner) -> None:
    invoice_service = FakeService(list=FakePager([{"reference_number": "invoice-ref"}]))
    runtime = fake_runtime(
        auth=type("Auth", (), {"invoice_sessions": invoice_service})()
    )

    result = runner.invoke(
        app,
        cli_args(
            "sessions",
            "invoice-list",
            "--type",
            "online",
            "--created-from",
            "2026-01-01T00:00:00Z",
            "--created-to",
            "2026-01-02T00:00:00Z",
            "--closed-from",
            "2026-01-03T00:00:00Z",
            "--closed-to",
            "2026-01-04T00:00:00Z",
            "--modified-from",
            "2026-01-05T00:00:00Z",
            "--modified-to",
            "2026-01-06T00:00:00Z",
        ),
        obj=runtime,
    )

    assert payload(result) == [{"reference_number": "invoice-ref"}]
    params = invoice_service.called("list")["params"]
    assert params.date_created_from == datetime(2026, 1, 1, tzinfo=UTC)
    assert params.date_created_to == datetime(2026, 1, 2, tzinfo=UTC)
    assert params.date_closed_from == datetime(2026, 1, 3, tzinfo=UTC)
    assert params.date_closed_to == datetime(2026, 1, 4, tzinfo=UTC)
    assert params.date_modified_from == datetime(2026, 1, 5, tzinfo=UTC)
    assert params.date_modified_to == datetime(2026, 1, 6, tzinfo=UTC)

    # A date the SDK would reject is reported as a CLI usage error instead.
    bad_date = runner.invoke(
        app,
        cli_args(
            "sessions",
            "invoice-list",
            "--type",
            "online",
            "--closed-from",
            "yesterday",
        ),
        obj=runtime,
    )
    assert bad_date.exit_code == 1
    assert "--closed-from must be a date like" in bad_date.output
