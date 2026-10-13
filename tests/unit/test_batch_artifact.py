"""The prepared batch artifact comes back as the exact payload that was written."""

import base64
import json
from pathlib import Path

import pytest
from conftest import PREPARED_PARTS, prepared_batch
from ksef2.models import PreparedBatch

from ksef2_cli.batch_artifact import (
    ARTIFACT_VERSION,
    MANIFEST_NAME,
    PARTS_DIR,
    read_prepared_batch,
    write_prepared_batch,
)
from ksef2_cli.exceptions import CliError


def out_of_order(batch: PreparedBatch) -> PreparedBatch:
    """The same package with its parts listed the other way round."""

    return batch.model_copy(update={"parts": list(reversed(batch.parts))})


def manifest_path(directory: Path) -> Path:
    return directory / MANIFEST_NAME


def read_manifest(directory: Path) -> dict[str, object]:
    return json.loads(manifest_path(directory).read_text(encoding="utf-8"))


def write_manifest(directory: Path, changes: dict[str, object]) -> Path:
    manifest = read_manifest(directory) | changes
    manifest_path(directory).write_text(json.dumps(manifest), encoding="utf-8")
    return manifest_path(directory)


def test_round_trip_returns_the_same_payload(tmp_path: Path) -> None:
    batch = prepared_batch(offline_mode=True)
    artifact = tmp_path / "prepared"

    assert write_prepared_batch(artifact, batch) == artifact
    loaded = read_prepared_batch(artifact)

    assert loaded.recovery_digest() == batch.recovery_digest()
    assert [part.content for part in loaded.parts] == PREPARED_PARTS
    assert loaded.offline_mode is True
    assert loaded.batch_file == batch.batch_file
    assert loaded.invoices == batch.invoices
    assert (
        loaded.encryption.to_sensitive_dict() == batch.encryption.to_sensitive_dict()
    )


def test_part_order_survives_as_prepared(tmp_path: Path) -> None:
    """The digest covers the part sequence, so loading must not renumber or sort it."""

    batch = out_of_order(prepared_batch())
    artifact = tmp_path / "prepared"
    _ = write_prepared_batch(artifact, batch)

    loaded = read_prepared_batch(artifact)

    assert [part.ordinal_number for part in loaded.parts] == [2, 1]
    assert loaded.recovery_digest() == batch.recovery_digest()


def test_artifact_keeps_the_payload_where_a_stranger_cannot_read_it(
    tmp_path: Path,
) -> None:
    _ = write_prepared_batch(tmp_path / "prepared", prepared_batch())
    artifact = tmp_path / "prepared"

    manifest = manifest_path(artifact)
    assert (manifest.stat().st_mode & 0o777) == 0o600
    assert [
        part.stat().st_mode & 0o777
        for part in sorted((artifact / PARTS_DIR).iterdir())
    ] == [0o600, 0o600]
    # The part bytes live in their own files, so the manifest alone cannot upload them.
    assert PREPARED_PARTS[0].decode() not in manifest.read_text(encoding="utf-8")
    assert read_manifest(artifact)["encryption"] == {
        "aes_key": base64.b64encode(b"aes-key-32-bytes" * 2).decode(),
        "iv": base64.b64encode(b"iv-16-bytes!!!!!").decode(),
        "encrypted_key": base64.b64encode(b"encrypted-session-key").decode(),
        "public_key_id": "key-id",
    }


def test_manifest_describes_the_package_it_stored(tmp_path: Path) -> None:
    batch = prepared_batch()
    _ = write_prepared_batch(tmp_path / "prepared", batch)

    manifest = read_manifest(tmp_path / "prepared")

    assert manifest["kind"] == "ksef2-cli.prepared-batch"
    assert manifest["version"] == ARTIFACT_VERSION
    assert manifest["form_code"] == "FA3"
    assert manifest["digest"] == batch.recovery_digest()
    assert manifest["invoices"] == [
        {"file_name": "invoice-1.xml", "invoice_hash": "invoice-hash-1"},
        {"file_name": "invoice-2.xml", "invoice_hash": "invoice-hash-2"},
    ]
    assert [part["file"] for part in manifest["parts"]] == [
        f"{PARTS_DIR}/part-0001.bin",
        f"{PARTS_DIR}/part-0002.bin",
    ]


