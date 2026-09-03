"""Behavior tests for the pre-hook session marker: acs_lib.session_marker_path,
acs_lib.record_session_marker, and append_in_progress_run's session threading.

Originating ticket: MAR-1. Covers design.md section SS1.1 (session-anchored
correlation, corrected from the tabp precedent's cwd-slug guess): the marker
round-trips through session_marker_path/record_session_marker, a missing
envelope field is persisted as null rather than guessed, append_in_progress_run
keeps every existing caller's run-entry shape byte-identical when session is
left at its default, and a bug inside record_session_marker must never make
run_pre fail closed (block the skill) -- that wrapper is the single most
important behavior in this unit.
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

sys.path.insert(0, os.path.join(REPO_ROOT, "tests", "acs"))
from acs_case import AcsWorkspaceCase  # noqa: E402


class TestAttributionSkillMap(unittest.TestCase):
    """design.md's Module map (SS "Module map and attribution mapping"):
    ATTRIBUTION_SKILL_MAP is the explicit override table for observed
    attributionSkill values that don't literally match a skill name once the
    "acs:" prefix is stripped -- e.g. the setup skill (renamed under MAR-1
    from initialize, itself renamed under MAR-184 from init) is observed on
    the wire as either historical name, "acs:init" or "acs:initialize", never
    "acs:setup". "ship" needs no override since stripping "acs:" from
    "acs:ship" already yields the literal skill name."""

    def test_init_overrides_to_setup(self):
        self.assertEqual(lib.ATTRIBUTION_SKILL_MAP["init"], "setup")

    def test_initialize_overrides_to_setup(self):
        self.assertEqual(lib.ATTRIBUTION_SKILL_MAP["initialize"], "setup")

    def test_covers_both_hooked_and_unhooked_skill_universes(self):
        # The map's target values must all be real skill names -- either
        # HOOKED_SKILLS or UNHOOKED_SKILLS, never a made-up bucket.
        for target in lib.ATTRIBUTION_SKILL_MAP.values():
            self.assertIn(target, lib.HOOKED_SKILLS + lib.UNHOOKED_SKILLS)


class TestSessionMarkerPath(unittest.TestCase):
    """session_marker_path is a sibling of the existing per-checkout pointer:
    same sessions/ directory, `<ckid>-session.json` rather than `<ckid>.json`."""

    def test_sibling_of_pointer_path(self):
        pointer = lib.pointer_path("/ws", "acme-shop", "shop-ab12cd34")
        marker = lib.session_marker_path("/ws", "acme-shop", "shop-ab12cd34")
        self.assertEqual(os.path.dirname(marker), os.path.dirname(pointer))
        self.assertEqual(os.path.basename(marker), "shop-ab12cd34-session.json")


class TestRecordSessionMarker(AcsWorkspaceCase):
    """record_session_marker persists the envelope's correlation fields via
    the existing atomic write_json, at session_marker_path."""

    def test_round_trip_persists_envelope_fields(self):
        ctx = lib.build_context(self.repo)
        payload = {
            "session_id": "sess-123",
            "transcript_path": "/home/user/.claude/projects/x/sess-123.jsonl",
            "cwd": self.repo,
            "hook_event_name": "PreToolUse",
            "tool_input": {"skill": "acs:code"},
        }
        marker = lib.record_session_marker(ctx, payload)

        on_disk = lib.read_json(
            lib.session_marker_path(ctx["workspace"], ctx["repo_id"], ctx["checkout_id"]))
        self.assertEqual(on_disk, marker)
        self.assertEqual(on_disk["session_id"], "sess-123")
        self.assertEqual(on_disk["transcript_path"],
                         "/home/user/.claude/projects/x/sess-123.jsonl")
        self.assertEqual(on_disk["cwd"], self.repo)
        self.assertEqual(on_disk["checkout_id"], ctx["checkout_id"])
        self.assertEqual(on_disk["hook_event_name"], "PreToolUse")
        self.assertIn("updated_at", on_disk)
        self.assertIsInstance(on_disk["updated_at"], str)

    def test_missing_envelope_field_persists_as_null_never_a_guess(self):
        ctx = lib.build_context(self.repo)
        # No session_id, no transcript_path, no hook_event_name, no tool_input --
        # record_session_marker must never fall back to constructing/guessing
        # a value (e.g. from cwd) for any of them.
        marker = lib.record_session_marker(ctx, {"cwd": self.repo})
        self.assertIsNone(marker["session_id"])
        self.assertIsNone(marker["transcript_path"])
        self.assertIsNone(marker["hook_event_name"])
        self.assertIsNone(marker["skill"])

        on_disk = lib.read_json(
            lib.session_marker_path(ctx["workspace"], ctx["repo_id"], ctx["checkout_id"]))
        self.assertIsNone(on_disk["session_id"])
        self.assertIsNone(on_disk["transcript_path"])


class TestAppendInProgressRunSession(unittest.TestCase):
    """append_in_progress_run gains an optional session=None parameter; the
    default leaves every existing caller's entry shape byte-identical."""

    def setUp(self):
        self.tdir = tempfile.mkdtemp(prefix="acs-test-")
        self.addCleanup(lambda: __import__("shutil").rmtree(self.tdir, ignore_errors=True))

    def test_default_session_none_leaves_entry_shape_unchanged(self):
        state = lib.append_in_progress_run(self.tdir, "code", "SHOP-1")
        entry = state["runs"][-1]
        self.assertNotIn("session_id", entry)
        self.assertNotIn("transcript_path", entry)
        self.assertEqual(set(entry.keys()),
                         {"started_at", "ended_at", "tokens", "cost_usd", "status", "stop_reason"})

    def test_session_marker_persists_session_id_and_transcript_path(self):
        marker = {"session_id": "sess-abc", "transcript_path": "/tmp/sess-abc.jsonl"}
        state = lib.append_in_progress_run(self.tdir, "code", "SHOP-1", session=marker)
        entry = state["runs"][-1]
        self.assertEqual(entry["session_id"], "sess-abc")
        self.assertEqual(entry["transcript_path"], "/tmp/sess-abc.jsonl")

    def test_new_ticket_py_real_call_site_unaffected(self):
        """new-ticket.py:117 calls append_in_progress_run(tdir, "create-ticket",
        ticket_id) with no session argument -- grounds the "existing callers keep
        working" claim against the actual second call site, not just this
        module's own fixtures."""
        with open(os.path.join(SCRIPTS, "new-ticket.py")) as fh:
            body = fh.read()
        self.assertIn('lib.append_in_progress_run(tdir, "create-ticket", ticket_id)', body)
        state = lib.append_in_progress_run(self.tdir, "create-ticket", "SHOP-2")
        self.assertNotIn("session_id", state["runs"][-1])


