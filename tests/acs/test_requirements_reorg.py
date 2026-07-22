"""MAR-145 spec 02 — functional/non-functional requirements reorg.

Covers AC-4 (content-preservation across the flat -> functional/non-functional
re-split), the positive topology half of AC-4/AC-5 (the move is complete, not
a copy-and-leave), AC-2 (the README documents the functional/non-functional
model + the requirements_layout setting), and the no-hardcoding half of AC-6
(the /acs:code merge-routing prose resolves the subfolder via settings, never
a literal marketplace path).

Stdlib-only (json, os, re, unittest). Run:
  python3 -m unittest tests.acs.test_mar145_requirements_reorg -v
"""

import json
import os
import re
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO_ROOT, "tests", "acs"))

import evidence_sidecar  # noqa: E402

REQ = os.path.join(REPO_ROOT, "docs", "requirements")
FUNCTIONAL = os.path.join(REQ, "functional")
NON_FUNCTIONAL = os.path.join(REQ, "non-functional")
FIXTURE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "fixtures", "mar145_clause_inventory.json")

ORIGINAL_FLAT_FILES = (
    "overview.md", "skills.md", "hooks.md", "workflow.md", "configuration.md",
    "reflection.md", "usage.md", "workspace-and-state.md", "tabp.md",
)

EXPECTED_FUNCTIONAL_FILES = {
    "workflow.md", "skills.md", "hooks.md", "reflection.md",
    "configuration.md", "workspace-and-state.md", "usage.md", "tabp.md",
}

EXPECTED_NON_FUNCTIONAL_FILES = {
    "packaging-distribution.md", "portability.md", "statelessness.md",
    "security.md", "reliability-resumability.md", "performance-cost.md",
    "quality-gates.md",
}


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _tree_bodies():
    """Read every file under functional/ + non-functional/ once."""
    bodies = []
    for d in (FUNCTIONAL, NON_FUNCTIONAL):
        if not os.path.isdir(d):
            continue
        for name in os.listdir(d):
            if name.endswith(".md") and not evidence_sidecar.is_evidence_sidecar(name):
                bodies.append(read(os.path.join(d, name)))
    return bodies


class ContentPreservationTest(unittest.TestCase):
    """AC-4: every MUST/SHOULD/MAY/[OPEN]/[ASSUMPTION]-tagged clause (or an
    equivalent clause-level unit — a markdown table data row) inventoried
    from the flat pre-reorg source files lands in EXACTLY ONE file under the
    reorganized functional/ + non-functional/ tree. The fixture was captured
    from docs/requirements/*.md before the move (commit d1531e3); overview.md
    contributes only its Packaging/Distribution/Core-principles sections —
    its Vision/Goals-framing/Target-domains/Out-of-scope content is retained
    as context in the rewritten README.md instead (design non-1:1 seam rule),
    which this functional/non-functional exact-one-place check deliberately
    does not cover."""

    @classmethod
    def setUpClass(cls):
        with open(FIXTURE, encoding="utf-8") as fh:
            cls.fixture = json.load(fh)["clauses_by_source_file"]
        cls.bodies = _tree_bodies()

    def _homes(self, clause):
        return [i for i, body in enumerate(self.bodies) if clause in body]

    def test_every_clause_lands_in_exactly_one_destination_file(self):
        missing = []
        duplicated = []
        for source, clauses in self.fixture.items():
            for clause in clauses:
                homes = self._homes(clause)
                if len(homes) == 0:
                    missing.append((source, clause))
                elif len(homes) > 1:
                    duplicated.append((source, clause, len(homes)))
        self.assertEqual(
            missing, [],
            "clauses dropped by the reorg (present in no functional/"
            "non-functional file): %r" % (missing[:5],))
        self.assertEqual(
            duplicated, [],
            "clauses duplicated across >1 functional/non-functional file: "
            "%r" % (duplicated[:5],))

    def test_fixture_is_non_trivial(self):
        total = sum(len(v) for v in self.fixture.values())
        self.assertGreater(
            total, 200,
            "the clause fixture looks truncated (expected the full "
            "pre-reorg inventory, ~283 lines)")


