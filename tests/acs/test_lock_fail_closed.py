"""MAR-530: the repo-level write guards and the ticket lock fail CLOSED.

Two mechanisms, one principle — a guard that gives up silently is worse than
no guard, because it makes the loss invisible:

  * `repo_guard` (and through it `_guarded_repo_write` and
    `allocate_ticket_id`) used to spin for ten seconds and then run the
    read-modify-write anyway. Exhaustion now raises `GuardTimeout` and writes
    nothing. `tests/acs/test_index_metrics_concurrency_guard.py` covers the two
    repo-level writers; this module covers the id allocator, whose fail-open
    arm could hand two sessions the SAME ticket id.
  * The ticket `.lock` has no cross-host liveness signal at all — a pid from
    another container is meaningless here. `lock_staleness` now says which
    regime a verdict came from, and `force_release_lock` is the explicit,
    audited way to break a lock instead of "delete the file and hope someone
    remembers who did it".
"""

import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRIPTS = os.path.join(REPO_ROOT, "plugins", "acs", "hooks", "scripts")
sys.path.insert(0, SCRIPTS)

import acs_lib as lib  # noqa: E402

sys.path.insert(0, os.path.join(REPO_ROOT, "tests", "acs"))
from acs_case import AcsWorkspaceCase  # noqa: E402


def _hours_ago(n):
    return (datetime.now(timezone.utc) - timedelta(hours=n)).strftime("%Y-%m-%dT%H:%M:%SZ")


