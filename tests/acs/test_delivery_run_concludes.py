"""A product skill runs ticketless, and its run ends when the skill does (ADR-0127).

Before ADR-0127 `acs step start --allocate` minted a delivery ticket for a
product skill (`create-prd`, `create-architecture`) and opened a run over it.
Only /acs:create-pr commits now, so a product skill mints no ticket: `step
start` opens a standalone run over the invocation -- the way the Audit skills'
runs are opened -- and the post-hook concludes it. The property this file has
always guarded still holds: the skill is never a workflow step, so without the
conclusion its run stayed `in_progress` with its cursor on the workflow's
first step, and the next `/acs:ship` from that checkout resumed it at
`analyze-requirements`.
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from acs_case import AcsWorkspaceCase, lib  # noqa: E402


class StandaloneProductRunConcludesTest(AcsWorkspaceCase):

    def begin(self, step="create-architecture", *extra):
        out = self.run_script("acs.py", "step", "start", "--step", step, *extra)
        self.assertEqual(out.returncode, 0, out.stderr)
        return json.loads(out.stdout)

    def finish(self, step, run_id, result):
        out = self.post(step, run_id, result)
        self.assertEqual(out.returncode, 0, out.stderr)
        return json.loads(out.stdout)

    def pointer(self):
        return lib.sessions.current_run_id(lib.repo_dir(self.ws, "acme-shop"),
                                           lib.checkout_id(self.repo))

    def tickets(self):
        index = lib.read_json(lib.index_path(self.ws, "acme-shop")) or {}
        return sorted(index.get("tickets") or {})

    def test_a_product_skill_mints_no_ticket_and_runs_over_its_invocation(self):
        started = self.begin("create-prd", "--args", "amend the roadmap")
        self.assertIsNone(started["ticket_id"])
        self.assertEqual(started["subject"], {"kind": "prompt",
                                              "text": "/acs:create-prd amend the roadmap"})
        self.assertFalse(started["in_workflow"])
        self.assertEqual(self.tickets(), [], "a product skill must not mint a ticket")
        self.assertEqual(self.pointer(), started["run_id"])

    def test_a_completed_product_skill_completes_its_run_and_frees_the_checkout(self):
        run_id = self.begin()["run_id"]
        out = self.finish("create-architecture", run_id, {
            "status": "completed", "summary": "doc set written, left uncommitted",
            "states": {"recommended_follow_ups": []}})
        self.assertEqual(out["run_status"], "completed")
        doc = lib.load_run(lib.run_dir(lib.repo_dir(self.ws, "acme-shop"), run_id))
        self.assertIsNone(doc["cursor"], "no workflow step is pending on a standalone run")
        self.assertEqual(doc["concluded_by"], "create-architecture")
        self.assertIsNone(self.pointer(), "a finished standalone run must not stay current")

    def test_a_failed_product_skill_fails_its_run(self):
        run_id = self.begin("create-prd")["run_id"]
        out = self.finish("create-prd", run_id, {"status": "failed",
                                                 "summary": "the user withdrew the scope"})
        self.assertEqual(out["run_status"], "failed")

    def test_an_interrupted_product_skill_keeps_its_run_for_the_resume(self):
        run_id = self.begin()["run_id"]
        out = self.finish("create-architecture", run_id,
                          {"status": "interrupted", "stop_reason": "session_end"})
        self.assertEqual(out["run_status"], "in_progress")
        self.assertEqual(self.pointer(), run_id)
        lib.release_lock(lib.run_dir(lib.repo_dir(self.ws, "acme-shop"), run_id))
        self.assertEqual(self.begin()["run_id"], run_id, "the resume reuses the live run")

    def test_a_second_handoff_still_names_the_product_skill(self):
        """Nothing in flight on the second call: a standalone run has no cursor
        for /acs:ship to follow, so the resume names the skill it interrupted."""
        run_id = self.begin()["run_id"]
        for _ in range(2):
            out = self.run_script("handoff.py", "--summary", "s", "--run", run_id)
            self.assertEqual(out.returncode, 0, out.stderr)
            self.assertEqual(json.loads(out.stdout)["continue_with"],
                             "/acs:create-architecture %s" % run_id)

    def test_the_standalone_run_records_a_baseline(self):
        run_id = self.begin()["run_id"]
        rdir = lib.run_dir(lib.repo_dir(self.ws, "acme-shop"), run_id)
        self.assertIsNotNone(lib.changes.load_baseline(rdir))

    def test_a_workflow_run_is_not_concluded_by_a_standalone_skill(self):
        """A standalone skill finishing inside a run that has recorded workflow
        steps leaves that run to the workflow."""
        ticket = self.new_ticket("Wishlist API", "task")
        self.walk_to(ticket, "analyze-requirements")
        doc = lib.conclude_standalone_run(self.rdir(ticket), "create-architecture", "completed")
        self.assertEqual(doc["status"], "in_progress")
        self.assertNotIn("concluded_by", doc)


if __name__ == "__main__":
    import unittest
    unittest.main()
