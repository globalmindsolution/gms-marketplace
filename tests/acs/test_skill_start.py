"""Behavior tests for skill-start.py's ticket-resolution refusal paths and the
first-child epic-status flip.

Originating ticket: MAR-169. Before this module skill-start.py's GateError-from-
build_context refusal, its unresolvable/archived/missing-partition/corrupt
ticket refusals, its lock-acquisition GateError, and the first-child epic
open -> in_progress flip were exercised by no test. Fixtures mint tickets
in-process via acs_case.lib (never through new-ticket.py's subprocess) --
this seam needs no subprocess at all.
"""

import json
import os
import shutil
import socket
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

TESTS_ACS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TESTS_ACS)

import acs_case  # noqa: E402

MODULE_FILENAME = "skill-start.py"
REPO_ID = "acme-shop"


def _mint(ws, tid, ttype="task", status="open", parent=None):
    """Write a valid active-partition ticket.json + index entry -- no subprocess."""
    tdir = acs_case.lib.ticket_dir(ws, REPO_ID, tid)
    os.makedirs(tdir, exist_ok=True)
    ticket = acs_case.lib.new_ticket_doc(tid, tid, ttype, status=status, parent=parent)
    acs_case.lib.save_ticket(tdir, ticket)
    acs_case.lib.update_index(ws, REPO_ID, ticket, archived=False)
    return tdir, ticket


def _mint_archived(ws, tid, ttype="task", status="done"):
    """Write a valid ticket.json under archive/ only -- no active partition."""
    tdir = os.path.join(acs_case.lib.archive_dir(ws, REPO_ID), tid)
    os.makedirs(tdir, exist_ok=True)
    ticket = acs_case.lib.new_ticket_doc(tid, tid, ttype, status=status)
    acs_case.lib.save_ticket(tdir, ticket)
    return tdir


def _partition_entries(ws):
    """Snapshot of this repo's workspace partition dir -- proves "nothing minted"."""
    rdir = acs_case.lib.repo_dir(ws, REPO_ID)
    return set(os.listdir(rdir)) if os.path.isdir(rdir) else set()


def _foreign_lock(tdir):
    """Write a live (this pid), non-stale lock held by a different checkout."""
    acs_case.lib.write_json(acs_case.lib.lock_path(tdir), {
        "checkout_id": "elsewhere-checkout",
        "checkout_path": "/elsewhere",
        "pid": os.getpid(),
        "hostname": socket.gethostname(),
        "created_at": acs_case.lib.now_iso(),
    })


class TestBuildContextGateError(unittest.TestCase):
    """119-121: build_context's GateError (cwd outside any git repo) exits 2."""

    def test_uninitialized_repo_exits_2_with_gate_error(self):
        mod = acs_case.load_module(MODULE_FILENAME)
        nongit = tempfile.mkdtemp(prefix="acs-skillstart-nongit-")
        self.addCleanup(shutil.rmtree, nongit, True)
        with acs_case.pushd(nongit):
            code, out, err = acs_case.run_main(mod, ["--skill", "code"])
        self.assertEqual(code, 2)
        self.assertEqual(out, "")
        self.assertTrue(
            err.startswith("acs skill-start: acs requires a git repository;"), err)


