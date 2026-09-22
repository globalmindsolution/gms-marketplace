"""The full unit suite runs once per iteration, in the review's final gate.

A repo's test command is one artifact that usually answers several questions at
once — did the tests pass, what is the coverage, does it clear the threshold.
The pipeline used to ask each question as its own numbered step, in both `code`
agents, so each question bought its own run: the executor ran the suite to
reach green and again to measure coverage, the verifier re-ran it for tests and
again for coverage, and resume re-ran it once per implemented spec. On this
repo — 5000+ tests, ~415s per instrumented run — a three-spec ticket spent
roughly fifteen full runs.

It now runs ONCE per iteration and `/acs:review-code`'s **final gate** owns it.
`/acs:code`'s executors iterate against the TARGETED set the plan's test
strategy names for their file map — `/acs:create-impl-plan` answered that
question, so `/acs:code` reads it rather than re-deriving it. The gate's single
independent run then establishes that the assembled changeset is green and,
from the same output, what the coverage is.

That run goes LAST, after stage 2 leaves nothing blocking: an iteration already
going back to `/acs:code` does not need a suite run to say so, and the tree is
about to change anyway. The half that makes the deferral safe is pinned beside
it — the gate is unconditional and terminal, so a verdict that passes has a
green run behind it — because keeping the saving while losing that clause would
turn this into a way to pass without ever running the suite.

**What moving the run out of `/acs:code` bought, beyond the saving.** The run
used to sit inside an iteration that might be discarded, and `states.tests` was
the implementer's self-report about its own work. It is now the review's
finding about that work, established after the changeset is assembled, by an
agent that shares no memory with the one that wrote it. The padded-coverage
failure mode the executor charter warned about stops being something a report
can even claim.

The e2e suite is split the same way but lands on a different owner, because
`workflows/ship.yaml` has a dedicated step for it (`create-e2e-tests` →
`run-e2e-tests`) and none for unit. Each suite gets exactly one full-run owner;
the pipeline decides which.

Assertions are by substring over whitespace-normalized text, never by line
number, EXCEPT the `derive_tests` ones, which drive the real function against
real artifacts on disk — behaviour beats prose where behaviour is available.
Stdlib-only. Run:  python3 -m unittest tests.acs.test_single_suite_run -v
"""

import json
import os
import re
import shutil
import sys
import tempfile
import unittest


REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN = os.path.join(REPO_ROOT, "plugins", "acs")
#: The execute instruction the four delivery paths share (ADR-0095).
CODE_EXECUTE = os.path.join(PLUGIN, "skills", "code", "references", "execute.md")
CODE_SKILL = os.path.join(PLUGIN, "skills", "code", "SKILL.md")
CODE_EXECUTOR = os.path.join(PLUGIN, "agents", "code-executor.md")
REVIEW_SKILL = os.path.join(PLUGIN, "skills", "review-code", "SKILL.md")
REVIEW_LENS = os.path.join(PLUGIN, "agents", "review-code-lens.md")
VERDICT_SCHEMA = os.path.join(PLUGIN, "schemas", "verdict.schema.json")

sys.path.insert(0, os.path.join(PLUGIN, "hooks", "scripts"))
import acs_lib as lib  # noqa: E402
from acs_lib import verdict as V  # noqa: E402


def norm(path):
    """Collapse whitespace runs so markdown line-wrap cannot break a match."""
    with open(path, encoding="utf-8") as fh:
        return re.sub(r"\s+", " ", fh.read())


class OnlyTheGateRunsTheFullUnitSuiteTest(unittest.TestCase):

    def test_executor_is_told_not_to_run_it(self):
        body = norm(CODE_EXECUTOR)
        self.assertIn("**You do not run the full unit suite.**", body)
        self.assertIn("iterating against the TARGETED set", body)

    def test_the_code_dispatcher_states_the_same_division(self):
        body = norm(CODE_SKILL)
        self.assertIn("**Never run the full test suite.**", body)
        self.assertIn("Targeted tests only", body)

    def test_the_review_says_its_gate_is_the_only_full_run(self):
        body = norm(REVIEW_SKILL)
        self.assertIn("This is the only place the full suite runs in the whole "
                      "pipeline", body)

    def test_the_lenses_run_nothing_at_all(self):
        """Five lenses each running the suite would undo the saving five times
        over. They read; the coordinator's gate runs."""
        body = norm(REVIEW_LENS)
        self.assertIn("You run nothing", body)
        self.assertIn("The gate runs those once, later, in the coordinator", body)

    def test_the_legs_point_at_the_gate_rather_than_running_it(self):
        for leg in ("code-trivial", "code-small", "code-standard", "code-complex"):
            body = norm(os.path.join(PLUGIN, "skills", leg, "SKILL.md"))
            with self.subTest(leg=leg):
                self.assertIn("Run the tests your change touches, not the full "
                              "suite", body)


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


