"""Behavior tests for new-ticket.py's error/refusal paths.

Originating ticket: MAR-169. Before this module new-ticket.py's GateError-from-
build_context refusal, its --external validation (both the malformed-input
refusal and the successful mapping), and its parent-ticket refusals (missing,
archived, non-epic) were exercised by no test. Fixtures mint tickets
in-process via acs_case.lib (never through new-ticket.py's own subprocess) --
this seam needs no subprocess at all.
"""

import json
import os
import shutil
import sys
import tempfile
import unittest

TESTS_ACS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TESTS_ACS)

import acs_case  # noqa: E402

MODULE_FILENAME = "new-ticket.py"
REPO_ID = "acme-shop"


def _mint(ws, tid, ttype="task", status="open"):
    """Write a valid active-partition ticket.json + index entry -- no subprocess."""
    tdir = acs_case.lib.ticket_dir(ws, REPO_ID, tid)
    os.makedirs(tdir, exist_ok=True)
    ticket = acs_case.lib.new_ticket_doc(tid, tid, ttype, status=status)
    acs_case.lib.save_ticket(tdir, ticket)
    acs_case.lib.update_index(ws, REPO_ID, ticket, archived=False)
    return tdir


def _mint_archived(ws, tid, ttype="epic"):
    """Write a valid ticket.json under archive/ only -- no active partition."""
    tdir = os.path.join(acs_case.lib.archive_dir(ws, REPO_ID), tid)
    os.makedirs(tdir, exist_ok=True)
    ticket = acs_case.lib.new_ticket_doc(tid, tid, ttype, status="done")
    acs_case.lib.save_ticket(tdir, ticket)
    return tdir


def _partition_entries(ws):
    """Snapshot of this repo's workspace partition dir -- proves "nothing minted"."""
    rdir = acs_case.lib.repo_dir(ws, REPO_ID)
    return set(os.listdir(rdir)) if os.path.isdir(rdir) else set()


class TestBuildContextGateError(unittest.TestCase):
    """62-64: build_context's GateError (cwd outside any git repo) exits 2."""

    def test_uninitialized_repo_exits_2(self):
        mod = acs_case.load_module(MODULE_FILENAME)
        nongit = tempfile.mkdtemp(prefix="acs-newticket-nongit-")
        self.addCleanup(shutil.rmtree, nongit, True)
        with acs_case.pushd(nongit):
            code, out, err = acs_case.run_main(
                mod, ["--title", "X", "--type", "task"])
        self.assertEqual(code, 2)
        self.assertEqual(out, "")
        self.assertTrue(
            err.startswith("acs new-ticket: acs requires a git repository;"), err)


class TestExternalMapping(acs_case.AcsWorkspaceCase):
    """67-73: --external parsing -- the valid mapping and the malformed refusal."""

    def test_external_mapping_is_recorded_on_the_ticket(self):
        mod = acs_case.load_module(MODULE_FILENAME)
        with acs_case.pushd(self.repo):
            code, out, err = acs_case.run_main(
                mod, ["--title", "X", "--type", "task", "--external", "github:456"])
        self.assertEqual(code, 0, err)
        payload = json.loads(out)
        ticket = acs_case.lib.load_ticket(
            acs_case.lib.ticket_dir(self.ws, REPO_ID, payload["ticket_id"]))
        self.assertEqual(ticket["external"], {"provider": "github", "key": "456"})

    def test_malformed_external_exits_2_and_mints_nothing(self):
        before = _partition_entries(self.ws)
        mod = acs_case.load_module(MODULE_FILENAME)
        with acs_case.pushd(self.repo):
            code, out, err = acs_case.run_main(
                mod, ["--title", "X", "--type", "task", "--external", "github"])
        self.assertEqual(code, 2)
        self.assertEqual(err, "acs new-ticket: --external must be <provider>:<key>\n")
        self.assertEqual(_partition_entries(self.ws), before)


