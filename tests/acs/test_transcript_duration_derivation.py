"""Behavior tests for usage_reader's per-role API-duration derivation (MAR-5).

Covers T1 of MAR-5/phases/code/iter-1-plan.md, S6a: role_duration is derived
from inter-record transcript timestamp gaps, attributing each token-bearing
record's gap-since-predecessor to that record's own role, capped at
MAX_RECORD_GAP_SECONDS and never negative -- an explicitly DERIVED
approximation (ADR 0084), never a measured per-call latency. Fixtures are
synthetic transcript trees built under tempfile.mkdtemp() -- never ~/.claude.
"""

import json
import os
import shutil
import sys
import tempfile
import unittest

_SCRIPTS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "plugins", "acs", "hooks", "scripts",
)
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

import usage_reader  # noqa: E402


def _usage(input_tokens=1, output_tokens=0, cache_creation=0, cache_read=0):
    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cache_creation_input_tokens": cache_creation,
        "cache_read_input_tokens": cache_read,
    }


def _record(ts, usage=None, attribution_skill=None, attribution_agent=None, model="claude-sonnet-5"):
    rec = {"type": "assistant", "timestamp": ts, "message": {"model": model}}
    if usage is not None:
        rec["message"]["usage"] = usage
    if attribution_skill is not None:
        rec["attributionSkill"] = attribution_skill
    if attribution_agent is not None:
        rec["attributionAgent"] = attribution_agent
    return rec


def _no_usage_record(ts):
    """A user/tool-result-shaped record: timestamped, in-window, but carries
    no message.usage -- the M1 finding (user-role records never carry usage)."""
    return {"type": "user", "timestamp": ts, "message": {"role": "user", "content": []}}


def _write_jsonl(path, records):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(rec) + "\n")


class DurationCase(unittest.TestCase):
    """Same synthetic-transcript layout as test_usage_reader.py's
    UsageReaderCase: <root>/<session_id>.jsonl plus its sibling
    <root>/<session_id>/subagents/ subtree."""

    PROJECT_DIRNAME = "-home-user-gms-marketplace"
    SESSION_ID = "sess-abcdef12"

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="acs-test-duration-")
        self.addCleanup(shutil.rmtree, self.root, True)
        self.project_dir = os.path.join(self.root, self.PROJECT_DIRNAME)
        self.transcript_path = os.path.join(self.project_dir, self.SESSION_ID + ".jsonl")

    def write_main(self, records):
        _write_jsonl(self.transcript_path, records)

    def write_subagent(self, name, records):
        path = os.path.join(self.project_dir, self.SESSION_ID, "subagents", name)
        _write_jsonl(path, records)

    def read(self, started_at="2026-01-01T00:00:00Z", ended_at="2026-01-01T00:10:00Z", skill="code"):
        return usage_reader.read_transcript_usage(self.transcript_path, started_at, ended_at, skill)

    def duration_by_role(self, result):
        return {item["role"]: item for item in result["role_duration"]}


class TestGapAttributedToEachTokenBearingRecordsOwnRole(DurationCase):
    def test_gap_before_each_token_bearing_record_is_attributed_to_its_role(self):
        self.write_main([
            _record("2026-01-01T00:00:00Z", usage=_usage(), attribution_skill="acs:code"),  # coordinator, first: 0
            _record("2026-01-01T00:00:04Z", usage=_usage()),  # unattributed, gap=4s from prior
            _record("2026-01-01T00:00:09Z", usage=_usage(), attribution_skill="acs:code"),  # coordinator, gap=5s
        ])
        result = self.read()
        self.assertFalse(result["degraded"])
        by_role = self.duration_by_role(result)
        self.assertEqual(by_role["coordinator"]["api_duration_ms"], 5000)
        self.assertEqual(by_role["unattributed"]["api_duration_ms"], 4000)


class TestGapBeforeNonUsageRecordNeverAttributed(DurationCase):
    def test_gap_before_a_record_without_usage_is_never_attributed(self):
        self.write_main([
            _record("2026-01-01T00:00:00Z", usage=_usage(), attribution_skill="acs:code"),
            _no_usage_record("2026-01-01T00:00:03Z"),
            _record("2026-01-01T00:00:07Z", usage=_usage(), attribution_skill="acs:code"),
        ])
        result = self.read()
        self.assertFalse(result["degraded"])
        # Only one role ever carried usage, so only one role_duration entry
        # exists -- and its total is 4000ms (07 - 03), never 7000ms (which
        # would mean the no-usage record was skipped rather than advancing
        # the predecessor) and never anything above 4000ms attributed
        # elsewhere (the no-usage record's own would-be 3000ms gap).
        self.assertEqual([item["role"] for item in result["role_duration"]], ["coordinator"])
        self.assertEqual(result["role_duration"][0]["api_duration_ms"], 4000)


