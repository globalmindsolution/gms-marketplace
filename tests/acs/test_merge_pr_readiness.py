"""MAR-524: merge-pr's readiness decision is a pure function, not prose.

`merge-pr/SKILL.md` described four dimensions and left the model to rebuild a
decision table from `gh pr view --json` every run — so two runs over the same
PR could reach different verdicts and neither would be reviewable.
`acs_lib.readiness.merge_readiness` is that table, and `acs.py readiness` is the
one way a coordinator reaches it.

Every case below is driven from a RECORDED document with no network, which is
the acceptance criterion as much as it is a testing convenience: a verdict that
cannot be reproduced offline cannot be audited after the fact.
"""

import json
import os
import shutil
import sys
import tempfile
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRIPTS = os.path.join(REPO_ROOT, "plugins", "acs", "hooks", "scripts")
sys.path.insert(0, SCRIPTS)

import acs_lib as lib  # noqa: E402

sys.path.insert(0, os.path.join(REPO_ROOT, "tests", "acs"))
from acs_case import AcsWorkspaceCase, fake_gh  # noqa: E402

MERGE_PR_SKILL = os.path.join(REPO_ROOT, "plugins", "acs", "skills", "merge-pr", "SKILL.md")


def check(name, conclusion="SUCCESS", required=True, status="COMPLETED"):
    return {"__typename": "CheckRun", "name": name, "status": status,
            "conclusion": conclusion, "isRequired": required}


def context(name, state="SUCCESS", required=True):
    return {"__typename": "StatusContext", "context": name, "state": state,
            "isRequired": required}


def pr_view(**over):
    """A PR that is ready to merge; each test spoils exactly one thing."""
    doc = {
        "number": 42,
        "state": "OPEN",
        "isDraft": False,
        "mergeable": "MERGEABLE",
        "mergeStateStatus": "CLEAN",
        "reviewDecision": "APPROVED",
        "statusCheckRollup": [check("build"), check("lint")],
        "baseRefName": "main",
        "headRefName": "task/MAR-1-thing",
        "url": "https://github.com/acme/shop/pull/42",
    }
    doc.update(over)
    return doc


class AllClearTest(unittest.TestCase):

    def test_every_dimension_passes_and_the_verdict_is_ready(self):
        out = lib.merge_readiness(pr_view(), True)
        self.assertEqual(out["dimensions"],
                         {"ci": "pass", "approvals": "pass",
                          "conflicts": "pass", "protections": "pass"})
        self.assertEqual(out["verdict"], "ready")
        self.assertTrue(out["ready"])
        self.assertEqual(out["failed"], [])
        self.assertIsNone(out["stop_reason"])

    def test_the_reported_dimensions_are_exactly_the_documented_four(self):
        """A fifth dimension would be a change to merge-pr-state.json's shape,
        not an addition here."""
        self.assertEqual(tuple(lib.merge_readiness(pr_view(), True)["dimensions"]),
                         lib.DIMENSIONS)
        self.assertEqual(lib.DIMENSIONS, ("ci", "approvals", "conflicts", "protections"))


