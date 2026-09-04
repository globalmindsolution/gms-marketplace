"""MAR-125 (E2E-1) — /acs:setup Step 7f: e2e required merge gate wiring.

Prose-contract unit test for `plugins/acs/skills/setup/SKILL.md`'s new opt-in
Step 7f, which:
  1. is gated ENTIRELY on settings.e2e/suites.e2e being configured (opt-in
     invariant — the offer-gating half; the runner's own no-command guard is
     spec 01's half);
  2. on offer + accept, copies acs-e2e.yml + run-e2e.py into the consumer
     repo, mirroring Step 7d's install pattern;
  3. reuses Step 7c's admin-detect block rather than re-deriving it;
  4. on admin=true AND explicit consent, extends the SAME
     required_status_checks.contexts array 7c/7d already manage with the
     literal "E2E suite" — never a second, competing PUT;
  5. otherwise prints the exact gh api command once and never hard-fails
     (the report-once safeguard);
  6. records the outcome in Step 8's summary table and the completion report.

Stdlib-only (os, re, unittest, json), mirroring
tests/acs/test_setup_offers.py's `section()` helper + bounded-window
co-occurrence style — never a bare file-wide assertIn.

Renamed under MAR-1 (the skill formerly invoked as acs:initialize is now
acs:setup): module name and internal skill-path/token references updated;
behavior and originating ticket reference unchanged.

Run:  python3 -m unittest tests.acs.test_mar125_init_e2e_gate -v
"""

import json
import os
import re
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN = os.path.join(REPO_ROOT, "plugins", "acs")
SKILL_PATH = os.path.join(PLUGIN, "skills", "setup", "SKILL.md")
SCHEMA_PATH = os.path.join(PLUGIN, "schemas", "settings.schema.json")


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def section(body, heading):
    """Return the text of a markdown section: from the line whose start is
    `heading` (a real heading, matched at line-start) up to the next
    same-or-higher-level heading (or end of file). Mirrors
    test_setup_offers.py's helper exactly."""
    m = re.search(r"(?m)^" + re.escape(heading) + r"\b.*$", body)
    if m is None:
        raise AssertionError("heading %r not found in SKILL.md" % heading)
    start = m.start()
    level = len(heading) - len(heading.lstrip("#"))
    nxt = re.search(r"(?m)^#{1,%d} \S" % level, body[m.end():])
    end = m.end() + nxt.start() if nxt else len(body)
    return body[start:end]


