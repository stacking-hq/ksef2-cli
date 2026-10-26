"""Saving auth state on login and reusing it from a file."""

import json
import stat
from datetime import UTC, datetime, timedelta
from pathlib import Path
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
    plain,
)
from ksef2 import KSeFAuthenticationExpiredError, KSeFRateLimitError
from ksef2.models import (
    AuthenticationResumeState,
    RefreshedToken,
    TokenCredentials,
)

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

    assert payload(result)["access_token_valid_until"]
    assert _saved(state_file)["access_token"] == "access-token"
    assert _saved(state_file)["refresh_token"] == "refresh-token"
    assert stat.S_IMODE(state_file.stat().st_mode) == 0o600


def test_auth_login_masks_tokens_in_text_mode(runner, tmp_path) -> None:
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
    assert "access_token: access-t…oken" in result.output
    assert "refresh_token: refresh-…oken" in result.output


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

    assert payload(result)["refresh_token_valid_until"]
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

    assert payload(result)["access_token_valid_until"]
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
    branch = FakeAuthenticated(auth_state(), certificates=certificates)
    auth = FakeService(resume=branch)

    result = runner.invoke(
        app,
        cli_args("--auth-state", str(state_file), "certificates", "limits"),
        obj=fake_runtime(client=FakeClient(authentication=auth)),
    )

    assert payload(result) == {"limits": "ok"}
    assert _methods(auth) == ["resume"]


def test_global_auth_state_is_written_back_after_a_refresh(runner, tmp_path) -> None:
    # The SDK refreshes the access token during the command, and the new token only
    # lives in that client, so the file has to take it back or it goes stale.
    state_file = _state_file(tmp_path / "auth.json", auth_state())
    branch = FakeAuthenticated(
        auth_state(access_token="refreshed-access"),
        certificates=FakeService(get_limits={"limits": "ok"}),
    )

    result = runner.invoke(
        app,
        cli_args("--auth-state", str(state_file), "certificates", "limits"),
        obj=fake_runtime(client=FakeClient(authentication=FakeService(resume=branch))),
    )

    assert payload(result) == {"limits": "ok"}
    assert _saved(state_file)["access_token"] == "refreshed-access"
    assert stat.S_IMODE(state_file.stat().st_mode) == 0o600


def test_failed_command_leaves_the_saved_state_alone(runner, tmp_path) -> None:
    state_file = _state_file(tmp_path / "auth.json", auth_state())
    branch = FakeAuthenticated(
        auth_state(access_token="refreshed-access"),
        certificates=FakeService(
            get_limits=KSeFRateLimitError(30, "KSeF is throttling this subject")
        ),
    )

    result = runner.invoke(
        app,
        cli_args("--auth-state", str(state_file), "certificates", "limits"),
        obj=fake_runtime(client=FakeClient(authentication=FakeService(resume=branch))),
    )

    assert result.exit_code == 1
    assert _saved(state_file)["access_token"] == "access-token"


def test_expired_auth_state_is_reported_with_a_login_hint(runner, tmp_path) -> None:
    state_file = _state_file(tmp_path / "auth.json", expired_auth_state())
    branch = FakeAuthenticated(
        expired_auth_state(),
        certificates=FakeService(get_limits=KSeFAuthenticationExpiredError()),
    )

    result = runner.invoke(
        app,
        cli_args("--auth-state", str(state_file), "certificates", "limits"),
        obj=fake_runtime(client=FakeClient(authentication=FakeService(resume=branch))),
    )

    assert result.exit_code == 1
    assert "refresh token is expired" in plain(result.output)
    assert "ksef2 auth login --save-state PATH" in plain(result.output)
    assert "access-token" not in result.output


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


def _logout_setup() -> tuple[FakeClient, FakeService, FakeService]:
    """Client, authentication service, and sessions service for one logout run.

    The client has no auth method other than the saved state, so ``resume`` is the only
    way ``logout`` can reach KSeF.
    """

    sessions = FakeService(terminate_current=None)
    auth = FakeService(resume=FakeAuthenticated(sessions=sessions))
    return FakeClient(authentication=auth), auth, sessions


def test_auth_logout_ends_the_session_and_deletes_the_state(runner, tmp_path) -> None:
    state_file = _state_file(tmp_path / "auth.json", auth_state())
    client, auth, sessions = _logout_setup()

    result = runner.invoke(
        app,
        cli_args("auth", "logout", "--state-file", str(state_file)),
        obj=fake_runtime(client=client),
    )

    assert payload(result) == {
        "path": str(state_file),
        "terminated_current": True,
    }
    assert not state_file.exists()
    assert [call[0] for call in sessions.calls] == ["terminate_current"]
    assert _methods(auth) == ["resume"]
    # The state is resumed on a client of its own, which `logout` has to close.
    assert client.exited == 1


def test_auth_logout_reads_the_state_from_the_global_option(runner, tmp_path) -> None:
    state_file = _state_file(tmp_path / "auth.json", auth_state())
    client, _auth, sessions = _logout_setup()

    result = runner.invoke(
        app,
        cli_args("--auth-state", str(state_file), "auth", "logout"),
        obj=fake_runtime(client=client),
    )

    assert payload(result)["path"] == str(state_file)
    assert not state_file.exists()
    assert sessions.called("terminate_current") == {}


def test_auth_logout_never_prints_the_saved_tokens(runner, tmp_path) -> None:
    state_file = _state_file(tmp_path / "auth.json", auth_state())
    client, _auth, _sessions = _logout_setup()

    result = runner.invoke(
        app,
        ["--no-config", "auth", "logout", "--state-file", str(state_file)],
        obj=fake_runtime(client=client),
    )

    assert result.exit_code == 0, result.output
    assert "access-token" not in result.output
    assert "refresh-token" not in result.output


def test_auth_logout_keeps_the_state_when_ksef_rejects_termination(
    runner, tmp_path
) -> None:
    state_file = _state_file(tmp_path / "auth.json", auth_state())
    sessions = FakeService(terminate_current=KSeFAuthenticationExpiredError())
    auth = FakeService(resume=FakeAuthenticated(sessions=sessions))

    result = runner.invoke(
        app,
        cli_args("auth", "logout", "--state-file", str(state_file)),
        obj=fake_runtime(client=FakeClient(authentication=auth)),
    )

    # KSeF never confirmed the session ended, so the credential that still works stays.
    assert result.exit_code == 1
    assert state_file.exists()


def test_auth_logout_without_a_state_file_is_usage_error(runner) -> None:
    result = runner.invoke(
        app, cli_args("auth", "logout"), obj=fake_runtime(client=FakeClient())
    )

    assert result.exit_code == 1
    assert "--state-file" in result.output
