from pathlib import Path
from types import SimpleNamespace

import pytest
import typer

from conftest import FakeClient, FakeService, settings
from ksef2.profiles import ProfileAuthConfig, ProfileAuthType, ProfileConfig
from ksef2_cli.config import OutputMode, RuntimeOverrides
from ksef2_cli.exceptions import AuthenticationConfigError
from ksef2_cli import context, runtime


def ctx_for(settings_obj):
    return SimpleNamespace(obj=settings_obj)


def token_profile(
    *, nip: str = "5261040828", token_env: str = "KSEF2_PROFILE_TOKEN"
) -> ProfileConfig:
    return ProfileConfig(
        environment="test",
        nip=nip,
        auth=ProfileAuthConfig(type=ProfileAuthType.TOKEN, token_env=token_env),
    )


def test_get_settings_requires_initialized_context() -> None:
    with pytest.raises(RuntimeError, match="settings were not initialized"):
        context.get_settings(SimpleNamespace(obj=None))


def test_select_auth_method_reports_flag_methods_only() -> None:
    assert runtime.select_auth_method(settings()) is None
    assert runtime.select_auth_method(settings(token="token")) is ProfileAuthType.TOKEN
    assert (
        runtime.select_auth_method(settings(test_certificate=True))
        is ProfileAuthType.TEST_CERTIFICATE
    )
    assert runtime.select_auth_method(settings(p12=Path("auth.p12"))) is (
        ProfileAuthType.XADES_P12
    )
    assert (
        runtime.select_auth_method(settings(cert=Path("cert.pem"), key=Path("key.pem")))
        is ProfileAuthType.XADES_PEM
    )

    with pytest.raises(AuthenticationConfigError):
        runtime.select_auth_method(settings(token="token", test_certificate=True))


def test_authentication_requires_nip_and_one_method() -> None:
    client = FakeClient(authentication=FakeService())

    with pytest.raises(AuthenticationConfigError, match="requires --nip"):
        context.authenticate_client(ctx_for(settings(nip=None, token="token")), client)

    with pytest.raises(AuthenticationConfigError, match="Provide one auth method"):
        context.authenticate_client(ctx_for(settings()), client)

    with pytest.raises(AuthenticationConfigError, match="Both --cert and --key"):
        context.authenticate_client(ctx_for(settings(cert=Path("cert.pem"))), client)


def test_profile_without_cli_auth_flags_delegates_to_with_profile() -> None:
    auth = FakeService(with_profile={"auth": "profile"})
    client = FakeClient(authentication=auth)
    settings_obj = settings(
        profile_name="demo",
        profile=token_profile(),
        auth_timeout=45.0,
        poll_interval=2.0,
    )

    result = context.authenticate_client(ctx_for(settings_obj), client)

    assert result == {"auth": "profile"}
    method, args, kwargs = auth.calls[-1]
    assert method == "with_profile"
    assert args == ("demo",)
    assert kwargs == {
        "config_path": settings_obj.config_file,
        "timeout": 45.0,
        "poll_interval": 2.0,
    }
    # The SDK resolves the profile's own auth settings and secrets; the CLI does not
    # call an authentication method of its own for the same profile.
    assert auth.calls == [("with_profile", args, kwargs)]


def test_cli_auth_flags_keep_authentication_cli_side(monkeypatch) -> None:
    monkeypatch.setenv("KSEF2_PROFILE_TOKEN", "profile-token")
    auth = FakeService(with_token={"auth": "token"}, with_profile={"auth": "profile"})
    client = FakeClient(authentication=auth)

    result = context.authenticate_client(
        ctx_for(
            settings(
                profile_name="demo",
                profile=token_profile(nip="1111111111"),
                nip="5261040828",
                auth_timeout=5.0,
            )
        ),
        client,
    )

    assert result == {"auth": "token"}
    kwargs = auth.called("with_token")
    assert kwargs["ksef_token"] == "profile-token"
    assert kwargs["nip"] == "5261040828"
    assert kwargs["context_type"] == "nip"
    assert kwargs["timeout"] == 5.0
    assert kwargs["poll_interval"] == 1.0


def test_authenticate_client_token_and_test_certificate() -> None:
    auth = FakeService(
        with_token={"auth": "token"},
        with_test_certificate={"auth": "cert"},
    )
    client = FakeClient(authentication=auth)

    assert context.authenticate_client(ctx_for(settings(token="token")), client) == {
        "auth": "token"
    }
    assert auth.called("with_token")["ksef_token"] == "token"
    assert auth.called("with_token")["timeout"] == 60.0
    assert auth.called("with_token")["poll_interval"] == 1.0

    assert context.authenticate_client(
        ctx_for(settings(test_certificate=True)), client
    ) == {"auth": "cert"}
    assert auth.called("with_test_certificate")["nip"] == "5261040828"


