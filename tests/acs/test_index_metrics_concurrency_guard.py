"""Tests for the O_EXCL guard on acs_lib's two repo-level read-modify-write
writers, update_index and update_metrics (D5.1(a)). Mirrors the arms already
proven for the identical spin-lock pattern in
tests/acs/test_acs_lib_state_locks.py::TestAllocateTicketId.
"""

import os
import shutil
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRIPTS = os.path.join(REPO_ROOT, "plugins", "acs", "hooks", "scripts")
sys.path.insert(0, SCRIPTS)

import acs_lib as lib  # noqa: E402


def _ticket(tid):
    return {"id": tid, "title": "t", "type": "task", "status": "open"}


class GuardDocstringHonestyTest(unittest.TestCase):
    """Finding 5: the docstring must name the bounded-spin fail-open fallback
    rather than claim an absolute guarantee the mechanism does not provide."""

    def test_docstring_names_the_bounded_spin_fallback(self):
        doc = lib._guarded_repo_write.__doc__ or ""
        self.assertIn("unguarded", doc)
        self.assertNotRegex(doc, r"never (drop|lose)")


class _GuardedWriterCaseMixin:

    """Shared arms for the O_EXCL guard around a repo-level read-modify-write.
    Subclasses set guard_name and implement _call()."""

    #: The acs_lib submodule whose read_json/write_json binding the writer under
    #: test calls. acs_lib is a package (MAR-522), and a name imported into a
    #: sibling binds at import time -- patching the facade would not reach it.
    MODULE = None

    guard_name = None

    def setUp(self):
        self.workspace = tempfile.mkdtemp(prefix="acs-test-")
        self.addCleanup(shutil.rmtree, self.workspace, True)
        self.rdir = lib.repo_dir(self.workspace, "acme-shop")

    def _guard_path(self):
        return os.path.join(self.rdir, self.guard_name)

    def _call(self, n=1):
        raise NotImplementedError

    def _landed(self, n=1):
        """Assert self._call(n)'s write actually reached its target file."""
        raise NotImplementedError

    def test_guard_file_held_during_read_modify_write(self):
        seen = {}
        original_write_json = self.MODULE.write_json

        def shim(path, data):
            seen["guard_exists"] = os.path.exists(self._guard_path())
            return original_write_json(path, data)

        with mock.patch.object(self.MODULE, "write_json", side_effect=shim):
            self._call()
        self.assertTrue(seen.get("guard_exists"))
        self.assertFalse(os.path.exists(self._guard_path()))

    def test_stale_guard_removed_and_proceeds(self):
        os.makedirs(self.rdir, exist_ok=True)
        guard = self._guard_path()
        open(guard, "w").close()
        old = time.time() - 60
        os.utime(guard, (old, old))
        self._call()
        self.assertFalse(os.path.exists(guard))

    def test_waits_out_live_guard_until_released(self):
        os.makedirs(self.rdir, exist_ok=True)
        guard = self._guard_path()
        open(guard, "w").close()  # fresh mtime -> not stale, must be waited out

        def _release():
            if os.path.exists(guard):
                os.unlink(guard)

        timer = threading.Timer(0.15, _release)
        timer.start()
        try:
            self._call()
        finally:
            timer.cancel()
        self.assertFalse(os.path.exists(guard))

    def test_swallows_oserror_releasing_own_guard(self):
        guard = self._guard_path()
        original_write_json = self.MODULE.write_json

        def shim(path, data):
            try:
                os.unlink(guard)
            except OSError:
                pass
            return original_write_json(path, data)

        with mock.patch.object(self.MODULE, "write_json", side_effect=shim):
            self._call()  # must not raise

    def test_proceeds_unguarded_when_the_guard_cannot_be_acquired(self):
        """Finding 5: mirrors allocate_ticket_id's pre-existing bounded-spin
        fail-open fallback -- a live (never-stale) foreign guard held for the
        whole call must not block the write forever, and the fallback must
        not steal the foreign guard file out from under its owner."""
        os.makedirs(self.rdir, exist_ok=True)
        guard = self._guard_path()
        open(guard, "w").close()  # fresh mtime -> never stale, held for the call

        with mock.patch("time.sleep"):
            self._call()

        self._landed()
        self.assertTrue(os.path.exists(guard), "fail-open must not unlink a foreign guard")


class UpdateIndexGuardTest(_GuardedWriterCaseMixin, unittest.TestCase):
    MODULE = lib.state
    guard_name = "tickets-index.json.lock"

    def _call(self, n=1):
        return lib.update_index(self.workspace, "acme-shop", _ticket("SHOP-%d" % n))

    def _landed(self, n=1):
        data = lib.read_json(lib.index_path(self.workspace, "acme-shop")) or {}
        self.assertIn("SHOP-%d" % n, data.get("tickets", {}))


class UpdateMetricsGuardTest(_GuardedWriterCaseMixin, unittest.TestCase):
    MODULE = lib.metrics
    guard_name = "metrics.json.lock"

    def _call(self, n=1):
        return lib.update_metrics(self.workspace, "acme-shop", pr_created=True, pr_number=n)

    def _landed(self, n=1):
        data = lib.read_json(lib.metrics_path(self.workspace, "acme-shop")) or {}
        self.assertIn(n, data.get("prs", {}).get("created_pr_numbers", []))


class ConcurrentWritersTest(unittest.TestCase):
    def setUp(self):
        self.workspace = tempfile.mkdtemp(prefix="acs-test-")
        self.addCleanup(shutil.rmtree, self.workspace, True)

    def test_no_index_entry_dropped_under_interleaved_writers(self):
        """Two threads each add a distinct ticket; without the guard, thread
        B's read (taken while thread A holds an unwritten in-memory copy)
        would let thread A's later write clobber thread B's addition."""
        index_path = lib.index_path(self.workspace, "acme-shop")
        original_read_json = lib.read_json
        first_reader_seen = threading.Event()

        def slow_read(path):
            data = original_read_json(path)
            if path == index_path and not first_reader_seen.is_set():
                first_reader_seen.set()
                time.sleep(0.2)
            return data

        def _write(n):
            lib.update_index(self.workspace, "acme-shop", _ticket("SHOP-%d" % n))

        with mock.patch.object(lib.state, "read_json", side_effect=slow_read):
            t1 = threading.Thread(target=_write, args=(1,))
            t2 = threading.Thread(target=_write, args=(2,))
            t1.start()
            time.sleep(0.05)
            t2.start()
            t1.join(timeout=5)
            t2.join(timeout=5)

        data = original_read_json(index_path)
        self.assertEqual(set(data["tickets"].keys()), {"SHOP-1", "SHOP-2"})
