"""The RUN machine: runs/<run-id>/run.json (§4.3 of the redesign).

What these pin, and why each one matters:

  * a run needs no ticket -- the whole point of re-keying the partition
  * the run id is DERIVED from the subject, so it reads like the thing it
    names and a second run on one subject does not collide
  * the cursor is "the first step not completed", which is the whole of what
    replaced the ready-set walk
  * `skipped` and `handed_off` are not states, and the vocabulary refuses them
  * the loop settles in ONE writer, so a caller cannot advance the cursor
    without also settling the loop
  * I1-I5 catch a ledger that has drifted

Run:  python3 -m unittest tests.acs.test_run_machine -v
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))), "src", "acs", "hooks", "scripts"))

from acs_lib import run as R  # noqa: E402
from acs_lib import step as S  # noqa: E402
from acs_lib import workflow as W  # noqa: E402
from acs_lib._common import GateError  # noqa: E402

PLUGIN = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "src", "acs")
SHIP = os.path.join(PLUGIN, "workflows", "ship.yaml")


def ship():
    return W.validate_workflow_file(SHIP)


class RunIdTest(unittest.TestCase):
    """§4.2: the id reads like the thing it names, because nobody remembers
    `20260919-a1b2c3`."""

    def test_a_ticket_run_is_named_by_its_ticket(self):
        self.assertEqual(R.derive_run_id({"kind": "ticket", "ticket_id": "MAR-590"}),
                         "MAR-590")

    def test_a_prompt_run_is_a_slug_plus_four_hex(self):
        rid = R.derive_run_id({"kind": "prompt", "text": "fix the login timeout on slow networks"})
        self.assertTrue(rid.startswith("fix-the-login-timeout-on-slow-"), rid)
        self.assertRegex(rid, r"-[0-9a-f]{4}$")

    def test_two_different_prompts_do_not_collide(self):
        a = R.derive_run_id({"kind": "prompt", "text": "fix the login timeout badly"})
        b = R.derive_run_id({"kind": "prompt", "text": "fix the login timeout wisely"})
        self.assertNotEqual(a, b)

    def test_a_second_run_on_one_subject_gets_r2(self):
        subject = {"kind": "ticket", "ticket_id": "MAR-590"}
        self.assertEqual(R.derive_run_id(subject, existing=["MAR-590"]), "MAR-590-r2")
        self.assertEqual(R.derive_run_id(subject, existing=["MAR-590", "MAR-590-r2"]),
                         "MAR-590-r3")

    def test_a_document_run_is_named_by_its_basename(self):
        rid = R.derive_run_id({"kind": "document", "path": "docs/rfcs/0042-retry-policy.md",
                               "sha256": "abc"})
        self.assertTrue(rid.startswith("0042-retry-policy-"), rid)


class RunLifecycleTest(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.repo = os.path.join(self.tmp, "wk", "acme")
        os.makedirs(self.repo)
        self.wf = ship()

    def _run(self, subject=None):
        subject = subject or {"kind": "prompt", "text": "add a retry budget"}
        return R.create_run(self.repo, subject, self.wf, SHIP)

    def _complete(self, rdir, rid, step, **kw):
        R.start_step(rdir, step, self.wf)
        S.write_noop_result(rdir, step, rid, kw.get("outcome"), "x")
        return R.finish_step(rdir, step, self.wf, status="completed", **kw)

    def test_a_run_needs_no_ticket(self):
        """The re-key's whole point: a developer with a prompt and a repo."""
        rid, rdir, doc = self._run()
        self.assertEqual(doc["subject"]["kind"], "prompt")
        self.assertIsNone(doc["subject"].get("ticket_id"))
        self.assertTrue(os.path.isfile(R.run_path(rdir)))

    def test_the_cursor_starts_at_the_first_step(self):
        _rid, _rdir, doc = self._run()
        self.assertEqual(doc["cursor"], "analyze-requirements")

    def test_the_cursor_is_the_first_step_not_completed(self):
        rid, rdir, _doc = self._run()
        doc = self._complete(rdir, rid, "analyze-requirements")
        self.assertEqual(doc["cursor"], "create-impl-plan")

    def test_a_step_absent_from_steps_is_pending(self):
        _rid, _rdir, doc = self._run()
        self.assertEqual(doc["steps"], {})
        self.assertIsNone(R.step_status(doc, "code"))

    def test_two_steps_cannot_be_in_progress_at_once(self):
        """I1. Two steps writing one changeset is how a run loses track of
        which one owns a commit."""
        _rid, rdir, _doc = self._run()
        R.start_step(rdir, "analyze-requirements", self.wf)
        with self.assertRaises(GateError) as caught:
            R.start_step(rdir, "code", self.wf)
        self.assertIn("already in_progress", str(caught.exception))

    def test_an_interrupted_step_must_say_why(self):
        """`handed_off` was a reason wearing a status; this is the distinction
        that replaced it."""
        _rid, rdir, _doc = self._run()
        R.start_step(rdir, "code", self.wf)
        with self.assertRaises(GateError) as caught:
            R.finish_step(rdir, "code", self.wf, status="interrupted")
        self.assertIn("stop_reason", str(caught.exception))
        doc = R.finish_step(rdir, "code", self.wf, status="interrupted",
                            stop_reason="needs_input")
        self.assertEqual(doc["steps"]["code"]["stop_reason"], "needs_input")

    def test_skipped_and_handed_off_are_not_states(self):
        self.assertNotIn("skipped", R.STEP_STATUSES)
        self.assertNotIn("handed_off", R.STEP_STATUSES)

    def test_a_failed_step_fails_the_run(self):
        _rid, rdir, _doc = self._run()
        R.start_step(rdir, "code", self.wf)
        doc = R.finish_step(rdir, "code", self.wf, status="failed")
        self.assertEqual(doc["status"], "failed")

    def test_completing_the_last_step_completes_the_run(self):
        rid, rdir, _doc = self._run()
        for step in W.steps_of(self.wf):
            doc = self._complete(rdir, rid, step)
        self.assertIsNone(doc["cursor"])
        self.assertEqual(doc["status"], "completed")

    def test_only_a_human_abandons_a_run(self):
        _rid, rdir, _doc = self._run()
        doc = R.abandon_run(rdir, "superseded by a different approach")
        self.assertEqual(doc["status"], "abandoned")
        self.assertIn("superseded", doc["abandoned_reason"])


