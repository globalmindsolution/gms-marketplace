"""The `test` -> `run-e2e-tests` rename, and the alias directory left behind.

The suite runner's own prose contracts live in
tests/acs/test_run_e2e_tests_run_mechanics.py, _closed_loop.py and
_ticket_scoped_mode.py (all three retargeted from `skills/test/` by this
refactor). THIS module pins the RENAME itself:

  * the prose now lives in skills/run-e2e-tests/SKILL.md, under that name, and
    carries no leftover `/acs:test` instruction — only the note that says it was
    renamed;
  * skills/test/ survives for one release as an ALIAS: a short forwarding page
    with none of the run mechanics duplicated into it, so there is exactly one
    copy of the contract to maintain;
  * the registry agrees — phases.yaml carries `aliases: {test: run-e2e-tests}`,
    both directories are unhooked, and the ledger keeps the pre-rename `test`
    step name so an old pipeline-state still validates and still resolves;
  * ship.yaml drives `run-e2e-tests` (never `test`), with the args, predicate
    and failure relay the skill's prose promises.

Run:  python3 -m unittest tests.acs.test_run_e2e_tests -v
"""

import os
import re
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN = os.path.join(REPO_ROOT, "plugins", "acs")
HOOKS = os.path.join(PLUGIN, "hooks", "scripts")
SKILL_PATH = os.path.join(PLUGIN, "skills", "run-e2e-tests", "SKILL.md")
ALIAS_PATH = os.path.join(PLUGIN, "skills", "test", "SKILL.md")

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
        cls.text = read(SKILL_PATH)
        cls.fm, cls.body = frontmatter(cls.text, SKILL_PATH)

    def test_the_prose_lives_under_the_new_name(self):
        self.assertRegex(self.fm, r"(?m)^name: run-e2e-tests$")
        self.assertRegex(self.fm, r"(?m)^description: \S")

    def test_it_keeps_the_unhooked_utility_frontmatter_shape(self):
        """Like skills/metrics and skills/usage: no argument-hint, no
        disallowed-tools, and model-invocable."""
        self.assertNotIn("argument-hint", self.fm)
        self.assertNotIn("disallowed-tools", self.fm)
        self.assertNotIn("disable-model-invocation", self.fm)

    def test_the_completion_block_is_headed_by_the_new_name(self):
        self.assertIn("## /acs:run-e2e-tests · <status>", self.body)

    def test_the_only_mention_of_the_old_name_is_the_rename_note(self):
        """A leftover `/acs:test` instruction would tell the user to invoke the
        alias the next release deletes."""
        note = re.search(r"(?s)This skill was `/acs:test` until.*?RUNS the "
                         r"configured suites\.", self.body)
        self.assertIsNotNone(note, "the rename note must be present")
        rest = self.body.replace(note.group(0), "")
        self.assertNotIn("/acs:test`", rest)
        self.assertNotIn("/acs:test ", rest)

    def test_it_points_at_the_skill_that_writes_the_suites(self):
        self.assertIn("/acs:create-e2e-tests", self.body)
        self.assertRegex(self.body, r"WRITES a ticket's e2e suites; this skill\s+RUNS")

    def test_it_records_its_ledger_step_under_the_new_name(self):
        self.assertIn("--skill run-e2e-tests", self.body)
        self.assertNotIn("--skill test ", self.body)


