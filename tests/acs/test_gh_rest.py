"""acs_lib.gh_rest: REST answers reshaped into the `gh pr view --json` document (ADR-0149).

Every reader is driven from a recorded runner, so these prove the reshaping
-- the part readiness and the fixtures depend on -- with no forge.
"""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "plugins", "acs", "hooks", "scripts"))

from acs_lib import gh_rest  # noqa: E402
from acs_lib.readiness import merge_readiness  # noqa: E402


def runner(answers):
    """A gh runner answering by endpoint substring; records every argv."""
    def gh(argv):
        gh.calls.append(argv)
        endpoint = argv[2]
        for needle, answer in answers:
            if needle in endpoint:
                return answer
        return 1, "", "unexpected endpoint %s" % endpoint
    gh.calls = []
    return gh


def lines(rows):
    return "\n".join(json.dumps(r) for r in rows)


PULL = {"number": 7, "state": "open", "draft": False, "mergeable": True,
        "mergeable_state": "clean", "html_url": "https://github.com/a/b/pull/7",
        "head": {"ref": "task/X-1", "sha": "abc"}, "base": {"ref": "main"},
        "labels": [{"name": "ACS"}]}


def forge(pull=None, reviews=None, required=("build",), runs=None, statuses=()):
    return runner([
        ("/reviews", (0, lines(reviews if reviews is not None else
                               [{"state": "APPROVED", "user": {"login": "r"}}]), "")),
        ("/pulls/7", (0, json.dumps(dict(PULL, **(pull or {}))), "")),
        ("/branches/", (0, json.dumps({"protection": {"required_status_checks": {
            "contexts": list(required)}}}), "")),
        ("/check-runs", (0, lines(runs if runs is not None else [
            {"name": "build", "status": "completed", "conclusion": "success"}]), "")),
        ("/status", (0, json.dumps({"statuses": list(statuses)}), "")),
    ])


class ViewPrTest(unittest.TestCase):

    def test_a_ready_pr_reads_as_the_porcelain_document(self):
        doc = gh_rest.view_pr(forge(), 7)
        self.assertEqual(doc["state"], "OPEN")
        self.assertEqual(doc["mergeable"], "MERGEABLE")
        self.assertEqual(doc["mergeStateStatus"], "CLEAN")
        self.assertEqual(doc["reviewDecision"], "APPROVED")
        self.assertEqual(doc["headRefName"], "task/X-1")
        self.assertEqual(doc["labels"], [{"name": "ACS"}])
        self.assertEqual(doc["statusCheckRollup"][0]["isRequired"], True)
        self.assertEqual(merge_readiness(doc, gh_rest.required_checks(doc))["verdict"],
                         "ready")

    def test_every_call_is_rest(self):
        gh = forge()
        gh_rest.view_pr(gh, 7)
        self.assertTrue(all(argv[:2] == ["gh", "api"] for argv in gh.calls))
        self.assertTrue(all("graphql" not in argv[2] for argv in gh.calls))

    def test_a_merged_pr_and_a_conflict_keep_their_enum_spellings(self):
        doc = gh_rest.view_pr(forge(pull={"state": "closed", "merged_at": "2026-10-01",
                                          "mergeable": False, "mergeable_state": "dirty"}), 7)
        self.assertEqual((doc["state"], doc["mergeable"], doc["mergeStateStatus"]),
                         ("MERGED", "CONFLICTING", "DIRTY"))

    def test_unknown_mergeability_is_not_a_pass(self):
        doc = gh_rest.view_pr(forge(pull={"mergeable": None}), 7)
        self.assertEqual(doc["mergeable"], "UNKNOWN")

    def test_the_short_read_stops_at_the_pull(self):
        gh = forge()
        doc = gh_rest.view_pr(gh, 7, full=False)
        self.assertEqual(len(gh.calls), 1)
        self.assertNotIn("reviewDecision", doc)

    def test_a_read_that_does_not_answer_raises_with_ghs_words(self):
        gh = runner([("/pulls/7", (1, "", "HTTP 403: nope"))])
        with self.assertRaises(gh_rest.GhError) as caught:
            gh_rest.view_pr(gh, 7)
        self.assertIn("HTTP 403", caught.exception.detail)

    def test_statuses_join_the_rollup(self):
        doc = gh_rest.view_pr(forge(required=("ci/legacy",), runs=[],
                                    statuses=[{"context": "ci/legacy", "state": "pending"}]), 7)
        self.assertEqual(doc["statusCheckRollup"],
                         [{"context": "ci/legacy", "state": "PENDING", "isRequired": True}])


