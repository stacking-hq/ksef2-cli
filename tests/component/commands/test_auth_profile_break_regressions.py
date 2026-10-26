"""Local regressions for the auth/profile break-test report. No live transport."""

import json
import stat
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from click import BadParameter
from conftest import auth_state, fake_runtime, payload, plain
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID
from ksef2 import Client, Environment
from ksef2.profiles import CliProfileConfig, ProfileAuthConfig, ProfileConfig

from ksef2_cli.app import app
from ksef2_cli.config import EnvironmentName, resolve_settings, write_cli_config
from ksef2_cli.runtime import load_p12_credentials, load_pem_credentials


def _config(
    path, *, environment="test", auth_type="test_certificate", nip="5261040828"
):
    profile = ProfileConfig(
        environment=environment,
        nip=nip,
        auth=ProfileAuthConfig(type=auth_type, token_env="LOCAL_TOKEN"),
    )
    write_cli_config(
        path, CliProfileConfig(active_profile="local", profiles={"local": profile})
    )


def test_default_test_and_explicit_production(tmp_path):
    assert resolve_settings(no_config=True).environment is Environment.TEST
    assert (
        resolve_settings(
            no_config=True, environment=EnvironmentName.production
        ).environment
        is Environment.PRODUCTION
    )
    path = tmp_path / "config.toml"
    _config(path, environment="production", auth_type="token")
    assert resolve_settings(config_file=path).environment is Environment.PRODUCTION


def test_unknown_profile_attributed_to_profile(runner, tmp_path):
    result = runner.invoke(
        app,
        [
            "--config",
            str(tmp_path / "absent"),
            "--profile",
            "ghost",
            "profile",
            "current",
        ],
    )
    assert result.exit_code == 2
    assert "Invalid value for --profile" in plain(result.output)


@pytest.mark.parametrize(
    "nip",
    [
        "0000000000",
        "1234567890",
        "123",
        "abcdefghij",
        "５２６１０４０８２８",
        "5261040829",
    ],
)
def test_invalid_nip_at_profile_and_runtime_boundaries(runner, tmp_path, nip):
    path = tmp_path / "config.toml"
    result = runner.invoke(
        app,
        [
            "--no-config",
            "--config",
            str(path),
            "profile",
            "create",
            "bad",
            "--env",
            "test",
            "--nip",
            nip,
            "--test-cert",
        ],
    )
    assert result.exit_code != 0
    assert "checksum" in result.output
    assert not path.exists()
    with pytest.raises(BadParameter, match="checksum"):
        resolve_settings(no_config=True, nip=nip, token="never-sent")


@pytest.mark.parametrize("environment", ["production", "demo"])
def test_test_certificate_rejected_before_transport(runner, tmp_path, environment):
    path = tmp_path / "config.toml"
    result = runner.invoke(
        app,
        [
            "--no-config",
            "--config",
            str(path),
            "profile",
            "create",
            "bad",
            "--env",
            environment,
            "--nip",
            "5261040828",
            "--test-cert",
        ],
    )
    assert result.exit_code != 0
    assert not path.exists()
    with pytest.raises(BadParameter, match="TEST"):
        resolve_settings(
            no_config=True,
            environment=EnvironmentName(environment),
            test_certificate=True,
        )
    _config(path, environment=environment)
    with pytest.raises(BadParameter, match="TEST"):
        resolve_settings(config_file=path)
    # An explicit real credential displaces the profile's test-certificate method.
    assert (
        resolve_settings(config_file=path, token="real-token").environment
        is Environment[environment.upper()]
    )


def test_current_honors_no_config(runner, tmp_path):
    path = tmp_path / "config.toml"
    _config(path)
    assert (
        payload(
            runner.invoke(app, ["--config", str(path), "--json", "profile", "current"])
        )["name"]
        == "local"
    )
    assert payload(
        runner.invoke(
            app, ["--no-config", "--config", str(path), "--json", "profile", "current"]
        )
    ) == {"name": None, "profile": None}


def test_delete_checks_existence_and_handles_eof_and_y_alias(runner, tmp_path):
    path = tmp_path / "config.toml"
    _config(path)
    args = ["--config", str(path), "profile", "delete"]
    missing = runner.invoke(app, [*args, "ghost"])
    assert "not defined" in plain(missing.output)
    assert "Delete profile" not in missing.output
    eof = runner.invoke(app, [*args, "local"])
    assert eof.exit_code == 1
    assert "--yes" in plain(eof.output)
    assert "local" in path.read_text()
    assert runner.invoke(app, [*args, "local", "-y"]).exit_code == 0


def _client(handler):
    return Client(
        Environment.TEST,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )


@pytest.mark.parametrize("json_mode", [False, True])
def test_login_masks_both_tokens_but_saves_resumable_state(runner, tmp_path, json_mode):
    from conftest import FakeAuthenticated, FakeClient, FakeService

    state = auth_state(access_token="private-access", refresh_token="private-refresh")
    path = tmp_path / "auth.json"
    args = [
        "--no-config",
        *(["--json"] if json_mode else []),
        "--nip",
        "5261040828",
        "--token",
        "ksef-secret",
        "auth",
        "login",
        "--save-state",
        str(path),
    ]
    result = runner.invoke(
        app,
        args,
        obj=fake_runtime(
            client=FakeClient(
                authentication=FakeService(with_token=FakeAuthenticated(state))
            )
        ),
    )
    assert result.exit_code == 0, result.output
    assert (
        "private-access" not in result.output and "private-refresh" not in result.output
    )
    assert "--save-state" in result.output
    assert "**********" in result.output
    assert json.loads(path.read_text())["access_token"] == "private-access"
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_refresh_real_sdk_from_state_and_explicit_token(runner, tmp_path):
    path = tmp_path / "auth.json"
    path.write_text(
        auth_state(access_token="old-access", refresh_token="saved-refresh").to_json()
    )
    requests = []
    until = datetime.now(UTC) + timedelta(hours=1)

    def handler(request):
        requests.append(request)
        assert request.method == "POST"
        assert request.url.path.endswith("/auth/token/refresh")
        return httpx.Response(
            200,
            json={
                "accessToken": {
                    "token": "new-private-access",
                    "validUntil": until.isoformat(),
                }
            },
        )

    for args, expected in [
        (["--auth-state", str(path)], "saved-refresh"),
        (["--refresh-token", "explicit-refresh"], "explicit-refresh"),
    ]:
        result = runner.invoke(
            app,
            ["--no-config", "--json", "auth", "refresh", *args],
            obj=fake_runtime(client=_client(handler)),
        )
        assert result.exit_code == 0, result.output
        assert requests[-1].headers["Authorization"] == f"Bearer {expected}"
        assert "new-private-access" not in result.output
        assert payload(result)["access_token"]["token"] == "**********"
    saved = json.loads(path.read_text())
    assert saved["access_token"] == "new-private-access"
    assert saved["refresh_token"] == "saved-refresh"
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


@pytest.mark.parametrize("status", [204, 500])
def test_logout_real_sdk_terminates_auth_session_and_retains_state_on_failure(
    runner, tmp_path, status
):
    path = tmp_path / "auth.json"
    path.write_text(auth_state(access_token="saved-access").to_json())
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(status)

    result = runner.invoke(
        app,
        ["--no-config", "auth", "logout", "--auth-state", str(path)],
        obj=fake_runtime(client=_client(handler)),
    )
    assert requests[0].method == "DELETE"
    assert requests[0].url.path.endswith("/auth/sessions/current")
    assert requests[0].headers["Authorization"] == "Bearer saved-access"
    assert (result.exit_code == 0) == (status == 204), result.output
    assert path.exists() == (status != 204)


def test_real_crypto_encrypted_pem_and_p12_loaders(tmp_path):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = x509.Name(
        [x509.NameAttribute(NameOID.COMMON_NAME, "Local contract test")]
    )
    now = datetime.now(UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=1))
        .not_valid_after(now + timedelta(days=1))
        .sign(key, hashes.SHA256())
    )
    password = "local-test-password"
    encryption = serialization.BestAvailableEncryption(password.encode())
    cert_path, key_path, p12_path = [
        tmp_path / name for name in ("cert.pem", "key.pem", "auth.p12")
    ]
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, encryption
        )
    )
    p12_path.write_bytes(
        pkcs12.serialize_key_and_certificates(b"local", key, cert, None, encryption)
    )
    for loader in [
        lambda pw: load_pem_credentials(
            cert_path=cert_path, key_path=key_path, key_password=pw
        ),
        lambda pw: load_p12_credentials(p12_path, password=pw),
    ]:
        loaded_cert, loaded_key = loader(password)
        assert loaded_cert.fingerprint(hashes.SHA256()) == cert.fingerprint(
            hashes.SHA256()
        )
        assert (
            loaded_key.public_key().public_numbers()
            == key.public_key().public_numbers()
        )
        signature = loaded_key.sign(b"local proof", padding.PKCS1v15(), hashes.SHA256())
        key.public_key().verify(
            signature, b"local proof", padding.PKCS1v15(), hashes.SHA256()
        )
        with pytest.raises(ValueError):
            loader("wrong-password")


@pytest.mark.parametrize("save_copy", [False, True])
def test_refresh_global_state_and_optional_destination(runner, tmp_path, save_copy):
    source, target = tmp_path / "source.json", tmp_path / "target.json"
    original = auth_state(refresh_token="saved-refresh").to_json()
    source.write_text(original)

    def handler(request):
        assert request.headers["Authorization"] == "Bearer saved-refresh"
        return httpx.Response(
            200,
            json={
                "accessToken": {
                    "token": "updated-access",
                    "validUntil": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
                }
            },
        )

    result = runner.invoke(
        app,
        [
            "--no-config",
            "--auth-state",
            str(source),
            "auth",
            "refresh",
            *(["--save-state", str(target)] if save_copy else []),
        ],
        obj=fake_runtime(client=_client(handler)),
    )
    assert result.exit_code == 0, result.output
    destination = target if save_copy else source
    assert json.loads(destination.read_text())["access_token"] == "updated-access"
    if save_copy:
        assert source.read_text() == original


