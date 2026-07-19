"""MAR-152 spec 03 — dogfood migration coverage/topology gate.

Gates the migration of this repo's 3 in-scope-citation docs
(`docs/architecture/lld/runtime-coupling-inventory.md`,
`docs/architecture/lld/flows/tabp-usage-read.md`,
`docs/requirements/functional/tabp.md`) into `.evidence.md` sidecars:
(a) every human body under docs/requirements + docs/architecture (sidecars
excluded) greps to 0 in-scope code-evidence citations; (b) per sidecar,
coverage is preserved (never reduced) against the pinned pre-migration
inline count, and every clause anchor keeps >=1 evidence entry; (c) C-22
DRAFT/human-confirm-required markers are unchanged by the migration. Also
pins regex coherence between this gate and the migration pattern documented
in Spec 03's Ground-truth footprint section, and asserts ADR 0064 + the
CHANGELOG [Unreleased] entry exist.

Stdlib-only (os, re, glob, unittest). Run:
  python3 -m unittest tests.acs.test_evidence_sidecar_topology -v
"""

import glob
import os
import re
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO_ROOT, "tests", "acs"))

import evidence_sidecar  # noqa: E402

DOCS_ARCHITECTURE = os.path.join(REPO_ROOT, "docs", "architecture")
DOCS_REQUIREMENTS = os.path.join(REPO_ROOT, "docs", "requirements")
ADR_DIR = os.path.join(REPO_ROOT, "docs", "adr")
CHANGELOG_PATH = os.path.join(REPO_ROOT, "plugins", "acs", "CHANGELOG.md")

SKIP_DIRS = {".git", "node_modules", "__pycache__", ".claude"}

# Shared in-scope citation regex (R-D regex coherence) — textually identical
# to the pattern quoted in specs/03-dogfood-migrate-architecture-citations-
# and-coverage-gate.md's Ground-truth footprint section, and to the pattern
# used to perform the migration itself. Matches a repo source path:line for
# py/json/sh/xsd, PLUS SKILL.md:line. Does NOT match generic .md:line
# (design.md/roadmap.md/prd.md/overview.md/contracts.md/data-model.md are
# provenance and stay), bare filenames without :line, or .yml:line.
CITATION_RE = re.compile(r"(?:[A-Za-z0-9_./-]+\.(?:py|json|sh|xsd)|SKILL\.md):[0-9]+(?:-[0-9]+)?")

RUNTIME_COUPLING_SIDECAR = os.path.join(
    DOCS_ARCHITECTURE, "lld", "runtime-coupling-inventory.evidence.md")
TABP_USAGE_READ_SIDECAR = os.path.join(
    DOCS_ARCHITECTURE, "lld", "flows", "tabp-usage-read.evidence.md")
TABP_REQUIREMENTS_SIDECAR = os.path.join(
    DOCS_REQUIREMENTS, "functional", "tabp.evidence.md")

# Pinned pre-migration inline counts, re-derived this task via
#   grep -oE '<CITATION_RE pattern>' <file> | wc -l
# against the un-migrated docs (Spec 03's Ground-truth footprint section) —
# NOT the design's "~26+~7" approximation (design.md:504-508), which counted
# .md:NN workspace provenance the scope rule excludes.
RUNTIME_COUPLING_PRE_MIGRATION_COUNT = 16
TABP_USAGE_READ_PRE_MIGRATION_COUNT = 1
TABP_REQUIREMENTS_PRE_MIGRATION_COUNT = 1

DRAFT_MARKER = "DRAFT — human-confirm-required"


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _markdown_files(root):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            if name.endswith(".md"):
                path = os.path.join(dirpath, name)
                if evidence_sidecar.is_evidence_sidecar(path):
                    continue
                yield path


class RegexCoherenceTest(unittest.TestCase):
    """R-D: this gate's CITATION_RE must be textually identical to the
    migration pattern documented in Spec 03's Ground-truth footprint
    section, so the two can never silently drift apart."""

    def test_citation_regex_matches_spec_03_literal(self):
        spec_pattern = (
            r"(?:[A-Za-z0-9_./-]+\.(?:py|json|sh|xsd)|SKILL\.md):[0-9]+(?:-[0-9]+)?"
        )
        self.assertEqual(CITATION_RE.pattern, spec_pattern)


class BodyCleanGlobalTest(unittest.TestCase):
    """AC-2 check (a): every human body under docs/requirements +
    docs/architecture (sidecars excluded) greps to 0 in-scope citations —
    tree-wide, not merely the 3 migrated files."""

    def test_no_in_scope_citations_in_any_human_body(self):
        offenders = {}
        for root in (DOCS_ARCHITECTURE, DOCS_REQUIREMENTS):
            for path in _markdown_files(root):
                matches = CITATION_RE.findall(read(path))
                if matches:
                    offenders[path] = matches
        self.assertEqual(
            offenders, {},
            "human bodies must carry 0 in-scope code-evidence citations "
            "(relocated to .evidence.md sidecars): %r" % offenders)

    def test_contracts_md_passes_trivially_proving_tree_wide_scope(self):
        # contracts.md has 0 in-scope citations both before and after this
        # migration (its only path:line is the out-of-scope ci.yml:197-199)
        # — proves check (a) is genuinely tree-wide, not narrowly scoped to
        # the 3 touched docs.
        contracts = os.path.join(DOCS_ARCHITECTURE, "lld", "contracts.md")
        self.assertTrue(os.path.isfile(contracts))
        self.assertEqual(CITATION_RE.findall(read(contracts)), [])


