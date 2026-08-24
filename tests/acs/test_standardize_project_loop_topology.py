"""MAR-302 -- /acs:standardize-project's reflection loop drops the
per-iteration re-plan: the planner now runs exactly once per run, before the
loop, and the loop body is execute -> verify only. Unlike MAR-300/301, this
skill's primary safety control (dimension 1, additive-only diff-status) is
judged against an allowlist the planner itself writes into prose, so the
iteration-1 plan is FROZEN as the allowlist for the whole run: iteration 2+
verifier findings route straight to the executor's <context>, and a
plan-conformance-class finding naming a path outside the frozen allowlist
degrades to severity="info" + recommended_follow_ups instead of silently
widening the executor's writable surface (the D2-c split). Mirrors the
structure (never the content) of
tests/acs/test_create_project_loop_topology.py, which pins the analogous
MAR-301 topology change for the fully-independent-verifier case.

Every assertion is by file + substring/regex over whitespace-normalized text,
never by line number (line numbers drift as prose is revised). Stdlib-only
(os, re, unittest). Run:
  python3 -m unittest tests.acs.test_standardize_project_loop_topology -v
"""

import os
import re
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN = os.path.join(REPO_ROOT, "plugins", "acs")
SP_SKILL = os.path.join(PLUGIN, "skills", "standardize-project", "SKILL.md")
SP_PLANNER = os.path.join(PLUGIN, "agents", "standardize-project-planner.md")
SP_EXECUTOR = os.path.join(PLUGIN, "agents", "standardize-project-executor.md")
SP_VERIFIER = os.path.join(PLUGIN, "agents", "standardize-project-verifier.md")
ACS_LIB = os.path.join(PLUGIN, "hooks", "scripts", "acs_lib.py")


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
    """AC-2: a standardize-project run that needs 2 or 3 iterations spawns
    exactly one acs:standardize-project-planner subagent across the whole
    run."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(SP_SKILL)
        cls.norm = norm(cls.body)

    def test_reflection_loop_states_exactly_one_planner_spawn_per_run(self):
        for m in re.finditer(r"exactly one", self.norm, re.IGNORECASE):
            window = self.norm[max(0, m.start() - 80):m.end() + 80]
            if "acs:standardize-project-planner" in window and re.search(
                    r"(?i)\b(run|whole run)\b", window):
                return
        self.fail(
            "standardize-project/SKILL.md must co-locate an 'exactly one' "
            "clause with 'acs:standardize-project-planner' and a whole-run "
            "qualifier within ~80 chars")

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

        loop_window = section(self.norm, "## Reflection loop", "## Delivery")
        assert_all_negated(loop_window, "the reflection-loop section")
        # file-wide, so any un-negated sequence outside the loop window is
        # covered too.
        assert_all_negated(self.norm, "the file as a whole")

    def test_resume_reuses_the_frozen_plan_without_a_second_planner(self):
        window = section(self.norm, "## Resume & reconcile", "## Brownfield orientation")
        self.assertIn("iter-1-plan.md", window)
        self.assertRegex(window, r"(?i)(never|no|without).{0,40}second planner")


class FindingsRouteStraightToExecutorTest(unittest.TestCase):
    """AC-4/D4: verifier findings on iteration 2+ are delivered to the
    executor's <context>, with no intervening planner spawn."""

    def test_findings_feed_the_executor_context_with_no_planner_in_between(self):
        body_norm = norm(read(SP_SKILL))
        no_planner_re = re.compile(r"(?i)(no|never|without)\W{0,20}planner")
        for m in re.finditer(r"(?i)findings", body_norm):
            window = body_norm[max(0, m.start() - 300):m.end() + 300]
            if ("executor" in window.lower() and "<context>" in window
                    and no_planner_re.search(window)):
                return
        self.fail(
            "standardize-project/SKILL.md must co-locate 'findings', "
            "'executor', '<context>' and a no-planner clause within ~300 chars")

    def test_executor_input_contract_carries_iteration_2plus_findings(self):
        body_norm = norm(read(SP_EXECUTOR))
        self.assertIn("<context>", body_norm)
        self.assertIn("iteration >= 2", body_norm)
        self.assertIn("NOT executable", body_norm)
        self.assertIn("report it, never scaffold it", body_norm)


class AdditiveOnlyGuaranteeUnchangedTest(unittest.TestCase):
    """AC-3 (verbatim): the verifier's additive-only diff-status enforcement
    (reject R/D/out-of-allowlist M) is unchanged and independently re-run
    every iteration."""

    def test_verifier_dimension_one_tokens_survive(self):
        body = read(SP_VERIFIER)
        for token in ("diff --name-status", "every iteration", "re-run",
                      "never trust", "`R`", "`D`", "out-of-allowlist",
                      "classify_additive_diff"):
            self.assertIn(token, body, "missing dimension-1 token %r" % token)

    def test_all_five_dimension_names_survive(self):
        body = read(SP_VERIFIER)
        for token in ("additive-only", "doc-set-authorship",
                      "recommended-follow-ups-only", "plan-conformance",
                      "completion-report"):
            self.assertIn(token, body, "missing dimension name %r" % token)

    def test_classify_additive_diff_signature_unchanged(self):
        body = read(ACS_LIB)
        self.assertIn(
            "def classify_additive_diff(diff_output, allowlist_globs):", body)


