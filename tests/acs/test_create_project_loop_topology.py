"""/acs:create-project runs execute -> verify with no planner (ADR-0092 class D).

MAR-301 first dropped the per-iteration re-plan (plan once, then execute -> verify). ADR-0092 followed that to its conclusion: the scaffold plan is a document only its own executor uses, so iteration 1's executor pins the scaffold (layout, config, commands, vertical slice) in its authoring notes and builds it; the verifier re-runs the notes' commands. This module pins that topology so a planner cannot creep back in
through prose, the registry, or an agent file. Mirrors
tests/acs/test_create_docs_loop_topology.py.

Run:  python3 -m unittest tests.acs.test_create_project_loop_topology -v
"""

import os
import re
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN = os.path.join(REPO_ROOT, "plugins", "acs")
SKILL = os.path.join(PLUGIN, "skills", "create-project", "SKILL.md")
AGENTS = os.path.join(PLUGIN, "agents")
EXECUTOR = os.path.join(AGENTS, "create-project-executor.md")
VERIFIER = os.path.join(AGENTS, "create-project-verifier.md")
sys.path.insert(0, os.path.join(PLUGIN, "hooks", "scripts"))

import acs_lib  # noqa: E402


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def norm(body):
    return re.sub(r"\s+", " ", body)


class NoPlannerTest(unittest.TestCase):

    def test_the_registry_declares_executor_and_verifier_only(self):
        self.assertEqual(acs_lib.skill_agents()["create-project"], ["executor", "verifier"])

    def test_the_two_agent_files_exist_and_no_planner_does(self):
        self.assertTrue(os.path.isfile(EXECUTOR))
        self.assertTrue(os.path.isfile(VERIFIER))
        self.assertFalse(os.path.exists(os.path.join(AGENTS, "create-project-planner.md")))

    def test_the_prose_never_spawns_a_planner(self):
        for path in (SKILL, EXECUTOR, VERIFIER):
            body = read(path)
            self.assertNotIn("acs:create-project-planner", body)
            self.assertNotIn("iter-1-plan.md", body)
            self.assertNotIn("iter-<n>-plan.md", body)
        self.assertNotRegex(read(SKILL), r"(?i)spawn (exactly )?one .{0,40}planner")
        self.assertNotIn('phase="plan"', read(SKILL))

    def test_the_prose_says_there_is_no_plan_phase(self):
        body = norm(read(SKILL))
        self.assertRegex(body, r"(?i)execute -> verify, no planner")
        self.assertRegex(body, r"(?i)There is no plan phase")

    def test_no_unnegated_replan_instruction(self):
        body = read(SKILL)
        negating = re.compile(r"(?i)never|no |not|without|instead of")
        for m in re.finditer(r"(?i)re-?plan\w*", body):
            window = body[max(0, m.start() - 60):m.end() + 60]
            self.assertRegex(window, negating,
                             "un-negated 're-plan' instruction found: %r" % window)


class ExecuteVerifyLoopTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.body = read(SKILL)
        cls.norm = norm(cls.body)

    def test_cap_is_three_execute_verify_rounds(self):
        self.assertRegex(self.norm, r"(?i)(at most|max) 3 iterations")
        self.assertIn("After iteration 3", self.norm)
        self.assertRegex(self.norm, r"(?i)an iteration counts:\*\* one execute -> verify round")

    def test_iteration_one_surveys_then_writes(self):
        self.assertRegex(self.norm, r"(?i)iteration 1'?s executor reads the architecture doc set, pins the scaffold")
        self.assertRegex(self.norm, r"(?i)findings go verbatim into the next executor `<task>` `<context>`")

    def test_the_executor_writes_frozen_notes_and_the_verifier_reads_them(self):
        self.assertIn("iter-1-authoring.md", self.body)
        executor = read(EXECUTOR)
        self.assertIn("iter-1-authoring.md", executor)
        self.assertIn("## Survey — what you establish before you write (iteration 1)", executor)
        self.assertRegex(norm(executor), r"(?i)authored exactly once and never rewritten")
        verifier = read(VERIFIER)
        self.assertIn("iter-1-authoring.md", verifier)
        self.assertRegex(norm(verifier), r"(?i)run the notes'? build command")

    def test_findings_feed_the_executor_context_with_no_plan_phase_in_between(self):
        no_plan_re = re.compile(r"(?i)(no|never|without)\W{0,20}plan(ner| phase)")
        for m in re.finditer(r"(?i)findings", self.norm):
            window = self.norm[max(0, m.start() - 300):m.end() + 300]
            if ("executor" in window.lower() and "<context>" in window
                    and no_plan_re.search(window)):
                return
        self.fail("create-project/SKILL.md must co-locate 'findings', 'executor', "
                  "'<context>' and a no-plan-phase clause within ~300 chars")

    def test_no_lane_driven_verify_depth_machinery_introduced(self):
        for token in ("verify_depth", "VERIFY_ITERATION_CAP", "TRIVIAL", "COMPLEX"):
            self.assertNotIn(token, self.body)

    def test_resume_never_reintroduces_a_plan_artifact(self):
        self.assertRegex(self.norm, r"(?i)no plan artifact to reuse")
        self.assertNotRegex(self.norm, r"(?i)second planner")

class VerifierIndependenceUnchangedTest(unittest.TestCase):
    """The verifier still RUNS build, lint and tests itself, from the notes'
    commands — the plan's removal changed who pins the commands, never who
    re-runs them."""

    def test_skill_verify_phase_keeps_independent_command_rerun_clauses(self):
        body_norm = norm(read(SKILL))
        self.assertRegex(body_norm, r"(?i)the exact commands the notes pinned, and see them pass")

    def test_verifier_agent_still_refuses_to_trust_the_execute_report(self):
        body = norm(read(VERIFIER))
        self.assertIn("Never rubber-stamp", body)
        self.assertRegex(body, r"(?i)plan-conformance.{0,80}every file in the notes'? manifest exists")


if __name__ == "__main__":
    unittest.main()
