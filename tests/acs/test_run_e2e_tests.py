"""`/acs:run-e2e-tests`: the rename landed, the alias is gone, and it is a step.

The suite runner's own prose contracts live in
tests/acs/test_run_e2e_tests_run_mechanics.py, _closed_loop.py and
_ticket_scoped_mode.py. THIS module pins its POSITION:

  * the prose lives in skills/run-e2e-tests/SKILL.md, under that name, and
    carries no leftover `/acs:test` instruction — only the note that says it
    was renamed;
  * `skills/test/` is gone. It survived one release as a forwarding alias; §6
    retires it, because a second name for one skill is a second thing every
    registry, schema and doc has to keep level with the first;
  * it is a HOOKED STEP of `ship.yaml` with its own pre/post pair. The "not
    really a pipeline skill in its default mode, except under `--for-ticket`"
    framing is gone with the two modes it described: there is one mode (§3.11),
    and a standing invocation records its start and finish like every other;
  * the workflow names it in order, after `create-e2e-tests` writes the suites
    it runs, with no predicate: a run with nothing to run says so.

Run:  python3 -m unittest tests.acs.test_run_e2e_tests -v
"""

import os
import re
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN = os.path.join(REPO_ROOT, "src", "acs")
HOOKS = os.path.join(PLUGIN, "hooks", "scripts")
SKILL_PATH = os.path.join(PLUGIN, "skills", "run-e2e-tests", "SKILL.md")

sys.path.insert(0, HOOKS)

import acs_lib as lib  # noqa: E402


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def frontmatter(text, path):
    parts = text.split("---\n", 2)
    assert len(parts) >= 3 and parts[0] == "", "%s: missing frontmatter" % path
    return parts[1], parts[2]


class TestTheRenamedSkill(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.body = read(SKILL_PATH)
        cls.front, cls.prose = frontmatter(cls.body, SKILL_PATH)

    def test_the_prose_lives_under_the_new_name(self):
        self.assertRegex(self.front, r"(?m)^name: run-e2e-tests$")
        self.assertIn("/acs:run-e2e-tests", self.prose)

    def test_it_carries_the_frontmatter_shape_every_coordinator_carries(self):
        """It is a step now, so it is a coordinator like any other: it may not
        edit files by hand, and it takes a subject."""
        self.assertRegex(self.front, r"(?m)^disallowed-tools: Edit, NotebookEdit$")
        self.assertRegex(self.front, r"(?m)^argument-hint: ")

    def test_the_completion_block_is_headed_by_the_new_name(self):
        self.assertIn("## /acs:run-e2e-tests ·", self.prose)

    def test_the_old_name_survives_nowhere_as_an_instruction(self):
        """A retired alias in live prose is a command that fails at the worst
        possible moment -- when someone follows the documentation."""
        self.assertNotIn("/acs:test", self.prose)

    def test_it_points_at_the_skill_that_writes_the_suites(self):
        self.assertIn("/acs:create-e2e-tests", self.prose)

    def test_it_records_its_ledger_step_under_the_new_name(self):
        self.assertIn("--step run-e2e-tests", self.prose)


class TestTheAliasIsGone(unittest.TestCase):
    """§6: `test` (alias) -- ambiguous; `run-e2e-tests` is the skill."""

    def test_the_alias_directory_is_deleted(self):
        self.assertFalse(
            os.path.isdir(os.path.join(PLUGIN, "skills", "test")),
            "skills/test/ was a forwarding page kept for one release; a second "
            "name for one skill is a second thing every registry has to keep "
            "level with the first")

    def test_no_registry_still_lists_it(self):
        for name, names in (("HOOKED_SKILLS", lib.HOOKED_SKILLS),
                            ("UNHOOKED_SKILLS", lib.UNHOOKED_SKILLS),
                            ("the skill directories", lib.registered_skills())):
            with self.subTest(registry=name):
                self.assertNotIn("test", names)

    def test_no_workflow_step_names_it(self):
        wf = lib.validate_workflow_file(lib.default_workflow_path())
        self.assertNotIn("test", lib.steps_of(wf))


class TestItIsAHookedStep(unittest.TestCase):
    """The framing that went with the two modes it described."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(SKILL_PATH)
        cls.wf = lib.validate_workflow_file(lib.default_workflow_path())

    def test_it_is_registered_as_hooked(self):
        self.assertIn("run-e2e-tests", lib.HOOKED_SKILLS)
        self.assertNotIn("run-e2e-tests", lib.UNHOOKED_SKILLS)

    def test_it_owns_its_lifecycle_scripts(self):
        for prefix in ("pre", "post"):
            with self.subTest(hook=prefix):
                self.assertTrue(os.path.isfile(
                    os.path.join(HOOKS, "%s-run-e2e-tests.py" % prefix)))

    def test_it_starts_and_finishes_through_the_one_verb(self):
        self.assertIn('acs.py" step start --step run-e2e-tests', self.body)
        self.assertIn('post-run-e2e-tests.py" --result-file', self.body)

    def test_it_describes_one_mode_not_two(self):
        """`--for-ticket` named a second mode with its own rules. A standing
        invocation and a pipeline step are the same protocol (§3.11)."""
        self.assertNotIn("--for-ticket", self.body)
        self.assertNotIn("Ticket-scoped mode", self.body)

    def test_the_workflow_names_it_after_the_step_that_writes_the_suites(self):
        steps = lib.steps_of(self.wf)
        self.assertIn("run-e2e-tests", steps)
        self.assertLess(steps.index("create-e2e-tests"), steps.index("run-e2e-tests"))

    def test_the_step_carries_no_predicate(self):
        """`when: e2e_configured` is gone with every other predicate (§2.1). A
        run with no harness and nothing to run COMPLETES and says which."""
        raw = read(lib.default_workflow_path())
        body = "\n".join(line for line in raw.splitlines()
                         if not line.lstrip().startswith("#"))
        self.assertNotIn("when:", body)
        for outcome in ("passed", "no_harness", "nothing_to_run"):
            with self.subTest(outcome=outcome):
                self.assertIn(outcome, lib.outcome_vocabulary("run-e2e-tests"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
