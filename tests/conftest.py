import base64
import json
import re
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from ksef2 import Environment, FormSchema
from ksef2.models import (
    AuthenticationResumeState,
    AuthTokens,
    BatchEncryptionData,
    BatchFilePart,
    BatchFileInfo,
    BatchInvoiceHash,
    BatchPreparedPart,
    BatchSessionResumeState,
    OnlineSessionResumeState,
    PreparedBatch,
    TokenStatusResponse,
)
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


_ANSI = re.compile(r"\x1b\[[0-9;]*m")


def plain(output: str) -> str:
    """Output as one line of text, whatever colour and wrapping the terminal added.

    CI forces colour and an 80-column width, which splits long messages (they embed
    the temporary directory) across lines and wraps option names in escape codes.
    """

    return " ".join(_ANSI.sub("", output).split())


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
        "auth_state": None,
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


def auth_state(
    *,
    access_token: str = "access-token",
    refresh_token: str = "refresh-token",
    access_valid_until: datetime | None = None,
    refresh_valid_until: datetime | None = None,
) -> AuthenticationResumeState:
    """Saved auth state whose access token is valid for a day and refresh token for two."""

    now = datetime.now(UTC)
    return AuthenticationResumeState(
        access_token=access_token,
        access_token_valid_until=access_valid_until or now + timedelta(days=1),
        refresh_token=refresh_token,
        refresh_token_valid_until=refresh_valid_until or now + timedelta(days=2),
    )


def expired_auth_state(
    *,
    refresh_valid_until: datetime | None = None,
) -> AuthenticationResumeState:
    """Saved auth state whose access token expired an hour ago."""

    return auth_state(
        access_valid_until=datetime.now(UTC) - timedelta(hours=1),
        refresh_valid_until=refresh_valid_until,
    )


def batch_state(reference_number: str = "batch-ref") -> BatchSessionResumeState:
    return BatchSessionResumeState.from_encoded(
        reference_number=reference_number,
        aes_key=base64.b64decode(_SESSION_AES_KEY, validate=True),
        iv=base64.b64decode(_SESSION_IV, validate=True),
        form_code=FormSchema.FA3,
        part_upload_requests=[],
    )


# Encrypted part payloads, as they come back from batch preparation.
PREPARED_PARTS = [b"encrypted-part-one", b"encrypted-part-two"]


def prepared_batch(*, offline_mode: bool = False) -> PreparedBatch:
    """A prepared package shaped the way ``auth.batch.prepare()`` returns one.

    Parts keep the order they were prepared in, which is the order the recovery digest
    covers, so a test that needs another order has to reorder the returned model.
    """

    parts = [
        BatchPreparedPart(
            ordinal_number=index,
            content=content,
            file_size=len(content),
            file_hash=f"part-hash-{index}",
        )
        for index, content in enumerate(PREPARED_PARTS, start=1)
    ]
    return PreparedBatch(
        form_code=FormSchema.FA3,
        offline_mode=offline_mode,
        batch_file=BatchFileInfo(
            file_size=sum(len(part.content) for part in parts),
            file_hash="batch-file-hash",
            parts=[
                BatchFilePart(
                    ordinal_number=part.ordinal_number,
                    file_size=part.file_size,
                    file_hash=part.file_hash,
                )
                for part in parts
            ],
        ),
        parts=parts,
        encryption=BatchEncryptionData.from_bytes(
            aes_key=b"aes-key-32-bytes" * 2,
            iv=b"iv-16-bytes!!!!!",
            encrypted_key=b"encrypted-session-key",
            public_key_id="key-id",
        ),
        invoices=[
            BatchInvoiceHash(
                file_name=f"invoice-{part.ordinal_number}.xml",
                invoice_hash=f"invoice-hash-{part.ordinal_number}",
            )
            for part in parts
        ],
    )


class FakePager:
    """Stand-in for ``ksef2.clients.Pager``, the 1.0 return type of list calls.

    Construct it with the pages a list call should yield, e.g.
    ``FakePager([item1, item2], [item3])``. ``first_page()`` returns the first
    page, ``pages()`` every page, and iterating yields every item.
    """

    def __init__(self, *pages: list[Any]) -> None:
        self._pages = [list(page) for page in pages] or [[]]

    def first_page(self) -> list[Any]:
        return list(self._pages[0])

    def pages(self) -> Iterator[list[Any]]:
        return iter([list(page) for page in self._pages])

    def __iter__(self) -> Iterator[Any]:
        return (item for page in self._pages for item in page)


class FakeTokenHandle:
    """Stand-in for ``ksef2.clients.GeneratedToken``, the handle ``generate()`` returns.

    The handle carries the one-time token and polls for activation, so tests can
    assert on the arguments passed to ``wait()`` and on the status it returns.
    """

    def __init__(
        self, *, reference_number: str, token: str, status: str = "active"
    ) -> None:
        self.reference_number = reference_number
        self.token = token
        self.status = TokenStatusResponse(
            reference_number=reference_number, status=status
        )
        self.wait_calls: list[dict[str, Any]] = []

    def wait(self, **kwargs: Any) -> TokenStatusResponse:
        self.wait_calls.append(kwargs)
        return self.status


class FakeAuthenticated:
    """Stand-in for ``ksef2.clients.AuthenticatedClient``, the branch auth calls return.

    Carries the resume state an authenticated branch reports, so commands can save it.
    """

    def __init__(
        self, state: AuthenticationResumeState | None = None, **services: Any
    ) -> None:
        self._state = state or auth_state()
        for name, service in services.items():
            setattr(self, name, service)

    @property
    def auth_tokens(self) -> AuthTokens:
        return self._state.to_tokens()

    def resume_state(self) -> AuthenticationResumeState:
        return self._state


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
    invoice_pdf_renderer: Any | None = None,
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
        invoice_pdf_renderer=invoice_pdf_renderer,
    )
