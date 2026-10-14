"""Recoverable on-disk artifact for a prepared batch package.

``PreparedBatch`` keeps its encrypted parts in ``Field(exclude=True)`` members, so no
public dump of the model can be read back: ``model_dump()`` drops the part bytes and
the AES key, IV, and encrypted key that the upload needs. The artifact therefore keeps
the part bytes in their own files and the encryption material through the SDK's own
``BatchEncryptionData.to_sensitive_dict()`` export, joined by a JSON manifest.

The manifest also records ``PreparedBatch.recovery_digest()``, so loading an artifact
proves the parts on disk are the ones ``batch prepare`` wrote. Treat the whole directory
as credential material: it holds a session key and invoice payloads.
"""

import json
from pathlib import Path
from typing import Never

from ksef2.models import (
    BatchEncryptionData,
    BatchFileInfo,
    BatchInvoiceHash,
    BatchPreparedPart,
    FormSchema,
    PreparedBatch,
)
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from ksef2_cli.exceptions import UsageError
from ksef2_cli.io import SECRET_MODEL_FILE_MODE, write_bytes_file, write_text_file

ARTIFACT_KIND = "ksef2-cli.prepared-batch"
ARTIFACT_VERSION = 1
MANIFEST_NAME = "prepared.json"
PARTS_DIR = "parts"


class PreparedPartFile(BaseModel):
    """One encrypted part stored beside the manifest."""

    model_config = ConfigDict(extra="forbid")

    ordinal_number: int = Field(ge=1)
    file: str
    file_size: int = Field(ge=0)
    file_hash: str


class PreparedBatchManifest(BaseModel):
    """Manifest describing a stored prepared batch and how to reassemble it."""

    model_config = ConfigDict(extra="forbid")

    kind: str = ARTIFACT_KIND
    version: int = ARTIFACT_VERSION
    form_code: str
    offline_mode: bool = False
    batch_file: BatchFileInfo
    invoices: list[BatchInvoiceHash] = Field(default_factory=list)
    encryption: dict[str, str | None]
    parts: list[PreparedPartFile] = Field(min_length=1)
    digest: str = Field(pattern=r"^[0-9a-f]{64}$")


def _fail(
    message: str, hints: tuple[str, ...], *, cause: BaseException | None = None
) -> Never:
    error = UsageError(
        message,
        title="Prepared batch artifact is not usable",
        hints=hints,
    )
    raise error from cause


def _recreate_hint(directory: Path) -> str:
    return f"Re-create it with: ksef2 batch prepare INVOICE.xml --out {directory}"


def write_prepared_batch(directory: Path, batch: PreparedBatch) -> Path:
    """Store a prepared batch as ``directory/prepared.json`` plus one file per part.

    Args:
        directory: Artifact directory to write into, created when missing.
        batch: Prepared batch returned by ``auth.batch.prepare()``.

    Returns:
        The artifact directory.
    """
    parts: list[PreparedPartFile] = []
    # The order is kept as prepared because recovery_digest() covers the part sequence,
    # so reordering here would make the artifact fail its own check.
    for part in batch.parts:
        relative = f"{PARTS_DIR}/part-{part.ordinal_number:04d}.bin"
        _ = write_bytes_file(
            directory / relative, part.content, file_mode=SECRET_MODEL_FILE_MODE
        )
        parts.append(
            PreparedPartFile(
                ordinal_number=part.ordinal_number,
                file=relative,
                file_size=part.file_size,
                file_hash=part.file_hash,
            )
        )

    manifest = PreparedBatchManifest(
        # form_code serializes as the enum's tuple value, so the manifest keeps the
        # name instead, which is also what the CLI's --form option accepts.
        form_code=batch.form_code.name,
        offline_mode=batch.offline_mode,
        batch_file=batch.batch_file,
        invoices=batch.invoices,
        encryption=batch.encryption.to_sensitive_dict(),
        parts=parts,
        digest=batch.recovery_digest(),
    )
    _ = write_text_file(
        directory / MANIFEST_NAME,
        json.dumps(manifest.model_dump(mode="json"), indent=2) + "\n",
        file_mode=SECRET_MODEL_FILE_MODE,
    )
    return directory


