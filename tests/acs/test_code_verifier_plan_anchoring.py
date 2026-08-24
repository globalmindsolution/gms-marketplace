"""Verifier plan-conformance + approval-audit dimensions; ADR-0073 amending
ADR-0004; plan-revocation escape hatch (MAR-74, slice 4 of epic MAR-69).

Prose-contract tests over `plugins/acs/agents/code-verifier.md` (new
dimensions 15 "Plan conformance" and 16 "Approval-audit"),
`plugins/acs/skills/code/SKILL.md` (the mirrored dimension bullets plus the
new `### Plan revocation` subsection), and the `docs/adr/0073-*.md` +
`docs/adr/README.md` deliverables.

Stdlib-only (os, re, unittest). Every prose assertion is by file plus
whitespace-normalized substring/regex, never by line number -- the house
style of tests/acs/test_plan_approval.py and
tests/acs/test_code_loop_topology.py.

Run:
  python3 -m unittest tests.acs.test_code_verifier_plan_anchoring -v
"""

import os
import re
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN = os.path.join(REPO_ROOT, "plugins", "acs")
CODE_VERIFIER = os.path.join(PLUGIN, "agents", "code-verifier.md")


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def norm(text):
    return re.sub(r"\s+", " ", text)


def dimension_window(body, number, label, radius=900):
    """The whitespace-normalized prose window for one `code-verifier.md`
    numbered dimension item, from its own `N. **Label**` line up to (not
    including) the next top-level numbered item or the `**Retired
    dimensions.**` paragraph -- normalized so a phrase wrapped across
    source lines still matches as one substring."""
    m = re.search(r"(?m)^%d\.\s+\*\*%s\*\*" % (number, re.escape(label)), body)
    if m is None:
        raise AssertionError(
            "dimension %d **%s** not found" % (number, label))
    nxt = re.search(r"(?m)^(?:\d+\.\s+\*\*|\*\*Retired dimensions\.\*\*)",
                     body[m.end():])
    end = m.end() + nxt.start() if nxt else min(len(body), m.end() + radius)
    return norm(body[m.start():end])


def code_verifier_body():
    return read(CODE_VERIFIER)


class Dimension15PlanConformanceTest(unittest.TestCase):
    """AC-1: the plan-conformance dimension judges only against an APPROVED
    plan.md; unapproved stubs are never a conformance contract."""

    def test_dimension_15_plan_conformance_exists(self):
        body = code_verifier_body()
        self.assertRegex(
            body, r"(?m)^15\.\s+\*\*Plan conformance\*\*",
            "code-verifier.md must have a '15. **Plan conformance**' "
            "dimension item")

    def test_dimension_15_requires_an_eligible_approval_record(self):
        window = dimension_window(code_verifier_body(), 15, "Plan conformance")
        self.assertIn("plan-approval.json", window)
        self.assertRegex(window, r"(?i)`?eligible`?\s+(?:is\s+)?`?true`?")

    def test_dimension_15_requires_the_record_to_describe_plan_md(self):
        window = dimension_window(code_verifier_body(), 15, "Plan conformance")
        self.assertIn("plan_path", window)
        self.assertIn("phases/code/plan.md", window)

    def test_dimension_15_requires_digest_match(self):
        window = dimension_window(code_verifier_body(), 15, "Plan conformance")
        self.assertRegex(window, r"(?i)sha256")
        self.assertIn("plan_sha256", window)

    def test_dimension_15_is_na_not_blocking_without_a_record(self):
        window = dimension_window(code_verifier_body(), 15, "Plan conformance")
        self.assertRegex(window, r"(?i)\bN/A\b")
        self.assertRegex(window, r"(?i)never\s+a\s+block")
        self.assertRegex(window, r"(?i)never\s+a\s+silent\s+skip")

    def test_verifier_reads_the_record_itself(self):
        body = code_verifier_body()
        inputs_section = body[body.index("## Input contract"):body.index("## Charter")]
        self.assertIn("plan-approval.json", inputs_section)
        window = dimension_window(body, 15, "Plan conformance")
        self.assertRegex(
            window, r"(?i)itself.{0,120}never.{0,40}coordinator-relayed|"
                     r"never.{0,40}coordinator-relayed.{0,120}itself",
            "dimension 15 must forbid trusting a coordinator-relayed "
            "plan_approved value and require the verifier compute it itself")


