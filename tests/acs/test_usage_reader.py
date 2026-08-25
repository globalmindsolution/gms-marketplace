"""Behavior tests for usage_reader.read_transcript_usage (MAR-1).

Covers AC-3 (real message.usage token counts, all four classes, read from the
exact recorded transcript_path plus its own subagents/ subtree -- never a
constructed slug) and AC-4 (a first-class, non-empty "coordinator" role_usage
bucket, and unattributed same-window tokens dropped rather than redistributed,
with the dropped share recorded). Fixtures are synthetic transcript trees
built under tempfile.mkdtemp() -- never ~/.claude.
"""

import json
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

_SCRIPTS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "plugins", "acs", "hooks", "scripts",
)
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

import usage_reader  # noqa: E402


def _usage(input_tokens=0, output_tokens=0, cache_creation=0, cache_read=0):
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


def _write_jsonl(path, records):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(rec) + "\n")


class UsageReaderCase(unittest.TestCase):
    """Builds a synthetic <root>/<session_id>.jsonl transcript plus its
    sibling <root>/<session_id>/subagents/ subtree, exactly mirroring the
    real observed layout (design.md:1179-1181): dirname(transcript_path)/
    <session_id>/subagents/, where session_id is transcript_path's own
    basename minus extension -- never derived from cwd."""

    #: the fixture's project-directory name deliberately begins with "-",
    #: mirroring Claude Code's real "-home-user-<repo>" layout -- the exact
    #: shape that made tabp's cwd-slug construction (P1) silently return zero.
    PROJECT_DIRNAME = "-home-user-gms-marketplace"
    SESSION_ID = "sess-abcdef12"

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="acs-test-usage-")
        self.addCleanup(shutil.rmtree, self.root, True)
        self.project_dir = os.path.join(self.root, self.PROJECT_DIRNAME)
        self.transcript_path = os.path.join(self.project_dir, self.SESSION_ID + ".jsonl")

    def write_main(self, records):
        _write_jsonl(self.transcript_path, records)

    def write_subagent(self, name, records):
        path = os.path.join(self.project_dir, self.SESSION_ID, "subagents", name)
        _write_jsonl(path, records)


class TestCacheTokenFieldsCounted(UsageReaderCase):
    """P2 guard: all four usage-field classes are counted, not just two."""

    def test_all_four_fields_summed_into_the_role_bucket(self):
        self.write_main([
            _record("2026-01-01T00:00:10Z",
                     usage=_usage(10, 20, 30, 40),
                     attribution_skill="acs:code"),
        ])
        result = usage_reader.read_transcript_usage(
            self.transcript_path, "2026-01-01T00:00:00Z", "2026-01-01T00:01:00Z")
        self.assertFalse(result["degraded"])
        coordinator = next(r for r in result["role_usage"] if r["role"] == "coordinator")
        self.assertEqual(coordinator["input"], 10)
        self.assertEqual(coordinator["output"], 20)
        self.assertEqual(coordinator["cache_creation"], 30)
        self.assertEqual(coordinator["cache_read"], 40)


class TestSubagentsSubtreeIncluded(UsageReaderCase):
    """P3 guard: the subagents/ subtree is walked recursively, including a
    nested directory -- never a non-recursive glob."""

    def test_nested_subagent_file_is_included(self):
        self.write_main([
            _record("2026-01-01T00:00:05Z", usage=_usage(1, 1, 0, 0), attribution_skill="acs:code"),
        ])
        nested = os.path.join(self.project_dir, self.SESSION_ID, "subagents", "nested", "agent-1.jsonl")
        _write_jsonl(nested, [
            _record("2026-01-01T00:00:20Z", usage=_usage(5, 6, 7, 8),
                     attribution_agent="acs:code-executor"),
        ])
        result = usage_reader.read_transcript_usage(
            self.transcript_path, "2026-01-01T00:00:00Z", "2026-01-01T00:01:00Z")
        self.assertFalse(result["degraded"])
        executor = next(r for r in result["role_usage"] if r["role"] == "executor")
        self.assertEqual(executor, {"role": "executor", "input": 5, "output": 6,
                                     "cache_creation": 7, "cache_read": 8})


