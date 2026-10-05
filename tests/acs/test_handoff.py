"""Behavior tests for handoff.py's summary-file input, refusal paths, and the
no-in-progress-step resume fallback.

Originating ticket: MAR-177. Before this module the --summary-file reader
(the entire alternate input mode), the missing/whitespace-only-summary
refusal, the GateError-from-build_context refusal, the unresolvable-run and
missing-run refusals, and the "no in-progress step" /acs:ship resume fallback
were exercised by no test -- the existing suite only drives the --summary
inline form with an in-progress /acs:code step.

v0.5.0 moved the partition from the ticket to the RUN (4.2): handoff.py
resolves a run id from the checkout pointer, reads the one in_progress step
from the run ledger (I1), and finalizes it as `interrupted` with a
`stop_reason` -- `handed_off` is no longer a status (4.3). The fixtures below
build runs through acs_case's own helpers so they exercise the same
create_run / step start path a real invocation takes.
"""

import json
import os
import re
import shutil
import sys
import tempfile
import unittest

TESTS_ACS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TESTS_ACS)

import acs_case  # noqa: E402

MODULE_FILENAME = "handoff.py"
REPO_ID = "acme-shop"


def _mint_ticket(ws, tid, ttype="task", status="open", parent=None):
    """Write a valid active-partition ticket.json + index entry -- no subprocess.

    A run's SUBJECT, not its partition: the run directory is minted separately
    by acs_case.ensure_run()."""
    tdir = acs_case.lib.ticket_dir(ws, REPO_ID, tid)
    os.makedirs(tdir, exist_ok=True)
    ticket = acs_case.lib.new_ticket_doc(tid, tid, ttype, status=status, parent=parent)
    acs_case.lib.save_ticket(tdir, ticket)
    acs_case.lib.update_index(ws, REPO_ID, ticket, archived=False)
    return tdir, ticket


class TestSummaryRequired(unittest.TestCase):
    """38-40: the not-summary refusal fires before any git/ticket context is
    touched, whether no flag was given or --summary-file resolved to nothing
    but whitespace."""

    def test_missing_summary_exits_2(self):
        mod = acs_case.load_module(MODULE_FILENAME)
        nongit = tempfile.mkdtemp(prefix="acs-handoff-nosummary-")
        self.addCleanup(shutil.rmtree, nongit, True)
        with acs_case.pushd(nongit):
            code, out, err = acs_case.run_main(mod, [])
        self.assertEqual(code, 2)
        self.assertEqual(out, "")
        self.assertEqual(
            err,
            "acs handoff: a handoff summary is required "
            "(--summary or --summary-file)\n")

    def test_whitespace_only_summary_file_is_refused(self):
        tmp = tempfile.mkdtemp(prefix="acs-handoff-summaryfile-")
        self.addCleanup(shutil.rmtree, tmp, True)
        path = os.path.join(tmp, "summary.txt")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("   \n\t\n")
        mod = acs_case.load_module(MODULE_FILENAME)
        with acs_case.pushd(tmp):
            code, out, err = acs_case.run_main(mod, ["--summary-file", path])
        self.assertEqual(code, 2)
        self.assertEqual(
            err,
            "acs handoff: a handoff summary is required "
            "(--summary or --summary-file)\n")


class TestBuildContextGateError(unittest.TestCase):
    """45-47: build_context's GateError (cwd outside any git repo) exits 2."""

    def test_uninitialized_repo_exits_2_with_gate_error(self):
        mod = acs_case.load_module(MODULE_FILENAME)
        nongit = tempfile.mkdtemp(prefix="acs-handoff-nongit-")
        self.addCleanup(shutil.rmtree, nongit, True)
        with acs_case.pushd(nongit):
            code, out, err = acs_case.run_main(mod, ["--summary", "s"])
        self.assertEqual(code, 2)
        self.assertEqual(out, "")
        self.assertTrue(
            err.startswith("acs handoff: acs requires a git repository;"), err)


