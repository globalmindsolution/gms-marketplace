"""The pre-hook gate's generic half (§3.11).

Replaces tests/acs/test_acs_lib_gates.py, whose subject was the seventeen
per-skill `gate_*` functions and the four-family `GATE_INPUTS` partition that
classified them. Both are gone, and so is the generic input gate that replaced
them: what stayed is only what is genuinely a safety brake.

The claims that matter:

  * a gate NEVER checks position. Order is /acs:ship's, via the cursor, and a
    skill invoked by hand is never asked whether it is next -- which is the
    whole of what makes every skill independently invocable.
  * a gate NEVER checks inputs either: each skill reads what it finds and
    falls back to the run's subject
  * a step that owes nothing is COMPLETED by the pre-hook, with the plan's own
    reason, and its coordinator never runs

Run:  python3 -m unittest tests.acs.test_step_gate -v
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))), "plugins", "acs", "hooks", "scripts"))

from acs_lib import run as R  # noqa: E402
from acs_lib import step as S  # noqa: E402
from acs_lib import stepgate as G  # noqa: E402
from acs_lib import workflow as W  # noqa: E402
from acs_lib._common import GateError  # noqa: E402

PLUGIN = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "plugins", "acs")
SHIP = os.path.join(PLUGIN, "workflows", "ship.yaml")

PLAN = """# Plan

Retry with a capped backoff.

## Contract
delivery_path: %s
owes:
%s  test_cases: %s
  e2e: %s
  reason: "%s"

