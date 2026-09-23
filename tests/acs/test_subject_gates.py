"""The two pre-hook gates for skills that are NOT steps of the resolved workflow.

Originating ticket: MAR-586. `/acs:merge-pr` and `/acs:create-design` are
deliberately absent from `ship.yaml`, so the gate's `has_step` return used to
short-circuit before any brake ran and both hooks exited 0 on every profile.
This module pins the restored behaviour:

  * merge-pr refuses when no ticket resolves, and when no completed run recorded
    a PR reference for the one that does -- bare, ticketed and epic alike;
  * merge-pr's exempt non-ticket forms (--pr N, #N, a PR URL) still pass through
    un-gated, which is what keeps `_merge_pr_arg_text` a live helper;
  * create-design refuses a ticket that is not flagged needs_design, and refuses
    when no ticket resolves, while a needs_design ticket keeps opening;
  * the refusal WORDING is read out of the golden dataset at test time, so
    drift fails here rather than only in the eval tier;
  * a subject gate resolves a TICKET, never a run: it creates no run directory,
    which is what keeps `acs gate`'s side-effect-free contract intact.

Stdlib-only. Run:  python3 -m unittest tests.acs.test_subject_gates -v
"""

import json
import os
import sys
import unittest

TESTS_ACS = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(os.path.dirname(TESTS_ACS))
sys.path.insert(0, TESTS_ACS)

import acs_case  # noqa: E402

lib = acs_case.lib

#: The refusal wording these gates emit, recorded verbatim. This used to be
#: read out of the eval suite's `dataset/cases/06-gates.json`, a 355-case
#: no-model tier that asserted the plugin's observable surface. That tier was
#: replaced by `claude plugin eval`, whose format grades an agent session and
#: cannot express a CLI's exact stderr -- so the five strings these tests need
#: moved HERE, to the layer that was always the right home for them.
GOLDENS = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "subject_gate_goldens.json")

#: The prefix the golden sandbox mints under, the one this fixture does, and
#: the ticket id every recorded ticketed/epic case names.
GOLDEN_PREFIX, FIXTURE_PREFIX = "TKT", "SHOP"
GOLDEN_SUBJECT = "TKT-1"


def golden_messages(case_id, ticket=None):
    """The `stderr_contains` strings one recorded case pins, with the golden
    sandbox's ticket ids rewritten to this fixture's."""
    with open(GOLDENS, encoding="utf-8") as fh:
        doc = json.load(fh)
    if case_id not in doc:
        raise AssertionError("no case %s in %s" % (case_id, GOLDENS))
    out = []
    for text in doc[case_id]:
        text = text.replace(GOLDEN_PREFIX + "-123", FIXTURE_PREFIX + "-123")
        out.append(text.replace(GOLDEN_SUBJECT, ticket) if ticket else text)
    return out


