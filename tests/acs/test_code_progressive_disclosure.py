"""/acs:code's conditional branches live in references/, and stay reachable.

SKILL.md is loaded in full every time the skill runs. /acs:code's was 918 lines
of which roughly a third described three branches most runs never enter -- the
non-epic COMPLEX breakdown recommendation, the in-loop escalation check, and
boundary-only de-escalation. Those moved to references/lane-changes.md, read on
demand.

The failure mode a split like this introduces is silent: a pointer that does not
resolve, or a rule the coordinator never learns it should go and read, costs
nothing at load time and everything at the moment the branch is taken. So what
is pinned here is not the line count -- that is a means -- but the two
properties that keep the split honest:

1. the reference EXISTS and is reachable by a path that resolves wherever the
   plugin is installed (``${CLAUDE_PLUGIN_ROOT}/...``, the same convention every
   other file reference in this skill uses -- a bare relative path has no
   defined base at runtime);
2. each pointer says WHEN to read it, because a reference nobody is told to
   open is a deleted section with extra steps.

Note what is deliberately NOT asserted: that SKILL.md is under any particular
length. The <500-line guidance suits skills Claude *consults*; /acs:code is a
coordinator protocol *executed* start to finish, so most of its body is hot
path by construction. Splitting further would trade context for the risk of a
missed contract, which is the more expensive mistake.

Stdlib-only. Run:  python3 -m unittest tests.acs.test_code_progressive_disclosure -v
"""

import os
import re
import unittest


REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN = os.path.join(REPO_ROOT, "src", "acs")
CODE_DIR = os.path.join(PLUGIN, "skills", "code")
CODE_SKILL = os.path.join(CODE_DIR, "SKILL.md")
LANE_CHANGES = os.path.join(CODE_DIR, "references", "lane-changes.md")

#: The one spelling that resolves wherever the plugin is installed.
POINTER = "${CLAUDE_PLUGIN_ROOT}/skills/code/references/lane-changes.md"


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def norm(path):
    return re.sub(r"\s+", " ", read(path))


class TheReferenceExistsAndIsReachableTest(unittest.TestCase):

    def test_the_reference_file_is_present(self):
        self.assertTrue(os.path.isfile(LANE_CHANGES),
                        "SKILL.md points at %s; it must exist" % LANE_CHANGES)

    def test_skill_md_points_at_it_with_a_resolvable_path(self):
        body = read(CODE_SKILL)
        self.assertIn(POINTER, body,
                      "the pointer must be plugin-root-relative: a bare "
                      "`references/...` has no defined base when the "
                      "coordinator resolves it at runtime")

    def test_no_bare_relative_pointer_survives(self):
        """The spelling this was first written with, which would not resolve."""
        self.assertNotIn("`references/lane-changes.md`", read(CODE_SKILL))

    def test_every_pointer_says_when_to_read_it(self):
        """A reference nobody is told to open is a deleted section."""
        body = norm(CODE_SKILL)
        self.assertIn("read it only when one applies", body)
        self.assertIn("Most runs hit none of them and never open that file",
                      body)


class TheMovedBranchesAreAllThereTest(unittest.TestCase):
    """Moved verbatim, so each section's own heading should be findable."""

    def test_all_three_conditional_sections_landed(self):
        body = read(LANE_CHANGES)
        for heading in ("### Non-epic COMPLEX breakdown recommendation",
                        "### In-loop escalation check",
                        "### Boundary-only user-confirmed de-escalation"):
            with self.subTest(section=heading):
                self.assertIn(heading, body)

    def test_they_are_gone_from_the_hot_path(self):
        body = read(CODE_SKILL)
        for heading in ("### In-loop escalation check",
                        "### Boundary-only user-confirmed de-escalation"):
            with self.subTest(section=heading):
                self.assertNotIn(heading, body,
                                 "%s should be in the reference, not inline" % heading)


class HotPathRulesStayedOnTheHotPathTest(unittest.TestCase):
    """The regression this split actually produced, and the guard against it.

    A block of general orchestration rules -- XML message validation, phase
    persistence, the no-nested-subagents rule, the executor and verifier agent
    names -- sat under the de-escalation heading WITHOUT a heading of its own.
    A by-heading slice swept it into the reference, taking rules that every run
    needs off the hot path. The pinning tests caught it; these keep it caught.
    """

    def test_the_orchestration_rules_are_in_skill_md(self):
        body = read(CODE_SKILL)
        for token in ("acs:code-executor", "acs:code-verifier",
                      "validate_xml.py",
                      "<partition>/phases/code/iter-<n>-<phase>.xml",
                      "subagents never spawn subagents"):
            with self.subTest(rule=token):
                self.assertIn(token, body,
                              "%r is needed by every run and belongs in "
                              "SKILL.md, not a conditional reference" % token)

    def test_the_reference_does_not_carry_them(self):
        body = read(LANE_CHANGES)
        for token in ("validate_xml.py",
                      "<partition>/phases/code/iter-<n>-<phase>.xml"):
            with self.subTest(rule=token):
                self.assertNotIn(token, body)


if __name__ == "__main__":
    unittest.main(verbosity=2)
