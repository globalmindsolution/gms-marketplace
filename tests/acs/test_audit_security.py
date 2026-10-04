"""ADR-0123: the Audit phase and /acs:audit-security.

- audit-security is a hooked, ticketless, read-only skill owning two roles: the
  auditor (survey, one per category and code area) and the adjudicator (judge, one
  per candidate finding, refute-by-default).
- Report only: no ticket, no SARIF; uncovered is never clean; a secret's value
  never appears.
"""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from acs_case import AcsWorkspaceCase  # noqa: E402

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN = os.path.join(REPO_ROOT, "plugins", "acs")
sys.path.insert(0, os.path.join(PLUGIN, "hooks", "scripts"))

import acs_lib as lib  # noqa: E402


def flat(*parts):
    with open(os.path.join(PLUGIN, *parts), encoding="utf-8") as fh:
        return " ".join(fh.read().split())


class RegistryTest(unittest.TestCase):

    def test_audit_security_is_hooked_and_owns_two_roles(self):
        self.assertIn("audit-security", lib.HOOKED_SKILLS)
        self.assertEqual(lib.skills_registry.agent_roles_of("audit-security"),
                         ["adjudicator", "auditor"])

    def test_the_roles_are_a_survey_and_a_judge_with_model_defaults(self):
        self.assertEqual(lib.ROLE_KINDS["auditor"], "survey")
        self.assertEqual(lib.ROLE_KINDS["adjudicator"], "judge")
        for role in ("auditor", "adjudicator"):
            self.assertIn(role, lib.models.covered_roles())


class AuditSecurityRunsWithoutATicketTest(AcsWorkspaceCase):

    def test_step_start_and_finish(self):
        # A real invocation's pre-hook records the run over the prompt; stand in for it.
        start = self.run_script("acs.py", "step", "start", "--step", "audit-security",
                                "--args", "all")
        self.assertEqual(start.returncode, 0, start.stderr)
        ctx = json.loads(start.stdout)
        self.assertEqual(ctx["agents"].get("auditor"), "acs:audit-security-auditor")
        self.assertEqual(ctx["agents"].get("adjudicator"), "acs:audit-security-adjudicator")
        path = os.path.join(ctx["partition"], "steps", "audit-security", "iter-1", "report.md")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(os.path.join(PLUGIN, "templates", "audit-security-report.md"),
                  encoding="utf-8") as src, open(path, "w", encoding="utf-8") as dst:
            dst.write(src.read())
        result = {"status": "completed", "summary": "nothing confirmed",
                  "states": {"audit": {"scope": "all", "critical": 0, "high": 0}}}
        done = self.run_script("post-audit-security.py", stdin=json.dumps(result))
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(json.loads(done.stdout)["run_status"], "completed")


class ProseContractTest(unittest.TestCase):

    def test_the_skill_is_read_only_and_report_only(self):
        body = flat("skills", "audit-security", "SKILL.md")
        for phrase in ("You never edit the code", "you never file a ticket",
                       "The audit asks nothing and offers nothing",
                       "never reported as clean", "A secret's value never appears"):
            self.assertIn(phrase, body)

    def test_the_skill_covers_four_categories_and_adjudicates_each_candidate(self):
        body = flat("skills", "audit-security", "SKILL.md")
        for phrase in ("`code`", "`secrets-config`", "`dependencies`", "`threat-model`",
                       "hld/data-flow.md", "exactly one fresh-context adjudicator",
                       "Corroboration is not a filter", "max_parallel = 4",
                       "run_in_background: false"):
            self.assertIn(phrase, body)

    def test_the_auditor_never_installs_and_never_names_a_cve_from_memory(self):
        body = flat("agents", "audit-security-auditor.md")
        for phrase in ("**Never install a scanner**", "**never name a CVE from memory**",
                       "**Never write a secret's value**", "Uncovered is never reported as clean",
                       "CWE-89", "## Grounding (anti-hallucination)"):
            self.assertIn(phrase, body)

    def test_the_adjudicator_refutes_by_default(self):
        body = flat("agents", "audit-security-adjudicator.md")
        for phrase in ("Your job is to **refute** it", "**Default to refuted when uncertain.**",
                       "`resolved_when`", "`needs-context`", "Never raise it without new evidence"):
            self.assertIn(phrase, body)


if __name__ == "__main__":
    unittest.main()
