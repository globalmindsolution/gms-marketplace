"""MAR-300 — /acs:docs-sync's reflection loop drops the per-iteration
re-plan: the planner now runs exactly once per run, before the loop, and the
loop body is execute -> verify only. Verifier findings on iteration 2+ route
straight to the executor's <context>, with no intervening planner spawn.
Mirrors the structure (never the content) of
tests/acs/test_code_loop_topology.py, which pins the identical topology
change /acs:code made in MAR-71.

Every assertion is by file + substring/regex over whitespace-normalized text,
never by line number (line numbers drift as prose is revised). Stdlib-only
(os, re, unittest). Run:
  python3 -m unittest tests.acs.test_docs_sync_loop_topology -v
"""

import os
import re
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN = os.path.join(REPO_ROOT, "plugins", "acs")
DOCS_SYNC_SKILL = os.path.join(PLUGIN, "skills", "docs-sync", "SKILL.md")
DOCS_SYNC_PLANNER = os.path.join(PLUGIN, "agents", "docs-sync-planner.md")
DOCS_SYNC_EXECUTOR = os.path.join(PLUGIN, "agents", "docs-sync-executor.md")
DOCS_SYNC_VERIFIER = os.path.join(PLUGIN, "agents", "docs-sync-verifier.md")


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def norm(body):
    """Collapse whitespace runs so markdown line-wrap can never break a
    phrase-spanning match."""
    return re.sub(r"\s+", " ", body)


class SinglePlannerSpawnPerRunTest(unittest.TestCase):
    """AC-1: a docs-sync run that needs 3 iterations spawns exactly one
    acs:docs-sync-planner subagent across the whole run."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(DOCS_SYNC_SKILL)
        cls.norm = norm(cls.body)

    def test_reflection_loop_states_exactly_one_planner_spawn_per_run(self):
        for m in re.finditer(r"exactly one", self.norm, re.IGNORECASE):
            window = self.norm[max(0, m.start() - 80):m.end() + 80]
            if "acs:docs-sync-planner" in window and re.search(
                    r"(?i)\b(run|whole run)\b", window):
                return
        self.fail(
            "docs-sync/SKILL.md must co-locate an 'exactly one' clause with "
            "'acs:docs-sync-planner' and a whole-run qualifier within ~80 chars")

    def test_plan_phase_heading_is_not_per_iteration(self):
        self.assertRegex(self.body, r"(?m)^### Phase: plan \(once[^)]*\)")
        self.assertNotRegex(self.body, r"(?m)^### Phase: plan\s+—")

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

    def test_resume_reuses_the_existing_plan_artifact_without_a_second_planner(self):
        resume_start = self.norm.find("## Resume & reconcile")
        resume_end = self.norm.find("## Inputs", resume_start)
        self.assertNotEqual(resume_start, -1, "## Resume & reconcile heading not found")
        self.assertNotEqual(resume_end, -1, "## Inputs heading not found")
        window = self.norm[resume_start:resume_end]
        self.assertIn("iter-1-plan.md", window)
        self.assertRegex(window, r"(?i)(never|no|without).{0,40}second planner")


class FindingsRouteStraightToExecutorTest(unittest.TestCase):
    """AC-2: verifier findings on iteration 2+ are delivered to the
    executor's <context>, with no intervening planner spawn."""

    def test_findings_feed_the_executor_context_with_no_planner_in_between(self):
        body_norm = norm(read(DOCS_SYNC_SKILL))
        no_planner_re = re.compile(r"(?i)(no|never|without)\W{0,20}planner")
        for m in re.finditer(r"(?i)findings", body_norm):
            window = body_norm[max(0, m.start() - 300):m.end() + 300]
            if ("executor" in window.lower() and "<context>" in window
                    and no_planner_re.search(window)):
                return
        self.fail(
            "docs-sync/SKILL.md must co-locate 'findings', 'executor', "
            "'<context>' and a no-planner clause within ~300 chars")

    def test_executor_input_contract_still_carries_iteration_2plus_findings(self):
        body_norm = norm(read(DOCS_SYNC_EXECUTOR))
        self.assertIn(
            "on iteration >= 2, the verifier findings your output must fix",
            body_norm)
        self.assertIn("<context>", body_norm)

    def test_executor_charter_still_requires_fixing_every_listed_finding(self):
        body_norm = norm(read(DOCS_SYNC_EXECUTOR))
        self.assertIn(
            "On iteration >= 2, fix every finding listed in `<context>`",
            body_norm)


