"""Behavior tests for acs_lib.elapsed_seconds and its two adapters (MAR-1).

Covers AC-1 (a missing/malformed/inverted interval is excluded from time sums
rather than counted as zero) and AC-2 (acs_lib.run_seconds and
metrics_aggregate._elapsed_seconds share identical None-safe semantics because
both are adapters over the same acs_lib.elapsed_seconds primitive).
"""

import importlib
import os
import sys
import unittest
from unittest import mock

_SCRIPTS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "plugins", "acs", "hooks", "scripts",
)
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

import acs_lib  # noqa: E402  (after sys.path mutation)
metrics_aggregate = importlib.import_module("metrics_aggregate")  # noqa: E402


class TestElapsedSecondsPrimitive(unittest.TestCase):
    """acs_lib.elapsed_seconds(start, end): None for unknown, int for known."""

    def test_none_for_missing_end(self):
        self.assertIsNone(acs_lib.elapsed_seconds("2026-01-01T00:00:00Z", None))

    def test_none_for_malformed_end(self):
        self.assertIsNone(acs_lib.elapsed_seconds("2026-01-01T00:00:00Z", "not-a-date"))

    def test_none_for_inverted_interval(self):
        self.assertIsNone(acs_lib.elapsed_seconds(
            "2026-01-01T00:05:00Z", "2026-01-01T00:00:00Z"))

    def test_zero_for_true_zero_length_interval(self):
        # A real zero-length interval must stay distinguishable from "unknown":
        # it is 0, not None.
        value = acs_lib.elapsed_seconds("2026-01-01T00:00:00Z", "2026-01-01T00:00:00Z")
        self.assertEqual(value, 0)
        self.assertIsNotNone(value)

    def test_positive_valid_interval(self):
        value = acs_lib.elapsed_seconds("2026-01-01T00:00:00Z", "2026-01-01T00:05:00Z")
        self.assertEqual(value, 300)


class TestRunSecondsAdapter(unittest.TestCase):
    """run_seconds(entry) is a one-line adapter: None (not 0) for a missing end — AC-1."""

    def test_returns_none_not_zero_for_missing_ended_at(self):
        result = acs_lib.run_seconds({"started_at": "2026-01-01T00:00:00Z"})
        self.assertIsNone(result)

    def test_returns_int_for_valid_interval(self):
        result = acs_lib.run_seconds({
            "started_at": "2026-01-01T00:00:00Z",
            "ended_at": "2026-01-01T00:05:00Z",
        })
        self.assertEqual(result, 300)

    def test_returns_zero_for_true_zero_length_run(self):
        result = acs_lib.run_seconds({
            "started_at": "2026-01-01T00:00:00Z",
            "ended_at": "2026-01-01T00:00:00Z",
        })
        self.assertEqual(result, 0)


class TestSharedPrimitiveStructural(unittest.TestCase):
    """AC-2, structurally: run_seconds and _elapsed_seconds are both adapters over
    the SAME acs_lib.elapsed_seconds — proven by monkeypatching the primitive and
    observing both call paths change together, not merely by matching examples."""

    def test_monkeypatched_primitive_changes_both_call_paths(self):
        sentinel = 424242
        with mock.patch.object(acs_lib, "elapsed_seconds", return_value=sentinel):
            self.assertEqual(
                acs_lib.run_seconds({
                    "started_at": "2026-01-01T00:00:00Z",
                    "ended_at": "2026-01-01T00:05:00Z",
                }),
                sentinel,
            )
            self.assertEqual(
                metrics_aggregate._elapsed_seconds(
                    "2026-01-01T00:00:00Z", "2026-01-01T00:05:00Z"),
                sentinel,
            )

    def test_monkeypatched_none_changes_both_call_paths(self):
        with mock.patch.object(acs_lib, "elapsed_seconds", return_value=None):
            self.assertIsNone(acs_lib.run_seconds({
                "started_at": "2026-01-01T00:00:00Z",
                "ended_at": "2026-01-01T00:05:00Z",
            }))
            self.assertIsNone(metrics_aggregate._elapsed_seconds(
                "2026-01-01T00:00:00Z", "2026-01-01T00:05:00Z"))

    def test_cross_checked_equal_returns_over_shared_input_table(self):
        cases = [
            (None, "2026-01-01T00:00:00Z"),                      # missing start
            ("2026-01-01T00:00:00Z", None),                      # missing end
            ("not-a-date", "2026-01-01T00:00:00Z"),               # malformed start
            ("2026-01-01T00:05:00Z", "2026-01-01T00:00:00Z"),     # inverted
            ("2026-01-01T00:00:00Z", "2026-01-01T00:00:00Z"),     # valid zero-length
            ("2026-01-01T00:00:00Z", "2026-01-01T00:05:00Z"),     # valid positive
        ]
        for start, end in cases:
            run_result = acs_lib.run_seconds({"started_at": start, "ended_at": end})
            agg_result = metrics_aggregate._elapsed_seconds(start, end)
            self.assertEqual(run_result, agg_result, msg="mismatch for %r" % ((start, end),))


class TestUpdateMetricsNoneGuard(unittest.TestCase):
    """acs_lib.py:1561's int(...) + run_seconds(...) must not raise TypeError on None."""

    def test_update_metrics_does_not_raise_on_none_elapsed_run(self):
        import shutil
        import tempfile
        workspace = tempfile.mkdtemp(prefix="acs-test-")
        self.addCleanup(shutil.rmtree, workspace, True)
        run_entry = {
            "status": "in_progress",
            "started_at": "2026-01-01T00:00:00Z",
            # no ended_at -> run_seconds(run_entry) is None
            "tokens": {"input": 5, "output": 7},
            "cost_usd": 0.1,
        }
        # Must not raise.
        data = acs_lib.update_metrics(workspace, "acme-shop", run_entry=run_entry)
        self.assertEqual(data["totals"]["runs"], 1)
        # A None-elapsed run contributes nothing to working_seconds.
        self.assertEqual(data["totals"]["working_seconds"], 0)
        self.assertEqual(data["totals"]["runs_timed"], 0)
        self.assertEqual(data["totals"]["runs_untimed"], 1)


if __name__ == "__main__":
    unittest.main()