def test_authenticate_client_p12_and_pem() -> None:
    auth = FakeService(with_xades={"auth": "xades"})
    client = FakeClient(authentication=auth)

    result = context.authenticate_client(
        ctx_for(
            settings(
                p12=Path("auth.p12"),
                p12_password="secret",
                runtime_overrides=RuntimeOverrides(
                    p12_credentials_loader=lambda path, password: (
                        "p12-cert",
                        "p12-key",
                    )
                ),
            )
        ),
        client,
    )
    assert result == {"auth": "xades"}
    assert auth.called("with_xades")["cert"] == "p12-cert"

    result = context.authenticate_client(
        ctx_for(
            settings(
                cert=Path("cert.pem"),
                key=Path("key.pem"),
                key_password="secret",
                runtime_overrides=RuntimeOverrides(
                    pem_credentials_loader=lambda cert_path, key_path, key_password: (
                        "pem-cert",
                        "pem-key",
                    )
                ),
            )
        ),
        client,
    )
    assert result == {"auth": "xades"}


def test_runtime_overrides_supply_fake_clients() -> None:
    client = FakeClient()
    auth = {"auth": True}
    overrides = RuntimeOverrides(
        client_factory=lambda: client,
        authenticated_client_factory=lambda: SimpleNamespace(client=client, auth=auth),
    )
    ctx = ctx_for(settings(runtime_overrides=overrides))

    runtime = context.get_authenticated_client(ctx)

    assert context.create_client(ctx) is client
    assert runtime.client is client
    assert runtime.auth == auth


def test_run_client_enters_client_context() -> None:
    client = FakeClient()
    ctx = ctx_for(
        settings(runtime_overrides=RuntimeOverrides(client_factory=lambda: client))
    )

    assert context.run_client(ctx, lambda sdk_client: sdk_client) is client
    assert client.entered == 1
    assert client.exited == 1


def test_run_authenticated_enters_client_context() -> None:
    client = FakeClient()
    auth = {"auth": True}
    overrides = RuntimeOverrides(
        authenticated_client_factory=lambda: SimpleNamespace(client=client, auth=auth),
    )
    ctx = ctx_for(settings(runtime_overrides=overrides))

    assert (
        context.run_authenticated(ctx, lambda authenticated: authenticated["auth"])
        is True
    )
    assert client.entered == 1
    assert client.exited == 1


def test_run_authenticated_command_validates_before_authentication(capsys) -> None:
    client = FakeClient()
    factory_called = False

    def authenticated_factory():
        nonlocal factory_called
        factory_called = True
        return SimpleNamespace(client=client, auth={})

    ctx = ctx_for(
        settings(
            output=OutputMode.text,
            runtime_overrides=RuntimeOverrides(
                authenticated_client_factory=authenticated_factory
            ),
        )
    )

    with pytest.raises(typer.Exit):
        context.run_authenticated_command(
            ctx,
            lambda _auth: "ok",
            validate=lambda: (_ for _ in ()).throw(ValueError("bad input")),
        )

    assert "bad input" in capsys.readouterr().err
    assert factory_called is False
    assert client.entered == 0


def test_run_command_formats_errors(capsys) -> None:
    ctx = ctx_for(settings(output=OutputMode.text))

    context.run_command(ctx, lambda: "ok")
    assert capsys.readouterr().out == "ok\n"

    with pytest.raises(typer.Exit):
        context.run_command(ctx, lambda: (_ for _ in ()).throw(ValueError("bad input")))
    assert "bad input" in capsys.readouterr().err


def test_credential_loader_wrappers(tmp_path) -> None:
    p12_path = tmp_path / "auth.p12"
    cert_path = tmp_path / "cert.pem"
    key_path = tmp_path / "key.pem"

    assert runtime.password_bytes("secret") == b"secret"
    assert runtime.password_bytes(None) is None
    assert runtime.load_p12_credentials(
        p12_path,
        password="secret",
        loader=lambda path, password: (("p12", path), password),
    ) == (("p12", p12_path), b"secret")
    assert runtime.load_pem_credentials(
        cert_path=cert_path,
        key_path=key_path,
        key_password="secret",
        cert_loader=lambda path: ("cert", path),
        key_loader=lambda path, password: (("key", path), password),
    ) == (("cert", cert_path), (("key", key_path), b"secret"))
