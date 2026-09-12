"""Prose-contract tests for /acs:run-e2e-tests' ticket-scoped (--for-ticket) mode.

Stdlib-only (re, unittest); mirrors the read()/section() helper pattern used
elsewhere for prompt-driven-skill prose contracts.
"""

import os
import re
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN = os.path.join(REPO_ROOT, "plugins", "acs")
TEST_SKILL = os.path.join(PLUGIN, "skills", "run-e2e-tests", "SKILL.md")
SKILLS_REQ = os.path.join(REPO_ROOT, "docs", "requirements", "functional", "skills.md")

_CONDITIONAL_ESCAPE_HATCH = re.compile(r"(?i)\bunless\b|\bexcept when\b|\bif not\b")


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def section(body, heading):
    """Return the text of a markdown section: from the line whose start is
    `heading` up to the next same-or-higher-level heading (or end of file)."""
    m = re.search(r"(?m)^" + re.escape(heading) + r".*$", body)
    if m is None:
        raise AssertionError("heading %r not found" % heading)
    start = m.start()
    level = len(heading) - len(heading.lstrip("#"))
    nxt = re.search(r"(?m)^#{1,%d} \S" % level, body[m.end():])
    end = m.end() + nxt.start() if nxt else len(body)
    return body[start:end]


class Step1FlagParsingTest(unittest.TestCase):
    """AC-1: Step 1 documents --for-ticket <id> parsing."""

    def _step1(self):
        return section(read(TEST_SKILL), "## Step 1")

    def test_for_ticket_flag_documented(self):
        self.assertIn("--for-ticket", self._step1())

    def test_id_validation_pattern_documented(self):
        self.assertIn("[A-Z][A-Z0-9]*-[0-9]+", self._step1())

    def test_combinable_with_suite_flag(self):
        self.assertIsNotNone(
            re.search(r"(?i)combin", self._step1()),
            "Step 1 must state --for-ticket combines with --suite")

    def test_fail_fast_on_unresolvable_id(self):
        self.assertIsNotNone(
            re.search(r"(?i)fail fast", self._step1()),
            "Step 1 must state an unresolvable --for-ticket id fails fast")


class TicketScopedSubsectionTest(unittest.TestCase):
    """AC-1/AC-2: the ticket-scoped subsection exists, reuses Steps 2-3, and
    states the suite-scoping selection rule (F-3)."""

    def _subsection(self):
        return section(read(TEST_SKILL), "## Ticket-scoped mode")

    def test_subsection_exists(self):
        self._subsection()  # raises AssertionError if the heading is absent

    def test_steps_2_3_reuse_stated_not_redescribed(self):
        sub = self._subsection()
        self.assertIsNotNone(
            re.search(r"(?i)steps? 2.{0,5}3", sub),
            "must reference Steps 2-3 by number")
        self.assertIsNotNone(
            re.search(r"(?i)reused|unmodified|exactly as", sub),
            "must state Steps 2-3 are reused, not redescribed")

    def test_subsection_textually_distinct_from_4a_4b(self):
        body = read(TEST_SKILL)
        sub_start = body.index("## Ticket-scoped mode")
        sub_end = sub_start + len(self._subsection())
        step4a_start = body.index("## Step 4a")
        step4b_start = body.index("## Step 4b")
        self.assertLessEqual(
            sub_end, step4a_start,
            "the ticket-scoped subsection must end before Step 4a starts, "
            "not be nested inside it")
        self.assertLess(step4a_start, step4b_start)

    def test_verdict_object_in_fenced_code_block(self):
        sub = self._subsection()
        m = re.search(r"```json\n(.*?)```", sub, re.S)
        self.assertIsNotNone(m, "verdict object must be documented in a fenced code block")
        self.assertIn('"status"', m.group(1))
        self.assertIn('"failure_output"', m.group(1))

    def test_suite_scoping_reads_the_ticket_case_document(self):
        # The skills-independence refactor made test-cases.md
        # (/acs:create-test-docs' artifact) the source of a ticket's suites;
        # the folded Test-plan section of the plan is the fallback for a
        # ticket planned before that skill existed, and plan.md still resolves
        # the legacy partition path for those.
        sub = self._subsection()
        self.assertIn("test-cases.md", sub)
        self.assertIsNotNone(
            re.search(r"(?i)fallback", sub),
            "the plan's Test-plan section must be named as the FALLBACK, not "
            "the primary source")
        self.assertIn("Test-plan", sub)
        self.assertIn("phases/code/plan.md", sub)

    def test_suite_scoping_selection_rule_language(self):
        sub = self._subsection()
        self.assertIsNotNone(
            re.search(r"(?i)re-evaluated fresh", sub),
            "suite-scoping rule must state the selection is re-evaluated "
            "fresh on every --for-ticket invocation")
        # MAR-73 retired the MAR-70 read-both resume fallback: plan.md is
        # the only name ever read here now -- no legacy iter-*-plan.md
        # literal should survive in this subsection.
        self.assertNotIn("iter-*-plan.md", sub)
        self.assertNotIn("iter-<n>-plan.md", sub)