class TestNegativeGapNeverSubtracts(DurationCase):
    def test_negative_gap_contributes_zero_not_a_negative_duration(self):
        self.write_main([
            _record("2026-01-01T00:00:10Z", usage=_usage(), attribution_skill="acs:code"),  # first: 0
            _record("2026-01-01T00:00:05Z", usage=_usage(), attribution_skill="acs:code"),  # gap=-5s -> 0
            _record("2026-01-01T00:00:20Z", usage=_usage(), attribution_skill="acs:code"),  # gap=+15s
        ])
        result = self.read()
        self.assertFalse(result["degraded"])
        by_role = self.duration_by_role(result)
        # 0 + 0 + 15000 = 15000. A bug that let the negative gap subtract
        # would instead total 10000 (15000 - 5000).
        self.assertEqual(by_role["coordinator"]["api_duration_ms"], 15000)


class TestGapAboveCapIsClamped(DurationCase):
    def test_gap_above_the_cap_is_clamped_to_max_record_gap_seconds(self):
        self.assertEqual(usage_reader.MAX_RECORD_GAP_SECONDS, 60)
        self.write_main([
            _record("2026-01-01T00:00:00Z", usage=_usage(), attribution_skill="acs:code"),
            _record("2026-01-01T00:05:00Z", usage=_usage(), attribution_skill="acs:code"),  # gap=300s
        ])
        result = self.read()
        self.assertFalse(result["degraded"])
        by_role = self.duration_by_role(result)
        self.assertEqual(by_role["coordinator"]["api_duration_ms"], 60000)


class TestFirstInWindowRecordContributesNoDuration(DurationCase):
    def test_first_in_window_record_of_a_file_contributes_no_duration(self):
        self.write_main([
            # First record of the file: no predecessor, so it contributes
            # nothing to ITS OWN role, even though a real gap follows it.
            _record("2026-01-01T00:00:00Z", usage=_usage(), attribution_skill="acs:code"),
            _record("2026-01-01T00:00:02Z", usage=_usage()),  # unattributed, gap=2s from the first record
        ])
        result = self.read()
        self.assertFalse(result["degraded"])
        by_role = self.duration_by_role(result)
        self.assertIsNone(by_role["coordinator"]["api_duration_ms"])
        self.assertEqual(by_role["coordinator"]["duration_basis"], "unavailable")
        self.assertEqual(by_role["unattributed"]["api_duration_ms"], 2000)


class TestOutOfWindowRecordExcludedFromPredecessorChain(DurationCase):
    def test_out_of_window_record_neither_contributes_nor_advances_the_predecessor(self):
        self.write_main([
            # Out of window (before the run's started_at): must be skipped
            # entirely -- neither charged nor used as the next record's
            # predecessor timestamp.
            _record("2025-12-31T23:50:00Z", usage=_usage(), attribution_skill="acs:code"),
            _record("2026-01-01T00:00:00Z", usage=_usage(), attribution_skill="acs:code"),  # first in-window: 0
            _record("2026-01-01T00:00:05Z", usage=_usage(), attribution_skill="acs:code"),  # gap=5s
        ])
        result = self.read()
        self.assertFalse(result["degraded"])
        by_role = self.duration_by_role(result)
        # If the out-of-window record had leaked in as a predecessor, the
        # 00:00:00 record's gap against 23:50:00 the prior day would be
        # clamped to the 60s cap, making the total 65000 instead of 5000.
        self.assertEqual(by_role["coordinator"]["api_duration_ms"], 5000)


class TestRoleWithNoAttributableGapIsUnavailableNeverZero(DurationCase):
    def test_role_with_no_attributable_gap_is_unavailable_never_zero_ms(self):
        self.write_main([
            _record("2026-01-01T00:00:20Z", usage=_usage(), attribution_skill="acs:code"),  # first: 0
            _record("2026-01-01T00:00:05Z", usage=_usage(), attribution_skill="acs:code"),  # gap=-15s -> 0
            _record("2026-01-01T00:00:01Z", usage=_usage(), attribution_skill="acs:code"),  # gap=-4s -> 0
        ])
        result = self.read()
        self.assertFalse(result["degraded"])
        by_role = self.duration_by_role(result)
        # Three records, all contributing 0 (first + two negative gaps): the
        # role's total is genuinely 0, and must publish None/"unavailable",
        # never a fabricated literal 0.
        self.assertEqual(by_role["coordinator"]["api_duration_ms"], None)
        self.assertEqual(by_role["coordinator"]["duration_basis"], "unavailable")


class TestDurationBasisAlwaysDerived(DurationCase):
    def test_duration_basis_is_always_derived_never_measured(self):
        self.write_main([
            _record("2026-01-01T00:00:00Z", usage=_usage(), attribution_skill="acs:code"),
            _record("2026-01-01T00:00:05Z", usage=_usage(), attribution_skill="acs:code"),
        ])
        result = self.read()
        self.assertFalse(result["degraded"])
        by_role = self.duration_by_role(result)
        self.assertEqual(by_role["coordinator"]["duration_basis"], "derived")
        for item in result["role_duration"]:
            self.assertIn(item["duration_basis"], ("derived", "unavailable"))
            self.assertNotEqual(item["duration_basis"], "measured")
            self.assertNotEqual(item["duration_basis"], "apportioned")