class RepoGuardExhaustionTest(unittest.TestCase):
    """The shared guard: what happens at the end of the budget."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="acs-test-")
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def test_raises_without_running_the_body(self):
        open(os.path.join(self.tmp, "g.lock"), "w").close()  # fresh -> never stale
        ran = []
        with mock.patch("time.sleep"):
            with self.assertRaises(lib.GuardTimeout):
                with lib.repo_guard(self.tmp, "g.lock"):
                    ran.append(True)
        self.assertEqual(ran, [], "the body must not run without the guard")

    def test_the_message_names_the_guard_the_budget_and_the_refusal(self):
        open(os.path.join(self.tmp, "g.lock"), "w").close()
        with mock.patch("time.sleep"):
            with self.assertRaises(lib.GuardTimeout) as caught:
                with lib.repo_guard(self.tmp, "g.lock", attempts=4, interval=0.25):
                    pass
        message = str(caught.exception)
        self.assertIn("g.lock", message)
        self.assertIn("1.0s", message)          # attempts * interval, not the default
        self.assertIn("REFUSED", message)

    def test_budget_is_bounded_by_attempts_not_wall_clock(self):
        """The spin is exactly `attempts` iterations — a test that mocks sleep
        must terminate, and a caller reading the constants gets the real
        budget."""
        open(os.path.join(self.tmp, "g.lock"), "w").close()
        with mock.patch("time.sleep") as slept:
            with self.assertRaises(lib.GuardTimeout):
                with lib.repo_guard(self.tmp, "g.lock", attempts=7, interval=0.05):
                    pass
        self.assertEqual(slept.call_count, 7)
        self.assertEqual(lib.GUARD_ATTEMPTS * lib.GUARD_INTERVAL, 10.0)


    def test_releases_its_own_guard_on_the_way_out(self):
        with lib.repo_guard(self.tmp, "g.lock") as guard:
            self.assertTrue(os.path.exists(guard))
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "g.lock")))

    def test_releases_its_own_guard_when_the_body_raises(self):
        with self.assertRaises(ZeroDivisionError):
            with lib.repo_guard(self.tmp, "g.lock"):
                1 / 0
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "g.lock")))

    def test_guard_timeout_is_a_gate_error_so_the_pre_hook_reports_it(self):
        """run_pre already turns a GateError into `blocked — <reason>` + exit 2.
        Inheriting from it is what keeps a guard timeout out of a traceback."""
        self.assertTrue(issubclass(lib.GuardTimeout, lib.GateError))


class GuardAttemptsOverrideTest(unittest.TestCase):
    """The budget is operable: refusing after 10s is a real failure mode, so a
    slow shared workspace can raise it and a test can collapse it."""

    def test_default_when_unset_or_unusable(self):
        for value in ({}, {"ACS_GUARD_ATTEMPTS": ""}, {"ACS_GUARD_ATTEMPTS": "many"},
                      {"ACS_GUARD_ATTEMPTS": "0"}, {"ACS_GUARD_ATTEMPTS": "-3"}):
            with mock.patch.dict(os.environ, value, clear=True):
                self.assertEqual(lib.guard_attempts(), lib.GUARD_ATTEMPTS)

    def test_positive_override_is_honoured(self):
        with mock.patch.dict(os.environ, {"ACS_GUARD_ATTEMPTS": "3"}):
            self.assertEqual(lib.guard_attempts(), 3)

    def test_repo_guard_reads_it_per_call(self):
        tmp = tempfile.mkdtemp(prefix="acs-test-")
        self.addCleanup(shutil.rmtree, tmp, True)
        open(os.path.join(tmp, "g.lock"), "w").close()
        with mock.patch.dict(os.environ, {"ACS_GUARD_ATTEMPTS": "2"}):
            with mock.patch("time.sleep") as slept:
                with self.assertRaises(lib.GuardTimeout):
                    with lib.repo_guard(tmp, "g.lock"):
                        pass
        self.assertEqual(slept.call_count, 2)


class StaleGuardReclaimTest(unittest.TestCase):
    """The reclaim arm, which used to fail OPEN while the docs said otherwise.

    Removing a guard whose mtime is old and proceeding puts a SECOND writer
    inside a body the first is still running, and the first one's `finally`
    then unlinks the second one's guard. Both halves are covered here."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="acs-test-")
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def _age(self, path, seconds):
        old = datetime.now(timezone.utc).timestamp() - seconds
        os.utime(path, (old, old))

    def test_a_live_holder_on_this_host_is_never_reclaimed(self):
        """An age threshold alone cannot tell a crashed writer from a slow one.
        A guard recording a pid that is still running here is a slow one."""
        guard = os.path.join(self.tmp, "g.lock")
        with open(guard, "w", encoding="utf-8") as fh:
            json.dump({"pid": os.getpid(), "host": socket.gethostname()}, fh)
        self._age(guard, 3600)
        with mock.patch("time.sleep"):
            with self.assertRaises(lib.GuardTimeout):
                with lib.repo_guard(self.tmp, "g.lock", attempts=3, interval=0.01):
                    self.fail("a live holder's guard must not be stolen")
        self.assertTrue(os.path.exists(guard), "and it must still be there")

    def test_a_guard_left_by_a_dead_writer_is_reclaimed(self):
        """The case the reclaim exists for: the holder is gone, so waiting for
        it is waiting forever."""
        guard = os.path.join(self.tmp, "g.lock")
        with open(guard, "w", encoding="utf-8") as fh:
            json.dump({"pid": _dead_pid(), "host": socket.gethostname()}, fh)
        self._age(guard, 3600)
        with lib.repo_guard(self.tmp, "g.lock", attempts=3, interval=0.01):
            pass
        self.assertFalse(os.path.exists(guard))

    def test_a_guard_from_another_host_is_reclaimed_on_age_alone(self):
        """A pid from another container means nothing here, so the age
        threshold is all there is -- which is why it now derives from the
        budget rather than sitting at a fixed 30s."""
        guard = os.path.join(self.tmp, "g.lock")
        with open(guard, "w", encoding="utf-8") as fh:
            json.dump({"pid": 1, "host": "some-other-container"}, fh)
        self._age(guard, 3600)
        with lib.repo_guard(self.tmp, "g.lock", attempts=3, interval=0.01):
            pass
        self.assertFalse(os.path.exists(guard))

    def test_the_stale_threshold_moves_with_the_configured_budget(self):
        """`$ACS_GUARD_ATTEMPTS` is documented as the remedy for slow shared
        storage. With a fixed 30s threshold, raising it made things WORSE: a
        100-second budget meant every waiter outlived the threshold and stole
        the guard from a live writer, restoring the lost update this ticket
        exists to close."""
        self.assertEqual(lib.guard_stale_seconds(200, 0.05), lib.GUARD_STALE_SECONDS)
        self.assertEqual(lib.guard_stale_seconds(2000, 0.05), 200.0,
                         "twice the budget: no reclaim while a peer could still "
                         "legitimately be holding on")
        self.assertGreater(lib.guard_stale_seconds(2000, 0.05),
                           2000 * 0.05, "and strictly past the budget itself")

    def test_a_holder_whose_guard_was_reclaimed_does_not_unlink_the_new_one(self):
        """The other half of the double-entry: the displaced holder's `finally`
        used to strip the guard off whoever reclaimed it."""
        guard = os.path.join(self.tmp, "g.lock")
        with lib.repo_guard(self.tmp, "g.lock"):
            os.unlink(guard)                       # a waiter reclaims it...
            with open(guard, "w", encoding="utf-8") as fh:
                json.dump({"pid": os.getpid() + 1, "host": "elsewhere"}, fh)
        self.assertTrue(os.path.exists(guard),
                        "the new holder's guard must survive our release")

    def test_the_refusal_no_longer_tells_the_operator_to_delete_a_guard(self):
        """Advice that invites deleting a LIVE writer's guard, for a file that
        is reclaimed automatically."""
        open(os.path.join(self.tmp, "g.lock"), "w").close()
        with mock.patch("time.sleep"):
            with self.assertRaises(lib.GuardTimeout) as caught:
                with lib.repo_guard(self.tmp, "g.lock", attempts=2, interval=0.01):
                    pass
        self.assertNotIn("delete the guard file", str(caught.exception))
        self.assertIn("reclaimed automatically", str(caught.exception))


