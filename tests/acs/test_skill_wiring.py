"""Registration wiring: what it takes for a skill to be reachable and gated.

Replaces tests/acs/test_build_test_skill_registry.py, most of whose subject is
gone by design — the `GATES` table, the `UNHOOKED_SKILLS` split, the closed
steps enum, the `skipped` status and the `test` alias.

What is left is the wiring that still has to hold, and one new obligation:
`review-code` and `run-e2e-tests` are STEPS now, so each needs its own gate
where before they had none.

Run:  python3 -m unittest tests.acs.test_skill_wiring -v
"""

import json
import os
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRIPTS = os.path.join(REPO_ROOT, "plugins", "acs", "hooks", "scripts")
sys.path.insert(0, SCRIPTS)

import acs_lib as lib  # noqa: E402
from acs_lib import skills as K  # noqa: E402
from acs_lib import workflow as W  # noqa: E402

PLUGIN = os.path.join(REPO_ROOT, "plugins", "acs")
SHIP = os.path.join(PLUGIN, "workflows", "ship.yaml")


class HookWrapperTest(unittest.TestCase):
    """A hooked skill owns a thin pre-/post- pair. They are two lines each, and
    their absence is silent: dispatch just does not gate the skill."""

    def test_every_hooked_skill_has_both_wrappers(self):
        for skill in lib.HOOKED_SKILLS:
            for side in ("pre", "post"):
                path = os.path.join(SCRIPTS, "%s-%s.py" % (side, skill))
                with self.subTest(skill=skill, side=side):
                    self.assertTrue(os.path.isfile(path), "missing %s" % path)

    def test_every_wrapper_names_a_skill_that_ships(self):
        known = set(K.registered_skills())
        for name in sorted(os.listdir(SCRIPTS)):
            if not (name.startswith(("pre-", "post-")) and name.endswith(".py")):
                continue
            skill = name.split("-", 1)[1][:-3]
            with self.subTest(wrapper=name):
                self.assertIn(skill, known)

    def test_the_two_new_steps_are_hooked(self):
        """review-code and run-e2e-tests are steps now; a step with no gate is
        a step nothing checks the inputs of."""
        for skill in ("review-code", "run-e2e-tests"):
            self.assertIn(skill, lib.HOOKED_SKILLS, skill)

    def test_the_removed_surface_has_no_wrappers_left(self):
        for skill in ("analyze-ticket", "test", "create-spec"):
            for side in ("pre", "post"):
                path = os.path.join(SCRIPTS, "%s-%s.py" % (side, skill))
                with self.subTest(skill=skill, side=side):
                    self.assertFalse(os.path.exists(path), path)


class WorkflowCoverageTest(unittest.TestCase):

    def setUp(self):
        self.wf = W.validate_workflow_file(SHIP)

    def test_every_step_of_ship_is_hooked(self):
        """A step /acs:ship runs but nothing gates would take its inputs on
        trust."""
        for step in W.steps_of(self.wf):
            self.assertIn(step, lib.HOOKED_SKILLS, step)

    def test_every_step_has_a_directory_and_a_manifest(self):
        manifests = K.load_manifests()
        for step in W.steps_of(self.wf):
            with self.subTest(step=step):
                self.assertTrue(K.is_skill(step))
                self.assertTrue(manifests.get(step), "%s declares nothing" % step)

    def test_the_legs_are_reachable_but_are_not_steps(self):
        manifests = K.load_manifests()
        for leg in K.legs_of("code", manifests):
            with self.subTest(leg=leg):
                self.assertTrue(K.is_skill(leg))
                self.assertNotIn(leg, W.steps_of(self.wf))


class SettingsEnumTest(unittest.TestCase):
    """The schema enum and HOOKED_SKILLS are two copies of one list. The schema
    half is hand-maintained, so nothing but this notices when a skill is hooked
    and only one copy is updated."""

    def setUp(self):
        with open(os.path.join(PLUGIN, "schemas", "settings.schema.json"),
                  encoding="utf-8") as handle:
            self.schema = json.load(handle)

    def test_the_model_override_enum_tracks_hooked_skills(self):
        enum = self.schema["properties"]["models"]["properties"]["overrides"][
            "propertyNames"]["enum"]
        self.assertEqual(sorted(enum), sorted(lib.HOOKED_SKILLS))


class RemovedVocabularyTest(unittest.TestCase):
    """The words this redesign retired. Each was load-bearing once, and a
    reader who finds one still in use will reasonably assume it still means
    something."""

    def test_skipped_is_not_a_step_status(self):
        """It recorded a workflow predicate's answer. There are no predicates,
        and a step with nothing to do completes with an evidenced outcome."""
        self.assertNotIn("skipped", lib.STEP_STATUSES)

    def test_handed_off_is_not_a_step_status(self):
        """It named a REASON, not a state: `interrupted` + stop_reason."""
        self.assertNotIn("handed_off", lib.STEP_STATUSES)
        self.assertNotIn("handed_off", lib.RUN_STATUSES)

    def test_the_run_schema_carries_no_skill_enum(self):
        with open(os.path.join(PLUGIN, "schemas", "run.schema.json"),
                  encoding="utf-8") as handle:
            schema = json.load(handle)
        self.assertNotIn("propertyNames", schema["properties"]["steps"])

    def test_the_step_state_schema_carries_no_skill_enum(self):
        with open(os.path.join(PLUGIN, "schemas", "step-state.schema.json"),
                  encoding="utf-8") as handle:
            schema = json.load(handle)
        self.assertNotIn("enum", schema["properties"]["skill"])


if __name__ == "__main__":
    unittest.main()