class MergePrGateTest(acs_case.AcsWorkspaceCase):
    """/acs:merge-pr needs a recorded PR reference before it may merge."""

    def test_merge_pr_is_refused_when_no_ticket_resolves(self):
        out = self.pre("merge-pr")
        self.assertEqual(out.returncode, 2, out.stderr)
        self.assertIn("acs pre-merge-pr: blocked", out.stderr)
        self.assertIn(
            "could not resolve a ticket id for /merge-pr (no argument, no session "
            "pointer, no ticket in the branch name). Pass it explicitly, e.g. "
            "/acs:merge-pr SHOP-123.", out.stderr)

    def test_merge_pr_is_refused_with_no_pr_reference_recorded(self):
        ticket = self.new_ticket("Add user login", "task")
        out = self.pre("merge-pr", ticket)
        self.assertEqual(out.returncode, 2, out.stderr)
        self.assertIn("acs pre-merge-pr: blocked", out.stderr)
        self.assertIn(
            "no PR reference recorded for %s — /acs:create-pr (or the product-level "
            "skill) must complete first." % ticket, out.stderr)

    def test_merge_pr_is_refused_on_an_epic_with_no_pr_reference(self):
        ticket = self.new_ticket("Checkout revamp", "epic")
        out = self.pre("merge-pr", ticket)
        self.assertEqual(out.returncode, 2, out.stderr)
        self.assertIn(
            "no PR reference recorded for %s — /acs:create-pr (or the product-level "
            "skill) must complete first." % ticket, out.stderr)

    def test_merge_pr_opens_once_a_completed_create_pr_recorded_a_pr(self):
        ticket = self.new_ticket("Add user login", "task")
        self.walk_to(ticket, "docs-sync")
        started = self.start("create-pr", ticket)
        self.assertEqual(started.returncode, 0, started.stderr)
        posted = self.post("create-pr", ticket, {
            "status": "completed",
            "states": {"pr": {"number": 7, "url": "https://example.invalid/pull/7"}}})
        self.assertEqual(posted.returncode, 0, posted.stderr)

        out = self.pre("merge-pr", ticket)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertNotIn("blocked", out.stderr)

    def test_a_run_locked_by_another_checkout_refuses_the_merge(self):
        # v0.5.0 locks the RUN, not the ticket partition, so that is where the
        # subject gate looks for a holder.
        ticket = self.new_ticket("Add user login", "task")
        rdir = self.ensure_run(ticket)
        lib.write_json(lib.lock_path(rdir), {
            "checkout_id": "someone-else", "checkout_path": "/elsewhere/shop",
            "pid": os.getpid(), "hostname": "elsewhere", "created_at": lib.now_iso()})

        out = self.pre("merge-pr", ticket)
        self.assertEqual(out.returncode, 2, out.stderr)
        self.assertIn("locked by another session", out.stderr)

    def test_the_exempt_pr_form_is_never_ticket_gated(self):
        for args_text in ("--pr 42", "#42", "https://github.com/acme/shop/pull/42"):
            with self.subTest(args=args_text):
                out = self.pre("merge-pr", args_text)
                self.assertEqual(out.returncode, 0, out.stderr)
                self.assertNotIn("blocked", out.stderr)


class CodeSubjectGateTest(acs_case.AcsWorkspaceCase):
    """/acs:code refuses a ticket reference that names no ticket.

    A `<PREFIX>-<n>` token is a ticket REFERENCE, and a run over a reference to
    nothing is a run whose subject cannot be read -- so the gate refuses it up
    front rather than letting the first step that needs ticket.json discover it.

    Ported from the behavioural harness's s01 install-gate smoke when that
    harness was retired: s01 was the ONLY thing asserting this refusal. Its
    other gate checks were already pinned on the source tree here; this one was
    not, and a coverage audit against the real gate's message found no test
    carrying it. s01 ran it against the INSTALLED build -- that angle now
    belongs to `claude plugin eval acs@gms-marketplace`, which no unit test can
    stand in for."""

    def test_code_is_refused_for_a_ticket_that_does_not_exist(self):
        out = self.pre("code", "SHOP-1")
        self.assertEqual(out.returncode, 2, out.stderr)
        self.assertIn("acs pre-code: blocked", out.stderr)
        self.assertIn(
            "no ticket SHOP-1 in this repo's workspace — run /acs:create-ticket "
            "to make one, or give /acs:code a prompt or a document instead.",
            out.stderr)

    def test_the_same_reference_opens_once_the_ticket_exists(self):
        """The refusal is about the missing SUBJECT, nothing else: mint the
        ticket and the identical invocation passes."""
        minted = self.run_script("new-ticket.py", "--title", "Add a /health endpoint",
                                 "--type", "task", "--needs-design", "false")
        self.assertEqual(minted.returncode, 0, minted.stderr)
        self.assertEqual(json.loads(minted.stdout)["ticket_id"], "SHOP-1")
        out = self.pre("code", "SHOP-1")
        self.assertEqual(out.returncode, 0, out.stderr)