### Executor tasks & file map
- task 1: src/auth/session.py
"""


class GateBase(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.repo = os.path.join(self.tmp, "wk", "acme")
        os.makedirs(self.repo)
        self.wf = W.validate_workflow_file(SHIP)
        self.rid, self.rdir, _doc = R.create_run(
            self.repo, {"kind": "prompt", "text": "add a retry budget"}, self.wf, SHIP)

    def write_plan(self, path="standard", cases="true", e2e="false",
                   reason="CLI-only change; no HTTP surface, no browser flow",
                   legacy_api=None):
        """`legacy_api` writes the `owes.api_contract` line a plan carried
        before ADR-0134 -- still a loadable plan, the key ignored."""
        target = R.artifact_path(self.rdir, "plan")
        os.makedirs(os.path.dirname(target), exist_ok=True)
        legacy = "  api_contract: %s\n" % legacy_api if legacy_api is not None else ""
        with open(target, "w", encoding="utf-8") as handle:
            handle.write(PLAN % (path, legacy, cases, e2e, reason))
        return target


class NoInputGateTest(GateBase):

    def test_there_is_no_input_gate(self):
        """Skills are independent: nothing refuses one because an upstream
        artifact is absent."""
        self.assertFalse(hasattr(G, "check_inputs"))
        self.assertFalse(hasattr(R, "missing_reads"))


class NoOpTest(GateBase):
    """§2.2 — the steps that can owe nothing on a change that owes nothing,
    and the pre-hook is where that is settled."""

    def test_a_plan_that_owes_no_cases_settles_the_step(self):
        self.write_plan(cases="false", reason="docs-only change; nothing to test")
        settled = G.settle_no_op(self.rdir, "create-test-docs", self.rid, self.wf)
        self.assertEqual(settled[0], "no_cases_owed")
        self.assertEqual(settled[1], "docs-only change; nothing to test",
                         "the PLAN's reason, not a generic one")

    def test_the_step_is_completed_and_the_cursor_moves_on(self):
        self.write_plan(cases="false")
        G.settle_no_op(self.rdir, "create-test-docs", self.rid, self.wf)
        doc = R.load_run(self.rdir)
        entry = doc["steps"]["create-test-docs"]
        self.assertEqual(entry["status"], "completed")
        self.assertEqual(entry["outcome"], "no_cases_owed")
        self.assertNotEqual(doc["cursor"], "create-test-docs")

    def test_the_no_op_writes_a_result_so_i3_holds(self):
        self.write_plan(cases="false")
        G.settle_no_op(self.rdir, "create-test-docs", self.rid, self.wf)
        errors, _warnings = R.check(self.rdir, self.wf)
        self.assertEqual(errors, [], "a completed step must have a result.json")

    def test_a_plan_that_owes_the_cases_does_not_settle(self):
        self.write_plan(cases="true")
        self.assertIsNone(G.settle_no_op(self.rdir, "create-test-docs",
                                         self.rid, self.wf))

    def test_silence_is_not_permission_to_skip(self):
        """A plan that does not mention an artifact leaves the step to do its
        work. The alternative -- treating absence as `false` -- would make an
        old plan silently disable the test-cases step."""
        target = R.artifact_path(self.rdir, "plan")
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "w", encoding="utf-8") as handle:
            handle.write("# Plan\n\nProse only; no Contract block.\n")
        self.assertIsNone(G.noop_decision(self.rdir, "create-test-docs"))

    def test_no_plan_at_all_owes_work(self):
        self.assertIsNone(G.noop_decision(self.rdir, "create-test-docs"))

    def test_a_step_that_always_has_work_never_settles(self):
        self.write_plan(cases="false", e2e="false")
        for step in ("code", "review-code", "docs-sync", "create-pr"):
            self.assertIsNone(G.noop_decision(self.rdir, step), step)

    def test_the_api_contract_is_no_longer_a_no_op_step(self):
        """ADR-0134: create-api-contract is a Design skill, not a step of
        ship, so no plan decides whether it runs."""
        self.assertNotIn("create-api-contract", G.NO_OP_STEPS)
        self.assertEqual(sorted(G.NO_OP_STEPS),
                         ["create-e2e-tests", "create-test-docs", "run-e2e-tests"])

    def test_a_legacy_plan_owing_no_contract_settles_nothing_for_it(self):
        """A plan written before ADR-0134 still carries `owes.api_contract`.
        It loads, its other flags still settle their steps, and the legacy
        key decides nothing."""
        self.write_plan(cases="false", legacy_api="false")
        self.assertIsNone(G.noop_decision(self.rdir, "create-api-contract"))
        self.assertEqual(G.noop_decision(self.rdir, "create-test-docs")[0],
                         "no_cases_owed")


class InvariantGateTest(GateBase):

    def test_a_clean_run_passes(self):
        self.assertEqual(G.check_invariants(self.rdir, self.wf), [])

    def test_a_drifted_ledger_is_refused_before_any_write(self):
        doc = R.require_run(self.rdir)
        doc["steps"]["code"] = {"status": "completed"}   # no result.json: I3
        R.save_run(self.rdir, doc)
        with self.assertRaises(GateError) as caught:
            G.check_invariants(self.rdir, self.wf)
        self.assertIn("inconsistent", str(caught.exception))
        self.assertIn("acs run check", str(caught.exception),
                      "the refusal says how to inspect it")

    def test_exceeding_a_loop_cap_by_hand_is_a_warning_not_a_refusal(self):
        """I4: /acs:ship refuses to loop past the cap, but by hand the user is
        the loop controller."""
        doc = R.require_run(self.rdir)
        doc["loops"] = {"review-code": {"iteration": 9, "max": 3}}
        R.save_run(self.rdir, doc)
        warnings = G.check_invariants(self.rdir, self.wf)
        self.assertTrue(any("I4" in w for w in warnings), warnings)


class OrderIsNotGatedTest(GateBase):
    """The property the whole redesign rests on: a gate checks brakes, never
    position and never inputs."""

    def test_a_later_step_passes_with_nothing_before_it_run(self):
        self.assertEqual(R.load_run(self.rdir)["steps"], {},
                         "nothing has run yet")
        self.assertEqual(G.check_invariants(self.rdir, self.wf), [])
        self.assertIsNone(G.noop_decision(self.rdir, "code"),
                          "code has work without analyze-requirements having run")


if __name__ == "__main__":
    unittest.main()
