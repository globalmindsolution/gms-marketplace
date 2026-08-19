"""Behavior tests for acs_lib.py's pre-hook gate functions.

Originating ticket: MAR-173. _require_completed's in_progress and
last-ended-with-status detail branches, gate_create_prd's unconditional
return, gate_create_architecture's PRD-found return, gate_create_project's
missing/found tech-stack.md branches, _resolve_ticket_for_gate's archived
and corrupt/missing-ticket.json branches, gate_create_design's success
return, tracker_cli_warning's github/jira not-found branches, and
_tool_version's nonexistent-binary branch were exercised by no test.
"""

import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRIPTS = os.path.join(REPO_ROOT, "plugins", "acs", "hooks", "scripts")
sys.path.insert(0, SCRIPTS)

import acs_lib as lib  # noqa: E402

sys.path.insert(0, os.path.join(REPO_ROOT, "tests", "acs"))
from acs_case import AcsWorkspaceCase  # noqa: E402


class TestRequireCompleted(unittest.TestCase):
    """1552: reports the in_progress detail; 1554: reports the "last ended
    with status X" detail."""

    def setUp(self):
        self.tdir = tempfile.mkdtemp(prefix="acs-test-")
        self.addCleanup(shutil.rmtree, self.tdir, True)

    def test_reports_in_progress_detail(self):
        lib.append_in_progress_run(self.tdir, "create-ticket", "SHOP-1")
        with self.assertRaises(lib.GateError) as ctx:
            lib._require_completed(self.tdir, "create-ticket", "SHOP-1", "run it")
        self.assertIn("in_progress", str(ctx.exception))

    def test_reports_last_ended_with_status_detail(self):
        lib.append_in_progress_run(self.tdir, "create-ticket", "SHOP-1")
        lib.finalize_run(self.tdir, "create-ticket", "SHOP-1", {"status": "failed"})
        with self.assertRaises(lib.GateError) as ctx:
            lib._require_completed(self.tdir, "create-ticket", "SHOP-1", "run it")
        self.assertIn("failed", str(ctx.exception))


class TestGateCreatePrd(unittest.TestCase):
    """1561: returns None unconditionally."""

    def test_returns_none_unconditionally(self):
        self.assertIsNone(lib.gate_create_prd({}, {}))


class TestGateCreateArchitecture(unittest.TestCase):
    """1573: returns None when prd.md exists under the configured prd_path."""

    def test_returns_none_when_prd_exists(self):
        root = tempfile.mkdtemp(prefix="acs-test-")
        self.addCleanup(shutil.rmtree, root, True)
        os.makedirs(os.path.join(root, "docs", "product"))
        open(os.path.join(root, "docs", "product", "prd.md"), "w").close()
        ctx = {"checkout_root": root, "settings": {}}
        self.assertIsNone(lib.gate_create_architecture(ctx, {}))


class TestGateCreateProject(unittest.TestCase):
    """1577-1583: raises GateError when hld/tech-stack.md is missing;
    1584: returns None when it exists."""

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="acs-test-")
        self.addCleanup(shutil.rmtree, self.root, True)
        self.ctx = {"checkout_root": self.root, "settings": {}}

    def test_raises_when_tech_stack_missing(self):
        with self.assertRaises(lib.GateError) as ctx:
            lib.gate_create_project(self.ctx, {})
        self.assertIn("tech-stack.md", str(ctx.exception))

    def test_returns_none_when_tech_stack_exists(self):
        hld = os.path.join(self.root, "docs", "architecture", "hld")
        os.makedirs(hld)
        open(os.path.join(hld, "tech-stack.md"), "w").close()
        self.assertIsNone(lib.gate_create_project(self.ctx, {}))


class TestResolveTicketForGate(AcsWorkspaceCase):
    """1606: raises for an archived ticket; 1611: raises for a corrupt/missing
    ticket.json."""

    def _ctx(self):
        return {
            "cwd": self.repo, "settings": {"ticket_prefix": "SHOP"},
            "workspace": self.ws, "repo_id": "acme-shop",
            "checkout_id": lib.checkout_id(self.repo),
        }

    def test_raises_for_archived_ticket(self):
        tdir = os.path.join(lib.archive_dir(self.ws, "acme-shop"), "SHOP-1")
        os.makedirs(tdir)
        payload = {"tool_input": {"args": "SHOP-1"}}
        with self.assertRaises(lib.GateError) as ctx:
            lib._resolve_ticket_for_gate(self._ctx(), payload, "create-design")
        self.assertIn("archived", str(ctx.exception))

    def test_raises_for_missing_ticket_json(self):
        tdir = self.tdir("SHOP-2")
        os.makedirs(tdir)
        payload = {"tool_input": {"args": "SHOP-2"}}
        with self.assertRaises(lib.GateError) as ctx:
            lib._resolve_ticket_for_gate(self._ctx(), payload, "create-design")
        self.assertIn("ticket.json", str(ctx.exception))


