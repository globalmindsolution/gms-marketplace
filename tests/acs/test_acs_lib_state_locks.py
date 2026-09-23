"""Behavior tests for acs_lib's state files, ticket ledger, locking, and
context-resolution helpers.

Originating ticket: MAR-173. resolve_ticket_id's pointer-file and branch-name
fallback arms, last_run_status's absent/empty/non-list-runs arm, finalize_run's
invalid-status guard and no-in-progress-run synthesis and findings/errors
persistence, record_escalation_event's no-run-entry guard, allocate_ticket_id's stale-guard removal / live-guard wait /
own-guard-release OSError swallow, lock_is_stale's PermissionError and
foreign-host-age arms, check_lock's re-entrant arm, release_lock's
refuse-another-checkout arm, and build_context's two GateError arms were
exercised by no test.

MAR-2 adds: the worktree-sharing guarantee (design.md's "Concurrency &
locking" NFR) -- default_state_root and repo_partition_id resolve identically
from a linked worktree and its main checkout, checkout_id still differs, and
a lock file written from one side is visible at the same path from the other.
"""

import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRIPTS = os.path.join(REPO_ROOT, "plugins", "acs", "hooks", "scripts")
sys.path.insert(0, SCRIPTS)

import acs_lib as lib  # noqa: E402

sys.path.insert(0, os.path.join(REPO_ROOT, "tests", "acs"))
from acs_case import AcsWorkspaceCase  # noqa: E402


def _mkrepo(parent, name):
    """A real (non-bare) git repo, no remote configured."""
    path = os.path.join(parent, name)
    os.makedirs(path)
    subprocess.run(["git", "init", "-q", path], check=True, capture_output=True)
    return path


class TestResolveTicketId(AcsWorkspaceCase):
    """1022: resolves from the session pointer file when present; 1025: falls
    back to the branch name when no pointer exists."""

    def test_resolves_from_session_pointer_file(self):
        ckid = lib.checkout_id(self.repo)
        pointer = lib.pointer_path(self.ws, "acme-shop", ckid)
        lib.write_json(pointer, {"run_id": "SHOP-77"})
        result = lib.resolve_ticket_id(self.repo, {"ticket_prefix": "SHOP"}, self.ws, "acme-shop")
        self.assertEqual(result, ("SHOP-77", "pointer"))

    def test_resolves_from_branch_name_when_no_pointer(self):
        # `git rev-parse --abbrev-ref HEAD` fails on an unborn branch, so an
        # initial commit is required before the branch name is resolvable —
        # scope the identity to this repo so the test never depends on the
        # runner's global git config.
        subprocess.run(["git", "-C", self.repo, "config", "user.email", "acs-test@example.com"],
                        check=True, capture_output=True)
        subprocess.run(["git", "-C", self.repo, "config", "user.name", "acs-test"],
                        check=True, capture_output=True)
        subprocess.run(["git", "-C", self.repo, "commit", "--allow-empty", "-q", "-m", "init"],
                        check=True, capture_output=True)
        subprocess.run(["git", "-C", self.repo, "checkout", "-b", "SHOP-42-fix-thing"],
                        check=True, capture_output=True)
        result = lib.resolve_ticket_id(self.repo, {"ticket_prefix": "SHOP"}, self.ws, "acme-shop")
        self.assertEqual(result, ("SHOP-42", "branch"))


class TestLastRunStatus(unittest.TestCase):
    """1055: returns None when runs is absent, empty, or not a list."""

    def setUp(self):
        self.tdir = tempfile.mkdtemp(prefix="acs-test-")
        self.addCleanup(shutil.rmtree, self.tdir, True)

    def test_returns_none_for_absent_empty_or_non_list_runs(self):
        lib.write_json(lib.state_path(self.tdir, "code"), {"skill": "code"})
        self.assertIsNone(lib.last_status(self.tdir, "code"))
        lib.write_json(lib.state_path(self.tdir, "code"), {"invocations": []})
        self.assertIsNone(lib.last_status(self.tdir, "code"))
        lib.write_json(lib.state_path(self.tdir, "code"), {"runs": "oops"})
        self.assertIsNone(lib.last_status(self.tdir, "code"))