class TestNoSlugConstructed(UsageReaderCase):
    """P1 guard: a transcript path whose parent directory begins with a
    leading "-" (the real Claude Code project-dir shape) still resolves
    correctly -- the exact case that made tabp silently return zeros."""

    def test_leading_dash_project_dir_resolves_real_tokens(self):
        self.assertTrue(os.path.basename(self.project_dir).startswith("-"))
        self.write_main([
            _record("2026-01-01T00:00:05Z", usage=_usage(100, 200, 0, 0), attribution_skill="acs:code"),
        ])
        self.write_subagent("agent-1.jsonl", [
            _record("2026-01-01T00:00:06Z", usage=_usage(3, 4, 0, 0),
                     attribution_agent="acs:code-verifier"),
        ])
        result = usage_reader.read_transcript_usage(
            self.transcript_path, "2026-01-01T00:00:00Z", "2026-01-01T00:01:00Z")
        self.assertFalse(result["degraded"])
        totals = {r["role"]: r for r in result["role_usage"]}
        self.assertEqual(totals["coordinator"]["input"], 100)
        self.assertEqual(totals["verifier"]["input"], 3)


class TestCoordinatorBucketPresent(UsageReaderCase):
    """AC-4: a coordinator role_usage bucket is present and non-empty for a
    run whose main-session records carry the (own) attributionSkill."""

    def test_coordinator_bucket_non_empty(self):
        self.write_main([
            _record("2026-01-01T00:00:05Z", usage=_usage(50, 60, 0, 0), attribution_skill="acs:create-design"),
        ])
        result = usage_reader.read_transcript_usage(
            self.transcript_path, "2026-01-01T00:00:00Z", "2026-01-01T00:01:00Z")
        self.assertFalse(result["degraded"])
        coordinator = [r for r in result["role_usage"] if r["role"] == "coordinator"]
        self.assertEqual(len(coordinator), 1)
        self.assertGreater(coordinator[0]["input"] + coordinator[0]["output"], 0)


class TestUnattributedTokensDropped(UsageReaderCase):
    """AC-4/C-8: same-window tokens with no attributionSkill/attributionAgent
    are dropped, not redistributed onto attributed roles, with the dropped
    share recorded on the result rather than silently vanishing."""

    def test_unattributed_tokens_excluded_not_redistributed(self):
        self.write_main([
            _record("2026-01-01T00:00:05Z", usage=_usage(100, 0, 0, 0), attribution_skill="acs:code"),
            _record("2026-01-01T00:00:06Z", usage=_usage(300, 0, 0, 0)),  # no attributionSkill
        ])
        result = usage_reader.read_transcript_usage(
            self.transcript_path, "2026-01-01T00:00:00Z", "2026-01-01T00:01:00Z")
        self.assertFalse(result["degraded"])
        coordinator = next(r for r in result["role_usage"] if r["role"] == "coordinator")
        # The unattributed 300 must not land on coordinator (100 only).
        self.assertEqual(coordinator["input"], 100)
        self.assertEqual(len(result["role_usage"]), 1)
        self.assertIn("excluded_token_share", result)
        self.assertAlmostEqual(result["excluded_token_share"], 300 / 400)


class TestMetaJsonNeverOpened(UsageReaderCase):
    """Privacy boundary: subagents/*.meta.json is never opened, even when
    present -- proved by a booby-trapped sidecar (a directory in place of a
    file, so opening it would raise) that the read must never touch."""

    def test_booby_trapped_meta_json_does_not_break_the_read(self):
        self.write_main([
            _record("2026-01-01T00:00:05Z", usage=_usage(1, 1, 0, 0), attribution_skill="acs:code"),
        ])
        self.write_subagent("agent-1.jsonl", [
            _record("2026-01-01T00:00:06Z", usage=_usage(2, 2, 0, 0),
                     attribution_agent="acs:code-planner"),
        ])
        # A directory named like a meta.json sidecar: any attempt to open()
        # it as a file raises IsADirectoryError.
        booby = os.path.join(self.project_dir, self.SESSION_ID, "subagents", "agent-1.meta.json")
        os.makedirs(booby, exist_ok=True)

        result = usage_reader.read_transcript_usage(
            self.transcript_path, "2026-01-01T00:00:00Z", "2026-01-01T00:01:00Z")
        self.assertFalse(result["degraded"])
        planner = next(r for r in result["role_usage"] if r["role"] == "planner")
        self.assertEqual(planner["input"], 2)


