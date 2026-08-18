"""MAR-67 (Task 1) -- forge-tier target config: schema key + non-production
guards (AC-2, AC-6 config side).

Covers `evals.forge_repo` / `ACS_FORGE_REPO` resolution and the pre-clone
guards (G-a unconfigured, G-b naming convention, G-c never-self) plus the
post-clone marker-file guard (G-d), exercised standalone since ForgeSandbox
itself is Task 2. Stdlib-only; no network, no `claude` process.

Run:  python3 -m unittest tests.acs.test_forge_target_config -v
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCHEMA_PATH = os.path.join(REPO_ROOT, "plugins", "acs", "schemas", "settings.schema.json")
HARNESS_PATH = os.path.join(REPO_ROOT, "evals", "acs", "harness.py")

sys.path.insert(0, os.path.join(REPO_ROOT, "evals", "acs"))
import harness  # noqa: E402  (path-inserted, same resolution run_evals.py uses)

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
    "description": "Unit/integration test suite for the CI tests+coverage gate scaffolded by /acs:initialize (.github/workflows/acs-tests.yml + .acs/ci/run-tests.py, opt-in). The command MUST run the suite and FAIL on coverage shortfall — delegate to the tool (e.g. 'pytest --cov --cov-fail-under=$ACS_COVERAGE', or a jest coverageThreshold); acs exports ACS_COVERAGE (= test_coverage_percent) into the env. Read from the committed project settings.json; the CI runner has no acs install.",
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


def make_git_repo(tmp, remote_url=None):
    """A throwaway git checkout, optionally with a fake `origin` remote."""
    subprocess.run(["git", "init", "-q", tmp], check=True, capture_output=True)
    if remote_url:
        subprocess.run(["git", "-C", tmp, "remote", "add", "origin", remote_url],
                        check=True, capture_output=True)
    return tmp


def write_settings(repo_root, forge_repo, local=False):
    rel = ".acs/settings.local.json" if local else ".acs/settings.json"
    path = os.path.join(repo_root, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({"evals": {"forge_repo": forge_repo}}, fh)


class SchemaShapeTest(unittest.TestCase):
    """AC-2, AC-6: the `evals.forge_repo` schema key."""

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


class ResolveForgeTargetTest(unittest.TestCase):
    """AC-2: ACS_FORGE_REPO / evals.forge_repo resolution + guards G-a..G-c."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="acs-forge-config-test-")
        self.addCleanup(subprocess.run, ["rm", "-rf", self.tmp])

    def test_env_var_overrides_settings_forge_repo(self):
        write_settings(self.tmp, "someorg/acs-eval-settings")
        target = harness.resolve_forge_target(
            env={"ACS_FORGE_REPO": "someorg/acs-eval-env"}, repo_root=self.tmp)
        self.assertEqual(target, "someorg/acs-eval-env")

    def test_settings_local_overrides_project_settings_for_evals(self):
        write_settings(self.tmp, "someorg/acs-eval-project")
        write_settings(self.tmp, "someorg/acs-eval-local", local=True)
        target = harness.resolve_forge_target(env={}, repo_root=self.tmp)
        self.assertEqual(target, "someorg/acs-eval-local")

    def test_unconfigured_target_raises_forge_config_error(self):
        with self.assertRaises(harness.ForgeConfigError) as ctx:
            harness.resolve_forge_target(env={}, repo_root=self.tmp)
        message = str(ctx.exception)
        self.assertIn("ACS_FORGE_REPO", message)
        self.assertIn("evals.forge_repo", message)

    def test_malformed_target_value_rejected(self):
        for bad in ("no-slash-here", "", "   ", "/leading-slash"):
            with self.subTest(bad=bad):
                with self.assertRaises(harness.ForgeConfigError):
                    harness.resolve_forge_target(
                        env={"ACS_FORGE_REPO": bad}, repo_root=self.tmp)

    def test_non_eval_repo_name_rejected_by_naming_guard(self):
        for target in ("globalmindsolution/gms-marketplace", "acme/payments"):
            with self.subTest(target=target):
                with self.assertRaises(harness.ForgeConfigError):
                    harness.resolve_forge_target(
                        env={"ACS_FORGE_REPO": target}, repo_root=self.tmp)

    def test_target_equal_to_this_repo_rejected(self):
        make_git_repo(self.tmp, remote_url="https://github.com/someorg/acs-eval-self.git")
        with self.assertRaises(harness.ForgeConfigError):
            harness.resolve_forge_target(
                env={"ACS_FORGE_REPO": "someorg/acs-eval-self"}, repo_root=self.tmp)


class ForgeMarkerGuardTest(unittest.TestCase):
    """AC-2, AC-6: G-d, the post-clone marker-file guard, tested standalone."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="acs-forge-marker-test-")
        self.addCleanup(subprocess.run, ["rm", "-rf", self.tmp])

    def test_missing_marker_file_rejected_after_clone(self):
        with self.assertRaises(harness.ForgeConfigError):
            harness.check_forge_marker(self.tmp)

    def test_marker_file_present_passes_guard(self):
        with open(os.path.join(self.tmp, harness.FORGE_MARKER), "w") as fh:
            fh.write("never-production; safe to force-reset\n")
        harness.check_forge_marker(self.tmp)  # must not raise


class NoRepoCreationCallTest(unittest.TestCase):
    """AC-6: pins the C-3 deferral -- no repo-creation call anywhere in the source."""

    def test_harness_source_contains_no_repo_creation_call(self):
        with open(HARNESS_PATH, encoding="utf-8") as fh:
            source = fh.read()
        for banned in ("repo create", "POST /orgs/", "/user/repos"):
            self.assertNotIn(banned, source,
                              "harness.py must never call the repo-creation API (C-3)")


if __name__ == "__main__":
    unittest.main()
