"""Behavior tests for acs_lib.py's hook entry points and post-merge lifecycle
helpers.

Originating ticket: MAR-173. run_pre's malformed-stdin fallback, tracker-warning
emission, and fail-closed-on-unexpected-exception arms; _read_result_from_argv's
missing/non-object --result-file, invalid-stdin-JSON, --status/--stop-reason
flags, and valid-file arms; _epic_auto_done's no-parent, no-children,
sibling-not-done, and parent-ticket-unreadable returns; _archive_partition's
destination-suffix-on-collision arm; _clear_pointers_for_ticket's
missing-sessions-dir, non-.json-skip, and unlink-OSError-swallow arms;
run_post's context-cannot-be-built, ticket-unresolved, and absent-partition
exits; and session_end's uninitialized-repo, no-pointer, absent-partition, and
foreign-checkout-lock returns were exercised by no test.

Safety (Risk R1): run_pre, run_post, and _read_result_from_argv all resolve a
cwd from the process (os.getcwd() or payload["cwd"]); session_end does too.
Every call into these four is therefore driven as a subprocess via
AcsWorkspaceCase.run_script()/.pre() (cwd=self.repo, an isolated workspace) --
never in-process, which would resolve this repo's own real acs workspace.
Only _epic_auto_done, _archive_partition, and _clear_pointers_for_ticket are
called in-process, and only with a hand-built ctx touching
ctx["workspace"]/ctx["repo_id"], never the process cwd.
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
sys.path.insert(0, SCRIPTS)

import acs_lib as lib  # noqa: E402

sys.path.insert(0, os.path.join(REPO_ROOT, "tests", "acs"))
import acs_case  # noqa: E402
from acs_case import AcsWorkspaceCase  # noqa: E402


class TestRunPre(AcsWorkspaceCase):
    """run_pre: malformed-stdin fallback, tracker warning, fail-closed."""

    def test_malformed_stdin_treated_as_empty_payload(self):
        """1857-1858: invalid JSON on stdin is treated as an empty payload
        (cwd falls back to the process cwd) rather than crashing the hook."""
        result = self.run_script("pre-code.py", stdin="{not json")
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("blocked", result.stderr)

    def test_tracker_warning_emitted_when_gh_missing(self):
        """1864: tracker.provider=github with no gh on PATH writes a warning
        to stderr before the gate runs -- it never blocks (gate_create_ticket
        is an unconditional pass)."""
        self.write_settings({
            "ticket_prefix": "SHOP", "test_coverage_percent": 90,
            "tracker": {"provider": "github"},
        })
        bin_dir = os.path.join(self.tmp, "bin")
        os.makedirs(bin_dir)
        env = acs_case.fake_gh(bin_dir, None)
        result = self.run_script("pre-create-ticket.py",
                                 stdin=json.dumps({"cwd": self.repo}), env=env)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("tracker sync will fail", result.stderr)

    def test_unexpected_exception_fails_closed(self):
        """1869-1871: a non-GateError exception inside the gate (a list
        tool_input makes _resolve_ticket_for_gate's dict .get() raise
        AttributeError) still exits 2 -- a gating system must fail closed."""
        payload = json.dumps({"cwd": self.repo, "tool_input": ["not", "a", "dict"]})
        result = self.run_script("pre-code.py", stdin=payload)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("unexpected error in gate", result.stderr)


class TestReadResultFromArgv(AcsWorkspaceCase):
    """_read_result_from_argv via post-code.py: --result-file, stdin JSON,
    and the --status/--stop-reason convenience flags."""

    def test_missing_and_non_object_result_file(self):
        """1890-1893: a --result-file that is missing, or whose JSON is not
        an object, exits 1 with a diagnostic naming the path."""
        missing = os.path.join(self.tmp, "does-not-exist.json")
        result = self.run_script("post-code.py", "--result-file", missing)
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn(missing, result.stderr)

        not_object = os.path.join(self.tmp, "list-result.json")
        with open(not_object, "w") as fh:
            json.dump([1, 2, 3], fh)
        result = self.run_script("post-code.py", "--result-file", not_object)
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn(not_object, result.stderr)

    def test_invalid_json_on_stdin(self):
        """1900-1902: invalid JSON piped on stdin (no --result-file) exits 1."""
        result = self.run_script("post-code.py", stdin="{not valid json")
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("invalid JSON", result.stderr)

    def test_status_and_stop_reason_flags_persisted(self):
        """1904: --status overrides result['status']; 1906: --stop-reason
        sets result['stop_reason'] -- both persisted into code-state.json."""
        ticket = self.new_ticket("Flag-driven post", "task")
        result = self.run_script(
            "post-code.py", "--ticket", ticket, "--status", "failed",
            "--stop-reason", "boom", stdin="")
        self.assertEqual(result.returncode, 0, result.stderr)
        state = lib.load_state(self.tdir(ticket), "code")
        self.assertEqual(state["runs"][-1]["status"], "failed")
        self.assertEqual(state["runs"][-1]["stop_reason"], "boom")

    def test_valid_result_file_used_when_partition_is_absent(self):
        """1894: a valid --result-file's JSON object becomes the result dict
        (no error, parsing falls through to it). Doubles as run_post's
        1976-1977 absent-partition exit: --ticket resolves the id directly,
        but that ticket was never created, so no partition exists for it."""
        result_file = os.path.join(self.tmp, "result.json")
        with open(result_file, "w") as fh:
            json.dump({"status": "completed"}, fh)
        result = self.run_script(
            "post-code.py", "--ticket", "SHOP-999", "--result-file", result_file)
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("no active partition", result.stderr)


class TestRunPostExits(AcsWorkspaceCase):
    """run_post's early exit-1 arms, ahead of any state mutation."""

    def test_exits_when_context_cannot_be_built(self):
        """1966-1968: run_post exits 1 (not a traceback) when build_context
        raises -- an uninitialized repo. HOME is isolated to a temp dir so a
        real ~/.acs/settings.json on the runner's machine can't mask this."""
        plain = os.path.join(self.tmp, "no-acs")
        os.makedirs(plain)
        subprocess.run(["git", "init", "-q", plain], check=True)
        fake_home = os.path.join(self.tmp, "fake-home")
        os.makedirs(fake_home)
        env = dict(os.environ, HOME=fake_home)
        result = self.run_script("post-code.py", cwd=plain, env=env, stdin="")
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("no .acs/settings.json", result.stderr)

    def test_exits_when_ticket_cannot_be_resolved(self):
        """1972-1973: run_post exits 1 when no ticket id can be resolved (no
        --ticket, no session pointer, and the fixture's branch is not a
        <PREFIX>-N form)."""
        result = self.run_script("post-code.py", stdin="")
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("could not resolve the ticket id", result.stderr)


