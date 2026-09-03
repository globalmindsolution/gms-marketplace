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
import stat
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

    def test_file_mode_is_0600_immediately_after_first_write(self):
        # Before any rotation -- the sample log is a privacy-sensitive
        # workspace artifact (operator cumulative AI spend) and must match
        # every other acs artifact's 0600 convention, not the default umask.
        cost_sampler._append_sample_line(
            self.path, {"ts": "2026-08-25T00:00:00Z", "total_cost_usd": 1.0, "src": "total_cost_usd"})
        mode = stat.S_IMODE(os.stat(self.path).st_mode)
        self.assertEqual(mode, 0o600)


# ---------------------------------------------------------------------------
# read_latest_sample: the public accessor statusline.py uses instead of the
# module-private _read_samples (encapsulation across the component boundary).
# ---------------------------------------------------------------------------

class TestReadLatestSample(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="acs-latest-sample-")
        self.addCleanup(lambda: __import__("shutil").rmtree(self.tmp, ignore_errors=True))
        self.workspace = self.tmp
        self.repo_id = "acme-shop"
        self.ckid = "shop-ab12cd34"

    def test_returns_none_when_no_samples_exist(self):
        self.assertIsNone(cost_sampler.read_latest_sample(self.workspace, self.repo_id, self.ckid))

    def test_returns_the_most_recently_written_samples_value(self):
        path = cost_sampler.cost_samples_path(self.workspace, self.repo_id, self.ckid)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(json.dumps({"ts": "2026-08-25T06:00:00Z", "total_cost_usd": 1.0}) + "\n")
            fh.write(json.dumps({"ts": "2026-08-25T06:01:00Z", "total_cost_usd": 2.5}) + "\n")
        self.assertEqual(cost_sampler.read_latest_sample(self.workspace, self.repo_id, self.ckid), 2.5)


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
        self.assertEqual(result_1["cost_usd"], 2.0)
        self.assertEqual(result_1["cost_basis"], "measured")

        result_2 = cost_sampler.allocate_cost(
            self.workspace, self.repo_id, self.ckid,
            "2026-08-25T06:05:00Z", "2026-08-25T06:15:00Z", role_usage)
        self.assertIsNone(result_2["cost_usd"])
        self.assertEqual(result_2["cost_basis"], "unavailable")
        self.assertEqual(result_2["cost_scope"], "no_unconsumed_sample_in_window")
        for r in result_2["role_usage"]:
            self.assertIsNone(r["cost_usd"])
            self.assertEqual(r["cost_basis"], "unavailable")

    def test_sample_newer_than_run_end_is_never_consumed(self):
        self._samples([
            {"ts": "2026-08-25T06:00:00Z", "total_cost_usd": 1.0, "src": "total_cost_usd"},
            {"ts": "2026-08-25T07:00:00Z", "total_cost_usd": 9.0, "src": "total_cost_usd"},
        ])
        role_usage = [{"role": "executor", "input": 1, "output": 1, "cache_creation": 0, "cache_read": 0}]
        result = cost_sampler.allocate_cost(
            self.workspace, self.repo_id, self.ckid,
            "2026-08-25T05:00:00Z", "2026-08-25T06:30:00Z", role_usage)
        # Only the 06:00 sample is <= T=06:30; the 07:00 sample must never be used.
        self.assertEqual(result["cost_usd"], 1.0)
        self.assertEqual(result["cost_basis"], "measured")

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
        result = cost_sampler.allocate_cost(
            self.workspace, self.repo_id, self.ckid,
            "2026-08-25T06:05:00Z", "2026-08-25T06:15:00Z", role_usage)
        self.assertIsNone(result["cost_usd"])
        self.assertEqual(result["cost_basis"], "unavailable")
        self.assertEqual(result["cost_scope"], "cost_total_reset")
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
        result_3 = cost_sampler.allocate_cost(
            self.workspace, self.repo_id, self.ckid,
            "2026-08-25T06:15:00Z", "2026-08-25T06:25:00Z", role_usage)
        self.assertAlmostEqual(result_3["cost_usd"], 0.2)
        self.assertEqual(result_3["cost_basis"], "measured")
        self.assertEqual(result_3["cost_scope"], "session_total")

    def test_no_sample_at_all_is_unavailable(self):
        role_usage = [{"role": "executor", "input": 1, "output": 1, "cache_creation": 0, "cache_read": 0}]
        result = cost_sampler.allocate_cost(
            self.workspace, self.repo_id, self.ckid,
            "2026-08-25T06:00:00Z", "2026-08-25T06:10:00Z", role_usage)
        self.assertIsNone(result["cost_usd"])
        self.assertEqual(result["cost_basis"], "unavailable")
        self.assertEqual(result["cost_scope"], "no_unconsumed_sample_in_window")
        self.assertIsNone(result["excluded_cost_usd"])
        self.assertIsNone(result["excluded_token_share"])

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
        result = cost_sampler.allocate_cost(
            self.workspace, self.repo_id, self.ckid,
            "2026-08-25T05:55:00Z", "2026-08-25T06:05:00Z", role_usage)

        # C-8 "drop, don't redistribute": the returned cost_usd is the
        # attributed-only share of the session-window charge (delta minus the
        # dropped unattributed slice), never the raw full delta.
        self.assertAlmostEqual(result["cost_usd"], 0.4)
        self.assertEqual(result["cost_basis"], "measured")
        self.assertAlmostEqual(result["excluded_token_share"], 0.6)
        self.assertAlmostEqual(result["excluded_cost_usd"], 0.6)

        by_role = {r["role"]: r for r in result["role_usage"]}
        self.assertAlmostEqual(by_role["coordinator"]["cost_usd"], 0.2)
        self.assertEqual(by_role["coordinator"]["cost_basis"], "apportioned")
        self.assertAlmostEqual(by_role["executor"]["cost_usd"], 0.2)
        self.assertEqual(by_role["executor"]["cost_basis"], "apportioned")
        self.assertIsNone(by_role["unattributed"]["cost_usd"])
        self.assertEqual(by_role["unattributed"]["cost_basis"], "unavailable")

        # Attributed roles alone must sum back to the returned cost_usd -- the
        # excluded slice is dropped, not folded back in.
        attributed_sum = by_role["coordinator"]["cost_usd"] + by_role["executor"]["cost_usd"]
        self.assertAlmostEqual(attributed_sum, result["cost_usd"])

    def test_no_role_usage_data_excludes_entire_delta(self):
        self._samples([{"ts": "2026-08-25T06:00:00Z", "total_cost_usd": 1.5, "src": "total_cost_usd"}])
        result = cost_sampler.allocate_cost(
            self.workspace, self.repo_id, self.ckid,
            "2026-08-25T05:55:00Z", "2026-08-25T06:05:00Z", [])
        # 100% of the delta is unattributed (no role_usage data at all), so the
        # returned cost_usd -- the attributed-only share -- is zero, even
        # though the session-window charge itself was real.
        self.assertEqual(result["cost_usd"], 0.0)
        self.assertEqual(result["cost_basis"], "measured")
        self.assertEqual(result["role_usage"], [])
        self.assertEqual(result["excluded_token_share"], 1.0)
        self.assertEqual(result["excluded_cost_usd"], 1.5)

    def test_returned_cost_usd_is_attributed_share_not_full_delta(self):
        """FIX 1 (allocate_cost's own contract): the returned cost_usd for a
        run with both attributed and unattributed same-window tokens equals
        delta * attributed_token_fraction, not the raw full delta -- C-8's
        "drop, don't redistribute" policy applies at the run level, not just
        to the informational excluded_cost_usd side-channel."""
        self._samples([{"ts": "2026-08-25T06:00:00Z", "total_cost_usd": 10.0, "src": "total_cost_usd"}])
        role_usage = [
            {"role": "executor", "input": 25, "output": 0, "cache_creation": 0, "cache_read": 0},
            {"role": "unattributed", "input": 75, "output": 0, "cache_creation": 0, "cache_read": 0},
        ]
        result = cost_sampler.allocate_cost(
            self.workspace, self.repo_id, self.ckid,
            "2026-08-25T05:55:00Z", "2026-08-25T06:05:00Z", role_usage)
        # attributed fraction = 25/100 = 0.25 -> 10.0 * 0.25 = 2.5
        self.assertAlmostEqual(result["cost_usd"], 2.5)
        self.assertAlmostEqual(result["excluded_cost_usd"], 7.5)

    def test_cost_usd_none_leaves_every_role_null_no_apportionment(self):
        # No samples at all -> unavailable; roles must carry no cost figure.
        role_usage = [
            {"role": "coordinator", "input": 10, "output": 10, "cache_creation": 0, "cache_read": 0},
            {"role": "executor", "input": 90, "output": 90, "cache_creation": 0, "cache_read": 0},
        ]
        result = cost_sampler.allocate_cost(
            self.workspace, self.repo_id, self.ckid,
            "2026-08-25T06:00:00Z", "2026-08-25T06:10:00Z", role_usage)
        self.assertIsNone(result["cost_usd"])
        self.assertEqual(result["cost_basis"], "unavailable")
        self.assertIsNone(result["excluded_cost_usd"])
        self.assertIsNone(result["excluded_token_share"])
        for r in result["role_usage"]:
            self.assertIsNone(r["cost_usd"])
            self.assertEqual(r["cost_basis"], "unavailable")