class TestTheAliasDirectory(unittest.TestCase):
    """skills/test/ forwards; it does not fork the contract."""

    @classmethod
    def setUpClass(cls):
        cls.text = read(ALIAS_PATH)
        cls.fm, cls.body = frontmatter(cls.text, ALIAS_PATH)

    def test_it_still_declares_its_directory_name(self):
        self.assertRegex(self.fm, r"(?m)^name: test$")

    def test_the_description_routes_to_the_new_skill(self):
        self.assertIn("/acs:run-e2e-tests", self.fm)
        self.assertRegex(self.fm, r"(?i)deprecated|alias")

    def test_it_is_short_and_forwards(self):
        self.assertLess(len(self.text.splitlines()), 40,
                        "the alias must stay a forwarding page, not a second copy")
        self.assertRegex(self.body, r"(?i)invoke `/acs:run-e2e-tests`")
        self.assertRegex(self.body, r"(?i)passing every argument you were given")

    def test_it_duplicates_none_of_the_run_mechanics(self):
        for leaked in ("## Step 1", "results.json", "acs-regression-key",
                       "new-ticket.py", "--only-if-present", "test-runs/"):
            with self.subTest(leaked=leaked):
                self.assertNotIn(leaked, self.body)

    def test_it_carries_the_house_completion_report_heading(self):
        """Every skill declares one (tests/acs/test_skill_contracts.py); this
        one declares that the report is the forwarded skill's, unaltered."""
        self.assertIn("## Completion report (normative)", self.body)
        self.assertRegex(self.body, r"(?i)renders no report of its own")

    def test_it_says_the_alias_is_temporary(self):
        self.assertRegex(self.body, r"(?i)one release")


class TestRegistryAgreement(unittest.TestCase):
    """The prose's claims about the registry are the registry's facts."""

    def test_phases_yaml_records_the_alias(self):
        self.assertEqual(lib.skill_aliases(), {"test": "run-e2e-tests"})

    def test_the_alias_resolves_to_the_test_phase(self):
        self.assertEqual(lib.phase_of("run-e2e-tests"), "test")
        self.assertEqual(lib.phase_of("test"), "test")

    def test_both_directories_are_unhooked(self):
        for name in ("run-e2e-tests", "test"):
            with self.subTest(name=name):
                self.assertIn(name, lib.UNHOOKED_SKILLS)
                self.assertNotIn(name, lib.HOOKED_SKILLS)
                self.assertNotIn(name, lib.GATES)

    def test_neither_has_a_lifecycle_wrapper(self):
        for name in ("run-e2e-tests", "test"):
            for phase in ("pre", "post"):
                with self.subTest(name=name, phase=phase):
                    self.assertFalse(os.path.exists(
                        os.path.join(HOOKS, "%s-%s.py" % (phase, name))))

    def test_the_ledger_keeps_the_pre_rename_step_name(self):
        """A pipeline-state.json written before the rename must still validate,
        and `workflow next` still resolves steps.test to this step."""
        self.assertIn("run-e2e-tests", lib.PIPELINE_STEP_ORDER)
        self.assertIn("test", lib.PIPELINE_STEP_ORDER)


class TestShipWorkflowDrivesTheNewName(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        doc, _lines = lib.load_workflow(lib.default_workflow_path())
        cls.doc = doc
        cls.step = [s for s in doc["steps"] if s["id"] == "run-e2e-tests"][0]

    def test_no_step_names_the_alias(self):
        self.assertNotIn("test", [s["skill"] for s in self.doc["steps"]])

    def test_the_step_passes_the_ticket_scoped_flag(self):
        self.assertEqual(self.step["args"], "--for-ticket {ticket_id}")
        self.assertIn("--for-ticket", read(SKILL_PATH))

    def test_the_step_is_conditional_and_relays_a_failure_to_code(self):
        self.assertEqual(self.step["when"], "post_code_test_active")
        self.assertEqual(self.step["on_fail"]["relay_to"], "code")
        self.assertIn("post_code_test_active", lib.PREDICATES)

    def test_the_skill_names_the_relay_it_feeds(self):
        body = read(SKILL_PATH)
        self.assertIn("on_fail", body)
        self.assertIn("relay_to: code", body)

    def test_the_suites_it_runs_are_written_by_the_step_before_it(self):
        self.assertEqual(self.step["needs"], ["create-e2e-tests"])


if __name__ == "__main__":
    unittest.main()