class TestReconciliationRefusal(acs_case.AcsWorkspaceCase):
    """AC-1, AC-6 (CLI half): allocate_ticket_id's fail-closed reconciliation
    gate surfaces as an exit-2 refusal with actionable stderr, and mints
    nothing (MAR-402)."""

    def test_first_allocation_in_an_unreconciled_workspace_exits_2(self):
        self.unreconcile()
        before = _partition_entries(self.ws)
        mod = acs_case.load_module(MODULE_FILENAME)
        with acs_case.pushd(self.repo):
            code, out, err = acs_case.run_main(
                mod, ["--title", "X", "--type", "task"])
        self.assertEqual(code, 2)
        self.assertEqual(out, "")
        self.assertTrue(err.startswith("acs new-ticket: "))
        self.assertIn("blocked", err)
        self.assertIn("SHOP", err)
        self.assertIn("new-ticket.py --seed-next <n>", err)
        self.assertEqual(_partition_entries(self.ws), before)


class TestSeedNext(acs_case.AcsWorkspaceCase):
    """AC-5: --seed-next <n> confirms/repairs the reconciliation floor on
    new-ticket.py (MAR-402)."""

    def test_seed_next_confirms_the_floor_and_mints_that_id(self):
        self.unreconcile()
        mod = acs_case.load_module(MODULE_FILENAME)
        with acs_case.pushd(self.repo):
            code, out, err = acs_case.run_main(
                mod, ["--title", "X", "--type", "task", "--seed-next", "5"])
        self.assertEqual(code, 0, err)
        payload = json.loads(out)
        self.assertEqual(payload["ticket_id"], "SHOP-5")

    def test_seed_next_records_explicit_user_provenance(self):
        self.unreconcile()
        mod = acs_case.load_module(MODULE_FILENAME)
        with acs_case.pushd(self.repo):
            code, out, err = acs_case.run_main(
                mod, ["--title", "X", "--type", "task", "--seed-next", "5"])
        self.assertEqual(code, 0, err)
        counters = acs_case.lib.read_json(self._counters_path())
        self.assertEqual(counters["seed_source"], "explicit-user")
        self.assertTrue(counters["reconciled"])

    def test_seed_next_repairs_a_wrong_existing_reconciliation(self):
        # setUp seeds a reconciled next=1; simulate a stuck/wrong value and
        # repair it downward -- no workspace state is deleted to do so.
        self.seed_counters(next_n=100)
        mod = acs_case.load_module(MODULE_FILENAME)
        with acs_case.pushd(self.repo):
            code, out, err = acs_case.run_main(
                mod, ["--title", "X", "--type", "task", "--seed-next", "3"])
        self.assertEqual(code, 0, err)
        payload = json.loads(out)
        self.assertEqual(payload["ticket_id"], "SHOP-3")
        self.assertIn("--seed-next", err)
        self.assertIn("100", err)
        self.assertTrue(os.path.exists(self._counters_path()))
        self.assertTrue(os.path.isdir(
            acs_case.lib.ticket_dir(self.ws, REPO_ID, "SHOP-3")))

    def test_seed_next_below_one_exits_2(self):
        before = _partition_entries(self.ws)
        mod = acs_case.load_module(MODULE_FILENAME)
        with acs_case.pushd(self.repo):
            code, out, err = acs_case.run_main(
                mod, ["--title", "X", "--type", "task", "--seed-next", "0"])
        self.assertEqual(code, 2)
        self.assertEqual(out, "")
        self.assertEqual(_partition_entries(self.ws), before)

    def test_seed_next_non_integer_exits_2(self):
        before = _partition_entries(self.ws)
        mod = acs_case.load_module(MODULE_FILENAME)
        with acs_case.pushd(self.repo):
            code, out, err = acs_case.run_main(
                mod, ["--title", "X", "--type", "task", "--seed-next", "abc"])
        self.assertEqual(code, 2)
        self.assertEqual(_partition_entries(self.ws), before)


