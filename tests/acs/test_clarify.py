"""Behavior tests for clarify.py's refusal paths and rationale-recording arms.

Originating ticket: MAR-177. Before this module clarify.py's GateError-from-
build_context refusal, its unresolvable-ticket / missing-partition /
archived-write refusals, the archived-partition list exception, the
assumption-without-answer refusal, the answer command's rationale-stripping
and rationale-preserving arms, and the unknown-entry-id refusal were
exercised by no test. Fixtures mint tickets in-process via acs_case.lib
(never through new-ticket.py's subprocess) -- this seam needs no subprocess
at all.
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

MODULE_FILENAME = "clarify.py"
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


class TestBuildContextGateError(unittest.TestCase):
    """48-50: build_context's GateError (cwd outside any git repo) exits 2."""

    def test_uninitialized_repo_exits_2_with_gate_error(self):
        mod = acs_case.load_module(MODULE_FILENAME)
        nongit = tempfile.mkdtemp(prefix="acs-clarify-nongit-")
        self.addCleanup(shutil.rmtree, nongit, True)
        with acs_case.pushd(nongit):
            code, out, err = acs_case.run_main(mod, ["list"])
        self.assertEqual(code, 2)
        self.assertEqual(out, "")
        self.assertTrue(
            err.startswith("acs clarify: acs requires a git repository;"), err)


class TestTicketResolutionRefusals(acs_case.AcsWorkspaceCase):
    """54-62: unresolvable / missing-partition / archived-write refusals, and the
    archived-list exception (the `and args.cmd != "list"` conjunct)."""

    def test_unresolvable_ticket_id_exits_2(self):
        mod = acs_case.load_module(MODULE_FILENAME)
        with acs_case.pushd(self.repo):
            code, out, err = acs_case.run_main(mod, ["list"])
        self.assertEqual(code, 2)
        self.assertEqual(out, "")
        self.assertEqual(
            err, "acs clarify: could not resolve the ticket id (pass --ticket)\n")

    def test_missing_partition_exits_2(self):
        mod = acs_case.load_module(MODULE_FILENAME)
        with acs_case.pushd(self.repo):
            code, out, err = acs_case.run_main(mod, ["list", "--ticket", "SHOP-999"])
        self.assertEqual(code, 2)
        self.assertEqual(err, "acs clarify: no partition for SHOP-999\n")

    def test_archived_partition_refuses_add(self):
        tdir = _mint_archived(self.ws, "SHOP-500")
        mod = acs_case.load_module(MODULE_FILENAME)
        with acs_case.pushd(self.repo):
            code, out, err = acs_case.run_main(mod, [
                "add", "--skill", "code", "--question", "q", "--ticket", "SHOP-500"])
        self.assertEqual(code, 2)
        self.assertEqual(
            err, "acs clarify: SHOP-500 is archived — ledger is read-only\n")
        self.assertFalse(os.path.exists(os.path.join(tdir, "clarifications.json")))

    def test_archived_partition_allows_list(self):
        _mint_archived(self.ws, "SHOP-500")
        mod = acs_case.load_module(MODULE_FILENAME)
        with acs_case.pushd(self.repo):
            code, out, err = acs_case.run_main(mod, ["list", "--ticket", "SHOP-500"])
        self.assertEqual(code, 0, err)
        payload = json.loads(out)
        self.assertEqual(
            payload, {"ticket_id": "SHOP-500", "count": 0, "clarifications": []})


class TestAddRefusals(acs_case.AcsWorkspaceCase):
    """98-100: an assumption without --answer is refused even with --rationale
    present (a different guard from the rationale-missing refusal)."""

    def test_assumption_without_answer_exits_2(self):
        _mint(self.ws, "SHOP-1")
        mod = acs_case.load_module(MODULE_FILENAME)
        with acs_case.pushd(self.repo):
            code, out, err = acs_case.run_main(mod, [
                "add", "--skill", "code", "--question", "Retries?",
                "--source", "assumption", "--rationale", "matches retry.py:12",
                "--ticket", "SHOP-1"])
        self.assertEqual(code, 2)
        self.assertEqual(
            err,
            "acs clarify: an assumption must state the assumed answer (--answer)\n")
        tdir = acs_case.lib.ticket_dir(self.ws, REPO_ID, "SHOP-1")
        self.assertFalse(os.path.exists(os.path.join(tdir, "clarifications.json")))


class TestAnswerCommand(acs_case.AcsWorkspaceCase):
    """122-130: rationale-stripping, rationale-preserving, unknown-entry refusal."""

    def setUp(self):
        super().setUp()
        _mint(self.ws, "SHOP-1")
        self.tdir = acs_case.lib.ticket_dir(self.ws, REPO_ID, "SHOP-1")

    def _run(self, argv):
        mod = acs_case.load_module(MODULE_FILENAME)
        with acs_case.pushd(self.repo):
            return acs_case.run_main(mod, argv + ["--ticket", "SHOP-1"])

    def test_answer_records_stripped_rationale(self):
        code, out, err = self._run(["add", "--skill", "code", "--question", "Retries?"])
        self.assertEqual(code, 0, err)
        code, out, err = self._run([
            "answer", "--id", "C-1", "--answer", "reject", "--source", "assumption",
            "--rationale", "  matches retry.py:12  "])
        self.assertEqual(code, 0, err)
        ledger = acs_case.lib.read_json(os.path.join(self.tdir, "clarifications.json"))
        entry = ledger["clarifications"][0]
        self.assertEqual(entry["rationale"], "matches retry.py:12")
        self.assertEqual(entry["status"], "assumed")

    def test_answer_without_rationale_keeps_the_prior_rationale(self):
        self._run(["add", "--skill", "code", "--question", "Retries?"])
        self._run([
            "answer", "--id", "C-1", "--answer", "reject", "--source", "assumption",
            "--rationale", "  matches retry.py:12  "])
        code, out, err = self._run([
            "answer", "--id", "C-1", "--answer", "accept", "--source", "user"])
        self.assertEqual(code, 0, err)
        ledger = acs_case.lib.read_json(os.path.join(self.tdir, "clarifications.json"))
        entry = ledger["clarifications"][0]
        self.assertEqual(entry["rationale"], "matches retry.py:12")
        self.assertEqual(entry["status"], "answered")

    def test_unknown_entry_id_exits_2(self):
        code, out, err = self._run(["answer", "--id", "C-9", "--answer", "x"])
        self.assertEqual(code, 2)
        self.assertEqual(
            err,
            "acs clarify: no entry C-9 in %s\n"
            % os.path.join(self.tdir, "clarifications.json"))


if __name__ == "__main__":
    unittest.main()
