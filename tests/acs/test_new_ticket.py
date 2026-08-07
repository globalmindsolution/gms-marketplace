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


if __name__ == "__main__":
    unittest.main()