class GuardAttemptsCeilingTest(unittest.TestCase):
    """The budget is operable, not unbounded."""

    def test_an_absurd_override_is_clamped_rather_than_honoured(self):
        """Only the lower bound was checked, so `ACS_GUARD_ATTEMPTS=20000`
        bought a 17-minute spin inside a hook Claude Code kills at 25s."""
        with mock.patch.dict(os.environ, {"ACS_GUARD_ATTEMPTS": "20000"}):
            self.assertEqual(lib.guard_attempts(), lib.GUARD_ATTEMPTS_MAX)
        self.assertGreater(lib.GUARD_ATTEMPTS_MAX, lib.GUARD_ATTEMPTS,
                           "the ceiling must leave the documented remedy usable")


class LockLedgerHasASchemaTest(unittest.TestCase):
    """An append-only AUDIT artifact is the one whose shape most needs a
    contract: its readers are future tooling and auditors, not this code."""

    SCHEMAS = os.path.join(REPO_ROOT, "plugins", "acs", "schemas")

    def _schema(self):
        with open(os.path.join(self.SCHEMAS, "lock-events.schema.json"),
                  encoding="utf-8") as fh:
            return json.load(fh)

    def test_the_ledger_ships_with_a_schema_like_every_other_artifact(self):
        schema = self._schema()
        self.assertEqual(schema["required"], ["event", "at", "reason"])
        self.assertEqual(schema["properties"]["event"]["enum"],
                         ["lock_force_released", "lock_force_release_failed"],
                         "the two kinds carry different keys, so `event` is the "
                         "declared discriminator")

    def test_a_real_break_validates_against_it(self):
        """Written from the artifact the code actually produces, so the schema
        cannot drift from it silently."""
        tmp = tempfile.mkdtemp(prefix="acs-test-")
        self.addCleanup(shutil.rmtree, tmp, True)
        lib.write_json(lib.lock_path(tmp), {"checkout_id": "other", "pid": 4242,
                                            "hostname": "elsewhere",
                                            "created_at": _hours_ago(1)})
        out = lib.force_release_lock(tmp, os.getcwd(), "container died", actor="dana")
        with open(out["audit_path"], encoding="utf-8") as fh:
            entry = json.loads(fh.readline())
        schema = self._schema()
        for key in schema["required"]:
            self.assertIn(key, entry)
        released = schema["allOf"][0]["then"]["required"]
        for key in released:
            self.assertIn(key, entry, "declared required for lock_force_released")
        self.assertTrue(set(entry) <= set(schema["properties"]),
                        "every key the writer emits must be declared: %s"
                        % sorted(set(entry) - set(schema["properties"])))


def _dead_pid():
    """A pid that is certainly not running: fork a child and reap it."""
    pid = os.fork()
    if pid == 0:
        os._exit(0)
    os.waitpid(pid, 0)
    return pid