class TheGateRunsLastAndOnlyOnACleanReadTest(unittest.TestCase):
    """Order, not skipping. An iteration already going back to /acs:code does
    not need a suite run to say so; the tree is about to change anyway.

    The deferral is only safe because of its other half, so both are pinned
    together: removing the second while keeping the first would turn a saving
    into a way to pass without ever running the suite.
    """

    def test_the_gate_runs_only_on_a_clean_adjudication(self):
        body = norm(REVIEW_SKILL)
        self.assertIn("Runs **only** when stage 2 leaves nothing blocking", body)

    def test_it_runs_exactly_once_per_surviving_iteration(self):
        self.assertIn("It runs last, exactly once per iteration that survives "
                      "review", norm(REVIEW_SKILL))

    def test_a_gate_failure_re_enters_the_loop_as_a_finding(self):
        """The alternative — a separate failure channel — is how a gate result
        ends up outside the trail the next iteration reads."""
        body = norm(REVIEW_SKILL)
        self.assertIn("A gate failure is a blocking finding of `kind: gate` "
                      "with the failing command as its evidence", body)
        self.assertIn("does not skip the loop", body)

    def test_the_gate_kind_is_a_real_finding_kind(self):
        """Behavioural: the vocabulary the prose promises is the one the
        validator enforces."""
        self.assertIn("gate", lib.FINDING_KINDS)

    def test_the_four_checks_are_named(self):
        body = norm(REVIEW_SKILL)
        for check in ("build", "lint", "full unit test suite",
                      "settings.test_coverage_percent"):
            with self.subTest(check=check):
                self.assertIn(check, body)


