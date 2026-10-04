"""A delivery-ticket skill's run ends when the skill does.

`acs step start --allocate` opens a run over a product skill's delivery ticket
(the product skills, e.g. `create-architecture`). The skill is never a workflow
step, so `finish_step` never touched that run: it stayed `in_progress` with its
cursor on the workflow's first step, and the checkout's pointer kept naming it
-- so the next `/acs:ship` from that checkout resumed the delivery ticket at
`analyze-requirements`.
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from acs_case import AcsWorkspaceCase, lib  # noqa: E402


class DeliveryRunConcludesTest(AcsWorkspaceCase):

    def allocate(self, step="create-architecture"):
        out = self.run_script("acs.py", "step", "start", "--step", step, "--allocate")
        self.assertEqual(out.returncode, 0, out.stderr)
        return json.loads(out.stdout)["ticket_id"]

    def finish(self, step, ticket, result):
        out = self.post(step, ticket, result)
        self.assertEqual(out.returncode, 0, out.stderr)
        return json.loads(out.stdout)

    def pointer(self):
        return lib.sessions.current_run_id(lib.repo_dir(self.ws, "acme-shop"),
                                           lib.checkout_id(self.repo))

    def test_a_completed_delivery_skill_completes_its_run_and_frees_the_checkout(self):
        ticket = self.allocate()
        self.assertEqual(self.pointer(), ticket)
        out = self.finish("create-architecture", ticket, {
            "status": "completed", "summary": "additive scaffold verified",
            "states": {"recommended_follow_ups": []}})
        self.assertEqual(out["run_status"], "completed")
        doc = lib.load_run(self.rdir(ticket))
        self.assertIsNone(doc["cursor"], "no workflow step is pending on a delivery run")
        self.assertEqual(doc["concluded_by"], "create-architecture")
        self.assertIsNone(self.pointer(), "a finished delivery run must not stay current")

    def test_a_failed_delivery_skill_fails_its_run(self):
        ticket = self.allocate("create-prd")
        out = self.finish("create-prd", ticket, {"status": "failed",
                                                 "summary": "gh pr create failed"})
        self.assertEqual(out["run_status"], "failed")

    def test_an_interrupted_delivery_skill_keeps_its_run_for_the_resume(self):
        ticket = self.allocate()
        out = self.finish("create-architecture", ticket,
                          {"status": "interrupted", "stop_reason": "session_end"})
        self.assertEqual(out["run_status"], "in_progress")
        self.assertEqual(self.pointer(), ticket)

    def test_a_second_handoff_still_names_the_delivery_skill(self):
        """Nothing in flight on the second call: a delivery run has no cursor
        for /acs:ship to follow, so the resume names the skill it interrupted."""
        ticket = self.allocate()
        for _ in range(2):
            out = self.run_script("handoff.py", "--summary", "s", "--run", ticket)
            self.assertEqual(out.returncode, 0, out.stderr)
            self.assertEqual(json.loads(out.stdout)["continue_with"],
                             "/acs:create-architecture %s" % ticket)

    def test_a_workflow_run_is_not_concluded_by_a_standalone_skill(self):
        """A delivery skill finishing inside a run that has recorded workflow
        steps leaves that run to the workflow."""
        ticket = self.new_ticket("Wishlist API", "task")
        self.walk_to(ticket, "analyze-requirements")
        doc = lib.conclude_standalone_run(self.rdir(ticket), "create-architecture", "completed")
        self.assertEqual(doc["status"], "in_progress")
        self.assertNotIn("concluded_by", doc)


if __name__ == "__main__":
    import unittest
    unittest.main()
