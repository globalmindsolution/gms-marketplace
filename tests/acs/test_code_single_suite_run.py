"""/acs:code spends one full-suite run where it used to spend several.

A repo's test command is one artifact that usually answers several questions at
once -- did the tests pass, what is the coverage, does it clear the threshold.
This skill used to ask each question as its own numbered step, in both agents,
and a numbered step reads as "run something": the executor ran the suite to go
green and again to measure coverage, the verifier re-ran it for tests and again
for coverage, and the coordinator's resume re-ran it once per implemented spec.
On this repo -- 5088 tests, ~415s per instrumented run -- a three-spec ticket on
a full-verify lane spent around fifteen full runs, of which six were the same
command twice on an unchanged tree.

What is pinned here is the division that fixes it WITHOUT weakening the review:

- within one agent, one run answers everything that run reports;
- across agents, the verifier still establishes its own result and trusts
  nothing the executor recorded.

That second half is the one that must never be "optimized" away. The verifier
IS the changeset review -- it is the reason a padded coverage number gets
caught -- so a future change that has it read the executor's numbers instead of
running the suite itself would gut the phase while looking like a speedup. The
NoCrossAgentTrustTest class below exists to fail loudly if anyone tries.

Every assertion is by file + substring over whitespace-normalized text, never by
line number (line numbers drift as prose is revised). Stdlib-only. Run:
  python3 -m unittest tests.acs.test_code_single_suite_run -v
"""

import os
import re
import unittest


REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN = os.path.join(REPO_ROOT, "src", "acs")
CODE_SKILL = os.path.join(PLUGIN, "skills", "code", "SKILL.md")
CODE_EXECUTOR = os.path.join(PLUGIN, "agents", "code-executor.md")
CODE_VERIFIER = os.path.join(PLUGIN, "agents", "code-verifier.md")


def norm(path):
    """Collapse whitespace runs so markdown line-wrap cannot break a match."""
    with open(path, encoding="utf-8") as fh:
        return re.sub(r"\s+", " ", fh.read())


class CoverageIsReadNotReMeasuredTest(unittest.TestCase):
    """The single biggest saving: coverage falls out of the run you already did.

    Both agents keep a numbered coverage step -- other prose cross-references
    those numbers -- but each now points at its own earlier run before spending
    a second one.
    """

    def test_coordinator_points_step_3_at_step_2s_run(self):
        body = norm(CODE_SKILL)
        self.assertIn("Read step 2's run first", body,
                      "the coordinator's coverage step must send the executor "
                      "to the run it already has")
        self.assertIn("Spend a second run only when the test command genuinely "
                      "produces no coverage number", body)

    def test_executor_reads_its_own_green_run(self):
        body = norm(CODE_EXECUTOR)
        self.assertIn("but read step 2's run first", body)
        self.assertIn("Run the suite a second time only if that output carries "
                      "no coverage figure at all", body)

    def test_verifier_takes_the_number_from_its_own_test_run(self):
        body = norm(CODE_VERIFIER)
        self.assertIn("Take it from your own run in dimension 2 when that "
                      "command reports coverage", body)
        self.assertIn("the run is YOURS", body,
                      "one run, but its provenance still has to be stated -- "
                      "that is what separates this from trusting the executor")
        self.assertIn("Re-measure separately only when the test command reports "
                      "no coverage", body)

    def test_the_pre_fix_phrasings_are_gone(self):
        """Each of these read as an unconditional instruction to run again."""
        stale = [
            (CODE_VERIFIER, "RE-MEASURE with the repo's coverage tooling"),
            (CODE_EXECUTOR, "one instrumented run of the test suite, the same "
                            "measurement the verifier repeats"),
            (CODE_SKILL, "RE-RUN THE TEST SUITE for every spec recorded implemented"),
        ]
        for path, phrase in stale:
            with self.subTest(file=os.path.basename(path)):
                self.assertNotIn(phrase, norm(path),
                                 "%r is the pre-fix wording and instructs a "
                                 "redundant run" % phrase)


class FullUnitSuiteOncePerExecutorTest(unittest.TestCase):
    """The executor's fast loop is the affected tests; the full unit suite is a
    once-per-executor check, not a per-spec or per-edit one.

    "Did the assembled work break anything" has ONE answer per changeset, so an
    executor holding three specs in its file map asks it once, not three times.
    """

    def test_coordinator_scopes_the_iteration_loop_to_affected_tests(self):
        body = norm(CODE_SKILL)
        self.assertIn("Iterate against the tests your change touches", body)
        self.assertIn("runs **once per executor**, after its last spec, not "
                      "once per spec", body)

    def test_executor_says_once_per_executor_and_says_why(self):
        body = norm(CODE_EXECUTOR)
        self.assertIn("Run the full unit suite ONCE, after your LAST spec", body)
        self.assertIn("Once per executor, not once per spec", body)
        self.assertIn("re-running an entire suite after every edit tells you "
                      "nothing the affected tests did not", body)

    def test_resume_runs_the_suite_once_for_every_spec_at_once(self):
        body = norm(CODE_SKILL)
        self.assertIn("Re-run the test suite — once", body)
        self.assertIn("A single full run reports on every spec recorded "
                      "implemented at the same time", body)


