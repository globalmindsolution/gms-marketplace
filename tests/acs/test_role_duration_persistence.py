"""Behavior tests for acs_lib._measure_run_usage's `role_duration` persistence
(ADR 0084, MAR-5): the derived per-role API-duration list usage_reader now
emits is written onto the run entry on all four exit paths, independent of
cost_sampler.allocate_cost (which has no duration input or output).

Originating ticket: MAR-5. Fixture pattern mirrors
tests/acs/test_acs_lib_state_locks.py::TestFinalizeRun.
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


class TestRoleDurationPersistence(unittest.TestCase):

    def setUp(self):
        self.tdir = tempfile.mkdtemp(prefix="acs-test-")
        self.addCleanup(shutil.rmtree, self.tdir, True)

    def test_role_duration_persisted_on_finalize_run(self):
        """The full allocate_cost path persists the transcript-derived
        role_duration list verbatim -- it is never touched by, or taken
        from, cost_sampler.allocate_cost's return."""
        lib.append_in_progress_run(self.tdir, "code", "SHOP-1", session={
            "session_id": "sess-1", "transcript_path": "/fake/sess-1.jsonl", "checkout_id": "ck-1",
        })
        measured_role_usage = [
            {"role": "coordinator", "input": 10, "output": 20, "cache_creation": 0, "cache_read": 0},
        ]
        measured_role_duration = [
            {"role": "coordinator", "api_duration_ms": 4200, "duration_basis": "derived"},
        ]
        priced_role_usage = [
            {"role": "coordinator", "input": 10, "output": 20, "cache_creation": 0, "cache_read": 0,
             "cost_usd": 0.05, "cost_basis": "apportioned"},
        ]
        with mock.patch("usage_reader.read_transcript_usage") as read_usage, \
                mock.patch("cost_sampler.allocate_cost") as allocate:
            read_usage.return_value = {
                "degraded": False, "reason": None, "role_usage": measured_role_usage,
                "model_usage": [], "role_duration": measured_role_duration,
            }
            allocate.return_value = {
                "role_usage": priced_role_usage, "model_usage": [],
                "cost_usd": 0.05, "cost_basis": "measured", "cost_scope": "session_total",
                "excluded_cost_usd": 0.0, "excluded_token_share": 0.0,
            }
            state, entry = lib.finalize_run(self.tdir, "code", "SHOP-1", {"status": "completed"})
        self.assertEqual(entry["role_duration"], measured_role_duration)
        # allocate_cost's own (duration-less) call args are unaffected.
        allocate.assert_called_once_with(
            os.path.dirname(os.path.dirname(self.tdir)), os.path.basename(os.path.dirname(self.tdir)),
            "ck-1", entry["started_at"], entry["ended_at"], measured_role_usage, [])

    def test_role_duration_is_empty_list_without_a_transcript_path(self):
        """No session_id/transcript_path -- no transcript I/O at all -- must
        still persist role_duration=[] (never absent, never omitted)."""
        lib.append_in_progress_run(self.tdir, "code", "SHOP-1")
        with mock.patch("usage_reader.read_transcript_usage") as read_usage:
            state, entry = lib.finalize_run(self.tdir, "code", "SHOP-1", {"status": "completed"})
        read_usage.assert_not_called()
        self.assertEqual(entry["role_duration"], [])

    def test_role_duration_is_persisted_even_without_a_checkout_id(self):
        """S2 consequence: duration is transcript-only, so unlike cost_usd it
        IS available on the no-checkout_id path -- the real derived list is
        persisted, not []."""
        lib.append_in_progress_run(self.tdir, "code", "SHOP-1", session={
            "session_id": "sess-1", "transcript_path": "/fake/sess-1.jsonl",
        })
        measured_role_duration = [
            {"role": "executor", "api_duration_ms": 900, "duration_basis": "derived"},
        ]
        with mock.patch("usage_reader.read_transcript_usage") as read_usage, \
                mock.patch("cost_sampler.allocate_cost") as allocate:
            read_usage.return_value = {
                "degraded": False, "reason": None, "role_usage": [], "model_usage": [],
                "role_duration": measured_role_duration,
            }
            state, entry = lib.finalize_run(self.tdir, "code", "SHOP-1", {"status": "completed"})
        allocate.assert_not_called()
        self.assertEqual(entry["role_duration"], measured_role_duration)
        self.assertIsNone(entry["cost_usd"])
        self.assertEqual(entry["cost_basis"], "unavailable")

    def test_role_duration_is_empty_list_on_a_degraded_transcript_read(self):
        """A degraded read must never look like a successful measurement --
        role_duration stays [] exactly like role_usage/model_usage do,
        regardless of what usage_reader's degraded return happens to carry."""
        lib.append_in_progress_run(self.tdir, "code", "SHOP-1", session={
            "session_id": "sess-1", "transcript_path": "/fake/sess-1.jsonl", "checkout_id": "ck-1",
        })
        with mock.patch("usage_reader.read_transcript_usage") as read_usage, \
                mock.patch("cost_sampler.allocate_cost") as allocate:
            read_usage.return_value = {
                "degraded": True, "reason": "cap_exceeded", "role_usage": [], "model_usage": [],
                "role_duration": [],
            }
            state, entry = lib.finalize_run(self.tdir, "code", "SHOP-1", {"status": "completed"})
        allocate.assert_not_called()
        self.assertEqual(entry["role_duration"], [])

    def test_role_usage_shape_is_byte_identical_after_role_duration_ships(self):
        """The epic's out-of-scope line made executable (design.md:58-63,
        143-146): role_usage's persisted items carry no duration keys --
        role_duration is a fully separate, parallel list."""
        lib.append_in_progress_run(self.tdir, "code", "SHOP-1", session={
            "session_id": "sess-1", "transcript_path": "/fake/sess-1.jsonl", "checkout_id": "ck-1",
        })
        measured_role_usage = [
            {"role": "coordinator", "input": 10, "output": 20, "cache_creation": 0, "cache_read": 0},
        ]
        priced_role_usage = [
            {"role": "coordinator", "input": 10, "output": 20, "cache_creation": 0, "cache_read": 0,
             "cost_usd": 0.05, "cost_basis": "apportioned"},
        ]
        measured_role_duration = [
            {"role": "coordinator", "api_duration_ms": 1200, "duration_basis": "derived"},
        ]
        with mock.patch("usage_reader.read_transcript_usage") as read_usage, \
                mock.patch("cost_sampler.allocate_cost") as allocate:
            read_usage.return_value = {
                "degraded": False, "reason": None, "role_usage": measured_role_usage,
                "model_usage": [], "role_duration": measured_role_duration,
            }
            allocate.return_value = {
                "role_usage": priced_role_usage, "model_usage": [],
                "cost_usd": 0.05, "cost_basis": "apportioned", "cost_scope": "session_total",
                "excluded_cost_usd": 0.0, "excluded_token_share": 0.0,
            }
            state, entry = lib.finalize_run(self.tdir, "code", "SHOP-1", {"status": "completed"})
        self.assertEqual(entry["role_usage"], priced_role_usage)
        for item in entry["role_usage"]:
            self.assertNotIn("api_duration_ms", item)
            self.assertNotIn("duration_basis", item)


if __name__ == "__main__":
    unittest.main()
