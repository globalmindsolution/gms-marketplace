"""MAR-119 spec 03 — conformance-chain, docs, and CHANGELOG sweep.

Prose-contract tests over the five conformance-chain locations
(`docs/architecture/lld/contracts.md`, `docs/architecture/hld/overview.md`,
`docs/requirements/non-functional/quality-gates.md` (the SEVEN_NODE chain
lives in the moved "PRD at the top" Core-principles row, MAR-145),
`docs/requirements/functional/workflow.md`,
`docs/README.md`), the code-verifier and create-design-verifier
living-requirements descriptions (`docs/requirements/functional/skills.md`,
`docs/requirements/functional/reflection.md`), the durable MAR-119 CHANGELOG entry, and
the Flow-2 no-new-flow-file guardrail.

Stdlib-only (os, re, unittest). Run:
  python3 -m unittest tests.acs.test_mar119_docs_chain -v
"""

import os
import re
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN = os.path.join(REPO_ROOT, "plugins", "acs")

CORE = "architecture → principles → standards → design"
SEVEN_NODE = ("PRD → architecture → principles → standards → "
              "design → specs → code")
NINE_NODE = ("PRD → architecture → principles → standards → "
             "design → specs → code → verify → release")

CONTRACTS_MD = os.path.join(REPO_ROOT, "docs", "architecture", "lld", "contracts.md")
HLD_OVERVIEW_MD = os.path.join(REPO_ROOT, "docs", "architecture", "hld", "overview.md")
REQ_OVERVIEW_MD = os.path.join(REPO_ROOT, "docs", "requirements",
                                "non-functional", "quality-gates.md")
WORKFLOW_MD = os.path.join(REPO_ROOT, "docs", "requirements", "functional", "workflow.md")
DOCS_README_MD = os.path.join(REPO_ROOT, "docs", "README.md")
SKILLS_MD = os.path.join(REPO_ROOT, "docs", "requirements", "functional", "skills.md")
REFLECTION_MD = os.path.join(REPO_ROOT, "docs", "requirements", "functional", "reflection.md")
FLOWS_DIR = os.path.join(REPO_ROOT, "docs", "architecture", "lld", "flows")

FIVE_FILES = [CONTRACTS_MD, HLD_OVERVIEW_MD, REQ_OVERVIEW_MD, WORKFLOW_MD, DOCS_README_MD]
SEVEN_NODE_FILES = [CONTRACTS_MD, HLD_OVERVIEW_MD, REQ_OVERVIEW_MD, WORKFLOW_MD]

BASELINE_FLOWS = {
    "hook-gated-skill-run.md",
    "ship-pipeline.md",
    "standardize-project.md",
    "tabp-screening-state-write.md",
    "tabp-usage-read.md",
    "ticket-lifecycle.md",
}
# MAR-125 (E2E-1) legitimately added enforce-e2e-merge-gate.md — its OWN
# binding design (MAR-124/design.md Flow 1) requires a new standing flow
# file, unlike MAR-119's Flow 2 (a re-anchor, no new file). This guardrail
# still catches an ACCIDENTAL new flow file from a future MAR-119-adjacent
# change; it is not meant to freeze the directory against every later ticket.
KNOWN_LATER_ADDITIONS = {"enforce-e2e-merge-gate.md", "release-cut.md"}


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def section(body, heading):
    """Return the text of a markdown section: from the line whose start is
    `heading` (matched at line-start) up to the next same-or-higher-level
    heading (or end of file)."""
    m = re.search(r"(?m)^" + re.escape(heading) + r".*$", body)
    if m is None:
        raise AssertionError("heading %r not found" % heading)
    start = m.start()
    level = len(heading) - len(heading.lstrip("#"))
    nxt = re.search(r"(?m)^#{1,%d} \S" % level, body[m.end():])
    end = m.end() + nxt.start() if nxt else len(body)
    return body[start:end]


def norm(text):
    """Collapse whitespace/newlines to single spaces, so a prose substring
    check tolerates markdown line-wrapping (e.g. "technical\\n  standards")."""
    return re.sub(r"\s+", " ", text)


class ChainCoreSegmentTest(unittest.TestCase):
    """AC-5: the shared 'architecture -> principles -> standards -> design'
    core segment is present at all five conformance-chain locations."""

    def test_core_segment_present_in_all_five_files(self):
        for path in FIVE_FILES:
            body = read(path)
            self.assertIn(
                CORE, body,
                "%s must contain the chain core segment %r" % (path, CORE))


class ChainFullStringExactnessTest(unittest.TestCase):
    """AC-5: the byte-identical 7-node chain at the four non-README
    locations; the 9-node chain (with the verify -> release suffix) at
    docs/README.md only."""

    def test_seven_node_chain_at_four_locations(self):
        for path in SEVEN_NODE_FILES:
            body = read(path)
            self.assertIn(
                SEVEN_NODE, body,
                "%s must contain the 7-node chain %r" % (path, SEVEN_NODE))

    def test_nine_node_chain_at_docs_readme_only(self):
        body = read(DOCS_README_MD)
        self.assertIn(
            NINE_NODE, body,
            "docs/README.md must contain the 9-node chain %r" % NINE_NODE)

    def test_seven_and_nine_node_constants_share_core(self):
        self.assertIn(CORE, SEVEN_NODE)
        self.assertIn(CORE, NINE_NODE)


class ContractsMdSettingsKeysTest(unittest.TestCase):
    """AC-5: contracts.md's Settings key list gains principles_path? and
    standards_path? after adr_path?."""

    def test_principles_and_standards_path_keys_present(self):
        body = read(CONTRACTS_MD)
        self.assertIn("principles_path", body,
                       "contracts.md Settings key list must mention "
                       "principles_path")
        self.assertIn("standards_path", body,
                       "contracts.md Settings key list must mention "
                       "standards_path")


