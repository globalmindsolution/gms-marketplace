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


# Captured pre-existing sibling blocks (e2e/suites/tests), re-serialized from
# the schema before this change so a real diff -- not a tautological
# self-comparison -- is caught if this change touches them.
_SIBLING_FIXTURE = json.loads(r"""
{
  "e2e": {
    "description": "End-to-end test layer (unset = repo has no e2e suite). When configured: /code's folded Test plan content must state e2e impact, /code authors/updates e2e tests in the same changeset, and the code-verifier runs the suite (green required for a passing verdict; per_iteration=false runs it only on the final, otherwise-passing iteration since e2e is slow). /create-project scaffolds the harness for greenfield repos with a user-facing surface. DEPRECATED compatibility alias for suites.e2e — kept for backward compatibility; new configs should set suites.e2e directly. When present, normalized into suites[\"e2e\"] at settings-load time (see acs_lib.load_settings).",
    "type": "object",
    "required": [
      "command"
    ],
    "properties": {
      "command": {
        "type": "string",
        "minLength": 1,
        "description": "Command that runs the e2e suite, e.g. 'npm run test:e2e'."
      },
      "setup": {
        "type": "string",
        "minLength": 1,
        "description": "Optional environment bring-up, e.g. 'docker compose up -d --wait'."
      },
      "teardown": {
        "type": "string",
        "minLength": 1,
        "description": "Optional environment teardown; always run after the suite, pass or fail."
      },
      "per_iteration": {
        "type": "boolean",
        "default": false,
        "description": "true = verifier runs e2e every iteration; false = only on the final, otherwise-passing iteration."
      }
    },
    "additionalProperties": true
  },
  "suites": {
    "description": "Named test suites /acs:test runs (single source of truth for configured test commands; generalizes settings.e2e). Each entry shares the e2e sub-schema shape. The reserved name \"e2e\" is auto-populated automatically from a configured settings.e2e at load time (see e2e above) — do not hand-author suites.e2e directly if e2e is also set; the two are the same normalized entry.",
    "type": "object",
    "additionalProperties": {
      "type": "object",
      "required": [
        "command"
      ],
      "properties": {
        "command": {
          "type": "string",
          "minLength": 1,
          "description": "Command that runs the suite, e.g. 'npm run lint'."
        },
        "setup": {
          "type": "string",
          "minLength": 1,
          "description": "Optional environment bring-up, e.g. 'docker compose up -d --wait'."
        },
        "teardown": {
          "type": "string",
          "minLength": 1,
          "description": "Optional environment teardown; always run after the suite, pass or fail."
        },
        "per_iteration": {
          "type": "boolean",
          "default": false,
          "description": "true = the verifier/scheduler runs this suite every iteration; false = only on demand."
        }
      },
      "additionalProperties": true
    },
    "default": {}
  },
  "tests": {
    "description": "Unit/integration test suite for the CI tests+coverage gate scaffolded by /acs:setup (.github/workflows/acs-tests.yml + .acs/ci/run-tests.py, opt-in). The command MUST run the suite and FAIL on coverage shortfall — delegate to the tool (e.g. 'pytest --cov --cov-fail-under=$ACS_COVERAGE', or a jest coverageThreshold); acs exports ACS_COVERAGE (= test_coverage_percent) into the env. Read from the committed project settings.json; the CI runner has no acs install.",
    "type": "object",
    "required": [
      "command"
    ],
    "properties": {
      "command": {
        "type": "string",
        "minLength": 1,
        "description": "Runs the suite and enforces coverage, e.g. 'pytest --cov --cov-fail-under=$ACS_COVERAGE'."
      },
      "setup": {
        "type": "string",
        "minLength": 1,
        "description": "Optional environment bring-up before the command, e.g. 'pip install -e .[test]' or 'npm ci'."
      }
    },
    "additionalProperties": true
  }
}
""")


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
                self.properties[key], fixture,
                "settings.schema.json's %r block must be untouched by the evals addition" % key,
            )


if __name__ == "__main__":
    unittest.main()