@pytest.mark.parametrize(
    ("changes", "expected"),
    [
        ({"kind": "ksef2-cli.something-else"}, "not a prepared batch"),
        ({"version": ARTIFACT_VERSION + 1}, "version 2"),
        ({"form_code": "FA9"}, "unknown form schema"),
        ({"encryption": {"aes_key": "not-base64"}}, "encryption material"),
        (
            {
                "parts": [
                    {
                        "ordinal_number": 1,
                        "file": f"{PARTS_DIR}/part-0001.bin",
                        "file_size": 1,
                        "file_hash": "h",
                    },
                    {
                        "ordinal_number": 1,
                        "file": f"{PARTS_DIR}/part-0002.bin",
                        "file_size": 1,
                        "file_hash": "h",
                    },
                ]
            },
            "same part more than once",
        ),
        (
            {
                "parts": [
                    {
                        "ordinal_number": 1,
                        "file": "../outside.bin",
                        "file_size": 1,
                        "file_hash": "h",
                    }
                ]
            },
            "outside the artifact directory",
        ),
    ],
)
def test_rejects_manifests_it_cannot_trust(
    tmp_path: Path, changes: dict[str, object], expected: str
) -> None:
    artifact = tmp_path / "prepared"
    _ = write_prepared_batch(artifact, prepared_batch())
    _ = write_manifest(artifact, changes)

    with pytest.raises(CliError) as caught:
        _ = read_prepared_batch(artifact)

    assert expected in caught.value.message
    assert any("batch prepare" in hint for hint in caught.value.hints)


def test_missing_manifest_points_at_prepare(tmp_path: Path) -> None:
    artifact = tmp_path / "not-prepared"
    artifact.mkdir()

    with pytest.raises(CliError) as caught:
        _ = read_prepared_batch(artifact)

    assert "not a prepared batch artifact" in caught.value.message
    assert any("batch prepare" in hint for hint in caught.value.hints)


def test_detects_a_part_that_is_no_longer_the_one_prepared(tmp_path: Path) -> None:
    artifact = tmp_path / "prepared"
    _ = write_prepared_batch(artifact, prepared_batch())
    (artifact / PARTS_DIR / "part-0001.bin").write_bytes(
        b"x" * len(PREPARED_PARTS[0])
    )

    with pytest.raises(CliError) as caught:
        _ = read_prepared_batch(artifact)

    assert "no longer match the package" in caught.value.message


def test_detects_a_truncated_part_before_the_digest(tmp_path: Path) -> None:
    artifact = tmp_path / "prepared"
    _ = write_prepared_batch(artifact, prepared_batch())
    (artifact / PARTS_DIR / "part-0002.bin").write_bytes(b"short")

    with pytest.raises(CliError) as caught:
        _ = read_prepared_batch(artifact)

    assert "holds 5 bytes" in caught.value.message


def test_rejects_a_manifest_that_is_not_json(tmp_path: Path) -> None:
    artifact = tmp_path / "prepared"
    _ = write_prepared_batch(artifact, prepared_batch())
    manifest_path(artifact).write_text("prepared batch, do not upload", encoding="utf-8")

    with pytest.raises(CliError) as caught:
        _ = read_prepared_batch(artifact)

    assert "not a readable prepared batch manifest" in caught.value.message


def test_reports_a_manifest_it_cannot_open(tmp_path: Path) -> None:
    artifact = tmp_path / "prepared"
    _ = write_prepared_batch(artifact, prepared_batch())
    # A directory where the manifest should be fails the read itself, not its content.
    manifest_path(artifact).unlink()
    manifest_path(artifact).mkdir()

    with pytest.raises(CliError) as caught:
        _ = read_prepared_batch(artifact)

    assert "Can't read" in caught.value.message


def test_reports_a_part_file_the_artifact_lost(tmp_path: Path) -> None:
    artifact = tmp_path / "prepared"
    _ = write_prepared_batch(artifact, prepared_batch())
    (artifact / PARTS_DIR / "part-0002.bin").unlink()

    with pytest.raises(CliError) as caught:
        _ = read_prepared_batch(artifact)

    assert "is missing from the artifact" in caught.value.message


def test_rejects_a_digest_that_is_not_a_digest(tmp_path: Path) -> None:
    artifact = tmp_path / "prepared"
    _ = write_prepared_batch(artifact, prepared_batch())
    _ = write_manifest(artifact, {"digest": "not-a-digest"})

    with pytest.raises(CliError) as caught:
        _ = read_prepared_batch(artifact)

    assert "not a readable prepared batch manifest" in caught.value.message