class TheVerdictIsTheSourceOfRecordTest(unittest.TestCase):
    """Behavioural, not prose: drive acs_lib.derive_tests over real artifacts.

    /acs:code produces no coverage number, so states.tests has to come from the
    review's verdict. A fallback to the execute reports stays, because some runs
    legitimately have no review numbers — a docs-only subject, or a run that
    ended before any verdict was written.
    """

    def setUp(self):
        self.rdir = tempfile.mkdtemp(prefix="acs-tests-source-")
        self.addCleanup(shutil.rmtree, self.rdir, True)

    def _execute(self, doc, skill="code", iteration=1):
        directory = lib.iteration_dir(self.rdir, skill, iteration)
        os.makedirs(directory, exist_ok=True)
        with open(os.path.join(directory, "execute.json"), "w", encoding="utf-8") as fh:
            json.dump(doc, fh)

    def _verdict(self, iteration=1, **extra):
        doc = {"skill": "review-code", "run_id": "SHOP-1", "iteration": iteration,
               "reviewed_sha": "9c1e4a2", "passed": True, "findings": []}
        doc.update(extra)
        V.write_verdict(self.rdir, "review-code", iteration, doc)

    def test_the_verdicts_numbers_win(self):
        self._execute({"tests": {"passed": 1, "failed": 0},
                       "coverage": {"percent": 10.0}})
        self._verdict(tests={"passed": 84, "failed": 0, "command": "pytest -q"},
                      coverage={"percent": 93.4, "command": "pytest --cov"})
        value, why = lib.derive_tests(self.rdir, "review-code",
                                      {"test_coverage_percent": 90})
        self.assertEqual(value, {"passed": 84, "failed": 0,
                                 "coverage_percent": 93.4,
                                 "coverage_target": 90})
        self.assertIn("verdict", why,
                      "provenance must name where the numbers came from")

    def test_the_command_is_carried_into_provenance(self):
        """Numbers with no command behind them are not the same evidence."""
        self._verdict(tests={"passed": 84, "failed": 0, "command": "pytest -q"})
        _value, why = lib.derive_tests(self.rdir, "review-code", {})
        self.assertIn("pytest -q", why)

    def test_it_falls_back_to_execute_reports_when_the_verdict_has_no_numbers(self):
        self._execute({"tests": {"passed": 12, "failed": 0},
                       "coverage": {"percent": 91.0}}, skill="review-code")
        self._verdict()
        value, why = lib.derive_tests(self.rdir, "review-code",
                                      {"test_coverage_percent": 90})
        self.assertEqual(value["passed"], 12)
        self.assertEqual(value["coverage_percent"], 91.0)
        self.assertIn("execute report", why)

    def test_it_falls_back_when_no_verdict_exists_at_all(self):
        """A run can end before any review writes one."""
        self._execute({"tests": {"passed": 5, "failed": 0}}, skill="review-code")
        value, _why = lib.derive_tests(self.rdir, "review-code", {})
        self.assertEqual(value["passed"], 5)

    def test_nothing_recorded_anywhere_stays_an_honest_absence(self):
        value, why = lib.derive_tests(self.rdir, "review-code", {})
        self.assertIsNone(value, "inventing numbers is worse than reporting none")
        self.assertTrue(why)

    def test_the_target_always_comes_from_settings(self):
        """Whoever supplied the measurement, the bar it is judged against is
        the repo's, never a number the artifact claimed for itself."""
        self._verdict(tests={"passed": 1, "failed": 0},
                      coverage={"percent": 91.0, "target": 50})
        value, _why = lib.derive_tests(self.rdir, "review-code",
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
        """A docs-only subject has no coverage to record, and requiring them
        would make every verdict written before the gate ran invalid."""
        for key in ("tests", "coverage"):
            with self.subTest(field=key):
                self.assertNotIn(key, self.schema["required"])

    def test_the_tests_block_names_the_gate_as_its_source(self):
        """A reader who finds numbers here must be able to tell WHO ran them:
        that provenance is the whole reason the figure can be trusted."""
        self.assertIn("gate", self.schema["properties"]["tests"]["description"])


class EachSuiteHasOneFullRunOwnerTest(unittest.TestCase):
    """Unit and e2e each get one full-run owner, and they are different owners
    because workflows/ship.yaml has a dedicated e2e step and no unit step."""

    def test_the_review_does_not_run_the_e2e_suite(self):
        body = norm(REVIEW_SKILL)
        self.assertIn("full unit test suite", body)
        self.assertNotIn("full e2e suite", body)

    def test_executor_points_full_e2e_at_the_dedicated_skill(self):
        body = norm(CODE_EXECUTOR)
        self.assertIn("the full e2e suite is `/acs:run-e2e-tests`' job", body)
        self.assertNotIn("the full e2e suite is the verifier's job", body)

    def test_the_e2e_step_is_in_the_workflow_and_the_unit_run_is_not(self):
        """Behavioural: the reason the owners differ is the workflow's shape,
        so read the workflow rather than asserting the reason as prose."""
        wf = lib.validate_workflow_file(
            os.path.join(PLUGIN, "workflows", "ship.yaml"))
        steps = lib.steps_of(wf)
        self.assertIn("run-e2e-tests", steps)
        self.assertNotIn("run-unit-tests", steps)
        self.assertLess(steps.index("review-code"), steps.index("run-e2e-tests"))


class NoCrossAgentTrustTest(unittest.TestCase):
    """The guard rail, and the one thing this whole change must not cost.

    Collapsing several runs into one is free. Collapsing the REVIEW into the
    work would not be: the gate's run is the only reason a coverage number can
    be trusted at all, now that it is the only one taken. If a future change
    has the review read the implementer's numbers instead of running the suite
    itself, these fail — which is the point.
    """

    def test_the_review_runs_the_gate_itself(self):
        self.assertIn("Run all four yourself", norm(REVIEW_SKILL))

    def test_the_review_records_the_commands_and_their_output(self):
        self.assertIn("record the commands and their output in "
                      "`iter-<n>/gate.json`", norm(REVIEW_SKILL))

    def test_the_conclusion_is_derived_not_asserted(self):
        """The other half of the same guard: the reviewer may not write its own
        pass any more than the implementer could."""
        self.assertIn("`passed` is **not yours to assert**", norm(REVIEW_SKILL))

    def test_the_kernel_actually_derives_it(self):
        """Behavioural: `review-code` is the skill whose verdict the post-hook
        computes `verifier_passed` from, and `code` is not."""
        self.assertIn("review-code", lib.VERDICT_SKILLS)
        self.assertNotIn("code", lib.VERDICT_SKILLS)


class GeneralisedNotHardcodedTest(unittest.TestCase):
    """This ships to consumer repos whose suites run in seconds and whose test
    command may report no coverage at all, so the coverage target is read from
    settings rather than assumed."""

    def test_the_target_comes_from_settings(self):
        self.assertIn("settings.test_coverage_percent", norm(REVIEW_SKILL))

    def test_the_schema_says_the_target_is_not_the_verdicts_to_choose(self):
        description = self.__class__._coverage_description()
        self.assertIn("settings.test_coverage_percent", description)
        self.assertIn("never from here", description)

    @staticmethod
    def _coverage_description():
        with open(VERDICT_SCHEMA, encoding="utf-8") as fh:
            return json.load(fh)["properties"]["coverage"]["description"]


if __name__ == "__main__":
    unittest.main(verbosity=2)
