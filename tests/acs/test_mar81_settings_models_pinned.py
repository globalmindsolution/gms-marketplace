"""MAR-81 — Pin acs subagent models to explicit ids.

Asserts the repo-committed .acs/settings.json `models` block holds explicit,
version-stable model ids (claude-opus-4-8 / claude-sonnet-5) instead of the
generic runtime aliases ("opus" / "sonnet"), and that the file remains valid
against plugins/acs/schemas/settings.schema.json.

Run:  python3 -m unittest tests.acs.test_mar81_settings_models_pinned -v
"""

import json
import os
import unittest

from jsonschema import Draft202012Validator

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SETTINGS_PATH = os.path.join(REPO_ROOT, ".acs", "settings.json")
SCHEMA_PATH = os.path.join(REPO_ROOT, "plugins", "acs", "schemas", "settings.schema.json")


class SettingsModelsPinnedCase(unittest.TestCase):
    """Fixture: load the committed settings.json + schema once."""

    @classmethod
    def setUpClass(cls):
        with open(SETTINGS_PATH, encoding="utf-8") as f:
            cls.settings = json.load(f)
        with open(SCHEMA_PATH, encoding="utf-8") as f:
            cls.schema = json.load(f)

    def test_planner_pinned(self):
        self.assertEqual(self.settings["models"]["planner"], "claude-opus-4-8")

    def test_verifier_pinned(self):
        self.assertEqual(self.settings["models"]["verifier"], "claude-opus-4-8")

    def test_coordinator_pinned(self):
        self.assertEqual(self.settings["models"]["coordinator"], "claude-opus-4-8")

    def test_executor_pinned(self):
        self.assertEqual(self.settings["models"]["executor"], "claude-sonnet-5")

    def test_settings_schema_valid(self):
        validator = Draft202012Validator(self.schema)
        errors = sorted(validator.iter_errors(self.settings), key=str)
        self.assertEqual(errors, [], msg="\n".join(str(e) for e in errors))

    def test_no_alias_literals_remain(self):
        models = self.settings["models"]
        for role in ("planner", "executor", "verifier", "coordinator"):
            self.assertNotIn(
                models[role],
                ("opus", "sonnet"),
                msg=f"models.{role} still holds a generic alias literal: {models[role]!r}",
            )


if __name__ == "__main__":
    unittest.main()
