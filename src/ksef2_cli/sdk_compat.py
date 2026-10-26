"""Temporary shims for SDK APIs the CLI still needs until a replacement exists."""

from __future__ import annotations

import warnings
from collections.abc import Iterator
from contextlib import contextmanager


@contextmanager
def allow_deprecated_batch_reference_reads() -> Iterator[None]:
    """Call ``auth.batch`` status/list helpers that take a bare session reference.

    Those service methods are deprecated in favour of ``BatchSessionClient``, which
    needs encryption state the CLI does not have for reference-only reads. Until the
    SDK exposes a non-deprecated reference API, keep the calls listed in
    ``PENDING_MIGRATION`` and silence their ``DeprecationWarning`` so
    ``-W error::DeprecationWarning`` (SDK-head CI) does not turn them into crashes.
    """

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        yield
