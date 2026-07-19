"""Guard test for the `.evidence.md` sidecar exclusion (MAR-152).

Pins two things: the shared `is_evidence_sidecar` predicate's classification
table, and that `test_mermaid_diagrams._markdown_files()` actually excludes a
sidecar path from its yielded set (the one doc-enumerating walk confirmed to
need the filter).
"""

import os
import sys
import tempfile
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO_ROOT, "tests", "acs"))

import evidence_sidecar  # noqa: E402
import test_mermaid_diagrams  # noqa: E402


class TestIsEvidenceSidecarTable(unittest.TestCase):
    """Unit table for `is_evidence_sidecar()` across representative paths."""

    def test_classification_table(self):
        cases = [
            ("runtime-coupling-inventory.md", False),
            ("runtime-coupling-inventory.evidence.md", True),
            ("docs/requirements/functional/checkout.md", False),
            ("docs/requirements/functional/checkout.evidence.md", True),
        ]
        for path, expected in cases:
            with self.subTest(path=path):
                self.assertEqual(evidence_sidecar.is_evidence_sidecar(path), expected)


class TestMarkdownFilesExcludesSidecars(unittest.TestCase):
    """Fixture-based proof that `_markdown_files()` skips `*.evidence.md`."""

    def test_sidecar_excluded_plain_md_included(self):
        with tempfile.TemporaryDirectory() as tmp:
            plain = os.path.join(tmp, "foo.md")
            sidecar = os.path.join(tmp, "foo.evidence.md")
            with open(plain, "w", encoding="utf-8") as f:
                f.write("# Foo\n")
            with open(sidecar, "w", encoding="utf-8") as f:
                f.write("# Foo evidence\n")

            found = set(test_mermaid_diagrams._markdown_files(tmp))

            self.assertIn(plain, found)
            self.assertNotIn(sidecar, found)


if __name__ == "__main__":
    unittest.main()