class AllocateTicketIdFailsClosedTest(AcsWorkspaceCase):
    """The allocator is the sharpest case: fail-open here mints a DUPLICATE id."""

    def test_refuses_rather_than_minting_from_an_unguarded_read(self):
        rdir = lib.repo_dir(self.ws, "acme-shop")
        guard = os.path.join(rdir, "counters.json.lock")
        open(guard, "w").close()  # fresh mtime -> never stale, held for the call

        with mock.patch("time.sleep"):
            with self.assertRaises(lib.GuardTimeout):
                lib.allocate_ticket_id(self.ws, "acme-shop", "SHOP")

        counters = lib.read_json(os.path.join(rdir, "counters.json"))
        self.assertEqual(counters["next"], 1, "a refused allocation must not advance the counter")
        self.assertTrue(os.path.exists(guard), "the refusal must not steal the foreign guard")

    def test_new_ticket_cli_reports_the_refusal_instead_of_a_duplicate_id(self):
        """Out of process, so the refusal is proven where a coordinator meets
        it. $ACS_GUARD_ATTEMPTS collapses the 10s budget to one attempt --
        the arm under test is exhaustion, not how long exhaustion takes.

        The assertions are on the SHAPE of the refusal, not merely on its
        failure: `assertNotEqual(returncode, 0)` plus "the guard name appears
        in stderr" is satisfied by an unhandled traceback, which is exactly the
        behaviour this test exists to prevent -- so it could not have failed on
        its own defect."""
        rdir = lib.repo_dir(self.ws, "acme-shop")
        open(os.path.join(rdir, "counters.json.lock"), "w").close()
        out = self.run_script("new-ticket.py", "--title", "T", "--type", "task",
                              env=dict(os.environ, ACS_GUARD_ATTEMPTS="1"))
        self.assertEqual(out.returncode, 2, out.stderr)
        self.assertIn("acs new-ticket:", out.stderr)
        self.assertNotIn("Traceback", out.stderr)
        self.assertIn("counters.json.lock", out.stderr)
        self.assertEqual(lib.read_json(os.path.join(rdir, "counters.json"))["next"], 1)


class GuardTimeoutIsNeverATracebackTest(AcsWorkspaceCase):
    """Every entry point that can hit a refused repo-level write reports it the
    way the CLI contract documents -- `acs <command>: <reason>` and exit 2 --
    and, where it holds the ticket lock, releases it on the way out.

    Guard exhaustion used to be exercised at four call sites out of ten, which
    is why a traceback and a stranded lock at the other six shipped green."""

    def _hold(self, name):
        """Hold a repo-level guard with a fresh mtime for the whole test."""
        rdir = lib.repo_dir(self.ws, "acme-shop")
        os.makedirs(rdir, exist_ok=True)
        path = os.path.join(rdir, name)
        open(path, "w").close()
        self.addCleanup(lambda: os.path.exists(path) and os.unlink(path))
        return path

    def _env(self):
        return dict(os.environ, ACS_GUARD_ATTEMPTS="1")

    def _assert_clean_refusal(self, out, command):
        self.assertEqual(out.returncode, 2, out.stderr)
        self.assertIn("acs %s:" % command, out.stderr)
        self.assertNotIn("Traceback", out.stderr)

    def test_skill_start_releases_the_lock_it_took_before_refusing(self):
        """The lock is acquired BEFORE the repo-level writes, so a refusal
        there left the ticket locked by a pid that immediately exits -- and a
        cross-host lock stranded that way is not even reported stale for 24h."""
        ticket = self.new_ticket("Audit", "task")
        tdir = self.tdir(ticket)
        self._hold("tickets-index.json.lock")
        out = self.run_script("skill-start.py", "--skill", "code", "--ticket", ticket,
                              env=self._env())
        self._assert_clean_refusal(out, "skill-start")
        self.assertFalse(os.path.exists(lib.lock_path(tdir)),
                         "a skill that did not start must not hold the lock")

    def test_skill_start_allocate_refuses_without_minting_an_id(self):
        self._hold("counters.json.lock")
        out = self.run_script("skill-start.py", "--skill", "create-ticket", "--allocate",
                              "--title", "T", env=self._env())
        self._assert_clean_refusal(out, "skill-start")
        rdir = lib.repo_dir(self.ws, "acme-shop")
        self.assertEqual(lib.read_json(os.path.join(rdir, "counters.json"))["next"], 1,
                         "a refused allocation must not advance the counter")

    def test_handoff_releases_the_lock_even_when_metrics_refuses(self):
        """Releasing the lock IS the handoff. A refused metrics write that
        finalizes the run `handed_off` and then keeps the lock leaves the
        ticket unresumable by anyone, which is the one unrecoverable outcome."""
        ticket = self.new_ticket("Audit", "task")
        self.start("code", ticket)
        tdir = self.tdir(ticket)
        self.assertTrue(os.path.exists(lib.lock_path(tdir)))
        self._hold("metrics.json.lock")
        out = self.run_script("handoff.py", "--summary", "stopping here",
                              env=self._env())
        self._assert_clean_refusal(out, "handoff")
        self.assertFalse(os.path.exists(lib.lock_path(tdir)),
                         "the lock must be released even when metrics is refused")
        self.assertEqual(lib.last_run_status(tdir, "code"), "handed_off")

    def test_session_end_releases_the_lock_even_when_metrics_refuses(self):
        """The SessionEnd net's whole job is the release, and dispatch.py
        swallows what it raises -- so a refusal here exited 0 with the lock
        held and nothing said."""
        ticket = self.new_ticket("Audit", "task")
        self.start("code", ticket)
        tdir = self.tdir(ticket)
        self._hold("metrics.json.lock")
        out = self.run_script("dispatch.py", "session-end",
                              stdin=json.dumps({"cwd": self.repo}),
                              env=self._env())
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertFalse(os.path.exists(lib.lock_path(tdir)),
                         "the safety net must release the lock it came to release")
        self.assertEqual(lib.last_run_status(tdir, "code"), "interrupted")

    def test_lane_apply_records_the_escalation_event_even_when_the_index_refuses(self):
        """The raise landed between the durable lane change and its audit
        event, so a refusal produced a lane raise with no event and no index
        row -- delivered as a traceback."""
        ticket = self.new_ticket("Audit", "task")
        self.start("code", ticket)
        tdir = self.tdir(ticket)
        self._hold("tickets-index.json.lock")
        out = self.run_script("acs.py", "lane", "apply", "--ticket", ticket,
                              "--skill", "code", "--proposed-size", "large",
                              "--trigger", "verifier", env=self._env())
        self._assert_clean_refusal(out, "lane apply")
        doc = lib.load_ticket(tdir)
        self.assertEqual((doc["size"], doc["lane"]), ("large", "COMPLEX"))
        events = (lib.last_run(lib.load_state(tdir, "code", ticket)) or {}).get("escalations")
        self.assertTrue(events, "the audit event has no other source; the index has one")