class TestDegradedNeverRaises(UsageReaderCase):
    """An unreadable transcript file, an empty/invalid time window, and a cap
    breach each return degraded=true with a reason -- and never raise."""

    def test_unreadable_transcript_file_degrades(self):
        # A directory in place of the transcript file: open() raises
        # IsADirectoryError -- root-proof, unlike a chmod-based fixture.
        os.makedirs(self.transcript_path, exist_ok=True)
        result = usage_reader.read_transcript_usage(
            self.transcript_path, "2026-01-01T00:00:00Z", "2026-01-01T00:01:00Z")
        self.assertTrue(result["degraded"])
        self.assertEqual(result["reason"], "unreadable_transcript")

    def test_missing_transcript_file_degrades(self):
        result = usage_reader.read_transcript_usage(
            os.path.join(self.project_dir, "does-not-exist.jsonl"),
            "2026-01-01T00:00:00Z", "2026-01-01T00:01:00Z")
        self.assertTrue(result["degraded"])
        self.assertEqual(result["reason"], "unreadable_transcript")

    def test_empty_window_missing_started_at_degrades(self):
        self.write_main([_record("2026-01-01T00:00:05Z", usage=_usage(1, 1, 0, 0),
                                  attribution_skill="acs:code")])
        result = usage_reader.read_transcript_usage(self.transcript_path, None, None)
        self.assertTrue(result["degraded"])
        self.assertEqual(result["reason"], "empty_window")

    def test_inverted_window_degrades(self):
        self.write_main([_record("2026-01-01T00:00:05Z", usage=_usage(1, 1, 0, 0),
                                  attribution_skill="acs:code")])
        result = usage_reader.read_transcript_usage(
            self.transcript_path, "2026-01-01T00:01:00Z", "2026-01-01T00:00:00Z")
        self.assertTrue(result["degraded"])
        self.assertEqual(result["reason"], "empty_window")

    def test_no_session_marker_degrades(self):
        result = usage_reader.read_transcript_usage(None, "2026-01-01T00:00:00Z", None)
        self.assertTrue(result["degraded"])
        self.assertEqual(result["reason"], "no_session_marker")

    def test_cap_exceeded_degrades(self):
        original_max_bytes = usage_reader.MAX_BYTES
        usage_reader.MAX_BYTES = 10  # force an immediate breach
        try:
            self.write_main([
                _record("2026-01-01T00:00:05Z", usage=_usage(1, 1, 0, 0), attribution_skill="acs:code"),
                _record("2026-01-01T00:00:06Z", usage=_usage(1, 1, 0, 0), attribution_skill="acs:code"),
            ])
            result = usage_reader.read_transcript_usage(
                self.transcript_path, "2026-01-01T00:00:00Z", "2026-01-01T00:01:00Z")
        finally:
            usage_reader.MAX_BYTES = original_max_bytes
        self.assertTrue(result["degraded"])
        self.assertEqual(result["reason"], "cap_exceeded")

    def test_file_count_cap_exceeded_degrades(self):
        original_max_files = usage_reader.MAX_FILES
        usage_reader.MAX_FILES = 1  # the main transcript alone already exhausts it
        try:
            self.write_main([
                _record("2026-01-01T00:00:05Z", usage=_usage(1, 1, 0, 0), attribution_skill="acs:code"),
            ])
            self.write_subagent("agent-1.jsonl", [
                _record("2026-01-01T00:00:06Z", usage=_usage(1, 1, 0, 0),
                         attribution_agent="acs:code-executor"),
            ])
            result = usage_reader.read_transcript_usage(
                self.transcript_path, "2026-01-01T00:00:00Z", "2026-01-01T00:01:00Z")
        finally:
            usage_reader.MAX_FILES = original_max_files
        self.assertTrue(result["degraded"])
        self.assertEqual(result["reason"], "cap_exceeded")