class TestFinalizeRun(unittest.TestCase):
    """1083: raises ValueError for an invalid or in_progress final status;
    1086-1087: synthesizes a run entry when none was registered in_progress;
    1099/1101: persists findings/errors from the result document."""

    def setUp(self):
        self.tdir = tempfile.mkdtemp(prefix="acs-test-")
        self.addCleanup(shutil.rmtree, self.tdir, True)

    def test_raises_for_invalid_or_in_progress_status(self):
        with self.assertRaises(ValueError):
            lib.finalize_invocation(self.tdir, "code", "SHOP-1", {"status": "bogus"})
        with self.assertRaises(ValueError):
            lib.finalize_invocation(self.tdir, "code", "SHOP-1", {"status": "in_progress"})

    def test_raises_when_the_result_states_no_status(self):
        """finalize_run writes the status the next pre-hook gates on, so it is
        the last place a missing one can still be caught. It used to default to
        "completed" here -- refusing only at the CLI boundary left the silent
        default intact at the point of persistence, reachable by any in-process
        caller."""
        with self.assertRaises(ValueError) as ctx:
            lib.finalize_invocation(self.tdir, "code", "SHOP-1", {"stop_reason": "no status given"})
        self.assertIn("None", str(ctx.exception))
        self.assertEqual(lib.load_state(self.tdir, "code", "SHOP-1").get("runs", []), [])

    def test_synthesizes_run_entry_when_none_in_progress(self):
        state, entry = lib.finalize_invocation(self.tdir, "code", "SHOP-1", {"status": "completed"})
        self.assertEqual(entry["status"], "completed")
        self.assertEqual(len(state["invocations"]), 1)

    def test_persists_findings_and_errors_from_result(self):
        lib.append_invocation(self.tdir, "code", "SHOP-1")
        state, entry = lib.finalize_invocation(self.tdir, "code", "SHOP-1", {
            "status": "completed",
            "findings": [{"severity": "info", "summary": "x"}],
            "errors": ["boom"],
        })
        self.assertEqual(state["findings"], [{"severity": "info", "summary": "x"}])
        self.assertEqual(state["errors"], ["boom"])
        self.assertEqual(entry["status"], "completed")

    def test_records_no_usage_even_when_the_result_reports_some(self):
        """ADR-0104: nothing measures usage any more, and a coordinator's own
        `tokens`/`cost_usd` in `result` is legacy and ignored."""
        lib.append_invocation(self.tdir, "code", "SHOP-1")
        _state, entry = lib.finalize_invocation(self.tdir, "code", "SHOP-1", {
            "status": "completed",
            "tokens": {"input": 999999, "output": 999999},
            "cost_usd": 123.45,
        })
        for key in ("tokens", "role_usage", "model_usage", "cost_usd",
                    "session_id", "transcript_path"):
            self.assertNotIn(key, entry)


class TestRecordGuardEventWithoutARunTest(unittest.TestCase):
    """No run entry to attach the event to: report it, never raise.

    This used to be `record_escalation_event`, which raised ValueError here —
    the right answer for an audit write whose absence was itself the signal
    that a lane change went unrecorded. ADR-0095 retired escalations, and the
    one recorder left is `record_guard_event`, whose sole caller is the file-map
    guard's DENY path. That verdict must not depend on whether the recording
    succeeded, so a missing run entry returns False and the deny still stands."""

    def test_returns_false_without_existing_run_entry(self):
        tdir = tempfile.mkdtemp(prefix="acs-test-")
        self.addCleanup(shutil.rmtree, tdir, True)
        self.assertIs(
            lib.record_guard_event(tdir, "code", "SHOP-1", {"reason": "outside_map"}),
            False)

    def test_the_retired_escalation_recorder_is_gone(self):
        self.assertFalse(hasattr(lib, "record_escalation_event"))


