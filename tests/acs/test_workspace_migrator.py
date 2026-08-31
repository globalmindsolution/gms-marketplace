"""Behavior tests for migrate_workspace.py's preflight, classification/copy,
idempotent re-run, and --dry-run behavior.

Originating ticket: MAR-3. Implements the design's Migrator contract
(MAR-1/design.md, Rollout/migration section): copies <old>/<repo-id>/ into
<new>/<repo-id>/ with a hard preflight (no live .lock, no in_progress run),
repo-level-file conflict-abort handling, idempotent ticket-partition resume,
and copy-then-verify-then-remove ordering. Fixtures mint tickets in-process
via acs_case.lib (never through new-ticket.py's subprocess) and drive
migrate_workspace.py's main() in-process via acs_case.run_main -- this seam
needs no live workspace and no subprocess for the script itself.
"""

import ast
import configparser
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

TESTS_ACS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TESTS_ACS)

import acs_case  # noqa: E402

MODULE_FILENAME = "migrate_workspace.py"
REPO_ID = "acme-shop"


class MigratorCase(unittest.TestCase):
    """Shared fixture: a throwaway git repo (repo_id resolves to acme-shop)
    plus separate old/new workspace roots, all removed on cleanup."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="acs-migrator-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.repo_root = os.path.join(self.tmp, "repo")
        os.makedirs(self.repo_root)
        subprocess.run(["git", "init", "-q", self.repo_root], check=True)
        subprocess.run(["git", "-C", self.repo_root, "remote", "add", "origin",
                        "https://github.com/acme/shop.git"], check=True)
        self.old_ws = os.path.join(self.tmp, "old-workspace")
        self.new_ws = os.path.join(self.tmp, "new-workspace")
        os.makedirs(self.old_ws)
        os.makedirs(self.new_ws)

    def run_migrator(self, dry_run=False, extra_args=()):
        mod = acs_case.load_module(MODULE_FILENAME)
        argv = ["--from", self.old_ws, "--to", self.new_ws, "--repo-root", self.repo_root]
        if dry_run:
            argv.append("--dry-run")
        argv = argv + list(extra_args)
        with acs_case.pushd(self.tmp):
            return acs_case.run_main(mod, argv)

    def old_repo_dir(self):
        return acs_case.lib.repo_dir(self.old_ws, REPO_ID)

    def new_repo_dir(self):
        return acs_case.lib.repo_dir(self.new_ws, REPO_ID)

    def mint_ticket(self, ticket_id, ws=None, archived=False, state=None):
        """Write a valid ticket.json partition (active or archived); an optional
        `state=(skill, status)` also writes a matching <skill>-state.json."""
        ws = ws or self.old_ws
        if archived:
            tdir = os.path.join(acs_case.lib.archive_dir(ws, REPO_ID), ticket_id)
        else:
            tdir = acs_case.lib.ticket_dir(ws, REPO_ID, ticket_id)
        os.makedirs(tdir, exist_ok=True)
        ticket = acs_case.lib.new_ticket_doc(ticket_id, ticket_id, "task",
                                             status="done" if archived else "open")
        acs_case.lib.save_ticket(tdir, ticket)
        if state:
            skill, status = state
            with open(os.path.join(tdir, "%s-state.json" % skill), "w", encoding="utf-8") as fh:
                json.dump({"skill": skill, "ticket_id": ticket_id,
                           "runs": [{"status": status}]}, fh)
        return tdir

    def write_repo_level(self, rel_path, content, ws=None):
        """Write a repo-level file (or a file inside a repo-level directory like
        sessions/ or test-runs/) at <ws>/<repo_id>/<rel_path>."""
        ws = ws or self.old_ws
        path = os.path.join(acs_case.lib.repo_dir(ws, REPO_ID), *rel_path.split("/"))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(content)
        return path

    def read(self, path):
        with open(path, encoding="utf-8") as fh:
            return fh.read()


class TestPreflight(MigratorCase):

    def test_lock_in_a_ticket_partition_aborts_exit_2_naming_the_lock_path(self):
        tdir = self.mint_ticket("MAR-1")
        lock_path = os.path.join(tdir, ".lock")
        with open(lock_path, "w", encoding="utf-8") as fh:
            fh.write("{}")
        code, out, err = self.run_migrator()
        self.assertEqual(code, 2)
        self.assertIn(lock_path, err)

    def test_lock_under_archive_partition_also_aborts(self):
        tdir = self.mint_ticket("MAR-2", archived=True)
        lock_path = os.path.join(tdir, ".lock")
        with open(lock_path, "w", encoding="utf-8") as fh:
            fh.write("{}")
        code, out, err = self.run_migrator()
        self.assertEqual(code, 2)
        self.assertIn(lock_path, err)

    def test_in_progress_last_run_aborts_naming_the_ticket_and_skill(self):
        self.mint_ticket("MAR-3", state=("code", "in_progress"))
        code, out, err = self.run_migrator()
        self.assertEqual(code, 2)
        self.assertIn("MAR-3", err)
        self.assertIn("code", err)

    def test_completed_last_run_does_not_abort(self):
        self.mint_ticket("MAR-4", state=("code", "completed"))
        code, out, err = self.run_migrator()
        self.assertEqual(code, 0, err)

    def test_counters_json_lock_guard_file_is_not_a_partition_lock(self):
        self.write_repo_level("counters.json.lock", "guard")
        code, out, err = self.run_migrator()
        self.assertEqual(code, 0, err)

    def test_preflight_abort_leaves_destination_empty_and_source_intact(self):
        tdir = self.mint_ticket("MAR-6")
        with open(os.path.join(tdir, ".lock"), "w", encoding="utf-8") as fh:
            fh.write("{}")
        code, out, err = self.run_migrator()
        self.assertEqual(code, 2)
        new_root = self.new_repo_dir()
        self.assertFalse(os.path.isdir(new_root))
        self.assertTrue(os.path.isfile(os.path.join(tdir, "ticket.json")))

    def test_no_force_or_allow_active_flag_is_accepted(self):
        self.mint_ticket("MAR-7")
        code, _out, _err = self.run_migrator(extra_args=["--force"])
        self.assertEqual(code, 2)
        code, _out, _err = self.run_migrator(extra_args=["--allow-active"])
        self.assertEqual(code, 2)


class TestSuccessfulMigration(MigratorCase):

    def test_ticket_partitions_land_at_the_destination_with_file_contents(self):
        tdir = self.mint_ticket("MAR-8")
        source_content = self.read(os.path.join(tdir, "ticket.json"))
        code, out, err = self.run_migrator()
        self.assertEqual(code, 0, err)
        dest = acs_case.lib.ticket_dir(self.new_ws, REPO_ID, "MAR-8")
        self.assertEqual(self.read(os.path.join(dest, "ticket.json")), source_content)

    def test_repo_level_files_land_at_the_destination(self):
        self.write_repo_level("counters.json", '{"n": 1}')
        self.write_repo_level("tickets-index.json", '{"tickets": []}')
        self.write_repo_level("metrics.json", '{"totals": {}}')
        code, out, err = self.run_migrator()
        self.assertEqual(code, 0, err)
        new_root = self.new_repo_dir()
        self.assertEqual(self.read(os.path.join(new_root, "counters.json")), '{"n": 1}')
        self.assertEqual(self.read(os.path.join(new_root, "tickets-index.json")),
                          '{"tickets": []}')
        self.assertEqual(self.read(os.path.join(new_root, "metrics.json")), '{"totals": {}}')

    def test_archive_partitions_land_at_the_destination(self):
        self.mint_ticket("MAR-10", archived=True)
        code, out, err = self.run_migrator()
        self.assertEqual(code, 0, err)
        dest = os.path.join(acs_case.lib.archive_dir(self.new_ws, REPO_ID), "MAR-10")
        self.assertTrue(os.path.isfile(os.path.join(dest, "ticket.json")))

    def test_old_repo_partition_is_removed_after_a_verified_copy(self):
        self.mint_ticket("MAR-11")
        code, out, err = self.run_migrator()
        self.assertEqual(code, 0, err)
        old_root = self.old_repo_dir()
        self.assertFalse(os.path.isdir(old_root))

    def test_sibling_repo_partitions_and_the_old_root_are_left_untouched(self):
        sibling_marker = os.path.join(self.old_ws, "other-repo", "counters.json")
        os.makedirs(os.path.dirname(sibling_marker))
        with open(sibling_marker, "w", encoding="utf-8") as fh:
            fh.write('{"n": 9}')
        self.mint_ticket("MAR-12")
        code, out, err = self.run_migrator()
        self.assertEqual(code, 0, err)
        self.assertTrue(os.path.isdir(self.old_ws))
        self.assertTrue(os.path.isfile(sibling_marker))

    def test_successful_run_exits_0_and_reports_what_it_moved(self):
        self.mint_ticket("MAR-13")
        code, out, err = self.run_migrator()
        self.assertEqual(code, 0, err)
        self.assertIn("MAR-13", out)


class TestRepoLevelFileConflicts(MigratorCase):

    def test_repo_level_file_absent_at_destination_is_copied(self):
        self.write_repo_level("counters.json", '{"a": 1}')
        code, out, err = self.run_migrator()
        self.assertEqual(code, 0, err)
        new_root = self.new_repo_dir()
        self.assertEqual(self.read(os.path.join(new_root, "counters.json")), '{"a": 1}')

    def test_byte_identical_repo_level_file_at_both_sides_is_left_as_is(self):
        self.write_repo_level("counters.json", '{"a": 1}', ws=self.old_ws)
        self.write_repo_level("counters.json", '{"a": 1}', ws=self.new_ws)
        code, out, err = self.run_migrator()
        self.assertEqual(code, 0, err)
        new_root = self.new_repo_dir()
        self.assertEqual(self.read(os.path.join(new_root, "counters.json")), '{"a": 1}')

    def test_differing_repo_level_file_aborts_exit_2_naming_that_file(self):
        self.write_repo_level("counters.json", '{"a": 1}', ws=self.old_ws)
        self.write_repo_level("counters.json", '{"a": 2}', ws=self.new_ws)
        code, out, err = self.run_migrator()
        self.assertEqual(code, 2)
        self.assertIn("counters.json", err)

    def test_conflict_abort_removes_nothing_from_the_source(self):
        self.write_repo_level("counters.json", '{"a": 1}', ws=self.old_ws)
        self.write_repo_level("counters.json", '{"a": 2}', ws=self.new_ws)
        code, out, err = self.run_migrator()
        self.assertEqual(code, 2)
        old_root = self.old_repo_dir()
        self.assertEqual(self.read(os.path.join(old_root, "counters.json")), '{"a": 1}')

    def test_sessions_files_follow_the_repo_level_rule_per_file(self):
        self.write_repo_level("sessions/a.json", '{"s": "a"}')
        self.write_repo_level("sessions/nested/b.json", '{"s": "b"}')
        code, out, err = self.run_migrator()
        self.assertEqual(code, 0, err)
        new_root = self.new_repo_dir()
        self.assertEqual(self.read(os.path.join(new_root, "sessions", "a.json")), '{"s": "a"}')
        self.assertEqual(self.read(os.path.join(new_root, "sessions", "nested", "b.json")),
                          '{"s": "b"}')

    def test_unenumerated_test_runs_directory_is_migrated_not_dropped(self):
        self.write_repo_level("test-runs/run1/results.json", '{"ok": true}')
        code, out, err = self.run_migrator()
        self.assertEqual(code, 0, err)
        new_root = self.new_repo_dir()
        self.assertEqual(self.read(os.path.join(new_root, "test-runs", "run1", "results.json")),
                          '{"ok": true}')


class TestIdempotentRerun(MigratorCase):

    def test_missing_old_repo_partition_reports_already_migrated_and_exits_0(self):
        code, out, err = self.run_migrator()
        self.assertEqual(code, 0, err)
        self.assertIn("already migrated", out)

    def test_ticket_present_at_both_sides_keeps_the_destination_copy(self):
        self.mint_ticket("MAR-21", ws=self.old_ws)
        dest_tdir = self.mint_ticket("MAR-21", ws=self.new_ws)
        with open(os.path.join(dest_tdir, "SENTINEL.txt"), "w", encoding="utf-8") as fh:
            fh.write("kept")
        code, out, err = self.run_migrator()
        self.assertEqual(code, 0, err)
        self.assertTrue(os.path.isfile(os.path.join(dest_tdir, "SENTINEL.txt")))

    def test_resumed_run_copies_the_remaining_tickets_then_removes_old(self):
        self.mint_ticket("MAR-22A", ws=self.old_ws)
        self.mint_ticket("MAR-22A", ws=self.new_ws)
        self.mint_ticket("MAR-22B", ws=self.old_ws)
        code, out, err = self.run_migrator()
        self.assertEqual(code, 0, err)
        dest_b = acs_case.lib.ticket_dir(self.new_ws, REPO_ID, "MAR-22B")
        self.assertTrue(os.path.isfile(os.path.join(dest_b, "ticket.json")))
        old_root = self.old_repo_dir()
        self.assertFalse(os.path.isdir(old_root))

    def test_running_twice_in_a_row_is_a_no_op_the_second_time(self):
        self.mint_ticket("MAR-23")
        code, out, err = self.run_migrator()
        self.assertEqual(code, 0, err)
        code, out, err = self.run_migrator()
        self.assertEqual(code, 0, err)
        self.assertIn("already migrated", out)


class TestCliContract(MigratorCase):

    def test_missing_required_arguments_exit_2(self):
        mod = acs_case.load_module(MODULE_FILENAME)
        with acs_case.pushd(self.tmp):
            code, out, err = acs_case.run_main(mod, ["--from", self.old_ws])
        self.assertEqual(code, 2)

    def test_unresolvable_repo_id_exits_2(self):
        nongit = os.path.join(self.tmp, "not-a-repo")
        os.makedirs(nongit)
        code, out, err = self.run_migrator(extra_args=["--repo-root", nongit])
        # the last --repo-root wins with argparse's default store action
        self.assertEqual(code, 2)
        self.assertIn("repo", err.lower())

    def test_dry_run_prints_the_plan_and_writes_nothing(self):
        self.mint_ticket("MAR-26")
        code, out, err = self.run_migrator(dry_run=True)
        self.assertEqual(code, 0, err)
        self.assertIn("MAR-26", out)
        new_root = self.new_repo_dir()
        self.assertFalse(os.path.isdir(new_root))
        old_root = self.old_repo_dir()
        self.assertTrue(os.path.isdir(old_root))

    def test_only_read_only_acs_lib_helpers_are_called(self):
        path = os.path.join(acs_case.SCRIPTS, MODULE_FILENAME)
        with open(path, encoding="utf-8") as fh:
            source = fh.read()
        tree = ast.parse(source)
        called = set()
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and isinstance(node.func.value, ast.Name) and node.func.value.id == "lib"):
                called.add(node.func.attr)
        allowed = {"repo_partition_id", "repo_dir", "archive_dir", "ticket_dir",
                   "sessions_dir", "read_json", "last_run_status"}
        forbidden = {"write_json", "update_index", "update_metrics", "acquire_lock",
                     "release_lock", "save_ticket", "finalize_run", "build_context"}
        self.assertTrue(called)
        self.assertTrue(called.issubset(allowed), called - allowed)
        self.assertFalse(called & forbidden, called & forbidden)

    def test_migrate_workspace_is_not_in_the_coveragerc_omit_list(self):
        cp = configparser.ConfigParser()
        cp.read(os.path.join(acs_case.REPO_ROOT, ".coveragerc"))
        entries = [line.strip() for line in cp.get("run", "omit").splitlines() if line.strip()]
        self.assertTrue(all(not entry.endswith("migrate_workspace.py") for entry in entries))


if __name__ == "__main__":
    unittest.main()