class TestGateCreateDesign(AcsWorkspaceCase):
    """1626: returns the ticket id for a needs_design:true ticket whose
    create-ticket run completed."""

    def test_returns_ticket_id_when_needs_design_and_create_ticket_completed(self):
        tdir = self.tdir("SHOP-3")
        os.makedirs(tdir)
        lib.save_ticket(tdir, {"id": "SHOP-3", "needs_design": True})
        lib.append_in_progress_run(tdir, "create-ticket", "SHOP-3")
        lib.finalize_run(tdir, "create-ticket", "SHOP-3", {"status": "completed"})
        ctx = {
            "cwd": self.repo, "settings": {"ticket_prefix": "SHOP"},
            "workspace": self.ws, "repo_id": "acme-shop",
            "checkout_id": lib.checkout_id(self.repo),
        }
        payload = {"tool_input": {"args": "SHOP-3"}}
        self.assertEqual(lib.gate_create_design(ctx, payload), "SHOP-3")


class TestGateCodeEpicRefusal(AcsWorkspaceCase):
    """1648: refuses type=='epic' tickets with a breakdown-direction
    GateError; non-epic tickets (including COMPLEX-lane and parentless
    tasks, and stories whose parent is an epic) pass through unaffected."""

    def _ctx(self):
        return {
            "cwd": self.repo, "settings": {"ticket_prefix": "SHOP"},
            "workspace": self.ws, "repo_id": "acme-shop",
            "checkout_id": lib.checkout_id(self.repo),
        }

    def test_epic_ticket_is_refused_with_breakdown_direction(self):
        tdir = self.tdir("SHOP-4")
        os.makedirs(tdir)
        lib.save_ticket(tdir, {"id": "SHOP-4", "type": "epic"})
        payload = {"tool_input": {"args": "SHOP-4"}}
        with self.assertRaises(lib.GateError) as ctx:
            lib.gate_code(self._ctx(), payload)
        msg = str(ctx.exception)
        self.assertIn("SHOP-4", msg)
        self.assertIn("epic", msg)
        self.assertIn("/acs:create-ticket", msg)
        self.assertIn("child", msg)

    def test_epic_refusal_surfaces_as_exit_2_through_the_pre_hook(self):
        tdir = self.tdir("SHOP-5")
        os.makedirs(tdir)
        lib.save_ticket(tdir, {"id": "SHOP-5", "type": "epic"})
        result = self.pre("code", "SHOP-5")
        self.assertEqual(result.returncode, 2)
        self.assertIn("epic", result.stderr)

    def test_non_epic_large_size_ticket_is_not_refused(self):
        tdir = self.tdir("SHOP-6")
        os.makedirs(tdir)
        lib.save_ticket(tdir, {"id": "SHOP-6", "type": "task", "size": "large"})
        payload = {"tool_input": {"args": "SHOP-6"}}
        self.assertEqual(lib.gate_code(self._ctx(), payload), "SHOP-6")

    def test_task_with_null_parent_and_no_design_still_passes(self):
        tdir = self.tdir("SHOP-7")
        os.makedirs(tdir)
        lib.save_ticket(tdir, {"id": "SHOP-7", "type": "task", "parent": None})
        payload = {"tool_input": {"args": "SHOP-7"}}
        self.assertEqual(lib.gate_code(self._ctx(), payload), "SHOP-7")

    def test_story_child_of_epic_is_not_refused(self):
        tdir = self.tdir("SHOP-8")
        os.makedirs(tdir)
        lib.save_ticket(tdir, {"id": "SHOP-8", "type": "story", "parent": "SHOP-1"})
        payload = {"tool_input": {"args": "SHOP-8"}}
        self.assertEqual(lib.gate_code(self._ctx(), payload), "SHOP-8")


class TestTrackerCliWarning(unittest.TestCase):
    """1779: warns for provider github with no gh; 1781: warns for provider
    jira with no acli."""

    def test_warns_for_github_without_gh(self):
        with mock.patch("shutil.which", return_value=None):
            msg = lib.tracker_cli_warning({"tracker": {"provider": "github"}})
        self.assertIn("gh", msg)

    def test_warns_for_jira_without_acli(self):
        with mock.patch("shutil.which", return_value=None):
            msg = lib.tracker_cli_warning({"tracker": {"provider": "jira"}})
        self.assertIn("acli", msg)


class TestToolVersion(unittest.TestCase):
    """1819-1820: returns None for a non-existent binary."""

    def test_returns_none_for_nonexistent_binary(self):
        self.assertIsNone(lib._tool_version("acs-definitely-not-a-real-binary-xyz"))


if __name__ == "__main__":
    unittest.main()
