"""Behavior tests for cost_sampler.py: the shape-agnostic statusLine cost
sampler and the cursor-based, non-overlapping consumption rule.

Originating ticket: MAR-1. Covers design.md section SS1.2/SS1.3
(shape-agnostic probe + cursor-based consumption, replacing "nearest
bracketing pair"): record_cost_sample's ordered candidate probe and
resilience to malformed payloads, the sample log's 64 KiB rotation bound,
and allocate_cost's no-double-charge invariant -- a sample already consumed
by one run can never again serve as another run's "after" -- plus the
negative-delta (session reset) handling and the token-share apportionment
that drops the unattributed slice rather than redistributing it.
"""

import json
import os
import sys
import tempfile
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRIPTS = os.path.join(REPO_ROOT, "plugins", "acs", "hooks", "scripts")
sys.path.insert(0, SCRIPTS)

import acs_lib as lib  # noqa: E402
import cost_sampler  # noqa: E402

sys.path.insert(0, os.path.join(REPO_ROOT, "tests", "acs"))
from acs_case import AcsWorkspaceCase  # noqa: E402


# ---------------------------------------------------------------------------
# _extract_total_cost: the ordered, shape-agnostic candidate probe
# ---------------------------------------------------------------------------

class TestExtractTotalCost(unittest.TestCase):
    def test_candidate_1_cost_total_cost_usd(self):
        value, src = cost_sampler._extract_total_cost({"cost": {"total_cost_usd": 2.5}})
        self.assertEqual(value, 2.5)
        self.assertEqual(src, "cost.total_cost_usd")

    def test_candidate_2_cost_total_cost(self):
        value, src = cost_sampler._extract_total_cost({"cost": {"total_cost": 1.1}})
        self.assertEqual(value, 1.1)
        self.assertEqual(src, "cost.total_cost")

    def test_candidate_3_top_level_total_cost_usd(self):
        value, src = cost_sampler._extract_total_cost({"total_cost_usd": 3.75})
        self.assertEqual(value, 3.75)
        self.assertEqual(src, "total_cost_usd")

    def test_candidate_4_bounded_recursive_scan(self):
        payload = {"session": {"stats": {"total_cost_usd": 0.42}}}
        value, src = cost_sampler._extract_total_cost(payload)
        self.assertEqual(value, 0.42)
        self.assertEqual(src, "session.stats.total_cost_usd")

    def test_candidates_probed_in_order_earliest_wins(self):
        # cost.total_cost_usd present alongside a top-level total_cost_usd:
        # candidate 1 must win, not candidate 3.
        payload = {"cost": {"total_cost_usd": 9.0}, "total_cost_usd": 1.0}
        value, src = cost_sampler._extract_total_cost(payload)
        self.assertEqual(value, 9.0)
        self.assertEqual(src, "cost.total_cost_usd")

    def test_recursive_scan_depth_bound_excludes_deeper_matches(self):
        # 4 levels deep (payload -> a -> b -> c -> total_cost_usd) exceeds depth<=3.
        payload = {"a": {"b": {"c": {"total_cost_usd": 5.0}}}}
        value, src = cost_sampler._extract_total_cost(payload)
        self.assertIsNone(value)
        self.assertIsNone(src)

    def test_no_candidate_matches_returns_none(self):
        value, src = cost_sampler._extract_total_cost({"unrelated": {"foo": 1}})
        self.assertIsNone(value)
        self.assertIsNone(src)

    def test_non_numeric_candidate_is_skipped(self):
        payload = {"cost": {"total_cost_usd": "not-a-number"}, "total_cost_usd": 4.0}
        value, src = cost_sampler._extract_total_cost(payload)
        self.assertEqual(value, 4.0)
        self.assertEqual(src, "total_cost_usd")

    def test_non_dict_payload_returns_none(self):
        self.assertEqual(cost_sampler._extract_total_cost(None), (None, None))
        self.assertEqual(cost_sampler._extract_total_cost([1, 2, 3]), (None, None))


# ---------------------------------------------------------------------------
# record_cost_sample: end-to-end, against a real (throwaway) workspace
# ---------------------------------------------------------------------------

