"""MAR-162 spec 03 — ADR 0007 second amendment + plugin-internal reconciliation.

Falsifiable AC-4/AC-5 guard: asserts docs/adr/0007-living-docs-by-induction.md
carries exactly three `## Amendment — ` headings with the MAR-162 one strictly
after the MAR-65 one and the MAR-72 one after both (MAR-72 promoted the third
amendment to top level), and the MAR-65 span byte-unchanged; the MAR-162 block
has all four required sub-headings and states MAR-65's obligations are
unchanged; docs-sync's shipped existence (AC-5 evidence); and cross-file
coherence — the reworded plugin-internal files no longer assert the retired
present-tense claim that /code step 4 still authors general doc updates.

Stdlib-only (os, re, unittest). Run:
  python3 -m unittest tests.acs.test_adr_0007_second_amendment -v
"""

import os
import sys
import re
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN = os.path.join(REPO_ROOT, "plugins", "acs")
ADR_0007 = os.path.join(REPO_ROOT, "docs", "adr", "0007-living-docs-by-induction.md")
DOCS_SYNC_SKILL = os.path.join(PLUGIN, "skills", "docs-sync", "SKILL.md")
README = os.path.join(PLUGIN, "README.md")
INTERNALS = os.path.join(PLUGIN, "docs", "INTERNALS.md")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from acs_case import acs_lib_source  # noqa: E402

# The MAR-65 amendment's original byte span (docs/adr/0007-…md:29-75 on
# origin/main, before this ticket's append). Recorded here so a later diff
# of that exact span can be checked for zero drift.
MAR65_SPAN_START = "## Amendment — MAR-65"
MAR65_SPAN_END = "the inductive step enforceable for the prd/roadmap doc set."


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


