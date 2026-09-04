"""Behavior tests for acs_lib.py's state files, ticket ledger, locking, and
context-resolution helpers.

Originating ticket: MAR-173. resolve_ticket_id's pointer-file and branch-name
fallback arms, last_run_status's absent/empty/non-list-runs arm, finalize_run's
invalid-status guard and no-in-progress-run synthesis and findings/errors
persistence, record_escalation_event's no-run-entry guard, compute_ticket_totals's
non-dict-entry skip, allocate_ticket_id's stale-guard removal / live-guard wait /
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
        lib.write_json(pointer, {"ticket_id": "SHOP-77"})
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
        self.assertIsNone(lib.last_run_status(self.tdir, "code"))
        lib.write_json(lib.state_path(self.tdir, "code"), {"runs": []})
        self.assertIsNone(lib.last_run_status(self.tdir, "code"))
        lib.write_json(lib.state_path(self.tdir, "code"), {"runs": "oops"})
        self.assertIsNone(lib.last_run_status(self.tdir, "code"))


class TestFinalizeRun(unittest.TestCase):
    """1083: raises ValueError for an invalid or in_progress final status;
    1086-1087: synthesizes a run entry when none was registered in_progress;
    1099/1101: persists findings/errors from the result document."""

    def setUp(self):
        self.tdir = tempfile.mkdtemp(prefix="acs-test-")
        self.addCleanup(shutil.rmtree, self.tdir, True)

    def test_raises_for_invalid_or_in_progress_status(self):
        with self.assertRaises(ValueError):
            lib.finalize_run(self.tdir, "code", "SHOP-1", {"status": "bogus"})
        with self.assertRaises(ValueError):
            lib.finalize_run(self.tdir, "code", "SHOP-1", {"status": "in_progress"})

    def test_raises_when_the_result_states_no_status(self):
        """finalize_run writes the status the next pre-hook gates on, so it is
        the last place a missing one can still be caught. It used to default to
        "completed" here -- refusing only at the CLI boundary left the silent
        default intact at the point of persistence, reachable by any in-process
        caller."""
        with self.assertRaises(ValueError) as ctx:
            lib.finalize_run(self.tdir, "code", "SHOP-1", {"stop_reason": "no status given"})
        self.assertIn("None", str(ctx.exception))
        self.assertEqual(lib.load_state(self.tdir, "code", "SHOP-1").get("runs", []), [])

    def test_synthesizes_run_entry_when_none_in_progress(self):
        state, entry = lib.finalize_run(self.tdir, "code", "SHOP-1", {"status": "completed"})
        self.assertEqual(entry["status"], "completed")
        self.assertEqual(len(state["runs"]), 1)

    def test_persists_findings_and_errors_from_result(self):
        lib.append_in_progress_run(self.tdir, "code", "SHOP-1")
        state, entry = lib.finalize_run(self.tdir, "code", "SHOP-1", {
            "status": "completed",
            "findings": [{"severity": "info", "summary": "x"}],
            "errors": ["boom"],
        })
        self.assertEqual(state["findings"], [{"severity": "info", "summary": "x"}])
        self.assertEqual(state["errors"], ["boom"])
        self.assertEqual(entry["status"], "completed")

    def test_persists_measured_tokens_and_role_usage_not_coordinator_self_report(self):
        """AC-3: a coordinator-supplied tokens/cost_usd self-estimate in
        `result` is ignored; the persisted figures come from
        usage_reader/cost_sampler instead."""
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
        measured_model_usage = [
            {"model": "claude-opus", "input": 10, "output": 20, "cache_creation": 0, "cache_read": 0},
        ]
        priced_model_usage = [
            {"model": "claude-opus", "input": 10, "output": 20, "cache_creation": 0, "cache_read": 0,
             "cost_usd": 0.05, "cost_basis": "apportioned"},
        ]
        with mock.patch("usage_reader.read_transcript_usage") as read_usage, \
                mock.patch("cost_sampler.allocate_cost") as allocate:
            read_usage.return_value = {
                "degraded": False, "reason": None, "role_usage": measured_role_usage,
                "model_usage": measured_model_usage,
            }
            allocate.return_value = {
                "role_usage": priced_role_usage, "model_usage": priced_model_usage,
                "cost_usd": 0.05, "cost_basis": "measured", "cost_scope": "session_total",
                "excluded_cost_usd": 0.0, "excluded_token_share": 0.0,
                "api_duration_ms": None, "api_duration_basis": "unavailable",
                "api_duration_scope": "duration_unavailable_on_cursor",
            }
            state, entry = lib.finalize_run(self.tdir, "code", "SHOP-1", {
                "status": "completed",
                "tokens": {"input": 999999, "output": 999999},
                "cost_usd": 123.45,
            })
        read_usage.assert_called_once_with(
            "/fake/sess-1.jsonl", entry["started_at"], entry["ended_at"], "code")
        allocate.assert_called_once_with(
            os.path.dirname(os.path.dirname(self.tdir)), os.path.basename(os.path.dirname(self.tdir)),
            "ck-1", entry["started_at"], entry["ended_at"], measured_role_usage, measured_model_usage)
        self.assertEqual(entry["tokens"], {"input": 10, "output": 20, "cache_creation": 0, "cache_read": 0})
        self.assertEqual(entry["role_usage"], priced_role_usage)
        self.assertEqual(entry["model_usage"], priced_model_usage)
        self.assertEqual(entry["cost_usd"], 0.05)
        self.assertEqual(entry["cost_basis"], "measured")

    def test_own_skill_is_threaded_through_to_usage_reader_not_hardcoded(self):
        """finalize_run's own `skill` argument -- not a fixed constant -- is
        what reaches usage_reader.read_transcript_usage, so a run's own-skill
        filter always matches this run's own skill, whichever skill it is."""
        lib.append_in_progress_run(self.tdir, "create-design", "SHOP-1", session={
            "session_id": "sess-2", "transcript_path": "/fake/sess-2.jsonl", "checkout_id": "ck-2",
        })
        with mock.patch("usage_reader.read_transcript_usage") as read_usage, \
                mock.patch("cost_sampler.allocate_cost") as allocate:
            read_usage.return_value = {
                "degraded": False, "reason": None, "role_usage": [], "model_usage": [],
            }
            allocate.return_value = {
                "role_usage": [], "model_usage": [],
                "cost_usd": None, "cost_basis": "unavailable", "cost_scope": "session_total",
                "excluded_cost_usd": 0.0, "excluded_token_share": 0.0,
                "api_duration_ms": None, "api_duration_basis": "unavailable",
                "api_duration_scope": "duration_unavailable_on_cursor",
            }
            state, entry = lib.finalize_run(self.tdir, "create-design", "SHOP-1", {"status": "completed"})
        read_usage.assert_called_once_with(
            "/fake/sess-2.jsonl", entry["started_at"], entry["ended_at"], "create-design")

    def test_no_session_id_finalizes_completed_with_cost_unavailable_and_no_transcript_io(self):
        """Required short-circuit (Risk R-N): a run entry with no session_id/
        transcript_path (e.g. new-ticket.py's synthetic create-ticket runs)
        performs NO transcript I/O and finalizes as completed/unavailable."""
        lib.append_in_progress_run(self.tdir, "code", "SHOP-1")
        with mock.patch("usage_reader.read_transcript_usage") as read_usage:
            state, entry = lib.finalize_run(self.tdir, "code", "SHOP-1", {"status": "completed"})
        read_usage.assert_not_called()
        self.assertEqual(entry["status"], "completed")
        self.assertIsNone(entry["cost_usd"])
        self.assertEqual(entry["cost_basis"], "unavailable")
        self.assertEqual(entry["tokens"], {"input": 0, "output": 0, "cache_creation": 0, "cache_read": 0})
        self.assertEqual(entry["model_usage"], [])

    def test_degraded_transcript_read_never_charges_or_calls_allocate_cost(self):
        """FIX 2: a degraded usage_reader result (unreadable file, cap
        breach, no tokens in window, ...) must never look like a successful
        measurement -- cost_usd stays None/cost_basis="unavailable", tokens
        stay empty, role_usage stays empty, and allocate_cost is never
        invoked (no degraded run may consume a real cost sample or advance
        the per-checkout cursor)."""
        lib.append_in_progress_run(self.tdir, "code", "SHOP-1", session={
            "session_id": "sess-1", "transcript_path": "/fake/sess-1.jsonl", "checkout_id": "ck-1",
        })
        with mock.patch("usage_reader.read_transcript_usage") as read_usage, \
                mock.patch("cost_sampler.allocate_cost") as allocate:
            read_usage.return_value = {
                "degraded": True, "reason": "cap_exceeded", "role_usage": [], "model_usage": [],
            }
            state, entry = lib.finalize_run(self.tdir, "code", "SHOP-1", {"status": "completed"})
        allocate.assert_not_called()
        self.assertIsNone(entry["cost_usd"])
        self.assertEqual(entry["cost_basis"], "unavailable")
        self.assertEqual(entry["tokens"], {"input": 0, "output": 0, "cache_creation": 0, "cache_read": 0})
        self.assertEqual(entry["role_usage"], [])
        self.assertEqual(entry["model_usage"], [])

    def test_ticket_rollup_reflects_only_attributed_spend_not_full_delta(self):
        """FIX 1 composition test: finalize_run persists cost_sampler's
        attributed-only cost_usd onto the run entry, and compute_ticket_totals
        sums exactly that figure -- a ticket with a non-zero excluded_token_share
        on one of its runs must never roll up the full (unattributed-inclusive)
        session-window delta into its cost_usd total."""
        lib.append_in_progress_run(self.tdir, "code", "SHOP-1", session={
            "session_id": "sess-1", "transcript_path": "/fake/sess-1.jsonl", "checkout_id": "ck-1",
        })
        measured_role_usage = [
            {"role": "executor", "input": 25, "output": 0, "cache_creation": 0, "cache_read": 0},
            {"role": "unattributed", "input": 75, "output": 0, "cache_creation": 0, "cache_read": 0},
        ]
        # delta was 10.0; 75% of tokens are unattributed -> attributed-only
        # cost_usd of 2.5, matching cost_sampler.allocate_cost's own contract.
        priced_role_usage = [
            {"role": "executor", "input": 25, "output": 0, "cache_creation": 0, "cache_read": 0,
             "cost_usd": 2.5, "cost_basis": "apportioned"},
            {"role": "unattributed", "input": 75, "output": 0, "cache_creation": 0, "cache_read": 0,
             "cost_usd": None, "cost_basis": "unavailable"},
        ]
        with mock.patch("usage_reader.read_transcript_usage") as read_usage, \
                mock.patch("cost_sampler.allocate_cost") as allocate:
            read_usage.return_value = {
                "degraded": False, "reason": None, "role_usage": measured_role_usage, "model_usage": [],
            }
            allocate.return_value = {
                "role_usage": priced_role_usage, "model_usage": [],
                "cost_usd": 2.5, "cost_basis": "measured", "cost_scope": "session_total",
                "excluded_cost_usd": 7.5, "excluded_token_share": 0.75,
                "api_duration_ms": None, "api_duration_basis": "unavailable",
                "api_duration_scope": "duration_unavailable_on_cursor",
            }
            lib.finalize_run(self.tdir, "code", "SHOP-1", {"status": "completed"})

        totals = lib.compute_ticket_totals(self.tdir)
        self.assertEqual(totals["cost_usd"], 2.5)
        self.assertEqual(totals["runs_cost_measured"], 1)

    def test_no_checkout_id_branch_keeps_model_usage_tokens_only(self):
        """design.md:718 -- the no-checkout_id branch persists model_usage
        tokens-only (no cost keys), mirroring role_usage's own behavior at
        this branch (acs_lib.py:1368): measured token data is never
        discarded just because cost can't be located."""
        lib.append_in_progress_run(self.tdir, "code", "SHOP-1", session={
            "session_id": "sess-1", "transcript_path": "/fake/sess-1.jsonl",
        })
        measured_model_usage = [
            {"model": "claude-opus", "input": 5, "output": 5, "cache_creation": 0, "cache_read": 0},
        ]
        with mock.patch("usage_reader.read_transcript_usage") as read_usage, \
                mock.patch("cost_sampler.allocate_cost") as allocate:
            read_usage.return_value = {
                "degraded": False, "reason": None, "role_usage": [], "model_usage": measured_model_usage,
            }
            state, entry = lib.finalize_run(self.tdir, "code", "SHOP-1", {"status": "completed"})
        allocate.assert_not_called()
        self.assertEqual(entry["model_usage"], measured_model_usage)
        for item in entry["model_usage"]:
            self.assertNotIn("cost_usd", item)
            self.assertNotIn("cost_basis", item)

    def test_no_session_marker_and_degraded_branches_emit_empty_model_usage(self):
        """No session_id/transcript_path, and a degraded transcript read,
        both persist model_usage=[] -- same rule as role_usage's own
        empty-list branches (acs_lib.py:1342-1347, :1352-1360)."""
        lib.append_in_progress_run(self.tdir, "code", "SHOP-1")
        with mock.patch("usage_reader.read_transcript_usage") as read_usage:
            state, entry = lib.finalize_run(self.tdir, "code", "SHOP-1", {"status": "completed"})
        read_usage.assert_not_called()
        self.assertEqual(entry["model_usage"], [])

        lib.append_in_progress_run(self.tdir, "code", "SHOP-1", session={
            "session_id": "sess-2", "transcript_path": "/fake/sess-2.jsonl", "checkout_id": "ck-2",
        })
        with mock.patch("usage_reader.read_transcript_usage") as read_usage:
            read_usage.return_value = {
                "degraded": True, "reason": "unreadable_transcript", "role_usage": [], "model_usage": [],
            }
            state, entry = lib.finalize_run(self.tdir, "code", "SHOP-1", {"status": "completed"})
        self.assertEqual(entry["model_usage"], [])

    def test_model_usage_is_a_sibling_of_tokens_never_inside_it(self):
        """F10 guard at the persistence layer: model_usage must be a
        top-level key on the run entry, never nested inside entry['tokens']
        (skill-state.schema.json's tokens object is additionalProperties:
        false and must stay that way)."""
        lib.append_in_progress_run(self.tdir, "code", "SHOP-1", session={
            "session_id": "sess-1", "transcript_path": "/fake/sess-1.jsonl", "checkout_id": "ck-1",
        })
        measured_model_usage = [
            {"model": "claude-opus", "input": 1, "output": 1, "cache_creation": 0, "cache_read": 0},
        ]
        with mock.patch("usage_reader.read_transcript_usage") as read_usage, \
                mock.patch("cost_sampler.allocate_cost") as allocate:
            read_usage.return_value = {
                "degraded": False, "reason": None, "role_usage": [], "model_usage": measured_model_usage,
            }
            allocate.return_value = {
                "role_usage": [], "model_usage": measured_model_usage,
                "cost_usd": None, "cost_basis": "unavailable", "cost_scope": "session_total",
                "excluded_cost_usd": 0.0, "excluded_token_share": 0.0,
                "api_duration_ms": None, "api_duration_basis": "unavailable",
                "api_duration_scope": "duration_unavailable_on_cursor",
            }
            state, entry = lib.finalize_run(self.tdir, "code", "SHOP-1", {"status": "completed"})
        self.assertIn("model_usage", entry)
        self.assertNotIn("model_usage", entry["tokens"])
        self.assertEqual(set(entry["tokens"]), {"input", "output", "cache_creation", "cache_read"})

    def test_finalize_run_persists_api_duration_fields_on_checkout_success(self):
        """AC-2: the checkout_id success branch unpacks
        api_duration_ms/api_duration_basis/api_duration_scope from
        allocate_cost's return dict onto entry, as siblings of
        cost_usd/cost_basis/cost_scope (never inside entry['tokens'] -- F10)."""
        lib.append_in_progress_run(self.tdir, "code", "SHOP-1", session={
            "session_id": "sess-1", "transcript_path": "/fake/sess-1.jsonl", "checkout_id": "ck-1",
        })
        measured_role_usage = [
            {"role": "executor", "input": 10, "output": 20, "cache_creation": 0, "cache_read": 0},
        ]
        priced_role_usage = [
            {"role": "executor", "input": 10, "output": 20, "cache_creation": 0, "cache_read": 0,
             "cost_usd": 0.05, "cost_basis": "apportioned",
             "api_duration_ms": 500.0, "api_duration_basis": "apportioned"},
        ]
        with mock.patch("usage_reader.read_transcript_usage") as read_usage, \
                mock.patch("cost_sampler.allocate_cost") as allocate:
            read_usage.return_value = {
                "degraded": False, "reason": None, "role_usage": measured_role_usage, "model_usage": [],
            }
            allocate.return_value = {
                "role_usage": priced_role_usage, "model_usage": [],
                "cost_usd": 0.05, "cost_basis": "measured", "cost_scope": "session_total",
                "excluded_cost_usd": 0.0, "excluded_token_share": 0.0,
                "api_duration_ms": 500.0, "api_duration_basis": "measured",
                "api_duration_scope": "session_total",
            }
            state, entry = lib.finalize_run(self.tdir, "code", "SHOP-1", {"status": "completed"})
        self.assertEqual(entry["api_duration_ms"], 500.0)
        self.assertEqual(entry["api_duration_basis"], "measured")
        self.assertEqual(entry["api_duration_scope"], "session_total")
        self.assertNotIn("api_duration_ms", entry["tokens"])
        self.assertNotIn("api_duration_basis", entry["tokens"])
        self.assertNotIn("api_duration_scope", entry["tokens"])

    def test_no_checkout_id_branch_sets_duration_unavailable_tokens_still_measured(self):
        """The no-checkout_id branch sets api_duration_ms=None,
        api_duration_basis="unavailable" -- tokens/model_usage are still
        measured; duration needs the checkout-scoped cursor it has no id to
        locate, exact parity with cost_usd's own rule there."""
        lib.append_in_progress_run(self.tdir, "code", "SHOP-1", session={
            "session_id": "sess-1", "transcript_path": "/fake/sess-1.jsonl",
        })
        measured_role_usage = [
            {"role": "executor", "input": 5, "output": 5, "cache_creation": 0, "cache_read": 0},
        ]
        with mock.patch("usage_reader.read_transcript_usage") as read_usage, \
                mock.patch("cost_sampler.allocate_cost") as allocate:
            read_usage.return_value = {
                "degraded": False, "reason": None, "role_usage": measured_role_usage, "model_usage": [],
            }
            state, entry = lib.finalize_run(self.tdir, "code", "SHOP-1", {"status": "completed"})
        allocate.assert_not_called()
        self.assertIsNone(entry["api_duration_ms"])
        self.assertEqual(entry["api_duration_basis"], "unavailable")
        self.assertNotIn("api_duration_scope", entry)
        self.assertEqual(entry["tokens"], {"input": 5, "output": 5, "cache_creation": 0, "cache_read": 0})

    def test_no_session_marker_and_degraded_branches_set_duration_unavailable_no_scope_key(self):
        """The no-session-marker branch and the degraded-transcript branch
        both set entry["api_duration_ms"]=None,
        entry["api_duration_basis"]="unavailable" -- no api_duration_scope
        key in either, mirroring how those branches set cost_usd/cost_basis
        but never cost_scope."""
        lib.append_in_progress_run(self.tdir, "code", "SHOP-1")
        with mock.patch("usage_reader.read_transcript_usage") as read_usage:
            state, entry = lib.finalize_run(self.tdir, "code", "SHOP-1", {"status": "completed"})
        read_usage.assert_not_called()
        self.assertIsNone(entry["api_duration_ms"])
        self.assertEqual(entry["api_duration_basis"], "unavailable")
        self.assertNotIn("api_duration_scope", entry)

        lib.append_in_progress_run(self.tdir, "code", "SHOP-1", session={
            "session_id": "sess-2", "transcript_path": "/fake/sess-2.jsonl", "checkout_id": "ck-2",
        })
        with mock.patch("usage_reader.read_transcript_usage") as read_usage:
            read_usage.return_value = {
                "degraded": True, "reason": "unreadable_transcript", "role_usage": [], "model_usage": [],
            }
            state, entry = lib.finalize_run(self.tdir, "code", "SHOP-1", {"status": "completed"})
        self.assertIsNone(entry["api_duration_ms"])
        self.assertEqual(entry["api_duration_basis"], "unavailable")
        self.assertNotIn("api_duration_scope", entry)

    def test_sum_role_tokens_unchanged_by_model_usage(self):
        """Inverse obligation: entry['tokens'] still equals the role-sum
        result (acs_lib._sum_role_tokens) on a mixed-model fixture --
        model_usage introduces no new total."""
        lib.append_in_progress_run(self.tdir, "code", "SHOP-1", session={
            "session_id": "sess-1", "transcript_path": "/fake/sess-1.jsonl", "checkout_id": "ck-1",
        })
        measured_role_usage = [
            {"role": "executor", "input": 10, "output": 5, "cache_creation": 0, "cache_read": 0},
        ]
        measured_model_usage = [
            {"model": "claude-opus", "input": 6, "output": 3, "cache_creation": 0, "cache_read": 0},
            {"model": "claude-sonnet", "input": 4, "output": 2, "cache_creation": 0, "cache_read": 0},
        ]
        with mock.patch("usage_reader.read_transcript_usage") as read_usage, \
                mock.patch("cost_sampler.allocate_cost") as allocate:
            read_usage.return_value = {
                "degraded": False, "reason": None, "role_usage": measured_role_usage,
                "model_usage": measured_model_usage,
            }
            allocate.return_value = {
                "role_usage": measured_role_usage, "model_usage": measured_model_usage,
                "cost_usd": None, "cost_basis": "unavailable", "cost_scope": "session_total",
                "excluded_cost_usd": 0.0, "excluded_token_share": 0.0,
                "api_duration_ms": None, "api_duration_basis": "unavailable",
                "api_duration_scope": "duration_unavailable_on_cursor",
            }
            state, entry = lib.finalize_run(self.tdir, "code", "SHOP-1", {"status": "completed"})
        self.assertEqual(entry["tokens"], lib._sum_role_tokens(measured_role_usage))
        self.assertEqual(entry["tokens"], {"input": 10, "output": 5, "cache_creation": 0, "cache_read": 0})