class TestRunResolutionRefusals(acs_case.AcsWorkspaceCase):
    """52-57: the unresolvable-run and missing-run disjuncts.

    Both refuse BEFORE touching the lock: a handoff that cannot name the run
    must not release someone else's."""

    def test_unresolvable_run_exits_2(self):
        mod = acs_case.load_module(MODULE_FILENAME)
        with acs_case.pushd(self.repo):
            code, out, err = acs_case.run_main(mod, ["--summary", "s"])
        self.assertEqual(code, 2)
        self.assertEqual(out, "")
        self.assertEqual(
            err,
            "acs handoff: no current run for this checkout "
            "(nothing to hand off)\n")

    def test_missing_run_is_refused(self):
        mod = acs_case.load_module(MODULE_FILENAME)
        rdir = self.rdir("SHOP-999")
        with acs_case.pushd(self.repo):
            code, out, err = acs_case.run_main(
                mod, ["--summary", "s", "--run", "SHOP-999"])
        self.assertEqual(code, 2)
        self.assertEqual(err, "acs handoff: no run recorded at %s\n" % rdir)

    def test_a_ticket_without_a_run_is_refused_without_taking_its_lock(self):
        """A ticket can exist with no run over it (nothing has started yet).
        That is "nothing to hand off", not a run to finalize."""
        tdir, _ticket = _mint_ticket(self.ws, "SHOP-500")
        acs_case.lib.acquire_lock(tdir, self.repo)
        mod = acs_case.load_module(MODULE_FILENAME)
        with acs_case.pushd(self.repo):
            code, out, err = acs_case.run_main(
                mod, ["--summary", "s", "--run", "SHOP-500"])
        self.assertEqual(code, 2)
        self.assertIn("no run recorded at", err)
        self.assertTrue(os.path.exists(acs_case.lib.lock_path(tdir)))