class TestTicketResolutionRefusals(acs_case.AcsWorkspaceCase):
    """149-169: unresolvable / archived / missing-partition / corrupt / locked."""

    def test_unresolvable_ticket_id_exits_2_and_writes_no_pointer(self):
        mod = acs_case.load_module(MODULE_FILENAME)
        with acs_case.pushd(self.repo):
            code, out, err = acs_case.run_main(mod, ["--skill", "code"])
        self.assertEqual(code, 2)
        self.assertEqual(out, "")
        self.assertEqual(
            err,
            "acs skill-start: could not resolve a ticket id (argument -> "
            "session pointer -> branch name). Pass --ticket explicitly.\n")
        self.assertFalse(
            os.path.isdir(acs_case.lib.sessions_dir(self.ws, REPO_ID)))

    def test_archived_ticket_is_refused(self):
        tdir = _mint_archived(self.ws, "SHOP-500")
        mod = acs_case.load_module(MODULE_FILENAME)
        with acs_case.pushd(self.repo):
            code, out, err = acs_case.run_main(
                mod, ["--skill", "code", "--ticket", "SHOP-500"])
        self.assertEqual(code, 2)
        self.assertEqual(err, "acs skill-start: ticket SHOP-500 is archived (done)\n")
        self.assertFalse(os.path.exists(acs_case.lib.lock_path(tdir)))

    def test_missing_partition_is_refused(self):
        mod = acs_case.load_module(MODULE_FILENAME)
        with acs_case.pushd(self.repo):
            code, out, err = acs_case.run_main(
                mod, ["--skill", "code", "--ticket", "SHOP-999"])
        self.assertEqual(code, 2)
        self.assertEqual(
            err,
            "acs skill-start: no partition for SHOP-999 — run /acs:create-ticket first\n")

    def test_corrupt_ticket_json_is_refused_before_the_lock(self):
        tdir = acs_case.lib.ticket_dir(self.ws, REPO_ID, "SHOP-77")
        os.makedirs(tdir)
        with open(os.path.join(tdir, "ticket.json"), "w") as fh:
            fh.write("{not json")
        mod = acs_case.load_module(MODULE_FILENAME)
        with acs_case.pushd(self.repo):
            code, out, err = acs_case.run_main(
                mod, ["--skill", "code", "--ticket", "SHOP-77"])
        self.assertEqual(code, 2)
        self.assertEqual(
            err.strip().splitlines()[-1],
            "acs skill-start: ticket.json missing/corrupt for SHOP-77")
        self.assertFalse(os.path.exists(acs_case.lib.lock_path(tdir)))

    def test_lock_held_by_another_checkout_is_refused_and_preserved(self):
        tdir, _ticket = _mint(self.ws, "SHOP-42")
        _foreign_lock(tdir)
        mod = acs_case.load_module(MODULE_FILENAME)
        with acs_case.pushd(self.repo):
            code, out, err = acs_case.run_main(
                mod, ["--skill", "code", "--ticket", "SHOP-42"])
        self.assertEqual(code, 2)
        # Pin skill-start.py's own message prefix (line 168's formatting) --
        # not just acquire_lock's exception body (assertIn below).
        self.assertTrue(err.startswith("acs skill-start: "), err)
        self.assertIn("locked by another session", err)
        lock = acs_case.lib.read_lock(tdir)
        self.assertEqual(lock["checkout_id"], "elsewhere-checkout")


class TestReconciliationRefusal(acs_case.AcsWorkspaceCase):
    """AC-1, AC-6 (CLI half): allocate_ticket_id's fail-closed reconciliation
    gate surfaces as an exit-2 refusal with actionable stderr on
    --allocate, and mints nothing -- including on the product-level-skill
    path (MAR-402)."""

    def test_first_allocation_in_an_unreconciled_workspace_exits_2(self):
        self.unreconcile()
        before = _partition_entries(self.ws)
        mod = acs_case.load_module(MODULE_FILENAME)
        with acs_case.pushd(self.repo):
            code, out, err = acs_case.run_main(
                mod, ["--skill", "create-ticket", "--allocate", "--title", "X"])
        self.assertEqual(code, 2)
        self.assertEqual(out, "")
        self.assertIn("blocked", err)
        self.assertIn("SHOP", err)
        self.assertEqual(_partition_entries(self.ws), before)

    def test_product_level_skill_allocate_also_refuses(self):
        self.unreconcile()
        before = _partition_entries(self.ws)
        mod = acs_case.load_module(MODULE_FILENAME)
        with acs_case.pushd(self.repo):
            code, out, err = acs_case.run_main(
                mod, ["--skill", "create-prd", "--allocate"])
        self.assertEqual(code, 2)
        self.assertIn("blocked", err)
        self.assertEqual(_partition_entries(self.ws), before)