def _read_manifest(directory: Path) -> PreparedBatchManifest:
    path = directory / MANIFEST_NAME
    try:
        payload = path.read_text(encoding="utf-8")
    except FileNotFoundError as error:
        _fail(
            f"{directory} has no {MANIFEST_NAME}, so it is not a prepared "
            "batch artifact.",
            (_recreate_hint(directory),),
            cause=error,
        )
    except OSError as error:
        _fail(
            f"Can't read {path}: {error.strerror or error}",
            (_recreate_hint(directory),),
            cause=error,
        )

    try:
        manifest = PreparedBatchManifest.model_validate_json(payload)
    except ValidationError as error:
        _fail(
            f"{path} is not a readable prepared batch manifest.",
            (str(error), _recreate_hint(directory)),
            cause=error,
        )

    if manifest.kind != ARTIFACT_KIND:
        _fail(
            f"{path} describes {manifest.kind!r}, not a prepared batch.",
            (_recreate_hint(directory),),
        )
    if manifest.version != ARTIFACT_VERSION:
        _fail(
            f"{path} uses artifact version {manifest.version}, this CLI writes "
            f"version {ARTIFACT_VERSION}.",
            (_recreate_hint(directory),),
        )

    ordinals = [part.ordinal_number for part in manifest.parts]
    if len(set(ordinals)) != len(ordinals):
        _fail(
            f"{path} lists the same part more than once: {sorted(ordinals)}.",
            (_recreate_hint(directory),),
        )
    return manifest


def _part_path(directory: Path, manifest_path: Path, relative: str) -> Path:
    candidate = Path(relative)
    if (
        candidate.is_absolute()
        or ".." in candidate.parts
        or candidate.parts[:1] != (PARTS_DIR,)
    ):
        _fail(
            f"{manifest_path} points outside the artifact directory: {relative!r}.",
            (_recreate_hint(directory),),
        )
    return directory / candidate


def read_prepared_batch(directory: Path) -> PreparedBatch:
    """Rebuild the exact ``PreparedBatch`` written by ``write_prepared_batch()``.

    Args:
        directory: Artifact directory produced by ``batch prepare``.

    Returns:
        A prepared batch whose ``recovery_digest()`` matches the stored one.

    Raises:
        UsageError: If the manifest is missing or malformed, or a part file no longer
            matches what was prepared.
    """
    manifest = _read_manifest(directory)
    manifest_path = directory / MANIFEST_NAME

    try:
        form_code = FormSchema[manifest.form_code]
    except KeyError as error:
        _fail(
            f"{manifest_path} declares unknown form schema {manifest.form_code!r}.",
            (_recreate_hint(directory),),
            cause=error,
        )

    parts: list[BatchPreparedPart] = []
    for descriptor in manifest.parts:
        path = _part_path(directory, manifest_path, descriptor.file)
        try:
            content = path.read_bytes()
        except OSError as error:
            _fail(
                f"{path} is missing from the artifact: {error.strerror or error}",
                (_recreate_hint(directory),),
                cause=error,
            )
        if len(content) != descriptor.file_size:
            _fail(
                f"{path} holds {len(content)} bytes, but {manifest_path} recorded "
                f"{descriptor.file_size} for part {descriptor.ordinal_number}.",
                (_recreate_hint(directory),),
            )
        parts.append(
            BatchPreparedPart(
                ordinal_number=descriptor.ordinal_number,
                content=content,
                file_size=descriptor.file_size,
                file_hash=descriptor.file_hash,
            )
        )

    try:
        batch = PreparedBatch(
            form_code=form_code,
            offline_mode=manifest.offline_mode,
            batch_file=manifest.batch_file,
            invoices=manifest.invoices,
            encryption=BatchEncryptionData(**manifest.encryption),
            parts=parts,
        )
    except (ValidationError, TypeError) as error:
        _fail(
            f"{manifest_path} does not hold complete batch encryption material.",
            (str(error), _recreate_hint(directory)),
            cause=error,
        )

    if batch.recovery_digest() != manifest.digest:
        _fail(
            f"The parts in {directory} no longer match the package they were prepared "
            "for, so KSeF would reject them.",
            (_recreate_hint(directory),),
        )
    return batch