class Mar125InitE2eGateCase(unittest.TestCase):
    """MAR-125's acceptance criteria, re-pointed at the implementation.

    These pinned the e2e merge gate as `## Step 7f` prose — the template copies,
    the admin-detect reuse, the shared contexts array. MAR-526 turned setup into
    a conversational skill: the copies are `setup_wizard.py`'s job, and the
    branch-protection rules are one step covering every gate rather than a
    per-gate repetition. Every AC below is the original one; only where it is
    read changed."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(SKILL_PATH)
        cls.protection = section(cls.body, "## Step 4")
        cls.summary = section(cls.body, "## Step 6")
        cls.wizard = read(os.path.join(PLUGIN, "hooks", "scripts", "setup_wizard.py"))

    def test_the_e2e_gate_is_offered_and_guarded_on_e2e_being_configured(self):
        """AC-1: unset e2e is a no-op — the offer is not made at all."""
        self.assertIsNotNone(
            re.search(r"(?s)e2e (required )?merge gate.{0,200}(configured|unset)",
                      self.body, re.IGNORECASE)
            or re.search(r"(?s)(configured|unset).{0,200}e2e", self.body, re.IGNORECASE),
            "setup must state the e2e gate offer is gated on e2e/suites.e2e "
            "being configured (AC-1)")

    def test_both_templates_are_installed_by_the_wizard(self):
        """The artifact-installation contract, now in code: the runner and the
        workflow are copied verbatim, and refreshed on every re-run."""
        import sys
        sys.path.insert(0, os.path.join(PLUGIN, "hooks", "scripts"))
        import setup_wizard
        files, workflow, context = setup_wizard.CI_INSTALLS["e2e"]
        self.assertEqual(files, ("run-e2e.py",))
        self.assertEqual(workflow, "acs-e2e.yml")
        self.assertEqual(context, "E2E suite")
        for name in ("run-e2e.py", "acs-e2e.yml"):
            self.assertTrue(os.path.exists(
                os.path.join(PLUGIN, "templates", "ci", name)), name)

    def test_the_e2e_runner_is_installed_executable(self):
        """It is invoked directly by the workflow, so the copy sets the bit."""
        self.assertIn("executable=True", self.wizard)

    def test_one_admin_detect_and_one_contexts_array_for_every_gate(self):
        """AC-3: the E2E context extends the SAME contexts array the other
        gates manage — never a second protection call per gate."""
        self.assertIn("permissions.admin", self.protection)
        self.assertIsNotNone(
            re.search(r"(?is)same.{0,80}`contexts`|`contexts`.{0,80}same",
                      self.protection),
            "the branch-protection step must state every context extends the "
            "same contexts array (AC-3)")
        self.assertIn("never a second protection call", self.protection)

    def test_the_context_literal_is_pinned(self):
        """AC-3: the required status check's name is exact."""
        self.assertIn('"E2E suite"', self.protection)
        import sys
        sys.path.insert(0, os.path.join(PLUGIN, "hooks", "scripts"))
        import setup_wizard
        self.assertEqual(setup_wizard.CI_INSTALLS["e2e"][2], "E2E suite")

    def test_the_mutating_call_needs_admin_and_consent(self):
        """AC-3: admin detection alone is not permission."""
        self.assertIsNotNone(
            re.search(r"(?is)admin.{0,40}(and|AND).{0,40}consent", self.protection),
            "the step must gate the mutating PUT on admin AND consent (AC-3)")

    def test_the_register_check_first_recovery_is_stated(self):
        """Operability: a context GitHub has never seen returns 422."""
        self.assertIn("422", self.protection)
        self.assertIsNotNone(
            re.search(r"(?is)422.{0,200}(open a PR|re-run)", self.protection))

    def test_it_is_printed_once_and_never_hard_fails(self):
        """AC-4."""
        self.assertIsNotNone(
            re.search(r"(?is)once.{0,120}never hard-fail", self.protection),
            "the step must state the command is printed ONCE and setup never "
            "hard-fails over branch protection (AC-4)")

    def test_gh_only_auth_no_secrets(self):
        """AC-6: gh is the transport and its own auth is the credential."""
        self.assertIn("gh api", self.protection)
        lowered = self.protection.lower()
        for gate in ("secret key", "credential in settings", "store a token"):
            self.assertNotIn(gate, lowered)
        self.assertIsNotNone(
            re.search(r"(?is)nothing is ever stored in settings", lowered),
            "the step must say gh's own authentication is what authorises the "
            "call, so nothing is stored (AC-6)")

    def test_no_new_settings_key(self):
        """C-4: the gate introduces no settings key — the command source is
        whatever e2e/suites.e2e already holds."""
        lowered = self.body.lower()
        for shaped in ("e2e.ci", "e2e.required", "suites.e2e.ci"):
            self.assertNotIn(shaped, lowered)
        with open(SCHEMA_PATH, encoding="utf-8") as fh:
            schema = json.load(fh)
        self.assertNotIn("ci", schema["properties"]["e2e"]["properties"])

    def test_the_summary_reports_the_gate_outcome(self):
        """Recording parity: the summary still covers every resolved setting
        and where it landed, and the completion report names the e2e gate."""
        self.assertIsNotNone(re.search(r"(?i)where it landed", self.summary))
        m = re.search(r"(?s)CI convention enforcement outcome.{0,400}", self.body)
        self.assertIsNotNone(m)
        self.assertIn("e2e gate", m.group(0))


if __name__ == "__main__":
    unittest.main()