class TestResumeHint(acs_case.AcsWorkspaceCase):
    """36-37, 84-87: summary-file content is read and stripped into the
    persisted artifacts; the resume hint falls back to /acs:ship when no step
    is in_progress, and to /acs:<step> plus a released lock when one is."""

    def _started(self, tid="SHOP-42", step="code"):
        """A run over `tid` with `step` in flight, started the way a real
        invocation starts it (`acs step start`), so the ledger, the step
        state and the lock all say what the gate would have written."""
        _mint_ticket(self.ws, tid)
        out = self.start(step, tid)
        self.assertEqual(out.returncode, 0, out.stderr)
        return self.rdir(tid)

    def test_summary_file_content_is_recorded_stripped(self):
        rdir = self._started()
        summary_path = os.path.join(self.tmp, "summary.txt")
        with open(summary_path, "w", encoding="utf-8") as fh:
            fh.write("  done: probe; next: nothing  \n")
        mod = acs_case.load_module(MODULE_FILENAME)
        with acs_case.pushd(self.repo):
            code, out, err = acs_case.run_main(
                mod, ["--summary-file", summary_path, "--run", "SHOP-42"])
        self.assertEqual(code, 0, err)
        state = acs_case.lib.load_state(rdir, "code")
        self.assertEqual(
            state["invocations"][-1]["handoff_summary"], "done: probe; next: nothing")
        run = acs_case.lib.load_run(rdir)
        self.assertEqual(
            run["steps"]["code"]["summary"], "done: probe; next: nothing")

    def test_no_in_progress_step_resumes_with_ship(self):
        _mint_ticket(self.ws, "SHOP-42")
        rdir = self.ensure_run("SHOP-42")
        mod = acs_case.load_module(MODULE_FILENAME)
        with acs_case.pushd(self.repo):
            code, out, err = acs_case.run_main(
                mod, ["--summary", "s", "--run", "SHOP-42"])
        self.assertEqual(code, 0, err)
        payload = json.loads(out)
        self.assertIsNone(payload["step"])
        self.assertIsNone(payload["stop_reason"])
        self.assertEqual(payload["continue_with"], "/acs:ship SHOP-42")
        # Read the STEP MACHINE rather than probing for a file: "no
        # invocation was opened" is the claim, and a path check states it
        # only as long as the layout does not move.
        for step in acs_case.lib.HOOKED_SKILLS:
            self.assertIsNone(acs_case.lib.last_status(rdir, step), step)

    def test_in_progress_step_resumes_with_it_and_releases_the_lock(self):
        rdir = self._started()
        self.assertTrue(os.path.exists(acs_case.lib.lock_path(rdir)))
        mod = acs_case.load_module(MODULE_FILENAME)
        with acs_case.pushd(self.repo):
            code, out, err = acs_case.run_main(
                mod, ["--summary", "s", "--run", "SHOP-42"])
        self.assertEqual(code, 0, err)
        payload = json.loads(out)
        self.assertEqual(payload["step"], "code")
        self.assertEqual(payload["continue_with"], "/acs:code SHOP-42")
        state = acs_case.lib.load_state(rdir, "code")
        self.assertEqual(state["invocations"][-1]["status"], "interrupted")
        self.assertFalse(os.path.exists(acs_case.lib.lock_path(rdir)))

    def test_a_handoff_is_interrupted_with_a_stop_reason_not_handed_off(self):
        """4.3: `handed_off` named a REASON wearing a status. The step and its
        invocation both land on `interrupted`, and `stop_reason` carries why."""
        rdir = self._started()
        mod = acs_case.load_module(MODULE_FILENAME)
        with acs_case.pushd(self.repo):
            code, out, err = acs_case.run_main(
                mod, ["--summary", "s", "--run", "SHOP-42"])
        self.assertEqual(code, 0, err)
        payload = json.loads(out)
        self.assertEqual(payload["stop_reason"], "context_pressure")
        run = acs_case.lib.load_run(rdir)
        self.assertEqual(run["steps"]["code"]["status"], "interrupted")
        self.assertEqual(run["steps"]["code"]["stop_reason"], "context_pressure")
        entry = acs_case.lib.load_state(rdir, "code")["invocations"][-1]
        self.assertEqual(entry["stop_reason"], "context_pressure")
        self.assertNotIn(
            "handed_off", json.dumps(run),
            "`handed_off` is not a status any more (4.3)")

    def test_an_explicit_stop_reason_is_recorded(self):
        rdir = self._started()
        mod = acs_case.load_module(MODULE_FILENAME)
        with acs_case.pushd(self.repo):
            code, out, err = acs_case.run_main(
                mod, ["--summary", "s", "--run", "SHOP-42",
                      "--stop-reason", "session_end"])
        self.assertEqual(code, 0, err)
        self.assertEqual(json.loads(out)["stop_reason"], "session_end")
        self.assertEqual(
            acs_case.lib.load_run(rdir)["steps"]["code"]["stop_reason"],
            "session_end")

    def test_the_ledger_snapshot_is_written_to_the_run_root(self):
        """handoff.py's derived snapshot is state, not conversation: it names
        the run, the workflow and the step that was in flight."""
        rdir = self._started()
        mod = acs_case.load_module(MODULE_FILENAME)
        with acs_case.pushd(self.repo):
            code, _out, err = acs_case.run_main(
                mod, ["--summary", "s", "--run", "SHOP-42"])
        self.assertEqual(code, 0, err)
        path = os.path.join(rdir, acs_case.lib.HANDOFF_CONTEXT_FILENAME)
        with open(path, encoding="utf-8") as fh:
            body = fh.read()
        self.assertIn("# Handoff context \u2014 SHOP-42", body)
        self.assertIn("## Workflow", body)
        self.assertIn("`/acs:code` invocation started", body)


# ---------------------------------------------------------------------------
# The /acs:handoff SKILL (ADR-0131). handoff.py above is the INTERNAL
# context-pressure pause the step skills call; the skill of the same name is
# the member -> member ticket handoff over `refs/acs/handoff/<ID>`, and never
# calls handoff.py. These pin its contract; acs.py handoff's own behaviour is
# tested with the CLI.
# ---------------------------------------------------------------------------

HANDOFF_SKILL = os.path.join(acs_case.REPO_ROOT, "plugins", "acs", "skills",
                             "handoff", "SKILL.md")


