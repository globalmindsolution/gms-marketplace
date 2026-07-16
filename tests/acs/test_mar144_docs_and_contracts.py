"""MAR-144 (Spec 02) — docs, ADR, and CHANGELOG contract for the
create-requirements greenfield/amend completion.

Prose/doc-fixture tests (read each file's body and assert on content), in the
style of test_mar123_docs_topology.py. They pin the Spec-02 payload:

- AC-5: the contracts.md D1 living-contract note (chain line byte-unchanged,
  requirements documented as a living contract ALONGSIDE the chain, not a
  verified conformance level, no new downstream verifier dimension).
- AC-6: the CHANGELOG [Unreleased] (MAR-144) bullet + the create-requirements
  per-skill block in functional/skills.md + the workflow.md bootstrap-path
  correction.
- AC-7: ADR 0062 (Accepted, xrefs 0060+0061) + the README decision-log row.

Stdlib-only. Run:
  python3 -m unittest tests.acs.test_mar144_docs_and_contracts -v
"""

import glob
import os
import re
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN = os.path.join(REPO_ROOT, "plugins", "acs")

CONTRACTS = os.path.join(REPO_ROOT, "docs", "architecture", "lld", "contracts.md")
SKILLS_MD = os.path.join(REPO_ROOT, "docs", "requirements", "functional", "skills.md")
WORKFLOW_MD = os.path.join(REPO_ROOT, "docs", "requirements", "functional", "workflow.md")
REQ_README = os.path.join(REPO_ROOT, "docs", "requirements", "README.md")
CHANGELOG = os.path.join(PLUGIN, "CHANGELOG.md")
ADR_DIR = os.path.join(REPO_ROOT, "docs", "adr")

# The conformance-chain inner text — MUST stay byte-identical (Decision D1).
CHAIN_TEXT = "PRD → architecture → principles → standards → design → specs → code"


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def section(body, heading):
    """Text of a markdown section: from the line whose start is `heading`
    (matched at line-start) up to the next same-or-higher-level heading."""
    m = re.search(r"(?m)^" + re.escape(heading) + r".*$", body)
    if m is None:
        raise AssertionError("heading %r not found" % heading)
    level = len(heading) - len(heading.lstrip("#"))
    nxt = re.search(r"(?m)^#{1,%d} \S" % level, body[m.end():])
    end = m.end() + nxt.start() if nxt else len(body)
    return body[m.start():end]


class ContractsD1NoteTest(unittest.TestCase):
    """AC-5 — the D1 living-contract note at the conformance-chain line."""

    def _d1_note(self):
        body = read(CONTRACTS)
        m = re.search(r"(?m)^Conformance chain:.*$", body)
        self.assertIsNotNone(m, "conformance-chain line not found in contracts.md")
        after = body[m.end():]
        paras = [p.strip() for p in re.split(r"\n\s*\n", after) if p.strip()]
        self.assertTrue(paras, "no paragraph follows the conformance-chain line")
        return paras[0]

    def test_conformance_chain_line_unchanged(self):
        body = read(CONTRACTS)
        self.assertIn(CHAIN_TEXT, body,
                      "the conformance-chain text must stay byte-identical (D1)")
        # The full chain-line sentence must survive intact, not be rewritten.
        self.assertRegex(
            body,
            r"(?m)^Conformance chain: `" + re.escape(CHAIN_TEXT)
            + r"`, each level verified against the one above it\.$")

    def test_d1_living_contract_note_present(self):
        note = self._d1_note().lower()
        self.assertIn("living", note,
                      "D1 note must describe requirements as a living contract")
        self.assertIn("alongside", note,
                      "D1 note must place requirements ALONGSIDE the chain")
        self.assertIn("not a verified conformance level", note,
                      "D1 note must state requirements is NOT a verified level")

    def test_no_new_downstream_verifier_dimension_claimed(self):
        note = self._d1_note().lower()
        # Positive: the note explicitly disclaims a downstream requirements gate.
        self.assertRegex(
            note, r"no create-spec or code-verifier dimension",
            "D1 note must disclaim any create-spec/code verifier dimension")
        # Negative: it must NOT assert a new verifier dimension was added.
        self.assertNotRegex(
            note,
            r"(adds?|added|new)\s+(a\s+)?(create-spec|code)[-\s]?verifier\s+dimension",
            "D1 note must not claim a new downstream verifier dimension exists")


