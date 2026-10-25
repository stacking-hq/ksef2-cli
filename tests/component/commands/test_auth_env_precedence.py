"""Auth environment variables yield to a selected profile, but typed flags do not."""

import json

import pytest
from ksef2 import Client, Environment

from conftest import (
    FakeAuthenticated,
    FakeClient,
    FakeService,
    fake_runtime,
    payload,
    plain,
)
from ksef2_cli.app import app


@pytest.fixture
def token_config(tmp_path):
    config = tmp_path / "config.toml"
    config.write_text(
        'active_profile = "qa"\n'
        '[profiles.qa]\nenvironment = "test"\nnip = "5261040828"\n'
        '[profiles.qa.auth]\ntype = "token"\ntoken_env = "KSEF2_TOKEN"\n',
        encoding="utf-8",
    )
    return config


@pytest.fixture
def auth_env(monkeypatch, tmp_path):
    cert = tmp_path / "cert.pem"
    key = tmp_path / "key.pem"
    cert.touch()
    key.touch()
    values = {
        "KSEF2_TOKEN": "profile-token",
        "KSEF2_CERT": str(cert),
        "KSEF2_KEY": str(key),
    }
    for name, value in values.items():
        monkeypatch.setenv(name, value)
    return values


@pytest.mark.parametrize("selection", ["active", "flag", "env"])
@pytest.mark.parametrize("override_nip", [False, True])
def test_token_profile_ignores_auth_env(
    runner, monkeypatch, token_config, auth_env, selection, override_nip
) -> None:
    args = ["--json", "--config", str(token_config)]
    if selection != "active":
        token_config.write_text(
            token_config.read_text().replace('active_profile = "qa"\n', ""),
            encoding="utf-8",
        )
    if selection == "flag":
        args += ["--profile", "qa"]
    elif selection == "env":
        monkeypatch.setenv("KSEF2_PROFILE", "qa")
    if override_nip:
        args += ["--nip", "6880313213"]

    # Include every auth env option so passwords/context cannot displace the profile.
    monkeypatch.setenv("KSEF2_TEST_CERT", "true")
    monkeypatch.setenv("KSEF2_P12", auth_env["KSEF2_CERT"])
    monkeypatch.setenv("KSEF2_KEY_PASSWORD", "unused-key-password")
    monkeypatch.setenv("KSEF2_P12_PASSWORD", "unused-p12-password")
    monkeypatch.setenv("KSEF2_CONTEXT_TYPE", "internal_id")
    auth = FakeService(with_token=FakeAuthenticated())
    client = Client(environment=Environment.TEST)
    monkeypatch.setattr(
        type(client.authentication),
        "with_token",
        lambda self, **kwargs: auth.with_token(**kwargs),
    )

    result = runner.invoke(
        app, [*args, "auth", "login"], obj=fake_runtime(client=client)
    )

    assert set(payload(result)) == {"access_token", "refresh_token"}
    assert auth.called("with_token") == {
        "ksef_token": "profile-token",
        "nip": "6880313213" if override_nip else "5261040828",
        "context_type": "nip",
        "poll_interval": 1.0,
        "timeout": 60.0,
    }


def test_typed_pem_overrides_token_profile(runner, token_config, auth_env) -> None:
    auth = FakeService(with_xades=FakeAuthenticated())
    loaded = []

    def load_pem(**kwargs):
        loaded.append(kwargs)
        return "pem-cert", "pem-key"

    result = runner.invoke(
        app,
        [
            "--json",
            "--config",
            str(token_config),
            "--cert",
            auth_env["KSEF2_CERT"],
            "--key",
            auth_env["KSEF2_KEY"],
            "auth",
            "login",
        ],
        obj=fake_runtime(
            client=FakeClient(authentication=auth), pem_credentials_loader=load_pem
        ),
    )

    assert set(payload(result)) == {"access_token", "refresh_token"}
    assert [name for name, _, _ in auth.calls] == ["with_xades"]
    assert auth.called("with_xades")["cert"] == "pem-cert"
    assert str(loaded[0]["cert_path"]) == auth_env["KSEF2_CERT"]
    assert str(loaded[0]["key_path"]) == auth_env["KSEF2_KEY"]


@pytest.mark.parametrize("typed_cert", [False, True])
def test_auth_env_conflicts_without_profile(runner, auth_env, typed_cert) -> None:
    args = ["--no-config", "--json", "--nip", "5261040828"]
    if typed_cert:
        args += ["--cert", auth_env["KSEF2_CERT"]]
    auth = FakeService()
    result = runner.invoke(
        app,
        [*args, "auth", "login"],
        obj=fake_runtime(client=FakeClient(authentication=auth)),
    )

    assert result.exit_code == 1
    assert json.loads(result.output)["error"]["message"] == (
        "Provide only one auth method: token (KSEF2_TOKEN), "
        f"certificate ({'--cert' if typed_cert else 'KSEF2_CERT'}, KSEF2_KEY)."
    )
    assert auth.calls == []


def test_token_env_without_profile_still_authenticates(runner, monkeypatch) -> None:
    monkeypatch.setenv("KSEF2_TOKEN", "env-token")
    auth = FakeService(with_token=FakeAuthenticated())
    result = runner.invoke(
        app,
        ["--no-config", "--json", "--nip", "5261040828", "auth", "login"],
        obj=fake_runtime(client=FakeClient(authentication=auth)),
    )

    assert set(payload(result)) == {"access_token", "refresh_token"}
    assert auth.called("with_token")["ksef_token"] == "env-token"
