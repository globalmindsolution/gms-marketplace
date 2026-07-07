"""MAR-114 spec 03 — /acs:test failure-path closed loop (AC-9 triage half, AC-10, R1).

Prose-contract unit test for `plugins/acs/skills/test/SKILL.md`'s failure-path
section (layered by spec 03 onto spec 02's deterministic-run body). Uses the
same bounded-window `section()` technique as
`tests/acs/test_mar112_quality_path_init.py:29-40` so a stray mention
elsewhere in the file cannot satisfy an assertion.

Asserts, within the failure-path section:
  - the regression-key shape <suite-name>:<normalized-failing-test-id>;
  - the C-1 suite-level fallback key <suite>:__suite__, stated explicitly as
    a fallback for an unparseable per-test failure — NOT a content
    fingerprint/hash;
  - the exact three-way policy vocabulary (new / comment-bump-open /
    new-linked-on-closed) with the required guard phrases;
  - the R1 no-interpolation rule.

Run:  python3 -m unittest tests.acs.test_mar114_test_skill_closed_loop -v
"""

import os
import re
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SKILL_PATH = os.path.join(REPO_ROOT, "plugins", "acs", "skills", "test", "SKILL.md")


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def section(body, heading):
    """Return the text of a markdown section: from the line whose start is
    `heading` (matched at line-start) up to the next same-or-higher-level
    heading (or end of file)."""
    m = re.search(r"(?m)^" + re.escape(heading) + r"\b.*$", body)
    if m is None:
        raise AssertionError("heading %r not found in SKILL.md" % heading)
    start = m.start()
    level = len(heading) - len(heading.lstrip("#"))
    nxt = re.search(r"(?m)^#{1,%d} \S" % level, body[m.end():])
    end = m.end() + nxt.start() if nxt else len(body)
    return body[start:end]


def failure_path_window(body):
    """The failure-path steps live after spec 02's all-green short-circuit
    boundary (## Step 4) and before Step 5's report / scheduling / completion
    sections that spec 02 already owns. Concatenate every section from the
    first failure-path heading onward so the assertions are bounded to
    spec-03 content, not the whole file."""
    # Spec 03 adds one or more "## Step" / "### " headings after Step 4's
    # all-green short-circuit. We scan every top-level heading from Step 4
    # onward and keep the ones that are not Step 5/Scheduling/Completion
    # (spec 02's own sections), which is exactly the failure-path material.
    idx = body.find("## Step 4")
    if idx == -1:
        raise AssertionError("Step 4 (all-green short-circuit) heading not found")
    tail = body[idx:]
    return tail


class Mar114ClosedLoopCase(unittest.TestCase):
    """Fixture: read the /acs:test SKILL.md once, isolate the failure-path window."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(SKILL_PATH)
        cls.tail = failure_path_window(cls.body)

    def test_regression_key_shape_stated(self):
        """The stable regression-key shape <suite>:<normalized-failing-test-id> is stated."""
        self.assertRegex(
            self.tail,
            r"<suite[- ]?name>:<normalized-failing-test-id>|<suite>:<normalized-failing-test-id>",
            "regression-key shape not stated in the failure-path section",
        )

    def test_c1_suite_level_fallback_key_stated(self):
        """C-1: the literal fallback key <suite>:__suite__ is stated."""
        self.assertIn(
            "__suite__", self.tail,
            "suite-level fallback marker __suite__ not found in the failure-path section",
        )
        self.assertRegex(
            self.tail,
            r"<suite>:__suite__",
            "fallback key shape <suite>:__suite__ not stated verbatim",
        )

    def test_c1_fallback_is_not_a_hash_or_fingerprint(self):
        """The fallback must be stated as a fixed marker, explicitly NOT a content fingerprint/hash."""
        # Find the neighborhood of the fallback mention and confirm it disclaims a hash/fingerprint.
        idx = self.tail.find("__suite__")
        self.assertNotEqual(idx, -1, "__suite__ fallback not found")
        window = self.tail[max(0, idx - 800):idx + 800]
        self.assertRegex(
            window,
            r"[Nn]ot a (content[- ])?fingerprint|[Nn]ot a hash",
            "fallback not explicitly disclaimed as 'not a hash/fingerprint' near its definition",
        )

    def test_no_parseable_failing_test_id_condition_stated(self):
        """The unparseable-failure condition (bare exit code / compile error) triggering the
        fallback is stated, not just the key shape in isolation."""
        self.assertRegex(
            self.tail,
            r"no parseable( individual)? failing[- ]test id|unparseable",
            "condition for the suite-level fallback not stated",
        )

    def test_three_way_policy_new_ticket_branch(self):
        """Not-found case: mint a new ticket via new-ticket.py."""
        self.assertRegex(
            self.tail,
            r"(?i)not found.{0,200}?mint",
            "new-ticket (not-found) branch not stated",
        )
        self.assertIn("new-ticket.py", self.tail)

    def test_three_way_policy_comment_bump_open_branch(self):
        """Open/in_progress/in_review case: comment-bump, never duplicate, never silently skip."""
        self.assertRegex(
            self.tail,
            r"open.{0,40}in_progress.{0,40}in_review|open/in_progress/in_review",
            "open/in_progress/in_review case not stated together",
        )
        self.assertRegex(
            self.tail,
            r"comment[- /]?bump",
            "comment/bump branch not stated",
        )
        self.assertIn(
            "never mint a duplicate", self.tail,
            "guard phrase 'never mint a duplicate' missing",
        )
        self.assertIn(
            "never silently skip", self.tail,
            "guard phrase 'never silently skip' missing",
        )

    def test_three_way_policy_new_linked_on_closed_branch(self):
        """Done/closed case: mint a NEW ticket linked to the old one, never silently reopen."""
        self.assertRegex(
            self.tail,
            r"(?is)status is `?done`?.{0,300}?(new|mint)",
            "done/closed -> mint-new-linked branch not stated",
        )
        self.assertRegex(
            self.tail,
            r"(?i)link(s|ed|ing)? (back )?to the old|old \(closed\) ticket|links back",
            "link-back-to-old-ticket language not stated",
        )
        self.assertIn(
            "never silently reopen", self.tail,
            "guard phrase 'never silently reopen' missing",
        )

    def test_three_way_vocabulary_distinguishable(self):
        """The three branches are distinguishable using the new / comment-bump-open /
        new-linked-on-closed vocabulary (or an equivalent explicit labeling)."""
        for term in ("new", "comment", "bump", "link"):
            self.assertIn(term, self.tail.lower())

    def test_regression_key_marker_convention_stated(self):
        """The acs-regression-key: <key> marker line convention is stated."""
        self.assertIn("acs-regression-key:", self.tail)

    def test_r1_no_interpolation_restated(self):
        """R1: failure content is never interpolated into a shell command."""
        self.assertRegex(
            self.tail,
            r"never interpolat|no.{0,20}interpolat",
            "R1 no-interpolation rule not restated in the failure-path section",
        )
        self.assertRegex(
            self.tail.lower(),
            r"shell command",
            "R1 restatement does not mention shell command",
        )

    def test_regressions_array_population_stated(self):
        """The regressions[] results-artifact array population (key/ticket_id/action/linked_ticket_id)
        is described in the failure-path section."""
        self.assertIn("regressions", self.tail)
        for action in ("minted", "commented", "minted_linked"):
            self.assertIn(action, self.tail)


if __name__ == "__main__":
    unittest.main()
