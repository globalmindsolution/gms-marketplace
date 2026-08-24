"""MAR-301 — /acs:create-project's reflection loop drops the per-iteration
re-plan: the planner now runs exactly once per run, before the loop, and the
loop body is execute -> verify only. Verifier findings on iteration 2+ route
straight to the executor's <context>, with no intervening planner spawn.
Mirrors the structure (never the content) of
tests/acs/test_docs_sync_loop_topology.py, which pins the identical topology
change /acs:docs-sync made in MAR-300 (itself mirroring /acs:code's MAR-71).

Every assertion is by file + substring/regex over whitespace-normalized text,
never by line number (line numbers drift as prose is revised). Stdlib-only
(os, re, unittest). Run:
  python3 -m unittest tests.acs.test_create_project_loop_topology -v
"""

import os
import re
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN = os.path.join(REPO_ROOT, "plugins", "acs")
CP_SKILL = os.path.join(PLUGIN, "skills", "create-project", "SKILL.md")
CP_PLANNER = os.path.join(PLUGIN, "agents", "create-project-planner.md")
CP_EXECUTOR = os.path.join(PLUGIN, "agents", "create-project-executor.md")
CP_VERIFIER = os.path.join(PLUGIN, "agents", "create-project-verifier.md")


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
    """AC-1: a create-project run that needs 3 iterations spawns exactly one
    acs:create-project-planner subagent across the whole run."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(CP_SKILL)
        cls.norm = norm(cls.body)

    def test_reflection_loop_states_exactly_one_planner_spawn_per_run(self):
        for m in re.finditer(r"exactly one", self.norm, re.IGNORECASE):
            window = self.norm[max(0, m.start() - 80):m.end() + 80]
            if "acs:create-project-planner" in window and re.search(
                    r"(?i)\b(run|whole run)\b", window):
                return
        self.fail(
            "create-project/SKILL.md must co-locate an 'exactly one' clause "
            "with 'acs:create-project-planner' and a whole-run qualifier "
            "within ~80 chars")

    def test_plan_section_heading_is_not_per_iteration(self):
        self.assertRegex(self.body, r"(?m)^### Plan \(once[^)]*\)$")
        self.assertNotRegex(self.body, r"(?m)^### Plan$")

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
        triad_re = re.compile(r"plan\W{0,4}(->|→)\W{0,4}execute")
        negating = re.compile(r"(?i)never|no |not|without|instead of")

        def assert_all_negated(text, label):
            for m in triad_re.finditer(text):
                window = text[max(0, m.start() - 60):m.end() + 60]
                self.assertRegex(
                    window, negating,
                    "un-negated plan->execute sequence in %s: %r" % (label, window))

        loop_window = section(self.norm, "## Reflection loop", "## Delivery")
        assert_all_negated(loop_window, "the reflection-loop section")
        # file-wide, so the CI-proof clause (outside the loop window, under
        # "## Delivery") is covered too.
        assert_all_negated(self.norm, "the file as a whole")

    def test_resume_reuses_the_existing_plan_artifact_without_a_second_planner(self):
        window = section(self.norm, "## Resume & reconcile", "## Greenfield gate")
        self.assertIn("iter-1-plan.md", window)
        self.assertRegex(window, r"(?i)(never|no|without).{0,40}second planner")


class FindingsRouteStraightToExecutorTest(unittest.TestCase):
    """AC-2: verifier findings on iteration 2+ are delivered to the
    executor's <context>, with no intervening planner spawn."""

    def test_findings_feed_the_executor_context_with_no_planner_in_between(self):
        body_norm = norm(read(CP_SKILL))
        no_planner_re = re.compile(r"(?i)(no|never|without)\W{0,20}planner")
        for m in re.finditer(r"(?i)findings", body_norm):
            window = body_norm[max(0, m.start() - 300):m.end() + 300]
            if ("executor" in window.lower() and "<context>" in window
                    and no_planner_re.search(window)):
                return
        self.fail(
            "create-project/SKILL.md must co-locate 'findings', 'executor', "
            "'<context>' and a no-planner clause within ~300 chars")

    def test_ci_proof_remediation_is_execute_verify_only(self):
        body_norm = norm(read(CP_SKILL))
        idx = body_norm.find("If CI fails")
        self.assertNotEqual(idx, -1, "'If CI fails' clause not found")
        window = body_norm[max(0, idx - 100):idx + 300]
        self.assertRegex(window, r"(?i)execute\s*(->|→|\+|and)\s*verify")
        triad_re = re.compile(r"(?i)plan\W{0,4}(->|→)")
        for m in triad_re.finditer(window):
            self.fail(
                "un-negated plan-> sequence survives in the CI-proof "
                "clause: %r" % window[max(0, m.start() - 20):m.end() + 20])


