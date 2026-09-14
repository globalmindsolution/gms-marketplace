"""/acs:create-prd runs execute -> verify with no planner (ADR-0092 class D).

MAR-305 first dropped the per-iteration re-plan (plan once, then execute ->
verify). ADR-0092 followed that to its conclusion: a PRD is a document, so a
plan for it is a second copy of the writing — the executor surveys (mode,
outline, open questions, the three corroboration sections the verifier's
deterministic floor parses) in its authoring notes and writes the set from
them. This module pins that topology so a planner cannot creep back in
through prose, the registry, or an agent file. Mirrors
tests/acs/test_create_docs_loop_topology.py.

Run:  python3 -m unittest tests.acs.test_create_prd_loop_topology -v
"""

import os
import re
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN = os.path.join(REPO_ROOT, "src", "acs")
PRD_SKILL = os.path.join(PLUGIN, "skills", "create-prd", "SKILL.md")
AGENTS = os.path.join(PLUGIN, "agents")
PRD_EXECUTOR = os.path.join(AGENTS, "create-prd-executor.md")
PRD_VERIFIER = os.path.join(AGENTS, "create-prd-verifier.md")
sys.path.insert(0, os.path.join(PLUGIN, "hooks", "scripts"))

import acs_lib  # noqa: E402


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def norm(body):
    return re.sub(r"\s+", " ", body)


def section(body, start_heading, end_heading):
    start = body.find(start_heading)
    end = body.find(end_heading, start)
    assert start != -1, "%r heading not found" % start_heading
    assert end != -1, "%r heading not found" % end_heading
    return body[start:end]


class NoPlannerTest(unittest.TestCase):

    def test_the_registry_declares_executor_and_verifier_only(self):
        self.assertEqual(acs_lib.skill_agents()["create-prd"], ["executor", "verifier"])

    def test_the_two_agent_files_exist_and_no_planner_does(self):
        self.assertTrue(os.path.isfile(PRD_EXECUTOR))
        self.assertTrue(os.path.isfile(PRD_VERIFIER))
        self.assertFalse(os.path.exists(os.path.join(AGENTS, "create-prd-planner.md")))

    def test_the_prose_never_spawns_a_planner(self):
        body = read(PRD_SKILL)
        self.assertNotIn("acs:create-prd-planner", body)
        self.assertNotRegex(body, r"(?i)spawn (exactly )?one .{0,40}planner")
        self.assertNotIn("iter-1-plan.md", body)
        self.assertNotIn('phase="plan"', body)

    def test_the_prose_says_there_is_no_plan_phase(self):
        body = norm(read(PRD_SKILL))
        self.assertRegex(body, r"(?i)execute -> verify, no planner")
        self.assertRegex(body, r"(?i)There is no plan phase")

    def test_no_unnegated_replan_instruction(self):
        negating = re.compile(r"(?i)never|no |not|without|instead of")
        for m in re.finditer(r"(?i)re-?plan\w*", read(PRD_SKILL)):
            window = read(PRD_SKILL)[max(0, m.start() - 60):m.end() + 60]
            self.assertRegex(window, negating,
                             "un-negated 're-plan' instruction found: %r" % window)


class ExecuteVerifyLoopTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.body = read(PRD_SKILL)
        cls.norm = norm(cls.body)

    def test_cap_is_three_execute_verify_rounds(self):
        self.assertIn("max 3 iterations", self.norm)
        self.assertIn("After iteration 3", self.norm)
        self.assertRegex(self.norm, r"(?i)an iteration counts:\*\* one execute -> verify round")

    def test_iteration_one_surveys_then_writes(self):
        self.assertRegex(self.norm, r"(?i)iteration 1'?s executor classifies the mode")
        self.assertRegex(self.norm, r"(?i)returns `needs_input` with the open questions before writing any file")
        self.assertRegex(self.norm, r"(?i)findings go verbatim into the next executor `<task>` `<context>`")

    def test_the_executor_writes_authoring_notes_and_the_verifier_reads_them(self):
        self.assertIn("iter-<n>-authoring.md", self.body)
        executor = read(PRD_EXECUTOR)
        self.assertIn("iter-<n>-authoring.md", executor)
        self.assertIn("## Survey — what you establish before you write (iteration 1)", executor)
        for heading in ("## Code evidence", "## Answer fidelity", "## Roadmap milestones"):
            self.assertIn(heading, executor)
        verifier = read(PRD_VERIFIER)
        self.assertIn("--plan <partition>/phases/create-prd/iter-<n>-authoring.md", verifier)
        self.assertNotIn("iter-<n>-plan.md", verifier)

    def test_findings_feed_the_executor_context_with_no_plan_phase_in_between(self):
        no_plan_re = re.compile(r"(?i)(no|never|without)\W{0,20}plan(ner| phase)")
        for m in re.finditer(r"(?i)findings", self.norm):
            window = self.norm[max(0, m.start() - 300):m.end() + 300]
            if ("executor" in window.lower() and "<context>" in window
                    and no_plan_re.search(window)):
                return
        self.fail("create-prd/SKILL.md must co-locate 'findings', 'executor', "
                  "'<context>' and a no-plan-phase clause within ~300 chars")

    def test_executor_charter_still_requires_fixing_every_listed_finding(self):
        self.assertIn("On iteration 2+, fix EVERY finding listed in `<context>`", norm(read(PRD_EXECUTOR)))

    def test_no_lane_driven_verify_depth_machinery_introduced(self):
        for token in ("verify_depth", "VERIFY_ITERATION_CAP", "TRIVIAL", "COMPLEX"):
            self.assertNotIn(token, self.body)

    def test_resume_never_reintroduces_a_plan_artifact(self):
        window = section(self.norm, "## Resume & reconcile", "## Reflection loop")
        self.assertNotIn("iter-1-plan.md", window)
        self.assertRegex(window, r"(?i)no plan artifact to reuse")


class VerifierIndependenceUnchangedTest(unittest.TestCase):

    def test_skill_verify_phase_keeps_artifact_only_independence_clause(self):
        body_norm = norm(read(PRD_SKILL))
        self.assertIn("with ONLY artifact references", body_norm)
        self.assertIn("never the executor's reasoning", body_norm)
        self.assertIn("repo_root", body_norm)

    def test_verifier_agent_still_refuses_to_trust_the_execute_report(self):
        body = read(PRD_VERIFIER)
        self.assertIn("Never rubber-stamp: re-run every cheap check yourself", norm(body))
        self.assertIn("prd_conformance_check.py", body)
        self.assertIn("independently and deterministically re-checks three families", norm(body))


if __name__ == "__main__":
    unittest.main()