class TestRecordEscalationEventRequiresRun(unittest.TestCase):
    """1115: raises ValueError when no run entry exists to attach the event to."""

    def test_raises_without_existing_run_entry(self):
        tdir = tempfile.mkdtemp(prefix="acs-test-")
        self.addCleanup(shutil.rmtree, tdir, True)
        with self.assertRaises(ValueError):
            lib.record_escalation_event(tdir, "code", {"trigger": "x"})


class TestComputeTicketTotals(unittest.TestCase):
    """1225: skips a non-dict entry inside a state file's runs list."""

    def test_skips_non_dict_run_entries(self):
        tdir = tempfile.mkdtemp(prefix="acs-test-")
        self.addCleanup(shutil.rmtree, tdir, True)
        lib.write_json(lib.state_path(tdir, "code"), {"runs": [
            None,
            "oops",
            {"status": "completed", "started_at": "2026-01-01T00:00:00Z",
             "ended_at": "2026-01-01T00:05:00Z",
             "tokens": {"input": 1, "output": 2}, "cost_usd": 0.5},
        ]})
        totals = lib.compute_ticket_totals(tdir)
        self.assertEqual(totals["runs"], 1)
        self.assertEqual(totals["tokens"], {"input": 1, "output": 2, "cache_creation": 0, "cache_read": 0})

    def test_none_elapsed_run_excluded_from_working_seconds_not_zeroed(self):
        """AC-1: a completed run plus an in-progress (no ended_at) run yields
        runs==2, runs_timed==1, runs_untimed==1, and working_seconds equal to
        the completed run's seconds alone — excluded, not counted as zero."""
        tdir = tempfile.mkdtemp(prefix="acs-test-")
        self.addCleanup(shutil.rmtree, tdir, True)
        lib.write_json(lib.state_path(tdir, "code"), {"runs": [
            {"status": "completed", "started_at": "2026-01-01T00:00:00Z",
             "ended_at": "2026-01-01T00:05:00Z",
             "tokens": {"input": 1, "output": 2}, "cost_usd": 0.5},
            {"status": "in_progress", "started_at": "2026-01-01T01:00:00Z"},
        ]})
        totals = lib.compute_ticket_totals(tdir)
        self.assertEqual(totals["runs"], 2)
        self.assertEqual(totals["runs_timed"], 1)
        self.assertEqual(totals["runs_untimed"], 1)
        self.assertEqual(totals["working_seconds"], 300)

    def test_legacy_run_with_absent_cost_basis_excluded_from_cost_totals(self):
        """C-11: a pre-cutover run entry with no cost_basis field at all is
        treated the same as cost_basis="unavailable" -- excluded from the
        cost_usd sum and counted in runs_cost_unavailable, never
        runs_cost_measured."""
        tdir = tempfile.mkdtemp(prefix="acs-test-")
        self.addCleanup(shutil.rmtree, tdir, True)
        lib.write_json(lib.state_path(tdir, "code"), {"runs": [
            {"status": "completed", "started_at": "2026-01-01T00:00:00Z",
             "ended_at": "2026-01-01T00:05:00Z",
             "tokens": {"input": 1, "output": 2}, "cost_usd": 0.5},
            {"status": "completed", "started_at": "2026-01-01T01:00:00Z",
             "ended_at": "2026-01-01T01:05:00Z",
             "tokens": {"input": 3, "output": 4}, "cost_usd": 0.75, "cost_basis": "measured"},
        ]})
        totals = lib.compute_ticket_totals(tdir)
        self.assertEqual(totals["runs_cost_unavailable"], 1)
        self.assertEqual(totals["runs_cost_measured"], 1)
        self.assertEqual(totals["cost_usd"], 0.75)

    def test_cache_tokens_summed_into_ticket_totals_not_dropped(self):
        """FIX 3: cache_creation/cache_read are the dominant token volume --
        compute_ticket_totals must accumulate all four token fields from each
        run entry's tokens dict, not silently drop the cache pair."""
        tdir = tempfile.mkdtemp(prefix="acs-test-")
        self.addCleanup(shutil.rmtree, tdir, True)
        lib.write_json(lib.state_path(tdir, "code"), {"runs": [
            {"status": "completed", "started_at": "2026-01-01T00:00:00Z",
             "ended_at": "2026-01-01T00:05:00Z",
             "tokens": {"input": 10, "output": 20, "cache_creation": 1000, "cache_read": 2000},
             "cost_usd": 0.5, "cost_basis": "measured"},
            {"status": "completed", "started_at": "2026-01-01T01:00:00Z",
             "ended_at": "2026-01-01T01:05:00Z",
             "tokens": {"input": 5, "output": 7, "cache_creation": 300, "cache_read": 400},
             "cost_usd": 0.25, "cost_basis": "measured"},
        ]})
        totals = lib.compute_ticket_totals(tdir)
        self.assertEqual(totals["tokens"], {"input": 15, "output": 27, "cache_creation": 1300, "cache_read": 2400})

    def test_compute_ticket_totals_counts_api_duration_measured_vs_unavailable(self):
        """AC-2: mirrors the cost_basis/cost_usd pattern verbatim for
        api_duration_basis/api_duration_ms -- "measured"/"apportioned" with a
        numeric api_duration_ms increments runs_api_duration_measured and
        sums into totals["api_duration_ms"]; every other run increments
        runs_api_duration_unavailable."""
        tdir = tempfile.mkdtemp(prefix="acs-test-")
        self.addCleanup(shutil.rmtree, tdir, True)
        lib.write_json(lib.state_path(tdir, "code"), {"runs": [
            {"status": "completed", "started_at": "2026-01-01T00:00:00Z",
             "ended_at": "2026-01-01T00:05:00Z",
             "tokens": {"input": 1, "output": 2}, "cost_usd": 0.5, "cost_basis": "measured",
             "api_duration_ms": 1500.0, "api_duration_basis": "measured"},
            {"status": "completed", "started_at": "2026-01-01T01:00:00Z",
             "ended_at": "2026-01-01T01:05:00Z",
             "tokens": {"input": 3, "output": 4}, "cost_usd": 0.75, "cost_basis": "apportioned",
             "api_duration_ms": 500.0, "api_duration_basis": "apportioned"},
            {"status": "completed", "started_at": "2026-01-01T02:00:00Z",
             "ended_at": "2026-01-01T02:05:00Z",
             "tokens": {"input": 1, "output": 1}, "cost_usd": None, "cost_basis": "unavailable",
             "api_duration_ms": None, "api_duration_basis": "unavailable"},
        ]})
        totals = lib.compute_ticket_totals(tdir)
        self.assertEqual(totals["runs_api_duration_measured"], 2)
        self.assertEqual(totals["runs_api_duration_unavailable"], 1)
        self.assertEqual(totals["api_duration_ms"], 2000.0)

    def test_compute_ticket_totals_legacy_entry_without_api_duration_basis_counts_unavailable(self):
        """A pre-cutover run entry with no api_duration_basis field at all is
        treated the same as api_duration_basis="unavailable" -- excluded from
        the api_duration_ms sum, counted in runs_api_duration_unavailable."""
        tdir = tempfile.mkdtemp(prefix="acs-test-")
        self.addCleanup(shutil.rmtree, tdir, True)
        lib.write_json(lib.state_path(tdir, "code"), {"runs": [
            {"status": "completed", "started_at": "2026-01-01T00:00:00Z",
             "ended_at": "2026-01-01T00:05:00Z",
             "tokens": {"input": 1, "output": 2}, "cost_usd": 0.5},
        ]})
        totals = lib.compute_ticket_totals(tdir)
        self.assertEqual(totals["runs_api_duration_unavailable"], 1)
        self.assertEqual(totals["runs_api_duration_measured"], 0)
        self.assertEqual(totals["api_duration_ms"], 0.0)


