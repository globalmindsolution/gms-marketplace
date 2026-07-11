"""Shape/security assertions for the e2e CI workflow template /acs:init Step 7f
ships into consumer repos (plugins/acs/templates/ci/acs-e2e.yml).

acs-e2e.yml is cloned from acs-tests.yml (NOT acs-conventions.yml): safe
trigger events only, minimal permissions, cancel-in-progress enabled (unlike
the conventions gate — see design.md:129-141), no secrets interpolated, and a
pinned job name (`E2E suite`) that /acs:init's Step 7f wires into branch
protection as the required-check context. Plain-text/YAML-shape assertions,
mirroring test_acs_conventions_concurrency.py's style.

Run:  python3 -m unittest discover -s tests -v
"""

import json
import os
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
WORKFLOW = os.path.join(REPO_ROOT, "plugins", "acs", "templates", "ci", "acs-e2e.yml")
SCHEMA_PATH = os.path.join(REPO_ROOT, "plugins", "acs", "schemas", "settings.schema.json")


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


class TestAcsE2eWorkflowShape(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.content = _read(WORKFLOW)

    def test_trigger_is_pull_request_only_safe_events(self):
        """[AC-6] safe events only; never pull_request_target (fork-PR secret boundary)."""
        self.assertIn("pull_request:", self.content)
        self.assertIn("types: [opened, reopened, synchronize]", self.content)
        self.assertNotIn("pull_request_target", self.content)

    def test_permissions_contents_read(self):
        """[AC-6] minimal-permissions posture."""
        self.assertIn("permissions:", self.content)
        self.assertIn("contents: read", self.content)

    def test_concurrency_cancel_in_progress_true(self):
        """tests-gate shape (not the conventions gate's false), design.md:129-141."""
        self.assertIn("cancel-in-progress: true", self.content)

    def test_job_name_is_e2e_suite(self):
        """The pinned required-check context string."""
        self.assertIn("name: E2E suite", self.content)

    def test_no_secrets_interpolated(self):
        """[AC-6] no secrets in the template."""
        self.assertNotIn("secrets.", self.content)

    def test_uses_checkout_v4_and_setup_python_v5(self):
        """Clone fidelity: acs-tests.yml's pins, not acs-conventions.yml's."""
        self.assertIn("actions/checkout@v4", self.content)
        self.assertIn("actions/setup-python@v5", self.content)


class TestNoNewSettingsKey(unittest.TestCase):
    def test_no_new_settings_key_introduced(self):
        """[C-4] spec 01 introduces no e2e.ci / suites.e2e.ci-shaped enable flag."""
        with open(SCHEMA_PATH, encoding="utf-8") as fh:
            schema = json.load(fh)
        e2e_props = schema["properties"]["e2e"]["properties"]
        self.assertNotIn("ci", e2e_props)
        suites_entry = schema["properties"]["suites"]["additionalProperties"]
        self.assertNotIn("ci", suites_entry["properties"])


if __name__ == "__main__":
    unittest.main()
