"""MAR-125 (E2E-1) — /acs:init Step 7f: e2e required merge gate wiring.

Prose-contract unit test for `plugins/acs/skills/init/SKILL.md`'s new opt-in
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
tests/acs/test_mar89_init_offers.py's `section()` helper + bounded-window
co-occurrence style — never a bare file-wide assertIn.

Run:  python3 -m unittest tests.acs.test_mar125_init_e2e_gate -v
"""

import json
import os
import re
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN = os.path.join(REPO_ROOT, "plugins", "acs")
SKILL_PATH = os.path.join(PLUGIN, "skills", "init", "SKILL.md")
SCHEMA_PATH = os.path.join(PLUGIN, "schemas", "settings.schema.json")


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def section(body, heading):
    """Return the text of a markdown section: from the line whose start is
    `heading` (a real heading, matched at line-start) up to the next
    same-or-higher-level heading (or end of file). Mirrors
    test_mar89_init_offers.py's helper exactly."""
    m = re.search(r"(?m)^" + re.escape(heading) + r"\b.*$", body)
    if m is None:
        raise AssertionError("heading %r not found in SKILL.md" % heading)
    start = m.start()
    level = len(heading) - len(heading.lstrip("#"))
    nxt = re.search(r"(?m)^#{1,%d} \S" % level, body[m.end():])
    end = m.end() + nxt.start() if nxt else len(body)
    return body[start:end]


class Mar125InitE2eGateCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.body = read(SKILL_PATH)
        # Anchored on the real `## Step 7f` heading, not any inline mention.
        cls.step7f = section(cls.body, "## Step 7f")
        cls.step8 = section(cls.body, "## Step 8")

    # 1. heading exists (fixture for every other case)
    def test_step7f_heading_exists(self):
        self.assertIn("Step 7f", self.step7f.splitlines()[0])

    # 2. AC-1 opt-in-guard half — the required unset-is-a-no-op test
    def test_step7f_guarded_on_e2e_configured(self):
        head = self.step7f[:800]
        self.assertTrue(
            re.search(r"(?s)(suites\.e2e|`e2e`|settings\.e2e).{0,200}"
                      r"(configured|unset)", head)
            or re.search(r"(?s)(configured|unset).{0,200}"
                         r"(suites\.e2e|`e2e`|settings\.e2e)", head),
            "Step 7f must state near its top that it is gated on "
            "settings.e2e/suites.e2e being configured (AC-1 opt-in-guard)",
        )

    # 3. artifact-installation contract
    def test_step7f_copies_both_templates(self):
        self.assertIn("acs-e2e.yml", self.step7f)
        self.assertIn("run-e2e.py", self.step7f)
        self.assertIn("cp ", self.step7f)

    # 4. reuse, not duplicate
    def test_step7f_reuses_step7c_admin_detect(self):
        self.assertTrue(
            re.search(r"(?s)admin.{0,300}(gh api|permissions\.admin)", self.step7f)
            or re.search(r"(?s)Step 7c.{0,300}admin", self.step7f),
            "Step 7f must reference Step 7c's admin-detect mechanism",
        )

    # 5. AC-3 — no duplicate protection call
    def test_step7f_extends_same_contexts_array(self):
        self.assertTrue(
            re.search(r"(?is)contexts.{0,200}(same|alongside|extend)", self.step7f)
            or re.search(r"(?is)(same|alongside|extend).{0,200}contexts", self.step7f),
            "Step 7f must state the E2E suite context extends the SAME "
            "contexts array 7c/7d manage",
        )

    # 6. AC-3 — pins the literal
    def test_step7f_context_literal_is_e2e_suite(self):
        self.assertIn('"E2E suite"', self.step7f)

    # 7. AC-3 — admin AND consent, not admin alone
    def test_step7f_admin_gated_wiring(self):
        self.assertTrue(
            re.search(r"(?is)admin\s*=\s*true.{0,200}consent", self.step7f)
            or re.search(r"(?is)consent.{0,200}admin\s*=\s*true", self.step7f),
            "Step 7f must gate the mutating PUT on admin=true AND consent, "
            "not admin detection alone",
        )

    # 8. operability — avoids chicken-and-egg lockout
    def test_step7f_register_check_first_ordering(self):
        self.assertTrue(
            re.search(r"(?is)(422|unknown context).{0,300}(open a PR|re-run)", self.step7f)
            or re.search(r"(?is)(open a PR|re-run).{0,300}(422|unknown context)", self.step7f),
            "Step 7f must state the register-check-first / 422 recovery",
        )

    # 9. AC-4 — report-once safeguard
    def test_step7f_report_once_never_hard_fails(self):
        self.assertTrue(
            re.search(r"(?is)once.{0,300}never.{0,60}hard.?fail", self.step7f)
            or re.search(r"(?is)never.{0,60}hard.?fail.{0,300}once", self.step7f),
            "Step 7f must state the manual gh api command is printed ONCE "
            "and /acs:init NEVER hard-fails (AC-4)",
        )

    # 10. AC-6 — gh-only auth, no secrets
    def test_step7f_gh_only_auth_no_secrets(self):
        self.assertIn("gh api", self.step7f)
        lowered = self.step7f.lower()
        for gate in ("secret key", "credential in settings", "store a token"):
            self.assertNotIn(gate, lowered)

    # 11. C-4 — no new settings key
    def test_no_new_settings_key_in_step7f(self):
        lowered = self.step7f.lower()
        for shaped in ("e2e.ci", "e2e.required", "suites.e2e.ci"):
            self.assertNotIn(shaped, lowered)
        with open(SCHEMA_PATH, encoding="utf-8") as fh:
            schema = json.load(fh)
        self.assertNotIn("ci", schema["properties"]["e2e"]["properties"])

    # 12. recording parity — Step 8 summary table
    def test_step8_summary_table_has_e2e_row(self):
        self.assertTrue(
            re.search(r"(?i)e2e.*gate|e2e.*ci", self.step8),
            "Step 8's summary table must gain a row referencing the e2e "
            "gate outcome",
        )

    # 13. recording parity — completion report Results line.
    # Anchored directly on cls.body (not a section() extraction): the
    # completion report's fenced markdown EXAMPLE itself contains a
    # `## /acs:init · <ticket-id> · <status>` line that section()'s
    # next-heading scan would mistake for a real heading boundary, cutting
    # the section off before the Results line it's meant to capture. A
    # bounded-window search anchored on the pre-existing "CI convention
    # enforcement outcome" marker avoids that trap.
    def test_completion_report_mentions_e2e_gate_outcome(self):
        m = re.search(r"(?s)CI convention enforcement outcome.{0,400}", self.body)
        self.assertIsNotNone(
            m, "completion report must retain the 'CI convention enforcement "
               "outcome' clause"
        )
        self.assertIn(
            "e2e gate", m.group(0),
            msg="the completion-report Results line must mention the e2e "
                "gate CI convention outcome alongside the existing clause",
        )


if __name__ == "__main__":
    unittest.main()
