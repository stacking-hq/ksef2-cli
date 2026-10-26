"""Bearer token display options do not change resumable credentials."""

import json
from datetime import UTC, datetime

import pytest
from conftest import (
    FakeAuthenticated,
    FakeClient,
    FakeService,
    auth_state,
    fake_runtime,
    payload,
)
from ksef2.models import RefreshedToken
from typer.testing import CliRunner

from ksef2_cli.app import app

ACCESS = "eyJhbGci-access-secret-P_eA"
REFRESH = "eyJhbGci-refresh-secret-R_eF"
ACCESS_EXPIRY = datetime(2099, 1, 1, tzinfo=UTC)
REFRESH_EXPIRY = datetime(2099, 1, 8, tzinfo=UTC)


@pytest.mark.parametrize("command", ["login", "resume", "refresh"])
@pytest.mark.parametrize("json_output", [False, True])
@pytest.mark.parametrize("show_tokens", [False, True])
def test_auth_token_display(
    runner, tmp_path, command, json_output, show_tokens
) -> None:
    state = auth_state(
        access_token=ACCESS,
        refresh_token=REFRESH,
        access_valid_until=ACCESS_EXPIRY,
        refresh_valid_until=REFRESH_EXPIRY,
    )
    auth = FakeService(
        with_token=FakeAuthenticated(state),
        resume=FakeAuthenticated(state),
        refresh=RefreshedToken(access_token=state.to_tokens().access_token),
    )
    args = ["--no-config", *(["--json"] if json_output else [])]
    if command == "login":
        args += ["--nip", "5261040828", "--token", "secret"]
    args += ["auth", command]
    if command == "resume":
        source = tmp_path / "auth.json"
        source.write_text(state.to_json(), encoding="utf-8")
        args += ["--state-file", str(source)]
    elif command == "refresh":
        args += ["--refresh-token", REFRESH]
    if show_tokens:
        args += ["--show-tokens"]

    result = runner.invoke(
        app, args, obj=fake_runtime(client=FakeClient(authentication=auth))
    )

    assert result.exit_code == 0, result.output
    expected_access = ACCESS if show_tokens else "eyJhbGci…P_eA"
    expected_refresh = REFRESH if show_tokens else "eyJhbGci…R_eF"
    if not show_tokens:
        assert ACCESS not in result.stdout
        assert REFRESH not in result.stdout
    if json_output:
        expected = {
            "access_token": expected_access,
            "access_token_valid_until": "2099-01-01T00:00:00Z",
        }
        if command != "refresh":
            expected.update(
                refresh_token=expected_refresh,
                refresh_token_valid_until="2099-01-08T00:00:00Z",
            )
        assert payload(result) == expected
    else:
        assert f"access_token: {expected_access}\n" in result.stdout
        assert "access_token_valid_until: 2099-01-01T00:00:00+00:00" in result.stdout
        if command != "refresh":
            assert f"refresh_token: {expected_refresh}\n" in result.stdout
            assert (
                "refresh_token_valid_until: 2099-01-08T00:00:00+00:00" in result.stdout
            )
    assert state.access_token.get_secret_value() == ACCESS
    assert state.refresh_token.get_secret_value() == REFRESH


