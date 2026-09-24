"""The pre-hook gate, driven by what the skill declares (§2.4, §3.11).

Replaces tests/acs/test_acs_lib_gates.py, whose subject was the seventeen
per-skill `gate_*` functions and the four-family `GATE_INPUTS` partition that
classified them. Both are gone: the input half is generic now, and what
stayed per-skill is only what is genuinely a safety brake.

The claims that matter:

  * a gate NEVER checks position. Order is /acs:ship's, via the cursor, and a
    skill invoked by hand is never asked whether it is next -- which is the
    whole of what makes every skill independently invocable.
  * the input check and `acs workflow validate` read ONE declaration, so they
    cannot disagree about what a skill needs
  * standalone, a missing required read is a FALLBACK, not a refusal
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
  api_contract: %s
  test_cases: %s
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

    def write_plan(self, path="standard", api="false", cases="true", e2e="false",
                   reason="CLI-only change; no HTTP surface, no browser flow"):
        target = R.artifact_path(self.rdir, "plan", None, self.wf)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "w", encoding="utf-8") as handle:
            handle.write(PLAN % (path, api, cases, e2e, reason))
        return target


class InputCheckTest(GateBase):

    def test_a_missing_required_read_is_refused_under_a_workflow(self):
        with self.assertRaises(GateError) as caught:
            G.check_inputs(self.rdir, "code", wf=self.wf, standalone=False)
        message = str(caught.exception)
        self.assertIn("plan", message)
        self.assertIn("create-impl-plan", message, "the refusal names the PRODUCER")

    def test_standalone_the_same_gap_is_a_fallback(self):
        """§3.11: every artifact has a chain that ends at the subject."""
        fell_back = G.check_inputs(self.rdir, "code", wf=self.wf, standalone=True)
        self.assertEqual(fell_back, ["plan"])

    def test_standalone_with_no_subject_at_all_is_refused(self):
        doc = R.require_run(self.rdir)
        doc["subject"] = {}
        R.save_run(self.rdir, doc)
        with self.assertRaises(GateError) as caught:
            G.check_inputs(self.rdir, "code", wf=self.wf, standalone=True)
        self.assertIn("no subject", str(caught.exception))

    def test_a_present_input_passes(self):
        self.write_plan()
        self.assertEqual(G.check_inputs(self.rdir, "code", wf=self.wf,
                                        standalone=False), [])

    def test_the_gate_reads_the_same_declaration_the_validator_does(self):
        """One declaration, two enforcers. If these ever diverge, a skill can
        pass validation and then be refused at runtime for an input the
        workflow was never asked to provide."""
        from acs_lib import skills as K
        manifests = K.load_manifests()
        for step in W.steps_of(self.wf):
            required, _optional = K.reads_of(step, manifests)
            missing = [a for a, _p in R.missing_reads(self.rdir, step, manifests, self.wf)]
            self.assertTrue(set(missing).issubset(set(required)), step)

    def test_an_artifact_that_is_not_a_file_is_not_checked(self):
        """`changeset` is the working tree against a base ref; the gate asks
        git about it rather than looking for a path."""
        self.assertEqual(G.check_inputs(self.rdir, "docs-sync", wf=self.wf,
                                        standalone=False), [])


class NoOpTest(GateBase):
    """§2.2 — four of the ten steps owe nothing on a change that owes nothing,
    and the pre-hook is where that is settled."""

    def test_a_plan_that_owes_no_contract_settles_the_step(self):
        self.write_plan(api="false", reason="CLI-only change; no HTTP surface")
        settled = G.settle_no_op(self.rdir, "create-api-contract", self.rid, self.wf)
        self.assertEqual(settled[0], "no_surface_owed")
        self.assertEqual(settled[1], "CLI-only change; no HTTP surface",
                         "the PLAN's reason, not a generic one")

    def test_the_step_is_completed_and_the_cursor_moves_on(self):
        self.write_plan(api="false")
        G.settle_no_op(self.rdir, "create-api-contract", self.rid, self.wf)
        doc = R.load_run(self.rdir)
        entry = doc["steps"]["create-api-contract"]
        self.assertEqual(entry["status"], "completed")
        self.assertEqual(entry["outcome"], "no_surface_owed")
        self.assertNotEqual(doc["cursor"], "create-api-contract")

    def test_the_no_op_writes_a_result_so_i3_holds(self):
        self.write_plan(api="false")
        G.settle_no_op(self.rdir, "create-api-contract", self.rid, self.wf)
        errors, _warnings = R.check(self.rdir, self.wf)
        self.assertEqual(errors, [], "a completed step must have a result.json")

    def test_a_plan_that_owes_the_contract_does_not_settle(self):
        self.write_plan(api="true")
        self.assertIsNone(G.settle_no_op(self.rdir, "create-api-contract",
                                         self.rid, self.wf))

    def test_silence_is_not_permission_to_skip(self):
        """A plan that does not mention an artifact leaves the step to do its
        work. The alternative -- treating absence as `false` -- would make an
        old plan silently disable the contract step."""
        target = R.artifact_path(self.rdir, "plan", None, self.wf)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "w", encoding="utf-8") as handle:
            handle.write("# Plan\n\nProse only; no Contract block.\n")
        self.assertIsNone(G.noop_decision(self.rdir, "create-api-contract", wf=self.wf))

    def test_no_plan_at_all_owes_work(self):
        self.assertIsNone(G.noop_decision(self.rdir, "create-api-contract", wf=self.wf))

    def test_a_step_that_always_has_work_never_settles(self):
        self.write_plan(api="false", cases="false", e2e="false")
        for step in ("code", "review-code", "docs-sync", "create-pr"):
            self.assertIsNone(G.noop_decision(self.rdir, step, wf=self.wf), step)


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
    """The property the whole redesign rests on: a gate checks inputs and
    brakes, never position."""

    def test_a_later_step_passes_with_its_inputs_and_nothing_before_it_run(self):
        self.write_plan()
        self.assertEqual(R.load_run(self.rdir)["steps"], {},
                         "nothing has run yet")
        self.assertEqual(G.check_inputs(self.rdir, "code", wf=self.wf,
                                        standalone=False), [],
                         "code gates on its PLAN, not on analyze-requirements "
                         "having completed")


if __name__ == "__main__":
    unittest.main()