class Adr0007SecondAmendmentShapeTest(unittest.TestCase):
    """AC-4: the MAR-162 amendment exists, is ordered after MAR-65, and
    carries the mirrored sub-heading structure."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(ADR_0007)

    def test_exactly_three_amendment_headings(self):
        headings = re.findall(r"^## Amendment — ", self.body, re.MULTILINE)
        self.assertEqual(
            len(headings), 3,
            "docs/adr/0007 must carry exactly three '## Amendment — ' headings "
            "(MAR-65 + MAR-162 + MAR-72)")

    def test_mar162_strictly_after_mar65(self):
        mar65_at = self.body.index("## Amendment — MAR-65")
        mar162_at = self.body.index("## Amendment — MAR-162")
        self.assertLess(
            mar65_at, mar162_at,
            "the MAR-162 amendment must appear strictly after the MAR-65 "
            "amendment")

    def test_mar65_span_unchanged(self):
        start = self.body.index(MAR65_SPAN_START)
        end = self.body.index(MAR65_SPAN_END) + len(MAR65_SPAN_END)
        span = self.body[start:end]
        self.assertIn(
            "The induction loop is extended to include FACTUAL claims", span,
            "MAR-65 amendment span drifted — expected original opening prose")
        self.assertIn(
            "commit\n`44ec46e` reconciled post-MAR-55 drift", span,
            "MAR-65 amendment span drifted — expected the 44ec46e citation")

    def test_mar162_has_four_required_subheadings(self):
        mar162 = self.body[self.body.index("## Amendment — MAR-162"):]
        for heading in (
            "### Narrowed scope",
            "### Ownership boundary",
            "### Divergence rationale",
            "### Enforcement note",
        ):
            self.assertIn(heading, mar162,
                          "MAR-162 amendment missing required sub-heading %r" % heading)

    def test_mar162_mentions_docs_sync(self):
        mar162 = self.body[self.body.index("## Amendment — MAR-162"):]
        self.assertIn("docs-sync", mar162)

    def test_mar162_mentions_same_pr_branch(self):
        mar162 = self.body[self.body.index("## Amendment — MAR-162"):]
        self.assertIn("same PR/branch", mar162)

    def test_mar162_states_mar65_obligations_unchanged(self):
        mar162 = self.body[self.body.index("## Amendment — MAR-162"):]
        self.assertIsNotNone(
            re.search(r"(?i)MAR-65.{0,200}(unchanged|does not supersede|not narrow)",
                      mar162, re.DOTALL),
            "MAR-162 amendment must explicitly state MAR-65's obligations "
            "are unchanged")

    def test_mar162_enforcement_note_says_six_input(self):
        mar162 = self.body[self.body.index("## Amendment — MAR-162"):]
        self.assertIn("six-input contract", mar162)
        self.assertNotIn("five-input", mar162)
        self.assertNotIn("five inputs", mar162)

    def test_divergence_rationale_names_ac5_driver(self):
        section = self.body[self.body.index("## Amendment — MAR-162"):]
        section = section[section.index("### Divergence rationale"):
                          section.index("### Enforcement note")]
        self.assertRegex(section, r"AC #5")
        self.assertRegex(section, r"(?i)execute phase")
        self.assertNotRegex(section, r"(?i)dead letter")

    def test_no_new_adr_number_minted(self):
        """Durable invariant, rewritten under MAR-164 (C-11).

        The original form of this assertion coupled MAR-162's guarantee to
        the *global* ADR ceiling (`assertEqual(highest, 68)`). That coupling
        broke by construction the moment MAR-164 minted ADR 0069 for an
        entirely unrelated decision (Gap 1's oversized-ticket two-lever
        control) — the global ceiling was never a stable proxy for anything
        MAR-162 actually guaranteed, and any later ticket that adds an ADR
        for its own reasons would break it again regardless of MAR-162.

        What MAR-162 actually guaranteed, and what this test still checks
        directly against the ADR directory: its concern (the docs-sync
        six-input contract / AC #5 execute-phase divergence) lives solely as
        ADR 0007's *second amendment* (see test_exactly_three_amendment_headings
        above) and never consumed a standalone ADR number of its own. So no
        OTHER ADR file's own title may name MAR-162 as its subject — that
        would mean the concern had been split into a new ADR after all,
        independent of what the current global ADR ceiling happens to be.
        """
        adr_dir = os.path.dirname(ADR_0007)
        files = [f for f in os.listdir(adr_dir) if f.endswith(".md") and f[0].isdigit()]
        this_file = os.path.basename(ADR_0007)
        for fname in files:
            if fname == this_file:
                continue
            with open(os.path.join(adr_dir, fname), encoding="utf-8") as fh:
                title_line = fh.readline()
            self.assertNotIn(
                "MAR-162", title_line,
                "MAR-162's concern must stay recorded solely as ADR 0007's "
                "amendment, never as a standalone ADR file's own subject "
                "(found in %s's title)" % fname)


class Adr0007ScopeDisciplineTest(unittest.TestCase):
    """spec 03's not_docs_only constraint: docs/adr/0012 stays untouched
    (spec 03's own file map excludes it)."""

    def test_0012_not_touched_by_this_module(self):
        # This module intentionally has no assertions about 0012's content —
        # it is out of spec 03's scope. This test documents that boundary.
        path = os.path.join(REPO_ROOT, "docs", "adr", "0012-design-time-doc-consistency.md")
        self.assertTrue(os.path.isfile(path), "0012 must still exist (untouched)")


class DocsSyncMechanismEvidenceTest(unittest.TestCase):
    """AC-5 evidence: docs-sync's mechanism is shipped and wired into the
    gate — the merge-order fact itself (AC-5's 'does not merge before
    MAR-160') is a CI/human fact, not unit-testable."""

    def test_docs_sync_skill_exists(self):
        self.assertTrue(os.path.isfile(DOCS_SYNC_SKILL),
                        "plugins/acs/skills/docs-sync/SKILL.md must exist")

    def test_workflow_skills_contains_docs_sync(self):
        body = acs_lib_source()
        match = re.search(r"WORKFLOW_SKILLS\s*=\s*\[([^\]]*)\]", body)
        self.assertIsNotNone(match, "acs_lib.py must define WORKFLOW_SKILLS")
        self.assertIn('"docs-sync"', match.group(1))

    def test_gate_create_pr_requires_docs_sync(self):
        body = acs_lib_source()
        gate = body[body.index("def gate_create_pr("):]
        gate = gate[:gate.index("\ndef ")]
        self.assertIn('"docs-sync"', gate,
                      "gate_create_pr must require docs-sync completed before /acs:create-pr")


class PluginInternalDocReconciliationTest(unittest.TestCase):
    """Cross-file coherence: the reworded plugin-internal prose no longer
    asserts the retired claim that /code step 4 still authors general doc
    updates, and preserves docs-sync's six-input contract."""

    def test_readme_code_row_drops_retired_phrase(self):
        body = read(README)
        self.assertNotIn("updates affected docs and the architecture doc set", body)

    def test_readme_adr_path_names_docs_sync_as_committer(self):
        body = read(README)
        self.assertIsNotNone(
            re.search(r"adr_path.{0,120}`/acs:docs-sync`.{0,80}commits", body, re.DOTALL),
            "README.md's adr_path config row must name /acs:docs-sync as the committer")

    def test_internals_inductive_step_names_docs_sync(self):
        body = read(INTERNALS)
        bullet = body[body.index("**Inductive step**"):body.index("**Drift repair")]
        self.assertIn("docs-sync", bullet)
        self.assertNotIn("the code plan's documentation map names the HLD files", bullet)

    def test_internals_living_requirements_names_docs_sync(self):
        body = read(INTERNALS)
        self.assertIn("`/acs:docs-sync`'s executor\nmerges the merged ticket's acceptance criteria", body)

    def test_docs_sync_skill_framing_preserves_six(self):
        body = read(DOCS_SYNC_SKILL)
        self.assertNotIn("five", body)
        self.assertIsNotNone(
            re.search(r"all six,\s*independently", body),
            "docs-sync/SKILL.md must preserve the 'reads all six, "
            "independently' framing")

    def test_docs_sync_skill_intro_drops_step4_general_claim(self):
        body = read(DOCS_SYNC_SKILL)
        intro = body[:body.index("## Start")]
        self.assertNotIn(
            "already tries to keep docs in sync while it implements", intro,
            "docs-sync/SKILL.md intro must drop the retired present-tense "
            "claim that /code step 4 still authors general doc updates")
        self.assertIn("sole producer", intro)


if __name__ == "__main__":
    unittest.main()