class LedgerWriteTest(unittest.TestCase):
    """The ticket-scoped run records its outcome under the step id ship.yaml
    declares (run-e2e-tests), not under the pre-rename `test` step, and the
    record is read by `acs.py workflow next` -- no gate blocks on it now that
    order lives in ship.yaml."""

    def _subsection(self):
        return section(read(TEST_SKILL), "## Ticket-scoped mode")

    def test_records_under_the_run_e2e_tests_step(self):
        sub = self._subsection()
        self.assertIn("steps.run-e2e-tests", sub)
        self.assertIsNotNone(
            re.search(r"--skill run-e2e-tests", sub),
            "the pipeline-step.py calls must record --skill run-e2e-tests")
        self.assertNotIn("--skill test ", sub)

    def test_names_workflow_next_as_the_reader(self):
        self.assertIn("workflow next", self._subsection())

    def test_does_not_claim_a_docs_sync_gate_blocks_on_it(self):
        # gate_docs_sync no longer reads this step at all; prose promising a
        # gate that no longer exists would send users chasing a refusal they
        # can never see.
        sub = self._subsection()
        m = re.search(r"(?i)docs-sync", sub)
        if m is not None:
            window = sub[max(0, m.start() - 200):m.start() + 200]
            self.assertIsNotNone(
                re.search(r"(?i)no longer|not in a gate|no gate", window),
                "any docs-sync mention must say the gate is gone, not that it "
                "blocks on this step")


class UnconditionalSkipTest(unittest.TestCase):
    """AC-2 / R2 (must-fix): the 4a/4b skip is unconditional prose, with no
    escape-hatch qualifier anywhere near the skip statement."""

    def _subsection(self):
        return section(read(TEST_SKILL), "## Ticket-scoped mode")

    def test_skip_paragraph_present(self):
        sub = self._subsection()
        paragraphs = re.split(r"\n\s*\n", sub)
        skip_paragraphs = [
            p for p in paragraphs
            if "4a" in p and "4b" in p and re.search(r"(?i)skip|never", p)
        ]
        self.assertTrue(skip_paragraphs, "no paragraph describing the 4a/4b skip found")

    def test_skip_paragraph_has_no_conditional_escape_hatch(self):
        sub = self._subsection()
        paragraphs = re.split(r"\n\s*\n", sub)
        skip_paragraphs = [
            p for p in paragraphs
            if "4a" in p and "4b" in p and re.search(r"(?i)skip|never", p)
        ]
        for p in skip_paragraphs:
            self.assertIsNone(
                _CONDITIONAL_ESCAPE_HATCH.search(p),
                "skip paragraph must not contain a conditional escape hatch "
                "('unless'/'except when'/'if not'): %r" % p)


class SelfDescriptionAmendmentTest(unittest.TestCase):
    """AC-6: the self-description no longer unconditionally claims 'not a
    hooked pipeline skill'; a default/standing qualifier is added; the
    'no pre/post hooks' negative-space characterization is retained."""

    def _intro(self):
        body = read(TEST_SKILL)
        intro = body[:body.index("## Step 1")]
        return re.sub(r"\s+", " ", intro)

    def test_qualifies_default_standing_mode(self):
        intro = self._intro()
        m = re.search(r"(?i)NOT a hooked pipeline skill", intro)
        self.assertIsNotNone(m, "self-description must still describe the standing mode as unhooked")
        window = intro[max(0, m.start() - 200):m.start()]
        self.assertIsNotNone(
            re.search(r"(?i)default|standing", window),
            "a qualifying default/standing-mode phrase must precede the "
            "'NOT a hooked pipeline skill' claim in the same paragraph")

    def test_for_ticket_mode_named(self):
        self.assertIn("--for-ticket", self._intro())

    def test_no_pre_post_hooks_characterization_retained(self):
        self.assertIsNotNone(re.search(r"(?i)no pre/post hooks", self._intro()))


class SkillsRequirementsDocImpactTest(unittest.TestCase):
    """Doc-map: the suite runner's section in
    docs/requirements/functional/skills.md mentions the ticket-scoped mode.

    The heading may name the skill either way while the `test` alias directory
    survives its one release -- the assertion is about the mode being
    documented, not about which of the two names the doc has been moved to."""

    def test_suite_runner_section_mentions_for_ticket_mode(self):
        body = read(SKILLS_REQ)
        m = (re.search(r"(?m)^## .*/acs:run-e2e-tests.*$", body)
             or re.search(r"(?m)^## .*/acs:test\b.*$", body))
        self.assertIsNotNone(
            m, "skills.md must have a section for the suite runner "
               "('## /acs:run-e2e-tests', or '## /acs:test' while the alias lasts)")
        window = section(body, m.group(0))
        self.assertIsNotNone(
            re.search(r"--for-ticket|ticket-scoped", window, re.I),
            "the suite-runner section must mention --for-ticket or "
            "ticket-scoped mode")


if __name__ == "__main__":
    unittest.main()
