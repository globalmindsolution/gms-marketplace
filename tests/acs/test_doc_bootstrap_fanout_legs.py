"""Fixture-repo tests for /acs:create-docs's per-set primitives.

Drives the REAL hook CLIs (dispatch.py pre, acs.py step start --allocate
--doc-set, post-create-docs.py) against a throwaway consumer repo
(AcsWorkspaceCase): the one precondition every set shares (AC-2, now the
skill's own Start check -- ADR-0102), failure isolation between two sets'
delivery tickets (AC-3), and each set's own run.json as its resume record
(AC-4). The skill's own prose is not directly executable by
a unit test -- this proves the primitives it describes behave as claimed.

Run:  python3 -m unittest tests.acs.test_doc_bootstrap_fanout_legs -v
"""

import json
import os
import re
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRIPTS = os.path.join(REPO_ROOT, "plugins", "acs", "hooks", "scripts")
sys.path.insert(0, SCRIPTS)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
SKILL_PATH = os.path.join(REPO_ROOT, "plugins", "acs", "skills", "create-docs", "SKILL.md")

import acs_lib as lib  # noqa: E402
from acs_case import AcsWorkspaceCase  # noqa: E402


def _write_architecture_doc_set(repo):
    hld = os.path.join(repo, "docs", "architecture", "hld")
    os.makedirs(hld, exist_ok=True)
    with open(os.path.join(hld, "tech-stack.md"), "w") as fh:
        fh.write("# tech stack\n")


class GateIntegrityTest(AcsWorkspaceCase):
    """AC-2: the one precondition every set shares -- the architecture doc set.

    ADR-0102 moved it out of the pre-hook: no setting says where the set
    lives, so the hook cannot look for it. The skill finds it at Start and
    states the refusal itself; the hook passes either way."""

    def test_the_hook_no_longer_refuses_and_the_skill_start_does(self):
        result = self.pre("create-docs")
        self.assertEqual(result.returncode, 0, result.stderr)
        with open(SKILL_PATH, encoding="utf-8") as fh:
            body = re.sub(r"\s+", " ", fh.read())
        self.assertIn("no architecture doc set found (expected hld/tech-stack.md) — run "
                      "/acs:create-architecture first.", body)

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
        out = self.run_script("acs.py", "step", "start", "--step", "create-docs", "--allocate")
        self.assertEqual(out.returncode, 2)
        self.assertIn("--doc-set", out.stderr)

    def test_doc_set_is_only_for_create_docs(self):
        out = self.run_script("acs.py", "step", "start", "--step", "create-prd", "--allocate",
                              "--doc-set", "quality")
        self.assertEqual(out.returncode, 2)
        self.assertIn("--doc-set is only valid with --step create-docs", out.stderr)

    def test_the_ticket_names_its_set_and_title(self):
        out = self.run_script("acs.py", "step", "start", "--step", "create-docs",
                              "--doc-set", "operations", "--allocate")
        self.assertEqual(out.returncode, 0, out.stderr)
        ctx = json.loads(out.stdout)
        self.assertEqual(ctx["ticket"]["doc_set"], "operations")
        self.assertEqual(ctx["ticket"]["title"], lib.DOC_SET_TITLES["operations"])
        self.assertEqual(ctx["ticket"]["type"], "task")
        index = lib.read_json(lib.index_path(self.ws, "acme-shop"))
        self.assertEqual(index["tickets"][ctx["ticket_id"]]["doc_set"], "operations")

    def test_resume_by_ticket_reads_the_set_back(self):
        out = self.run_script("acs.py", "step", "start", "--step", "create-docs",
                              "--doc-set", "quality", "--allocate")
        ticket_id = json.loads(out.stdout)["ticket_id"]
        lib.release_lock(self.rdir(ticket_id))
        again = self.run_script("acs.py", "step", "start", "--step", "create-docs", "--ticket", ticket_id)
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
        out = self.run_script("acs.py", "step", "start", "--step", "create-docs",
                              "--doc-set", doc_set, "--allocate")
        self.assertEqual(out.returncode, 0, out.stderr)
        return json.loads(out.stdout)["ticket_id"]

    def test_failed_set_leaves_the_other_sets_run_status_and_ticket_untouched(self):
        self.post("create-docs", self.operations_ticket,
                  {"status": "failed", "stop_reason": "verifier cap reached at iteration 3"})

        q_ticket = lib.load_ticket(self.tdir(self.quality_ticket))
        self.assertEqual(q_ticket["status"], "in_progress")
        # `create-docs` is not a step of `ship.yaml`, so it records its
        # INVOCATION and takes no position in the run (I5 refuses one). Its
        # state file is what says the other set is still in flight.
        q_state = lib.load_step_state(self.rdir(self.quality_ticket), "create-docs",
                                      self.quality_ticket)
        self.assertEqual(q_state["invocations"][-1]["status"], "in_progress")

        self.post("create-docs", self.quality_ticket,
                  {"status": "completed",
                   "states": {"pr": {"number": 1, "url": "https://example.invalid/pull/1"}}})
        self.assertEqual(lib.load_ticket(self.tdir(self.quality_ticket))["status"], "in_review")
        self.assertEqual(lib.load_ticket(self.tdir(self.operations_ticket))["status"], "in_progress")

    def test_failed_set_leaves_the_other_sets_partition_and_lock_untouched(self):
        before_lock = lib.read_lock(self.rdir(self.quality_ticket))
        self.assertIsInstance(before_lock, dict)
        self.post("create-docs", self.operations_ticket, {"status": "failed"})
        self.assertEqual(before_lock, lib.read_lock(self.rdir(self.quality_ticket)))
        self.assertTrue(os.path.isdir(self.tdir(self.quality_ticket)))
        self.assertIsNone(lib.read_lock(self.rdir(self.operations_ticket)))


