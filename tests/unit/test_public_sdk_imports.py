"""Fail on imports from internal ksef2 module paths.

ksef2 1.0 moves its internals to private ``_``-prefixed modules without
compatibility aliases, so the CLI may only import from the public API.
"""

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCANNED = ("src", "tests", "scripts")
LEGACY_INTERNAL = {"core", "domain", "infra", "endpoints", "services"}


def _internal_reason(module: str) -> str | None:
    parts = module.split(".")
    if parts[0] != "ksef2" or len(parts) == 1:
        return None
    if any(part.startswith("_") for part in parts[1:]):
        return "private (_-prefixed) component"
    if parts[1] in LEGACY_INTERNAL:
        return f"legacy internal package ksef2.{parts[1]}"
    if parts[1] == "clients" and len(parts) > 2:
        return "ksef2.clients.<module>; import from ksef2.clients"
    return None


def _violations(source: str) -> list[tuple[int, str, str]]:
    found = []
    for node in ast.walk(ast.parse(source)):
        modules: list[str] = []
        if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            modules = [node.module]
            if node.module == "ksef2":
                modules += [f"ksef2.{alias.name}" for alias in node.names]
        elif isinstance(node, ast.Import):
            modules = [alias.name for alias in node.names]
        for module in modules:
            if reason := _internal_reason(module):
                found.append((node.lineno, module, reason))
    return found


def _python_files() -> list[Path]:
    return sorted(
        path
        for directory in SCANNED
        if (ROOT / directory).is_dir()
        for path in (ROOT / directory).rglob("*.py")
    )


def test_no_internal_ksef2_imports() -> None:
    problems = [
        f"{path.relative_to(ROOT)}:{line}: {module} ({reason})"
        for path in _python_files()
        for line, module, reason in _violations(path.read_text())
    ]
    assert not problems, "internal ksef2 imports found:\n" + "\n".join(problems)


@pytest.mark.parametrize(
    "statement",
    [
        "from ksef2.core.xades import load_certificate_from_pem",
        "from ksef2.domain.models import KSeFBaseModel",
        "from ksef2.clients.authenticated import AuthenticatedClient",
        "from ksef2._core import xades",
        "from ksef2.models._base import KSeFBaseModel",
        "from ksef2 import _core",
        "import ksef2.infra.http",
    ],
)
def test_checker_flags_internal_imports(statement: str) -> None:
    assert _violations(statement)


@pytest.mark.parametrize(
    "statement",
    [
        "from ksef2 import Client, Environment",
        "from ksef2.clients import AuthenticatedClient",
        "from ksef2.models import AuthTokens",
        "from ksef2.xades import load_certificate_from_pem",
        "from ksef2.testdata import generate_nip",
        "import ksef2",
    ],
)
def test_checker_allows_public_imports(statement: str) -> None:
    assert not _violations(statement)