class TestSeedNext(acs_case.AcsWorkspaceCase):
    """AC-5: --seed-next <n> confirms/repairs the reconciliation floor on
    skill-start.py --allocate, and is refused without --allocate (MAR-402)."""

    def test_seed_next_confirms_the_floor_and_mints_that_id(self):
        self.unreconcile()
        mod = acs_case.load_module(MODULE_FILENAME)
        with acs_case.pushd(self.repo):
            code, out, err = acs_case.run_main(
                mod, ["--skill", "create-ticket", "--allocate", "--seed-next", "5"])
        self.assertEqual(code, 0, err)
        payload = json.loads(out)
        self.assertEqual(payload["ticket_id"], "SHOP-5")

    def test_seed_next_records_explicit_user_provenance(self):
        self.unreconcile()
        mod = acs_case.load_module(MODULE_FILENAME)
        with acs_case.pushd(self.repo):
            code, out, err = acs_case.run_main(
                mod, ["--skill", "create-ticket", "--allocate", "--seed-next", "5"])
        self.assertEqual(code, 0, err)
        counters = acs_case.lib.read_json(self._counters_path())
        self.assertEqual(counters["seed_source"], "explicit-user")
        self.assertTrue(counters["reconciled"])

    def test_seed_next_repairs_a_wrong_existing_reconciliation(self):
        self.seed_counters(next_n=100)
        mod = acs_case.load_module(MODULE_FILENAME)
        with acs_case.pushd(self.repo):
            code, out, err = acs_case.run_main(
                mod, ["--skill", "create-ticket", "--allocate", "--seed-next", "3"])
        self.assertEqual(code, 0, err)
        payload = json.loads(out)
        self.assertEqual(payload["ticket_id"], "SHOP-3")
        self.assertIn("--seed-next", err)
        self.assertIn("100", err)
        self.assertTrue(os.path.exists(self._counters_path()))

    def test_seed_next_below_one_exits_2(self):
        before = _partition_entries(self.ws)
        mod = acs_case.load_module(MODULE_FILENAME)
        with acs_case.pushd(self.repo):
            code, out, err = acs_case.run_main(
                mod, ["--skill", "create-ticket", "--allocate", "--seed-next", "0"])
        self.assertEqual(code, 2)
        self.assertEqual(_partition_entries(self.ws), before)

    def test_seed_next_non_integer_exits_2(self):
        before = _partition_entries(self.ws)
        mod = acs_case.load_module(MODULE_FILENAME)
        with acs_case.pushd(self.repo):
            code, out, err = acs_case.run_main(
                mod, ["--skill", "create-ticket", "--allocate", "--seed-next", "abc"])
        self.assertEqual(code, 2)
        self.assertEqual(_partition_entries(self.ws), before)

    def test_seed_next_without_allocate_exits_2(self):
        before = _partition_entries(self.ws)
        mod = acs_case.load_module(MODULE_FILENAME)
        with acs_case.pushd(self.repo):
            code, out, err = acs_case.run_main(
                mod, ["--skill", "code", "--seed-next", "5"])
        self.assertEqual(code, 2)
        self.assertIn("--seed-next", err)
        self.assertIn("--allocate", err)
        self.assertEqual(_partition_entries(self.ws), before)


