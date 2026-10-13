"""Unit tests for rehydrating saved authentication state."""

import json
import stat
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from conftest import FakeAuthenticated, auth_state, expired_auth_state, settings
from ksef2.models import RefreshedToken, TokenCredentials

from ksef2_cli.exceptions import AuthenticationConfigError
from ksef2_cli.runtime import renew_resume_state, write_back_resume_state


class _Auth:
    def __init__(self, returned: RefreshedToken) -> None:
        self.returned = returned
        self.calls: list[dict[str, object]] = []

    def refresh(self, **kwargs: object) -> RefreshedToken:
        self.calls.append(kwargs)
        return self.returned


def _client(refreshed: RefreshedToken) -> SimpleNamespace:
    return SimpleNamespace(authentication=_Auth(refreshed))


def test_renew_keeps_state_and_calls_nothing_while_access_is_valid() -> None:
    state = auth_state()
    client = _client(_refreshed())

    assert renew_resume_state(client, state) is state
    assert client.authentication.calls == []


def test_renew_reads_naive_saved_timestamps_as_utc() -> None:
    naive_past = datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=1)
    state = auth_state(access_valid_until=naive_past)

    renewed = renew_resume_state(_client(_refreshed()), state)

    assert renewed.access_token.get_secret_value() == "fresh-access"


def test_renew_exchanges_the_refresh_token_when_access_expired() -> None:
    state = expired_auth_state()
    renewed_at = datetime.now(UTC) + timedelta(hours=6)
    client = _client(_refreshed(valid_until=renewed_at))

    renewed = renew_resume_state(client, state)

    assert client.authentication.calls == [{"refresh_token": "refresh-token"}]
    assert renewed.access_token.get_secret_value() == "fresh-access"
    assert renewed.access_token_valid_until == renewed_at
    # The refresh token is reused as-is, so its own expiry still decides the end of life.
    assert renewed.refresh_token.get_secret_value() == "refresh-token"
    assert renewed.refresh_token_valid_until == state.refresh_token_valid_until


def test_renew_stops_when_nothing_can_be_refreshed_anymore() -> None:
    expired = datetime.now(UTC) - timedelta(hours=1)
    state = auth_state(access_valid_until=expired, refresh_valid_until=expired)

    with pytest.raises(AuthenticationConfigError, match="refresh token expired"):
        renew_resume_state(_client(_refreshed()), state)


def test_write_back_ignores_commands_that_did_not_resume_state(tmp_path) -> None:
    path = tmp_path / "auth.json"

    assert write_back_resume_state(settings(auth_state=None), _branch()) is None
    assert not path.exists()


def test_write_back_returns_the_current_state_at_secret_mode(tmp_path) -> None:
    path = tmp_path / "auth.json"
    path.write_text("stale", encoding="utf-8")

    saved = write_back_resume_state(
        settings(auth_state=path), _branch(access_token="refreshed-access")
    )

    assert saved == path
    assert json.loads(path.read_text(encoding="utf-8"))["access_token"] == (
        "refreshed-access"
    )
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_write_back_does_not_resurrect_a_state_file_the_command_removed(
    tmp_path,
) -> None:
    path = tmp_path / "nested" / "auth.json"

    assert write_back_resume_state(settings(auth_state=path), _branch()) is None
    assert not path.exists()


def _branch(**state_overrides: object) -> FakeAuthenticated:
    return FakeAuthenticated(auth_state(**state_overrides))  # type: ignore[arg-type]


def _refreshed(valid_until: datetime | None = None) -> RefreshedToken:
    return RefreshedToken(
        access_token=TokenCredentials(
            token="fresh-access",
            valid_until=valid_until or datetime.now(UTC) + timedelta(hours=2),
        )
    )
