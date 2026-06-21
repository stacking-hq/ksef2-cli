"""Typed CLI-owned command results."""

from pathlib import Path
from typing import Generic, TypeVar

from ksef2.domain.models.batch import BatchSessionState
from ksef2.domain.models.invoices import SendInvoiceResponse
from ksef2.domain.models.session import (
    OnlineSessionState,
    SessionInvoiceStatusResponse,
    SessionStatusResponse,
)
from ksef2.domain.models.testdata import Identifier, Permission
from pydantic import BaseModel, ConfigDict, Field

from ksef2_cli.config import CliConfig, ProfileConfig

PayloadT = TypeVar("PayloadT")
ItemT = TypeVar("ItemT")


class CliResult(BaseModel):
    """Base class for CLI-owned result models."""

    model_config = ConfigDict(frozen=True)


class ActionResult(CliResult):
    """Result for a completed mutation that has no SDK response body."""

    reference_number: str | None = None
    revoked: bool | None = None


class LimitUpdated(CliResult):
    """Result for a TEST limit override update."""

    kind: str
    updated: bool = True


class LimitReset(CliResult):
    """Result for a TEST limit override reset."""

    kind: str
    reset: bool = True


class ProductionRateLimitsSet(CliResult):
    """Result for setting TEST API limits to production defaults."""

    api_rate_limits: str = "production"


class SessionClosed(CliResult):
    """Result for closing an auth or invoice session."""

    reference_number: str
    closed: bool = True


class CurrentSessionTerminated(CliResult):
    """Result for terminating the active authentication session."""

    terminated_current: bool = True


class CertificateRevoked(CliResult):
    """Result for certificate revocation."""

    serial_number: str
    reason: str | None = None
    revoked: bool = True


class ConfigPathResult(CliResult):
    """Result for resolving the local config path."""

    path: Path
    exists: bool
    loaded: bool


class ConfigShowResult(CliResult):
    """Result for showing loaded local config values."""

    path: Path
    exists: bool
    config: CliConfig


class ConfigInitialized(CliResult):
    """Result for creating a local config file."""

    path: Path
    mode: str
    config: CliConfig


class ProfileListItem(CliResult):
    """One configured CLI profile shown by ``profile list``."""

    name: str
    active: bool
    environment: str
    nip: str
    auth: str


class ProfileListResult(CliResult):
    """Configured CLI profiles."""

    profiles: list[ProfileListItem]


class ProfileSaved(CliResult):
    """Result for creating or replacing a CLI profile."""

    name: str
    active: bool
    profile: ProfileConfig


class ProfileSelected(CliResult):
    """Result for selecting the active CLI profile."""

    name: str
    profile: ProfileConfig


class ProfileCurrent(CliResult):
    """Result for showing the currently selected CLI profile."""

    name: str | None = None
    profile: ProfileConfig | None = None


class OnlineSessionOpened(CliResult):
    """Result for opening an online invoice session."""

    state_file: Path | None = None
    state: OnlineSessionState


class BatchSubmitted(CliResult):
    """Result for submitting a batch invoice session."""

    state_file: Path | None = None
    state: BatchSessionState
    status: SessionStatusResponse | None = None


class OnlineSendItem(CliResult):
    """One invoice submission made by ``online send``."""

    file: Path
    result: SendInvoiceResponse | SessionInvoiceStatusResponse


class OnlineSendResult(CliResult):
    """Result for sending invoices through an online session."""

    state_file: Path | None = None
    closed: bool
    results: list[OnlineSendItem]


class TestSubjectCreated(CliResult):
    """Result for creating a TEST subject."""

    nip: str
    created: bool = True


class TestSubjectDeleted(CliResult):
    """Result for deleting a TEST subject."""

    nip: str
    deleted: bool = True


class TestPersonCreated(CliResult):
    """Result for creating a TEST person."""

    nip: str
    pesel: str
    created: bool = True


class TestPersonDeleted(CliResult):
    """Result for deleting a TEST person."""

    nip: str
    deleted: bool = True


class TestAttachmentsEnabled(CliResult):
    """Result for enabling TEST attachments."""

    nip: str
    attachments: str = "enabled"


class TestAttachmentsRevoked(CliResult):
    """Result for revoking TEST attachments."""

    nip: str
    expected_end_date: str | None = None
    attachments: str = "revoked"


class TestContextAccessChanged(CliResult):
    """Result for blocking or unblocking a TEST auth context."""

    context_type: str
    context_value: str
    blocked: bool


class TestPermissionsGranted(CliResult):
    """Result for granting TEST permissions."""

    grant_to: Identifier
    in_context_of: Identifier
    permissions: list[Permission]


class TestPermissionsRevoked(CliResult):
    """Result for revoking TEST permissions."""

    revoke_from: Identifier
    in_context_of: Identifier
    revoked: bool = True


class TestSandboxReady(CliResult):
    """Result for a temporary TEST subject sandbox."""

    nip: str
    subject_type: str
    token: str
    reference_number: str
    token_permissions: list[str]
    sandbox_dir: Path
    cert_file: Path
    key_file: Path
    env_file: Path
    source_command: str
    token_send_command: str
    certificate_send_command: str
    cleanup: str = "remote_test_data_on_exit"


class SavedFile(CliResult):
    """Result for a file written by the CLI."""

    path: Path
    size: int = Field(serialization_alias="bytes")


class FocusedResult(CliResult, Generic[PayloadT, ItemT]):
    """Result with full JSON payload and a narrower text rendering focus."""

    payload: PayloadT
    items: list[ItemT]
