"""A refused gate stays refused, and `acs step start` re-applies the brakes.

Three holes, one mechanism. The PreToolUse(Skill) hook writes its evidence
BEFORE it decides (fail-open, MAR-514) -- and `acs step start` then read the
evidence of a BLOCKED call as `gate_evidence_accepted`, so a coordinator that
carried on past a refusal opened its step with the ledger calling it gated.
`step start` itself checked the invariants and no brake, so on a host that
never fires the hook an epic was analyzed, a failed review opened as a PR and
a merge attempted with no PR recorded. And the pre-hook created the run and
took its lock before a brake refused, leaving both behind for a step that
never started.
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from acs_case import AcsWorkspaceCase, lib  # noqa: E402


class RefusedGateEvidenceTest(AcsWorkspaceCase):

    def verdict(self, skill):
        return lib.gate_evidence(lib.build_context(self.repo), skill)[1]

    def test_a_refused_pre_hook_leaves_no_run_and_no_lock(self):
        epic = self.new_ticket("Order tracking", "epic")
        out = self.pre("analyze-requirements", epic)
        self.assertEqual(out.returncode, 2, out.stderr)
        self.assertIn("epic", out.stderr)
        self.assertFalse(os.path.exists(os.path.join(self.rdir(epic), "run.json")))
        self.assertFalse(os.path.exists(os.path.join(self.rdir(epic), "lock.json")))
        self.assertIsNone(lib.sessions.current_run_id(lib.repo_dir(self.ws, "acme-shop"),
                                                      lib.checkout_id(self.repo)))

    def test_refused_evidence_is_never_accepted(self):
        story = self.new_ticket("Wishlist API", "story")
        out = self.pre("create-tech-design", story)
        self.assertEqual(out.returncode, 2, out.stderr)
        verdict = self.verdict("create-tech-design")
        self.assertFalse(verdict["gated"])
        self.assertEqual(verdict["reason"], "gate_refused")

    def test_a_passing_pre_hook_is_still_accepted(self):
        story = self.new_ticket("Wishlist API", "story")
        out = self.pre("analyze-requirements", story)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(self.verdict("analyze-requirements")["reason"],
                         "gate_evidence_accepted")

    def test_step_start_refuses_after_a_refused_gate_even_under_warn(self):
        story = self.new_ticket("Wishlist API", "story")
        self.ensure_run(story)
        self.assertEqual(self.pre("analyze-requirements", story).returncode, 0)
        # Force the refusal the pre-hook would have recorded for any reason.
        ctx = lib.build_context(self.repo)
        evidence = lib.read_json(lib.gate_evidence_path(
            ctx["workspace"], ctx["repo_id"], ctx["checkout_id"]))
        lib.refuse_gate_evidence(ctx, evidence)
        out = self.run_script("acs.py", "step", "start", "--step", "analyze-requirements",
                              "--run", story)
        self.assertEqual(out.returncode, 2, out.stdout)
        self.assertIn("REFUSED", out.stderr)


class StepStartAppliesTheBrakesTest(AcsWorkspaceCase):
    """No hook fires in any of these: `step start` alone must hold."""

    def step_start(self, *argv):
        return self.run_script("acs.py", "step", "start", *argv)

    def test_an_epic_is_not_analyzed_and_gets_no_run(self):
        epic = self.new_ticket("Order tracking", "epic")
        out = self.step_start("--step", "analyze-requirements", "--ticket", epic)
        self.assertEqual(out.returncode, 2, out.stdout)
        self.assertIn("epic", out.stderr)
        self.assertFalse(os.path.exists(os.path.join(self.rdir(epic), "run.json")))

    def test_an_epic_run_named_by_run_id_is_refused_too(self):
        epic = self.new_ticket("Order tracking", "epic")
        self.ensure_run(epic)
        out = self.step_start("--step", "create-impl-plan", "--run", epic)
        self.assertEqual(out.returncode, 2, out.stdout)
        self.assertIn("epic", out.stderr)

    def test_a_failed_review_never_becomes_a_pr(self):
        story = self.new_ticket("Wishlist API", "story")
        rdir = self.walk_to(story, "review-code")
        path = lib.state_path(rdir, "review-code")
        state = lib.read_json(path)
        state["states"]["verifier_passed"] = False
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(state, fh)
        out = self.step_start("--step", "create-pr", "--run", story)
        self.assertEqual(out.returncode, 2, out.stdout)
        self.assertIn("did not pass", out.stderr)

    def test_a_merge_needs_a_recorded_pr(self):
        story = self.new_ticket("Wishlist API", "story")
        out = self.step_start("--step", "merge-pr", "--ticket", story)
        self.assertEqual(out.returncode, 2, out.stdout)
        self.assertIn("no PR reference recorded", out.stderr)

    def test_create_tech_design_needs_the_flag(self):
        story = self.new_ticket("Wishlist API", "story")
        out = self.step_start("--step", "create-tech-design", "--ticket", story)
        self.assertEqual(out.returncode, 2, out.stdout)
        self.assertIn("needs_design", out.stderr)


if __name__ == "__main__":
    import unittest
    unittest.main()