class PostHookReportsGuardTimeoutTest(AcsWorkspaceCase):
    """Fail-closed has to be legible where a coordinator meets it. The post hook
    reaches the repo-level writers AFTER the run and pipeline-state are already
    durable, so a refusal there is a partial-write situation and the message has
    to say which half landed."""

    def test_index_guard_timeout_exits_1_names_what_landed_and_frees_the_lock(self):
        ticket = self.new_ticket("Audit", "task")
        self.start("standardize-project", ticket)
        tdir = self.tdir(ticket)
        self.assertTrue(os.path.exists(lib.lock_path(tdir)))

        guard = os.path.join(lib.repo_dir(self.ws, "acme-shop"), "tickets-index.json.lock")
        open(guard, "w").close()  # fresh -> never stale, held for the whole call
        out = self.run_script(
            "post-standardize-project.py", "--ticket", ticket,
            stdin=json.dumps({"status": "completed",
                              "states": {"pr": {"number": 1, "url": "https://example.invalid/pull/1"}}}),
            env=dict(os.environ, ACS_GUARD_ATTEMPTS="1"))

        self.assertEqual(out.returncode, 1, out.stderr)
        self.assertIn("tickets-index.json.lock", out.stderr)
        self.assertIn("ARE written", out.stderr)
        self.assertIn("Do NOT re-run this hook", out.stderr)
        # The half that landed really did land...
        self.assertEqual(lib.last_run_status(tdir, "standardize-project"), "completed")
        self.assertEqual(lib.load_ticket(tdir)["status"], "in_review")
        # ...the repo-level half did not: the index still carries the pre-call
        # status, which is the divergence the message tells the operator about.
        index = lib.read_json(lib.index_path(self.ws, "acme-shop")) or {}
        self.assertEqual(index["tickets"][ticket]["status"], "in_progress")
        # ...and the ticket is not left locked by a session that has exited.
        self.assertFalse(os.path.exists(lib.lock_path(tdir)))
        self.assertTrue(os.path.exists(guard), "the refusal must not steal the foreign guard")

    def test_merge_pr_names_the_archive_among_the_writes_that_did_not_happen(self):
        """merge-pr's tail archives the partition through a second guarded
        index write, so its failure loses more than the index entry and the
        message has to say so."""
        ticket = self.new_ticket("Audit", "task")
        self.start("merge-pr", ticket)
        guard = os.path.join(lib.repo_dir(self.ws, "acme-shop"), "tickets-index.json.lock")
        open(guard, "w").close()
        out = self.run_script(
            "post-merge-pr.py", "--ticket", ticket,
            stdin=json.dumps({"status": "completed"}),
            env=dict(os.environ, ACS_GUARD_ATTEMPTS="1"))

        self.assertEqual(out.returncode, 1, out.stderr)
        self.assertIn("and the partition archive", out.stderr)
        self.assertTrue(os.path.isdir(self.tdir(ticket)), "the partition must not be archived")


