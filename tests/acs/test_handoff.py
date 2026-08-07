"""Behavior tests for handoff.py's summary-file input, refusal paths, and the
no-in-progress-run resume fallback.

Originating ticket: MAR-177. Before this module the --summary-file reader
(the entire alternate input mode), the missing/whitespace-only-summary
refusal, the GateError-from-build_context refusal, the unresolvable-ticket
and archived/missing-partition refusals, and the "no in-progress run"
/acs:ship resume fallback were exercised by no test -- the existing suite
only drives the --summary inline form with an in-progress /acs:code run.
Fixtures mint tickets in-process via acs_case.lib (never through
new-ticket.py's subprocess) -- this seam needs no subprocess at all.
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

MODULE_FILENAME = "handoff.py"
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


class TestSummaryRequired(unittest.TestCase):
    """38-40: the not-summary refusal fires before any git/ticket context is
    touched, whether no flag was given or --summary-file resolved to nothing
    but whitespace."""

    def test_missing_summary_exits_2(self):
        mod = acs_case.load_module(MODULE_FILENAME)
        nongit = tempfile.mkdtemp(prefix="acs-handoff-nosummary-")
        self.addCleanup(shutil.rmtree, nongit, True)
        with acs_case.pushd(nongit):
            code, out, err = acs_case.run_main(mod, [])
        self.assertEqual(code, 2)
        self.assertEqual(out, "")
        self.assertEqual(
            err,
            "acs handoff: a handoff summary is required "
            "(--summary or --summary-file)\n")

    def test_whitespace_only_summary_file_is_refused(self):
        tmp = tempfile.mkdtemp(prefix="acs-handoff-summaryfile-")
        self.addCleanup(shutil.rmtree, tmp, True)
        path = os.path.join(tmp, "summary.txt")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("   \n\t\n")
        mod = acs_case.load_module(MODULE_FILENAME)
        with acs_case.pushd(tmp):
            code, out, err = acs_case.run_main(mod, ["--summary-file", path])
        self.assertEqual(code, 2)
        self.assertEqual(
            err,
            "acs handoff: a handoff summary is required "
            "(--summary or --summary-file)\n")


class TestBuildContextGateError(unittest.TestCase):
    """45-47: build_context's GateError (cwd outside any git repo) exits 2."""

    def test_uninitialized_repo_exits_2_with_gate_error(self):
        mod = acs_case.load_module(MODULE_FILENAME)
        nongit = tempfile.mkdtemp(prefix="acs-handoff-nongit-")
        self.addCleanup(shutil.rmtree, nongit, True)
        with acs_case.pushd(nongit):
            code, out, err = acs_case.run_main(mod, ["--summary", "s"])
        self.assertEqual(code, 2)
        self.assertEqual(out, "")
        self.assertTrue(
            err.startswith("acs handoff: acs requires a git repository;"), err)


class TestTicketResolutionRefusals(acs_case.AcsWorkspaceCase):
    """52-57: unresolvable-ticket and the archived/missing-partition disjuncts."""

    def test_unresolvable_ticket_exits_2(self):
        mod = acs_case.load_module(MODULE_FILENAME)
        with acs_case.pushd(self.repo):
            code, out, err = acs_case.run_main(mod, ["--summary", "s"])
        self.assertEqual(code, 2)
        self.assertEqual(out, "")
        self.assertEqual(
            err,
            "acs handoff: no current ticket for this checkout "
            "(nothing to hand off)\n")

    def test_archived_partition_is_refused(self):
        tdir = _mint_archived(self.ws, "SHOP-500")
        acs_case.lib.acquire_lock(tdir, self.repo)
        mod = acs_case.load_module(MODULE_FILENAME)
        with acs_case.pushd(self.repo):
            code, out, err = acs_case.run_main(
                mod, ["--summary", "s", "--ticket", "SHOP-500"])
        self.assertEqual(code, 2)
        self.assertEqual(err, "acs handoff: no active partition for SHOP-500\n")
        self.assertTrue(os.path.exists(acs_case.lib.lock_path(tdir)))

    def test_missing_partition_is_refused(self):
        mod = acs_case.load_module(MODULE_FILENAME)
        with acs_case.pushd(self.repo):
            code, out, err = acs_case.run_main(
                mod, ["--summary", "s", "--ticket", "SHOP-999"])
        self.assertEqual(code, 2)
        self.assertEqual(err, "acs handoff: no active partition for SHOP-999\n")


class TestResumeHint(acs_case.AcsWorkspaceCase):
    """36-37, 84-87: summary-file content is read and stripped into the
    persisted artifacts; the resume hint falls back to /acs:ship when no
    skill's last run is in_progress, and to /acs:<skill> plus a released
    lock when one is."""

    def test_summary_file_content_is_recorded_stripped(self):
        tdir, _ticket = _mint(self.ws, "SHOP-42")
        acs_case.lib.append_in_progress_run(tdir, "code", "SHOP-42")
        summary_path = os.path.join(self.tmp, "summary.txt")
        with open(summary_path, "w", encoding="utf-8") as fh:
            fh.write("  done: probe; next: nothing  \n")
        mod = acs_case.load_module(MODULE_FILENAME)
        with acs_case.pushd(self.repo):
            code, out, err = acs_case.run_main(
                mod, ["--summary-file", summary_path, "--ticket", "SHOP-42"])
        self.assertEqual(code, 0, err)
        state = acs_case.lib.load_state(tdir, "code")
        self.assertEqual(
            state["runs"][-1]["handoff_summary"], "done: probe; next: nothing")
        pipeline = acs_case.lib.read_json(os.path.join(tdir, "pipeline-state.json"))
        self.assertEqual(
            pipeline["steps"]["code"]["summary"], "done: probe; next: nothing")

    def test_no_in_progress_run_resumes_with_ship(self):
        tdir, _ticket = _mint(self.ws, "SHOP-42")
        mod = acs_case.load_module(MODULE_FILENAME)
        with acs_case.pushd(self.repo):
            code, out, err = acs_case.run_main(
                mod, ["--summary", "s", "--ticket", "SHOP-42"])
        self.assertEqual(code, 0, err)
        payload = json.loads(out)
        self.assertIsNone(payload["skill"])
        self.assertEqual(payload["continue_with"], "/acs:ship SHOP-42")
        for skill in acs_case.lib.HOOKED_SKILLS:
            self.assertFalse(
                os.path.exists(acs_case.lib.state_path(tdir, skill)), skill)

    def test_in_progress_run_resumes_with_that_skill_and_releases_the_lock(self):
        tdir, _ticket = _mint(self.ws, "SHOP-42")
        acs_case.lib.append_in_progress_run(tdir, "code", "SHOP-42")
        acs_case.lib.acquire_lock(tdir, self.repo)
        mod = acs_case.load_module(MODULE_FILENAME)
        with acs_case.pushd(self.repo):
            code, out, err = acs_case.run_main(
                mod, ["--summary", "s", "--ticket", "SHOP-42"])
        self.assertEqual(code, 0, err)
        payload = json.loads(out)
        self.assertEqual(payload["skill"], "code")
        self.assertEqual(payload["continue_with"], "/acs:code SHOP-42")
        state = acs_case.lib.load_state(tdir, "code")
        self.assertEqual(state["runs"][-1]["status"], "handed_off")
        self.assertFalse(os.path.exists(acs_case.lib.lock_path(tdir)))


if __name__ == "__main__":
    unittest.main()
