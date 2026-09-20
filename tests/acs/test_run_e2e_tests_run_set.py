"""Prose contracts for how `/acs:run-e2e-tests` narrows what it runs.

`--for-ticket` named a SECOND MODE with its own run-set resolution, its own
completion-report variant, and a rule about which later steps it skipped. There
is one mode now (§3.11): a standing invocation and a `ship.yaml` step resolve
the same way, which is what makes the two the same skill rather than two skills
sharing a file.

What survived the collapse is the part that was always doing the work — the
run set is narrowed by the run's own subject, and it falls back honestly when
the run has nothing to narrow by. Those are pinned here.

Stdlib-only (re, unittest); mirrors the read()/section() helper pattern used
elsewhere for prompt-driven-skill prose contracts.
"""

import os
import re
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN = os.path.join(REPO_ROOT, "src", "acs")
TEST_SKILL = os.path.join(PLUGIN, "skills", "run-e2e-tests", "SKILL.md")
SKILLS_REQ = os.path.join(REPO_ROOT, "docs", "requirements", "functional", "skills.md")

_CONDITIONAL_ESCAPE_HATCH = re.compile(r"(?i)\bunless\b|\bexcept when\b|\bif not\b")


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def norm(text):
    """Collapse whitespace runs so a phrase-spanning check cannot fail solely
    because markdown word-wrap put a line break between two words."""
    return re.sub(r"[ \t]*\n[ \t]*", " ", text)


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
    """Step 1 parses the ONE flag this skill takes."""

    def _step1(self):
        return section(read(TEST_SKILL), "## Step 1")

    def test_the_suite_flag_is_documented(self):
        self.assertIn("--suite", self._step1())

    def test_the_retired_mode_flag_is_gone(self):
        """A flag that named a mode which no longer exists is a command that
        fails at the worst moment -- when someone follows the documentation."""
        self.assertNotIn("--for-ticket", self._step1())


class RunSetTest(unittest.TestCase):
    """The narrowing rule: what this run runs, and why that is not everything."""

    def _subsection(self):
        return norm(section(read(TEST_SKILL), "## Which suites this run runs"))

    def test_the_subsection_exists(self):
        self._subsection()

    def test_it_says_there_is_no_second_mode(self):
        sub = self._subsection()
        self.assertRegex(sub, r"(?i)no second mode")
        self.assertRegex(sub, r"(?i)resolve the same way")

    def test_suite_scoping_reads_the_runs_case_document(self):
        """`/acs:create-test-docs` assigns each case to a suite, so the run's
        own cases are what scopes it -- not a list someone maintains here."""
        sub = self._subsection()
        self.assertIn("test-cases.md", sub)
        self.assertIn("/acs:create-test-docs", sub)
        self.assertRegex(sub, r"(?i)`Suite` column")

    def test_the_plan_is_the_documented_fallback(self):
        sub = self._subsection()
        self.assertIn("steps/create-impl-plan/plan.md", sub)

    def test_a_run_with_nothing_to_narrow_by_runs_everything_and_says_so(self):
        """A run started from a prompt against a repo has no cases and no
        plan. Running every configured suite is the honest answer there, and
        the prose has to SAY it is a fallback rather than leave a reader to
        infer that the narrowing silently failed."""
        sub = self._subsection()
        self.assertRegex(sub, r"(?i)nothing has said which suites")
        self.assertRegex(sub, r"(?i)the run cannot narrow")

    def test_the_selection_is_re_resolved_never_cached(self):
        sub = self._subsection()
        self.assertRegex(sub, r"(?i)never cached")

    def test_a_suite_must_also_be_configured(self):
        sub = self._subsection()
        self.assertRegex(sub, r'(?i)only when it is also a key in')


class NothingToRunTest(unittest.TestCase):
    """The empty case is a COMPLETION with a reason, not a failure: the absence
    of a suite is not evidence that anything is broken."""

    def _subsection(self):
        return section(read(TEST_SKILL), "## Which suites this run runs")

    def test_the_outcome_is_named(self):
        self.assertIn("nothing_to_run", self._subsection())

    def test_it_is_stated_as_a_completion_not_a_failure(self):
        self.assertRegex(norm(self._subsection()), r"(?i)not a failure")

    def test_the_statement_has_no_conditional_escape_hatch(self):
        paragraphs = re.split(r"\n\s*\n", self._subsection())
        for p in paragraphs:
            if "nothing_to_run" not in p:
                continue
            self.assertIsNone(
                _CONDITIONAL_ESCAPE_HATCH.search(p),
                "the nothing-to-run rule must not carry a conditional escape "
                "hatch ('unless'/'except when'/'if not'): %r" % p)


class SelfDescriptionTest(unittest.TestCase):
    """What the skill says it IS, now that it is a step like any other."""

    def _head(self):
        body = read(TEST_SKILL)
        return norm(body[:body.index("## Start")])

    def test_it_no_longer_calls_itself_unhooked(self):
        head = self._head()
        self.assertNotIn("not a hooked", head)
        self.assertNotIn("no pre/post hooks", head)

    def test_it_says_it_is_both_a_step_and_a_standing_command(self):
        head = self._head()
        self.assertRegex(head, r"(?i)step of \*\*`ship\.yaml`\*\*|step of `ship\.yaml`")
        self.assertRegex(head, r"(?i)standing command")

    def test_it_is_honest_that_it_writes(self):
        """Unlike /acs:metrics and /acs:usage, it mutates state -- and the
        prose says so up front rather than leaving a reader to discover it."""
        head = self._head()
        self.assertRegex(head, r"(?i)not read-only")


if __name__ == "__main__":
    unittest.main(verbosity=2)