class TestRecordCostSample(AcsWorkspaceCase):
    def _samples(self, ctx):
        path = cost_sampler.cost_samples_path(ctx["workspace"], ctx["repo_id"], ctx["checkout_id"])
        if not os.path.exists(path):
            return []
        with open(path, "r", encoding="utf-8") as fh:
            return [json.loads(line) for line in fh if line.strip()]

    def test_writes_sample_with_matching_src(self):
        ctx = lib.build_context(self.repo)
        payload = {"cwd": self.repo, "cost": {"total_cost_usd": 1.23}}
        cost_sampler.record_cost_sample(payload)

        samples = self._samples(ctx)
        self.assertEqual(len(samples), 1)
        self.assertEqual(samples[0]["total_cost_usd"], 1.23)
        self.assertEqual(samples[0]["src"], "cost.total_cost_usd")
        self.assertIn("ts", samples[0])

    def test_no_matching_candidate_writes_no_sample(self):
        ctx = lib.build_context(self.repo)
        payload = {"cwd": self.repo, "irrelevant": True}
        # Must complete without raising.
        cost_sampler.record_cost_sample(payload)
        self.assertEqual(self._samples(ctx), [])

    def test_malformed_payload_never_raises(self):
        # None, a list, and a dict missing "cwd" entirely must all be swallowed.
        cost_sampler.record_cost_sample(None)
        cost_sampler.record_cost_sample([1, 2, 3])
        cost_sampler.record_cost_sample({"cost": {"total_cost_usd": 1.0}})  # no cwd -> os.getcwd()

    def test_resolves_cwd_from_workspace_current_dir_like_statusline(self):
        ctx = lib.build_context(self.repo)
        payload = {"workspace": {"current_dir": self.repo}, "cost": {"total_cost_usd": 0.5}}
        cost_sampler.record_cost_sample(payload)
        samples = self._samples(ctx)
        self.assertEqual(len(samples), 1)
        self.assertEqual(samples[0]["total_cost_usd"], 0.5)

    def test_uninitialized_repo_swallows_and_writes_nothing(self):
        other = tempfile.mkdtemp(prefix="acs-uninit-")
        self.addCleanup(lambda: __import__("shutil").rmtree(other, ignore_errors=True))
        payload = {"cwd": other, "cost": {"total_cost_usd": 1.0}}
        # No .acs/settings.json at all in `other` -> build_context raises -> swallowed.
        cost_sampler.record_cost_sample(payload)


# ---------------------------------------------------------------------------
# Log rotation: exercised directly against the file-level primitive to avoid
# hundreds of slow build_context()/git subprocess round-trips in one test.
# ---------------------------------------------------------------------------

class TestLogRotation(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="acs-cost-log-")
        self.addCleanup(lambda: __import__("shutil").rmtree(self.tmp, ignore_errors=True))
        self.path = os.path.join(self.tmp, "ck-cost-samples.jsonl")

    def test_rotation_bounds_file_size(self):
        for i in range(3000):
            cost_sampler._append_sample_line(
                self.path, {"ts": "2026-08-25T00:00:00Z", "total_cost_usd": float(i), "src": "total_cost_usd"})
        size = os.path.getsize(self.path)
        self.assertLessEqual(size, cost_sampler.MAX_LOG_BYTES)
        self.assertGreater(size, 0)

    def test_rotation_keeps_most_recent_samples(self):
        for i in range(3000):
            cost_sampler._append_sample_line(
                self.path, {"ts": "2026-08-25T00:00:00Z", "total_cost_usd": float(i), "src": "total_cost_usd"})
        with open(self.path, "r", encoding="utf-8") as fh:
            lines = [json.loads(l) for l in fh if l.strip()]
        # The most recent sample must have survived rotation.
        self.assertEqual(lines[-1]["total_cost_usd"], 2999.0)
        # Rotation must have actually dropped older entries.
        self.assertLess(len(lines), 3000)


# ---------------------------------------------------------------------------
# allocate_cost: the cursor-based, non-overlapping consumption rule
# ---------------------------------------------------------------------------

def _write_samples(workspace, repo_id, ckid, samples):
    path = cost_sampler.cost_samples_path(workspace, repo_id, ckid)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        for s in samples:
            fh.write(json.dumps(s) + "\n")