class CiDimensionTest(unittest.TestCase):

    def test_a_failing_required_check_blocks_and_is_named(self):
        out = lib.merge_readiness(pr_view(statusCheckRollup=[check("build", "FAILURE")]), False)
        self.assertEqual(out["dimensions"]["ci"], "fail: required check(s) failing: build")
        self.assertEqual(out["verdict"], "blocked")

    def test_a_pending_required_check_blocks_and_says_so_differently(self):
        """"still running" and "failing" call for different things from the
        user, so they are not collapsed into one message."""
        out = lib.merge_readiness(
            pr_view(statusCheckRollup=[check("build", None, status="IN_PROGRESS")]), None)
        self.assertEqual(out["dimensions"]["ci"], "fail: required check(s) still running: build")

    def test_failing_non_required_checks_are_info_not_blockers(self):
        out = lib.merge_readiness(
            pr_view(statusCheckRollup=[check("build"), check("spell", "FAILURE", required=False)]),
            True)
        self.assertEqual(out["dimensions"]["ci"], "pass")
        self.assertEqual(out["info_findings"], ["non-required check spell is fail"])
        self.assertTrue(out["ready"])

    def test_gh_pr_checks_required_is_a_second_independent_signal(self):
        """A rollup with no `isRequired` anywhere (an older gh, a PR with no
        protection metadata) would otherwise read as "nothing required, all
        clear". The exit code of `gh pr checks --required` covers that."""
        rollup = [check("build", "FAILURE", required=None)]
        self.assertEqual(lib.merge_readiness(pr_view(statusCheckRollup=rollup), None)
                         ["dimensions"]["ci"], "pass")
        self.assertEqual(lib.merge_readiness(pr_view(statusCheckRollup=rollup), False)
                         ["dimensions"]["ci"], "fail: `gh pr checks --required` exited non-zero")

    def test_neutral_and_skipped_conclusions_pass(self):
        for conclusion in ("NEUTRAL", "SKIPPED"):
            with self.subTest(conclusion=conclusion):
                out = lib.merge_readiness(
                    pr_view(statusCheckRollup=[check("build", conclusion)]), True)
                self.assertEqual(out["dimensions"]["ci"], "pass")

    def test_status_contexts_are_read_alongside_check_runs(self):
        out = lib.merge_readiness(
            pr_view(statusCheckRollup=[check("build"), context("legacy-ci", "FAILURE")]), True)
        self.assertEqual(out["dimensions"]["ci"], "fail: required check(s) failing: legacy-ci")

    def test_a_pending_status_context_is_pending_not_failing(self):
        out = lib.merge_readiness(
            pr_view(statusCheckRollup=[context("legacy-ci", "PENDING")]), None)
        self.assertEqual(out["dimensions"]["ci"], "fail: required check(s) still running: legacy-ci")

    def test_an_unreadable_entry_is_pending_never_passing(self):
        """An entry with neither shape must not be counted as green — that is
        the direction that merges on no evidence."""
        self.assertEqual(lib.check_state({"name": "mystery"}), "pending")
        self.assertEqual(lib.check_state({}), "pending")

    def test_non_dict_rollup_entries_are_skipped(self):
        out = lib.merge_readiness(pr_view(statusCheckRollup=[None, "x", check("build")]), True)
        self.assertEqual(out["dimensions"]["ci"], "pass")

    def test_an_absent_rollup_leaves_the_required_exit_code_deciding(self):
        self.assertEqual(lib.merge_readiness(pr_view(statusCheckRollup=None), True)
                         ["dimensions"]["ci"], "pass")
        self.assertEqual(lib.merge_readiness(pr_view(statusCheckRollup=None), False)
                         ["dimensions"]["ci"], "fail: `gh pr checks --required` exited non-zero")

    def test_check_name_falls_back_across_both_shapes(self):
        self.assertEqual(lib.check_name({"name": "a"}), "a")
        self.assertEqual(lib.check_name({"context": "b"}), "b")
        self.assertEqual(lib.check_name({}), "<unnamed check>")


class ApprovalsDimensionTest(unittest.TestCase):
    """ADR-0028: APPROVED for every merge. The three not-approved states are
    reported apart because they call for different things from the user."""

    def test_approved_passes(self):
        self.assertEqual(lib.merge_readiness(pr_view(), True)["dimensions"]["approvals"], "pass")

    def test_changes_requested_names_the_reviewer_action(self):
        out = lib.merge_readiness(pr_view(reviewDecision="CHANGES_REQUESTED"), True)
        self.assertIn("CHANGES_REQUESTED", out["dimensions"]["approvals"])

    def test_review_required_is_distinct_from_changes_requested(self):
        out = lib.merge_readiness(pr_view(reviewDecision="REVIEW_REQUIRED"), True)
        self.assertIn("REVIEW_REQUIRED", out["dimensions"]["approvals"])

    def test_a_repo_requiring_no_review_still_fails_and_cites_the_adr(self):
        """The case that surprises people: an empty reviewDecision means the
        REPO requires no review, and acs requires one anyway."""
        for empty in ("", None):
            with self.subTest(reviewDecision=empty):
                out = lib.merge_readiness(pr_view(reviewDecision=empty), True)
                self.assertIn("ADR-0028", out["dimensions"]["approvals"])
                self.assertFalse(out["ready"])


class ConflictsDimensionTest(unittest.TestCase):

    def test_conflicting_fails(self):
        out = lib.merge_readiness(pr_view(mergeable="CONFLICTING"), True)
        self.assertIn("CONFLICTING", out["dimensions"]["conflicts"])

    def test_dirty_merge_state_fails_even_when_mergeable_still_says_mergeable(self):
        out = lib.merge_readiness(pr_view(mergeStateStatus="DIRTY"), True)
        self.assertIn("DIRTY", out["dimensions"]["conflicts"])

    def test_unknown_mergeability_fails_rather_than_merging_on_no_evidence(self):
        out = lib.merge_readiness(pr_view(mergeable="UNKNOWN"), True)
        self.assertIn("UNKNOWN", out["dimensions"]["conflicts"])
        self.assertIn("re-invoke", out["dimensions"]["conflicts"])
        self.assertFalse(out["ready"])

    def test_an_absent_mergeable_field_fails_and_says_it_was_absent(self):
        out = lib.merge_readiness(pr_view(mergeable=None), True)
        self.assertIn("absent", out["dimensions"]["conflicts"])