class TestTeamHandoffSkill(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(HANDOFF_SKILL, encoding="utf-8") as fh:
            text = fh.read()
        _, cls.fm, cls.body = text.split("---\n", 2)
        cls.norm = re.sub(r"\s+", " ", cls.body)

    def section(self, heading):
        start = self.body.index(heading)
        nxt = self.body.find("\n## ", start + len(heading))
        return self.body[start:nxt if nxt != -1 else len(self.body)]

    def test_frontmatter_routes_ticket_handoff_between_members(self):
        self.assertRegex(self.fm, r'(?m)^argument-hint: "<ticket-id> \| receive <ticket-id> \| list"$')
        desc = re.search(r"(?m)^description: (.*)$", self.fm).group(1)
        self.assertIn("teammate", desc)
        self.assertIn("refs/acs/handoff/<ID>", desc)
        self.assertIn("pick up", desc)
        self.assertIn("handoffs are waiting", desc)
        self.assertIn("Call it as your first action", desc)
        # A session pause is no longer this skill's job: the description
        # says so, so a "continue this in a new session" request routes
        # nowhere rather than here.
        self.assertIn("Not for pausing your own session", desc)
        self.assertNotIn("disallowed-tools", self.fm)

    def test_unhooked_and_inline(self):
        from acs_lib import UNHOOKED_SKILLS
        self.assertIn("handoff", UNHOOKED_SKILLS)
        self.assertIn("no `acs step start`", self.norm)
        self.assertIn("no subagents", self.norm)
        self.assertNotIn("handoff.py", self.body)

    def test_three_modes_each_one_cli_call(self):
        for mode in ("send", "receive", "list"):
            self.assertRegex(self.body, r'acs\.py" handoff %s\b' % mode, mode)
        self.assertIn("## Step 2 — Send", self.body)
        self.assertIn("## Step 3 — Receive", self.body)
        self.assertIn("## Step 4 — List", self.body)

    def test_send_previews_then_asks_once_then_pushes(self):
        send = self.section("## Step 2 — Send")
        preview = send.index("--dry-run")
        ask = send.index("ONE grouped AskUserQuestion")
        push = send.index("--note-file")
        self.assertLess(preview, ask)
        self.assertLess(ask, push)
        norm = re.sub(r"\s+", " ", send)
        for part in ("done", "in flight", "next", "decisions"):
            self.assertIn("**%s**" % part, norm, part)
        self.assertIn("`Include` / `Skip`", norm)
        self.assertIn("Confirm the push", norm)
        self.assertIn("--attach", norm)
        self.assertRegex(norm, r"(?i)ever packaged without its own `Include`")

    def test_sender_keeps_everything(self):
        send = re.sub(r"\s+", " ", self.section("## Step 2 — Send"))
        self.assertRegex(send, r"(?i)nothing on this machine changes")
        self.assertRegex(send, r"(?i)lock")

    def test_never_commits_branches_or_opens_a_pr(self):
        self.assertIn("ADR-0127", self.body)
        self.assertRegex(self.norm, r"(?i)never create or switch a branch, stage, commit, push or open a PR")
        self.assertRegex(self.norm, r"(?i)never push the ref yourself")

    def test_receive_shows_the_note_and_continue_with(self):
        recv = re.sub(r"\s+", " ", self.section("## Step 3 — Receive"))
        self.assertIn("**note**", recv)
        self.assertIn("`continue_with` VERBATIM", recv)
        self.assertRegex(recv, r"(?i)never stash or discard")

    def test_a_session_pause_is_answered_not_sent(self):
        self.assertRegex(self.norm, r"(?i)Not a session pause")
        self.assertIn("/acs:ship <ID>", self.norm)

    def test_completion_report(self):
        report = self.body[self.body.index("## Completion report (normative)"):]
        for label in ("Ticket", "Status", "Results", "Findings", "Artifacts",
                      "Metrics", "Next"):
            self.assertIn("- **%s**:" % label, report, label)
        self.assertNotIn("iterations <n>", report)


if __name__ == "__main__":
    unittest.main()
