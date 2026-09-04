"""MAR-523: the gate-bearing result fields are computed, not read.

`run_post` trusted `states.verifier_passed`, `states.tests.*`, `states.pr` and
`states.review.iterations` verbatim from a result document the COORDINATOR
wrote. The /acs:create-pr gate therefore checked whether a model had written
`true`, not whether a verifier had passed, and the metrics ledger recorded
whatever number the prose happened to carry.

Each now has a recorded source: the verifier's verdict (MAR-527), the
executors' execute reports, the forge, and the verify artifacts on disk.
Derivation WINS, and a disagreement is recorded rather than silently resolved —
"the document said X and the artifacts said Y" is worth more than either value.
"""

import json
import os
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRIPTS = os.path.join(REPO_ROOT, "plugins", "acs", "hooks", "scripts")
CODE_SKILL = os.path.join(REPO_ROOT, "plugins", "acs", "skills", "code", "SKILL.md")
sys.path.insert(0, SCRIPTS)

import acs_lib as lib  # noqa: E402

sys.path.insert(0, os.path.join(REPO_ROOT, "tests", "acs"))
from acs_case import AcsWorkspaceCase  # noqa: E402


class _Proc(object):
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode, self.stdout, self.stderr = returncode, stdout, stderr


class DeriveCase(AcsWorkspaceCase):

    def setUp(self):
        super().setUp()
        self.ticket = self.new_ticket("Bulk import", "task")
        self.tdir_path = self.tdir(self.ticket)

    def write_execute(self, iteration=1, index=None, tests=None, coverage=None):
        name = ("iter-%d-execute.json" % iteration if index is None
                else "iter-%d-execute-%d.json" % (iteration, index))
        path = os.path.join(self.tdir_path, "phases", "code", name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        doc = {"spec": "01.md"}
        if tests is not None:
            doc["tests"] = tests
        if coverage is not None:
            doc["coverage"] = coverage
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(doc, fh)
        return path

    def write_verify_report(self, iteration=1):
        path = os.path.join(self.tdir_path, "phases", "code", "iter-%d-verify.md" % iteration)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("# verify\n")
        return path


class VerifierPassedTest(DeriveCase):
    """The one derivation that refuses to fall back on the coordinator."""

    def test_a_passing_verdict_derives_true(self):
        self.seed_verdict(self.ticket, passed=True)
        value, why = lib.derive_verifier_passed(self.tdir_path, "code")
        self.assertTrue(value)
        self.assertIn("0 blocking finding", why)

    def test_a_failing_verdict_derives_false(self):
        self.seed_verdict(self.ticket, passed=False)
        value, why = lib.derive_verifier_passed(self.tdir_path, "code")
        self.assertFalse(value)
        self.assertIn("1 blocking finding", why)

    def test_no_verdict_at_all_is_false_and_says_where_it_looked(self):
        """Every other key answers "what happened"; this one answers "may the
        next step run", and the safe answer with no evidence is no."""
        value, why = lib.derive_verifier_passed(self.tdir_path, "code")
        self.assertFalse(value)
        self.assertIn("no verdict.json in", why)
        self.assertIn("phases/code", why)

    def test_a_malformed_verdict_is_false_and_names_the_errors(self):
        lib.write_verdict(self.tdir_path, "code", 1, {
            "skill": "code", "ticket_id": self.ticket, "iteration": 1, "passed": True,
            "dimensions": [{"id": 3, "result": "fail"}],
            "findings": [{"severity": "blocking", "dimension": "coverage", "detail": "86%"}]})
        value, why = lib.derive_verifier_passed(self.tdir_path, "code")
        self.assertFalse(value)
        self.assertIn("not well formed", why)

    def test_the_highest_iteration_is_the_verdict_that_counts(self):
        self.seed_verdict(self.ticket, passed=False, iteration=1)
        self.seed_verdict(self.ticket, passed=True, iteration=2)
        self.assertTrue(lib.derive_verifier_passed(self.tdir_path, "code")[0])
        self.assertEqual(lib.latest_verdict(self.tdir_path, "code")[0], 2)


class TestsAndCoverageTest(DeriveCase):

    def test_numbers_come_from_the_execute_report(self):
        self.write_execute(tests={"passed": 84, "failed": 0},
                           coverage={"percent": 93.4, "target": 90})
        value, why = lib.derive_tests(self.tdir_path, "code", {"test_coverage_percent": 90})
        self.assertEqual(value, {"passed": 84, "failed": 0,
                                 "coverage_percent": 93.4, "coverage_target": 90})
        self.assertIn("iter-1-execute.json", why)

    def test_only_the_last_iterations_reports_count(self):
        """An earlier iteration describes a suite that has since changed."""
        self.write_execute(iteration=1, tests={"passed": 10, "failed": 3})
        self.write_execute(iteration=2, tests={"passed": 84, "failed": 0})
        value, _why = lib.derive_tests(self.tdir_path, "code")
        self.assertEqual((value["passed"], value["failed"]), (84, 0))

    def test_a_suite_that_was_red_for_any_parallel_executor_is_red(self):
        self.write_execute(index=1, tests={"passed": 84, "failed": 0})
        self.write_execute(index=2, tests={"passed": 80, "failed": 2})
        value, _why = lib.derive_tests(self.tdir_path, "code")
        self.assertEqual(value["failed"], 2)

    def test_coverage_target_comes_from_settings_not_from_the_report(self):
        """The target is a setting, so it is never anyone's claim."""
        self.write_execute(coverage={"percent": 91.0, "target": 50})
        value, _why = lib.derive_tests(self.tdir_path, "code", {"test_coverage_percent": 90})
        self.assertEqual(value["coverage_target"], 90)

    def test_no_report_derives_nothing_rather_than_zero(self):
        value, why = lib.derive_tests(self.tdir_path, "code")
        self.assertIsNone(value)
        self.assertIn("no iter-<n>-execute", why)

    def test_a_report_with_no_numbers_derives_nothing(self):
        self.write_execute()
        value, why = lib.derive_tests(self.tdir_path, "code")
        self.assertIsNone(value)
        self.assertIn("record no tests or coverage", why)

    def test_unreadable_reports_are_skipped_not_fatal(self):
        path = os.path.join(self.tdir_path, "phases", "code", "iter-1-execute.json")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("{not json")
        self.write_execute(index=2, tests={"passed": 5, "failed": 0})
        value, _why = lib.derive_tests(self.tdir_path, "code")
        self.assertEqual(value["passed"], 5)


class ReviewIterationsTest(DeriveCase):

    def test_counted_from_the_artifacts_on_disk(self):
        self.write_verify_report(1)
        self.write_verify_report(2)
        self.assertEqual(lib.review_iterations(self.tdir_path, "code"), 2)

    def test_a_verdict_counts_as_a_verify_artifact(self):
        self.seed_verdict(self.ticket, iteration=1)
        self.assertEqual(lib.review_iterations(self.tdir_path, "code"), 1)

    def test_one_iterations_report_and_verdict_count_once(self):
        self.write_verify_report(1)
        self.seed_verdict(self.ticket, iteration=1)
        self.assertEqual(lib.review_iterations(self.tdir_path, "code"), 1)

    def test_nothing_on_disk_is_zero(self):
        self.assertEqual(lib.review_iterations(self.tdir_path, "code"), 0)


class PrFromTheForgeTest(unittest.TestCase):
    """The PR reference is the forge's answer, not the coordinator's."""

    def test_reads_the_pr_gh_reports_for_the_branch(self):
        rows = json.dumps([{"number": 7, "url": "https://example.invalid/pull/7",
                            "headRefName": "task/SHOP-1-x"}])
        value, why = lib.gh_pr_for_branch(
            "task/SHOP-1-x", runner=lambda argv: _Proc(stdout=rows))
        self.assertEqual(value, {"number": 7, "url": "https://example.invalid/pull/7",
                                 "branch": "task/SHOP-1-x"})
        self.assertIn("gh pr list --head", why)

    def test_no_pr_derives_nothing_and_says_so(self):
        value, why = lib.gh_pr_for_branch("b", runner=lambda argv: _Proc(stdout="[]"))
        self.assertIsNone(value)
        self.assertIn("no PR on the forge", why)

    def test_a_missing_gh_leaves_the_reference_unverified_rather_than_wrong(self):
        def missing(argv):
            raise FileNotFoundError("gh")
        value, why = lib.gh_pr_for_branch("b", runner=missing)
        self.assertIsNone(value)
        self.assertIn("gh is not on PATH", why)

    def test_a_failing_gh_call_is_reported_not_swallowed(self):
        value, why = lib.gh_pr_for_branch(
            "b", runner=lambda argv: _Proc(returncode=1, stderr="denied"))
        self.assertIsNone(value)
        self.assertIn("could not be verified", why)

    def test_unparseable_output_derives_nothing(self):
        value, why = lib.gh_pr_for_branch("b", runner=lambda argv: _Proc(stdout="<html>"))
        self.assertIsNone(value)
        self.assertIn("no parseable JSON", why)

    def test_no_branch_is_nothing_to_look_up(self):
        self.assertEqual(lib.gh_pr_for_branch(None)[0], None)


class DisagreementTest(unittest.TestCase):

    def test_only_keys_present_on_both_sides_and_differing_are_reported(self):
        self.assertEqual(
            lib.disagreements({"verifier_passed": True, "branch": "b"},
                              {"verifier_passed": False, "tests": {"passed": 1}}),
            [("verifier_passed", True, False)])

    def test_agreement_is_not_a_disagreement(self):
        self.assertEqual(lib.disagreements({"verifier_passed": True},
                                           {"verifier_passed": True}), [])


class PostHookDerivationTest(DeriveCase):
    """End to end, through the post hook a coordinator actually runs."""

    def setUp(self):
        super().setUp()
        self.assertEqual(self.start("code", self.ticket).returncode, 0)

    def _states(self):
        return lib.load_state(self.tdir_path, "code", self.ticket)["states"]

    def _entry(self):
        return lib.last_run(lib.load_state(self.tdir_path, "code", self.ticket))

    def test_a_claimed_pass_with_no_verdict_is_overwritten_and_logged(self):
        """The acceptance criterion: asserting verifier_passed without a
        passing verdict cannot open the create-pr gate."""
        out = self.post("code", self.ticket,
                        {"status": "completed", "states": {"verifier_passed": True}})
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIs(self._states()["verifier_passed"], False)
        self.assertIn("states.verifier_passed was True", out.stderr)
        self.assertIn("no verdict.json", out.stderr)

        self.start("docs-sync", self.ticket)
        self.post("docs-sync", self.ticket, {"status": "completed"})
        gate = self.pre("create-pr", self.ticket)
        self.assertEqual(gate.returncode, 2)
        self.assertIn("verifier_passed", gate.stderr)

    def test_the_override_is_recorded_on_the_run_entry_not_only_on_stderr(self):
        """stderr scrolls away; the ledger is the record."""
        self.post("code", self.ticket, {"status": "completed",
                                        "states": {"verifier_passed": True}})
        derived = self._entry()["derived_states"]
        self.assertEqual(derived["overrode"],
                         [{"key": "verifier_passed", "supplied": True, "derived": False}])
        self.assertIn("no verdict.json", derived["provenance"]["verifier_passed"])

    def test_a_real_verdict_derives_a_pass_the_coordinator_never_claimed(self):
        self.seed_verdict(self.ticket, passed=True)
        self.post("code", self.ticket, {"status": "completed"})
        self.assertIs(self._states()["verifier_passed"], True)
        self.assertEqual(self._entry()["derived_states"]["overrode"], [])

    def test_test_numbers_come_from_the_report_over_the_prose(self):
        self.seed_verdict(self.ticket)
        self.write_execute(tests={"passed": 84, "failed": 0},
                           coverage={"percent": 93.4, "target": 90})
        out = self.post("code", self.ticket, {
            "status": "completed",
            "states": {"tests": {"passed": 999, "failed": 0,
                                 "coverage_percent": 100.0, "coverage_target": 90}}})
        self.assertEqual(self._states()["tests"]["passed"], 84)
        self.assertIn("states.tests was", out.stderr)

    def test_review_iterations_come_from_the_artifacts(self):
        self.seed_verdict(self.ticket, iteration=1)
        self.seed_verdict(self.ticket, iteration=2)
        self.post("code", self.ticket, {"status": "completed",
                                        "states": {"review": {"iterations": 1, "findings_open": 0}}})
        review = self._states()["review"]
        self.assertEqual(review["iterations"], 2)
        self.assertEqual(review["findings_open"], 0,
                         "a key this module does not own must survive the derivation")

    def test_a_derivation_that_cannot_run_leaves_the_coordinators_value(self):
        """No execute report means no recorded run to read; inventing a number
        would be worse than keeping the one the coordinator wrote."""
        self.seed_verdict(self.ticket)
        supplied = {"passed": 12, "failed": 0, "coverage_percent": 91.0, "coverage_target": 90}
        self.post("code", self.ticket, {"status": "completed", "states": {"tests": supplied}})
        self.assertEqual(self._states()["tests"], supplied)
        self.assertIn("no iter-<n>-execute",
                      self._entry()["derived_states"]["provenance"]["tests"])

    def test_only_code_has_a_verifier_passed_to_derive(self):
        """Other skills' result documents must not acquire the key, and their
        post hooks must not start failing over a verdict they never write."""
        self.assertEqual(lib.VERDICT_SKILLS, ("code",))
        out = self.post("docs-sync", self.ticket, {"status": "completed"})
        self.assertEqual(out.returncode, 0, out.stderr)
        state = lib.load_state(self.tdir_path, "docs-sync", self.ticket)
        self.assertNotIn("verifier_passed", state["states"])


class ProseTest(unittest.TestCase):

    def test_the_skill_no_longer_asks_the_coordinator_to_supply_derived_values(self):
        with open(CODE_SKILL, encoding="utf-8") as fh:
            body = " ".join(fh.read().split())   # markdown wraps; the sentence does not
        self.assertIn("computed by the post-hook from the artifacts", body)
        self.assertIn("You cannot open the /acs:create-pr gate by writing `true`", body)
        for key in ("verifier_passed", "tests", "pr", "review.iterations"):
            self.assertIn(key, body)


if __name__ == "__main__":
    unittest.main()
