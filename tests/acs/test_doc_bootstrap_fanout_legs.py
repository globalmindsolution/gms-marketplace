"""Fixture-repo tests for /acs:create-docs's per-set primitives.

Drives the REAL hook CLIs (dispatch.py pre, skill-start.py --allocate
--doc-set, post-create-docs.py) against a throwaway consumer repo
(AcsWorkspaceCase): one gate for every set (AC-2), failure isolation between
two sets' delivery tickets (AC-3), and each set's own pipeline-state.json as
its resume record (AC-4). The skill's own prose is not directly executable by
a unit test -- this proves the primitives it describes behave as claimed.

Run:  python3 -m unittest tests.acs.test_doc_bootstrap_fanout_legs -v
"""

import json
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRIPTS = os.path.join(REPO_ROOT, "plugins", "acs", "hooks", "scripts")
sys.path.insert(0, SCRIPTS)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import acs_lib as lib  # noqa: E402
from acs_case import AcsWorkspaceCase  # noqa: E402


def _write_architecture_doc_set(repo):
    hld = os.path.join(repo, "docs", "architecture", "hld")
    os.makedirs(hld, exist_ok=True)
    with open(os.path.join(hld, "tech-stack.md"), "w") as fh:
        fh.write("# tech stack\n")


class GateIntegrityTest(AcsWorkspaceCase):
    """AC-2: the one gate every set shares -- the architecture doc set."""

    def test_gate_blocks_without_architecture_doc_set(self):
        result = self.pre("create-docs")
        self.assertEqual(result.returncode, 2)
        self.assertIn("create-architecture", result.stderr)

    def test_gate_passes_with_architecture_doc_set(self):
        _write_architecture_doc_set(self.repo)
        result = self.pre("create-docs")
        self.assertEqual(result.returncode, 0, result.stderr)


class AllocationTest(AcsWorkspaceCase):
    """skill-start mints one delivery ticket per set, titled from DOC_SETS
    and carrying the set, and refuses a set-less allocation."""

    def setUp(self):
        super().setUp()
        _write_architecture_doc_set(self.repo)

    def test_allocation_needs_a_doc_set(self):
        out = self.run_script("skill-start.py", "--skill", "create-docs", "--allocate")
        self.assertEqual(out.returncode, 2)
        self.assertIn("--doc-set", out.stderr)

    def test_doc_set_is_only_for_create_docs(self):
        out = self.run_script("skill-start.py", "--skill", "create-prd", "--allocate",
                              "--doc-set", "quality")
        self.assertEqual(out.returncode, 2)
        self.assertIn("--doc-set is only valid with --skill create-docs", out.stderr)

    def test_the_ticket_names_its_set_and_title(self):
        out = self.run_script("skill-start.py", "--skill", "create-docs",
                              "--doc-set", "operations", "--allocate")
        self.assertEqual(out.returncode, 0, out.stderr)
        ctx = json.loads(out.stdout)
        self.assertEqual(ctx["ticket"]["doc_set"], "operations")
        self.assertEqual(ctx["ticket"]["title"], lib.DOC_SET_TITLES["operations"])
        self.assertEqual(ctx["ticket"]["type"], "task")
        index = lib.read_json(lib.index_path(self.ws, "acme-shop"))
        self.assertEqual(index["tickets"][ctx["ticket_id"]]["doc_set"], "operations")

    def test_resume_by_ticket_reads_the_set_back(self):
        out = self.run_script("skill-start.py", "--skill", "create-docs",
                              "--doc-set", "quality", "--allocate")
        ticket_id = json.loads(out.stdout)["ticket_id"]
        lib.release_lock(self.tdir(ticket_id))
        again = self.run_script("skill-start.py", "--skill", "create-docs", "--ticket", ticket_id)
        self.assertEqual(again.returncode, 0, again.stderr)
        self.assertEqual(json.loads(again.stdout)["ticket"]["doc_set"], "quality")


