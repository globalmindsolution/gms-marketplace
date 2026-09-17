"""/acs:code runs the full unit suite once per iteration, in verify.

A repo's test command is one artifact that usually answers several questions at
once -- did the tests pass, what is the coverage, does it clear the threshold.
This skill used to ask each question as its own numbered step, in both agents,
so each question bought its own run: the executor ran the suite to reach green
and again to measure coverage, the verifier re-ran it for tests and again for
coverage, and resume re-ran it once per implemented spec. On this repo -- 5000+
tests, ~415s per instrumented run -- a three-spec ticket on a full-verify lane
spent roughly fifteen full runs.

It now runs ONCE per iteration, and the verifier owns it. The executors iterate
against the TARGETED set the plan's test strategy names for their file map --
/acs:create-impl-plan answered that question, so /acs:code reads it rather than
re-deriving it. The verifier's single independent run then establishes that the
assembled changeset is green and, from the same output, what the coverage is.

That run goes LAST, after the dimensions answered by reading, and only when
none of them blocks: an iteration already going back to the executor does not
need a suite run to say so, and the tree is about to change anyway. The half
that makes the deferral safe is pinned beside it -- no zero-findings verdict
without a green run on the iteration being passed -- because keeping the saving
while losing that clause would turn this into a way to pass without ever
running the suite.

That is cheaper, but the reason it is also BETTER is worth stating, because it
is what should stop a future reader "optimising" it back: states.tests used to
be the executor's self-report about its own work, and is now the review's
finding about that work, established by an agent that shares no memory with it.
The padded-coverage failure mode the executor charter used to warn about stops
being something a report can even claim.

The e2e suite is split the same way but lands on a different owner, because
workflows/ship.yaml has a dedicated step for it (code -> create-e2e-tests ->
run-e2e-tests) and none for unit. Each suite gets exactly one full-run owner;
the pipeline decides which.

Assertions are by substring over whitespace-normalized text, never by line
number, EXCEPT the derive_tests ones, which drive the real function against
real artifacts on disk -- behaviour beats prose where behaviour is available.
Stdlib-only. Run:  python3 -m unittest tests.acs.test_code_single_suite_run -v
"""

import json
import os
import re
import shutil
import sys
import tempfile
import unittest


REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN = os.path.join(REPO_ROOT, "src", "acs")
CODE_SKILL = os.path.join(PLUGIN, "skills", "code", "SKILL.md")
CODE_EXECUTOR = os.path.join(PLUGIN, "agents", "code-executor.md")
CODE_VERIFIER = os.path.join(PLUGIN, "agents", "code-verifier.md")
VERDICT_SCHEMA = os.path.join(PLUGIN, "schemas", "verdict.schema.json")

sys.path.insert(0, os.path.join(PLUGIN, "hooks", "scripts"))
import acs_lib as lib  # noqa: E402


def norm(path):
    """Collapse whitespace runs so markdown line-wrap cannot break a match."""
    with open(path, encoding="utf-8") as fh:
        return re.sub(r"\s+", " ", fh.read())


class OnlyTheVerifierRunsTheFullUnitSuiteTest(unittest.TestCase):

    def test_executor_is_told_not_to_run_it(self):
        body = norm(CODE_EXECUTOR)
        self.assertIn("**You do not run the full unit suite.**", body)
        self.assertIn("iterating against the TARGETED set", body)

    def test_executor_is_told_why_its_affected_set_matters(self):
        """Removing the safety net without saying so would be a trap: the
        executor needs to know a miss costs a whole extra round, not nothing."""
        self.assertIn("a regression you miss is one the verifier finds, which "
                      "costs a whole extra execute-verify round",
                      norm(CODE_EXECUTOR))

    def test_verifier_knows_its_run_is_the_only_one(self):
        self.assertIn("This is the ONLY full-suite run in a /acs:code iteration",
                      norm(CODE_VERIFIER))

    def test_coordinator_states_the_same_division(self):
        body = norm(CODE_SKILL)
        self.assertIn("**Executors never run the full unit suite.**", body)
        self.assertIn("It runs exactly once per iteration, in verify", body)


class TheTargetedSetComesFromThePlanTest(unittest.TestCase):
    """Which tests the work bears on is a question /acs:create-impl-plan has
    already answered. /acs:code does not plan, so it reads plan.md's test
    strategy rather than re-deriving the scope — and a scope that is declared
    can be reviewed, where one invented per executor cannot."""

    def test_executor_reads_the_scope_from_the_plan(self):
        body = norm(CODE_EXECUTOR)
        self.assertIn("the suites the plan's test strategy names for your file "
                      "map", body)
        self.assertIn("`/acs:create-impl-plan` wrote it — this skill does not "
                      "plan", body)

    def test_coordinator_says_the_same(self):
        self.assertIn("the plan's test strategy names for that executor's file "
                      "map", norm(CODE_SKILL))


