"""MAR-1 T-B -- fixture-repo tests for the doc-bootstrap fan-out legs.

Drives the REAL hook CLIs (dispatch.py pre, skill-start.py --allocate,
post-create-quality.py / post-create-operations.py) against a throwaway
consumer repo (AcsWorkspaceCase), exercising AC-2 (shared gate integrity),
AC-3 (failure isolation), and AC-4 (each leg's own pipeline-state.json is
the resume record) at the deterministic layer. This module does not invoke
/acs:create-docs itself (an unhooked skill's own prose is not directly
executable by a unit test) -- it proves the primitives the umbrella's SKILL.md
prose describes actually behave the way that prose claims.

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
    """AC-2: each leg's own pre-hook gate fires unchanged by the fan-out --
    both legs share exactly one precondition, the architecture doc set."""

    def test_both_legs_gate_blocks_without_architecture_doc_set(self):
        for skill in ("create-quality", "create-operations"):
            with self.subTest(skill=skill):
                result = self.pre(skill)
                self.assertEqual(result.returncode, 2)
                self.assertIn("create-architecture", result.stderr)

    def test_both_legs_gate_passes_with_architecture_doc_set(self):
        _write_architecture_doc_set(self.repo)
        for skill in ("create-quality", "create-operations"):
            with self.subTest(skill=skill):
                result = self.pre(skill)
                self.assertEqual(result.returncode, 0, result.stderr)


class LegIsolationTest(AcsWorkspaceCase):
    """AC-3: a failed leg leaves the other leg's run status, ticket, partition,
    and lock untouched -- no shared failure state between them."""

    def setUp(self):
        super().setUp()
        _write_architecture_doc_set(self.repo)
        self.assertEqual(self.pre("create-quality").returncode, 0)
        self.assertEqual(self.pre("create-operations").returncode, 0)
        self.quality_ticket = self._allocate("create-quality")
        self.operations_ticket = self._allocate("create-operations")

    def _allocate(self, skill):
        out = self.run_script("skill-start.py", "--skill", skill, "--allocate")
        self.assertEqual(out.returncode, 0, out.stderr)
        return json.loads(out.stdout)["ticket_id"]

    def test_failed_leg_leaves_other_legs_run_status_and_ticket_untouched(self):
        # leg O fails at the verifier cap (iteration 3, findings remaining).
        self.post("create-operations", self.operations_ticket,
                  {"status": "failed", "stop_reason": "verifier cap reached at iteration 3"})

        # leg Q is entirely untouched by leg O's finalize.
        q_ticket = lib.load_ticket(self.tdir(self.quality_ticket))
        self.assertEqual(q_ticket["status"], "in_progress")
        q_pipeline = lib.load_pipeline(self.tdir(self.quality_ticket), self.quality_ticket)
        self.assertEqual(q_pipeline["steps"]["create-quality"]["status"], "in_progress")
        self.assertNotIn("create-operations", q_pipeline["steps"])

        # leg Q can still complete normally afterward -- no shared failure state.
        self.post("create-quality", self.quality_ticket,
                  {"status": "completed",
                   "states": {"pr": {"number": 1, "url": "https://example.invalid/pull/1"}}})
        q_ticket = lib.load_ticket(self.tdir(self.quality_ticket))
        self.assertEqual(q_ticket["status"], "in_review")

        o_ticket = lib.load_ticket(self.tdir(self.operations_ticket))
        self.assertEqual(o_ticket["status"], "in_progress")

    def test_failed_leg_leaves_other_legs_partition_and_lock_untouched(self):
        before_lock = lib.read_lock(self.tdir(self.quality_ticket))
        self.assertIsInstance(before_lock, dict)

        self.post("create-operations", self.operations_ticket, {"status": "failed"})

        after_lock = lib.read_lock(self.tdir(self.quality_ticket))
        self.assertEqual(before_lock, after_lock, "leg O's failure must not touch leg Q's lock")
        self.assertTrue(os.path.isdir(self.tdir(self.quality_ticket)),
                        "leg Q's partition must survive leg O's failure")

        # leg O's own post-hook releases only ITS OWN lock.
        self.assertIsNone(lib.read_lock(self.tdir(self.operations_ticket)))


class LedgerTest(AcsWorkspaceCase):
    """AC-4: each leg's own pipeline-state.json records flow: "product" under
    its own step name; there is no shared batch ledger, and a re-run of the
    D4.1 eligibility predicate is the umbrella's whole resume mechanism."""

    def setUp(self):
        super().setUp()
        _write_architecture_doc_set(self.repo)

    def _allocate(self, skill):
        out = self.run_script("skill-start.py", "--skill", skill, "--allocate")
        self.assertEqual(out.returncode, 0, out.stderr)
        return json.loads(out.stdout)["ticket_id"]

    def test_each_leg_writes_its_own_pipeline_state_with_product_flow_and_own_step_name(self):
        q = self._allocate("create-quality")
        o = self._allocate("create-operations")

        q_pipeline = lib.load_pipeline(self.tdir(q), q)
        o_pipeline = lib.load_pipeline(self.tdir(o), o)

        self.assertEqual(q_pipeline["flow"], "product")
        self.assertEqual(o_pipeline["flow"], "product")
        self.assertIn("create-quality", q_pipeline["steps"])
        self.assertIn("create-operations", o_pipeline["steps"])
        self.assertNotIn("create-operations", q_pipeline["steps"])
        self.assertNotIn("create-quality", o_pipeline["steps"])

    def test_resume_after_one_leg_completed_returns_only_the_incomplete_leg(self):
        q = self._allocate("create-quality")

        # leg Q ships: its doc set lands on disk (as it would once the PR
        # merges to the default branch) -- D4.2(a)'s sentinel predicate is
        # what fanout_batches actually consults, independent of ticket status.
        quality_dir = os.path.join(self.repo, "docs", "quality")
        os.makedirs(quality_dir, exist_ok=True)
        with open(os.path.join(quality_dir, "test-strategy.md"), "w") as fh:
            fh.write("# strategy\n")
        self.post("create-quality", q,
                  {"status": "completed",
                   "states": {"pr": {"number": 1, "url": "https://example.invalid/pull/1"}}})

        # leg O was never even started -- it is the sole remaining/incomplete
        # member of the v1 pair (D7-A: {create-quality, create-operations}
        # only -- other doc-bootstrap skills' eligibility is out of scope here).
        settings, _ = lib.load_settings(self.repo)
        tickets_index = lib.read_json(lib.index_path(self.ws, "acme-shop"))
        batches = lib.fanout_batches(settings, tickets_index, self.repo)
        flat = [skill for batch in batches for skill in batch]
        v1_pair = {"create-quality", "create-operations"}

        self.assertEqual([s for s in flat if s in v1_pair], ["create-operations"])
        self.assertNotIn("create-quality", flat)

    def test_both_legs_completed_retain_both_pipeline_states_index_and_metrics_entries(self):
        """Finding 3: drive BOTH legs to completed and confirm every ledger
        surface (both pipeline-state.json files, the shared tickets-index.json,
        and metrics.json) retains both entries -- no last-write-wins loss."""
        q = self._allocate("create-quality")
        o = self._allocate("create-operations")

        self.assertEqual(self.post("create-quality", q,
                          {"status": "completed",
                           "states": {"pr": {"number": 1, "url": "https://example.invalid/pull/1"}}}
                          ).returncode, 0)
        self.assertEqual(self.post("create-operations", o,
                          {"status": "completed",
                           "states": {"pr": {"number": 2, "url": "https://example.invalid/pull/2"}}}
                          ).returncode, 0)

        q_pipeline = lib.load_pipeline(self.tdir(q), q)
        o_pipeline = lib.load_pipeline(self.tdir(o), o)
        self.assertEqual(q_pipeline["flow"], "product")
        self.assertEqual(o_pipeline["flow"], "product")
        self.assertEqual(q_pipeline["steps"]["create-quality"]["status"], "completed")
        self.assertEqual(o_pipeline["steps"]["create-operations"]["status"], "completed")
        self.assertNotIn("create-operations", q_pipeline["steps"])
        self.assertNotIn("create-quality", o_pipeline["steps"])

        tickets_index = lib.read_json(lib.index_path(self.ws, "acme-shop"))
        self.assertEqual(tickets_index["tickets"][q]["status"], "in_review")
        self.assertEqual(tickets_index["tickets"][o]["status"], "in_review")

        metrics = lib.read_json(lib.metrics_path(self.ws, "acme-shop"))
        self.assertEqual(metrics["totals"]["runs"], 2)
        self.assertEqual(metrics["prs"]["created"], 2)
        self.assertEqual(metrics["prs"]["created_pr_numbers"], [1, 2])
        self.assertEqual(metrics["tickets"]["total"], 2)
        self.assertEqual(metrics["tickets"]["by_status"]["in_review"], 2)


if __name__ == "__main__":
    import unittest
    unittest.main()
