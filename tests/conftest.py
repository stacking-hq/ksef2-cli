import base64
import json
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from ksef2 import Environment, FormSchema
from ksef2.domain.models.batch import BatchSessionResumeState
from ksef2.domain.models.session import OnlineSessionResumeState
from typer.testing import CliRunner

from ksef2_cli.config import OutputMode, RuntimeOverrides, Settings

# Resume state validates that the session key is Base64 of 32 raw bytes and the IV of 16.
_SESSION_AES_KEY = base64.b64encode(b"aes-key-32-bytes" * 2).decode("ascii")
_SESSION_IV = base64.b64encode(b"iv-16-bytes!!!!!").decode("ascii")


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    for item in items:
        path_parts = set(Path(str(item.fspath)).parts)
        if "unit" in path_parts:
            item.add_marker(pytest.mark.unit)
        elif "component" in path_parts:
            item.add_marker(pytest.mark.component)
        elif "e2e" in path_parts:
            item.add_marker(pytest.mark.e2e)


def cli_args(*args: str) -> list[str]:
    return ["--no-config", "--json", *args]


def payload(result: Any) -> Any:
    assert result.exit_code == 0, result.output
    return json.loads(result.output)


def settings(**overrides: Any) -> Settings:
    values = {
        "config_file": overrides.pop("config_file", None),
        "config_loaded": False,
        "profile_name": None,
        "profile": None,
        "environment": Environment.TEST,
        "output": OutputMode.json,
        "verbose": False,
        "nip": "5261040828",
        "token": None,
        "context_type": None,
        "test_certificate": False,
        "cert": None,
        "key": None,
        "key_password": None,
        "p12": None,
        "p12_password": None,
        "poll_interval": None,
        "auth_timeout": None,
        "runtime_overrides": None,
    }
    values.update(overrides)
    if values["config_file"] is None:
        values["config_file"] = Path("config.toml")
    return Settings(**values)


def online_state(reference_number: str = "online-ref") -> OnlineSessionResumeState:
    return OnlineSessionResumeState.from_encoded(
        reference_number=reference_number,
        aes_key=base64.b64decode(_SESSION_AES_KEY, validate=True),
        iv=base64.b64decode(_SESSION_IV, validate=True),
        valid_until=datetime(2026, 1, 1, tzinfo=UTC),
        form_code=FormSchema.FA3,
    )


def batch_state(reference_number: str = "batch-ref") -> BatchSessionResumeState:
    return BatchSessionResumeState.from_encoded(
        reference_number=reference_number,
        aes_key=base64.b64decode(_SESSION_AES_KEY, validate=True),
        iv=base64.b64decode(_SESSION_IV, validate=True),
        form_code=FormSchema.FA3,
        part_upload_requests=[],
    )


class FakeClient:
    def __init__(self, **services: Any) -> None:
        self.entered = 0
        self.exited = 0
        for name, service in services.items():
            setattr(self, name, service)

    def __enter__(self) -> "FakeClient":
        self.entered += 1
        return self

    def __exit__(self, *args: object) -> None:
        self.exited += 1


class FakeService:
    def __init__(self, **returns: Any) -> None:
        self.returns = returns
        self.calls: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = []

    def __enter__(self) -> "FakeService":
        return self

    def __exit__(self, *args: object) -> None:
        pass

    def __getattr__(self, name: str) -> Any:
        def method(*args: Any, **kwargs: Any) -> Any:
            self.calls.append((name, args, kwargs))
            result = self.returns.get(name, {"method": name, "kwargs": kwargs})
            if isinstance(result, Exception):
                raise result
            if callable(result):
                return result(*args, **kwargs)
            return result

        return method

    def called(self, name: str) -> dict[str, Any]:
        for call_name, _args, kwargs in self.calls:
            if call_name == name:
                return kwargs
        raise AssertionError(f"{name!r} was not called; calls={self.calls!r}")


def fake_runtime(
    *,
    client: FakeClient | None = None,
    auth: Any | None = None,
    model_reader: Any | None = None,
    p12_credentials_loader: Any | None = None,
    pem_credentials_loader: Any | None = None,
) -> RuntimeOverrides:
    fake_client = client or FakeClient()
    authenticated_factory = (
        (lambda: SimpleNamespace(client=fake_client, auth=auth))
        if auth is not None
        else None
    )
    return RuntimeOverrides(
        client_factory=lambda: fake_client,
        authenticated_client_factory=authenticated_factory,
        model_reader=model_reader,
        p12_credentials_loader=p12_credentials_loader,
        pem_credentials_loader=pem_credentials_loader,
    )
