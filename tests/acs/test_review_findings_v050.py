"""Regressions for the defects a review of the v0.5.0 redesign found.

Each of these shipped green: the deterministic suite exercised the helper and
the fixture agreed with the code, so the two were wrong together. The tests
here assert the property rather than the spelling, and each names the failure
it would have caught.

Run: python3 -m unittest tests.acs.test_review_findings_v050 -v
"""

import io
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import acs_case  # noqa: E402
from acs_case import lib  # noqa: E402

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRIPTS = os.path.join(REPO_ROOT, "plugins", "acs", "hooks", "scripts")

PLAN = """# Plan — a deep change

Prose the human approves in one read. Tests hold coverage at 90%.

## Contract
delivery_path: standard
owes:
  api_contract: false
  test_cases:   true
  e2e:          false
  reason: "fixture"

### Executor tasks & file map
- task 1: src/app.py
"""


class PlanApprovalBrakeTest(acs_case.AcsWorkspaceCase):
    """The brake must read the key the approval WRITES.

    `_brake_code` read `record["approved"]`; `plan-approval.py`, its sole
    writer, writes `eligible`. Every `standard` and `complex` run was refused
    with "records none", and re-approving wrote the same keys again — a loop
    with no exit.
    """

    def _approved_plan(self, text=PLAN):
        tid = self.new_ticket("A deep change", "task")
        rdir = self.ensure_run(tid)
        step = os.path.join(rdir, "steps", "create-impl-plan")
        os.makedirs(step, exist_ok=True)
        with io.open(os.path.join(step, "plan.md"), "w", encoding="utf-8",
                     newline="") as fh:
            fh.write(text)
        out = self.run_script("plan-approval.py", "--run", tid)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertTrue(json.loads(out.stdout)["eligible"], out.stdout)
        return tid, rdir

    def test_an_approved_plan_opens_the_code_gate(self):
        tid, _rdir = self._approved_plan()
        out = self.pre("code", tid)
        self.assertEqual(out.returncode, 0,
                         "an approved plan must open /acs:code: %s" % out.stderr)

    def test_an_unapproved_plan_still_closes_it(self):
        """The brake is not merely disabled: a deep path with no approval
        record on disk is still refused."""
        tid = self.new_ticket("A deep change", "task")
        rdir = self.ensure_run(tid)
        step = os.path.join(rdir, "steps", "create-impl-plan")
        os.makedirs(step, exist_ok=True)
        with io.open(os.path.join(step, "plan.md"), "w", encoding="utf-8") as fh:
            fh.write(PLAN)
        out = self.pre("code", tid)
        self.assertEqual(out.returncode, 2, out.stdout)
        self.assertIn("approved plan", out.stderr)

    def test_a_crlf_plan_is_approvable_and_stays_approved(self):
        """The approval hashes the DECODED text (universal newlines has
        already folded CRLF to LF); the brake hashed the raw bytes. A plan
        authored on Windows was approved and then permanently rejected as "a
        different revision", with no edit that could reconcile the two."""
        tid, _rdir = self._approved_plan(PLAN.replace("\n", "\r\n"))
        out = self.pre("code", tid)
        self.assertEqual(out.returncode, 0,
                         "a CRLF plan must stay approved: %s" % out.stderr)


class GateIsReadOnlyTest(acs_case.AcsWorkspaceCase):
    """`acs.py gate` is documented as "run one skill's pre-gate without
    running the skill". It created the run, took the lock, opened the step and
    settled no-ops — so asking "would this pass?" permanently completed the
    step it was asked about."""

    def _runs_root(self):
        return os.path.join(lib.repo_dir(self.ws, "acme-shop"), "runs")

    def test_asking_about_a_skill_creates_no_run(self):
        self.new_ticket("A change", "task")
        before = sorted(os.listdir(self._runs_root())) if os.path.isdir(self._runs_root()) else []
        out = self.run_script("acs.py", "gate", "--skill", "code")
        self.assertIn(out.returncode, (0, 2), out.stderr)
        after = sorted(os.listdir(self._runs_root())) if os.path.isdir(self._runs_root()) else []
        self.assertEqual(after, before)

    def test_asking_does_not_open_or_settle_the_step(self):
        tid = self.new_ticket("A change", "task")
        rdir = self.ensure_run(tid)
        self.run_script("acs.py", "gate", "--skill", "create-e2e-tests", "--ticket", tid)
        state = os.path.join(rdir, "steps", "create-e2e-tests", "state.json")
        self.assertFalse(os.path.exists(state),
                         "a question must not open or complete the step it asks about")

    def test_asking_does_not_take_the_lock(self):
        tid = self.new_ticket("A change", "task")
        rdir = self.ensure_run(tid)
        self.run_script("acs.py", "gate", "--skill", "code", "--ticket", tid)
        self.assertFalse(os.path.exists(os.path.join(rdir, "lock.json")))