class SkillsMdCodeVerifierDimensionTest(unittest.TestCase):
    """AC-6: the code-verifier living-requirements bullet in skills.md
    names the standards/ doc set + fallback as the source of truth for the
    re-anchored technical-standards dimension."""

    def _bullet_window(self):
        body = read(SKILLS_MD)
        m = re.search(r"(?m)^- The `code-verifier` MUST review the changeset.*$", body)
        self.assertIsNotNone(
            m, "skills.md must have the code-verifier MUST-review bullet")
        nxt = re.search(r"(?m)^- ", body[m.end():])
        end = m.end() + nxt.start() if nxt else len(body)
        return norm(body[m.start():end])

    def test_bullet_retains_technical_standards_label(self):
        window = self._bullet_window()
        self.assertIn("technical standards", window.lower(),
                       "the bullet must still name technical standards")

    def test_bullet_names_standards_source_of_truth(self):
        window = self._bullet_window()
        self.assertTrue(
            "standards_path" in window or "`standards/`" in window,
            "the code-verifier bullet must name standards_path or "
            "`standards/` as the re-anchored dimension's source of truth")


class SkillsMdCreateDesignVerifierDimensionTest(unittest.TestCase):
    """C-4: the create-design-verifier living-requirements description gains
    a minimal standards-conformance clause, mirroring the code-verifier
    edit, so it stays consistent with create-design-verifier.md's committed
    consistency/nfr standards sub-check."""

    def _bullet_window(self):
        body = read(SKILLS_MD)
        m = re.search(r"(?m)^- The `create-design-verifier` checks:.*$", body)
        self.assertIsNotNone(
            m, "skills.md must have the create-design-verifier checks bullet")
        nxt = re.search(r"(?m)^- ", body[m.end():])
        end = m.end() + nxt.start() if nxt else len(body)
        return norm(body[m.start():end])

    def test_bullet_names_standards_source_of_truth(self):
        window = self._bullet_window()
        self.assertTrue(
            "standards_path" in window or "`standards/`" in window,
            "the create-design-verifier bullet must name standards_path or "
            "`standards/`")

    def test_bullet_keeps_original_checks(self):
        window = self._bullet_window()
        for original in ("alternatives", "consistency", "feasibility", "NFR"):
            self.assertIn(original, window,
                           "the original check list item %r must be kept" % original)


class ReflectionMdDimensionTest(unittest.TestCase):
    """AC-6: reflection.md's broadest-scope Note gains the same
    standards/-doc-set + fallback parenthetical as skills.md."""

    def _note_window(self):
        body = read(REFLECTION_MD)
        m = re.search(r"the `code-verifier` carries the broadest verification scope", body)
        self.assertIsNotNone(
            m, "reflection.md must have the broadest-verification-scope Note")
        start = body.rfind("\n", 0, m.start()) + 1
        nxt = re.search(r"(?m)^>\s*$", body[m.end():])
        end = m.end() + nxt.start() if nxt else len(body)
        return norm(body[start:end])

    def test_note_retains_technical_standards_label(self):
        window = self._note_window()
        self.assertIn("technical standards", window.lower(),
                       "the Note must still name technical standards")

    def test_note_names_standards_source_of_truth(self):
        window = self._note_window()
        self.assertTrue(
            "standards_path" in window or "`standards/`" in window,
            "the reflection.md Note must name standards_path or "
            "`standards/`")


class ChangelogMar119EntryTest(unittest.TestCase):
    """AC-6: durable-invariant CHANGELOG entry — never pins the literal
    '[Unreleased]' or a dated version string as a fixed anchor (mirrors
    ChangelogMar118EntryTest in test_create_standards_docs_eval.py)."""

    def _changelog(self):
        return read(os.path.join(PLUGIN, "CHANGELOG.md"))

    def test_changelog_mar119_entry_durable_and_references_g10(self):
        body = self._changelog()
        spans = [m.start() for m in re.finditer(r"## \[[^\]]*\]", body)] + [len(body)]
        section_text = None
        for start, end in zip(spans, spans[1:]):
            candidate = body[start:end]
            if "(MAR-119)" in candidate:
                section_text = candidate
                break
        self.assertIsNotNone(
            section_text,
            "CHANGELOG.md must contain '(MAR-119)' inside a section span")
        heading = (section_text[:section_text.index("\n")]
                   if "\n" in section_text else section_text)
        self.assertRegex(
            heading, r"## \[(Unreleased|\d+\.\d+\.\d+)\]",
            "the '(MAR-119)' entry must live under [Unreleased] or a dated "
            "semver release heading (release cuts legitimately graduate it)")
        self.assertTrue(
            "standards conformance" in section_text.lower()
            or "standards_path" in section_text,
            "the MAR-119 CHANGELOG entry must mention standards conformance "
            "or standards_path")
        self.assertIn(
            "G10", section_text,
            "the MAR-119 CHANGELOG entry must reference G10")


class NoNewFlowFileTest(unittest.TestCase):
    """AC-6 guardrail: Flow 2 is a re-anchor of the existing dimension-7
    check, not a new standing flow -- no new lld/flows/ file (design.md
    :594-601, :642 assigns a new flow doc only to Flow 1 / MAR-121)."""

    def test_flows_dir_unchanged_from_baseline(self):
        actual = set(os.listdir(FLOWS_DIR)) - KNOWN_LATER_ADDITIONS
        self.assertEqual(
            actual, BASELINE_FLOWS,
            "no new lld/flows/ file expected for MAR-119 (Flow 2 is a "
            "re-anchor, not a new flow, per design.md:594-601) beyond "
            "KNOWN_LATER_ADDITIONS")


if __name__ == "__main__":
    unittest.main()