class ReviewDecisionTest(unittest.TestCase):

    def test_a_standing_change_request_outweighs_an_approval(self):
        self.assertEqual(gh_rest.review_decision([
            {"state": "APPROVED", "user": {"login": "a"}},
            {"state": "CHANGES_REQUESTED", "user": {"login": "b"}}]), "CHANGES_REQUESTED")

    def test_a_reviewers_latest_deciding_review_counts(self):
        self.assertEqual(gh_rest.review_decision([
            {"state": "CHANGES_REQUESTED", "user": {"login": "a"}},
            {"state": "COMMENTED", "user": {"login": "a"}},
            {"state": "APPROVED", "user": {"login": "a"}}]), "APPROVED")

    def test_a_dismissed_review_stands_for_nothing(self):
        self.assertEqual(gh_rest.review_decision([
            {"state": "APPROVED", "user": {"login": "a"}},
            {"state": "DISMISSED", "user": {"login": "a"}}]), "REVIEW_REQUIRED")


class RequiredChecksTest(unittest.TestCase):

    def doc(self, required, rollup):
        return {"baseRefName": "main", "requiredContexts": required,
                "statusCheckRollup": rollup}

    def test_nothing_required_reads_as_the_no_required_marker(self):
        ok, detail = gh_rest.required_checks(self.doc([], []))
        self.assertFalse(ok)
        self.assertIn("no required checks reported on the", detail)

    def test_a_required_check_that_never_ran_is_named(self):
        ok, detail = gh_rest.required_checks(self.doc(["build"], []))
        self.assertFalse(ok)
        self.assertIn("not reported: build", detail)

    def test_a_red_required_check_is_named(self):
        ok, detail = gh_rest.required_checks(self.doc(["build"], [
            {"name": "build", "status": "COMPLETED", "conclusion": "FAILURE"}]))
        self.assertFalse(ok)
        self.assertIn("not green: build", detail)


class WritesTest(unittest.TestCase):

    def test_reviewers_split_users_from_team_slugs(self):
        argv = gh_rest.request_reviewers(3, ["@alice", "@org/team"])
        self.assertIn("reviewers[]=alice", argv)
        self.assertIn("team_reviewers[]=team", argv)

    def test_a_branch_with_a_slash_survives_the_query(self):
        self.assertIn("head={owner}:release/v1.0.0&", gh_rest.pr_list("release/v1.0.0")[2])

    def test_list_prs_reports_the_porcelain_rows(self):
        gh = runner([("/pulls?", (0, json.dumps([PULL]), ""))])
        self.assertEqual(gh_rest.list_prs(gh, "task/X-1")[0]["url"],
                         "https://github.com/a/b/pull/7")

    def test_find_milestone_matches_by_title(self):
        gh = runner([("/milestones", (0, lines([{"title": "Q3", "number": 4}]), ""))])
        self.assertEqual(gh_rest.find_milestone(gh, "Q3"), 4)
        self.assertIsNone(gh_rest.find_milestone(gh, "Q4"))

    def test_the_default_runner_reports_a_missing_binary(self):
        code, _out, err = gh_rest.run(["gh-definitely-not-installed-acs"])
        self.assertEqual((code, err), (127, gh_rest.NOT_ON_PATH))


if __name__ == "__main__":
    unittest.main()