class TestAllocateCostModelUsage(unittest.TestCase):
    """D1.2 Option A (design.md:173-200): model_usage's cost is the FULL
    charged delta, apportioned by token share, with NO unattributed
    exclusion -- unlike role_usage's attributed-only cost."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="acs-allocate-cost-model-")
        self.addCleanup(lambda: __import__("shutil").rmtree(self.tmp, ignore_errors=True))
        self.workspace = self.tmp
        self.repo_id = "acme-shop"
        self.ckid = "shop-ab12cd34"

    def _samples(self, samples):
        _write_samples(self.workspace, self.repo_id, self.ckid, samples)

    def test_model_usage_cost_is_full_delta_without_unattributed_exclusion(self):
        # 300 of 400 tokens are unattributed (role scope) -- but model_usage
        # still gets the WHOLE delta apportioned across it, no exclusion.
        self._samples([{"ts": "2026-08-25T06:00:00Z", "total_cost_usd": 1.0, "src": "total_cost_usd"}])
        role_usage = [
            {"role": "executor", "input": 100, "output": 0, "cache_creation": 0, "cache_read": 0},
            {"role": "unattributed", "input": 300, "output": 0, "cache_creation": 0, "cache_read": 0},
        ]
        model_usage = [
            {"model": "model-a", "input": 100, "output": 0, "cache_creation": 0, "cache_read": 0},
            {"model": "model-b", "input": 300, "output": 0, "cache_creation": 0, "cache_read": 0},
        ]
        result = cost_sampler.allocate_cost(
            self.workspace, self.repo_id, self.ckid,
            "2026-08-25T05:55:00Z", "2026-08-25T06:05:00Z", role_usage, model_usage=model_usage)
        by_model = {m["model"]: m for m in result["model_usage"]}
        # Full delta (1.0) apportioned by token share -- model-b keeps its
        # 300/400 share even though it would be excluded at the role level.
        self.assertAlmostEqual(by_model["model-a"]["cost_usd"], 0.25)
        self.assertAlmostEqual(by_model["model-b"]["cost_usd"], 0.75)
        self.assertEqual(by_model["model-a"]["cost_basis"], "apportioned")
        self.assertEqual(by_model["model-b"]["cost_basis"], "apportioned")
        # Sum of model costs is the FULL delta, not the attributed-only share.
        self.assertAlmostEqual(sum(m["cost_usd"] for m in result["model_usage"]), 1.0)

    def test_model_cost_minus_attributed_role_cost_equals_excluded_cost_usd(self):
        # The named D1.2 reconciliation identity (design.md:198-199):
        # sum(model_usage.cost_usd) - sum(role_usage.cost_usd, attributed
        # roles only) == excluded_cost_usd.
        self._samples([{"ts": "2026-08-25T06:00:00Z", "total_cost_usd": 4.0, "src": "total_cost_usd"}])
        role_usage = [
            {"role": "coordinator", "input": 100, "output": 0, "cache_creation": 0, "cache_read": 0},
            {"role": "unattributed", "input": 300, "output": 0, "cache_creation": 0, "cache_read": 0},
        ]
        model_usage = [
            {"model": "only-model", "input": 400, "output": 0, "cache_creation": 0, "cache_read": 0},
        ]
        result = cost_sampler.allocate_cost(
            self.workspace, self.repo_id, self.ckid,
            "2026-08-25T05:55:00Z", "2026-08-25T06:05:00Z", role_usage, model_usage=model_usage)
        model_cost_sum = sum(m["cost_usd"] for m in result["model_usage"])
        attributed_role_cost_sum = sum(
            r["cost_usd"] for r in result["role_usage"] if r["role"] != "unattributed")
        self.assertAlmostEqual(model_cost_sum - attributed_role_cost_sum, result["excluded_cost_usd"])

    def test_allocate_cost_returns_dict_with_documented_keys(self):
        self._samples([{"ts": "2026-08-25T06:00:00Z", "total_cost_usd": 1.0, "src": "total_cost_usd"}])
        role_usage = [{"role": "executor", "input": 1, "output": 0, "cache_creation": 0, "cache_read": 0}]
        model_usage = [{"model": "m1", "input": 1, "output": 0, "cache_creation": 0, "cache_read": 0}]
        result = cost_sampler.allocate_cost(
            self.workspace, self.repo_id, self.ckid,
            "2026-08-25T05:55:00Z", "2026-08-25T06:05:00Z", role_usage, model_usage=model_usage)
        self.assertIsInstance(result, dict)
        # MAR-6 widens this pinned key set with api_duration_ms/basis/scope --
        # a mandatory, spec-required consequence of AC-1's return-dict widening,
        # not an unrelated edit to this test's own cost/model_usage assertions.
        self.assertEqual(set(result.keys()), {
            "role_usage", "model_usage", "cost_usd", "cost_basis",
            "cost_scope", "excluded_cost_usd", "excluded_token_share",
            "api_duration_ms", "api_duration_basis", "api_duration_scope",
        })

    def test_model_usage_none_argument_returns_none(self):
        self._samples([{"ts": "2026-08-25T06:00:00Z", "total_cost_usd": 1.0, "src": "total_cost_usd"}])
        role_usage = [{"role": "executor", "input": 1, "output": 0, "cache_creation": 0, "cache_read": 0}]
        result = cost_sampler.allocate_cost(
            self.workspace, self.repo_id, self.ckid,
            "2026-08-25T05:55:00Z", "2026-08-25T06:05:00Z", role_usage)
        self.assertIsNone(result["model_usage"])

    def test_no_unconsumed_sample_marks_every_model_entry_unavailable(self):
        role_usage = [{"role": "executor", "input": 1, "output": 0, "cache_creation": 0, "cache_read": 0}]
        model_usage = [{"model": "m1", "input": 1, "output": 0, "cache_creation": 0, "cache_read": 0}]
        result = cost_sampler.allocate_cost(
            self.workspace, self.repo_id, self.ckid,
            "2026-08-25T06:00:00Z", "2026-08-25T06:10:00Z", role_usage, model_usage=model_usage)
        self.assertEqual(result["cost_scope"], "no_unconsumed_sample_in_window")
        for m in result["model_usage"]:
            self.assertIsNone(m["cost_usd"])
            self.assertEqual(m["cost_basis"], "unavailable")

    def test_cost_total_reset_marks_every_model_entry_unavailable(self):
        self._samples([{"ts": "2026-08-25T06:00:00Z", "total_cost_usd": 5.0, "src": "total_cost_usd"}])
        role_usage = [{"role": "executor", "input": 1, "output": 0, "cache_creation": 0, "cache_read": 0}]
        model_usage = [{"model": "m1", "input": 1, "output": 0, "cache_creation": 0, "cache_read": 0}]
        cost_sampler.allocate_cost(
            self.workspace, self.repo_id, self.ckid,
            "2026-08-25T05:55:00Z", "2026-08-25T06:05:00Z", role_usage, model_usage=model_usage)

        self._samples([
            {"ts": "2026-08-25T06:00:00Z", "total_cost_usd": 5.0, "src": "total_cost_usd"},
            {"ts": "2026-08-25T06:10:00Z", "total_cost_usd": 0.3, "src": "total_cost_usd"},
        ])
        result = cost_sampler.allocate_cost(
            self.workspace, self.repo_id, self.ckid,
            "2026-08-25T06:05:00Z", "2026-08-25T06:15:00Z", role_usage, model_usage=model_usage)
        self.assertEqual(result["cost_scope"], "cost_total_reset")
        for m in result["model_usage"]:
            self.assertIsNone(m["cost_usd"])
            self.assertEqual(m["cost_basis"], "unavailable")

    def test_zero_token_model_usage_degrades_to_unavailable_never_zero(self):
        self._samples([{"ts": "2026-08-25T06:00:00Z", "total_cost_usd": 1.0, "src": "total_cost_usd"}])
        role_usage = [{"role": "executor", "input": 1, "output": 0, "cache_creation": 0, "cache_read": 0}]
        model_usage = [{"model": "m1", "input": 0, "output": 0, "cache_creation": 0, "cache_read": 0}]
        result = cost_sampler.allocate_cost(
            self.workspace, self.repo_id, self.ckid,
            "2026-08-25T05:55:00Z", "2026-08-25T06:05:00Z", role_usage, model_usage=model_usage)
        self.assertIsNone(result["model_usage"][0]["cost_usd"])
        self.assertEqual(result["model_usage"][0]["cost_basis"], "unavailable")

    def test_role_usage_cost_apportionment_unchanged(self):
        # Inverse obligation: passing model_usage must not change role_usage's
        # own attributed-only apportionment or the excluded_* figures.
        self._samples([{"ts": "2026-08-25T06:00:00Z", "total_cost_usd": 1.0, "src": "total_cost_usd"}])
        role_usage = [
            {"role": "executor", "input": 100, "output": 0, "cache_creation": 0, "cache_read": 0},
            {"role": "unattributed", "input": 300, "output": 0, "cache_creation": 0, "cache_read": 0},
        ]
        model_usage = [
            {"model": "m1", "input": 400, "output": 0, "cache_creation": 0, "cache_read": 0},
        ]
        result = cost_sampler.allocate_cost(
            self.workspace, self.repo_id, self.ckid,
            "2026-08-25T05:55:00Z", "2026-08-25T06:05:00Z", role_usage, model_usage=model_usage)
        by_role = {r["role"]: r for r in result["role_usage"]}
        self.assertAlmostEqual(by_role["executor"]["cost_usd"], 0.25)
        self.assertIsNone(by_role["unattributed"]["cost_usd"])
        self.assertAlmostEqual(result["cost_usd"], 0.25)
        self.assertAlmostEqual(result["excluded_cost_usd"], 0.75)
        self.assertAlmostEqual(result["excluded_token_share"], 0.75)


class TestRecordCostSampleApiDuration(AcsWorkspaceCase):
    """MAR-6: record_cost_sample's F5 fix -- a duration-only or cost-only
    payload now writes a sample; only a payload with neither quantity is a
    silent no-op. Originating ticket: MAR-6."""

    def _samples(self, ctx):
        path = cost_sampler.cost_samples_path(ctx["workspace"], ctx["repo_id"], ctx["checkout_id"])
        if not os.path.exists(path):
            return []
        with open(path, "r", encoding="utf-8") as fh:
            return [json.loads(line) for line in fh if line.strip()]

    # -- test 1: F5 fix -----------------------------------------------------
    def test_duration_only_payload_still_writes_a_sample(self):
        # F5 fix: a payload carrying total_api_duration_ms but no
        # total_cost_usd must still write a sample line (the early return
        # widens to "return only when BOTH are None").
        ctx = lib.build_context(self.repo)
        payload = {"cwd": self.repo, "cost": {"total_api_duration_ms": 1500.0}}
        cost_sampler.record_cost_sample(payload)
        samples = self._samples(ctx)
        self.assertEqual(len(samples), 1)
        self.assertEqual(samples[0]["total_api_duration_ms"], 1500.0)
        self.assertEqual(samples[0]["duration_src"], "cost.total_api_duration_ms")
        self.assertIsNone(samples[0]["total_cost_usd"])
        self.assertIsNone(samples[0]["src"])

    # -- test 2: cost-only writes null duration; neither writes nothing ----
    def test_cost_only_payload_writes_sample_with_null_duration(self):
        ctx = lib.build_context(self.repo)
        payload = {"cwd": self.repo, "cost": {"total_cost_usd": 2.0}}
        cost_sampler.record_cost_sample(payload)
        samples = self._samples(ctx)
        self.assertEqual(len(samples), 1)
        self.assertEqual(samples[0]["total_cost_usd"], 2.0)
        self.assertIsNone(samples[0]["total_api_duration_ms"])
        self.assertIsNone(samples[0]["duration_src"])

    def test_neither_quantity_found_writes_nothing(self):
        ctx = lib.build_context(self.repo)
        payload = {"cwd": self.repo, "irrelevant": True}
        cost_sampler.record_cost_sample(payload)
        self.assertEqual(self._samples(ctx), [])


class TestApiDurationSampling(unittest.TestCase):
    """MAR-6: cost.total_api_duration_ms sampled as a sibling probe to
    total_cost_usd, sharing one cursor file, apportioned per role by the
    same mechanism as cost (design.md D3, C-6). Originating ticket: MAR-6."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="acs-api-duration-")
        self.addCleanup(lambda: __import__("shutil").rmtree(self.tmp, ignore_errors=True))
        self.workspace = self.tmp
        self.repo_id = "acme-shop"
        self.ckid = "shop-ab12cd34"

    def _cursor(self):
        return lib.read_json(cost_sampler.cost_cursor_path(self.workspace, self.repo_id, self.ckid))

    # -- test 3: _extract_api_duration probe order ---------------------------
    def test_extract_api_duration_probe_order_and_recursive_fallback(self):
        value, src = cost_sampler._extract_api_duration({"cost": {"total_api_duration_ms": 5.0}})
        self.assertEqual(value, 5.0)
        self.assertEqual(src, "cost.total_api_duration_ms")

        value, src = cost_sampler._extract_api_duration({"cost": {"total_api_duration": 6.0}})
        self.assertEqual(value, 6.0)
        self.assertEqual(src, "cost.total_api_duration")

        value, src = cost_sampler._extract_api_duration({"total_api_duration_ms": 7.0})
        self.assertEqual(value, 7.0)
        self.assertEqual(src, "total_api_duration_ms")

        value, src = cost_sampler._extract_api_duration(
            {"session": {"stats": {"total_api_duration_ms": 8.0}}})
        self.assertEqual(value, 8.0)
        self.assertEqual(src, "session.stats.total_api_duration_ms")

        # earliest wins, mirroring _extract_total_cost's own ordering
        value, src = cost_sampler._extract_api_duration(
            {"cost": {"total_api_duration_ms": 9.0}, "total_api_duration_ms": 1.0})
        self.assertEqual(value, 9.0)
        self.assertEqual(src, "cost.total_api_duration_ms")

        self.assertEqual(cost_sampler._extract_api_duration({"unrelated": 1}), (None, None))
        self.assertEqual(cost_sampler._extract_api_duration(None), (None, None))

    # -- test 4: _recursive_scan's key_re is caller-supplied -----------------
    def test_recursive_scan_key_re_is_caller_supplied(self):
        # Default key_re still finds the cost key -- no regression on the
        # existing cost path.
        found = cost_sampler._recursive_scan({"a": {"total_cost_usd": 3.0}}, 1)
        self.assertEqual(found, (3.0, "a.total_cost_usd"))

        # A caller-supplied key_re finds the duration key instead, and does
        # NOT match a cost key even when both are present.
        found = cost_sampler._recursive_scan(
            {"a": {"total_api_duration_ms": 4.0, "total_cost_usd": 3.0}}, 1,
            key_re=cost_sampler._TOTAL_API_DURATION_KEY_RE)
        self.assertEqual(found, (4.0, "a.total_api_duration_ms"))

    # -- test 5: one cursor file, both fields, one write ----------------------
    def test_cursor_carries_both_quantities_in_one_write(self):
        # Seed a prior cursor so the duration edge is numeric on both sides
        # of this call (a totally cursor-less first call is Test 6's own
        # "legacy cursor" degrade-then-recover scenario, covered separately).
        lib.write_json(cost_sampler.cost_cursor_path(self.workspace, self.repo_id, self.ckid),
                        {"ts": "2026-08-25T05:50:00Z", "total_cost_usd": 0.0,
                         "total_api_duration_ms": 0.0})
        _write_samples(self.workspace, self.repo_id, self.ckid, [
            {"ts": "2026-08-25T06:00:00Z", "total_cost_usd": 2.0,
             "total_api_duration_ms": 1000.0, "src": "total_cost_usd"},
        ])
        role_usage = [{"role": "executor", "input": 10, "output": 20, "cache_creation": 0, "cache_read": 0}]
        import unittest.mock as mock
        with mock.patch.object(lib, "write_json", wraps=lib.write_json) as spy:
            result = cost_sampler.allocate_cost(
                self.workspace, self.repo_id, self.ckid,
                "2026-08-25T05:55:00Z", "2026-08-25T06:05:00Z", role_usage)
        self.assertEqual(spy.call_count, 1)
        cursor = self._cursor()
        self.assertEqual(set(cursor.keys()), {"ts", "total_cost_usd", "total_api_duration_ms"})
        self.assertEqual(cursor["total_cost_usd"], 2.0)
        self.assertEqual(cursor["total_api_duration_ms"], 1000.0)
        self.assertEqual(result["api_duration_ms"], 1000.0)
        self.assertEqual(result["api_duration_basis"], "apportioned")
        self.assertEqual(result["api_duration_scope"], "session_total")

    # -- test 6: legacy cursor without duration degrades once, then recovers -
    def test_legacy_cursor_without_duration_degrades_duration_only_then_recovers(self):
        # A pre-MAR-6 cursor file has no total_api_duration_ms at all.
        lib.write_json(cost_sampler.cost_cursor_path(self.workspace, self.repo_id, self.ckid),
                        {"ts": "2026-08-25T05:50:00Z", "total_cost_usd": 1.0})
        _write_samples(self.workspace, self.repo_id, self.ckid, [
            {"ts": "2026-08-25T06:00:00Z", "total_cost_usd": 2.0,
             "total_api_duration_ms": 1000.0, "src": "total_cost_usd"},
        ])
        role_usage = [{"role": "executor", "input": 10, "output": 0, "cache_creation": 0, "cache_read": 0}]
        result_1 = cost_sampler.allocate_cost(
            self.workspace, self.repo_id, self.ckid,
            "2026-08-25T05:55:00Z", "2026-08-25T06:05:00Z", role_usage)
        self.assertEqual(result_1["cost_basis"], "measured")
        self.assertEqual(result_1["cost_usd"], 1.0)
        self.assertIsNone(result_1["api_duration_ms"])
        self.assertEqual(result_1["api_duration_basis"], "unavailable")
        self.assertEqual(result_1["api_duration_scope"], "duration_unavailable_on_cursor")
        for r in result_1["role_usage"]:
            self.assertIsNone(r["api_duration_ms"])
            self.assertEqual(r["api_duration_basis"], "unavailable")

        # Second charge: cursor now carries a numeric duration -> normal apportionment.
        _write_samples(self.workspace, self.repo_id, self.ckid, [
            {"ts": "2026-08-25T06:00:00Z", "total_cost_usd": 2.0,
             "total_api_duration_ms": 1000.0, "src": "total_cost_usd"},
            {"ts": "2026-08-25T06:10:00Z", "total_cost_usd": 3.0,
             "total_api_duration_ms": 1500.0, "src": "total_cost_usd"},
        ])
        result_2 = cost_sampler.allocate_cost(
            self.workspace, self.repo_id, self.ckid,
            "2026-08-25T06:05:00Z", "2026-08-25T06:15:00Z", role_usage)
        self.assertEqual(result_2["api_duration_basis"], "apportioned")
        self.assertEqual(result_2["api_duration_scope"], "session_total")
        self.assertAlmostEqual(result_2["api_duration_ms"], 500.0)

    # -- test 7: cost reset marks both quantities unavailable -----------------
    def test_cost_reset_marks_both_quantities_unavailable(self):
        _write_samples(self.workspace, self.repo_id, self.ckid, [
            {"ts": "2026-08-25T06:00:00Z", "total_cost_usd": 5.0,
             "total_api_duration_ms": 1000.0, "src": "total_cost_usd"},
        ])
        role_usage = [{"role": "executor", "input": 1, "output": 1, "cache_creation": 0, "cache_read": 0}]
        cost_sampler.allocate_cost(
            self.workspace, self.repo_id, self.ckid,
            "2026-08-25T05:55:00Z", "2026-08-25T06:05:00Z", role_usage)

        _write_samples(self.workspace, self.repo_id, self.ckid, [
            {"ts": "2026-08-25T06:00:00Z", "total_cost_usd": 5.0,
             "total_api_duration_ms": 1000.0, "src": "total_cost_usd"},
            {"ts": "2026-08-25T06:10:00Z", "total_cost_usd": 0.3,
             "total_api_duration_ms": 200.0, "src": "total_cost_usd"},
        ])
        result = cost_sampler.allocate_cost(
            self.workspace, self.repo_id, self.ckid,
            "2026-08-25T06:05:00Z", "2026-08-25T06:15:00Z", role_usage)
        self.assertEqual(result["cost_scope"], "cost_total_reset")
        self.assertIsNone(result["api_duration_ms"])
        self.assertEqual(result["api_duration_basis"], "unavailable")
        self.assertEqual(result["api_duration_scope"], "cost_total_reset")
        # The cursor's duration field still advances to the post-reset sample's value.
        self.assertEqual(self._cursor()["total_api_duration_ms"], 200.0)

    # -- test 8: apportioned per role mirrors cost split -----------------------
    def test_api_duration_apportioned_per_role_mirrors_cost_split(self):
        lib.write_json(cost_sampler.cost_cursor_path(self.workspace, self.repo_id, self.ckid),
                        {"ts": "2026-08-25T05:50:00Z", "total_cost_usd": 0.0,
                         "total_api_duration_ms": 0.0})
        _write_samples(self.workspace, self.repo_id, self.ckid, [
            {"ts": "2026-08-25T06:00:00Z", "total_cost_usd": 1.0,
             "total_api_duration_ms": 1000.0, "src": "total_cost_usd"},
        ])
        role_usage = [
            {"role": "coordinator", "input": 100, "output": 100, "cache_creation": 0, "cache_read": 0},
            {"role": "executor", "input": 100, "output": 100, "cache_creation": 0, "cache_read": 0},
            {"role": "unattributed", "input": 300, "output": 300, "cache_creation": 0, "cache_read": 0},
        ]
        result = cost_sampler.allocate_cost(
            self.workspace, self.repo_id, self.ckid,
            "2026-08-25T05:55:00Z", "2026-08-25T06:05:00Z", role_usage)
        by_role = {r["role"]: r for r in result["role_usage"]}
        self.assertAlmostEqual(by_role["coordinator"]["api_duration_ms"], 200.0)
        self.assertEqual(by_role["coordinator"]["api_duration_basis"], "apportioned")
        self.assertAlmostEqual(by_role["executor"]["api_duration_ms"], 200.0)
        self.assertIsNone(by_role["unattributed"]["api_duration_ms"])
        self.assertEqual(by_role["unattributed"]["api_duration_basis"], "unavailable")
        self.assertAlmostEqual(result["api_duration_ms"], 400.0)

    # -- test 9: reuse, not recompute, the excluded_token_share ---------------
    def test_api_duration_uses_the_same_excluded_token_share_as_cost(self):
        lib.write_json(cost_sampler.cost_cursor_path(self.workspace, self.repo_id, self.ckid),
                        {"ts": "2026-08-25T05:50:00Z", "total_cost_usd": 0.0,
                         "total_api_duration_ms": 0.0})
        _write_samples(self.workspace, self.repo_id, self.ckid, [
            {"ts": "2026-08-25T06:00:00Z", "total_cost_usd": 4.0,
             "total_api_duration_ms": 777.0, "src": "total_cost_usd"},
        ])
        role_usage = [
            {"role": "coordinator", "input": 72256, "output": 0, "cache_creation": 0, "cache_read": 0},
            {"role": "executor", "input": 38154, "output": 0, "cache_creation": 0, "cache_read": 0},
            {"role": "unattributed", "input": 16360, "output": 0, "cache_creation": 0, "cache_read": 0},
        ]
        result = cost_sampler.allocate_cost(
            self.workspace, self.repo_id, self.ckid,
            "2026-08-25T05:55:00Z", "2026-08-25T06:05:00Z", role_usage)
        duration_delta = 777.0
        attributed_duration_ms = sum(
            r["api_duration_ms"] for r in result["role_usage"] if r["role"] != "unattributed")
        self.assertAlmostEqual(
            attributed_duration_ms, duration_delta * (1 - result["excluded_token_share"]))
        self.assertAlmostEqual(result["api_duration_ms"], attributed_duration_ms)

    # -- test 10: zero-token denominator degrades duration, never zero --------
    def test_zero_token_denominator_degrades_duration_to_unavailable_never_zero(self):
        # Both cursor edges numeric (so the coupled-degradation guard does
        # NOT short-circuit first) -- this isolates _apportion_duration's
        # OWN zero-token-denominator guard, exercised via a role_usage whose
        # only entry carries zero tokens (the "never zero" fixture: this
        # must degrade to None, not silently apportion 0.0 to the role).
        lib.write_json(cost_sampler.cost_cursor_path(self.workspace, self.repo_id, self.ckid),
                        {"ts": "2026-08-25T05:50:00Z", "total_cost_usd": 0.0,
                         "total_api_duration_ms": 0.0})
        _write_samples(self.workspace, self.repo_id, self.ckid, [
            {"ts": "2026-08-25T06:00:00Z", "total_cost_usd": 1.0,
             "total_api_duration_ms": 500.0, "src": "total_cost_usd"},
        ])
        role_usage = [{"role": "executor", "input": 0, "output": 0, "cache_creation": 0, "cache_read": 0}]
        result = cost_sampler.allocate_cost(
            self.workspace, self.repo_id, self.ckid,
            "2026-08-25T05:55:00Z", "2026-08-25T06:05:00Z", role_usage)
        # Mirrors cost's own established rule (test_no_role_usage_data_excludes_
        # entire_delta): the top-level basis stays "apportioned" (a valid delta
        # WAS computed), with the whole delta excluded (api_duration_ms == 0.0,
        # never a bare None at the top level) -- but each role item, having no
        # tokens to apportion by, individually degrades to unavailable.
        self.assertEqual(result["cost_basis"], "measured")  # cost side unaffected by this guard
        self.assertEqual(result["api_duration_basis"], "apportioned")
        self.assertEqual(result["api_duration_ms"], 0.0)
        for r in result["role_usage"]:
            self.assertIsNone(r["api_duration_ms"])
            self.assertEqual(r["api_duration_basis"], "unavailable")

    # -- test 11: no unconsumed sample -> duration unavailable, same scope ----
    def test_no_unconsumed_sample_marks_duration_unavailable_same_scope_as_cost(self):
        role_usage = [{"role": "executor", "input": 1, "output": 1, "cache_creation": 0, "cache_read": 0}]
        result = cost_sampler.allocate_cost(
            self.workspace, self.repo_id, self.ckid,
            "2026-08-25T06:00:00Z", "2026-08-25T06:10:00Z", role_usage)
        self.assertEqual(result["cost_scope"], "no_unconsumed_sample_in_window")
        self.assertIsNone(result["api_duration_ms"])
        self.assertEqual(result["api_duration_basis"], "unavailable")
        self.assertEqual(result["api_duration_scope"], "no_unconsumed_sample_in_window")
        for r in result["role_usage"]:
            self.assertIsNone(r["api_duration_ms"])
            self.assertEqual(r["api_duration_basis"], "unavailable")

    # -- test 12: pinned-key regression guard ----------------------------------
    def test_allocate_cost_return_dict_gains_api_duration_keys(self):
        _write_samples(self.workspace, self.repo_id, self.ckid, [
            {"ts": "2026-08-25T06:00:00Z", "total_cost_usd": 1.0,
             "total_api_duration_ms": 500.0, "src": "total_cost_usd"},
        ])
        role_usage = [{"role": "executor", "input": 1, "output": 0, "cache_creation": 0, "cache_read": 0}]
        result = cost_sampler.allocate_cost(
            self.workspace, self.repo_id, self.ckid,
            "2026-08-25T05:55:00Z", "2026-08-25T06:05:00Z", role_usage)
        self.assertEqual(set(result.keys()), {
            "role_usage", "model_usage", "cost_usd", "cost_basis", "cost_scope",
            "excluded_cost_usd", "excluded_token_share",
            "api_duration_ms", "api_duration_basis", "api_duration_scope",
        })
        for r in result["role_usage"]:
            self.assertIn("api_duration_ms", r)
            self.assertIn("api_duration_basis", r)

    # -- test 13: no edit obligation confirmed elsewhere; also confirm the
    # duration-only sample never becomes the selected `after`.
    def test_duration_only_sample_never_becomes_selected_after(self):
        _write_samples(self.workspace, self.repo_id, self.ckid, [
            {"ts": "2026-08-25T06:00:00Z", "total_cost_usd": None,
             "total_api_duration_ms": 999.0, "src": None},
        ])
        role_usage = [{"role": "executor", "input": 1, "output": 0, "cache_creation": 0, "cache_read": 0}]
        result = cost_sampler.allocate_cost(
            self.workspace, self.repo_id, self.ckid,
            "2026-08-25T05:55:00Z", "2026-08-25T06:05:00Z", role_usage)
        # `after` selection still requires numeric total_cost_usd -- a
        # duration-only sample is never selected, so this degrades exactly
        # like "no unconsumed sample" for BOTH quantities.
        self.assertEqual(result["cost_scope"], "no_unconsumed_sample_in_window")
        self.assertIsNone(result["cost_usd"])
        self.assertIsNone(result["api_duration_ms"])

    # -- test 14: negative duration_delta (regression without a cost reset)
    # must degrade to unavailable, never a negative or silently-clamped value.
    def test_duration_regression_without_cost_reset_marks_duration_unavailable_never_negative(self):
        lib.write_json(cost_sampler.cost_cursor_path(self.workspace, self.repo_id, self.ckid),
                        {"ts": "2026-08-25T05:50:00Z", "total_cost_usd": 1.0,
                         "total_api_duration_ms": 2000.0})
        _write_samples(self.workspace, self.repo_id, self.ckid, [
            {"ts": "2026-08-25T06:00:00Z", "total_cost_usd": 2.0,
             "total_api_duration_ms": 500.0, "src": "total_cost_usd"},
        ])
        role_usage = [
            {"role": "coordinator", "input": 100, "output": 100, "cache_creation": 0, "cache_read": 0},
            {"role": "executor", "input": 100, "output": 100, "cache_creation": 0, "cache_read": 0},
        ]
        result = cost_sampler.allocate_cost(
            self.workspace, self.repo_id, self.ckid,
            "2026-08-25T05:55:00Z", "2026-08-25T06:05:00Z", role_usage)
        # duration_delta = 500.0 - 2000.0 == -1500.0 (unpatched, this would
        # apportion -750.0 to each role below) while cost is legitimately
        # increasing (delta = 2.0 - 1.0 == 1.0), so cost_total_reset never fires.
        self.assertEqual(result["cost_basis"], "measured")
        self.assertAlmostEqual(result["cost_usd"], 1.0)
        self.assertIsNone(result["api_duration_ms"])
        self.assertEqual(result["api_duration_basis"], "unavailable")
        self.assertEqual(result["api_duration_scope"], "duration_unavailable_on_cursor")
        for r in result["role_usage"]:
            self.assertIsNone(r["api_duration_ms"])
            self.assertEqual(r["api_duration_basis"], "unavailable")
        # The cursor's duration field still advances to the new sample's value.
        self.assertEqual(self._cursor()["total_api_duration_ms"], 500.0)

    # -- test 15: duration_delta == 0 is the guard's >= 0 boundary -- still a
    # real measurement, never treated as a regression. --------------------------
    def test_zero_duration_delta_still_apportions_normally_not_treated_as_regression(self):
        lib.write_json(cost_sampler.cost_cursor_path(self.workspace, self.repo_id, self.ckid),
                        {"ts": "2026-08-25T05:50:00Z", "total_cost_usd": 1.0,
                         "total_api_duration_ms": 500.0})
        _write_samples(self.workspace, self.repo_id, self.ckid, [
            {"ts": "2026-08-25T06:00:00Z", "total_cost_usd": 2.0,
             "total_api_duration_ms": 500.0, "src": "total_cost_usd"},
        ])
        role_usage = [{"role": "executor", "input": 1, "output": 0, "cache_creation": 0, "cache_read": 0}]
        result = cost_sampler.allocate_cost(
            self.workspace, self.repo_id, self.ckid,
            "2026-08-25T05:55:00Z", "2026-08-25T06:05:00Z", role_usage)
        self.assertEqual(result["api_duration_basis"], "apportioned")
        self.assertEqual(result["api_duration_scope"], "session_total")
        self.assertEqual(result["api_duration_ms"], 0.0)