class ExecutorAndPlannerContractAlignmentTest(unittest.TestCase):
    """T1c (Q1 answered 'extend scope'): the sibling agent contracts are
    realigned with the new routing so no live contradiction with AC-2
    survives in create-project-executor.md / create-project-planner.md."""

    def test_executor_input_contract_carries_iteration_2plus_findings(self):
        body_norm = norm(read(CP_EXECUTOR))
        self.assertIn(
            "on iteration >= 2, the verifier findings your scaffold must fix",
            body_norm)
        self.assertIn("<context>", body_norm)
        self.assertIn(
            "On iteration >= 2, fix every finding listed in the task's "
            "`<context>`", body_norm)

    def test_planner_is_no_longer_promised_verifier_findings(self):
        body_norm = norm(read(CP_PLANNER))
        self.assertNotRegex(
            body_norm,
            r"(?i)treat each prior finding as the top of the agenda")
        self.assertNotIn("the previous `iter-<n>-verify.md`", body_norm)


class IterationCapUnchangedTest(unittest.TestCase):
    """AC-3: the iteration cap (max 3) and verify-depth selection are
    unchanged."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(CP_SKILL)
        cls.norm = norm(cls.body)

    def test_cap_is_still_at_most_three_iterations(self):
        self.assertIn("at most 3 iterations", self.norm)
        self.assertIn("After iteration 3", self.norm)

    def test_iteration_is_defined_as_an_execute_verify_round(self):
        window = section(self.norm, "## Reflection loop", "## Delivery")
        self.assertRegex(window, r"(?i)execute\s*(→|->|\+|and)\s*verify")
        self.assertRegex(
            window,
            r"(?i)not.{0,80}(triad|plan\W{0,4}execute\W{0,4}verify)")

    def test_no_lane_driven_verify_depth_machinery_introduced(self):
        for token in ("verify_depth", "VERIFY_ITERATION_CAP", "TRIVIAL", "COMPLEX"):
            self.assertNotIn(token, self.body)


class PlannerRoleStillWiredTest(unittest.TestCase):
    """AC-4: the test suite asserts single-planner-spawn behavior and the
    existing create-project test suite passes; this test guards against
    over-deletion of the planner/verifier roles."""

    def test_skill_still_references_planner_and_verifier(self):
        body = read(CP_SKILL)
        self.assertIn("acs:create-project-planner", body)
        self.assertIn("acs:create-project-verifier", body)

    def test_plan_artifact_name_is_consistent_with_the_planner_contract(self):
        body = read(CP_SKILL)
        self.assertIn("iter-1-plan.md", body)
        self.assertNotIn("scaffold-plan.md", body)


class VerifierIndependenceUnchangedTest(unittest.TestCase):
    """AC-5: the verifier's independent build/lint/test/coverage re-run
    behavior is unchanged."""

    def test_skill_verify_phase_keeps_independent_command_rerun_clauses(self):
        body_norm = norm(read(CP_SKILL))
        self.assertIn(
            "The verifier MUST actually run, from `<checkout_root>`, the "
            "exact commands the plan pinned, and see them pass", body_norm)
        self.assertIn(
            "A scaffold that does not run green FAILS verification", body_norm)

    def test_verifier_agent_still_refuses_to_trust_the_execute_report(self):
        body = read(CP_VERIFIER)
        body_norm = norm(body)
        self.assertIn("Never rubber-stamp", body)
        self.assertIn(
            "never accept the execute report's word for a command you can "
            "run yourself", body_norm)

    def test_verifier_dimension_list_is_intact(self):
        body = read(CP_VERIFIER)
        for token in ("build", "lint", "tests", "coverage-tooling",
                      "vertical-slice", "layout", "tech-stack", "ci",
                      "pre-commit", "repo-hygiene", "plan-conformance"):
            self.assertIn(token, body)


if __name__ == "__main__":
    unittest.main()
