"""MAR-529: the executor's file map is enforced, not requested.

"Mutate ONLY the files in your task's file map" was a bullet in the executor
charter. Plugin agents cannot carry frontmatter hooks, so the enforcement point
is the plugin's own PreToolUse hook, keyed on the active agent MAR-528's
SubagentStart recorded.

SCOPE, stated here as plainly as in the module: the guard checks a write against
the UNION of the iteration's declared task file maps, not against the one task
the running executor was given. Per-task binding is not achievable with what
Claude Code provides — neither SubagentStart nor PreToolUse carries a task
index, and parallel executors of one agent_type run at once, so there is nothing
to bind an agent to its task by. The union still enforces the property that
actually goes wrong: an executor wandering outside the PLAN. Disjointness
BETWEEN tasks stays the coordinator's parallel-vs-sequential decision.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRIPTS = os.path.join(REPO_ROOT, "plugins", "acs", "hooks", "scripts")
HOOKS_JSON = os.path.join(REPO_ROOT, "plugins", "acs", "hooks", "hooks.json")
CODE_EXECUTOR = os.path.join(REPO_ROOT, "plugins", "acs", "agents", "code-executor.md")
CODE_SKILL = os.path.join(REPO_ROOT, "plugins", "acs", "skills", "code", "SKILL.md")
sys.path.insert(0, SCRIPTS)

import acs_lib as lib  # noqa: E402

sys.path.insert(0, os.path.join(REPO_ROOT, "tests", "acs"))
from acs_case import AcsWorkspaceCase  # noqa: E402


class PathNormalizationTest(unittest.TestCase):
    """The plan writes repo-relative paths; a hook payload carries absolute
    ones. Both have to compare equal or the guard is decorative."""

    def test_relative_forms_collapse_to_one(self):
        for raw, expected in (("./src/a.py", "src/a.py"), ("src/a.py", "src/a.py"),
                              ("src\\a.py", "src/a.py"), ("  src/a.py  ", "src/a.py"),
                              ("/src/a.py", "src/a.py"), (None, ""), ("", "")):
            with self.subTest(raw=raw):
                self.assertEqual(lib.normalize_repo_path(raw), expected)

    def test_a_declared_directory_covers_what_is_under_it(self):
        """Plans write both forms — `docs/api/` and `docs/api/import.md` — and
        the guard should not care which."""
        tasks = {"1": ["docs/api/", "src/a.py"]}
        self.assertTrue(lib.path_in_filemap("docs/api/import.md", tasks))
        self.assertTrue(lib.path_in_filemap("src/a.py", tasks))
        self.assertFalse(lib.path_in_filemap("docs/apiary/x.md", tasks),
                         "a prefix match must not leak into a sibling directory")

    def test_an_absolute_path_is_resolved_against_the_checkout(self):
        root = tempfile.mkdtemp(prefix="acs-test-")
        self.addCleanup(shutil.rmtree, root, True)
        self.assertTrue(lib.path_in_filemap(
            os.path.join(root, "src", "a.py"), {"1": ["src/a.py"]}, root))
        self.assertFalse(lib.path_in_filemap(
            os.path.join(root, "src", "b.py"), {"1": ["src/a.py"]}, root))

    def test_a_path_outside_the_checkout_is_never_in_the_map(self):
        root = tempfile.mkdtemp(prefix="acs-test-")
        self.addCleanup(shutil.rmtree, root, True)
        self.assertFalse(lib.path_in_filemap("/etc/passwd", {"1": ["src/a.py"]}, root))

    def test_an_empty_map_matches_nothing(self):
        self.assertFalse(lib.path_in_filemap("src/a.py", {}))
        self.assertFalse(lib.path_in_filemap("src/a.py", None))


class FileMapGuardCase(AcsWorkspaceCase):

    def setUp(self):
        super().setUp()
        self.ticket = self.new_ticket("Ship the thing", "task")
        self.tdir_path = self.tdir(self.ticket)
        out = self.start("code", self.ticket)
        self.assertEqual(out.returncode, 0, out.stderr)

    def declare(self, *files, **kw):
        args = ["filemap", "set", "--task", str(kw.get("task", 1)),
                "--iteration", str(kw.get("iteration", 1))]
        for path in files:
            args += ["--file", path]
        out = self.run_script("acs.py", *args)
        self.assertEqual(out.returncode, 0, out.stderr)
        return json.loads(out.stdout)

    def spawn_executor(self, agent_id="a-1", agent_type="acs:code-executor"):
        out = self.hook("subagent-start", {"cwd": self.repo, "agent_id": agent_id,
                                           "agent_type": agent_type})
        self.assertEqual(out.returncode, 0, out.stderr)

    def hook(self, mode, payload):
        return subprocess.run(
            [sys.executable, os.path.join(SCRIPTS, "dispatch.py"), mode],
            input=json.dumps(payload), capture_output=True, text=True, cwd=self.repo)

    def write_attempt(self, path, tool="Write"):
        key = lib.WRITE_TOOL_PATH_KEYS[tool]
        return self.hook("file-map", {"cwd": self.repo, "tool_name": tool,
                                      "tool_input": {key: path}})


class GuardTest(FileMapGuardCase):

    def test_an_in_map_write_is_allowed(self):
        self.declare("src/a.py", "tests/test_a.py")
        self.spawn_executor()
        self.assertEqual(self.write_attempt("src/a.py").returncode, 0)

    def test_an_out_of_map_write_is_denied_with_the_needs_input_instruction(self):
        self.declare("src/a.py", "tests/test_a.py")
        self.spawn_executor()
        out = self.write_attempt("src/somewhere_else.py")
        self.assertEqual(out.returncode, 2)
        self.assertIn("src/somewhere_else.py", out.stderr)
        self.assertIn("outside this task's file map", out.stderr)
        self.assertIn("needs_input", out.stderr)
        # The denial names what WAS declared, so the executor can say what it needs.
        self.assertIn("src/a.py", out.stderr)
        self.assertIn("tests/test_a.py", out.stderr)

    def test_with_no_executor_active_the_guard_does_not_apply(self):
        """The coordinator, the planner and the verifier all legitimately write
        outside any task's file map."""
        self.declare("src/a.py")
        self.assertEqual(self.write_attempt("anything.py").returncode, 0)

    def test_a_planner_or_verifier_never_triggers_it(self):
        self.declare("src/a.py")
        for role in ("planner", "verifier"):
            with self.subTest(role=role):
                self.spawn_executor(agent_id="a-%s" % role,
                                    agent_type="acs:code-%s" % role)
                self.assertEqual(self.write_attempt("anything.py").returncode, 0)

    def test_an_undeclared_map_does_not_block_work(self):
        """A TRIVIAL lane runs no planner and declares nothing. The rule exists
        to stop scope creep, not to stop work the plan never had an opinion
        about — so an undeclared map fails OPEN."""
        self.spawn_executor()
        self.assertEqual(self.write_attempt("anything.py").returncode, 0)

    def test_the_union_of_the_declared_tasks_is_what_is_enforced(self):
        self.declare("src/a.py", task=1)
        self.declare("src/b.py", task=2)
        self.spawn_executor()
        for path in ("src/a.py", "src/b.py"):
            with self.subTest(path=path):
                self.assertEqual(self.write_attempt(path).returncode, 0)
        self.assertEqual(self.write_attempt("src/c.py").returncode, 2)

    def test_declaring_a_second_task_never_erases_the_first(self):
        self.declare("src/a.py", task=1)
        body = self.declare("src/b.py", task=2)
        self.assertEqual(sorted(body["tasks"]), ["1", "2"])

    def test_the_highest_declared_iteration_is_the_one_in_force(self):
        """Remediation executors get a fresh map; the earlier iteration's must
        not keep granting write access it no longer has a task for."""
        self.declare("src/a.py", iteration=1)
        self.declare("src/b.py", iteration=2)
        self.spawn_executor()
        self.assertEqual(self.write_attempt("src/b.py").returncode, 0)
        self.assertEqual(self.write_attempt("src/a.py").returncode, 2)

    def test_every_write_tool_is_covered(self):
        self.declare("src/a.py")
        self.spawn_executor()
        for tool in lib.WRITE_TOOL_PATH_KEYS:
            with self.subTest(tool=tool):
                self.assertEqual(self.write_attempt("src/a.py", tool=tool).returncode, 0)
                self.assertEqual(self.write_attempt("src/nope.py", tool=tool).returncode, 2)

    def test_a_read_tool_is_never_guarded(self):
        self.declare("src/a.py")
        self.spawn_executor()
        out = self.hook("file-map", {"cwd": self.repo, "tool_name": "Read",
                                     "tool_input": {"file_path": "anything.py"}})
        self.assertEqual(out.returncode, 0)

    def test_a_write_with_no_path_in_the_payload_is_allowed(self):
        self.declare("src/a.py")
        self.spawn_executor()
        out = self.hook("file-map", {"cwd": self.repo, "tool_name": "Write",
                                     "tool_input": {}})
        self.assertEqual(out.returncode, 0)

    def test_the_executors_own_phase_artifact_is_always_writable(self):
        """The charter says "plus your execute report", and that report lives in
        the partition — inside the workspace, never in the file map."""
        self.declare("src/a.py")
        self.spawn_executor()
        report = os.path.join(self.tdir_path, "phases", "code", "iter-1-execute.json")
        self.assertEqual(self.write_attempt(report).returncode, 0)

    def test_a_write_outside_any_acs_repo_is_allowed(self):
        tmp = tempfile.mkdtemp(prefix="acs-test-")
        self.addCleanup(shutil.rmtree, tmp, True)
        out = subprocess.run(
            [sys.executable, os.path.join(SCRIPTS, "dispatch.py"), "file-map"],
            input=json.dumps({"cwd": tmp, "tool_name": "Write",
                              "tool_input": {"file_path": "x.py"}}),
            capture_output=True, text=True, cwd=tmp)
        self.assertEqual(out.returncode, 0, out.stderr)

    def test_an_empty_payload_is_allowed(self):
        out = self.hook("file-map", {})
        self.assertEqual(out.returncode, 0, out.stderr)

    def test_a_guard_bug_never_blocks_a_write(self):
        """The guard rides on the lifecycle dispatcher, which fails OPEN. A
        bookkeeping bug that stops an executor writing costs more than the
        bookkeeping."""
        import importlib.util
        from unittest import mock
        spec = importlib.util.spec_from_file_location(
            "dispatch_guard_under_test", os.path.join(SCRIPTS, "dispatch.py"))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with mock.patch.object(module.acs_lib, "file_map_guard", side_effect=RuntimeError("x")):
            with mock.patch("sys.stderr"):
                self.assertEqual(module.run_lifecycle("file-map", {}), 0)