class LedgerTest(AcsWorkspaceCase):
    """AC-4: each set's own run.json records flow: "product" under
    the create-docs step, the ticket names the set, and re-running the
    eligibility predicate is the whole resume mechanism."""

    def setUp(self):
        super().setUp()
        _write_architecture_doc_set(self.repo)

    def _allocate(self, doc_set):
        out = self.run_script("acs.py", "step", "start", "--step", "create-docs",
                              "--doc-set", doc_set, "--allocate")
        self.assertEqual(out.returncode, 0, out.stderr)
        return json.loads(out.stdout)["ticket_id"]

    def test_each_set_writes_its_own_pipeline_state_under_the_create_docs_step(self):
        q = self._allocate("quality")
        o = self._allocate("operations")
        for ticket, doc_set in ((q, "quality"), (o, "operations")):
            run = lib.load_run(self.rdir(ticket))
            self.assertEqual(run["subject"], {"kind": "ticket", "ticket_id": ticket})
            self.assertEqual(run["workflow"], "ship")
            # `flow: ticket|product` is gone: the run names its WORKFLOW and
            # version, which says the same thing without a second vocabulary.
            self.assertNotIn("flow", run)
            self.assertEqual(run["steps"], {},
                             "a skill the workflow does not name takes no position")
            state = lib.load_step_state(self.rdir(ticket), "create-docs", ticket)
            self.assertEqual(len(state["invocations"]), 1)
            self.assertEqual(lib.load_ticket(self.tdir(ticket))["doc_set"], doc_set)

    def _present(self):
        """The coordinator's Start finding, reduced to the fixture's layout:
        a set is present when its sentinel sits at its default location.
        `fanout_batches` reads no disk itself (ADR-0102)."""
        return [name for name, sentinel in lib.DOC_BOOTSTRAP_SENTINEL.items()
                if os.path.isfile(os.path.join(self.repo, lib.DOC_SET_DEFAULT_DIR[name], sentinel))]

    def test_an_in_flight_set_is_not_re_offered(self):
        self._allocate("quality")
        tickets_index = lib.read_json(lib.index_path(self.ws, "acme-shop"))
        self.assertEqual(self._present(), [], "no set is on disk: only the ticket keeps it out")
        flat = [s for batch in lib.fanout_batches(tickets_index, present=self._present())
                for s in batch]
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
        tickets_index = lib.read_json(lib.index_path(self.ws, "acme-shop"))
        self.assertEqual(self._present(), ["quality"])
        flat = [s for batch in lib.fanout_batches(tickets_index, present=self._present())
                for s in batch]
        self.assertNotIn("quality", flat)
        self.assertIn("operations", flat)

    def test_both_sets_completed_retain_both_ledgers_and_index_entries(self):
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
        for ticket, pr in ((q, 1), (o, 2)):
            state = lib.load_step_state(self.rdir(ticket), "create-docs", ticket)
            self.assertEqual(state["invocations"][-1]["status"], "completed")
            self.assertEqual(state["states"]["pr"]["number"], pr)
        tickets_index = lib.read_json(lib.index_path(self.ws, "acme-shop"))
        self.assertEqual(tickets_index["tickets"][q]["status"], "in_review")
        self.assertEqual(tickets_index["tickets"][o]["status"], "in_review")


if __name__ == "__main__":
    import unittest
    unittest.main()