class TestAllocateCost(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="acs-allocate-cost-")
        self.addCleanup(lambda: __import__("shutil").rmtree(self.tmp, ignore_errors=True))
        self.workspace = self.tmp
        self.repo_id = "acme-shop"
        self.ckid = "shop-ab12cd34"

    def _samples(self, samples):
        _write_samples(self.workspace, self.repo_id, self.ckid, samples)

    def _cursor(self):
        return lib.read_json(cost_sampler.cost_cursor_path(self.workspace, self.repo_id, self.ckid))

    def test_no_double_charge_two_finalizes_over_one_sample(self):
        self._samples([{"ts": "2026-08-25T06:00:00Z", "total_cost_usd": 2.0, "src": "total_cost_usd"}])

        role_usage = [{"role": "executor", "input": 10, "output": 20, "cache_creation": 0, "cache_read": 0}]

        result_1 = cost_sampler.allocate_cost(
            self.workspace, self.repo_id, self.ckid,
            "2026-08-25T05:55:00Z", "2026-08-25T06:05:00Z", role_usage)
        _roles_1, cost_usd_1, basis_1, scope_1, excluded_cost_1, excluded_share_1 = result_1
        self.assertEqual(cost_usd_1, 2.0)
        self.assertEqual(basis_1, "measured")

        result_2 = cost_sampler.allocate_cost(
            self.workspace, self.repo_id, self.ckid,
            "2026-08-25T06:05:00Z", "2026-08-25T06:15:00Z", role_usage)
        roles_2, cost_usd_2, basis_2, scope_2, excluded_cost_2, excluded_share_2 = result_2
        self.assertIsNone(cost_usd_2)
        self.assertEqual(basis_2, "unavailable")
        self.assertEqual(scope_2, "no_unconsumed_sample_in_window")
        for r in roles_2:
            self.assertIsNone(r["cost_usd"])
            self.assertEqual(r["cost_basis"], "unavailable")

    def test_sample_newer_than_run_end_is_never_consumed(self):
        self._samples([
            {"ts": "2026-08-25T06:00:00Z", "total_cost_usd": 1.0, "src": "total_cost_usd"},
            {"ts": "2026-08-25T07:00:00Z", "total_cost_usd": 9.0, "src": "total_cost_usd"},
        ])
        role_usage = [{"role": "executor", "input": 1, "output": 1, "cache_creation": 0, "cache_read": 0}]
        _roles, cost_usd, basis, _scope, _ec, _es = cost_sampler.allocate_cost(
            self.workspace, self.repo_id, self.ckid,
            "2026-08-25T05:00:00Z", "2026-08-25T06:30:00Z", role_usage)
        # Only the 06:00 sample is <= T=06:30; the 07:00 sample must never be used.
        self.assertEqual(cost_usd, 1.0)
        self.assertEqual(basis, "measured")

    def test_negative_delta_is_session_reset_charges_nothing_but_advances_cursor(self):
        # First call consumes an initial sample so the cursor is non-trivial.
        self._samples([{"ts": "2026-08-25T06:00:00Z", "total_cost_usd": 5.0, "src": "total_cost_usd"}])
        role_usage = [{"role": "executor", "input": 1, "output": 1, "cache_creation": 0, "cache_read": 0}]
        cost_sampler.allocate_cost(
            self.workspace, self.repo_id, self.ckid,
            "2026-08-25T05:55:00Z", "2026-08-25T06:05:00Z", role_usage)
        self.assertEqual(self._cursor()["total_cost_usd"], 5.0)

        # A new session starts: the running total resets to something lower.
        self._samples([
            {"ts": "2026-08-25T06:00:00Z", "total_cost_usd": 5.0, "src": "total_cost_usd"},
            {"ts": "2026-08-25T06:10:00Z", "total_cost_usd": 0.3, "src": "total_cost_usd"},
        ])
        _roles, cost_usd, basis, scope, _ec, _es = cost_sampler.allocate_cost(
            self.workspace, self.repo_id, self.ckid,
            "2026-08-25T06:05:00Z", "2026-08-25T06:15:00Z", role_usage)
        self.assertIsNone(cost_usd)
        self.assertEqual(basis, "unavailable")
        self.assertEqual(scope, "cost_total_reset")
        # The cursor still advances to the post-reset sample, not left stale.
        self.assertEqual(self._cursor()["total_cost_usd"], 0.3)
        self.assertEqual(self._cursor()["ts"], "2026-08-25T06:10:00Z")

        # A third call must use the advanced (post-reset) cursor, not the stale one:
        # a new sample above 0.3 now yields a small positive delta, not a bogus
        # negative one re-derived against the pre-reset 5.0 cursor.
        self._samples([
            {"ts": "2026-08-25T06:00:00Z", "total_cost_usd": 5.0, "src": "total_cost_usd"},
            {"ts": "2026-08-25T06:10:00Z", "total_cost_usd": 0.3, "src": "total_cost_usd"},
            {"ts": "2026-08-25T06:20:00Z", "total_cost_usd": 0.5, "src": "total_cost_usd"},
        ])
        _roles, cost_usd_3, basis_3, scope_3, _ec, _es = cost_sampler.allocate_cost(
            self.workspace, self.repo_id, self.ckid,
            "2026-08-25T06:15:00Z", "2026-08-25T06:25:00Z", role_usage)
        self.assertAlmostEqual(cost_usd_3, 0.2)
        self.assertEqual(basis_3, "measured")
        self.assertEqual(scope_3, "session_total")

    def test_no_sample_at_all_is_unavailable(self):
        role_usage = [{"role": "executor", "input": 1, "output": 1, "cache_creation": 0, "cache_read": 0}]
        _roles, cost_usd, basis, scope, ec, es = cost_sampler.allocate_cost(
            self.workspace, self.repo_id, self.ckid,
            "2026-08-25T06:00:00Z", "2026-08-25T06:10:00Z", role_usage)
        self.assertIsNone(cost_usd)
        self.assertEqual(basis, "unavailable")
        self.assertEqual(scope, "no_unconsumed_sample_in_window")
        self.assertIsNone(ec)
        self.assertIsNone(es)

    def test_apportionment_denominator_includes_unattributed_slice(self):
        # Two attributed roles plus a synthetic "unattributed" entry carrying the
        # dropped, same-window token slice usage_reader.py excludes from
        # role_usage's real roles per its own contract (design.md C-8).
        self._samples([{"ts": "2026-08-25T06:00:00Z", "total_cost_usd": 1.0, "src": "total_cost_usd"}])
        role_usage = [
            {"role": "coordinator", "input": 100, "output": 100, "cache_creation": 0, "cache_read": 0},   # 200
            {"role": "executor", "input": 100, "output": 100, "cache_creation": 0, "cache_read": 0},      # 200
            {"role": "unattributed", "input": 300, "output": 300, "cache_creation": 0, "cache_read": 0},  # 600
        ]
        # total in-window tokens = 1000; unattributed share = 600/1000 = 0.6
        roles, cost_usd, basis, _scope, excluded_cost_usd, excluded_token_share = cost_sampler.allocate_cost(
            self.workspace, self.repo_id, self.ckid,
            "2026-08-25T05:55:00Z", "2026-08-25T06:05:00Z", role_usage)

        self.assertEqual(cost_usd, 1.0)
        self.assertEqual(basis, "measured")
        self.assertAlmostEqual(excluded_token_share, 0.6)
        self.assertAlmostEqual(excluded_cost_usd, 0.6)

        by_role = {r["role"]: r for r in roles}
        self.assertAlmostEqual(by_role["coordinator"]["cost_usd"], 0.2)
        self.assertEqual(by_role["coordinator"]["cost_basis"], "apportioned")
        self.assertAlmostEqual(by_role["executor"]["cost_usd"], 0.2)
        self.assertEqual(by_role["executor"]["cost_basis"], "apportioned")
        self.assertIsNone(by_role["unattributed"]["cost_usd"])
        self.assertEqual(by_role["unattributed"]["cost_basis"], "unavailable")

        # Attributed roles + excluded amount must sum back to the charged delta.
        attributed_sum = by_role["coordinator"]["cost_usd"] + by_role["executor"]["cost_usd"]
        self.assertAlmostEqual(attributed_sum + excluded_cost_usd, cost_usd)

    def test_no_role_usage_data_excludes_entire_delta(self):
        self._samples([{"ts": "2026-08-25T06:00:00Z", "total_cost_usd": 1.5, "src": "total_cost_usd"}])
        roles, cost_usd, basis, _scope, excluded_cost_usd, excluded_token_share = cost_sampler.allocate_cost(
            self.workspace, self.repo_id, self.ckid,
            "2026-08-25T05:55:00Z", "2026-08-25T06:05:00Z", [])
        self.assertEqual(cost_usd, 1.5)
        self.assertEqual(basis, "measured")
        self.assertEqual(roles, [])
        self.assertEqual(excluded_token_share, 1.0)
        self.assertEqual(excluded_cost_usd, 1.5)

    def test_cost_usd_none_leaves_every_role_null_no_apportionment(self):
        # No samples at all -> unavailable; roles must carry no cost figure.
        role_usage = [
            {"role": "coordinator", "input": 10, "output": 10, "cache_creation": 0, "cache_read": 0},
            {"role": "executor", "input": 90, "output": 90, "cache_creation": 0, "cache_read": 0},
        ]
        roles, cost_usd, basis, _scope, ec, es = cost_sampler.allocate_cost(
            self.workspace, self.repo_id, self.ckid,
            "2026-08-25T06:00:00Z", "2026-08-25T06:10:00Z", role_usage)
        self.assertIsNone(cost_usd)
        self.assertEqual(basis, "unavailable")
        self.assertIsNone(ec)
        self.assertIsNone(es)
        for r in roles:
            self.assertIsNone(r["cost_usd"])
            self.assertEqual(r["cost_basis"], "unavailable")


if __name__ == "__main__":
    unittest.main()