class TestEpicAutoDone(unittest.TestCase):
    """_epic_auto_done's no-parent (1915), parent-has-no-children (1920),
    sibling-not-done (1924-1926), and parent-ticket.json-unreadable (1932)
    returns. Driven in-process with a hand-built ctx touching only
    ctx["workspace"]/ctx["repo_id"] -- never the process cwd (Risk R1)."""

    def setUp(self):
        self.ws = tempfile.mkdtemp(prefix="acs-test-")
        self.addCleanup(shutil.rmtree, self.ws, True)
        self.ctx = {"workspace": self.ws, "repo_id": "acme-shop"}

    def test_returns_none_when_no_parent(self):
        self.assertIsNone(lib._epic_auto_done(self.ctx, {"id": "SHOP-2"}))

    def test_returns_none_when_parent_has_no_children(self):
        parent_dir = lib.ticket_dir(self.ws, "acme-shop", "SHOP-1")
        os.makedirs(parent_dir)
        lib.save_ticket(parent_dir, lib.new_ticket_doc("SHOP-1", "Epic", "epic"))
        self.assertIsNone(
            lib._epic_auto_done(self.ctx, {"id": "SHOP-2", "parent": "SHOP-1"}))

    def test_returns_none_when_sibling_not_done(self):
        parent_dir = lib.ticket_dir(self.ws, "acme-shop", "SHOP-1")
        os.makedirs(parent_dir)
        lib.save_ticket(parent_dir, lib.new_ticket_doc(
            "SHOP-1", "Epic", "epic", children=["SHOP-2", "SHOP-3"]))
        lib.write_json(lib.index_path(self.ws, "acme-shop"),
                       {"tickets": {"SHOP-3": {"status": "open"}}})
        self.assertIsNone(
            lib._epic_auto_done(self.ctx, {"id": "SHOP-2", "parent": "SHOP-1"}))

    def test_returns_none_when_parent_ticket_json_unreadable(self):
        # The partition directory exists (find_ticket_partition resolves it),
        # but it has no ticket.json -- load_ticket(pdir) is None, so children
        # must come from the index instead, and the final `if parent_ticket`
        # check falls through to the last `return None`.
        parent_dir = lib.ticket_dir(self.ws, "acme-shop", "SHOP-1")
        os.makedirs(parent_dir)
        lib.write_json(lib.index_path(self.ws, "acme-shop"),
                       {"tickets": {"SHOP-1": {"children": ["SHOP-2"]}}})
        self.assertIsNone(
            lib._epic_auto_done(self.ctx, {"id": "SHOP-2", "parent": "SHOP-1"}))


class TestArchivePartition(unittest.TestCase):
    """_archive_partition suffixes the destination with a timestamp when an
    archive directory of that name already exists (1940). In-process; touches
    only ctx["workspace"]/ctx["repo_id"], never the process cwd (Risk R1)."""

    def setUp(self):
        self.ws = tempfile.mkdtemp(prefix="acs-test-")
        self.addCleanup(shutil.rmtree, self.ws, True)
        self.ctx = {"workspace": self.ws, "repo_id": "acme-shop"}

    def test_suffixes_destination_when_archive_dir_exists(self):
        dest_root = lib.archive_dir(self.ws, "acme-shop")
        os.makedirs(dest_root)
        conflicting = os.path.join(dest_root, "SHOP-1")
        os.makedirs(conflicting)
        with open(os.path.join(conflicting, "marker.txt"), "w") as fh:
            fh.write("already archived")

        tdir = os.path.join(self.ws, "acme-shop", "SHOP-1")
        os.makedirs(tdir)
        with open(os.path.join(tdir, "ticket.json"), "w") as fh:
            fh.write("{}")

        dest = lib._archive_partition(self.ctx, tdir, "SHOP-1")

        self.assertNotEqual(dest, conflicting)
        self.assertTrue(dest.startswith(conflicting))
        self.assertTrue(os.path.isfile(os.path.join(dest, "ticket.json")))
        self.assertTrue(os.path.isfile(os.path.join(conflicting, "marker.txt")))


