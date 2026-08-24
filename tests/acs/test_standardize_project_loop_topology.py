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
(os, re, unittest). Iteration 2 adds the coordinator-side half of the
approval gate: what happens when the executor refuses an out-of-frozen-
allowlist finding by returning a `failed` result, so that refusal is
observable (routed to `recommended_follow_ups`) rather than dead-ending as
an undifferentiated run failure. Run:
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


def raw_section(body, start_heading, end_heading):
    """Line-anchored window over the RAW (un-normalized) file text, so
    markdown heading levels remain observable."""
    start = re.search(r"(?m)^" + re.escape(start_heading) + r"\s*$", body)
    end = re.search(r"(?m)^" + re.escape(end_heading) + r"\s*$", body)
    assert start is not None, "%r heading not found" % start_heading
    assert end is not None, "%r heading not found" % end_heading
    return body[start.start():end.start()]


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


class ExecutorFailedResultRoutingTest(unittest.TestCase):
    """AC-4 (F1 remediation): an executor `failed` result raised for an
    out-of-frozen-allowlist finding is routed to `recommended_follow_ups`
    rather than dead-ending as a generic run failure, fail-closed for
    every other `failed` result."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(SP_SKILL)
        cls.norm = norm(cls.body)
        cls.window = section(cls.norm, "## Reflection loop", "## Delivery")

    def test_executor_failed_colocates_with_recommended_follow_ups(self):
        for m in re.finditer(r'status="failed"', self.window):
            near = self.window[max(0, m.start() - 500):m.end() + 500]
            if "executor" in near.lower() and "recommended_follow_ups" in near:
                return
        self.fail(
            "reflection-loop window must co-locate an executor "
            "'status=\"failed\"' result with 'recommended_follow_ups' "
            "within ~500 normalized chars")

    def test_names_out_of_frozen_allowlist_trigger(self):
        self.assertRegex(
            self.window,
            r"(?i)(outside.{0,60}frozen.{0,40}allowlist|out-of-frozen-allowlist)")

    def test_states_not_a_run_failure(self):
        self.assertRegex(self.window, r"(?i)is not a run failure")

    def test_fail_closed_default_for_every_other_failed_result(self):
        self.assertIn("remains a genuine run failure", self.window)
        self.assertIn("never silently converted", self.window)

    def test_never_redispatched_and_never_widens_allowlist(self):
        self.assertRegex(self.window, r"(?i)never\s+re-?dispatch")
        self.assertIn("never widen the frozen allowlist", self.window)

    def test_both_sinks_present_and_cap_three_survives(self):
        self.assertIn('severity="info"', self.window)
        self.assertIn("recommended_follow_ups", self.window)
        self.assertRegex(
            self.window,
            r"(?i)executor.{0,300}failed|failed.{0,300}executor")
        for m in re.finditer(r"After iteration 3", self.window):
            near = self.window[max(0, m.start() - 60):m.end() + 60]
            if re.search(r"(?i)failed", near):
                return
        self.fail(
            "the terminal iteration-cap-3 rule must still co-locate "
            "'After iteration 3' with 'failed'")


class ReflectionLoopHeadingStructureTest(unittest.TestCase):
    """F1 (iteration-3 remediation): the '## Reflection loop' section carries
    either zero H3 sub-headings or a full Plan/Execute/Verify triad of them
    -- never a single orphan H3 whose scope runs unterminated to the end of
    the section."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(SP_SKILL)
        cls.window = raw_section(cls.body, "## Reflection loop", "## Delivery")

    def test_reflection_loop_h3_headings_are_balanced(self):
        headings = re.findall(r"(?m)^###\s+(.+?)\s*$", self.window)
        if not headings:
            return
        self.assertGreaterEqual(
            len(headings), 3,
            "a lone %r heading leaves the Execute and Verify phases reading "
            "as its sub-content" % (headings[0],))
        joined = " ".join(headings).lower()
        for phase in ("plan", "execute", "verify"):
            self.assertIn(
                phase, joined,
                "a lone %r heading leaves the Execute and Verify phases "
                "reading as its sub-content" % (headings[0],))

    def test_reflection_loop_phase_list_names_all_three_phases(self):
        self.assertRegex(self.window, r"(?m)^1\.\s+\*\*Plan\*\*")
        self.assertRegex(self.window, r"(?m)^2\.\s+\*\*Execute\*\*")
        self.assertRegex(self.window, r"(?m)^3\.\s+\*\*Verify\*\*")


class ExecutorFailedConversionScopeTest(unittest.TestCase):
    """F2 (iteration-3 remediation): the executor-failed ->
    recommended_follow_ups conversion clause is scoped to the same
    degradable plan-conformance/missing-scaffold class the verifier's own
    four-condition route uses -- never a blanket conversion keyed only on
    the executor's stated reason."""

    @classmethod
    def setUpClass(cls):
        cls.window = section(norm(read(SP_SKILL)), "## Reflection loop", "## Delivery")

    def test_conversion_scoped_to_degradable_plan_conformance_class(self):
        self.assertIn("Convert ONLY when", self.window)
        self.assertIn('dimension="plan-conformance"', self.window)
        self.assertRegex(self.window, r"(?i)missing-scaffold\s*/\s*under-coverage")

    def test_over_scaffold_refusal_never_convertible(self):
        self.assertRegex(self.window, r"(?i)never the over-scaffold")
        self.assertIn("unplanned extra scaffold file", self.window)

    def test_never_convertible_dimensions_enumerated(self):
        self.assertRegex(self.window, r"(?i)NEVER convertible")
        for token in ("additive-only", "doc-set-authorship",
                      "recommended-follow-ups-only", "completion-report-shape"):
            self.assertIn(token, self.window, "missing never-convertible token %r" % token)

    def test_class_judged_from_verifier_finding_not_executor_self_report(self):
        self.assertRegex(self.window, r"(?i)verifier'?s own prior")
        self.assertRegex(self.window, r"(?i)never from the executor.{0,3}s self-report")

    def test_conversion_is_fail_closed(self):
        self.assertRegex(self.window, r"(?i)fail closed")
        self.assertRegex(self.window, r"(?i)undetermined")

    def test_scoping_colocated_with_the_failed_trigger(self):
        found_any = False
        for m in re.finditer(r'status="failed"', self.window):
            found_any = True
            near = self.window[m.start():m.end() + 900]
            if "Convert ONLY when" in near:
                continue
            self.fail(
                "'Convert ONLY when' scoping text must occur within ~900 "
                "normalized chars after %r" % (self.window[m.start():m.end()],))
        self.assertTrue(found_any, "no status=\"failed\" trigger found in the window")

    def test_executor_defers_conversion_decision_to_the_scoped_coordinator_rule(self):
        body_norm = norm(read(SP_EXECUTOR))
        self.assertRegex(
            body_norm,
            r"recommended_follow_ups.{0,160}degradable plan-conformance class")


if __name__ == "__main__":
    unittest.main()