class Dimension1SubordinationTest(unittest.TestCase):
    """AC-2: the AC-conformance dimension (1) stays verified unchanged, and
    dimension 15 is explicitly subordinate to it."""

    LOAD_BEARING_PHRASES = [
        "FRESH, EVERY iteration",
        "MUST NOT accept the current iteration's plan artifact's "
        "restatement",
        "MUST NOT reuse a value cached from an earlier iteration",
        "Rebuild the AC-to-implementation matrix from scratch",
    ]

    def test_dimension_1_charter_text_unchanged(self):
        window = dimension_window(
            code_verifier_body(), 1, "Acceptance-criteria conformance")
        for phrase in self.LOAD_BEARING_PHRASES:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, window)

    def test_dimension_15_is_explicitly_subordinate_to_dimension_1(self):
        window = dimension_window(code_verifier_body(), 15, "Plan conformance")
        self.assertRegex(
            window, r"(?i)never\s+substitutes?\s+for\s+dimension\s+1")
        self.assertRegex(
            window,
            r"(?i)conforms?.{0,60}approved plan.{0,120}still\s+fails?"
            r"\s+dimension\s+1")
        self.assertRegex(
            window, r"(?i)approved plan.{0,40}never.{0,20}evidence")

    def test_existing_dimension_labels_1_through_14_unchanged(self):
        """Regression guard: appending 15/16 must not renumber or relabel
        any of dimensions 1-14 (extends
        test_code_verifier_multi_lens.NewDimensionTest.EXISTING_LABELS,
        which stops at 13, through dimension 14)."""
        labels_1_14 = [
            "Acceptance-criteria conformance",
            "Tests",
            "Coverage",
            "Business logic",
            "Features",
            "Quality",
            "Technical standards",
            "Architecture",
            "System design",
            "Security",
            "Documentation",
            "Simplicity & scope",
            "Audience-style",
            "Regression-risk",
        ]
        body = code_verifier_body()
        for n, label in enumerate(labels_1_14, start=1):
            with self.subTest(n=n, label=label):
                self.assertRegex(
                    body, r"(?m)^%d\.\s+\*\*%s\b" % (n, re.escape(label)),
                    "dimension %d must still read '**%s**' unchanged" % (
                        n, label))


class Dimension16ApprovalAuditTest(unittest.TestCase):
    """AC-3: the approval-audit dimension blocks on unaccounted-for
    high-stakes paths."""

    def test_dimension_16_approval_audit_exists(self):
        body = code_verifier_body()
        self.assertRegex(
            body, r"(?m)^16\.\s+\*\*Approval-audit\*\*",
            "code-verifier.md must have a '16. **Approval-audit**' "
            "dimension item")

    def test_dimension_16_reruns_recommend_stakes_over_changed_files(self):
        window = dimension_window(code_verifier_body(), 16, "Approval-audit")
        self.assertIn("recommend_stakes", window)
        self.assertIn("git diff --name-only", window)

    def test_dimension_16_blocks_when_unaccounted_for(self):
        window = dimension_window(code_verifier_body(), 16, "Approval-audit")
        self.assertIn('severity="blocking"', window)
        self.assertIn('dimension="approval-audit"', window)

    def test_dimension_16_accounted_for_escape_paths(self):
        window = dimension_window(code_verifier_body(), 16, "Approval-audit")
        self.assertRegex(window, r'stakes.{0,10}[:=].{0,10}"?high"?')
        self.assertIn("escalations", window)
        self.assertRegex(window, r'direction.{0,10}[:=].{0,10}"?up"?')


if __name__ == "__main__":
    unittest.main()