class LockStalenessBasisTest(unittest.TestCase):
    """Every arm of the verdict, and what each one could actually observe."""

    def test_same_host_live_process_is_not_stale(self):
        lock = {"hostname": lib.socket.gethostname(), "pid": os.getpid(),
                "created_at": _hours_ago(100)}
        self.assertEqual(lib.lock_staleness(lock), (False, "holder-process-live"))

    def test_same_host_gone_process_is_stale_however_young(self):
        lock = {"hostname": lib.socket.gethostname(), "pid": 424242, "created_at": lib.now_iso()}
        with mock.patch("os.kill", side_effect=ProcessLookupError):
            self.assertEqual(lib.lock_staleness(lock), (True, "holder-process-gone"))

    def test_same_host_unprobeable_process_is_not_stale(self):
        lock = {"hostname": lib.socket.gethostname(), "pid": 424242, "created_at": lib.now_iso()}
        with mock.patch("os.kill", side_effect=PermissionError):
            self.assertEqual(lib.lock_staleness(lock), (False, "holder-process-unprobeable"))

    def test_foreign_host_never_probes_the_pid(self):
        """The cross-host limit, asserted rather than described: a foreign
        lock's pid names a process in another namespace, so probing it here
        would answer a question about an unrelated LOCAL process."""
        lock = {"hostname": "some-other-host", "pid": os.getpid(), "created_at": lib.now_iso()}
        with mock.patch("os.kill") as killed:
            stale, basis = lib.lock_staleness(lock)
        killed.assert_not_called()
        self.assertEqual((stale, basis), (False, "age-within-timeout"))

    def test_foreign_host_degrades_to_an_age_timeout(self):
        old = {"hostname": "some-other-host", "created_at": _hours_ago(25)}
        self.assertEqual(lib.lock_staleness(old), (True, "age-timeout"))

    def test_same_host_non_integer_pid_has_no_liveness_signal_either(self):
        lock = {"hostname": lib.socket.gethostname(), "pid": "1234", "created_at": _hours_ago(25)}
        self.assertEqual(lib.lock_staleness(lock), (True, "age-timeout"))

    def test_unreadable_created_at_is_not_stale(self):
        self.assertEqual(lib.lock_staleness({"hostname": "elsewhere"}), (False, "age-unknown"))

    def test_lock_is_stale_is_the_verdict_half_of_lock_staleness(self):
        for lock in ({"hostname": "elsewhere", "created_at": _hours_ago(25)},
                     {"hostname": "elsewhere", "created_at": lib.now_iso()},
                     {"hostname": lib.socket.gethostname(), "pid": os.getpid()}):
            self.assertEqual(lib.lock_is_stale(lock), lib.lock_staleness(lock)[0])

    def test_every_basis_has_an_operator_facing_clause(self):
        """check_lock indexes LOCK_STALENESS_REASONS with whatever basis comes
        back; a basis with no entry would raise KeyError inside the message."""
        bases = {"holder-process-live", "holder-process-gone", "holder-process-unprobeable",
                 "age-timeout", "age-within-timeout", "age-unknown"}
        self.assertEqual(set(lib.LOCK_STALENESS_REASONS), bases)

    def test_the_documented_timeout_matches_the_constant(self):
        """The docstrings spell the number out (a docstring cannot be built by
        %-formatting and stay a docstring), so pin the two together."""
        self.assertEqual(lib.LOCK_MAX_AGE_HOURS, 24)
        for doc in (lib.lock_staleness.__doc__, lib.force_release_lock.__doc__):
            self.assertIn("LOCK_MAX_AGE_HOURS (24h)", doc)

    def test_lock_staleness_documents_the_no_liveness_signal_regime(self):
        doc = lib.lock_staleness.__doc__
        self.assertIn("no liveness signal", doc)
        self.assertIn("pid namespace", doc)


