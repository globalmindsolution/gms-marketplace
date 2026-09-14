"""/acs:standardize-project runs execute -> verify with no planner (ADR-0092 class D).

MAR-302 froze the planner's allowlist at iteration 1 so the executor's writable surface could only shrink. ADR-0092 removed the planner: iteration 1's executor audits the repo read-only, writes the frozen Additive-surface allowlist into its authoring notes, and scaffolds within it; the verifier enforces the same additive-only diff classification against those notes every iteration. This module pins that topology so a planner cannot creep back in
through prose, the registry, or an agent file. Mirrors
tests/acs/test_create_docs_loop_topology.py.

Run:  python3 -m unittest tests.acs.test_standardize_project_loop_topology -v
"""

import os
import re
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN = os.path.join(REPO_ROOT, "src", "acs")
SKILL = os.path.join(PLUGIN, "skills", "standardize-project", "SKILL.md")
AGENTS = os.path.join(PLUGIN, "agents")
EXECUTOR = os.path.join(AGENTS, "standardize-project-executor.md")
VERIFIER = os.path.join(AGENTS, "standardize-project-verifier.md")
sys.path.insert(0, os.path.join(PLUGIN, "hooks", "scripts"))

import acs_lib  # noqa: E402


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def norm(body):
    return re.sub(r"\s+", " ", body)


class NoPlannerTest(unittest.TestCase):

    def test_the_registry_declares_executor_and_verifier_only(self):
        self.assertEqual(acs_lib.skill_agents()["standardize-project"], ["executor", "verifier"])

    def test_the_two_agent_files_exist_and_no_planner_does(self):
        self.assertTrue(os.path.isfile(EXECUTOR))
        self.assertTrue(os.path.isfile(VERIFIER))
        self.assertFalse(os.path.exists(os.path.join(AGENTS, "standardize-project-planner.md")))

    def test_the_prose_never_spawns_a_planner(self):
        for path in (SKILL, EXECUTOR, VERIFIER):
            body = read(path)
            self.assertNotIn("acs:standardize-project-planner", body)
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
        self.assertRegex(self.norm, r"(?i)iteration 1'?s executor AUDITS the repo \(read-only\) and writes its authoring notes")
        self.assertRegex(self.norm, r"(?i)findings go verbatim into the next executor `<task>` `<context>`")

    def test_the_executor_writes_frozen_notes_and_the_verifier_reads_them(self):
        self.assertIn("iter-1-authoring.md", self.body)
        executor = read(EXECUTOR)
        self.assertIn("iter-1-authoring.md", executor)
        self.assertIn("## Survey — what you establish before you write (iteration 1)", executor)
        self.assertRegex(norm(executor), r"(?i)authored exactly once and never rewritten")
        verifier = read(VERIFIER)
        self.assertIn("iter-1-authoring.md", verifier)
        self.assertRegex(norm(verifier), r"(?i)read at their literal frozen path `iter-1-authoring.md` every iteration")

    def test_findings_feed_the_executor_context_with_no_plan_phase_in_between(self):
        no_plan_re = re.compile(r"(?i)(no|never|without)\W{0,20}plan(ner| phase)")
        for m in re.finditer(r"(?i)findings", self.norm):
            window = self.norm[max(0, m.start() - 300):m.end() + 300]
            if ("executor" in window.lower() and "<context>" in window
                    and no_plan_re.search(window)):
                return
        self.fail("standardize-project/SKILL.md must co-locate 'findings', 'executor', "
                  "'<context>' and a no-plan-phase clause within ~300 chars")

    def test_no_lane_driven_verify_depth_machinery_introduced(self):
        for token in ("verify_depth", "VERIFY_ITERATION_CAP", "TRIVIAL", "COMPLEX"):
            self.assertNotIn(token, self.body)

    def test_resume_never_reintroduces_a_plan_artifact(self):
        self.assertRegex(self.norm, r"(?i)no plan artifact to reuse")
        self.assertNotRegex(self.norm, r"(?i)second planner")

class FrozenAllowlistTest(unittest.TestCase):
    """The allowlist freeze survives the planner's removal: authored exactly
    once, on iteration 1, and enforced mechanically every iteration."""

    def test_skill_freezes_the_allowlist_in_the_iteration_one_notes(self):
        body = norm(read(SKILL))
        self.assertRegex(body, r"(?i)The executor authors the Additive-surface allowlist exactly once, in its iteration-1 authoring notes")
        self.assertRegex(body, r"(?i)monotonically non-increasing across iterations 1-3")

    def test_verifier_checks_the_allowlist_categories_itself(self):
        body = norm(read(VERIFIER))
        self.assertRegex(body, r"(?i)the allowlist itself draws only from the two sanctioned categories")
        self.assertIn("classify_additive_diff", body)
        self.assertRegex(body, r"(?i)fixed against the same frozen `iter-1-authoring.md`")

    def test_executor_refuses_findings_outside_the_frozen_allowlist(self):
        body = norm(read(EXECUTOR))
        self.assertRegex(body, r"(?i)outside the frozen iteration-1 Additive-surface allowlist is \*\*NOT executable\*\*")


if __name__ == "__main__":
    unittest.main()