class TestZeroTokensNeverAValidZero(UsageReaderCase):
    """R1: a run resolving zero real tokens is degraded, never a bare valid 0
    -- even when the transcript exists and the window is well-formed."""

    def test_valid_but_empty_window_degrades(self):
        self.write_main([
            _record("2026-01-01T05:00:00Z", usage=_usage(10, 10, 0, 0), attribution_skill="acs:code"),
        ])
        # A well-formed window that simply contains no matching records.
        result = usage_reader.read_transcript_usage(
            self.transcript_path, "2026-01-01T00:00:00Z", "2026-01-01T00:01:00Z")
        self.assertTrue(result["degraded"])
        self.assertEqual(result["reason"], "no_tokens_in_window")

    def test_empty_transcript_file_degrades(self):
        self.write_main([])
        result = usage_reader.read_transcript_usage(
            self.transcript_path, "2026-01-01T00:00:00Z", "2026-01-01T00:01:00Z")
        self.assertTrue(result["degraded"])
        self.assertEqual(result["reason"], "no_tokens_in_window")


class TestUnmappedAttributionSkillBucketsAsUnknownSkill(UsageReaderCase):
    """A present-but-unrecognized attributionSkill is bucketed as
    "unknown-skill" rather than dropped -- distinct from a genuinely absent
    attributionSkill, which IS dropped (TestUnattributedTokensDropped)."""

    def test_unrecognized_attribution_skill_is_not_dropped(self):
        self.write_main([
            _record("2026-01-01T00:00:05Z", usage=_usage(7, 7, 0, 0),
                     attribution_skill="acs:totally-unregistered-skill"),
        ])
        result = usage_reader.read_transcript_usage(
            self.transcript_path, "2026-01-01T00:00:00Z", "2026-01-01T00:01:00Z")
        self.assertFalse(result["degraded"])
        bucket = next(r for r in result["role_usage"] if r["role"] == "unknown-skill")
        self.assertEqual(bucket["input"], 7)


class TestSubagentUnattributedAndOtherRole(UsageReaderCase):
    """Subagent-side mirror of TestUnattributedTokensDropped/TestUnmapped...:
    an attributionAgent-less subagent record is dropped, and an unmatched
    (non-planner/executor/verifier) attributionAgent buckets as "other"."""

    def test_subagent_record_without_attribution_agent_is_dropped(self):
        self.write_main([
            _record("2026-01-01T00:00:05Z", usage=_usage(10, 0, 0, 0), attribution_skill="acs:code"),
        ])
        self.write_subagent("agent-1.jsonl", [
            _record("2026-01-01T00:00:06Z", usage=_usage(90, 0, 0, 0)),  # no attributionAgent
        ])
        result = usage_reader.read_transcript_usage(
            self.transcript_path, "2026-01-01T00:00:00Z", "2026-01-01T00:01:00Z")
        self.assertFalse(result["degraded"])
        self.assertEqual(len(result["role_usage"]), 1)
        self.assertAlmostEqual(result["excluded_token_share"], 90 / 100)

    def test_unmatched_attribution_agent_buckets_as_other(self):
        self.write_main([
            _record("2026-01-01T00:00:05Z", usage=_usage(1, 0, 0, 0), attribution_skill="acs:code"),
        ])
        self.write_subagent("agent-1.jsonl", [
            _record("2026-01-01T00:00:06Z", usage=_usage(12, 0, 0, 0), attribution_agent="Explore"),
        ])
        result = usage_reader.read_transcript_usage(
            self.transcript_path, "2026-01-01T00:00:00Z", "2026-01-01T00:01:00Z")
        self.assertFalse(result["degraded"])
        other = next(r for r in result["role_usage"] if r["role"] == "other")
        self.assertEqual(other["input"], 12)


class TestUnreadableIndividualSubagentFileIsSkipped(UsageReaderCase):
    """One unreadable subagent file (a broken symlink -- OSError on open(),
    robust even running as root) does not sink an otherwise-good read."""

    def test_broken_symlink_subagent_file_is_skipped(self):
        self.write_main([
            _record("2026-01-01T00:00:05Z", usage=_usage(5, 0, 0, 0), attribution_skill="acs:code"),
        ])
        subagents_dir = os.path.join(self.project_dir, self.SESSION_ID, "subagents")
        os.makedirs(subagents_dir, exist_ok=True)
        broken = os.path.join(subagents_dir, "agent-broken.jsonl")
        os.symlink(os.path.join(subagents_dir, "does-not-exist"), broken)

        result = usage_reader.read_transcript_usage(
            self.transcript_path, "2026-01-01T00:00:00Z", "2026-01-01T00:01:00Z")
        self.assertFalse(result["degraded"])
        coordinator = next(r for r in result["role_usage"] if r["role"] == "coordinator")
        self.assertEqual(coordinator["input"], 5)