class CheckLockMessageTest(unittest.TestCase):
    """The message an operator reads before deciding to break a lock."""

    def setUp(self):
        self.tdir = tempfile.mkdtemp(prefix="acs-test-")
        self.addCleanup(shutil.rmtree, self.tdir, True)

    def test_stale_message_names_the_basis_and_the_audited_way_out(self):
        lib.write_json(lib.lock_path(self.tdir),
                       {"checkout_id": "other", "hostname": "elsewhere",
                        "created_at": _hours_ago(30)})
        ok, message = lib.check_lock(self.tdir, "mine")
        self.assertFalse(ok)
        self.assertIn("older than 24h", message)
        self.assertIn("lock force-unlock", message)

    def test_live_message_says_why_it_is_not_considered_stale(self):
        lib.write_json(lib.lock_path(self.tdir),
                       {"checkout_id": "other", "hostname": "elsewhere",
                        "created_at": lib.now_iso()})
        ok, message = lib.check_lock(self.tdir, "mine")
        self.assertFalse(ok)
        self.assertIn("younger than 24h", message)


class ForceReleaseLockTest(unittest.TestCase):
    """The explicit break: refuses without a reason, and records before it acts."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="acs-test-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.repo = os.path.join(self.tmp, "repo")
        os.makedirs(self.repo)
        subprocess.run(["git", "init", "-q", self.repo], check=True, capture_output=True)
        self.tdir = os.path.join(self.tmp, "SHOP-1")
        os.makedirs(self.tdir)
        self.foreign = {"checkout_id": "someone-else", "checkout_path": "/elsewhere/repo",
                        "pid": 4242, "hostname": "dead-container", "created_at": lib.now_iso()}

    def _write_lock(self):
        lib.write_json(lib.lock_path(self.tdir), self.foreign)

    def _events(self):
        with open(lib.lock_audit_path(self.tdir), encoding="utf-8") as fh:
            return [json.loads(line) for line in fh if line.strip()]

    def test_refuses_without_a_reason(self):
        self._write_lock()
        for empty in (None, "", "   "):
            with self.assertRaises(ValueError):
                lib.force_release_lock(self.tdir, self.repo, empty)
        self.assertTrue(os.path.exists(lib.lock_path(self.tdir)),
                        "a refused break must leave the lock alone")
        self.assertFalse(os.path.exists(lib.lock_audit_path(self.tdir)),
                         "a refused break is not an event")

    def test_breaks_the_lock_and_records_who_and_why(self):
        self._write_lock()
        result = lib.force_release_lock(self.tdir, self.repo, "  the holding container died  ",
                                        actor="ops@example.com")
        self.assertTrue(result["forced"])
        self.assertFalse(os.path.exists(lib.lock_path(self.tdir)))

        events = self._events()
        self.assertEqual(len(events), 1)
        event = events[0]
        self.assertEqual(event["event"], "lock_force_released")
        self.assertEqual(event["reason"], "the holding container died")
        self.assertEqual(event["actor"], "ops@example.com")
        self.assertEqual(event["broken_lock"], self.foreign)
        self.assertEqual(event["by_checkout_id"], lib.checkout_id(self.repo))
        self.assertEqual(event["by_pid"], os.getpid())
        self.assertEqual(event["by_hostname"], lib.socket.gethostname())

    def test_records_the_staleness_verdict_it_did_not_obey(self):
        """A break does not need the lock to look stale — the audit entry is
        what makes the decision reviewable, so it must capture what the tooling
        thought at the time, including "this looked alive"."""
        self._write_lock()
        lib.force_release_lock(self.tdir, self.repo, "reclaiming the ticket")
        event = self._events()[0]
        self.assertFalse(event["staleness_verdict"])
        self.assertEqual(event["staleness_basis"], "age-within-timeout")

    def test_no_lock_is_reported_not_audited(self):
        result = lib.force_release_lock(self.tdir, self.repo, "nothing to break")
        self.assertFalse(result["forced"])
        self.assertIsNone(result["audit_path"])
        self.assertFalse(os.path.exists(lib.lock_audit_path(self.tdir)))

    def test_audit_is_written_before_the_unlink(self):
        """Ordering, proven by failing the unlink: the ledger must already name
        the break. The other order would leave a broken lock nobody can trace."""
        self._write_lock()
        with mock.patch("os.unlink", side_effect=OSError("read-only")):
            with self.assertRaises(lib.GateError) as caught:
                lib.force_release_lock(self.tdir, self.repo, "container died")
        self.assertIn("could not remove", str(caught.exception))
        events = self._events()
        self.assertEqual([e["event"] for e in events],
                         ["lock_force_released", "lock_force_release_failed"])
        self.assertEqual(events[1]["error"], "read-only")

    def test_the_ledger_is_append_only(self):
        for n in range(3):
            self._write_lock()
            lib.force_release_lock(self.tdir, self.repo, "break %d" % n)
        self.assertEqual([e["reason"] for e in self._events()],
                         ["break 0", "break 1", "break 2"])


class LockCliTest(AcsWorkspaceCase):
    """`acs.py lock status` / `lock force-unlock` end to end."""

    def setUp(self):
        super().setUp()
        self.ticket = self.new_ticket("Ship the thing", "task")
        self.tdir_path = self.tdir(self.ticket)

    def _acs(self, *args):
        return self.run_script("acs.py", *args)

    def _write_foreign_lock(self, **over):
        lock = {"checkout_id": "someone-else", "checkout_path": "/elsewhere/repo",
                "pid": 4242, "hostname": "dead-container", "created_at": lib.now_iso()}
        lock.update(over)
        lib.write_json(lib.lock_path(self.tdir_path), lock)
        return lock

    def test_status_reports_no_lock(self):
        out = self._acs("lock", "status", "--ticket", self.ticket)
        self.assertEqual(out.returncode, 0, out.stderr)
        body = json.loads(out.stdout)
        self.assertFalse(body["held"])
        self.assertIsNone(body["lock"])

    def test_status_reports_the_holder_the_verdict_and_the_basis(self):
        self._write_foreign_lock()
        out = self._acs("lock", "status", "--ticket", self.ticket)
        self.assertEqual(out.returncode, 0, out.stderr)
        body = json.loads(out.stdout)
        self.assertTrue(body["held"])
        self.assertFalse(body["held_by_me"])
        self.assertFalse(body["stale"])
        self.assertEqual(body["basis"], "age-within-timeout")
        self.assertIn("no liveness signal", body["basis_detail"])
        self.assertEqual(body["lock_path"], lib.lock_path(self.tdir_path))

    def test_force_unlock_requires_a_reason(self):
        self._write_foreign_lock()
        out = self._acs("lock", "force-unlock", "--ticket", self.ticket)
        self.assertNotEqual(out.returncode, 0)
        self.assertIn("--reason", out.stderr)
        self.assertTrue(os.path.exists(lib.lock_path(self.tdir_path)))

    def test_force_unlock_breaks_a_foreign_lock_and_leaves_the_ledger(self):
        lock = self._write_foreign_lock()
        out = self._acs("lock", "force-unlock", "--ticket", self.ticket,
                        "--reason", "the holding container died")
        self.assertEqual(out.returncode, 0, out.stderr)
        body = json.loads(out.stdout)
        self.assertTrue(body["forced"])
        self.assertEqual(body["broken_lock"], lock)
        self.assertFalse(os.path.exists(lib.lock_path(self.tdir_path)))
        with open(lib.lock_audit_path(self.tdir_path), encoding="utf-8") as fh:
            event = json.loads(fh.readline())
        self.assertEqual(event["reason"], "the holding container died")

    def test_force_unlock_refuses_this_checkouts_own_lock_without_force(self):
        """Breaking your own lock is almost always a mistake — the post hook
        releases it — so the CLI makes you say you meant it."""
        lib.acquire_lock(self.tdir_path, self.repo)
        out = self._acs("lock", "force-unlock", "--ticket", self.ticket, "--reason", "oops")
        self.assertNotEqual(out.returncode, 0)
        self.assertIn("--force", out.stderr)
        self.assertTrue(os.path.exists(lib.lock_path(self.tdir_path)))

        out = self._acs("lock", "force-unlock", "--ticket", self.ticket,
                        "--reason", "reclaiming after a crash", "--force")
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertFalse(os.path.exists(lib.lock_path(self.tdir_path)))

    def test_force_unlock_on_no_lock_is_reported_not_an_error(self):
        out = self._acs("lock", "force-unlock", "--ticket", self.ticket, "--reason", "tidying")
        self.assertEqual(out.returncode, 0, out.stderr)
        body = json.loads(out.stdout)
        self.assertFalse(body["forced"])
        self.assertIn("no lock file", body["detail"])


if __name__ == "__main__":
    unittest.main()
