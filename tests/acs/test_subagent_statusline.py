"""Behavior tests for subagent-statusline.py's never-crash fallback branches:
ticket_for's cwd/pointer guards, elapsed's and tokens' reject/format
boundaries, row's column-budget truncation, and main()'s per-task and
per-row failure isolation.

Originating ticket: MAR-178. Before this module none of these branches were
exercised in-process -- the existing suite drives subagent-statusline.py only
through a subprocess and never asserts row()/ticket_for()/elapsed()/tokens()
return values directly. Fixtures mint tickets and pointers in-process via
acs_case.lib (never through new-ticket.py's subprocess) -- this seam needs no
subprocess at all.
"""

import json
import os
import shutil
import sys
import tempfile
import time
import unittest

TESTS_ACS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TESTS_ACS)

import acs_case  # noqa: E402

MODULE_FILENAME = "subagent-statusline.py"
REPO_ID = "acme-shop"


class TestTicketForCwdGuard(unittest.TestCase):
    """60: a task with no usable cwd (absent, non-str, or empty) returns None
    before acs_lib is ever imported.

    Residual (documented, R3): deleting the :59 isinstance/empty guard is
    masked by the :67-68 except -- build_context(None) would raise and be
    swallowed, producing the same None result. This test kills value
    mutations of :60 only; it does not prove the guard's own necessity."""

    def test_ticket_for_returns_none_without_a_usable_cwd(self):
        mod = acs_case.load_module(MODULE_FILENAME)
        self.assertIsNone(mod.ticket_for({}))
        self.assertIsNone(mod.ticket_for({"cwd": ""}))
        self.assertIsNone(mod.ticket_for({"cwd": 5}))


class TestTicketForContextErrorSwallowed(unittest.TestCase):
    """61-68: a cwd outside any git repo makes build_context raise GateError,
    which is swallowed rather than propagated."""

    def test_ticket_for_swallows_a_context_error_from_a_non_repo_cwd(self):
        mod = acs_case.load_module(MODULE_FILENAME)
        tmp = tempfile.mkdtemp(prefix="acs-non-repo-")
        self.addCleanup(shutil.rmtree, tmp, True)
        self.assertIsNone(mod.ticket_for({"cwd": tmp}))


class TestTicketForPointer(acs_case.AcsWorkspaceCase):
    """64-69: a resolvable pointer's ticket_id is returned; a pointer that
    deserializes to something other than a dict returns None instead."""

    def test_ticket_for_reads_the_pointer_and_returns_none_when_it_is_not_a_dict(self):
        ckid = acs_case.lib.checkout_id(self.repo)
        mod = acs_case.load_module(MODULE_FILENAME)

        acs_case.lib.write_json(
            acs_case.lib.pointer_path(self.ws, REPO_ID, ckid), {"ticket_id": "SHOP-9"})
        self.assertEqual(mod.ticket_for({"cwd": self.repo}), "SHOP-9")

        acs_case.lib.write_json(
            acs_case.lib.pointer_path(self.ws, REPO_ID, ckid), ["not", "a", "dict"])
        self.assertIsNone(mod.ticket_for({"cwd": self.repo}))


class TestElapsed(unittest.TestCase):
    """73-82: unusable and future starts return None; both sides of the
    60-second boundary format distinctly."""

    def test_elapsed_rejects_unusable_and_future_starts_and_formats_both_sides_of_a_minute(self):
        mod = acs_case.load_module(MODULE_FILENAME)
        self.assertIsNone(mod.elapsed(None))
        self.assertIsNone(mod.elapsed(0))
        self.assertIsNone(mod.elapsed("2026"))
        self.assertIsNone(mod.elapsed(time.time() + 60))
        self.assertEqual(mod.elapsed(time.time() - 5), "5s")
        self.assertEqual(mod.elapsed(time.time() - 59), "59s")
        self.assertEqual(mod.elapsed(time.time() - 60), "1m00s")


