"""Pin the release metadata contract for the ksef2 1.0 line.

The published wheel must refuse any SDK outside ``>=1.0,<2`` even while
development installs ksef2 from the SDK's 1.0 release branch through the
``[tool.uv.sources]`` override (ksef2 1.0.0 is not on PyPI yet, see
stacking-hq/ksef2#147). These tests keep the project version, the declared
SDK bounds, the in-package ``__version__``, and the locked SDK version from
drifting apart. No network access.
"""

import re
import sys
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PYPROJECT = ROOT / "pyproject.toml"
UV_LOCK = ROOT / "uv.lock"

EXPECTED_VERSION = "1.0.0"
EXPECTED_SDK_SPECIFIER = ">=1.0,<2"


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


def test_normal_dependency_refuses_pre_1_0_sdk(pyproject: dict) -> None:
    requirement = _sdk_requirement(pyproject["project"]["dependencies"], extras=False)
    assert requirement == f"ksef2{EXPECTED_SDK_SPECIFIER}"


def test_pdf_extra_refuses_pre_1_0_sdk(pyproject: dict) -> None:
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
    # Guards against a `uv lock` run silently downgrading the SDK below 1.0
    # (the only ksef2 on PyPI while the 1.0 release is unpublished is 0.22.2).
    locked = [p for p in uv_lock["package"] if p["name"] == "ksef2"]
    assert len(locked) == 1
    version = _as_tuple(locked[0]["version"])
    assert (1, 0) <= version < (2, 0), f"locked ksef2 {locked[0]['version']} breaks {EXPECTED_SDK_SPECIFIER}"


def test_git_source_override_is_documented_when_present(pyproject: dict) -> None:
    override = pyproject.get("tool", {}).get("uv", {}).get("sources", {}).get("ksef2")
    if override is None:
        pytest.skip("no development source override; ksef2 resolves from PyPI")
    assert "git" in override, "expected the ksef2 dev override to pin a git source"
    lines = PYPROJECT.read_text(encoding="utf-8").splitlines()
    header = lines.index("[tool.uv.sources]")
    comments: list[str] = []
    for line in reversed(lines[:header]):
        stripped = line.strip()
        if stripped.startswith("#"):
            comments.append(stripped)
        elif not stripped:
            continue
        else:
            break
    annotated = " ".join(comments).upper()
    assert "DEVELOPMENT OVERRIDE" in annotated or "RELEASE BLOCKER" in annotated, (
        "the [tool.uv.sources] ksef2 override must carry a clear dev-override comment"
    )
