"""MAR-575 -- the paid tier's free pre-flight: never spend on a blind sandbox.

Three paid runs reported routing failures that were really a sandbox that could
not see the plugin at all. The runner now probes one throwaway session for
`/acs:setup` registration (decided at the session's init event, before any model
turn, so it is free) and refuses to start the paid tier when that probe fails.

These tests drive `evals/acs/run_evals.py` with fake scenarios and a fake
sandbox: no `claude`, no network, no cost.

Run:  python3 -m unittest tests.acs.test_eval_preflight -v
"""

import contextlib
import io
import os
import sys
import unittest
from unittest import mock

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

sys.path.insert(0, os.path.join(REPO_ROOT, "evals", "acs"))
import harness  # noqa: E402  (path-inserted, same resolution run_evals.py uses)
import run_evals  # noqa: E402


class _FakeScenario:
    """A scenario module stand-in that records whether it was run."""

    def __init__(self, name, tier, passing=True):
        self.META = {"name": name, "tier": tier, "goal": "g", "summary": "s"}
        self.passing = passing
        self.runs = 0

    def run(self):
        self.runs += 1
        check = harness.Check(self.META["name"])
        check.ok("did something", self.passing)
        return check


class _FakeSandbox:
    """Records how the pre-flight opened its sandbox and what it probed."""

    def __init__(self, answer):
        self.answer = answer
        self.kwargs = None
        self.probes = []

    def __call__(self, **kwargs):
        self.kwargs = kwargs
        return self

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def trigger_detail(self, request, **kwargs):
        self.probes.append(request)
        return self.answer


def drive(argv, scenarios, preflight=None):
    """Run `main()` with fake scenarios; returns (exit code, stdout)."""
    out = io.StringIO()
    with contextlib.ExitStack() as stack:
        stack.enter_context(
            mock.patch.object(run_evals, "load_scenarios", return_value=scenarios))
        stack.enter_context(mock.patch.object(sys, "argv", argv))
        stack.enter_context(contextlib.redirect_stdout(out))
        if preflight is not None:
            stack.enter_context(
                mock.patch.object(run_evals, "run_preflight", preflight))
        code = run_evals.main()
    return code, out.getvalue()


class PreflightVerdictTest(unittest.TestCase):
    """The decision itself is pure: only a registered /acs:setup is a pass."""

    def test_registered_setup_is_the_only_pass(self):
        ok, _ = run_evals.preflight_verdict("acs:setup", "registered")
        self.assertTrue(ok)

    def test_unregistered_command_fails(self):
        ok, msg = run_evals.preflight_verdict(None, "registered")
        self.assertFalse(ok)
        self.assertIn("acs:setup", msg)

    def test_unmeasured_session_fails(self):
        ok, msg = run_evals.preflight_verdict(None, "unmeasured")
        self.assertFalse(ok)
        self.assertIn("unmeasured", msg)

    def test_a_model_routed_answer_is_not_a_registration(self):
        ok, _ = run_evals.preflight_verdict("acs:setup", "skill_tool_use")
        self.assertFalse(ok)

    def test_another_command_is_not_setup(self):
        ok, _ = run_evals.preflight_verdict("acs:code", "registered")
        self.assertFalse(ok)


class RunPreflightTest(unittest.TestCase):
    """The probe runs in a fresh uninitialized sandbox and costs no model turn."""

    def _probe(self, answer):
        sandbox = _FakeSandbox(answer)
        with mock.patch.object(run_evals, "Sandbox", sandbox):
            ok, msg = run_evals.run_preflight()
        return ok, msg, sandbox

    def test_probes_an_uninitialized_sandbox_with_the_explicit_command(self):
        ok, _, sandbox = self._probe(("acs:setup", "registered"))
        self.assertTrue(ok)
        self.assertEqual(sandbox.probes, ["/acs:setup"])
        self.assertIs(sandbox.kwargs.get("init"), False)
        self.assertEqual(sandbox.kwargs.get("slug"), "preflight")

    def test_a_blind_sandbox_fails_the_probe(self):
        ok, msg, _ = self._probe((None, "registered"))
        self.assertFalse(ok)
        self.assertTrue(msg)


class PaidTierIsGatedTest(unittest.TestCase):
    """AC-4: a failed pre-flight aborts the paid tier without running one."""

    def setUp(self):
        self.free = _FakeScenario("install_gate_smoke", "free")
        self.paid = _FakeScenario("skill_triggers", "paid")
        self.scenarios = [self.free, self.paid]

    def test_failed_preflight_runs_no_paid_scenario(self):
        code, out = drive(["run_evals.py", "--paid"], self.scenarios,
                          preflight=lambda: (False, "no acs command is registered"))
        self.assertEqual(self.paid.runs, 0)
        self.assertEqual(code, 1)
        self.assertIn("PRE-FLIGHT FAILED", out)
        self.assertIn("cannot see the plugin", out)
        self.assertIn("skill_triggers", out)

    def test_failed_preflight_still_runs_the_free_tier(self):
        code, out = drive(["run_evals.py", "--paid"], self.scenarios,
                          preflight=lambda: (False, "no acs command is registered"))
        self.assertEqual(self.free.runs, 1)
        self.assertEqual(code, 1)
        self.assertNotIn("all passed.", out)

    def test_passing_preflight_runs_the_paid_tier(self):
        code, _ = drive(["run_evals.py", "--paid"], self.scenarios,
                        preflight=lambda: (True, "acs:setup is registered"))
        self.assertEqual(self.paid.runs, 1)
        self.assertEqual(self.free.runs, 1)
        self.assertEqual(code, 0)

    def test_free_tier_alone_never_runs_the_preflight(self):
        calls = []

        def preflight():
            calls.append(1)
            return True, "unused"

        code, _ = drive(["run_evals.py"], self.scenarios, preflight=preflight)
        self.assertEqual(calls, [])
        self.assertEqual(self.paid.runs, 0)
        self.assertEqual(self.free.runs, 1)
        self.assertEqual(code, 0)

    def test_listing_scenarios_never_runs_the_preflight(self):
        calls = []

        def preflight():
            calls.append(1)
            return True, "unused"

        code, _ = drive(["run_evals.py", "--paid", "--list"], self.scenarios,
                        preflight=preflight)
        self.assertEqual(calls, [])
        self.assertEqual(code, 0)


if __name__ == "__main__":
    unittest.main()
