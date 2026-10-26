import importlib.metadata

import ksef2_cli


def test_version_matches_package_metadata() -> None:
    assert ksef2_cli.__version__ == importlib.metadata.version("ksef2-cli")
