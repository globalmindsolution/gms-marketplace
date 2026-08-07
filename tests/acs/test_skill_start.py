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


if __name__ == "__main__":
    unittest.main()
