"""MAR-305 — /acs:create-standards's reflection loop drops the per-iteration
re-plan: the planner now runs exactly once per run, before the loop, and the
loop body is execute -> verify only. Verifier findings on iteration 2+ route
straight to the executor's <context>, with no intervening planner spawn.
Mirrors the structure (never the content) of
tests/acs/test_docs_sync_loop_topology.py, which pins the identical topology
change /acs:docs-sync made in MAR-300 (itself mirroring /acs:code's MAR-71).

Every assertion is by file + substring/regex over whitespace-normalized text,
never by line number (line numbers drift as prose is revised). Stdlib-only
(os, re, unittest). Run:
  python3 -m unittest tests.acs.test_create_standards_loop_topology -v
"""

import os
import re
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN = os.path.join(REPO_ROOT, "plugins", "acs")
STANDARDS_SKILL = os.path.join(PLUGIN, "skills", "create-standards", "SKILL.md")
STANDARDS_PLANNER = os.path.join(PLUGIN, "agents", "create-standards-planner.md")
STANDARDS_EXECUTOR = os.path.join(PLUGIN, "agents", "create-standards-executor.md")
STANDARDS_VERIFIER = os.path.join(PLUGIN, "agents", "create-standards-verifier.md")


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def norm(body):
    """Collapse whitespace runs so markdown line-wrap can never break a
    phrase-spanning match."""
    return re.sub(r"\s+", " ", body)


def section(body, start_heading, end_heading):
    start = body.find(start_heading)
    end = body.find(end_heading, start)
    assert start != -1, "%r heading not found" % start_heading
    assert end != -1, "%r heading not found" % end_heading
    return body[start:end]


class SinglePlannerSpawnPerRunTest(unittest.TestCase):
    """AC-1: a create-standards run that needs 3 iterations spawns exactly
    one acs:create-standards-planner subagent across the whole run."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(STANDARDS_SKILL)
        cls.norm = norm(cls.body)

    def test_reflection_loop_states_exactly_one_planner_spawn_per_run(self):
        for m in re.finditer(r"exactly one", self.norm, re.IGNORECASE):
            window = self.norm[max(0, m.start() - 80):m.end() + 80]
            if "acs:create-standards-planner" in window and re.search(
                    r"(?i)\b(run|whole run)\b", window):
                return
        self.fail(
            "create-standards/SKILL.md must co-locate an 'exactly one' clause "
            "with 'acs:create-standards-planner' and a whole-run qualifier "
            "within ~80 chars")

    def test_plan_list_item_is_not_per_iteration(self):
        self.assertRegex(self.body, r"(?m)^1\. \*\*Plan\*\* \(once[^)]*\)")
        self.assertNotRegex(self.body, r"(?m)^1\. \*\*Plan\*\* —")

    def test_plan_phase_runs_once_before_the_loop(self):
        self.assertRegex(
            self.norm,
            r"(?i)plan.{0,80}once.{0,80}(before the loop|up front|per run)")

    def test_no_unnegated_replan_instruction(self):
        negating = re.compile(r"(?i)never|no |not|without|instead of")
        for m in re.finditer(r"(?i)re-?plan\w*", self.body):
            window = self.body[max(0, m.start() - 60):m.end() + 60]
            self.assertRegex(
                window, negating,
                "un-negated 're-plan' instruction found: %r" % window)

    def test_no_surviving_plan_execute_verify_triad_instruction(self):
        triad_re = re.compile(r"(?i)plan\W{0,4}(->|→)\W{0,4}execute")
        negating = re.compile(r"(?i)never|no |not|without|instead of")

        def assert_all_negated(text, label):
            for m in triad_re.finditer(text):
                window = text[max(0, m.start() - 60):m.end() + 60]
                self.assertRegex(
                    window, negating,
                    "un-negated plan->execute sequence in %s: %r" % (label, window))

        loop_window = section(self.norm, "## Reflection loop", "## Delivery (branch, commit, PR)")
        assert_all_negated(loop_window, "the reflection-loop section")
        # file-wide, so any occurrence outside the loop window is covered too.
        assert_all_negated(self.norm, "the file as a whole")

    def test_resume_reuses_the_existing_plan_artifact_without_a_second_planner(self):
        window = section(self.norm, "## Resume & reconcile", "## Inputs & mode")
        self.assertIn("iter-1-plan.md", window)
        self.assertRegex(window, r"(?i)(never|no|without).{0,40}second planner")


class FindingsRouteStraightToExecutorTest(unittest.TestCase):
    """AC-2: verifier findings on iteration 2+ are delivered to the
    executor's <context>, with no intervening planner spawn."""

    def test_findings_feed_the_executor_context_with_no_planner_in_between(self):
        body_norm = norm(read(STANDARDS_SKILL))
        no_planner_re = re.compile(r"(?i)(no|never|without)\W{0,20}planner")
        for m in re.finditer(r"(?i)findings", body_norm):
            window = body_norm[max(0, m.start() - 300):m.end() + 300]
            if ("executor" in window.lower() and "<context>" in window
                    and no_planner_re.search(window)):
                return
        self.fail(
            "create-standards/SKILL.md must co-locate 'findings', 'executor', "
            "'<context>' and a no-planner clause within ~300 chars")

    def test_executor_input_contract_carries_iteration_2plus_findings(self):
        body_norm = norm(read(STANDARDS_EXECUTOR))
        self.assertIn(
            "on iteration >= 2, a `<context>` carrying the prior iteration's "
            "verifier findings verbatim",
            body_norm)
        self.assertIn("no planner spawn happens in between", body_norm)

    def test_executor_charter_still_requires_fixing_every_listed_finding(self):
        body_norm = norm(read(STANDARDS_EXECUTOR))
        self.assertIn(
            "On iteration >= 2, fix every finding listed in `<context>`",
            body_norm)