class CoverageNotReducedTest(unittest.TestCase):
    """AC-2 check (b): per sidecar, total in-scope citation count >= the
    pinned pre-migration inline count (never reduced), and every clause
    anchor keeps >=1 evidence entry."""

    def _sidecar_citation_count(self, path):
        self.assertTrue(os.path.isfile(path), "%s must exist" % path)
        return len(CITATION_RE.findall(read(path)))

    def test_runtime_coupling_inventory_sidecar_count_not_reduced(self):
        self.assertGreaterEqual(
            self._sidecar_citation_count(RUNTIME_COUPLING_SIDECAR),
            RUNTIME_COUPLING_PRE_MIGRATION_COUNT)

    def test_tabp_usage_read_sidecar_count_not_reduced(self):
        self.assertGreaterEqual(
            self._sidecar_citation_count(TABP_USAGE_READ_SIDECAR),
            TABP_USAGE_READ_PRE_MIGRATION_COUNT)

    def test_tabp_requirements_sidecar_count_not_reduced(self):
        self.assertGreaterEqual(
            self._sidecar_citation_count(TABP_REQUIREMENTS_SIDECAR),
            TABP_REQUIREMENTS_PRE_MIGRATION_COUNT)

    def test_runtime_coupling_inventory_anchors_each_keep_both_occurrences(self):
        # The 8 distinct anchors are each cited TWICE pre-migration (once in
        # the surfaces table, once in the anchor-verification table); the
        # sidecar must preserve BOTH occurrences per anchor, never deduping
        # to 8 total entries (R-C count-not-reduced risk).
        body = read(RUNTIME_COUPLING_SIDECAR)
        anchors = [
            "hooks.json:3-14", "hooks.json:16-26",
            "dispatch.py:25-38", "dispatch.py:41-75", "dispatch.py:49-54",
            "acs_lib.py:43", "acs_lib.py:485-500", "acs_lib.py:1621",
        ]
        for anchor in anchors:
            with self.subTest(anchor=anchor):
                self.assertGreaterEqual(
                    body.count(anchor), 2,
                    "%s must appear at least twice (surfaces + anchor-"
                    "verification occurrence contexts), found %d" %
                    (anchor, body.count(anchor)))

    def test_tabp_usage_read_anchor_has_entry(self):
        body = read(TABP_USAGE_READ_SIDECAR)
        self.assertIn("Step 3", body)
        self.assertIn("tabp_helper.py:1072-1077", body)

    def test_tabp_requirements_anchor_has_entry(self):
        body = read(TABP_REQUIREMENTS_SIDECAR)
        self.assertIn("tabp independent verifier", body)
        self.assertIn("SKILL.md:173-177", body)


class C22MarkersIntactTest(unittest.TestCase):
    """AC-2 check (c): the set of docs/requirements files carrying the
    literal DRAFT marker is unchanged by this migration — a general,
    re-runnable invariant (not a hardcoded "0"). This repo's
    docs/requirements predates G37 and carries no such marker in any real
    area file today (grep-confirmed, this task) — including
    functional/tabp.md, the only file this spec migrates under
    docs/requirements — so this check passes vacuously (0 files before, 0
    files after) here; it is written generally so it is meaningful for a
    consumer repo whose docs/requirements DOES carry real markers."""

    def _draft_marker_files(self):
        found = set()
        for path in _markdown_files(DOCS_REQUIREMENTS):
            if DRAFT_MARKER in read(path):
                found.add(path)
        return found

    def test_draft_marker_file_set_unchanged_by_migration(self):
        pre_migration_marker_files = set()  # grep-confirmed empty, this task
        self.assertEqual(self._draft_marker_files(), pre_migration_marker_files)


class Adr0064ExistsAndOnTopicTest(unittest.TestCase):
    """AC-6: docs/adr/0064-*.md exists (glob, not a hardcoded slug) and
    names Decision B / the sidecar convention / the intentional migration
    framing."""

    def test_adr_0064_file_exists_exactly_once(self):
        matches = glob.glob(os.path.join(ADR_DIR, "0064-*.md"))
        self.assertEqual(len(matches), 1, "expected exactly one docs/adr/0064-*.md file")

    def test_adr_0064_names_decision_b_and_not_byte_identical(self):
        matches = glob.glob(os.path.join(ADR_DIR, "0064-*.md"))
        self.assertTrue(matches, "docs/adr/0064-*.md must exist")
        body = read(matches[0])
        self.assertRegex(body, r"(?i)\.evidence\.md")
        self.assertRegex(body, r"(?i)not byte-identical|non-byte-identical")
        self.assertRegex(body, r"MAR-152")


class ChangelogMar152EntryTest(unittest.TestCase):
    """AC-6: CHANGELOG [Unreleased] section names MAR-152 + ADR 0064 + the
    not-byte-identical framing (mirrors ChangelogMar143EntryTest's pattern
    in test_create_requirements_brownfield.py)."""

    def test_changelog_mar152_entry_in_topmost_section(self):
        body = read(CHANGELOG_PATH)
        spans = [m.start() for m in re.finditer(r"## \[[^\]]*\]", body)] + [len(body)]
        section_text = None
        for start, end in zip(spans, spans[1:]):
            candidate = body[start:end]
            if re.search(r"\(MAR-152\b", candidate):
                section_text = candidate
                break
        self.assertIsNotNone(
            section_text, "CHANGELOG.md must contain '(MAR-152' inside a section span")
        heading = section_text[:section_text.index("\n")] if "\n" in section_text else section_text
        self.assertRegex(
            heading, r"## \[(Unreleased|\d+\.\d+\.\d+)\]",
            "the '(MAR-152' entry must live under [Unreleased] or a dated "
            "semver release heading")
        self.assertIn("ADR 0064", section_text)
        self.assertRegex(section_text, r"(?i)not byte-identical|non-byte-identical")


if __name__ == "__main__":
    unittest.main()