class TestEpicFlipOnFirstChildRun(acs_case.AcsWorkspaceCase):
    """198-205: the parent epic flips open -> in_progress on the child's first run."""

    def test_first_child_run_flips_the_parent_epic_to_in_progress(self):
        _mint(self.ws, "SHOP-20", ttype="epic", status="open")
        _mint(self.ws, "SHOP-21", ttype="task", status="open", parent="SHOP-20")
        # Straddle the invocation: read the index BEFORE running so the "open"
        # pre-state is observed, not merely assumed from the fixture -- this is
        # what makes the post-run assertion below prove line 204 (the parent's
        # lib.update_index call) actually ran, instead of sampling one side twice.
        index_before = acs_case.lib.read_json(
            acs_case.lib.index_path(self.ws, REPO_ID))
        self.assertEqual(index_before["tickets"]["SHOP-20"]["status"], "open")
        mod = acs_case.load_module(MODULE_FILENAME)
        with acs_case.pushd(self.repo):
            code, out, err = acs_case.run_main(
                mod, ["--skill", "code", "--ticket", "SHOP-21"])
        self.assertEqual(code, 0, err)
        payload = json.loads(out)
        self.assertEqual(payload["epic_marked_in_progress"], "SHOP-20")
        epic = acs_case.lib.load_ticket(
            acs_case.lib.ticket_dir(self.ws, REPO_ID, "SHOP-20"))
        self.assertEqual(epic["status"], "in_progress")
        index_after = acs_case.lib.read_json(
            acs_case.lib.index_path(self.ws, REPO_ID))
        self.assertEqual(index_after["tickets"]["SHOP-20"]["status"], "in_progress")

    def test_parent_epic_already_in_progress_is_not_re_flipped(self):
        epic_dir, _epic = _mint(self.ws, "SHOP-30", ttype="epic", status="in_progress")
        _mint(self.ws, "SHOP-31", ttype="task", status="open", parent="SHOP-30")
        mod = acs_case.load_module(MODULE_FILENAME)
        with acs_case.pushd(self.repo):
            code, out, err = acs_case.run_main(
                mod, ["--skill", "code", "--ticket", "SHOP-31"])
        self.assertEqual(code, 0, err)
        payload = json.loads(out)
        # epic_marked_in_progress (line 205) is set only inside the guarded
        # re-flip block, so None here is the discriminator that the guard at
        # skill-start.py:201 (parent already "in_progress") held -- unlike a
        # same-second updated_at comparison, this cannot pass by clock luck:
        # the guard mutant makes it a non-None string, never a coincidence.
        self.assertIsNone(payload["epic_marked_in_progress"])
        epic_after = acs_case.lib.load_ticket(epic_dir)
        self.assertEqual(epic_after["status"], "in_progress")


def _write_marker(ws, ckid, **overrides):
    """Write a session marker at sessions/<ckid>-session.json, fresh and
    same-checkout by default; overrides let a test make it stale/foreign."""
    marker = {
        "session_id": "sess-abc",
        "transcript_path": "/tmp/sess-abc.jsonl",
        "cwd": "/wherever",
        "checkout_id": ckid,
        "hook_event_name": "PreToolUse",
        "skill": "acs:code",
        "updated_at": acs_case.lib.now_iso(),
    }
    marker.update(overrides)
    acs_case.lib.write_json(
        acs_case.lib.session_marker_path(ws, REPO_ID, ckid), marker)
    return marker