class ProtectionsDimensionTest(unittest.TestCase):

    def test_blocked_is_a_flat_fail(self):
        out = lib.merge_readiness(pr_view(mergeStateStatus="BLOCKED"), True)
        self.assertIn("BLOCKED", out["dimensions"]["protections"])
        self.assertEqual(out["verdict"], "blocked")

    def test_a_closed_pr_fails(self):
        out = lib.merge_readiness(pr_view(state="MERGED"), True)
        self.assertEqual(out["dimensions"]["protections"], "fail: PR state is MERGED, not OPEN")

    def test_a_draft_fails(self):
        out = lib.merge_readiness(pr_view(isDraft=True), True)
        self.assertIn("draft", out["dimensions"]["protections"])

    def test_behind_with_everything_else_green_routes_to_the_carve_out(self):
        out = lib.merge_readiness(pr_view(mergeStateStatus="BEHIND"), True)
        self.assertEqual(out["verdict"], "update-branch")
        self.assertTrue(out["behind"])
        self.assertFalse(out["ready"])
        self.assertEqual(out["failed"], [])
        self.assertIsNone(out["stop_reason"])

    def test_behind_with_any_other_failure_is_a_flat_fail(self):
        """The carve-out fires only when ci, approvals and conflicts all pass —
        otherwise updating the branch would not make the PR mergeable."""
        out = lib.merge_readiness(
            pr_view(mergeStateStatus="BEHIND", reviewDecision="REVIEW_REQUIRED"), True)
        self.assertEqual(out["dimensions"]["protections"], "fail: BEHIND")
        self.assertEqual(out["verdict"], "blocked")
        self.assertFalse(out["behind"])
        self.assertEqual(out["failed"], ["approvals", "protections"])


class StopReasonTest(unittest.TestCase):
    """The sentence merge-pr drops into its result document, built once here so
    two runs over the same PR report the same thing."""

    def test_lists_every_failing_dimension_in_report_order(self):
        out = lib.merge_readiness(
            pr_view(statusCheckRollup=[check("build", "FAILURE")],
                    reviewDecision="CHANGES_REQUESTED"), False)
        self.assertEqual(
            out["stop_reason"],
            "readiness failed: ci required check(s) failing: build; "
            "approvals CHANGES_REQUESTED — a reviewer has requested changes")

    def test_is_absent_unless_blocked(self):
        for doc in (pr_view(), pr_view(mergeStateStatus="BEHIND")):
            self.assertIsNone(lib.merge_readiness(doc, True)["stop_reason"])