class TestAllocateTicketId(unittest.TestCase):
    """1292-1296: removes a stale (>30s) guard file and proceeds; 1299-1300:
    waits out a live guard until it is released; 1311-1312: swallows an
    OSError when releasing its own guard. (1297-1298's getmtime-race arm is
    unreachable on POSIX without patching stdlib internals — Risk R5,
    permanently missed, budgeted separately.)"""

    def setUp(self):
        self.workspace = tempfile.mkdtemp(prefix="acs-test-")
        self.addCleanup(shutil.rmtree, self.workspace, True)
        # MAR-402: allocate_ticket_id now refuses an unreconciled partition;
        # seed a reconciled counters.json so these lock-interaction cases
        # exercise the lock, not the reconciliation gate.
        rdir = lib.repo_dir(self.workspace, "acme-shop")
        os.makedirs(rdir, exist_ok=True)
        lib.write_json(os.path.join(rdir, "counters.json"), {"next": 1, "reconciled": True})

    def test_removes_stale_guard_and_proceeds(self):
        rdir = lib.repo_dir(self.workspace, "acme-shop")
        guard = os.path.join(rdir, "counters.json.lock")
        open(guard, "w").close()
        old = time.time() - 60
        os.utime(guard, (old, old))
        result = lib.allocate_ticket_id(self.workspace, "acme-shop", "SHOP")
        self.assertEqual(result, "SHOP-1")

    def test_waits_out_a_live_guard_until_released(self):
        rdir = lib.repo_dir(self.workspace, "acme-shop")
        guard = os.path.join(rdir, "counters.json.lock")
        open(guard, "w").close()  # fresh mtime -> not stale, must be waited out

        def _release():
            if os.path.exists(guard):
                os.unlink(guard)

        timer = threading.Timer(0.15, _release)
        timer.start()
        try:
            result = lib.allocate_ticket_id(self.workspace, "acme-shop", "SHOP")
        finally:
            timer.cancel()
        # Risk R6: assert only the returned id, never an iteration count or elapsed time.
        self.assertEqual(result, "SHOP-1")

    def test_swallows_oserror_releasing_its_own_guard(self):
        rdir = lib.repo_dir(self.workspace, "acme-shop")
        guard = os.path.join(rdir, "counters.json.lock")
        original_write_json = lib.write_json

        def shim(path, data):
            # Unlink the guard out from under allocate_ticket_id before it
            # reaches its own release, forcing that release's os.unlink to
            # raise OSError.
            try:
                os.unlink(guard)
            except OSError:
                pass
            return original_write_json(path, data)

        # acs_lib is a package (MAR-522): acs_lib.step bound this name at import
        # time, so patching the facade would leave the real one in place and
        # this branch would go uncovered while the test still passed.
        with mock.patch.object(lib.step, "write_json", side_effect=shim):
            result = lib.allocate_ticket_id(self.workspace, "acme-shop", "SHOP")
        self.assertEqual(result, "SHOP-1")


class TestLockIsStale(unittest.TestCase):
    """1448-1449: a PermissionError from os.kill is treated as NOT stale (never
    pid 1, whose behavior differs for a root CI user); 1450: a foreign-host
    lock older than 24h is stale, a fresh one is not."""

    def test_permission_error_from_os_kill_is_not_stale(self):
        lock = {"hostname": socket.gethostname(), "pid": 424242, "created_at": lib.now_iso()}
        with mock.patch("os.kill", side_effect=PermissionError):
            self.assertFalse(lib.lock_is_stale(lock))

    def test_foreign_host_lock_stale_by_age_only(self):
        old_created = (datetime.now(timezone.utc) - timedelta(hours=25)).strftime("%Y-%m-%dT%H:%M:%SZ")
        fresh_created = lib.now_iso()
        self.assertTrue(lib.lock_is_stale({"hostname": "some-other-host", "created_at": old_created}))
        self.assertFalse(lib.lock_is_stale({"hostname": "some-other-host", "created_at": fresh_created}))


class TestCheckLock(unittest.TestCase):
    """1459: re-entrant (ok=True) when the lock's checkout_id matches the caller's."""

    def test_reentrant_for_same_checkout(self):
        tdir = tempfile.mkdtemp(prefix="acs-test-")
        self.addCleanup(shutil.rmtree, tdir, True)
        lib.write_json(lib.lock_path(tdir), {"checkout_id": "abc-123"})
        self.assertEqual(lib.check_lock(tdir, "abc-123"), (True, None))


class TestReleaseLock(unittest.TestCase):
    """1487: refuses (returns False, leaves the lock file in place) when the
    caller's checkout_id does not match the lock holder's."""

    def test_refuses_to_release_another_checkouts_lock(self):
        tmp = tempfile.mkdtemp(prefix="acs-test-")
        self.addCleanup(shutil.rmtree, tmp, True)
        repo = _mkrepo(tmp, "repo")
        tdir = tempfile.mkdtemp(prefix="acs-test-", dir=tmp)
        lib.write_json(lib.lock_path(tdir), {"checkout_id": "someone-elses-checkout"})
        result = lib.release_lock(tdir, cwd=repo)
        self.assertFalse(result)
        self.assertTrue(os.path.exists(lib.lock_path(tdir)))