class TestSessionMarkerThreading(acs_case.AcsWorkspaceCase):
    """118/125/189: skill-start.py reads the session marker as its first
    action after build_context and before the --pr branch, applies the
    staleness/cross-session guard, and threads the accepted (or None) marker
    into append_in_progress_run(..., session=marker)."""

    def test_fresh_same_checkout_marker_is_threaded_onto_the_run_entry(self):
        _mint(self.ws, "SHOP-60")
        ckid = acs_case.lib.checkout_id(self.repo)
        _write_marker(self.ws, ckid)
        mod = acs_case.load_module(MODULE_FILENAME)
        with acs_case.pushd(self.repo):
            code, out, err = acs_case.run_main(
                mod, ["--skill", "code", "--ticket", "SHOP-60"])
        self.assertEqual(code, 0, err)
        tdir = acs_case.lib.ticket_dir(self.ws, REPO_ID, "SHOP-60")
        entry = acs_case.lib.load_state(tdir, "code", "SHOP-60")["runs"][-1]
        self.assertEqual(entry["session_id"], "sess-abc")
        self.assertEqual(entry["transcript_path"], "/tmp/sess-abc.jsonl")

    def test_foreign_checkout_marker_is_rejected(self):
        _mint(self.ws, "SHOP-61")
        ckid = acs_case.lib.checkout_id(self.repo)
        _write_marker(self.ws, ckid, checkout_id="some-other-checkout-deadbeef")
        mod = acs_case.load_module(MODULE_FILENAME)
        with acs_case.pushd(self.repo):
            code, out, err = acs_case.run_main(
                mod, ["--skill", "code", "--ticket", "SHOP-61"])
        self.assertEqual(code, 0, err)
        tdir = acs_case.lib.ticket_dir(self.ws, REPO_ID, "SHOP-61")
        entry = acs_case.lib.load_state(tdir, "code", "SHOP-61")["runs"][-1]
        self.assertNotIn("session_id", entry)
        self.assertNotIn("transcript_path", entry)

    def test_stale_marker_older_than_15_minutes_is_rejected(self):
        _mint(self.ws, "SHOP-62")
        ckid = acs_case.lib.checkout_id(self.repo)
        stale = (datetime.now(timezone.utc) - timedelta(minutes=20)).strftime("%Y-%m-%dT%H:%M:%SZ")
        _write_marker(self.ws, ckid, updated_at=stale)
        mod = acs_case.load_module(MODULE_FILENAME)
        with acs_case.pushd(self.repo):
            code, out, err = acs_case.run_main(
                mod, ["--skill", "code", "--ticket", "SHOP-62"])
        self.assertEqual(code, 0, err)
        tdir = acs_case.lib.ticket_dir(self.ws, REPO_ID, "SHOP-62")
        entry = acs_case.lib.load_state(tdir, "code", "SHOP-62")["runs"][-1]
        self.assertNotIn("session_id", entry)

    def test_marker_within_15_minutes_is_accepted(self):
        _mint(self.ws, "SHOP-63")
        ckid = acs_case.lib.checkout_id(self.repo)
        fresh_enough = (datetime.now(timezone.utc) - timedelta(minutes=10)).strftime(
            "%Y-%m-%dT%H:%M:%SZ")
        _write_marker(self.ws, ckid, updated_at=fresh_enough)
        mod = acs_case.load_module(MODULE_FILENAME)
        with acs_case.pushd(self.repo):
            code, out, err = acs_case.run_main(
                mod, ["--skill", "code", "--ticket", "SHOP-63"])
        self.assertEqual(code, 0, err)
        tdir = acs_case.lib.ticket_dir(self.ws, REPO_ID, "SHOP-63")
        entry = acs_case.lib.load_state(tdir, "code", "SHOP-63")["runs"][-1]
        self.assertEqual(entry["session_id"], "sess-abc")

    def test_marker_with_unparseable_updated_at_is_rejected(self):
        _mint(self.ws, "SHOP-65")
        ckid = acs_case.lib.checkout_id(self.repo)
        _write_marker(self.ws, ckid, updated_at="not-a-timestamp")
        mod = acs_case.load_module(MODULE_FILENAME)
        with acs_case.pushd(self.repo):
            code, out, err = acs_case.run_main(
                mod, ["--skill", "code", "--ticket", "SHOP-65"])
        self.assertEqual(code, 0, err)
        tdir = acs_case.lib.ticket_dir(self.ws, REPO_ID, "SHOP-65")
        entry = acs_case.lib.load_state(tdir, "code", "SHOP-65")["runs"][-1]
        self.assertNotIn("session_id", entry)

    def test_no_marker_present_leaves_entry_without_session_fields(self):
        _mint(self.ws, "SHOP-64")
        mod = acs_case.load_module(MODULE_FILENAME)
        with acs_case.pushd(self.repo):
            code, out, err = acs_case.run_main(
                mod, ["--skill", "code", "--ticket", "SHOP-64"])
        self.assertEqual(code, 0, err)
        tdir = acs_case.lib.ticket_dir(self.ws, REPO_ID, "SHOP-64")
        entry = acs_case.lib.load_state(tdir, "code", "SHOP-64")["runs"][-1]
        self.assertNotIn("session_id", entry)
        self.assertNotIn("transcript_path", entry)


if __name__ == "__main__":
    unittest.main()