class OneInvocationPerAttemptTest(acs_case.AcsWorkspaceCase):
    """Two writers open a step — the PreToolUse gate and `acs step start` — and
    a hooked run goes through both. Appending unconditionally gave every step
    two invocations, of which `finalize_invocation` closes only the last: the
    first stayed `in_progress` for ever and every per-step total counted it."""

    def test_the_gate_and_the_cli_open_one_invocation_between_them(self):
        tid = self.new_ticket("A change", "task")
        rdir = self.ensure_run(tid)
        self.pre("analyze-requirements", tid)
        self.run_script("acs.py", "step", "start", "--step", "analyze-requirements",
                        "--run", tid)
        state = lib.read_json(lib.step_state_path(rdir, "analyze-requirements"))
        self.assertEqual(len(state["invocations"]), 1, state["invocations"])

    def test_a_genuine_second_attempt_still_gets_its_own_entry(self):
        """Idempotency is per ATTEMPT, not per step: a resumed step must keep
        the interrupted attempt's cost and session trail."""
        tid = self.new_ticket("A change", "task")
        rdir = self.ensure_run(tid)
        self.run_script("acs.py", "step", "start", "--step", "analyze-requirements",
                        "--run", tid)
        self.run_script("acs.py", "step", "finish", "--step", "analyze-requirements",
                        "--run", tid, "--status", "interrupted",
                        "--stop-reason", "session_end")
        self.run_script("acs.py", "step", "start", "--step", "analyze-requirements",
                        "--run", tid)
        state = lib.read_json(lib.step_state_path(rdir, "analyze-requirements"))
        self.assertEqual(len(state["invocations"]), 2, state["invocations"])


class PhaseSnapshotDoesNotClobberTheReportTest(acs_case.AcsWorkspaceCase):
    """`ROLE_PHASES["executor"] == "execute"`, and the executor is told to
    write its JSON report to `iter-<n>/execute.json`. The SubagentStop
    snapshot wrote the raw XML message to the same path, so every reader of
    `execute*.json` — `derive.execute_reports`, and through it `states.tests` —
    found a file that does not parse."""

    def test_the_snapshot_and_the_report_are_two_paths(self):
        tid = self.new_ticket("A change", "task")
        rdir = self.ensure_run(tid)
        snapshot = lib.phase_artifact_path(rdir, "code", 1, "execute")
        report = os.path.join(rdir, "steps", "code", "iter-1", "execute.json")
        self.assertNotEqual(os.path.realpath(snapshot), os.path.realpath(report))

    def test_the_snapshot_is_not_named_json(self):
        """It holds an XML message. Naming it `.json` did not make its bytes
        JSON; it only made every JSON reader downstream fail on it."""
        tid = self.new_ticket("A change", "task")
        rdir = self.ensure_run(tid)
        self.assertFalse(
            lib.phase_artifact_path(rdir, "code", 1, "execute").endswith(".json"))


class TicketSubjectMustExistTest(acs_case.AcsWorkspaceCase):
    """A `<PREFIX>-<n>` token is a REFERENCE. A run minted over a reference to
    nothing has a subject that cannot be read, and the failure surfaces
    several steps later at whichever step first needs `ticket.json`."""

    def test_the_pointer_resolves_a_second_run_to_its_ticket(self):
        """`derive_run_id` appends `-r2` for a repeat run on one subject.
        Returning that verbatim as the ticket id sent every consumer looking
        for a partition named `MAR-590-r2`, which does not exist."""
        tid = self.new_ticket("A change", "task")
        repo = lib.repo_dir(self.ws, "acme-shop")
        lib.save_pointer(repo, lib.checkout_id(self.repo), run_id="%s-r2" % tid,
                         checkout_path=self.repo)
        resolved, source = lib.resolve_ticket_id(
            self.repo, {"ticket_prefix": "SHOP"}, self.ws, "acme-shop")
        self.assertEqual(source, "pointer")
        self.assertEqual(resolved, tid)


class GuardEventNeverRaisesTest(unittest.TestCase):
    """The docstring promises it: "An exception here would let a bookkeeping
    failure overturn a verdict." The handler was `except BaseException: raise`,
    a no-op, so the guarantee lived only in the one caller that happened to
    wrap it."""

    def test_an_unwritable_state_returns_false_rather_than_raising(self):
        from unittest import mock
        with mock.patch.object(lib.step, "save_state",
                               side_effect=OSError("read-only workspace")):
            with mock.patch.object(lib.step, "load_state",
                                   return_value={"invocations": [{"status": "in_progress"}]}):
                self.assertIs(
                    lib.step.record_guard_event("/nonexistent", "code", "MAR-1", {}),
                    False)


if __name__ == "__main__":
    unittest.main()