class TestApportionExcludedCostNeverNegative(unittest.TestCase):
    """_apportion's excluded_cost_usd must never go negative on an
    all-attributed input -- schema's own minimum:0 constraint -- even though
    per-role proportional floats can sum to marginally more than `delta`."""

    def test_named_reproduction_case_all_attributed(self):
        # The finding's own reproduction: delta=0.554199, tokens=[72256, 38154, 16360].
        role_usage = [
            {"role": "coordinator", "input": 72256, "output": 0, "cache_creation": 0, "cache_read": 0},
            {"role": "executor", "input": 38154, "output": 0, "cache_creation": 0, "cache_read": 0},
            {"role": "verifier", "input": 16360, "output": 0, "cache_creation": 0, "cache_read": 0},
        ]
        _roles, excluded_cost_usd, excluded_token_share = cost_sampler._apportion(role_usage, 0.554199)
        self.assertEqual(excluded_cost_usd, 0.0)
        self.assertEqual(excluded_token_share, 0.0)

    def test_varied_all_attributed_inputs_never_negative(self):
        cases = [
            (0.554199, [72256, 38154, 16360]),
            (1.0, [1, 1, 1]),
            (0.1, [3, 7]),
            (2.718281828, [999983, 17, 65536, 4194304]),
            (0.0001, [1, 2, 3, 4, 5, 6, 7]),
            (9.999999, [123456789, 1]),
        ]
        for delta, token_counts in cases:
            role_usage = [
                {"role": "role-%d" % i, "input": tokens, "output": 0, "cache_creation": 0, "cache_read": 0}
                for i, tokens in enumerate(token_counts)
            ]
            with self.subTest(delta=delta, token_counts=token_counts):
                _roles, excluded_cost_usd, _share = cost_sampler._apportion(role_usage, delta)
                self.assertGreaterEqual(excluded_cost_usd, 0.0)


if __name__ == "__main__":
    unittest.main()
