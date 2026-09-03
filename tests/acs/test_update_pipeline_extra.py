"""update_pipeline's `extra` channel: a writer for step fields it does not own.

MAR-510. /acs:ship keeps a `fix_loops` counter on the `test` step entry and
had no supported way to write it -- the skill's prose claimed update_pipeline
"already writes an arbitrary-shape step dict", which it did not. `extra` merges
caller fields, `extra={"<key>": None}` removes one, and the fields the step
entry itself owns stay unwritable through it.
"""

import json
import os
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO_ROOT, "plugins", "acs", "hooks", "scripts"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import acs_lib as lib  # noqa: E402
from acs_case import AcsWorkspaceCase  # noqa: E402


class PipelineCase(AcsWorkspaceCase):
    """AcsWorkspaceCase plus the repo id its fixture remote implies."""

    @property
    def repo_id(self):
        return lib.build_context(self.repo)["repo_id"]


class UpdatePipelineExtraTest(PipelineCase):
    """update_pipeline(extra=...) merges caller fields without letting them
    overwrite the fields the step entry owns."""

    def _tdir(self, ticket_id="SHOP-1"):
        tdir = lib.ticket_dir(self.ws, self.repo_id, ticket_id)
        os.makedirs(tdir, exist_ok=True)
        return tdir

    def test_extra_fields_are_merged(self):
        tdir = self._tdir()
        data = lib.update_pipeline(tdir, "SHOP-1", "test", "in_progress", extra={"fix_loops": 2})
        self.assertEqual(data["steps"]["test"]["fix_loops"], 2)

    def test_none_value_removes_the_field(self):
        tdir = self._tdir()
        lib.update_pipeline(tdir, "SHOP-1", "test", "in_progress", extra={"fix_loops": 2})
        data = lib.update_pipeline(tdir, "SHOP-1", "test", "completed", extra={"fix_loops": None})
        self.assertNotIn("fix_loops", data["steps"]["test"])

    def test_reserved_keys_are_not_overridable(self):
        """A caller cannot rewrite the step's own status or timestamps."""
        tdir = self._tdir()
        data = lib.update_pipeline(tdir, "SHOP-1", "test", "failed",
                                   extra={"status": "completed", "ended_at": "whenever",
                                          "summary": "spoofed"})
        self.assertEqual(data["steps"]["test"]["status"], "failed")
        self.assertNotEqual(data["steps"]["test"]["ended_at"], "whenever")
        self.assertNotEqual(data["steps"]["test"].get("summary"), "spoofed")


class PipelineStepCliTest(PipelineCase):
    """The CLI itself: an unhooked skill records a step without embedding Python."""

    def setUp(self):
        super().setUp()
        self.ticket_id = "SHOP-1"
        self.tdir = lib.ticket_dir(self.ws, self.repo_id, self.ticket_id)
        os.makedirs(self.tdir, exist_ok=True)
        lib.save_ticket(self.tdir, lib.new_ticket_doc(self.ticket_id, "A ticket", "task"))

    def _pipeline(self):
        return lib.load_pipeline(self.tdir, self.ticket_id)

    def test_records_a_completed_step(self):
        result = self.run_script("pipeline-step.py",
            "--ticket", self.ticket_id, "--skill", "test",
            "--status", "completed", "--summary", "unit green")
        self.assertEqual(result.returncode, 0, result.stderr)
        step = self._pipeline()["steps"]["test"]
        self.assertEqual(step["status"], "completed")
        self.assertEqual(step["summary"], "unit green")

    def test_set_parses_scalars(self):
        self.run_script("pipeline-step.py",
            "--ticket", self.ticket_id, "--skill", "test", "--status", "in_progress",
            "--set", "fix_loops=2", "--set", "capped=false", "--set", "note=two left")
        step = self._pipeline()["steps"]["test"]
        self.assertEqual(step["fix_loops"], 2)
        self.assertIs(step["capped"], False)
        self.assertEqual(step["note"], "two left")

    def test_unset_removes_a_field(self):
        self.run_script("pipeline-step.py",
            "--ticket", self.ticket_id, "--skill", "test", "--status", "in_progress",
            "--set", "fix_loops=2")
        self.run_script("pipeline-step.py",
            "--ticket", self.ticket_id, "--skill", "test", "--status", "completed",
            "--unset", "fix_loops")
        self.assertNotIn("fix_loops", self._pipeline()["steps"]["test"])

    def test_only_if_present_does_not_open_a_new_gate(self):
        """A standing test run that fails must not create a steps.test entry:
        that would newly block docs-sync on a pipeline that never gated on it."""
        result = self.run_script("pipeline-step.py",
            "--ticket", self.ticket_id, "--skill", "test", "--status", "failed",
            "--only-if-present")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIs(json.loads(result.stdout)["written"], False)
        self.assertNotIn("test", self._pipeline().get("steps", {}))

    def test_only_if_present_updates_an_active_gate(self):
        self.run_script("pipeline-step.py",
            "--ticket", self.ticket_id, "--skill", "test", "--status", "in_progress")
        self.run_script("pipeline-step.py",
            "--ticket", self.ticket_id, "--skill", "test", "--status", "failed",
            "--only-if-present", "--summary", "e2e red")
        self.assertEqual(self._pipeline()["steps"]["test"]["status"], "failed")

    def test_unknown_ticket_exits_2(self):
        result = self.run_script("pipeline-step.py",
            "--ticket", "SHOP-999", "--skill", "test", "--status", "completed")
        self.assertEqual(result.returncode, 2)
        self.assertIn("no active partition", result.stderr)

    def test_malformed_set_exits_2(self):
        result = self.run_script("pipeline-step.py",
            "--ticket", self.ticket_id, "--skill", "test", "--status", "completed",
            "--set", "nonsense")
        self.assertEqual(result.returncode, 2)
        self.assertIn("KEY=VALUE", result.stderr)


class DocsSyncGateRemedyTest(PipelineCase):
    """The gate's own error message must name a command that can open it."""

    def test_recording_the_test_step_completed_opens_the_gate(self):
        ticket_id = "SHOP-1"
        tdir = lib.ticket_dir(self.ws, self.repo_id, ticket_id)
        os.makedirs(tdir, exist_ok=True)
        lib.save_ticket(tdir, lib.new_ticket_doc(ticket_id, "A ticket", "task"))
        lib.append_in_progress_run(tdir, "code", ticket_id)
        lib.finalize_run(tdir, "code", ticket_id, {"status": "completed"})
        lib.update_pipeline(tdir, ticket_id, "test", "failed", summary="cap reached")

        ctx = lib.build_context(self.repo)
        payload = {"cwd": self.repo, "tool_name": "Skill",
                   "tool_input": {"skill": "acs:docs-sync", "args": ticket_id}}
        with self.assertRaises(lib.GateError) as blocked:
            lib.gate_docs_sync(ctx, payload)
        self.assertIn("/acs:test --for-ticket", str(blocked.exception))

        self.run_script("pipeline-step.py",
            "--ticket", ticket_id, "--skill", "test", "--status", "completed")
        lib.gate_docs_sync(ctx, payload)  # no longer blocked


if __name__ == "__main__":
    unittest.main()