class IterationCapUnchangedTest(unittest.TestCase):
    """AC-3: the iteration cap (max 3) and verify-depth selection are
    unchanged."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(STANDARDS_SKILL)
        cls.norm = norm(cls.body)

    def test_cap_is_still_max_three_iterations(self):
        self.assertIn("max 3 iterations", self.norm)
        self.assertIn("After iteration 3", self.norm)

    def test_iteration_is_defined_as_an_execute_verify_round(self):
        window = section(self.norm, "## Reflection loop", "## Delivery (branch, commit, PR)")
        self.assertRegex(window, r"(?i)execute\s*(→|->|\+|and)\s*verify")
        self.assertRegex(
            window,
            r"(?i)not.{0,80}(triad|plan\W{0,4}execute\W{0,4}verify)")

    def test_no_lane_driven_verify_depth_machinery_introduced(self):
        for token in ("verify_depth", "VERIFY_ITERATION_CAP", "TRIVIAL", "COMPLEX"):
            self.assertNotIn(token, self.body)


class PlannerRoleStillWiredTest(unittest.TestCase):
    """AC-6: this test guards against over-deletion of the planner/verifier
    roles and the plan-artifact naming."""

    def test_skill_still_references_planner_and_verifier(self):
        body = read(STANDARDS_SKILL)
        self.assertIn("acs:create-standards-planner", body)
        self.assertIn("acs:create-standards-verifier", body)
        self.assertIn("iter-1-plan.md", body)


class VerifierIndependenceUnchangedTest(unittest.TestCase):
    """AC-4: the verifier's independent, artifact-only judgment behavior is
    unchanged (still never trusts the execute report, and still
    independently re-derives every upstream-fact citation itself via
    citation_check.py). The verifier agent file is NOT edited by this
    ticket; these are read-only regression assertions."""

    def test_skill_verify_phase_keeps_corroboration_clause(self):
        body_norm = norm(read(STANDARDS_SKILL))
        self.assertIn(
            "the plan was followed exactly, including independent "
            "corroboration of every upstream-fact citation in its "
            "Upstream inventory",
            body_norm)

    def test_verifier_agent_still_refuses_to_trust_the_execute_report(self):
        body = read(STANDARDS_VERIFIER)
        body_norm = norm(body)
        self.assertIn(
            "you NEVER rubber-stamp: re-run every cheap check yourself "
            "instead of trusting what the execute report claims",
            body_norm)
        self.assertIn(
            "Independently re-open and check every upstream-fact citation "
            "the planner recorded",
            body_norm)
        self.assertIn("citation_check.py", body)


class PlannerNoLongerPromisedFindingsTest(unittest.TestCase):
    """create-standards-planner.md's prose no longer promises the planner
    iteration >= 2 verifier findings, since after this change the planner is
    never re-spawned to receive them."""

    def test_planner_no_longer_promised_prior_iteration_findings(self):
        body_norm = norm(read(STANDARDS_PLANNER))
        self.assertNotRegex(
            body_norm,
            r"(?i)iteration\s*>\s*1:?.{0,6}<context>.{0,6}\s*carries verifier findings")
        self.assertNotIn("prior-iteration verifier findings", body_norm)
        self.assertRegex(body_norm, r"(?i)spawned exactly once per run")


if __name__ == "__main__":
    unittest.main()
