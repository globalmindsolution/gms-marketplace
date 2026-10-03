"""The shipped settings schema's `evals.forge_repo` key.

This key is plugin SURFACE: it ships in plugins/acs/schemas/settings.schema.json,
so a consumer's settings may carry it. Its only reader was the behavioural
harness's forge tier, which was retired with the rest of the bespoke eval
harness when the suite moved to `claude plugin eval` -- so today nothing reads
it.

It is kept anyway, deliberately, and this test guards it. Removing a key from a
schema is a change to what a consumer's settings may contain, which belongs in
its own change with its own CHANGELOG entry -- not as a side effect of
rebuilding an eval folder. Until that change is made on purpose, the key's shape
and its never-production warning must not drift.

Split out of test_forge_target_config.py, whose remaining classes tested the
harness's forge-target resolution and were retired with it.

Run:  python3 -m unittest tests.acs.test_settings_schema_evals_key -v
"""

import json
import os
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCHEMA_PATH = os.path.join(REPO_ROOT, "plugins", "acs", "schemas", "settings.schema.json")


# Captured pre-existing sibling block (`tests`), shape only (the description is
# prose and may be reworded), so a real diff -- not a tautological
# self-comparison -- is caught if the evals addition touches it.
_SIBLING_FIXTURE = {
    "tests": {
        "type": "object",
        "properties": {
            "coverage": {"type": "number", "exclusiveMinimum": 0, "maximum": 100, "default": 90},
        },
        "additionalProperties": {
            "type": "object",
            "required": ["command"],
            "properties": {
                "command": {"type": "string", "minLength": 1},
                "setup": {"type": "string", "minLength": 1},
                "teardown": {"type": "string", "minLength": 1},
            },
            "additionalProperties": True,
        },
    },
}


def _shape(node):
    """The schema node with every `description` removed, recursively."""
    if isinstance(node, dict):
        return {k: _shape(v) for k, v in node.items() if k != "description"}
    return node


def load_schema():
    with open(SCHEMA_PATH, encoding="utf-8") as fh:
        return json.load(fh)


class SchemaShapeTest(unittest.TestCase):
    """AC-2, AC-6: the `evals.forge_repo` schema key, still shipped."""

    @classmethod
    def setUpClass(cls):
        cls.schema = load_schema()
        cls.properties = cls.schema["properties"]

    def test_schema_declares_evals_forge_repo_property(self):
        self.assertIn("evals", self.properties,
                       "settings.schema.json must gain a top-level `evals` property")
        evals = self.properties["evals"]
        self.assertEqual(evals["type"], "object")
        forge_repo = evals["properties"]["forge_repo"]
        self.assertEqual(forge_repo["type"], "string")
        self.assertEqual(forge_repo["pattern"], r"^[A-Za-z0-9._-]+/[A-Za-z0-9._-]+$")

    def test_schema_description_states_never_production(self):
        evals = self.properties["evals"]
        self.assertIn("NEVER-PRODUCTION", evals["description"])
        forge_repo_desc = evals["properties"]["forge_repo"]["description"]
        self.assertIn("MUST NOT be a production repo", forge_repo_desc)

    def test_existing_schema_properties_unchanged(self):
        for key, fixture in _SIBLING_FIXTURE.items():
            self.assertEqual(
                _shape(self.properties[key]), fixture,
                "settings.schema.json's %r block must be untouched by the evals addition" % key,
            )


if __name__ == "__main__":
    unittest.main()