class TestSubagentAndMainSessionTrackPredecessorsIndependently(DurationCase):
    def test_subagent_and_main_session_files_track_predecessors_independently(self):
        self.write_main([
            # The main session's only record: first-of-file, contributes 0.
            _record("2026-01-01T00:00:00Z", usage=_usage(), attribution_skill="acs:code"),
        ])
        self.write_subagent("agent-1.jsonl", [
            # First record of the SUBAGENT file, even though 50s after the
            # main session's own record -- must NOT be charged against the
            # main file's prev_ts (which would clamp to 60000ms under the
            # cap, since 50s < 60s).
            _record("2026-01-01T00:00:50Z", usage=_usage(), attribution_agent="acs:code-executor"),
            # Second record of the subagent's own file: a real 5s gap within
            # its own independent chain.
            _record("2026-01-01T00:00:55Z", usage=_usage(), attribution_agent="acs:code-executor"),
        ])
        result = self.read()
        self.assertFalse(result["degraded"])
        by_role = self.duration_by_role(result)
        self.assertIsNone(by_role["coordinator"]["api_duration_ms"])
        self.assertEqual(by_role["coordinator"]["duration_basis"], "unavailable")
        self.assertEqual(by_role["executor"]["api_duration_ms"], 5000)


class TestDegradedReadReturnsEmptyRoleDuration(DurationCase):
    def test_degraded_read_returns_an_empty_role_duration_list(self):
        result = usage_reader.read_transcript_usage(None, "2026-01-01T00:00:00Z", None, "code")
        self.assertTrue(result["degraded"])
        self.assertEqual(result["role_duration"], [])

    def test_unreadable_transcript_degrades_with_empty_role_duration(self):
        os.makedirs(self.transcript_path, exist_ok=True)  # a directory, not a file: OSError on open()
        result = self.read()
        self.assertTrue(result["degraded"])
        self.assertEqual(result["role_duration"], [])


class TestDurationDerivationRespectsExistingCaps(DurationCase):
    def test_duration_derivation_opens_no_additional_file_and_respects_the_existing_caps(self):
        # Exactly two files (main + one subagent). If duration derivation
        # opened any file beyond the existing role_usage/model_usage scan,
        # this file-count cap of 2 would be exceeded and the read would
        # degrade instead of succeeding.
        original_max_files = usage_reader.MAX_FILES
        usage_reader.MAX_FILES = 2
        try:
            self.write_main([
                _record("2026-01-01T00:00:00Z", usage=_usage(), attribution_skill="acs:code"),
                _record("2026-01-01T00:00:05Z", usage=_usage(), attribution_skill="acs:code"),
            ])
            self.write_subagent("agent-1.jsonl", [
                _record("2026-01-01T00:00:06Z", usage=_usage(), attribution_agent="acs:code-executor"),
            ])
            result = self.read()
        finally:
            usage_reader.MAX_FILES = original_max_files
        self.assertFalse(result["degraded"])
        by_role = self.duration_by_role(result)
        self.assertEqual(by_role["coordinator"]["api_duration_ms"], 5000)

    def test_cap_exceeded_still_degrades_with_duration_derivation_active(self):
        original_max_bytes = usage_reader.MAX_BYTES
        usage_reader.MAX_BYTES = 10  # force an immediate byte-cap breach
        try:
            self.write_main([
                _record("2026-01-01T00:00:00Z", usage=_usage(), attribution_skill="acs:code"),
                _record("2026-01-01T00:00:05Z", usage=_usage(), attribution_skill="acs:code"),
            ])
            result = self.read()
        finally:
            usage_reader.MAX_BYTES = original_max_bytes
        self.assertTrue(result["degraded"])
        self.assertEqual(result["reason"], "cap_exceeded")
        self.assertEqual(result["role_duration"], [])


class TestRoleUsageAndModelUsageShapesUnchanged(DurationCase):
    def test_role_usage_and_model_usage_shapes_are_unchanged_by_duration_derivation(self):
        self.write_main([
            _record("2026-01-01T00:00:00Z", usage=_usage(10, 20, 0, 0),
                     attribution_skill="acs:code", model="claude-opus-4"),
            _record("2026-01-01T00:00:05Z", usage=_usage(30, 40, 0, 0)),  # unattributed
        ])
        result = self.read()
        self.assertFalse(result["degraded"])
        # role_usage keeps exactly its pre-existing five keys -- no
        # api_duration_ms/duration_basis leakage onto it.
        for item in result["role_usage"]:
            self.assertEqual(set(item.keys()), {"role", "input", "output", "cache_creation", "cache_read"})
        # model_usage is untouched: still keyed by "model", no role or
        # duration fields at all.
        for item in result["model_usage"]:
            self.assertEqual(set(item.keys()), {"model", "input", "output", "cache_creation", "cache_read"})
        # excluded_token_share is present and computed exactly as before.
        self.assertIn("excluded_token_share", result)
        self.assertAlmostEqual(result["excluded_token_share"], 70 / 100)
        # role_duration is a genuinely separate, parallel list.
        self.assertEqual({"coordinator", "unattributed"}, {i["role"] for i in result["role_duration"]})


if __name__ == "__main__":
    unittest.main()
