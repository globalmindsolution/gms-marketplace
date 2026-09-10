"""MAR-575 -- what s03 asserts about the gates after a verifier-clean /acs:code.

The shipped pipeline puts /acs:docs-sync between /acs:code and /acs:create-pr
(plugins/acs/hooks/scripts/acs_lib/gates.py:165-211: gate_docs_sync needs only a
completed code step and no pending test step; gate_create_pr additionally needs
a completed docs-sync and blocks with "run /acs:docs-sync <id> first"). The
scenario asserted the create-pr gate opened straight after code, so every paid
run reported a failure the pipeline actually guarantees.

These tests drive `s03_resume_and_verify.run()` against a scripted sandbox --
no `claude`, no network, no cost -- and pin the G3 expectation while leaving G2
and G4 in place.

Run:  python3 -m unittest tests.acs.test_eval_scenario_gates -v
"""

import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

sys.path.insert(0, os.path.join(REPO_ROOT, "evals", "acs"))
from scenarios import s03_resume_and_verify as s03  # noqa: E402

BLOCKED_ON_DOCS_SYNC = (
    2, "acs pre-create-pr: blocked - /docs-sync has not run for EVAL-1 - "
       "run /acs:docs-sync EVAL-1 first.")


class _ScriptedSandbox:
    """Stand-in for `harness.Sandbox`: scripted gate answers, real temp dirs.

    `gates` maps a skill name to the (exit, message) pair its gate returns; the
    order the scenario asked in is recorded so the sequence can be asserted.
    """

    def __init__(self, tmp, gates, health_wired=True, changed=120,
                 pipeline=None, session_ok=True):
        self.tmp = tmp
        self.gates = gates
        self.health_wired = health_wired
        self.changed = changed
        self.pipeline = pipeline or {"steps": {"code": {"status": "completed"}}}
        self.session_ok = session_ok
        self.asked = []
        self.repo = os.path.join(tmp, "repo")
        os.makedirs(self.repo, exist_ok=True)

    def __call__(self, **kwargs):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def mint_ticket(self, title, ttype="task", needs_design=False, parent=None):
        return "EVAL-1"

    def ticket_path(self, ticket, *rel):
        return os.path.join(self.tmp, "ws", ticket, *rel)

    def gate(self, skill, args=""):
        self.asked.append(skill)
        return self.gates.get(skill, (0, ""))

    def run_skill(self, prompt, **kwargs):
        if self.health_wired:
            with open(os.path.join(self.repo, "app.py"), "w") as fh:
                fh.write('@app.get("/health")\ndef health():\n    return "ok"\n')
        return {"ok": self.session_ok, "cost_usd": 0.42, "raw": "", "stderr": ""}

    def ticket_json(self, ticket, name):
        return self.pipeline

    def changed_lines(self):
        return self.changed


class S03GateExpectationTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="acs-s03-test-")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def _run(self, gates, **kwargs):
        sandbox = _ScriptedSandbox(self.tmp, gates, **kwargs)
        with mock.patch.object(s03, "Sandbox", sandbox):
            check = s03.run()
        return check, sandbox

    def _labels(self, check):
        return [label for label, _, _ in check.results]

    def _result(self, check, needle):
        for label, ok, _ in check.results:
            if needle in label:
                return ok
        raise AssertionError("no assertion mentioning %r in %r"
                             % (needle, self._labels(check)))

    def test_shipped_pipeline_state_passes(self):
        check, sandbox = self._run({"code": (0, ""), "docs-sync": (0, ""),
                                    "create-pr": BLOCKED_ON_DOCS_SYNC})
        self.assertTrue(check.passed, self._labels(check))
        self.assertEqual(sandbox.asked, ["code", "docs-sync", "create-pr"])

    def test_a_blocked_docs_sync_gate_fails_the_scenario(self):
        check, _ = self._run({
            "code": (0, ""), "create-pr": BLOCKED_ON_DOCS_SYNC,
            "docs-sync": (2, "acs pre-docs-sync: blocked - /code has not run for EVAL-1.")})
        self.assertFalse(check.passed)
        self.assertFalse(self._result(check, "docs-sync"))

    def test_an_open_create_pr_gate_fails_the_scenario(self):
        # create-pr opening before docs-sync ran would mean the ordering the
        # pipeline promises is gone -- that is a finding, not a pass.
        check, _ = self._run({"code": (0, ""), "docs-sync": (0, ""),
                              "create-pr": (0, "")})
        self.assertFalse(check.passed)
        self.assertFalse(self._result(check, "create-pr"))

    def test_create_pr_blocked_for_another_reason_fails_the_scenario(self):
        check, _ = self._run({
            "code": (0, ""), "docs-sync": (0, ""),
            "create-pr": (2, "acs pre-create-pr: blocked - /code completed but its "
                             "verifier did not pass for EVAL-1.")})
        self.assertFalse(check.passed)
        self.assertFalse(self._result(check, "create-pr"))

    def test_g2_and_g4_are_still_asserted(self):
        check, _ = self._run({"code": (0, ""), "docs-sync": (0, ""),
                              "create-pr": BLOCKED_ON_DOCS_SYNC})
        labels = " | ".join(self._labels(check))
        self.assertIn("resumed from state", labels)
        self.assertIn("PR-size under cap (G4)", labels)
        self.assertIn("code step completed", labels)

    def test_g2_still_fails_when_the_spec_was_not_read(self):
        check, _ = self._run({"code": (0, ""), "docs-sync": (0, ""),
                              "create-pr": BLOCKED_ON_DOCS_SYNC},
                             health_wired=False)
        self.assertFalse(check.passed)
        self.assertFalse(self._result(check, "resumed from state"))

    def test_g4_still_fails_over_the_cap(self):
        check, _ = self._run({"code": (0, ""), "docs-sync": (0, ""),
                              "create-pr": BLOCKED_ON_DOCS_SYNC},
                             changed=612)
        self.assertFalse(check.passed)
        self.assertFalse(self._result(check, "PR-size under cap (G4)"))


if __name__ == "__main__":
    unittest.main()
