"""Shared predicate for the `.evidence.md` sidecar convention (test-harness only)."""

import os

SIDECAR_SUFFIX = ".evidence.md"


def is_evidence_sidecar(path):
    """Return True iff `path`'s basename ends with the sidecar suffix."""
    return os.path.basename(path).endswith(SIDECAR_SUFFIX)