def test_failed_refresh_keeps_state_unchanged(runner, tmp_path):
    source = tmp_path / "auth.json"
    original = auth_state().to_json()
    source.write_text(original)
    result = runner.invoke(
        app,
        ["--no-config", "auth", "refresh", "--auth-state", str(source)],
        obj=fake_runtime(client=_client(lambda request: httpx.Response(500))),
    )
    assert result.exit_code != 0
    assert source.read_text() == original


def test_refresh_rejects_conflicting_sources_without_requests(runner, tmp_path):
    source = tmp_path / "auth.json"
    source.write_text(auth_state().to_json())

    def unexpected(request):
        pytest.fail("Conflicting credentials must be rejected before HTTP")

    result = runner.invoke(
        app,
        [
            "--no-config",
            "auth",
            "refresh",
            "--auth-state",
            str(source),
            "--refresh-token",
            "other",
        ],
        obj=fake_runtime(client=_client(unexpected)),
    )
    assert result.exit_code != 0
    assert "only one" in plain(result.output)


def test_logout_expired_access_refreshes_before_terminating(runner, tmp_path):
    source = tmp_path / "auth.json"
    source.write_text(
        auth_state(access_valid_until=datetime.now(UTC) - timedelta(hours=1)).to_json()
    )
    requests = []

    def handler(request):
        requests.append(request)
        if request.url.path.endswith("/auth/token/refresh"):
            assert request.headers["Authorization"] == "Bearer refresh-token"
            return httpx.Response(
                200,
                json={
                    "accessToken": {
                        "token": "renewed-access",
                        "validUntil": (
                            datetime.now(UTC) + timedelta(hours=1)
                        ).isoformat(),
                    }
                },
            )
        assert request.method == "DELETE"
        assert request.url.path.endswith("/auth/sessions/current")
        assert request.headers["Authorization"] == "Bearer renewed-access"
        return httpx.Response(204)

    result = runner.invoke(
        app,
        ["--no-config", "auth", "logout", "--auth-state", str(source)],
        obj=fake_runtime(client=_client(handler)),
    )
    assert result.exit_code == 0, result.output
    assert len(requests) == 2
    assert not source.exists()


def test_delete_interrupted_confirmation_preserves_profile(
    runner, tmp_path, monkeypatch
):
    import click

    path = tmp_path / "config.toml"
    _config(path)
    before = path.read_bytes()
    monkeypatch.setattr("click.testing._NamedTextIOWrapper.isatty", lambda self: True)

    def interrupted(*args, **kwargs):
        raise click.Abort() from KeyboardInterrupt()

    monkeypatch.setattr("ksef2_cli.commands.profile.typer.confirm", interrupted)
    result = runner.invoke(app, ["--config", str(path), "profile", "delete", "local"])
    assert result.exit_code == 130, result.output
    assert "Interrupted" in result.output
    assert path.read_bytes() == before


@pytest.mark.parametrize("environment", ["production", "demo"])
def test_profile_environment_override_rejects_test_certificate_before_client(
    runner, tmp_path, environment
):
    from ksef2_cli.config import RuntimeOverrides

    path = tmp_path / "config.toml"
    _config(path)
    calls = []

    def forbidden_client():
        calls.append(True)
        raise AssertionError("Client must not be constructed")

    result = runner.invoke(
        app,
        ["--config", str(path), "--env", environment, "auth", "login"],
        obj=RuntimeOverrides(client_factory=forbidden_client),
    )
    assert result.exit_code == 2, result.output
    assert "TEST environment" in plain(result.output)
    assert calls == []


@pytest.mark.parametrize("context_type", ["internal_id", "nip_vat_ue", "peppol_id"])
def test_non_nip_token_context_is_not_validated_as_nip(context_type):
    settings = resolve_settings(
        no_config=True,
        nip="context-identifier",
        context_type=context_type,
        token="local-only",
    )
    assert settings.nip == "context-identifier"


@pytest.mark.parametrize("context_type", ["internal_id", "nip_vat_ue", "peppol_id"])
def test_profile_non_nip_token_context_round_trips(runner, tmp_path, context_type):
    path = tmp_path / "config.toml"
    result = runner.invoke(
        app,
        [
            "--no-config",
            "--config",
            str(path),
            "--json",
            "profile",
            "create",
            "external",
            "--env",
            "test",
            "--nip",
            "context-identifier",
            "--token-env",
            "LOCAL_TOKEN",
            "--context-type",
            context_type,
        ],
    )
    assert payload(result)["profile"]["nip"] == "context-identifier"
    settings = resolve_settings(config_file=path)
    assert settings.nip == "context-identifier"
    assert settings.profile.auth.context_type == context_type