class FilemapCliTest(FileMapGuardCase):

    def test_show_reports_the_declaration_and_the_enforced_union(self):
        self.declare("src/a.py", task=1)
        self.declare("src/b.py", "docs/x.md", task=2)
        body = json.loads(self.run_script("acs.py", "filemap", "show").stdout)
        self.assertTrue(body["declared"])
        self.assertEqual(body["union"], ["docs/x.md", "src/a.py", "src/b.py"])
        self.assertEqual(body["tasks"]["2"], ["docs/x.md", "src/b.py"])

    def test_show_says_so_when_nothing_is_declared(self):
        body = json.loads(self.run_script("acs.py", "filemap", "show").stdout)
        self.assertFalse(body["declared"])
        self.assertEqual(body["union"], [])

    def test_set_refuses_an_empty_declaration(self):
        out = self.run_script("acs.py", "filemap", "set", "--task", "1")
        self.assertEqual(out.returncode, 2)
        self.assertIn("at least one file", out.stderr)

    def test_paths_can_come_from_a_file_or_stdin(self):
        listing = os.path.join(self.tmp, "files.txt")
        with open(listing, "w", encoding="utf-8") as fh:
            fh.write("src/a.py\n\ntests/test_a.py\n")
        body = json.loads(self.run_script(
            "acs.py", "filemap", "set", "--task", "1", "--files-from", listing).stdout)
        self.assertEqual(body["files"], ["src/a.py", "tests/test_a.py"])

        body = json.loads(self.run_script(
            "acs.py", "filemap", "set", "--task", "2", "--files-from", "-",
            stdin="src/b.py\n").stdout)
        self.assertEqual(body["files"], ["src/b.py"])

    def test_declared_paths_are_normalized_on_the_way_in(self):
        body = self.declare("./src/a.py", "src/a.py", "/src/a.py")
        self.assertEqual(body["files"], ["src/a.py"])


class RegistrationAndProseTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        with open(HOOKS_JSON, encoding="utf-8") as fh:
            cls.hooks = json.load(fh)
        with open(CODE_EXECUTOR, encoding="utf-8") as fh:
            cls.executor = fh.read()
        with open(CODE_SKILL, encoding="utf-8") as fh:
            cls.skill = fh.read()

    def _guard_entry(self):
        for entry in self.hooks["hooks"]["PreToolUse"]:
            if entry.get("matcher") != "Skill":
                return entry
        return None

    def test_the_guard_is_registered_on_the_write_tools(self):
        entry = self._guard_entry()
        self.assertIsNotNone(entry, "PreToolUse must carry a second, write-tool entry")
        self.assertEqual(set(entry["matcher"].split("|")), set(lib.WRITE_TOOL_PATH_KEYS))
        self.assertTrue(entry["hooks"][0]["command"].endswith('dispatch.py" file-map'))

    def test_the_gate_entry_is_untouched(self):
        gate = [e for e in self.hooks["hooks"]["PreToolUse"] if e.get("matcher") == "Skill"]
        self.assertEqual(len(gate), 1)
        self.assertTrue(gate[0]["hooks"][0]["command"].endswith('dispatch.py" pre'))

    def test_the_prose_rule_is_one_sentence(self):
        line = [l for l in self.executor.splitlines()
                if l.startswith("- Mutate ONLY the files")]
        self.assertEqual(len(line), 1)
        rule = self.executor.split("- Mutate ONLY the files", 1)[1].split("\n- ", 1)[0]
        self.assertEqual(rule.count("."), 1, "the rule is one sentence: %r" % rule)

    def test_the_prose_still_names_the_escape_hatch_and_who_adjusts_the_map(self):
        self.assertIn("needs_input", self.executor)
        self.assertIn("coordinator adjusts the file map", self.executor)

    def test_the_skill_tells_the_coordinator_to_declare_the_map(self):
        self.assertIn("filemap set", self.skill)
        self.assertIn("an undeclared map means no enforcement at all", self.skill)


if __name__ == "__main__":
    unittest.main()