class SetIsolationTest(AcsWorkspaceCase):
    """AC-3: a failed set leaves the other set's run status, ticket, partition,
    and lock untouched -- no shared failure state between them."""

    def setUp(self):
        super().setUp()
        _write_architecture_doc_set(self.repo)
        self.assertEqual(self.pre("create-docs").returncode, 0)
        self.quality_ticket = self._allocate("quality")
        self.operations_ticket = self._allocate("operations")

    def _allocate(self, doc_set):
        out = self.run_script("skill-start.py", "--skill", "create-docs",
                              "--doc-set", doc_set, "--allocate")
        self.assertEqual(out.returncode, 0, out.stderr)
        return json.loads(out.stdout)["ticket_id"]

    def test_failed_set_leaves_the_other_sets_run_status_and_ticket_untouched(self):
        self.post("create-docs", self.operations_ticket,
                  {"status": "failed", "stop_reason": "verifier cap reached at iteration 3"})

        q_ticket = lib.load_ticket(self.tdir(self.quality_ticket))
        self.assertEqual(q_ticket["status"], "in_progress")
        q_pipeline = lib.load_pipeline(self.tdir(self.quality_ticket), self.quality_ticket)
        self.assertEqual(q_pipeline["steps"]["create-docs"]["status"], "in_progress")

        self.post("create-docs", self.quality_ticket,
                  {"status": "completed",
                   "states": {"pr": {"number": 1, "url": "https://example.invalid/pull/1"}}})
        self.assertEqual(lib.load_ticket(self.tdir(self.quality_ticket))["status"], "in_review")
        self.assertEqual(lib.load_ticket(self.tdir(self.operations_ticket))["status"], "in_progress")

    def test_failed_set_leaves_the_other_sets_partition_and_lock_untouched(self):
        before_lock = lib.read_lock(self.tdir(self.quality_ticket))
        self.assertIsInstance(before_lock, dict)
        self.post("create-docs", self.operations_ticket, {"status": "failed"})
        self.assertEqual(before_lock, lib.read_lock(self.tdir(self.quality_ticket)))
        self.assertTrue(os.path.isdir(self.tdir(self.quality_ticket)))
        self.assertIsNone(lib.read_lock(self.tdir(self.operations_ticket)))


class LedgerTest(AcsWorkspaceCase):
    """AC-4: each set's own pipeline-state.json records flow: "product" under
    the create-docs step, the ticket names the set, and re-running the
    eligibility predicate is the whole resume mechanism."""

    def setUp(self):
        super().setUp()
        _write_architecture_doc_set(self.repo)

    def _allocate(self, doc_set):
        out = self.run_script("skill-start.py", "--skill", "create-docs",
                              "--doc-set", doc_set, "--allocate")
        self.assertEqual(out.returncode, 0, out.stderr)
        return json.loads(out.stdout)["ticket_id"]

    def test_each_set_writes_its_own_pipeline_state_under_the_create_docs_step(self):
        q = self._allocate("quality")
        o = self._allocate("operations")
        for ticket, doc_set in ((q, "quality"), (o, "operations")):
            pipeline = lib.load_pipeline(self.tdir(ticket), ticket)
            self.assertEqual(pipeline["flow"], "product")
            self.assertEqual(list(pipeline["steps"]), ["create-docs"])
            self.assertEqual(lib.load_ticket(self.tdir(ticket))["doc_set"], doc_set)

    def test_an_in_flight_set_is_not_re_offered(self):
        self._allocate("quality")
        settings, _ = lib.load_settings(self.repo)
        tickets_index = lib.read_json(lib.index_path(self.ws, "acme-shop"))
        flat = [s for batch in lib.fanout_batches(settings, tickets_index, self.repo) for s in batch]
        self.assertNotIn("quality", flat)
        self.assertIn("operations", flat)

    def test_resume_after_one_set_shipped_returns_only_the_unshipped(self):
        q = self._allocate("quality")
        quality_dir = os.path.join(self.repo, "docs", "quality")
        os.makedirs(quality_dir, exist_ok=True)
        with open(os.path.join(quality_dir, "test-strategy.md"), "w") as fh:
            fh.write("# strategy\n")
        self.post("create-docs", q,
                  {"status": "completed",
                   "states": {"pr": {"number": 1, "url": "https://example.invalid/pull/1"}}})
        settings, _ = lib.load_settings(self.repo)
        tickets_index = lib.read_json(lib.index_path(self.ws, "acme-shop"))
        flat = [s for batch in lib.fanout_batches(settings, tickets_index, self.repo) for s in batch]
        self.assertNotIn("quality", flat)
        self.assertIn("operations", flat)

    def test_both_sets_completed_retain_both_ledgers_index_and_metrics_entries(self):
        q = self._allocate("quality")
        o = self._allocate("operations")
        self.assertEqual(self.post("create-docs", q,
                          {"status": "completed",
                           "states": {"pr": {"number": 1, "url": "https://example.invalid/pull/1"}}}
                          ).returncode, 0)
        self.assertEqual(self.post("create-docs", o,
                          {"status": "completed",
                           "states": {"pr": {"number": 2, "url": "https://example.invalid/pull/2"}}}
                          ).returncode, 0)
        for ticket in (q, o):
            pipeline = lib.load_pipeline(self.tdir(ticket), ticket)
            self.assertEqual(pipeline["flow"], "product")
            self.assertEqual(pipeline["steps"]["create-docs"]["status"], "completed")
        tickets_index = lib.read_json(lib.index_path(self.ws, "acme-shop"))
        self.assertEqual(tickets_index["tickets"][q]["status"], "in_review")
        self.assertEqual(tickets_index["tickets"][o]["status"], "in_review")
        metrics = lib.read_json(lib.metrics_path(self.ws, "acme-shop"))
        self.assertEqual(metrics["totals"]["runs"], 2)
        self.assertEqual(metrics["prs"]["created"], 2)
        self.assertEqual(metrics["prs"]["created_pr_numbers"], [1, 2])


if __name__ == "__main__":
    import unittest
    unittest.main()
