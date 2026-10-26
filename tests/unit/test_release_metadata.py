"""Release metadata stays compatible with the published SDK 1.x line."""

import re
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PYPROJECT = ROOT / "pyproject.toml"
UV_LOCK = ROOT / "uv.lock"

EXPECTED_VERSION = "1.0.0"
EXPECTED_SDK_SPECIFIER = ">=1.1,<2"


def _load(path: Path) -> dict:
    with path.open("rb") as fh:
        return tomllib.load(fh)


@pytest.fixture(scope="module")
def pyproject() -> dict:
    return _load(PYPROJECT)


@pytest.fixture(scope="module")
def uv_lock() -> dict:
    return _load(UV_LOCK)


def _sdk_requirement(requirements: list[str], *, extras: bool) -> str:
    pattern = re.compile(r"^ksef2\[pdf\][<>=!~]" if extras else r"^ksef2[<>=!~]")
    matches = [r for r in requirements if pattern.match(r)]
    assert len(matches) == 1, f"expected exactly one ksef2 requirement, got {matches}"
    return matches[0]


def _as_tuple(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version.split("."))


def test_project_version_is_expected(pyproject: dict) -> None:
    assert pyproject["project"]["version"] == EXPECTED_VERSION


def test_normal_dependency_requires_sdk_fixes(pyproject: dict) -> None:
    requirement = _sdk_requirement(pyproject["project"]["dependencies"], extras=False)
    assert requirement == f"ksef2{EXPECTED_SDK_SPECIFIER}"


def test_pdf_extra_requires_sdk_fixes(pyproject: dict) -> None:
    requirements = pyproject["project"]["optional-dependencies"]["pdf"]
    requirement = _sdk_requirement(requirements, extras=True)
    assert requirement == f"ksef2[pdf]{EXPECTED_SDK_SPECIFIER}"


def test_package_dunder_version_matches_project(pyproject: dict) -> None:
    from ksef2_cli import __version__

    assert __version__ == pyproject["project"]["version"]


def test_locked_cli_version_matches_project(pyproject: dict, uv_lock: dict) -> None:
    locked = [p for p in uv_lock["package"] if p["name"] == "ksef2-cli"]
    assert len(locked) == 1
    assert locked[0]["version"] == pyproject["project"]["version"]


def test_locked_sdk_satisfies_declared_bounds(uv_lock: dict) -> None:
    locked = [p for p in uv_lock["package"] if p["name"] == "ksef2"]
    assert len(locked) == 1
    version = _as_tuple(locked[0]["version"])
    assert (1, 1) <= version < (2, 0), f"locked ksef2 {locked[0]['version']} breaks {EXPECTED_SDK_SPECIFIER}"


def test_sdk_resolves_from_pypi(pyproject: dict, uv_lock: dict) -> None:
    assert "ksef2" not in pyproject.get("tool", {}).get("uv", {}).get("sources", {})
    sdk = next(package for package in uv_lock["package"] if package["name"] == "ksef2")
    assert sdk["source"] == {"registry": "https://pypi.org/simple"}
