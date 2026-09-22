"""MAR-114 — settings.suites schema fragment + e2e deprecation (AC-1, AC-2).

Structure-contract unit test over `plugins/acs/schemas/settings.schema.json`.
AC-1: a new top-level `suites` property, generalizing `e2e`, with the reserved
name "e2e" auto-populated at load. AC-2: the `e2e` property's description is
updated to mark it a DEPRECATED compatibility alias for `suites.e2e`, while its
`required`/`properties`/`additionalProperties` shape stays byte-identical to
the pre-change shape.

Stdlib-only (json, os, unittest).

Run:  python3 -m unittest tests.acs.test_mar114_suites_schema -v
"""

import json
import os
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN = os.path.join(REPO_ROOT, "plugins", "acs")
SCHEMA_PATH = os.path.join(PLUGIN, "schemas", "settings.schema.json")

# Captured pre-change e2e shape (required/properties/additionalProperties),
# per spec AC-2: "diff the shape sub-dict, not the description, against a
# fixture of the pre-change block".
PRE_CHANGE_E2E_SHAPE = {
    "type": "object",
    "required": ["command"],
    "properties": {
        "command": {"type": "string", "minLength": 1, "description": "Command that runs the e2e suite, e.g. 'npm run test:e2e'."},
        "setup": {"type": "string", "minLength": 1, "description": "Optional environment bring-up, e.g. 'docker compose up -d --wait'."},
        "teardown": {"type": "string", "minLength": 1, "description": "Optional environment teardown; always run after the suite, pass or fail."},
        "per_iteration": {"type": "boolean", "default": False, "description": "true = verifier runs e2e every iteration; false = only on the final, otherwise-passing iteration."},
    },
    "additionalProperties": True,
}


def load_schema():
    with open(SCHEMA_PATH, encoding="utf-8") as fh:
        return json.load(fh)


class Mar114SuitesSchemaCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = load_schema()
        cls.properties = cls.schema["properties"]

    # -- AC-1: suites property --------------------------------------------

    def test_suites_property_exists_and_is_object_type(self):
        self.assertIn("suites", self.properties, "settings.schema.json must gain a top-level `suites` property (AC-1)")
        self.assertEqual(self.properties["suites"]["type"], "object")

    def test_suites_default_is_empty_object(self):
        self.assertEqual(self.properties["suites"]["default"], {})

    def test_suites_additional_properties_require_command(self):
        entry_schema = self.properties["suites"]["additionalProperties"]
        self.assertEqual(entry_schema.get("required"), ["command"])
        self.assertEqual(entry_schema["properties"]["command"]["type"], "string")
        self.assertEqual(entry_schema["properties"]["command"]["minLength"], 1)

    def test_suites_entry_optional_fields_documented(self):
        entry_schema = self.properties["suites"]["additionalProperties"]
        props = entry_schema["properties"]
        self.assertEqual(props["setup"]["type"], "string")
        self.assertEqual(props["setup"]["minLength"], 1)
        self.assertEqual(props["teardown"]["type"], "string")
        self.assertEqual(props["teardown"]["minLength"], 1)
        self.assertEqual(props["per_iteration"]["type"], "boolean")
        self.assertEqual(props["per_iteration"]["default"], False)

    def test_suites_entry_additional_properties_true(self):
        entry_schema = self.properties["suites"]["additionalProperties"]
        self.assertTrue(entry_schema.get("additionalProperties"), "each suite entry must tolerate forward-compat extra keys, mirroring e2e")

    def test_suites_description_states_single_source_of_truth(self):
        desc = self.properties["suites"]["description"].lower()
        self.assertTrue(
            "single source of truth" in desc,
            "suites description must state it is the single source of truth generalizing e2e (AC-1)",
        )

    def test_suites_description_states_reserved_e2e_auto_population(self):
        desc = self.properties["suites"]["description"]
        self.assertIn(
            "e2e", desc,
            "suites description must reference the reserved name e2e (AC-1)",
        )
        desc_lower = desc.lower()
        self.assertTrue(
            "auto" in desc_lower or "automatically" in desc_lower,
            "suites description must state e2e is auto-populated at load (AC-1)",
        )

    # -- AC-2: e2e deprecation description, shape preserved ---------------

    def test_e2e_description_marks_deprecated_alias(self):
        desc = self.properties["e2e"]["description"]
        self.assertTrue(
            "DEPRECATED" in desc or "deprecated" in desc,
            "e2e description must mark it DEPRECATED (AC-2)",
        )
        self.assertIn(
            "suites.e2e", desc,
            "e2e description must reference suites.e2e as the canonical replacement (AC-2)",
        )

    def test_e2e_shape_is_byte_identical_to_pre_change(self):
        e2e = self.properties["e2e"]
        shape = {
            "type": e2e["type"],
            "required": e2e["required"],
            "properties": e2e["properties"],
            "additionalProperties": e2e["additionalProperties"],
        }
        self.assertEqual(
            shape, PRE_CHANGE_E2E_SHAPE,
            "e2e's required/properties/additionalProperties shape must stay byte-identical; only the description may change (AC-2)",
        )


if __name__ == "__main__":
    unittest.main()
