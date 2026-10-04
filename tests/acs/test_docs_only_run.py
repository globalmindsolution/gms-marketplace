"""`/acs:create-pr --docs`: a ticketless docs-only change in a run of its own (ADR-0127).

Docs-only changes (PRD, architecture, LLD, ADRs) ship through /acs:create-pr
with no ticket and no code run. The start opens a standalone run, the way the
Audit and product skills' runs are opened; no ticket is resolved and the
review brake does not apply; the post-hook concludes the run and moves no
ticket. Without `--docs` create-pr is exactly the ticket step it always was.

Run:  python3 -m unittest tests.acs.test_docs_only_run -v
"""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from acs_case import AcsWorkspaceCase, lib  # noqa: E402


class DocsModePredicateTest(unittest.TestCase):

    def test_is_docs_mode(self):
        self.assertTrue(lib.is_docs_mode("create-pr", "--docs"))
        self.assertTrue(lib.is_docs_mode("create-pr", "docs/product --docs"))
        self.assertFalse(lib.is_docs_mode("create-pr", "SHOP-1"))
        self.assertFalse(lib.is_docs_mode("create-pr", "--docsy"))
        self.assertFalse(lib.is_docs_mode("create-pr", None))
        self.assertFalse(lib.is_docs_mode("code", "--docs"))

    def test_docs_mode_run(self):
        run = {"subject": {"kind": "prompt", "text": "/acs:create-pr --docs"}}
        self.assertTrue(lib.docs_mode_run("create-pr", run))
        self.assertFalse(lib.docs_mode_run("create-prd", run))
        self.assertFalse(lib.docs_mode_run("create-pr", {"subject": {
            "kind": "prompt", "text": "/acs:create-prd --docs"}}))
        self.assertFalse(lib.docs_mode_run("create-pr", {"subject": {
            "kind": "ticket", "ticket_id": "SHOP-1"}}))
        self.assertFalse(lib.docs_mode_run("create-pr", None))


class ArgsValueBindingTest(unittest.TestCase):
    """`--args "$ARGUMENTS"` must survive arguments that start with a dash."""

    def test_binding(self):
        from acs_case import SCRIPTS
        sys.path.insert(0, SCRIPTS)
        import acs
        self.assertEqual(acs._bind_args_values(["step", "start", "--args", "--docs", "--run", "R"]),
                         ["step", "start", "--args=--docs", "--run", "R"])
        self.assertEqual(acs._bind_args_values(["--args"]), ["--args"])


class DocsOnlyRunTest(AcsWorkspaceCase):

    def setUp(self):
        super().setUp()
        # A ticket run is current, and its review FAILED: the brake that
        # holds a ticket's create-pr must not hold a docs-only one.
        self.ticket = self.new_ticket("Wishlist API", "task")
        rdir = self.ensure_run(self.ticket)
        lib.save_state(rdir, "review-code", dict(
            lib.empty_state("review-code", self.ticket),
            states={"verifier_passed": False}))

    def start_docs(self, *extra):
        out = self.run_script("acs.py", "step", "start", "--step", "create-pr",
                              "--args", "--docs", *extra)
        self.assertEqual(out.returncode, 0, out.stderr)
        return json.loads(out.stdout)

    def pointer(self):
        return lib.sessions.current_run_id(lib.repo_dir(self.ws, "acme-shop"),
                                           lib.checkout_id(self.repo))

    def test_the_ticket_step_is_still_braked(self):
        out = self.run_script("acs.py", "step", "start", "--step", "create-pr",
                              "--run", self.ticket)
        self.assertEqual(out.returncode, 2)
        self.assertIn("did not pass", out.stderr)

    def test_the_pre_hook_lets_a_docs_only_create_pr_through_and_writes_nothing(self):
        before = lib.load_run(self.rdir(self.ticket))
        out = self.pre("create-pr", "--docs")
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(lib.load_run(self.rdir(self.ticket)), before)
        self.assertEqual(self.pointer(), self.ticket)

    def test_start_opens_a_ticketless_run_in_docs_mode(self):
        out = self.start_docs()
        self.assertEqual(out["mode"], "docs")
        self.assertIsNone(out["ticket_id"])
        self.assertFalse(out["in_workflow"])
        self.assertNotEqual(out["run_id"], self.ticket)
        self.assertEqual(out["subject"], {"kind": "prompt", "text": "/acs:create-pr --docs"})
        self.assertEqual(self.pointer(), out["run_id"])
        self.assertEqual(lib.load_run(self.rdir(self.ticket))["steps"], {},
                         "the ticket's run is untouched")
        rdir = lib.run_dir(lib.repo_dir(self.ws, "acme-shop"), out["run_id"])
        self.assertIsNotNone(lib.changes.load_baseline(rdir))

    def test_a_ticket_create_pr_reports_ticket_mode(self):
        lib.save_state(self.rdir(self.ticket), "review-code", dict(
            lib.empty_state("review-code", self.ticket), states={"verifier_passed": True}))
        out = self.run_script("acs.py", "step", "start", "--step", "create-pr",
                              "--run", self.ticket)
        self.assertEqual(out.returncode, 0, out.stderr)
        doc = json.loads(out.stdout)
        self.assertEqual((doc["mode"], doc["in_workflow"]), ("ticket", True))

    def test_the_post_hook_concludes_the_run_and_moves_no_ticket(self):
        run_id = self.start_docs()["run_id"]
        out = self.post("create-pr", run_id, {
            "status": "completed", "summary": "docs PR opened",
            "states": {"pr": {"number": 9, "url": "https://example.invalid/pull/9"}}})
        self.assertEqual(out.returncode, 0, out.stderr)
        doc = json.loads(out.stdout)
        self.assertEqual(doc["run_status"], "completed")
        run = lib.load_run(lib.run_dir(lib.repo_dir(self.ws, "acme-shop"), run_id))
        self.assertEqual(run["concluded_by"], "create-pr")
        self.assertEqual(run["steps"], {})
        self.assertIsNone(self.pointer())
        self.assertEqual(lib.load_ticket(self.tdir(self.ticket))["status"], "open")

    def test_a_resumed_docs_start_reuses_its_run_and_step_finish_needs_no_ledger(self):
        run_id = self.start_docs()["run_id"]
        self.assertEqual(self.start_docs()["run_id"], run_id)
        out = self.run_script("acs.py", "step", "finish", "--step", "create-pr",
                              "--run", run_id, "--status", "interrupted",
                              "--stop-reason", "session_end")
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertFalse(json.loads(out.stdout)["in_workflow"])
        lib.release_lock(lib.run_dir(lib.repo_dir(self.ws, "acme-shop"), run_id))
        self.assertEqual(self.start_docs()["run_id"], run_id)

    def test_another_ticketless_skills_run_is_never_adopted(self):
        prd = self.run_script("acs.py", "step", "start", "--step", "create-prd")
        self.assertEqual(prd.returncode, 0, prd.stderr)
        prd_run = json.loads(prd.stdout)["run_id"]
        self.assertNotEqual(self.start_docs()["run_id"], prd_run)


if __name__ == "__main__":
    unittest.main()
