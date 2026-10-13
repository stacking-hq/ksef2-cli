"""Saving auth state on login and reusing it from a file."""

import json
import stat
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from conftest import (
    FakeAuthenticated,
    FakeClient,
    FakeService,
    auth_state,
    cli_args,
    expired_auth_state,
    fake_runtime,
    payload,
)
from ksef2.models import AuthenticationResumeState, RefreshedToken, TokenCredentials

from ksef2_cli.app import app


def _state_file(path: Path, state: AuthenticationResumeState) -> Path:
    path.write_text(state.to_json(), encoding="utf-8")
    return path


def _saved(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _methods(auth: FakeService) -> list[str]:
    return [name for name, _args, _kwargs in auth.calls]


def _resumed_state(auth: FakeService) -> AuthenticationResumeState:
    """Return the state handed to the most recent ``resume()`` call."""
    return auth.calls[-1][1][0]


def _refreshed(token: str, valid_for: timedelta) -> RefreshedToken:
    return RefreshedToken(
        access_token=TokenCredentials(
            token=token, valid_until=datetime.now(UTC) + valid_for
        )
    )


def test_auth_login_save_state_writes_secret_file(runner, tmp_path) -> None:
    state_file = tmp_path / "nested" / "auth.json"
    auth = FakeService(with_token=FakeAuthenticated(auth_state()))

    result = runner.invoke(
        app,
        cli_args(
            "--nip",
            "5261040828",
            "--token",
            "secret",
            "auth",
            "login",
            "--save-state",
            str(state_file),
        ),
        obj=fake_runtime(client=FakeClient(authentication=auth)),
    )

    assert payload(result)["access_token"]["valid_until"]
    assert _saved(state_file)["access_token"] == "access-token"
    assert _saved(state_file)["refresh_token"] == "refresh-token"
    assert stat.S_IMODE(state_file.stat().st_mode) == 0o600


def test_auth_login_prints_tokens_in_text_mode(runner, tmp_path) -> None:
    state_file = tmp_path / "auth.json"
    auth = FakeService(with_token=FakeAuthenticated(auth_state()))

    result = runner.invoke(
        app,
        [
            "--no-config",
            "--nip",
            "5261040828",
            "--token",
            "secret",
            "auth",
            "login",
            "--save-state",
            str(state_file),
        ],
        obj=fake_runtime(client=FakeClient(authentication=auth)),
    )

    assert result.exit_code == 0, result.output
    assert "access_token: access-token" in result.output
    assert "refresh_token: refresh-token" in result.output


def test_auth_login_without_save_state_writes_nothing(runner, tmp_path) -> None:
    state_file = tmp_path / "auth.json"

    result = runner.invoke(
        app,
        cli_args("--nip", "5261040828", "--token", "secret", "auth", "login"),
        obj=fake_runtime(
            client=FakeClient(
                authentication=FakeService(with_token=FakeAuthenticated())
            )
        ),
    )

    assert result.exit_code == 0, result.output
    assert not state_file.exists()


def test_auth_resume_reuses_valid_access_token_without_refresh(
    runner, tmp_path
) -> None:
    state_file = _state_file(tmp_path / "auth.json", auth_state())
    auth = FakeService(resume=FakeAuthenticated())

    result = runner.invoke(
        app,
        cli_args("auth", "resume", "--state-file", str(state_file)),
        obj=fake_runtime(client=FakeClient(authentication=auth)),
    )

    assert payload(result)["refresh_token"]["valid_until"]
    assert _methods(auth) == ["resume"]
    assert _resumed_state(auth).access_token.get_secret_value() == "access-token"


def test_auth_resume_refreshes_expired_access_token_and_saves_it(
    runner, tmp_path
) -> None:
    saved = tmp_path / "resumed.json"
    state_file = _state_file(
        tmp_path / "auth.json",
        expired_auth_state(refresh_valid_until=datetime.now(UTC) + timedelta(days=3)),
    )
    auth = FakeService(
        refresh=_refreshed("fresh-access", timedelta(hours=2)),
        resume=FakeAuthenticated(),
    )

    result = runner.invoke(
        app,
        cli_args(
            "auth",
            "resume",
            "--state-file",
            str(state_file),
            "--save-state",
            str(saved),
        ),
        obj=fake_runtime(client=FakeClient(authentication=auth)),
    )

    assert payload(result)["access_token"]["valid_until"]
    assert auth.called("refresh")["refresh_token"] == "refresh-token"
    assert _resumed_state(auth).access_token.get_secret_value() == "fresh-access"
    assert _saved(saved)["access_token"] == "fresh-access"
    assert stat.S_IMODE(saved.stat().st_mode) == 0o600


def test_auth_resume_rejects_state_whose_refresh_token_expired(
    runner, tmp_path
) -> None:
    expired = datetime.now(UTC) - timedelta(days=1)
    state_file = _state_file(
        tmp_path / "auth.json",
        expired_auth_state(refresh_valid_until=expired),
    )
    auth = FakeService(resume=FakeAuthenticated())

    result = runner.invoke(
        app,
        cli_args("auth", "resume", "--state-file", str(state_file)),
        obj=fake_runtime(client=FakeClient(authentication=auth)),
    )

    assert result.exit_code == 1
    assert "refresh token expired" in result.output
    assert "auth login" in result.output
    assert auth.calls == []


def test_auth_resume_without_state_source_is_usage_error(runner) -> None:
    result = runner.invoke(
        app, cli_args("auth", "resume"), obj=fake_runtime(client=FakeClient())
    )

    assert result.exit_code == 1
    assert "--state-file" in result.output


def test_auth_resume_reports_a_redacted_state_file(runner, tmp_path) -> None:
    # ``model_dump_json`` masks the bearer tokens, so such a file cannot resume anything.
    state_file = tmp_path / "auth.json"
    state_file.write_text(auth_state().model_dump_json(), encoding="utf-8")

    result = runner.invoke(
        app,
        cli_args("auth", "resume", "--state-file", str(state_file)),
        obj=fake_runtime(client=FakeClient(authentication=FakeService())),
    )

    assert result.exit_code == 1
    assert "does not hold resumable auth state" in result.output


def test_global_auth_state_resumes_other_commands(runner, tmp_path) -> None:
    state_file = _state_file(tmp_path / "auth.json", auth_state())
    certificates = FakeService(get_limits={"limits": "ok"})
    auth = FakeService(
        resume=SimpleNamespace(certificates=certificates),
        with_token=SimpleNamespace(certificates=certificates),
    )

    result = runner.invoke(
        app,
        cli_args("--auth-state", str(state_file), "certificates", "limits"),
        obj=fake_runtime(client=FakeClient(authentication=auth)),
    )

    assert payload(result) == {"limits": "ok"}
    assert _methods(auth) == ["resume"]


def test_global_auth_state_conflicts_with_other_auth_methods(runner, tmp_path) -> None:
    state_file = _state_file(tmp_path / "auth.json", auth_state())
    auth = FakeService(with_token=FakeAuthenticated())

    result = runner.invoke(
        app,
        cli_args(
            "--auth-state",
            str(state_file),
            "--nip",
            "5261040828",
            "--token",
            "secret",
            "auth",
            "login",
        ),
        obj=fake_runtime(client=FakeClient(authentication=auth)),
    )

    assert result.exit_code == 1
    assert "only one auth method" in result.output
    assert _methods(auth) == []