class PositiveTopologyTest(unittest.TestCase):
    """AC-4/AC-5: the reorganized tree exists and the move is complete (not
    a copy-and-leave) -- none of the 9 original flat content filenames sit
    directly under docs/requirements/ any more."""

    def test_functional_dir_exists_with_expected_files(self):
        self.assertTrue(os.path.isdir(FUNCTIONAL),
                         "docs/requirements/functional/ must exist")
        actual = {f for f in os.listdir(FUNCTIONAL)
                  if f.endswith(".md") and not evidence_sidecar.is_evidence_sidecar(f)}
        self.assertEqual(actual, EXPECTED_FUNCTIONAL_FILES)

    def test_non_functional_dir_exists_with_expected_files(self):
        self.assertTrue(os.path.isdir(NON_FUNCTIONAL),
                         "docs/requirements/non-functional/ must exist")
        actual = {f for f in os.listdir(NON_FUNCTIONAL)
                  if f.endswith(".md") and not evidence_sidecar.is_evidence_sidecar(f)}
        self.assertEqual(actual, EXPECTED_NON_FUNCTIONAL_FILES)

    def test_original_flat_files_no_longer_present(self):
        for name in ORIGINAL_FLAT_FILES:
            self.assertFalse(
                os.path.isfile(os.path.join(REQ, name)),
                "%s must no longer exist directly under docs/requirements/ "
                "(move must be complete, not copy-and-leave)" % name)

    def test_readme_still_present(self):
        self.assertTrue(os.path.isfile(os.path.join(REQ, "README.md")))


class ReadmeDocumentsModelTest(unittest.TestCase):
    """AC-2 (README half): docs/requirements/README.md documents the
    functional/non-functional model -- its Documents index lists the two
    subfolders (replacing the old flat 8-row table) and the prose names the
    structure plus the requirements_layout setting."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(os.path.join(REQ, "README.md"))

    def test_documents_index_lists_functional_subfolder(self):
        self.assertIn("functional/", self.body)

    def test_documents_index_lists_non_functional_subfolder(self):
        self.assertIn("non-functional/", self.body)

    def test_prose_names_the_model(self):
        lowered = self.body.lower()
        self.assertIn("functional", lowered)
        self.assertIn("non-functional", lowered)

    def test_mentions_requirements_layout_setting(self):
        self.assertIn("requirements_layout", self.body)

    def test_old_flat_table_rows_removed(self):
        # the old Documents table linked bare filenames directly under
        # docs/requirements/ (e.g. "[overview.md](overview.md)"); those bare
        # same-directory links must be gone now that the files moved.
        self.assertNotIn("[overview.md](overview.md)", self.body)
        self.assertNotIn("[skills.md](skills.md)", self.body)


class NoMarketplacePathHardcodingTest(unittest.TestCase):
    """AC-6 (no-hardcoding half): /acs:code's requirements-merge routing
    prose resolves the functional/non-functional subfolder via
    settings.requirements_layout (placeholder syntax), never a literal
    marketplace-specific 'docs/requirements/functional/...' path."""

    SCOPED_FILES = (
        os.path.join(REPO_ROOT, "plugins", "acs", "skills", "code", "SKILL.md"),
        os.path.join(REPO_ROOT, "plugins", "acs", "agents", "code-executor.md"),
        os.path.join(REPO_ROOT, "plugins", "acs", "agents", "code-verifier.md"),
    )

    LITERAL_PATH_RE = re.compile(
        r"docs/requirements/(functional|non-functional)/\S")

    def test_no_literal_resolved_subfolder_path_in_merge_routing_prose(self):
        for path in self.SCOPED_FILES:
            body = read(path)
            m = self.LITERAL_PATH_RE.search(body)
            self.assertIsNone(
                m,
                "%s hardcodes a literal marketplace requirements path (%r) "
                "instead of resolving via settings.requirements_layout" % (
                    path, m.group(0) if m else None))

    def test_merge_routing_prose_uses_settings_placeholder(self):
        for path in self.SCOPED_FILES:
            body = read(path)
            self.assertIn(
                "requirements_layout", body,
                "%s must resolve the functional/non-functional subfolder "
                "via settings.requirements_layout, not a hardcoded path"
                % path)


if __name__ == "__main__":
    unittest.main()