class TestBlankLineAndMalformedRecordsSkipped(UsageReaderCase):
    """A blank line, a non-dict JSON value, a non-dict message, and a
    non-dict usage are each skipped rather than raising or counting."""

    def test_blank_and_malformed_records_do_not_break_the_read(self):
        os.makedirs(self.project_dir, exist_ok=True)
        with open(self.transcript_path, "w", encoding="utf-8") as fh:
            fh.write("\n")                                  # blank line
            fh.write(json.dumps([1, 2, 3]) + "\n")           # not a dict
            fh.write(json.dumps({"timestamp": "2026-01-01T00:00:05Z",
                                  "message": "not-a-dict"}) + "\n")
            fh.write(json.dumps({"timestamp": "2026-01-01T00:00:06Z",
                                  "message": {"usage": "not-a-dict"}}) + "\n")
            fh.write(json.dumps(_record("2026-01-01T00:00:07Z", usage=_usage(0, 0, 0, 0),
                                         attribution_skill="acs:code")) + "\n")  # all-zero usage
            fh.write(json.dumps(_record("2026-01-01T00:00:08Z", usage=_usage(3, 0, 0, 0),
                                         attribution_skill="acs:code")) + "\n")
        result = usage_reader.read_transcript_usage(
            self.transcript_path, "2026-01-01T00:00:00Z", "2026-01-01T00:01:00Z")
        self.assertFalse(result["degraded"])
        coordinator = next(r for r in result["role_usage"] if r["role"] == "coordinator")
        self.assertEqual(coordinator["input"], 3)


class TestUnexpectedErrorNeverRaises(UsageReaderCase):
    """A genuinely unexpected internal failure still degrades rather than
    propagating -- the outer safety net, distinct from the specific
    unreadable/cap/window guards tested elsewhere."""

    def test_unexpected_exception_degrades_instead_of_raising(self):
        self.write_main([
            _record("2026-01-01T00:00:05Z", usage=_usage(1, 0, 0, 0), attribution_skill="acs:code"),
        ])
        with mock.patch.object(usage_reader, "_scan_file", side_effect=RuntimeError("boom")):
            result = usage_reader.read_transcript_usage(
                self.transcript_path, "2026-01-01T00:00:00Z", "2026-01-01T00:01:00Z")
        self.assertTrue(result["degraded"])
        self.assertEqual(result["reason"], "unexpected_error")


class TestOpenEndedWindow(UsageReaderCase):
    """ended_at=None means no upper bound (an in-progress run's window)."""

    def test_none_ended_at_has_no_upper_bound(self):
        self.write_main([
            _record("2026-06-01T00:00:00Z", usage=_usage(9, 9, 0, 0), attribution_skill="acs:code"),
        ])
        result = usage_reader.read_transcript_usage(
            self.transcript_path, "2026-01-01T00:00:00Z", None)
        self.assertFalse(result["degraded"])
        coordinator = next(r for r in result["role_usage"] if r["role"] == "coordinator")
        self.assertEqual(coordinator["input"], 9)


class TestCorruptLineSkipped(UsageReaderCase):
    """A corrupt JSON line is skipped, never raised on."""

    def test_corrupt_line_is_skipped_not_fatal(self):
        os.makedirs(self.project_dir, exist_ok=True)
        with open(self.transcript_path, "w", encoding="utf-8") as fh:
            fh.write("not json at all\n")
            fh.write(json.dumps(_record("2026-01-01T00:00:05Z", usage=_usage(4, 4, 0, 0),
                                         attribution_skill="acs:code")) + "\n")
        result = usage_reader.read_transcript_usage(
            self.transcript_path, "2026-01-01T00:00:00Z", "2026-01-01T00:01:00Z")
        self.assertFalse(result["degraded"])
        coordinator = next(r for r in result["role_usage"] if r["role"] == "coordinator")
        self.assertEqual(coordinator["input"], 4)


if __name__ == "__main__":
    unittest.main()