class IterationCapUnchangedTest(unittest.TestCase):
    """AC-3: the iteration cap (max 3) and verify-depth selection are
    unchanged."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(DOCS_SYNC_SKILL)
        cls.norm = norm(cls.body)

    def test_cap_is_still_max_three_iterations(self):
        self.assertIn("max 3 iterations", self.norm)
        self.assertIn("After iteration 3", self.norm)

    def test_iteration_is_defined_as_an_execute_verify_round(self):
        loop_start = self.norm.find("## Reflection loop")
        loop_end = self.norm.find("## User interaction")
        self.assertNotEqual(loop_start, -1)
        self.assertNotEqual(loop_end, -1)
        window = self.norm[loop_start:loop_end]
        self.assertRegex(window, r"(?i)execute\s*(→|->|\+|and)\s*verify")
        self.assertRegex(
            window,
            r"(?i)not.{0,80}(triad|plan\W{0,4}execute\W{0,4}verify)")

    def test_no_lane_driven_verify_depth_machinery_introduced(self):
        for token in ("verify_depth", "VERIFY_ITERATION_CAP", "TRIVIAL", "COMPLEX"):
            self.assertNotIn(token, self.body)


class PlannerRoleStillWiredTest(unittest.TestCase):
    """AC-4: the test suite is updated to assert single-planner-spawn
    behavior and the existing docs-sync test suite passes; this test guards
    against over-deletion of the planner/verifier roles."""

    def test_skill_still_references_planner_and_verifier(self):
        body = read(DOCS_SYNC_SKILL)
        self.assertIn("acs:docs-sync-planner", body)
        self.assertIn("acs:docs-sync-verifier", body)


class VerifierIndependenceUnchangedTest(unittest.TestCase):
    """AC-5: the verifier's independent doc-impact re-derivation behavior is
    unchanged (still never trusts the planner's doc-delta list as
    authoritative)."""

    def test_skill_verify_phase_keeps_independent_rederivation_clause(self):
        body_norm = norm(read(DOCS_SYNC_SKILL))
        self.assertIn(
            "re-derives doc impact from the same six-input contract itself",
            body_norm)
        self.assertIn(
            "not exempt from the independent-re-derivation rule", body_norm)

    def test_verifier_agent_still_refuses_to_trust_the_executor_report(self):
        body_norm = norm(read(DOCS_SYNC_VERIFIER))
        self.assertIn(
            "never trust the executor's doc-delta report as ground truth",
            body_norm)
        self.assertIn("NEVER rubber-stamp", body_norm)

    def test_six_input_contract_still_read_by_every_phase(self):
        body_norm = norm(read(DOCS_SYNC_SKILL))
        self.assertIn(
            "every phase (planner, executor, and verifier alike) reads all "
            "six, independently",
            body_norm)


class PlannerNoLongerPromisedFindingsTest(unittest.TestCase):
    """E2 (Q1 answered 'extend scope'): docs-sync-planner.md's prose no
    longer promises the planner iteration >= 2 verifier findings, since
    after this change the planner is never re-spawned to receive them."""

    def test_planner_no_longer_promised_prior_iteration_findings(self):
        body_norm = norm(read(DOCS_SYNC_PLANNER))
        self.assertNotRegex(
            body_norm,
            r"(?i)verifier(?:'|’)?s? blocking findings from the prior iteration")
        self.assertNotIn("prior-iteration findings", body_norm)


if __name__ == "__main__":
    unittest.main()
