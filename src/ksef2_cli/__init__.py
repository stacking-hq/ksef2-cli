"""Command-line interface for the ksef2 SDK."""

from importlib.metadata import PackageNotFoundError, version

__all__ = ["__version__"]

try:
    __version__ = version("ksef2-cli")
except PackageNotFoundError:
    __version__ = "unknown"