class TestParentRefusals(acs_case.AcsWorkspaceCase):
    """78-85: unknown / archived / non-epic parent refusals."""

    def test_unknown_parent_exits_2_and_mints_nothing(self):
        before = _partition_entries(self.ws)
        mod = acs_case.load_module(MODULE_FILENAME)
        with acs_case.pushd(self.repo):
            code, out, err = acs_case.run_main(
                mod, ["--title", "X", "--type", "task", "--parent", "SHOP-999"])
        self.assertEqual(code, 2)
        self.assertEqual(
            err, "acs new-ticket: parent ticket SHOP-999 not found (or archived)\n")
        self.assertEqual(_partition_entries(self.ws), before)

    def test_archived_parent_is_refused(self):
        _mint_archived(self.ws, "SHOP-600", ttype="epic")
        before = _partition_entries(self.ws)
        mod = acs_case.load_module(MODULE_FILENAME)
        with acs_case.pushd(self.repo):
            code, out, err = acs_case.run_main(
                mod, ["--title", "X", "--type", "task", "--parent", "SHOP-600"])
        self.assertEqual(code, 2)
        self.assertEqual(
            err, "acs new-ticket: parent ticket SHOP-600 not found (or archived)\n")
        self.assertEqual(_partition_entries(self.ws), before)

    def test_non_epic_parent_exits_2_and_mints_nothing(self):
        _mint(self.ws, "SHOP-8", ttype="task")
        before = _partition_entries(self.ws)
        mod = acs_case.load_module(MODULE_FILENAME)
        with acs_case.pushd(self.repo):
            code, out, err = acs_case.run_main(
                mod, ["--title", "X", "--type", "task", "--parent", "SHOP-8"])
        self.assertEqual(code, 2)
        self.assertEqual(
            err, "acs new-ticket: parent SHOP-8 is a task, not an epic\n")
        self.assertEqual(_partition_entries(self.ws), before)


class TestFeaturesInheritance(acs_case.AcsWorkspaceCase):
    """ADR-0138: a child minted under an epic traces to the epic's PRD
    features unless the caller narrows them -- /acs:breakdown-ticket proposes
    children that inherit them, and a child that silently traced to nothing
    would drop out of every feature's LLD and doc-sync."""

    def mint(self, *args):
        out = self.run_script("new-ticket.py", *args)
        self.assertEqual(out.returncode, 0, out.stderr)
        payload = json.loads(out.stdout)
        return payload, acs_case.lib.load_ticket(self.tdir(payload["ticket_id"]))

    def epic(self, features="wishlist,checkout"):
        args = ["--title", "Wishlist", "--type", "epic"]
        if features is not None:
            args += ["--features", features]
        payload, _ticket = self.mint(*args)
        return payload["ticket_id"]

    def test_a_child_inherits_the_parents_features_by_default(self):
        epic = self.epic()
        payload, child = self.mint("--title", "API", "--type", "story", "--parent", epic)
        self.assertEqual(child["features"], ["wishlist", "checkout"])
        self.assertEqual(payload["features"], ["wishlist", "checkout"])
        self.assertTrue(payload["features_inherited"])
        index = acs_case.lib.read_json(acs_case.lib.index_path(self.ws, REPO_ID))
        self.assertEqual(index["tickets"][payload["ticket_id"]]["features"],
                         ["wishlist", "checkout"])

    def test_an_explicit_features_overrides_the_parents(self):
        epic = self.epic()
        payload, child = self.mint("--title", "API", "--type", "task", "--parent", epic,
                                   "--features", "checkout")
        self.assertEqual(child["features"], ["checkout"])
        self.assertFalse(payload["features_inherited"])

    def test_an_explicit_empty_features_means_none(self):
        epic = self.epic()
        payload, child = self.mint("--title", "API", "--type", "task", "--parent", epic,
                                   "--features", "")
        self.assertNotIn("features", child)
        self.assertEqual(payload["features"], [])
        self.assertFalse(payload["features_inherited"])

    def test_a_parent_without_features_gives_none(self):
        epic = self.epic(features=None)
        payload, child = self.mint("--title", "API", "--type", "task", "--parent", epic)
        self.assertNotIn("features", child)
        self.assertFalse(payload["features_inherited"])

    def test_no_parent_inherits_nothing(self):
        payload, child = self.mint("--title", "API", "--type", "task")
        self.assertNotIn("features", child)
        self.assertEqual(payload["features"], [])
        self.assertFalse(payload["features_inherited"])

    def test_the_parent_keeps_its_own_features(self):
        epic = self.epic()
        self.mint("--title", "API", "--type", "task", "--parent", epic, "--features", "x")
        self.assertEqual(acs_case.lib.load_ticket(self.tdir(epic))["features"],
                         ["wishlist", "checkout"])

    def test_a_story_parent_is_still_refused_until_it_is_converted(self):
        """The split conversion (ticket save type epic) comes first; --parent
        itself never accepts a story or task."""
        _mint(self.ws, "SHOP-40", ttype="story")
        out = self.run_script("new-ticket.py", "--title", "X", "--type", "task",
                              "--parent", "SHOP-40")
        self.assertEqual(out.returncode, 2)
        self.assertIn("is a story, not an epic", out.stderr)


if __name__ == "__main__":
    unittest.main()