class FrozenAllowlistTest(unittest.TestCase):
    """AC-2/AC-4, D1-A/D3-a: the iteration-1 plan (and its Additive-surface
    allowlist) is the frozen, literal-path plan source for the whole run."""

    def test_verifier_reads_the_literal_frozen_plan_path(self):
        body_norm = norm(read(SP_VERIFIER))
        contract_window = section(body_norm, "## Input contract", "## Check dimensions")
        self.assertIn("iter-1-plan.md", contract_window)
        self.assertNotIn("iter-<n>-plan.md", contract_window)
        dim1_window = section(
            body_norm, "1. **additive-only diff-status**",
            "2. **doc-set-authorship")
        self.assertNotIn("iter-<n>-plan.md", dim1_window)

    def test_additive_surface_contract_states_frozen_and_monotonic(self):
        body_norm = norm(read(SP_SKILL))
        window = section(body_norm, "## Additive-surface contract", "## Reflection loop")
        self.assertIn("frozen", window.lower())
        self.assertIn("authoritative for the whole run", window)
        self.assertIn("monotonically non-increasing", window)

    def test_planner_no_longer_carries_iteration_gt1_replan_duty(self):
        body_norm = norm(read(SP_PLANNER))
        self.assertNotIn(
            "Iteration > 1: <context> carries verifier findings", body_norm)
        self.assertRegex(body_norm, r"(?i)spawned exactly once per run")


class VerdictSplitByDimensionTest(unittest.TestCase):
    """AC-4/D2-c: additive-only and doc-set-authorship findings ALWAYS
    block; only a missing-scaffold plan-conformance finding outside the
    frozen allowlist and absent from the diff degrades to a non-blocking
    recommended_follow_ups entry, evaluated fail-closed."""

    def test_never_degradable_dimensions_named(self):
        body_norm = norm(read(SP_VERIFIER))
        for m in re.finditer(r"(?i)never.?degradable", body_norm):
            window = body_norm[max(0, m.start() - 50):m.end() + 400]
            if ("additive-only" in window and "doc-set-authorship" in window
                    and "no unplanned extra scaffold file" in window):
                return
        self.fail(
            "verifier must name additive-only, doc-set-authorship, and "
            "'no unplanned extra scaffold file' as never-degradable")

    def test_degradable_case_restricted_and_fail_closed(self):
        body_norm = norm(read(SP_VERIFIER))
        self.assertRegex(body_norm, r"(?i)missing-scaffold\s*/\s*under-coverage")
        self.assertRegex(body_norm, r"(?i)fail-closed")
        self.assertRegex(
            body_norm, r"(?i)undetermined.{0,80}(blocking|stays blocking)")

    def test_degraded_verdict_uses_legal_schema_severity_info(self):
        body = read(SP_VERIFIER)
        self.assertIn('severity="info"', body)
        self.assertIn("recommended_follow_ups", body)
        for m in re.finditer(r'severity="(\w+)"', body):
            self.assertIn(m.group(1), ("blocking", "info"),
                          "unschemable severity value %r" % m.group(1))

    def test_four_condition_conjunction_present(self):
        body_norm = norm(read(SP_VERIFIER))
        self.assertRegex(body_norm, r"(?i)all four")
        self.assertIn('dimension="plan-conformance"', body_norm)
        self.assertRegex(body_norm, r"(?i)outside.{0,40}frozen.{0,40}allowlist")
        self.assertRegex(body_norm, r"(?i)absent from this iteration.{0,30}diff")


class RoleWiringNotOverDeletedTest(unittest.TestCase):
    """R5 guard/AC-5: the planner/verifier roles and the iteration cap
    survive the topology rewrite -- this only removes the per-iteration
    re-plan, never the roles or the cap."""

    def test_skill_still_references_planner_verifier_and_frozen_plan(self):
        body = read(SP_SKILL)
        self.assertIn("acs:standardize-project-planner", body)
        self.assertIn("acs:standardize-project-verifier", body)
        self.assertIn("iter-1-plan.md", body)

    def test_max_three_cap_survives_no_lane_machinery(self):
        body = read(SP_SKILL)
        body_norm = norm(body)
        self.assertIn("at most 3 iterations", body_norm)
        self.assertIn("After iteration 3", body_norm)
        for token in ("verify_depth", "VERIFY_ITERATION_CAP", "TRIVIAL", "COMPLEX"):
            self.assertNotIn(token, body)


class DesignDecisionTraceableTest(unittest.TestCase):
    """AC-1 proxy: the in-repo prose durably records that the freeze bounds,
    but does not close, the residual trust gap, and names the mechanically
    derived allowlist as the future closure (design.md D1 Option C)."""

    def test_freeze_bounds_not_closes_trust_gap(self):
        body_norm = norm(read(SP_SKILL))
        window = section(body_norm, "## Additive-surface contract", "## Reflection loop")
        self.assertIn("bounds, and does not close, the trust gap", window)
        self.assertIn("mechanically derived allowlist", window)


if __name__ == "__main__":
    unittest.main()
