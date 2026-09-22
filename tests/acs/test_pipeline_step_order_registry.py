"""Guard for acs_lib.PIPELINE_STEP_ORDER, the metrics funnel's column order.

Originating ticket: MAR-6, where the constant mirrored
pipeline-state.schema.json's `steps.propertyNames.enum` and the sole
obligation was that the two never drift.

v0.5.0 opened `steps`: run.schema.json validates SHAPE, step names validate
against the resolved workflow, and skill names against the skill directories
(§4.3), so a new workflow is a YAML file and a new skill is a directory --
neither touches a schema. There is no enum left to mirror.

What binds the list instead is what it is FOR: it orders the funnel's
columns, so every name in it must be a real skill and every hooked skill must
appear, or a column silently goes missing. A step it does not name still
renders, sorted after the ones it does -- which is why the check below is a
superset rather than an equality.
"""

import json
import os
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN = os.path.join(REPO_ROOT, "plugins", "acs")
SCRIPTS = os.path.join(PLUGIN, "hooks", "scripts")
sys.path.insert(0, SCRIPTS)

import acs_lib as lib  # noqa: E402

RUN_SCHEMA_PATH = os.path.join(PLUGIN, "schemas", "run.schema.json")


class TestPipelineStepOrderRegistry(unittest.TestCase):

    def test_every_name_is_a_real_skill_directory(self):
        for name in lib.PIPELINE_STEP_ORDER:
            with self.subTest(step=name):
                self.assertTrue(
                    os.path.isfile(os.path.join(PLUGIN, "skills", name, "SKILL.md")),
                    "%s is not a skill directory" % name)

    def test_every_hooked_skill_has_a_column(self):
        missing = [s for s in lib.HOOKED_SKILLS if s not in lib.PIPELINE_STEP_ORDER]
        self.assertEqual(missing, [],
                         "these hooked skills would have no funnel column")

    def test_the_names_are_unique(self):
        self.assertEqual(len(lib.PIPELINE_STEP_ORDER),
                         len(set(lib.PIPELINE_STEP_ORDER)))

    def test_the_run_schema_keeps_steps_open(self):
        """The reason there is nothing to mirror: a closed enum here would put
        a new skill's name in a schema, which is exactly what §4.3 removed."""
        with open(RUN_SCHEMA_PATH, encoding="utf-8") as fh:
            schema = json.load(fh)
        steps = schema["properties"]["steps"]
        self.assertNotIn("propertyNames", steps)
        self.assertNotIn("enum", json.dumps(steps))


if __name__ == "__main__":
    unittest.main()