class CreateDesignGateTest(acs_case.AcsWorkspaceCase):
    """/acs:create-design only runs for a design-significant ticket."""

    def test_create_design_is_refused_for_a_ticket_not_flagged_needs_design(self):
        ticket = self.new_ticket("Add user login", "task")
        out = self.pre("create-design", ticket)
        self.assertEqual(out.returncode, 2, out.stderr)
        self.assertIn("acs pre-create-design: blocked", out.stderr)
        self.assertIn(
            "ticket %s is not flagged needs_design — /create-design only runs for "
            "design-significant tickets; go straight to /acs:code %s."
            % (ticket, ticket), out.stderr)

    def test_create_design_is_refused_with_no_subject_at_all(self):
        out = self.pre("create-design")
        self.assertEqual(out.returncode, 2, out.stderr)
        self.assertIn("acs pre-create-design: blocked", out.stderr)
        self.assertIn(
            "could not resolve a ticket id for /create-design (no argument, no session "
            "pointer, no ticket in the branch name). Pass it explicitly, e.g. "
            "/acs:create-design SHOP-123.", out.stderr)

    def test_create_design_opens_for_a_needs_design_ticket(self):
        ticket = self.new_ticket("Checkout revamp", "epic")
        out = self.pre("create-design", ticket)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertNotIn("blocked", out.stderr)


class SecondRunLockTest(acs_case.AcsWorkspaceCase):
    """WHICH run's lock a subject gate consults when a subject has several.

    Every run recorded for the subject, plus the ticket-keyed partition -- the
    same list `_pr_recorded_for` already walks, for the same reason.
    `derive_run_id` mints `<ticket>-r2`, `-r3` for later runs on one subject
    (`run.py:126`), and `lock.py:11` states the model: "two runs on the same
    subject are two partitions and two locks". No single directory owns "the"
    lock for a ticket, and the bare `runs/<ticket_id>` join `partition_for_ticket`
    does cannot name a later one at all.

    Deliberately NOT "the newest open run": which runs are over is the runs
    index's claim, and `_reindex` writes it best-effort (`run.py:488-491`). A
    brake that consults a lock only while a second document says the run is live
    stops consulting it exactly when that document drifts. Checking every run
    refuses more, never less; a lock that outlived its run is what `check_lock`'s
    staleness branch and `force-unlock` exist to answer.
    """

    def lock_foreign(self, rdir):
        """The lock as another checkout writes it."""
        lib.write_json(lib.lock_path(rdir), {
            "checkout_id": "someone-else", "checkout_path": "/elsewhere/shop",
            "pid": os.getpid(), "hostname": "elsewhere", "created_at": lib.now_iso()})
        return rdir

    def second_run(self, ticket):
        """The run `acs run new` opens second on this subject."""
        repo = lib.repo_dir(self.ws, "acme-shop")
        wf_path = lib.default_workflow_path()
        run_id = "%s-r2" % ticket
        self.assertEqual(
            run_id, lib.derive_run_id({"kind": "ticket", "ticket_id": ticket}, [ticket]),
            "the fixture must use the id derive_run_id mints for a second run")
        _id, rdir, _doc = lib.create_run(
            repo, {"kind": "ticket", "ticket_id": ticket},
            lib.validate_workflow_file(wf_path), wf_path, run_id=run_id)
        return rdir

    def test_a_lock_on_the_only_run_is_honoured_when_that_run_is_a_second_one(self):
        ticket = self.new_ticket("Add user login", "task")
        self.lock_foreign(self.second_run(ticket))
        out = self.pre("merge-pr", ticket)
        self.assertEqual(out.returncode, 2, out.stderr)
        self.assertIn("locked by another session", out.stderr)
        self.assertNotIn("no PR reference recorded", out.stderr)

    def test_a_locked_second_run_refuses_while_the_first_run_sits_idle(self):
        ticket = self.new_ticket("Add user login", "task")
        self.ensure_run(ticket)  # runs/<ticket>, unlocked
        self.lock_foreign(self.second_run(ticket))
        out = self.pre("merge-pr", ticket)
        self.assertEqual(out.returncode, 2, out.stderr)
        self.assertIn("locked by another session", out.stderr)
        self.assertNotIn("no PR reference recorded", out.stderr)