class TestUpdateMetricsCostBasisExclusion(unittest.TestCase):
    """C-11: update_metrics excludes a run entry with absent (legacy) or
    "unavailable" cost_basis from the repo-level cost_usd sum, counting it
    in runs_cost_unavailable rather than runs_cost_measured."""

    def test_absent_cost_basis_excluded_present_measured_included(self):
        workspace = tempfile.mkdtemp(prefix="acs-test-")
        self.addCleanup(shutil.rmtree, workspace, True)
        lib.update_metrics(workspace, "acme-shop", run_entry={
            "started_at": "2026-01-01T00:00:00Z", "ended_at": "2026-01-01T00:05:00Z",
            "tokens": {"input": 1, "output": 2}, "cost_usd": 0.5,
        })
        data = lib.update_metrics(workspace, "acme-shop", run_entry={
            "started_at": "2026-01-01T01:00:00Z", "ended_at": "2026-01-01T01:05:00Z",
            "tokens": {"input": 3, "output": 4}, "cost_usd": 0.75, "cost_basis": "measured",
        })
        self.assertEqual(data["totals"]["runs_cost_unavailable"], 1)
        self.assertEqual(data["totals"]["runs_cost_measured"], 1)
        self.assertEqual(data["totals"]["cost_usd"], 0.75)

    def test_cache_tokens_summed_into_repo_totals_not_dropped(self):
        """FIX 3: repo-level totals must accumulate cache_creation/cache_read
        from each run entry, same as the ticket-level rollup."""
        workspace = tempfile.mkdtemp(prefix="acs-test-")
        self.addCleanup(shutil.rmtree, workspace, True)
        lib.update_metrics(workspace, "acme-shop", run_entry={
            "started_at": "2026-01-01T00:00:00Z", "ended_at": "2026-01-01T00:05:00Z",
            "tokens": {"input": 1, "output": 2, "cache_creation": 100, "cache_read": 200},
            "cost_usd": 0.5, "cost_basis": "measured",
        })
        data = lib.update_metrics(workspace, "acme-shop", run_entry={
            "started_at": "2026-01-01T01:00:00Z", "ended_at": "2026-01-01T01:05:00Z",
            "tokens": {"input": 3, "output": 4, "cache_creation": 50, "cache_read": 75},
            "cost_usd": 0.75, "cost_basis": "measured",
        })
        self.assertEqual(data["totals"]["tokens"],
                          {"input": 4, "output": 6, "cache_creation": 150, "cache_read": 275})

    def test_update_metrics_backfills_api_duration_counters_at_zero(self):
        """A pre-existing metrics.json (written before this ticket) predates
        the api_duration counters; update_metrics backfills them at 0 rather
        than raising or silently omitting them, then accumulates a new run's
        api_duration_ms/basis into the roll-up on the next call."""
        workspace = tempfile.mkdtemp(prefix="acs-test-")
        self.addCleanup(shutil.rmtree, workspace, True)
        lib.write_json(lib.metrics_path(workspace, "acme-shop"), {
            "tickets": {}, "prs": {"created": 0, "merged": 0, "created_pr_numbers": []},
            "totals": {
                "runs": 1, "working_seconds": 300,
                "tokens": {"input": 1, "output": 2, "cache_creation": 0, "cache_read": 0},
                "cost_usd": 0.5, "runs_timed": 1, "runs_untimed": 0,
                "runs_cost_measured": 1, "runs_cost_unavailable": 0,
            },
        })
        data = lib.update_metrics(workspace, "acme-shop", run_entry={
            "started_at": "2026-01-01T01:00:00Z", "ended_at": "2026-01-01T01:05:00Z",
            "tokens": {"input": 3, "output": 4}, "cost_usd": 0.75, "cost_basis": "measured",
            "api_duration_ms": 250.0, "api_duration_basis": "measured",
        })
        self.assertEqual(data["totals"]["runs_api_duration_measured"], 1)
        self.assertEqual(data["totals"]["runs_api_duration_unavailable"], 0)
        self.assertEqual(data["totals"]["api_duration_ms"], 250.0)


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

        # acs_lib is a package (MAR-522): acs_lib.state bound this name at import
        # time, so patching the facade would leave the real one in place and
        # this branch would go uncovered while the test still passed.
        with mock.patch.object(lib.state, "write_json", side_effect=shim):
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