class ChangelogTest(unittest.TestCase):
    """AC-6 (CHANGELOG half) — durable-invariant: the MAR-144 (and sibling
    MAR-143/MAR-145) entries live under [Unreleased] OR the current dated
    semver heading (release cuts legitimately graduate them), and tolerate a
    `, #<pr>` suffix on the ticket tag. Never a literal [Unreleased] pin."""

    def _section_for(self, tag):
        """Return (section_text, heading) of the CHANGELOG span carrying `(tag`."""
        body = read(CHANGELOG)
        spans = [m.start() for m in re.finditer(r"## \[[^\]]*\]", body)] + [len(body)]
        for start, end in zip(spans, spans[1:]):
            candidate = body[start:end]
            if re.search(r"\(" + re.escape(tag) + r"\b", candidate):
                heading = candidate[:candidate.index("\n")] if "\n" in candidate else candidate
                return candidate, heading
        return None, None

    def test_changelog_unreleased_has_mar144_entry(self):
        section, heading = self._section_for("MAR-144")
        self.assertIsNotNone(section, "CHANGELOG.md must contain a (MAR-144) entry")
        self.assertRegex(
            heading, r"## \[(Unreleased|\d+\.\d+\.\d+)\]",
            "the (MAR-144) entry must live under [Unreleased] or a dated semver heading")
        self.assertIn("### Added", section,
                      "the (MAR-144) entry's section must carry an '### Added' subsection")
        # The MAR-144 bullet (its own physical line) should cross-reference ADR 0062.
        m = re.search(r"(?m)^.*\(MAR-144\b.*$", section)
        self.assertIsNotNone(m, "MAR-144 bullet not isolatable")
        self.assertIn("0062", m.group(0),
                      "the MAR-144 CHANGELOG bullet must cross-reference ADR 0062")

    def test_changelog_mar145_mar143_entries_untouched(self):
        for tag in ("MAR-145", "MAR-143"):
            section, _ = self._section_for(tag)
            self.assertIsNotNone(section, "the pre-existing %s bullet must survive" % tag)


class SkillsMdBlockTest(unittest.TestCase):
    """AC-6 (consumer-general doc half) — the per-skill block."""

    def _block(self):
        body = read(SKILLS_MD)
        return section(body, "## `/acs:create-requirements` (product-level)")

    def test_skills_md_create_requirements_block_present(self):
        body = read(SKILLS_MD)
        self.assertIn("## `/acs:create-requirements` (product-level)", body,
                      "skills.md must gain a create-requirements product-level block")
        block = self._block().lower()
        for mode in ("brownfield", "greenfield", "amend"):
            self.assertIn(mode, block,
                          "the block must name the %s mode" % mode)
        for role in ("create-requirements-planner",
                     "create-requirements-executor",
                     "create-requirements-verifier"):
            self.assertIn(role, block,
                          "the block must name the %s triad agent" % role)

    def test_block_states_additive_and_draft_gate(self):
        block = self._block().lower()
        self.assertIn("draft", block,
                      "the block must state the DRAFT/human-confirm gate")
        self.assertTrue(
            "no-overwrite" in block or "never overwrites" in block
            or "byte-for-byte" in block,
            "the block must state the additive/no-overwrite discipline")


class WorkflowMdBootstrapTest(unittest.TestCase):
    """AC-6 (consumer-general doc half) — workflow.md correction."""

    def test_workflow_md_no_bootstrap_skill_claim_removed(self):
        body = read(WORKFLOW_MD)
        self.assertNotIn("no bootstrap skill", body,
                         "the stale 'no bootstrap skill' clause must be removed")
        self.assertIn("/acs:create-requirements", body,
                      "workflow.md must name /acs:create-requirements as the "
                      "bootstrap path")
        # The accrete-from-#1 behavior statement must be preserved.
        self.assertRegex(
            body, r"grows organically from ticket #1",
            "the accrete-from-ticket-#1 behavior must be preserved")


class Adr0062Test(unittest.TestCase):
    """AC-7 — ADR 0062 exists, Accepted, cross-references 0060 + 0061."""

    def _adr_path(self):
        hits = glob.glob(os.path.join(ADR_DIR, "0062-*.md"))
        self.assertEqual(len(hits), 1,
                         "exactly one docs/adr/0062-*.md must exist, found %r" % hits)
        return hits[0]

    def test_adr_0062_exists_and_accepted(self):
        body = read(self._adr_path())
        self.assertRegex(body, r"(?i)status\W+accepted",
                         "ADR 0062 must be Status: Accepted")
        self.assertIn("0060", body, "ADR 0062 must cross-reference ADR 0060")
        self.assertIn("0061", body, "ADR 0062 must cross-reference ADR 0061")

    def test_adr_0062_scopes_greenfield_and_draft_discipline(self):
        body = read(self._adr_path()).lower()
        self.assertIn("greenfield", body,
                      "ADR 0062 must scope the greenfield elicitation mode")
        self.assertIn("draft", body,
                      "ADR 0062 must record the DRAFT/interactive-confirm discipline")


class ReadmeDecisionLogTest(unittest.TestCase):
    """AC-7 — README decision-log row for the bootstrap path."""

    def _log(self):
        body = read(REQ_README)
        return section(body, "## Decision log")

    def test_readme_decision_log_row_present(self):
        log = self._log()
        self.assertIn("/acs:create-requirements", log,
                      "the decision log must gain a create-requirements row")
        # Newest-first: the create-requirements bootstrap row must precede the
        # pre-existing reorg row (2026-07-15 flat-reorg entry).
        rows = re.findall(r"(?m)^\|\s*20\d\d-\d\d-\d\d\s*\|.*$", log)
        self.assertTrue(rows, "no dated decision-log rows found")
        boot_idx = next((i for i, r in enumerate(rows)
                         if "/acs:create-requirements" in r), None)
        self.assertIsNotNone(boot_idx, "no create-requirements decision-log row")
        reorg_idx = next((i for i, r in enumerate(rows)
                          if "reorganized into" in r), None)
        if reorg_idx is not None:
            self.assertLess(boot_idx, reorg_idx,
                            "the create-requirements row must be newest-first")
        self.assertRegex(rows[boot_idx], r"0062",
                         "the decision-log row must cross-reference ADR 0062")


if __name__ == "__main__":
    unittest.main()
