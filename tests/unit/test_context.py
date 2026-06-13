from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
import typer

from conftest import FakeClient, FakeService, settings
from ksef2_cli.config import RuntimeOverrides
from ksef2_cli import context


def ctx_for(settings_obj):
    return SimpleNamespace(obj=settings_obj)


def test_get_settings_requires_initialized_context() -> None:
    with pytest.raises(RuntimeError, match="settings were not initialized"):
        context.get_settings(SimpleNamespace(obj=None))


def test_select_auth_method_validates_required_and_conflicting_settings() -> None:
    with pytest.raises(typer.Exit):
        context.select_auth_method(settings(nip=None))

    with pytest.raises(typer.Exit):
        context.select_auth_method(settings(token="token", test_certificate=True))

    with pytest.raises(typer.Exit):
        context.select_auth_method(settings(cert=Path("cert.pem")))

    assert context.select_auth_method(settings(token="token")) == "token"
    assert context.select_auth_method(settings(test_certificate=True)) == "test_certificate"
    assert context.select_auth_method(settings(p12=Path("auth.p12"))) == "p12"
    assert context.select_auth_method(settings(cert=Path("cert.pem"), key=Path("key.pem"))) == "pem"


def test_authenticate_client_token_and_test_certificate() -> None:
    auth = FakeService(
        with_token={"auth": "token"},
        with_test_certificate={"auth": "cert"},
    )
    client = FakeClient(authentication=auth)

    assert context.authenticate_client(ctx_for(settings(token="token")), client) == {"auth": "token"}
    assert auth.called("with_token")["ksef_token"] == "token"

    assert context.authenticate_client(ctx_for(settings(test_certificate=True)), client) == {"auth": "cert"}
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
                    p12_credentials_loader=lambda path, password: ("p12-cert", "p12-key")
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
                    pem_credentials_loader=lambda cert_path, key_path, key_password: ("pem-cert", "pem-key")
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


def test_run_authenticated_enters_client_context() -> None:
    client = FakeClient()
    auth = {"auth": True}
    overrides = RuntimeOverrides(
        authenticated_client_factory=lambda: SimpleNamespace(client=client, auth=auth),
    )
    ctx = ctx_for(settings(runtime_overrides=overrides))

    assert context.run_authenticated(ctx, lambda authenticated: authenticated["auth"]) is True
    assert client.entered == 1
    assert client.exited == 1


def test_run_command_formats_errors(capsys) -> None:
    ctx = ctx_for(settings())

    assert context.run_command(ctx, lambda: "ok") == "ok"

    with pytest.raises(typer.Exit):
        context.run_command(ctx, lambda: (_ for _ in ()).throw(ValueError("bad input")))
    assert "bad input" in capsys.readouterr().out


def test_credential_loader_wrappers(tmp_path) -> None:
    p12_path = tmp_path / "auth.p12"
    cert_path = tmp_path / "cert.pem"
    key_path = tmp_path / "key.pem"

    assert context.password_bytes("secret") == b"secret"
    assert context.password_bytes(None) is None
    assert context.load_p12_credentials(
        p12_path,
        password="secret",
        loader=lambda path, password: (("p12", path), password),
    ) == (("p12", p12_path), b"secret")
    assert context.load_pem_credentials(
        cert_path=cert_path,
        key_path=key_path,
        key_password="secret",
        cert_loader=lambda path: ("cert", path),
        key_loader=lambda path, password: (("key", path), password),
    ) == (("cert", cert_path), (("key", key_path), b"secret"))