class TestTokens(unittest.TestCase):
    """86-90: non-positive or non-numeric counts return None; both sides of
    the 1000-token boundary format distinctly."""

    def test_tokens_rejects_non_positive_counts_and_formats_both_sides_of_a_thousand(self):
        mod = acs_case.load_module(MODULE_FILENAME)
        self.assertIsNone(mod.tokens(None))
        self.assertIsNone(mod.tokens(0))
        self.assertIsNone(mod.tokens(-5))
        self.assertIsNone(mod.tokens("x"))
        self.assertEqual(mod.tokens(999), "999 tok")
        self.assertEqual(mod.tokens(1000), "1k tok")


class TestRowTruncation(unittest.TestCase):
    """108-111: a row exactly at the column budget is left untouched (the `>`
    boundary, not `>=`); a row over budget is truncated to columns - 1 plus
    an ellipsis; a degenerate budget at or under the columns > 4 guard is
    left untouched rather than truncated to something unusably short."""

    def test_row_truncates_to_the_column_budget_with_an_ellipsis(self):
        mod = acs_case.load_module(MODULE_FILENAME)
        task = {"id": "t1", "type": "acs:code-verifier", "status": "running"}

        # "▶ verify · code-verifier" is exactly 24 chars: columns == len(content)
        # must pass through unchanged (24 > 24 is False), distinguishing `>`
        # from a `>=` mutant that would truncate here instead.
        at_boundary = mod.row(task, 24)
        self.assertEqual(at_boundary["content"], "▶ verify · code-verifier")

        truncated = mod.row(task, 12)
        self.assertEqual(truncated["content"], "▶ verify · …")
        self.assertEqual(len(truncated["content"]), 12)
        self.assertTrue(truncated["content"].endswith("…"))

        # columns == 4 fails the `columns > 4` guard, so content must pass
        # through unchanged even though it is far longer than 4.
        narrow = mod.row(task, 4)
        self.assertEqual(narrow["content"], "▶ verify · code-verifier")


class TestMainSkipsUnusableTasks(unittest.TestCase):
    """119-122: a non-dict task and a task whose id is None or empty are
    skipped; a well-formed task still emits its row."""

    def test_main_skips_non_dict_and_idless_tasks(self):
        mod = acs_case.load_module(MODULE_FILENAME)
        payload = json.dumps({
            "columns": 200,
            "tasks": [
                "not-a-dict",
                {"id": "", "type": "acs:code-planner"},
                {"id": None, "type": "acs:code-planner"},
                {"id": "good1", "type": "acs:code-executor", "status": "running"},
            ],
        })
        tmp = tempfile.mkdtemp(prefix="acs-substatusline-")
        self.addCleanup(shutil.rmtree, tmp, True)
        with acs_case.pushd(tmp):
            code, out, err = acs_case.run_main(mod, [], stdin=payload)
        self.assertEqual(code, 0)
        lines = [line for line in out.splitlines() if line]
        self.assertEqual(len(lines), 1)
        self.assertEqual(json.loads(lines[0])["id"], "good1")


class TestMainDropsOnlyTheRaisingRow(unittest.TestCase):
    """123-126: when row() raises for one task, that task's row is dropped
    and the panel keeps rendering the rest."""

    def test_main_drops_only_the_row_that_raises(self):
        mod = acs_case.load_module(MODULE_FILENAME)
        real_row = mod.row

        def exploding_row(task, columns):
            if task.get("id") == "boom":
                raise RuntimeError("boom")
            return real_row(task, columns)

        mod.row = exploding_row
        self.addCleanup(setattr, mod, "row", real_row)

        payload = json.dumps({
            "columns": 200,
            "tasks": [
                {"id": "boom", "type": "acs:code-executor", "status": "running"},
                {"id": "ok", "type": "acs:code-verifier", "status": "completed"},
            ],
        })
        tmp = tempfile.mkdtemp(prefix="acs-substatusline-")
        self.addCleanup(shutil.rmtree, tmp, True)
        with acs_case.pushd(tmp):
            code, out, err = acs_case.run_main(mod, [], stdin=payload)
        self.assertEqual(code, 0)
        lines = [line for line in out.splitlines() if line]
        self.assertEqual(len(lines), 1)
        self.assertEqual(json.loads(lines[0])["id"], "ok")


if __name__ == "__main__":
    unittest.main()