class EachSuiteHasOneFullRunOwnerTest(unittest.TestCase):
    """The unit suite and the e2e suite each get run in full by exactly one
    owner, and they are different owners because the pipeline is shaped that
    way.

    `workflows/ship.yaml` has a dedicated e2e step -- code -> create-e2e-tests
    -> run-e2e-tests -- and no dedicated unit step. So the /code verifier is
    the full-run owner for unit, and `/acs:run-e2e-tests` is the owner for e2e.
    The verifier used to run BOTH, which cost the slowest suite in the pipeline
    twice per ticket AND ran it at a point where `create-e2e-tests` had not yet
    written the ticket's e2e tests -- a green result over an incomplete suite.
    """

    def test_verifier_does_not_run_the_e2e_suite(self):
        body = norm(CODE_VERIFIER)
        self.assertIn("**E2E — you do not run it.**", body)
        self.assertIn("Check the DIFF, not the suite", body)

    def test_verifier_says_why_running_it_there_was_premature(self):
        body = norm(CODE_VERIFIER)
        self.assertIn("code -> create-e2e-tests -> run-e2e-tests", body,
                      "the ordering is the reason, and it should be stated")
        self.assertIn("/acs:run-e2e-tests", body)

    def test_the_e2e_diff_check_survives_the_removal(self):
        """Dropping the run must not drop the obligation: a spec that declared
        e2e impact still has to show a matching e2e test change."""
        self.assertIn("declared e2e impact must show matching e2e test diffs",
                      norm(CODE_VERIFIER))

    def test_executor_points_full_e2e_at_the_dedicated_skill(self):
        body = norm(CODE_EXECUTOR)
        self.assertIn("run the AFFECTED e2e tests", body)
        self.assertIn("the full e2e suite is `/acs:run-e2e-tests`' job", body)
        self.assertNotIn("the full e2e suite is the verifier's job", body,
                         "stale ownership: the verifier no longer runs it")

    def test_the_dead_setting_is_named_as_dead_rather_than_left_looking_live(self):
        """`e2e_per_iteration` only ever steered the verifier's e2e run. Leaving
        it undocumented would leave operators tuning a knob wired to nothing."""
        self.assertIn("`e2e_per_iteration` is still accepted and still passed, "
                      "but nothing reads it any more", norm(CODE_SKILL))

class NoCrossAgentTrustTest(unittest.TestCase):
    """The guard rail. Deduplicating WITHIN an agent is free; deduplicating
    ACROSS agents would trade the review's whole basis for wall clock.

    If a future change makes the verifier read the executor's recorded numbers
    rather than establishing its own, these fail -- which is the point.
    """

    def test_verifier_still_runs_the_suite_itself(self):
        """Pre-dates this change and must outlive it, so it passes on both the
        old and new prose -- a regression guard that discriminated between
        versions would be pinning wording, not the invariant."""
        self.assertIn("RE-RUN the full suite yourself with the repo's own "
                      "commands", norm(CODE_VERIFIER))

    def test_verifier_still_trusts_nothing_recorded(self):
        body = norm(CODE_VERIFIER)
        self.assertIn("trust nothing recorded", body)
        self.assertIn("do NOT read the executors'", body,
                      "the verifier must not form its verdict from execute reports")

    def test_the_padded_coverage_brake_survives(self):
        """The executor is deterred from topping up coverage only because the
        verifier independently re-measures. Losing that sentence would remove
        the deterrent along with the duplicate run."""
        self.assertIn("the verifier re-measures from the suite alone and the "
                      "gap is a blocking finding", norm(CODE_EXECUTOR))


class GeneralisedNotHardcodedTest(unittest.TestCase):
    """This skill ships to consumer repos whose suites run in seconds and whose
    test command may report no coverage at all. The guidance has to be phrased
    as a conditional, not as an assumption that the two are always one command.
    """

    def test_each_agent_states_the_condition_rather_than_assuming_it(self):
        for path in (CODE_EXECUTOR, CODE_VERIFIER, CODE_SKILL):
            with self.subTest(file=os.path.basename(path)):
                body = norm(path)
                self.assertTrue(
                    "only if that output carries no coverage figure" in body
                    or "only when the test command reports no coverage" in body
                    or "only when the test command genuinely produces no "
                       "coverage number" in body,
                    "%s must keep a separate measurement available for repos "
                    "whose test command reports no coverage"
                    % os.path.basename(path))


if __name__ == "__main__":
    unittest.main(verbosity=2)