class TestWorktreeSharedStateRoot(unittest.TestCase):
    """default_state_root/repo_partition_id are shared across a linked worktree,
    while checkout_id differs -- design.md's "Concurrency & locking" NFR."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="acs-test-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.main = _mkrepo(self.tmp, "main")
        subprocess.run(["git", "-C", self.main, "config", "user.email", "acs-test@example.com"],
                        check=True, capture_output=True)
        subprocess.run(["git", "-C", self.main, "config", "user.name", "acs-test"],
                        check=True, capture_output=True)
        subprocess.run(["git", "-C", self.main, "commit", "--allow-empty", "-q", "-m", "init"],
                        check=True, capture_output=True)
        self.worktree = os.path.join(self.tmp, "wt")
        subprocess.run(
            ["git", "-C", self.main, "worktree", "add", "-q", "-b", "wt-branch", self.worktree],
            check=True, capture_output=True,
        )

    def test_state_root_and_repo_id_are_identical_from_main_checkout_and_worktree(self):
        self.assertEqual(
            os.path.realpath(lib.default_state_root(self.main)),
            os.path.realpath(lib.default_state_root(self.worktree)),
        )
        self.assertEqual(lib.repo_partition_id(self.main), lib.repo_partition_id(self.worktree))

    def test_checkout_id_differs_between_main_checkout_and_worktree(self):
        self.assertNotEqual(lib.checkout_id(self.main), lib.checkout_id(self.worktree))

    def test_lock_written_from_one_checkout_is_visible_at_the_same_path_from_the_other(self):
        state_root_main = lib.default_state_root(self.main)
        state_root_wt = lib.default_state_root(self.worktree)
        repo_id = lib.repo_partition_id(self.main)
        tdir_main = lib.ticket_dir(state_root_main, repo_id, "SHOP-1")
        tdir_wt = lib.ticket_dir(state_root_wt, repo_id, "SHOP-1")
        self.assertEqual(tdir_main, tdir_wt)
        lib.write_json(lib.lock_path(tdir_main), {"checkout_id": lib.checkout_id(self.main)})
        self.assertTrue(os.path.exists(lib.lock_path(tdir_wt)))
        self.assertEqual(
            lib.read_json(lib.lock_path(tdir_wt))["checkout_id"], lib.checkout_id(self.main)
        )


class TestBuildContext(unittest.TestCase):
    """1505: raises GateError when no .acs/settings.json exists in any scope
    (user or project); 1509: raises GateError when the repo identity cannot be
    derived, once a settings file has been found. Both patch HOME to an
    isolated temp dir (mandatory: settings_files always consults
    ~/.acs/settings.json, so an unpatched HOME couples the test to whoever
    runs it)."""

    def test_raises_when_no_settings_file_found_anywhere(self):
        tmp = tempfile.mkdtemp(prefix="acs-test-")
        self.addCleanup(shutil.rmtree, tmp, True)
        repo = _mkrepo(tmp, "repo")
        fake_home = os.path.join(tmp, "home")
        os.makedirs(fake_home)
        with mock.patch.dict(os.environ, {"HOME": fake_home}):
            with self.assertRaises(lib.GateError) as ctx:
                lib.build_context(repo)
        self.assertIn("no .acs/settings.json found", str(ctx.exception))

    def test_raises_when_repo_identity_cannot_be_derived(self):
        tmp = tempfile.mkdtemp(prefix="acs-test-")
        self.addCleanup(shutil.rmtree, tmp, True)
        repo = _mkrepo(tmp, "repo")
        os.makedirs(os.path.join(repo, ".acs"))
        ws = os.path.join(tmp, "workspace")
        lib.write_json(os.path.join(repo, ".acs", "settings.json"),
                        {"ticket_prefix": "SHOP", "workspace_path": ws})
        fake_home = os.path.join(tmp, "home")
        os.makedirs(fake_home)
        # build_context lives in acs_lib.gates and bound repo_partition_id at
        # import time (MAR-522), so the stub has to replace THAT binding.
        original = lib.gates.repo_partition_id
        lib.gates.repo_partition_id = lambda cwd: None
        try:
            with mock.patch.dict(os.environ, {"HOME": fake_home}):
                with self.assertRaises(lib.GateError) as ctx:
                    lib.build_context(repo)
        finally:
            lib.gates.repo_partition_id = original
        self.assertIn("could not derive a repo identity", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