class LoopTest(unittest.TestCase):
    """The one construct a workflow carries, and the only thing that can put
    the cursor backwards."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.repo = os.path.join(self.tmp, "wk", "acme")
        os.makedirs(self.repo)
        self.wf = ship()
        self.rid, self.rdir, _doc = R.create_run(
            self.repo, {"kind": "ticket", "ticket_id": "MAR-1"}, self.wf, SHIP)
        for step in ("analyze-requirements", "create-impl-plan", "create-api-contract",
                     "create-test-docs", "code"):
            R.start_step(self.rdir, step, self.wf)
            S.write_noop_result(self.rdir, step, self.rid, None, "x")
            R.finish_step(self.rdir, step, self.wf, status="completed")

    def _review(self, outcome):
        R.start_step(self.rdir, "review-code", self.wf)
        S.write_noop_result(self.rdir, "review-code", self.rid, outcome, "x")
        return R.finish_step(self.rdir, "review-code", self.wf,
                             status="completed", outcome=outcome)

    def test_blocking_findings_send_the_cursor_back_to_code(self):
        doc = self._review("blocking_findings")
        self.assertEqual(doc["cursor"], "code")
        self.assertEqual(doc["loops"]["review-code"]["iteration"], 2)

    def test_passing_moves_on(self):
        doc = self._review("passed")
        self.assertEqual(doc["cursor"], "create-e2e-tests")

    def test_the_cap_fails_the_run_rather_than_passing_with_findings(self):
        """on_exhausted: fail. A review never waves anything through."""
        for _ in range(2):
            self._review("blocking_findings")
            R.start_step(self.rdir, "code", self.wf)
            S.write_noop_result(self.rdir, "code", self.rid, None, "x")
            R.finish_step(self.rdir, "code", self.wf, status="completed")
        doc = self._review("blocking_findings")
        self.assertEqual(doc["status"], "failed")
        self.assertEqual(doc["steps"]["review-code"]["outcome"], "exhausted")

    def test_code_and_review_share_an_iteration_number(self):
        """steps/code/iter-2/ and steps/review-code/iter-2/ are the same round."""
        self._review("blocking_findings")
        doc = R.load_run(self.rdir)
        self.assertEqual(R.iteration_of(doc, "code", self.wf), 2)
        self.assertEqual(R.iteration_of(doc, "review-code", self.wf), 2)


class InvariantTest(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.repo = os.path.join(self.tmp, "wk", "acme")
        os.makedirs(self.repo)
        self.wf = ship()
        self.rid, self.rdir, _doc = R.create_run(
            self.repo, {"kind": "ticket", "ticket_id": "MAR-2"}, self.wf, SHIP)

    def test_a_clean_run_has_no_errors(self):
        errors, _warnings = R.check(self.rdir, self.wf)
        self.assertEqual(errors, [])

    def test_i3_catches_a_completed_step_with_no_result(self):
        doc = R.require_run(self.rdir)
        doc["steps"]["code"] = {"status": "completed"}
        doc["cursor"] = R.cursor(doc, self.wf)
        R.save_run(self.rdir, doc)
        errors, _warnings = R.check(self.rdir, self.wf)
        self.assertTrue(any("I3" in e for e in errors), errors)

    def test_i5_catches_a_step_that_is_not_in_the_workflow(self):
        doc = R.require_run(self.rdir)
        doc["steps"]["merge-pr"] = {"status": "completed"}
        R.save_run(self.rdir, doc)
        errors, _warnings = R.check(self.rdir, self.wf)
        self.assertTrue(any("I5" in e and "merge-pr" in e for e in errors), errors)

    def test_i5_catches_a_leg_that_is_not_a_leg_of_that_step(self):
        doc = R.require_run(self.rdir)
        doc["steps"]["code"] = {"status": "in_progress", "leg": "create-project"}
        doc["cursor"] = "code"
        R.save_run(self.rdir, doc)
        errors, _warnings = R.check(self.rdir, self.wf)
        self.assertTrue(any("I5" in e and "create-project" in e for e in errors), errors)


class ArtifactLocatorTest(unittest.TestCase):
    """One table maps an artifact NAME (the skills') to a PATH (the run's), so
    a skill never has to know where a run keeps things."""

    def setUp(self):
        self.wf = ship()

    def test_the_plan_lives_under_its_producer(self):
        self.assertEqual(R.artifact_path("/R", "plan", None, self.wf),
                         os.path.join("/R", "steps", "create-impl-plan", "plan.md"))

    def test_requirements_is_promoted_to_the_run_root(self):
        """Step 1's artifact: every later step reads it."""
        self.assertEqual(R.artifact_path("/R", "requirements", None, self.wf),
                         os.path.join("/R", "requirements.md"))

    def test_a_changeset_is_not_a_file(self):
        """The gate asks git about these rather than looking for a path."""
        self.assertIsNone(R.artifact_path("/R", "changeset", None, self.wf))

    def test_missing_reads_names_the_producer(self):
        missing = R.missing_reads("/nowhere", "code", None, self.wf)
        self.assertEqual(missing, [("plan", "create-impl-plan")])


if __name__ == "__main__":
    unittest.main()