class TestClearPointersForTicket(unittest.TestCase):
    """_clear_pointers_for_ticket's missing-sessions-dir return (1948),
    non-.json skip (1951), and unlink OSError swallow (1956-1957). In-process;
    touches only ctx["workspace"]/ctx["repo_id"] (Risk R1)."""

    def setUp(self):
        self.ws = tempfile.mkdtemp(prefix="acs-test-")
        self.addCleanup(shutil.rmtree, self.ws, True)
        self.ctx = {"workspace": self.ws, "repo_id": "acme-shop"}

    def test_returns_early_when_sessions_dir_missing(self):
        # No exception is the assertion: sessions_dir() was never created.
        lib._clear_pointers_for_ticket(self.ctx, "SHOP-1")

    def test_skips_non_json_entries_and_swallows_unlink_oserror(self):
        sdir = lib.sessions_dir(self.ws, "acme-shop")
        os.makedirs(sdir)
        stray = os.path.join(sdir, "notes.txt")
        with open(stray, "w") as fh:
            fh.write("not a pointer")
        target = os.path.join(sdir, "checkout-a.json")
        lib.write_json(target, {"ticket_id": "SHOP-1"})

        original_read_json = lib.read_json

        def shim(path):
            # Race simulation: the file disappears between this read and the
            # function's own os.unlink call below.
            data = original_read_json(path)
            if path == target:
                try:
                    os.unlink(path)
                except OSError:
                    pass
            return data

        lib.read_json = shim
        try:
            lib._clear_pointers_for_ticket(self.ctx, "SHOP-1")
        finally:
            lib.read_json = original_read_json

        self.assertTrue(os.path.isfile(stray))  # non-.json entry: untouched
        self.assertFalse(os.path.isfile(target))  # removed by the shim's race



class TestSessionEndEntryPoint(AcsWorkspaceCase):
    """session_end via `dispatch.py session-end` -- always subprocess-driven
    (Risk R1): it reads payload["cwd"] or os.getcwd(), so an in-process call
    from inside this repo's own suite could resolve the operator's real
    workspace instead of the fixture's isolated one."""

    def _session_end(self, cwd, env=None):
        return self.run_script("dispatch.py", "session-end",
                               stdin=json.dumps({"cwd": cwd}), env=env)

    def test_uninitialized_repo_returns_quietly(self):
        """2037-2038: build_context's GateError is swallowed -- nothing to
        clean up for a repo that never ran /acs:init. HOME is isolated so a
        real ~/.acs/settings.json on the runner's machine can't mask this."""
        plain = os.path.join(self.tmp, "no-acs")
        os.makedirs(plain)
        subprocess.run(["git", "init", "-q", plain], check=True)
        fake_home = os.path.join(self.tmp, "fake-home")
        os.makedirs(fake_home)
        result = self._session_end(plain, env=dict(os.environ, HOME=fake_home))
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_no_session_pointer_returns_quietly(self):
        """2041: an initialized repo with no session pointer file yet (no
        skill has started in this checkout) exits quietly."""
        result = self._session_end(self.repo)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_archived_or_absent_partition_returns_quietly(self):
        """2045: the pointer resolves a ticket id, but no partition exists
        for it (never created, and not archived either)."""
        ckid = lib.checkout_id(self.repo)
        lib.write_json(lib.pointer_path(self.ws, "acme-shop", ckid),
                       {"ticket_id": "SHOP-999"})
        result = self._session_end(self.repo)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_foreign_checkout_lock_returns_quietly(self):
        """2048: the partition exists and its lock belongs to a different
        checkout_id -- session_end must not touch another session's run."""
        ticket = self.new_ticket("Locked elsewhere", "task")
        tdir = self.tdir(ticket)
        ckid = lib.checkout_id(self.repo)
        lib.write_json(lib.pointer_path(self.ws, "acme-shop", ckid),
                       {"ticket_id": ticket})
        lib.write_json(lib.lock_path(tdir), {
            "checkout_id": "some-other-checkout-deadbeef",
            "pid": 1, "hostname": "elsewhere", "created_at": lib.now_iso(),
        })
        result = self._session_end(self.repo)
        self.assertEqual(result.returncode, 0, result.stderr)
        lock = lib.read_json(lib.lock_path(tdir))
        self.assertEqual(lock["checkout_id"], "some-other-checkout-deadbeef")