class ReadinessCliTest(AcsWorkspaceCase):
    """`acs.py readiness`, driven the way a SKILL.md drives it."""

    def setUp(self):
        super().setUp()
        self.bin = tempfile.mkdtemp(prefix="acs-bin-")
        self.addCleanup(shutil.rmtree, self.bin, True)

    def _acs(self, *args, **kw):
        return self.run_script("acs.py", *args, **kw)

    def _record(self, pr, required_ok=True):
        path = os.path.join(self.tmp, "recorded.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump({"pr_view": pr, "required_checks_ok": required_ok}, fh)
        return path

    def test_replays_a_recorded_document_with_no_network(self):
        out = self._acs("readiness", "--from", self._record(pr_view()))
        self.assertEqual(out.returncode, 0, out.stderr)
        body = json.loads(out.stdout)
        self.assertEqual(body["verdict"], "ready")
        self.assertEqual(body["pr"], 42)
        self.assertTrue(body["ok"])

    def test_a_bare_pr_view_document_is_accepted_as_the_recording(self):
        """`gh pr view --json ... > f.json` is what someone will actually
        capture, so a file that IS the pr view works without a wrapper."""
        path = os.path.join(self.tmp, "bare.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(pr_view(reviewDecision="CHANGES_REQUESTED"), fh)
        body = json.loads(self._acs("readiness", "--from", path).stdout)
        self.assertEqual(body["verdict"], "blocked")

    def test_reads_the_recording_from_stdin(self):
        out = self._acs("readiness", "--from", "-",
                        stdin=json.dumps({"pr_view": pr_view(), "required_checks_ok": True}))
        self.assertEqual(json.loads(out.stdout)["verdict"], "ready")

    def test_exit_zero_means_it_ran_not_that_the_pr_is_ready(self):
        out = self._acs("readiness", "--from", self._record(pr_view(state="CLOSED")))
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(json.loads(out.stdout)["verdict"], "blocked")

    def test_refuses_both_inputs_and_neither(self):
        for argv in (("readiness",), ("readiness", "--pr", "1", "--from", "x.json")):
            with self.subTest(argv=argv):
                res = self._acs(*argv)
                self.assertEqual(res.returncode, 2)
                self.assertIn("exactly one of --pr", res.stderr)

    def test_a_recording_without_a_pr_view_object_is_refused(self):
        path = os.path.join(self.tmp, "wrong.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump({"pr_view": "not an object"}, fh)
        res = self._acs("readiness", "--from", path)
        self.assertEqual(res.returncode, 2)
        self.assertIn("no `pr_view` object", res.stderr)

    def test_reads_github_through_gh_when_given_a_pr_number(self):
        env = fake_gh(self.bin, 'if [ "$2" = "checks" ]; then exit 0; fi\n'
                               'cat <<JSON\n%s\nJSON' % json.dumps(pr_view()))
        out = self._acs("readiness", "--pr", "42", env=env)
        self.assertEqual(out.returncode, 0, out.stderr)
        body = json.loads(out.stdout)
        self.assertEqual(body["verdict"], "ready")
        self.assertTrue(body["required_checks_ok"])

    def test_a_red_required_checks_exit_reaches_the_ci_dimension(self):
        env = fake_gh(self.bin, 'if [ "$2" = "checks" ]; then exit 1; fi\n'
                               'cat <<JSON\n%s\nJSON'
                               % json.dumps(pr_view(statusCheckRollup=[])))
        body = json.loads(self._acs("readiness", "--pr", "42", env=env).stdout)
        self.assertEqual(body["required_checks_ok"], False)
        self.assertEqual(body["verdict"], "blocked")

    def test_a_gh_failure_is_the_documented_refusal_with_the_canonical_hint(self):
        env = fake_gh(self.bin, 'echo "gh: something broke" >&2; exit 1')
        res = self._acs("readiness", "--pr", "42", env=env)
        self.assertEqual(res.returncode, 2)
        self.assertIn("something broke", res.stderr)
        self.assertIn(lib.GH_GENERIC_HINT.splitlines()[0], res.stderr)

    def test_a_missing_gh_says_so_rather_than_tracebacking(self):
        env = fake_gh(self.bin, None)
        res = self._acs("readiness", "--pr", "42", env=env)
        self.assertEqual(res.returncode, 2)
        self.assertIn("not found on PATH", res.stderr)
        self.assertNotIn("Traceback", res.stderr)


class SkillProseTest(unittest.TestCase):
    """The other half of the ticket: the prose keeps the judgment and stops
    restating the table."""

    @classmethod
    def setUpClass(cls):
        with open(MERGE_PR_SKILL, encoding="utf-8") as fh:
            cls.body = fh.read()

    def test_step_0_invokes_the_command(self):
        self.assertIn("acs.py\" readiness --pr <number>", self.body)

    def test_the_prose_no_longer_restates_the_decision_table(self):
        """The field-level rules moved into merge_readiness; a copy here is the
        second source of truth the ticket exists to remove.

        `reviewDecision` is `APPROVED` is the one exception and stays: MAR-42
        pins that exact phrase as the greppable form of mitigation m6
        (tests/acs/test_skill_contracts.py::test_merge_pr_is_agent_invocable),
        so removing it would delete an invariant, not a duplication."""
        for restatement in ("`mergeable` is `MERGEABLE`",
                            "`mergeStateStatus` is not `BLOCKED`",
                            "gh pr checks --required` exits 0",
                            "`CONFLICTING` (or",
                            "each as `\"pass\"` or"):
            self.assertNotIn(restatement, self.body, restatement)

    def test_the_judgment_that_is_not_mechanical_stays(self):
        for kept in ("ADR-0028", "G26", "solo maintainer", "REPORT-ONLY",
                     "E2E suite", "known tooling gap"):
            self.assertIn(kept, self.body, kept)

    def test_the_three_verdicts_are_documented_where_the_coordinator_reads_them(self):
        for verdict in lib.VERDICTS:
            self.assertIn("`%s`" % verdict, self.body, verdict)


if __name__ == "__main__":
    unittest.main()