class TestStalenessGuardFieldContract(unittest.TestCase):
    """The staleness/cross-session guard itself lives in skill-start.py and is
    exercised end-to-end in test_skill_start.py; this just pins the marker's
    on-disk field names the guard depends on (checkout_id, updated_at)."""

    def test_marker_carries_checkout_id_and_updated_at(self):
        tmp = tempfile.mkdtemp(prefix="acs-test-")
        self.addCleanup(lambda: __import__("shutil").rmtree(tmp, ignore_errors=True))
        ctx = {"workspace": tmp, "repo_id": "acme-shop", "checkout_id": "shop-deadbeef"}
        marker = lib.record_session_marker(ctx, {"session_id": "s1", "cwd": "/x"})
        self.assertEqual(marker["checkout_id"], "shop-deadbeef")
        self.assertIn("updated_at", marker)


class TestRunPreFailClosedRegressionGuard(AcsWorkspaceCase):
    """THE single most important test in this unit: a raised exception inside
    record_session_marker must not make run_pre exit 2. gate_create_ticket
    (acs_lib.py:1805) is an unconditional pass with no I/O of its own, so any
    exit 2 here can only be caused by an unwrapped marker-write bug. Driven via
    subprocess (never in-process) because run_pre resolves cwd from the process
    per Risk R1 -- see test_acs_lib_hook_entrypoints.py's module docstring."""

    def test_marker_write_failure_does_not_block_the_gate(self):
        # Force acs_lib.write_json's os.makedirs(dirname(sessions/...)) to raise
        # inside record_session_marker by pre-creating sessions/ as a plain file
        # instead of a directory -- a real, deterministic failure mode requiring
        # no monkeypatching across the subprocess boundary.
        sessions_path = lib.sessions_dir(self.ws, "acme-shop")
        os.makedirs(os.path.dirname(sessions_path), exist_ok=True)
        with open(sessions_path, "w") as fh:
            fh.write("not a directory")

        result = self.run_script(
            "pre-create-ticket.py",
            stdin=json.dumps({"cwd": self.repo, "session_id": "sess-1",
                              "transcript_path": "/tmp/sess-1.jsonl"}))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("unexpected error in gate", result.stderr)


if __name__ == "__main__":
    unittest.main()