class MalformedPrStateTest(acs_case.AcsWorkspaceCase):
    """A recorded `states.pr` that is not an object refuses by name.

    `schemas/result.schema.json` types `states` as a bare object, so
    `validate_result` admits any `states.pr` -- a string, a list -- and
    `finalize_invocation` copies it verbatim into the step state file
    (`step.py:191-192`). The merge brake reads it back from there and must say
    which file is wrong and what to do about it, rather than failing on an
    attribute the value does not have.
    """

    def state_with_pr(self, ticket, pr):
        """The create-pr state file a completed step leaves, with `states.pr`
        as recorded. Written through `save_state`, the writer the post-hook
        itself uses, so the fixture is the state the gate really reads."""
        self.assertEqual(
            lib.validate_result({"status": "completed", "skill": "create-pr",
                                 "run_id": ticket, "states": {"pr": pr}}, "create-pr"),
            [], "a non-object states.pr is admissible, which is why the gate meets one")
        self.walk_to(ticket, "docs-sync")
        started = self.start("create-pr", ticket)
        self.assertEqual(started.returncode, 0, started.stderr)
        posted = self.post("create-pr", ticket, {
            "status": "completed",
            "states": {"pr": {"number": 7, "url": "https://example.invalid/pull/7"}}})
        self.assertEqual(posted.returncode, 0, posted.stderr)
        rdir = self.rdir(ticket)
        state = lib.load_state(rdir, "create-pr")
        state["states"]["pr"] = pr
        lib.save_state(rdir, "create-pr", state)
        return lib.state_path(rdir, "create-pr")

    def test_a_non_object_pr_reference_is_refused_by_file_and_remedy(self):
        for pr in ("https://example.invalid/pull/7", [7]):
            with self.subTest(pr=pr):
                ticket = self.new_ticket("Add user login", "task")
                state_file = self.state_with_pr(ticket, pr)
                out = self.pre("merge-pr", ticket)
                self.assertEqual(out.returncode, 2, out.stderr)
                self.assertNotIn("Traceback", out.stderr)
                self.assertNotIn("AttributeError", out.stderr)
                self.assertIn(state_file, out.stderr)
                self.assertIn("is not an object", out.stderr)
                self.assertIn("/acs:create-pr", out.stderr)


class SubjectGateCreatesNoRunTest(acs_case.AcsWorkspaceCase):
    """A subject gate resolves a ticket, so it opens no run to answer with."""

    def test_a_refused_subject_gate_creates_no_run(self):
        ticket = self.new_ticket("Add user login", "task")
        runs = os.path.join(lib.repo_dir(self.ws, "acme-shop"), "runs")
        for skill in ("merge-pr", "create-design"):
            with self.subTest(skill=skill):
                out = self.pre(skill, ticket)
                self.assertEqual(out.returncode, 2, out.stderr)
                self.assertFalse(os.path.exists(runs),
                                 "%s opened a run to refuse with: %s" % (skill, runs))


class RecordedGoldenWordingTest(acs_case.AcsWorkspaceCase):
    """The restored refusals are byte-for-byte what the golden dataset records."""

    def test_restored_refusals_match_the_recorded_golden_strings(self):
        task = self.new_ticket("Add user login", "task")
        epic = self.new_ticket("Checkout revamp", "epic")
        cases = [
            ("GATE-011", "create-design", ""),
            ("GATE-015", "merge-pr", ""),
            ("GATE-026", "create-design", task),
            ("GATE-030", "merge-pr", task),
            ("GATE-045", "merge-pr", epic),
        ]
        for case_id, skill, args_text in cases:
            with self.subTest(case=case_id):
                out = self.pre(skill, args_text)
                self.assertEqual(out.returncode, 2, out.stderr)
                for message in golden_messages(case_id, args_text or None):
                    self.assertIn(message, out.stderr)


class OrphanHelpersTest(unittest.TestCase):
    """Neither helper the ticket names is left without a caller."""

    def test_merge_pr_arg_text_is_reached_by_the_restored_gate(self):
        source = acs_case.acs_lib_source()
        self.assertIn("_merge_pr_arg_text(payload)", source)
        gates = os.path.join(acs_case.ACS_LIB_PKG, "gates.py")
        with open(gates, encoding="utf-8") as fh:
            body = fh.read()
        self.assertIn("args_text = _merge_pr_arg_text(payload)", body)

    def test_design_requirement_has_a_live_caller(self):
        path = os.path.join(acs_case.SCRIPTS, "acs_state_commands.py")
        with open(path, encoding="utf-8") as fh:
            body = fh.read()
        self.assertIn("lib.design_requirement(", body)
        self.assertTrue(callable(lib.design_requirement))


if __name__ == "__main__":
    unittest.main()
