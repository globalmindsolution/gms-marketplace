"""MAR-71 (slice 1b of MAR-69) — /acs:code's reflection loop drops the
per-iteration re-plan: the planner now runs exactly once per run, before the
loop, and the loop body is execute -> verify only. Verifier findings on
iteration 2+ route straight to the executor's <context>, with no intervening
planner spawn. Mid-flight escalation's detection point and monotone-ceiling
guarantee are unaffected and are pinned here as regressions.

Every assertion is by file + substring/regex over whitespace-normalized text,
never by line number (line numbers drift as prose is revised). Stdlib-only
(os, re, unittest). Run:
  python3 -m unittest tests.acs.test_code_loop_topology -v
"""

import os
import re
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN = os.path.join(REPO_ROOT, "plugins", "acs")
CODE_SKILL = os.path.join(PLUGIN, "skills", "code", "SKILL.md")
CODE_PLANNER = os.path.join(PLUGIN, "agents", "code-planner.md")
CODE_EXECUTOR = os.path.join(PLUGIN, "agents", "code-executor.md")


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def norm(body):
    """Collapse whitespace runs so markdown line-wrap can never break a
    phrase-spanning match."""
    return re.sub(r"\s+", " ", body)


def section(body, start_heading, end_heading):
    return body[body.index(start_heading):body.index(end_heading)]


class SinglePlannerSpawnPerRunTest(unittest.TestCase):
    """AC-1: exactly one acs:code-planner spawn across the whole run."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(CODE_SKILL)
        cls.norm = norm(cls.body)

    def test_reflection_loop_states_exactly_one_planner_spawn_per_run(self):
        for m in re.finditer(r"exactly one", self.norm, re.IGNORECASE):
            window = self.norm[max(0, m.start() - 80):m.end() + 80]
            if "acs:code-planner" in window and re.search(
                    r"(?i)\b(run|whole run)\b", window):
                return
        self.fail(
            "code/SKILL.md must co-locate an 'exactly one' clause with "
            "'acs:code-planner' and a whole-run qualifier within ~80 chars")

    def test_plan_section_heading_is_not_per_iteration(self):
        self.assertNotIn("### Plan (per iteration)", self.body)
        self.assertRegex(self.body, r"(?m)^### Plan \(once[^)]*\)$")

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


class FindingsRouteStraightToExecutorTest(unittest.TestCase):
    """AC-2: verifier findings on iteration 2+ go straight to the executor's
    <context>, with no intervening planner spawn."""

    def test_findings_feed_the_executor_context_with_no_planner_in_between(self):
        body_norm = norm(read(CODE_SKILL))
        no_planner_re = re.compile(r"(?i)(no|never|without)\W{0,20}planner")
        for m in re.finditer(r"(?i)findings", body_norm):
            window = body_norm[max(0, m.start() - 300):m.end() + 300]
            if ("executor" in window.lower() and "<context>" in window
                    and no_planner_re.search(window)):
                return
        self.fail(
            "code/SKILL.md must co-locate 'findings', 'executor', "
            "'<context>' and a no-planner clause within ~300 chars")

    def test_executor_input_contract_still_carries_iteration_2plus_findings(self):
        body_norm = norm(read(CODE_EXECUTOR))
        self.assertIn(
            "on iteration 2+ the verifier findings assigned to you", body_norm)
        self.assertIn("<context>", body_norm)

    def test_planner_is_no_longer_promised_verifier_findings(self):
        body_norm = norm(read(CODE_PLANNER))
        self.assertNotRegex(
            body_norm, r"(?i)verifier findings from the previous iteration")
        self.assertNotIn("## Findings remediation", read(CODE_PLANNER))


class IterationCapCountsExecuteVerifyRoundsTest(unittest.TestCase):
    """AC-2/AC-4: the verify-depth section defines an iteration as one
    execute -> verify round, not a plan+execute+verify triad; cap values
    (light 1 / full 3) are unchanged."""

    @classmethod
    def setUpClass(cls):
        body = read(CODE_SKILL)
        cls.window = section(
            body, "### Verify-depth", "### In-loop escalation check")
        cls.window_norm = norm(cls.window)

    def test_verify_depth_section_defines_an_iteration_as_an_execute_verify_round(self):
        self.assertRegex(self.window_norm, r"(?i)execute\s*(->|→|\+|and)\s*verify")
        self.assertRegex(self.window_norm, r"(?i)round|iteration")
        self.assertRegex(
            self.window_norm,
            r"(?i)not.{0,60}(triad|plan\W{0,4}execute\W{0,4}verify)")

    def test_cap_values_unchanged_light_one_full_three(self):
        self.assertIn("ceiling = **1** iteration", self.window)
        self.assertIn("ceiling = **3** iterations", self.window)


class EscalationDetectionPointUnchangedTest(unittest.TestCase):
    """AC-3: mid-flight escalation's detection point and monotone-ceiling
    guarantee are unaffected by this ticket (regression pins)."""

    @classmethod
    def setUpClass(cls):
        cls.body_norm = norm(read(CODE_SKILL))

    def test_detection_point_stays_after_prior_verifier_and_before_current_execute(self):
        self.assertIn(
            "after the verifier for the previous iteration has run and "
            "before launching the current iteration's execute phase",
            self.body_norm)

    def test_ceiling_raise_is_monotone(self):
        self.assertIn(
            "monotone raise only, never lower an already-higher ceiling",
            self.body_norm)
        self.assertIn("max(current_ceiling, new_ceiling)", self.body_norm)


class ExecutorScopeEscapeHatchTest(unittest.TestCase):
    """AC-2 corollary: the executor's out-of-map escape hatch no longer
    promises a coordinator re-plan."""

    def test_out_of_map_escape_hatch_does_not_promise_a_replan(self):
        body_norm = norm(read(CODE_EXECUTOR))
        self.assertNotRegex(body_norm, r"(?i)coordinator\s+re-?plans")
        self.assertRegex(
            body_norm,
            r"(?i)coordinator.{0,60}(adjusts|updates).{0,40}(file map|scope)")


if __name__ == "__main__":
    unittest.main()
