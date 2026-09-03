"""pipeline-step.py — the CLI unhooked skills use to record a step transition.

MAR-511. /acs:test has no post-hook, so without this it would have to embed
Python in its prose to reach acs_lib.update_pipeline — the pattern ADR 0001
exists to prevent. The gate remedy depends on it: docs-sync blocks while
steps.test exists and is not completed, and before this nothing could set it.

Also pins the two prose contracts that carry AC-1, since the deliverable there
is instructions rather than code and would otherwise be silently reword-able.

Run:  python3 -m unittest tests.acs.test_pipeline_step_cli -v
"""

import json
import os
import re
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN = os.path.join(REPO_ROOT, "plugins", "acs")
sys.path.insert(0, os.path.join(PLUGIN, "hooks", "scripts"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import acs_lib as lib  # noqa: E402
from acs_case import AcsWorkspaceCase  # noqa: E402


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def assert_invocations_are_runnable(case, body):
    """Every pipeline-step.py call inside a ```bash fence must be copy-pasteable.

    Prose may name the script in backticks; a fenced command may not, because
    hooks/scripts/ is not on PATH.
    """
    blocks = re.findall(r"(?s)```bash(.*?)```", body)
    invocations = [line for block in blocks for line in block.splitlines()
                   if "pipeline-step.py" in line]
    case.assertTrue(invocations, "no fenced pipeline-step.py invocation found")
    for line in invocations:
        case.assertIn("CLAUDE_PLUGIN_ROOT", line, line.strip())
        case.assertIn("python3", line, line.strip())


class PipelineStepCliTest(AcsWorkspaceCase):
    @property
    def repo_id(self):
        return lib.build_context(self.repo)["repo_id"]

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
        """A direct `/acs:test --for-ticket` run — what the docs-sync gate's own
        error tells a user to run — must not create a steps.test entry by
        failing: that would newly shut the gate they ran it to open."""
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


class ArgumentsAreValidatedBeforeAnyWriteTest(PipelineStepCliTest):
    """--ticket becomes a path segment and --skill becomes a ledger key, so
    both are validated against pipeline-state.schema.json's own ticket_id
    pattern and steps enum before the partition is even resolved."""

    def _schema(self):
        with open(os.path.join(PLUGIN, "schemas", "pipeline-state.schema.json"),
                  encoding="utf-8") as fh:
            return json.load(fh)

    def test_a_traversing_ticket_id_is_refused(self):
        result = self.run_script("pipeline-step.py",
            "--ticket", "../victim", "--skill", "test", "--status", "completed")
        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertIn("not a ticket id", result.stderr)
        self.assertFalse(os.path.exists(os.path.join(self.ws, "victim")),
                         "a write escaped the partition tree")

    def test_a_step_name_outside_the_schema_enum_is_refused(self):
        result = self.run_script("pipeline-step.py",
            "--ticket", self.ticket_id, "--skill", "not-a-skill", "--status", "completed")
        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertNotIn("not-a-skill", self._pipeline().get("steps", {}))

    def test_the_accepted_skills_are_exactly_the_schema_enum(self):
        import ast
        source = read(os.path.join(PLUGIN, "hooks", "scripts", "pipeline-step.py"))
        steps = next(
            ast.literal_eval(node.value)
            for node in ast.parse(source).body
            if isinstance(node, ast.Assign)
            and any(getattr(t, "id", None) == "PIPELINE_STEPS" for t in node.targets))
        self.assertEqual(
            sorted(steps),
            sorted(self._schema()["properties"]["steps"]["propertyNames"]["enum"]))

    def test_a_negative_fix_loops_is_refused(self):
        """The schema gives fix_loops minimum 0."""
        result = self.run_script("pipeline-step.py",
            "--ticket", self.ticket_id, "--skill", "test", "--status", "in_progress",
            "--set", "fix_loops=-2")
        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertIn("non-negative", result.stderr)


class TestSkillProseContractTest(unittest.TestCase):
    """AC-1 ships as prose in test/SKILL.md; without these it could be deleted
    or reworded with the suite still green (repo precedent:
    tests/acs/test_ship_fix_retest_loop.py)."""

    def setUp(self):
        self.body = read(os.path.join(PLUGIN, "skills", "test", "SKILL.md"))

    def test_the_green_path_records_the_step_via_the_cli(self):
        window = re.search(r"(?s)Every suite in the run-set green.*?```bash(.*?)```", self.body)
        self.assertIsNotNone(window, "the green recording path must be documented")
        block = window.group(1)
        self.assertIn("pipeline-step.py", block)
        self.assertIn("--status completed", block)
        self.assertNotIn("--only-if-present", block,
                         "the green path must be able to OPEN the gate")

    def test_the_failure_path_carries_only_if_present(self):
        window = re.search(r"(?s)A suite failed.*?```bash(.*?)```", self.body)
        self.assertIsNotNone(window)
        self.assertIn("--only-if-present", window.group(1))

    def test_every_cli_invocation_is_runnable_as_written(self):
        """hooks/scripts/ is not on PATH: a bare `pipeline-step.py ...` copied
        from a fenced block is 'command not found'."""
        assert_invocations_are_runnable(self, self.body)

    def test_only_if_present_is_justified_by_a_reachable_case(self):
        """It used to cite a standing run — which never reaches this section at
        all, per the section's own scoping sentence."""
        window = re.search(r"(?s)`--only-if-present` on the failure path.{0,600}", self.body)
        self.assertIsNotNone(window)
        self.assertIsNotNone(re.search(r"(?i)direct", window.group(0)),
                             "the justification must name the direct --for-ticket case")

    def test_the_zero_run_set_and_error_paths_are_defined(self):
        self.assertIsNotNone(re.search(r"(?i)\*\*Zero run set", self.body))
        self.assertIsNotNone(re.search(r"(?i)non-zero `pipeline-step\.py` exit", self.body))


class ShipProseContractTest(unittest.TestCase):
    def setUp(self):
        self.body = read(os.path.join(PLUGIN, "skills", "ship", "SKILL.md"))

    def test_ship_writes_the_ledger_through_the_cli_not_embedded_python(self):
        self.assertIn("pipeline-step.py", self.body)
        self.assertNotIn('update_pipeline(..., "test"', self.body,
                         "the operative steps must not still mandate inline update_pipeline")

    def test_every_cli_invocation_is_runnable_as_written(self):
        assert_invocations_are_runnable(self, self.body)


class DocsSyncGateRemedyTest(AcsWorkspaceCase):
    """The gate's own error message must name a command that can open it."""

    @property
    def repo_id(self):
        return lib.build_context(self.repo)["repo_id"]

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