@pytest.mark.parametrize("command", ["login", "resume"])
@pytest.mark.parametrize("json_output", [False, True])
@pytest.mark.parametrize("show_tokens", [False, True])
def test_save_state_always_masks_and_remains_usable(
    runner, tmp_path, command, json_output, show_tokens
) -> None:
    state = auth_state(access_token=ACCESS, refresh_token=REFRESH)
    auth = FakeService(
        with_token=FakeAuthenticated(state), resume=FakeAuthenticated(state)
    )
    saved = tmp_path / "saved.json"
    args = ["--no-config", *(["--json"] if json_output else [])]
    if command == "login":
        args += ["--nip", "5261040828", "--token", "secret"]
    args += ["auth", command, "--save-state", str(saved)]
    if command == "resume":
        source = tmp_path / "source.json"
        source.write_text(state.to_json(), encoding="utf-8")
        args += ["--state-file", str(source)]
    if show_tokens:
        args += ["--show-tokens"]

    result = runner.invoke(
        app, args, obj=fake_runtime(client=FakeClient(authentication=auth))
    )

    assert result.exit_code == 0, result.output
    assert ACCESS not in result.stdout
    assert REFRESH not in result.stdout
    assert "eyJhbGci…P_eA" in result.stdout
    assert "eyJhbGci…R_eF" in result.stdout
    if json_output:
        assert payload(result)["state_file"] == str(saved)
    else:
        assert f"state_file: {saved}" in result.stdout
    persisted = json.loads(saved.read_text(encoding="utf-8"))
    assert persisted["access_token"] == ACCESS
    assert persisted["refresh_token"] == REFRESH

    reused = FakeService(
        resume=FakeAuthenticated(
            state, certificates=FakeService(get_limits={"limits": "ok"})
        )
    )
    result = runner.invoke(
        app,
        ["--no-config", "--json", "--auth-state", str(saved), "certificates", "limits"],
        obj=fake_runtime(client=FakeClient(authentication=reused)),
    )
    assert payload(result) == {"limits": "ok"}
    resumed = reused.calls[0][1][0]
    assert resumed.access_token.get_secret_value() == ACCESS
    assert resumed.refresh_token.get_secret_value() == REFRESH

    result = runner.invoke(
        app,
        ["--no-config", "--json", "auth", "resume", "--state-file", str(saved)],
        obj=fake_runtime(client=FakeClient(authentication=reused)),
    )
    assert payload(result)["access_token"] == "eyJhbGci…P_eA"


@pytest.mark.parametrize("json_output", [False, True])
@pytest.mark.parametrize("verbose", [False, True])
def test_show_tokens_render_failure_redacts_credentials(
    monkeypatch, json_output, verbose
):
    """An explicit reveal applies to successful output, never diagnostics."""
    runner = CliRunner(mix_stderr=False)
    state = auth_state(access_token=ACCESS, refresh_token=REFRESH)
    auth = FakeService(with_token=FakeAuthenticated(state))

    def fail_render(ctx, result):
        raise RuntimeError(f"Could not render {ACCESS} {REFRESH}")

    monkeypatch.setattr("ksef2_cli.context.render", fail_render)
    result = runner.invoke(
        app,
        [
            "--no-config",
            *(["--json"] if json_output else []),
            *(["--verbose"] if verbose else []),
            "--nip",
            "5261040828",
            "--token",
            "secret",
            "auth",
            "login",
            "--show-tokens",
        ],
        obj=fake_runtime(client=FakeClient(authentication=auth)),
    )
    assert result.exit_code == 1
    assert result.stdout == ""
    assert ACCESS not in result.stderr
    assert REFRESH not in result.stderr
    assert "<redacted>" in result.stderr


@pytest.mark.parametrize("json_output", [False, True])
def test_saved_refresh_failure_redacts_saved_credentials(tmp_path, json_output):
    runner = CliRunner(mix_stderr=False)
    state = auth_state(access_token=ACCESS, refresh_token=REFRESH)
    source = tmp_path / "saved.json"
    source.write_text(state.to_json(), encoding="utf-8")
    auth = FakeService(refresh=RuntimeError(f"Rejected {ACCESS} {REFRESH}"))
    result = runner.invoke(
        app,
        [
            "--no-config",
            *(["--json"] if json_output else []),
            "--verbose",
            "auth",
            "refresh",
            "--auth-state",
            str(source),
            "--show-tokens",
        ],
        obj=fake_runtime(client=FakeClient(authentication=auth)),
    )
    assert result.exit_code == 1
    assert result.stdout == ""
    assert ACCESS not in result.stderr
    assert REFRESH not in result.stderr
    assert "<redacted>" in result.stderr
    assert json.loads(source.read_text())["refresh_token"] == REFRESH