class TheSuiteRunsLastAndOnlyOnACleanReadTest(unittest.TestCase):
    """Order, not skipping. An iteration already going back to the executor
    does not need a suite run to say so; the tree is about to change anyway.

    The deferral is only safe because of its other half, so both are pinned
    together: removing the second while keeping the first would turn a saving
    into a way to pass without ever running the suite.
    """

    def test_the_reading_dimensions_are_judged_first(self):
        body = norm(CODE_VERIFIER)
        self.assertIn("**Read before you run.**", body)
        self.assertIn("reach for the suite only once nothing else blocks", body)

    def test_it_is_explicitly_about_order_not_skipping(self):
        self.assertIn("That is a rule about ORDER, never about skipping",
                      norm(CODE_VERIFIER))

    def test_a_pass_is_impossible_without_a_green_run(self):
        self.assertIn("you cannot return a zero-findings verdict without a "
                      "green full-suite run on the iteration you are passing",
                      norm(CODE_VERIFIER))

    def test_a_red_suite_on_clean_looking_code_is_the_point(self):
        """Guards against the deferral decaying into a formality."""
        self.assertIn("a red suite on a changeset that reads perfectly is "
                      "exactly the finding this phase exists to catch",
                      norm(CODE_VERIFIER))

    def test_coverage_is_deferred_with_it_not_separately(self):
        self.assertIn("It comes from the dimension-2 run, so it is deferred "
                      "with it", norm(CODE_VERIFIER))


class CoverageComesOffThatSameRunTest(unittest.TestCase):

    def test_executor_records_no_number_of_its_own(self):
        body = norm(CODE_EXECUTOR)
        self.assertIn("**Coverage is measured by the verifier, not by you.**",
                      body)
        self.assertIn('"coverage": {"percent": null, "target": "measured in verify"}',
                      body)

    def test_executor_still_has_to_write_coverable_tests(self):
        """The target did not stop binding, it is judged one phase later.
        Dropping that would read as permission to stop caring."""
        body = norm(CODE_EXECUTOR)
        self.assertIn("Write tests as if the target still binds, because it does",
                      body)
        self.assertIn("Never pad with meaningless tests", body)

    def test_verifier_takes_it_from_dimension_2_not_a_second_run(self):
        body = norm(CODE_VERIFIER)
        self.assertIn("Take the number from your own dimension-2 run when "
                      "that command reports coverage", body)
        self.assertIn("Measure separately only when the test command reports no "
                      "coverage at all", body)

    def test_verifier_knows_it_is_now_the_only_measurement(self):
        self.assertIn("The executor no longer reports a coverage number — it "
                      "does not run the full suite — so yours is the "
                      "measurement the coverage gate is judged on",
                      norm(CODE_VERIFIER))


class TheVerdictIsTheSourceOfRecordTest(unittest.TestCase):
    """Behavioural, not prose: drive acs_lib.derive_tests over real artifacts.

    The executor no longer produces a coverage number, so states.tests has to
    come from the verifier's verdict. A fallback to the execute reports stays,
    because some runs legitimately have no verifier numbers -- a docs-only
    ticket, a run that ended before any verdict was written, or state written
    by an earlier version of this skill.
    """

    def setUp(self):
        self.tdir = tempfile.mkdtemp(prefix="acs-tests-source-")
        self.addCleanup(shutil.rmtree, self.tdir, True)
        self.phases = os.path.join(self.tdir, "phases", "code")
        os.makedirs(self.phases)

    def _write(self, name, doc):
        with open(os.path.join(self.phases, name), "w", encoding="utf-8") as fh:
            json.dump(doc, fh)

    def _verdict(self, **extra):
        doc = {"skill": "code", "ticket_id": "SHOP-1", "iteration": 1,
               "passed": True, "dimensions": [], "findings": []}
        doc.update(extra)
        return doc

    def test_the_verdicts_numbers_win(self):
        self._write("iter-1-execute.json",
                    {"tests": {"passed": 1, "failed": 0},
                     "coverage": {"percent": 10.0}})
        self._write("iter-1-verdict.json", self._verdict(
            tests={"passed": 84, "failed": 0, "command": "pytest -q"},
            coverage={"percent": 93.4, "command": "pytest --cov"}))
        value, why = lib.derive_tests(self.tdir, "code",
                                      {"test_coverage_percent": 90})
        self.assertEqual(value, {"passed": 84, "failed": 0,
                                 "coverage_percent": 93.4,
                                 "coverage_target": 90})
        self.assertIn("verdict", why,
                      "provenance must name where the numbers came from")

    def test_the_command_is_carried_into_provenance(self):
        """Numbers with no command behind them are not the same evidence."""
        self._write("iter-1-verdict.json", self._verdict(
            tests={"passed": 84, "failed": 0, "command": "pytest -q"}))
        _value, why = lib.derive_tests(self.tdir, "code", {})
        self.assertIn("pytest -q", why)

    def test_it_falls_back_to_execute_reports_when_the_verdict_has_no_numbers(self):
        self._write("iter-1-execute.json",
                    {"tests": {"passed": 12, "failed": 0},
                     "coverage": {"percent": 91.0}})
        self._write("iter-1-verdict.json", self._verdict())
        value, why = lib.derive_tests(self.tdir, "code",
                                      {"test_coverage_percent": 90})
        self.assertEqual(value["passed"], 12)
        self.assertEqual(value["coverage_percent"], 91.0)
        self.assertIn("execute report", why)

    def test_it_falls_back_when_no_verdict_exists_at_all(self):
        """A run can end before any verifier writes one."""
        self._write("iter-1-execute.json", {"tests": {"passed": 5, "failed": 0}})
        value, _why = lib.derive_tests(self.tdir, "code", {})
        self.assertEqual(value["passed"], 5)

    def test_nothing_recorded_anywhere_stays_an_honest_absence(self):
        value, why = lib.derive_tests(self.tdir, "code", {})
        self.assertIsNone(value, "inventing numbers is worse than reporting none")
        self.assertTrue(why)

    def test_the_target_always_comes_from_settings(self):
        """Whoever supplied the measurement, the bar it is judged against is
        the repo's, never a number the artifact claimed for itself."""
        self._write("iter-1-verdict.json", self._verdict(
            tests={"passed": 1, "failed": 0},
            coverage={"percent": 91.0, "target": 50}))
        value, _why = lib.derive_tests(self.tdir, "code",
                                       {"test_coverage_percent": 90})
        self.assertEqual(value["coverage_target"], 90)


class TheVerdictSchemaCarriesThemTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        with open(VERDICT_SCHEMA, encoding="utf-8") as fh:
            cls.schema = json.load(fh)

    def test_tests_and_coverage_are_declared(self):
        props = self.schema["properties"]
        self.assertIn("tests", props)
        self.assertIn("coverage", props)

    def test_they_are_optional(self):
        """A docs-only ticket has no coverage to record, and requiring them
        would make every pre-existing verdict on disk invalid."""
        for key in ("tests", "coverage"):
            with self.subTest(field=key):
                self.assertNotIn(key, self.schema["required"])


class EachSuiteHasOneFullRunOwnerTest(unittest.TestCase):
    """Unit and e2e each get one full-run owner, and they are different owners
    because workflows/ship.yaml has a dedicated e2e step and no unit step."""

    def test_verifier_does_not_run_the_e2e_suite(self):
        body = norm(CODE_VERIFIER)
        self.assertIn("**E2E — you do not run it.**", body)
        self.assertIn("Check the DIFF, not the suite", body)

    def test_verifier_says_why_running_it_there_was_premature(self):
        body = norm(CODE_VERIFIER)
        self.assertIn("code -> create-e2e-tests -> run-e2e-tests", body)
        self.assertIn("/acs:run-e2e-tests", body)

    def test_the_e2e_diff_check_survives_the_removal(self):
        self.assertIn("declared e2e impact must show matching e2e test diffs",
                      norm(CODE_VERIFIER))

    def test_executor_points_full_e2e_at_the_dedicated_skill(self):
        body = norm(CODE_EXECUTOR)
        self.assertIn("the full e2e suite is `/acs:run-e2e-tests`' job", body)
        self.assertNotIn("the full e2e suite is the verifier's job", body)


class NoCrossAgentTrustTest(unittest.TestCase):
    """The guard rail, and the one thing this whole change must not cost.

    Collapsing two runs into one is free. Collapsing the REVIEW into the work
    would not be: the verifier's run is the only reason a coverage number can
    be trusted at all, now that it is the only one taken. If a future change
    has the verifier read the executor's numbers instead of running the suite
    itself, these fail -- which is the point. They pass on both the old and the
    new prose, because a regression guard that discriminated between versions
    would be pinning wording rather than the invariant it protects.
    """

    def test_verifier_still_runs_the_suite_itself(self):
        self.assertIn("run the full suite with the repo's own commands",
                      norm(CODE_VERIFIER))

    def test_verifier_still_trusts_nothing_recorded(self):
        body = norm(CODE_VERIFIER)
        self.assertIn("trust nothing recorded", body)
        self.assertIn("do NOT read the executors'", body)

    def test_the_run_is_stated_to_be_the_verifiers_own(self):
        self.assertIn("the run is YOURS", norm(CODE_VERIFIER))


class GeneralisedNotHardcodedTest(unittest.TestCase):
    """This ships to consumer repos whose suites run in seconds and whose test
    command may report no coverage at all, so the coverage guidance stays a
    conditional rather than an assumption that the two are one command."""

    def test_the_verifier_keeps_a_separate_measurement_available(self):
        self.assertIn("Measure separately only when the test command reports "
                      "no coverage at all", norm(CODE_VERIFIER))


if __name__ == "__main__":
    unittest.main(verbosity=2)
