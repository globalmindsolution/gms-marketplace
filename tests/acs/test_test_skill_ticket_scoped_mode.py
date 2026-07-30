"""Prose-contract tests for /acs:test's ticket-scoped (--for-ticket) mode.

Stdlib-only (re, unittest); mirrors the read()/section() helper pattern used
elsewhere for prompt-driven-skill prose contracts.
"""

import os
import re
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN = os.path.join(REPO_ROOT, "plugins", "acs")
TEST_SKILL = os.path.join(PLUGIN, "skills", "test", "SKILL.md")
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

    def test_suite_scoping_selection_rule_language(self):
        sub = self._subsection()
        self.assertIsNotNone(
            re.search(r"(?i)most recent|highest", sub),
            "suite-scoping rule must state 'most recent'/'highest'")
        self.assertIn("iter-<n>-plan.md", sub)
        self.assertIn("`n`", sub)


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
    """Doc-map: docs/requirements/functional/skills.md's /acs:test section
    mentions the new mode."""

    def test_acs_test_section_mentions_for_ticket_mode(self):
        body = read(SKILLS_REQ)
        m = re.search(r"(?m)^## .*/acs:test.*$", body)
        self.assertIsNotNone(m, "skills.md must have a '## /acs:test' section")
        window = section(body, m.group(0))
        self.assertIsNotNone(
            re.search(r"--for-ticket|ticket-scoped", window, re.I),
            "the /acs:test section must mention --for-ticket or ticket-scoped mode")


if __name__ == "__main__":
    unittest.main()
