"""Track calls to SDK methods that ksef2 1.0 deprecates.

The tables mirror "Deprecated APIs" in the SDK's public API contract
(docs/en/reference/public-api.md in stacking-hq/ksef2). Component tests run
against fakes, so ``-W error::DeprecationWarning`` cannot catch these calls;
this scan of ``src`` does instead.

``PENDING_MIGRATION`` lists the call sites still waiting to move to the 1.0
API. Delete an entry in the same change that migrates the call. The test fails
both when a new deprecated call appears and when a listed one is gone, so the
list always matches the code.
"""

import ast
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "src" / "ksef2_cli"

# Deprecated wherever they are called.
DEPRECATED_METHODS = frozenset(
    {
        "all_metadata",
        "download_invoice",
        "export_and_download",
        "fetch_package",
        "fetch_package_bytes",
        "get_entity_roles",
        "get_export_status",
        "get_invoice_upo_by_ksef_number",
        "get_invoice_upo_by_reference",
        "get_state",
        "list_all",
        "list_all_invoices",
        "list_page",
        "model_dump_sensitive",
        "model_dump_sensitive_json",
        "open_batch_session",
        "prepare_batch",
        "prepare_batch_from_paths",
        "query_all",
        "query_all_by_ksef_number",
        "query_authorizations",
        "query_by_ksef_number",
        "query_entities",
        "query_eu_entities",
        "query_metadata",
        "query_metadata_pages",
        "query_personal",
        "query_persons",
        "query_subordinate_entities",
        "query_subunits",
        "resume_batch_session",
        "resume_online_session",
        "revoke_common",
        "schedule_export",
        "send_invoice_and_wait",
        "submit_batch",
        "submit_prepared_batch",
        "wait_for_activation",
        "wait_for_export_package",
        "wait_for_invoice_download",
        "wait_for_invoice_ready",
        "wait_for_invoices",
    }
)

# Deprecated only on one service, e.g. ``auth.tokens.status()``; the same
# method name is current elsewhere (``session.list_invoices()``).
DEPRECATED_SERVICE_METHODS = frozenset(
    {
        ("batch", "get_status"),
        ("batch", "get_upo"),
        ("batch", "list_failed_invoices"),
        ("batch", "list_invoices"),
        ("batch", "open_session"),
        ("batch", "wait_for_completion"),
        ("certificates", "all"),
        ("certificates", "query"),
        ("collective_identifiers", "query"),
        ("invoice_sessions", "all"),
        ("invoice_sessions", "query"),
        ("peppol", "all"),
        ("peppol", "query"),
        ("sessions", "all"),
        ("sessions", "close"),
        ("sessions", "query"),
        ("tokens", "status"),
    }
)

# (path relative to src/ksef2_cli, "owner.method") -> number of call sites.
PENDING_MIGRATION: dict[tuple[str, str], int] = {
    ("commands/batch.py", "batch.get_status"): 1,
    ("commands/batch.py", "batch.get_upo"): 1,
    ("commands/batch.py", "batch.list_failed_invoices"): 1,
    ("commands/batch.py", "batch.list_invoices"): 1,
    ("commands/batch.py", "batch.prepare_batch_from_paths"): 2,
    ("commands/batch.py", "batch.submit_prepared_batch"): 1,
    ("commands/batch.py", "batch.wait_for_completion"): 2,
    ("commands/invoices/receipts.py", "auth.resume_online_session"): 2,
    ("commands/invoices/receipts.py", "batch.get_status"): 2,
    ("commands/invoices/receipts.py", "batch.wait_for_completion"): 2,
    ("commands/invoices/receipts.py", "session.get_invoice_upo_by_reference"): 1,
    ("commands/invoices/receipts.py", "session.wait_for_invoice_ready"): 2,
    ("commands/online.py", "auth.resume_online_session"): 6,
    ("commands/online.py", "session.get_invoice_upo_by_ksef_number"): 1,
    ("commands/online.py", "session.get_invoice_upo_by_reference"): 1,
    ("commands/online.py", "session.get_state"): 2,
    ("commands/online.py", "session.send_invoice_and_wait"): 1,
    ("commands/online.py", "session.wait_for_invoice_ready"): 1,
    ("invoice_workflows.py", "batch.get_upo"): 1,
    ("invoice_workflows.py", "batch_client.prepare_batch_from_paths"): 2,
    ("invoice_workflows.py", "batch_client.submit_prepared_batch"): 1,
    ("invoice_workflows.py", "invoices.all_metadata"): 1,
    ("invoice_workflows.py", "invoices.download_invoice"): 1,
    ("invoice_workflows.py", "invoices.fetch_package"): 2,
    ("invoice_workflows.py", "invoices.get_export_status"): 2,
    ("invoice_workflows.py", "invoices.query_metadata"): 1,
    ("invoice_workflows.py", "invoices.schedule_export"): 2,
    ("invoice_workflows.py", "invoices.wait_for_export_package"): 2,
    ("invoice_workflows.py", "invoices.wait_for_invoice_download"): 1,
    ("invoice_workflows.py", "session.get_invoice_upo_by_reference"): 1,
    ("invoice_workflows.py", "session.get_state"): 1,
    ("invoice_workflows.py", "session.send_invoice_and_wait"): 1,
}


def _owner(node: ast.expr) -> str:
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Name):
        return node.id
    return "?"


def _deprecated_calls(path: Path) -> Counter[tuple[str, str]]:
    found: Counter[tuple[str, str]] = Counter()
    relative = path.relative_to(SOURCE).as_posix()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        method = node.func.attr
        owner = _owner(node.func.value)
        if (
            method in DEPRECATED_METHODS
            or (owner, method) in DEPRECATED_SERVICE_METHODS
        ):
            found[(relative, f"{owner}.{method}")] += 1
    return found


def test_deprecated_sdk_calls_match_the_pending_migration_list() -> None:
    found: Counter[tuple[str, str]] = Counter()
    for path in sorted(SOURCE.rglob("*.py")):
        found += _deprecated_calls(path)

    expected = Counter(PENDING_MIGRATION)
    new = found - expected
    migrated = expected - found
    problems = [
        f"new deprecated SDK call: {path}: {call}() x{count}"
        for (path, call), count in sorted(new.items())
    ] + [
        f"no longer called, delete from PENDING_MIGRATION: {path}: {call}() x{count}"
        for (path, call), count in sorted(migrated.items())
    ]
    assert not problems, "\n".join(problems)
