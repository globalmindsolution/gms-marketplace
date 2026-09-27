"""/acs:create-project runs scaffold -> build-check, with no planner.

MAR-301 first dropped the per-iteration re-plan (plan once, then execute -> verify). ADR-0092 followed that to its conclusion: the scaffold plan is a document only the agent that builds it uses. The per-skill subagent topology then named the two roles for what they do: iteration 1's **scaffolder** pins the scaffold (layout, config, commands, vertical slice) in its authoring notes and builds it; the **build-checker** re-runs the notes' commands itself. This module pins that topology so a planner (or the generic executor/verifier pair) cannot creep back in
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
SCAFFOLDER = os.path.join(AGENTS, "create-project-scaffolder.md")
BUILD_CHECKER = os.path.join(AGENTS, "create-project-build-checker.md")
sys.path.insert(0, os.path.join(PLUGIN, "hooks", "scripts"))

import acs_lib  # noqa: E402


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def norm(body):
    return re.sub(r"\s+", " ", body)


class NoPlannerTest(unittest.TestCase):

    def test_the_registry_declares_scaffolder_and_build_checker_only(self):
        self.assertEqual(sorted(acs_lib.skill_agents()["create-project"]),
                         ["build-checker", "scaffolder"])
        self.assertEqual(acs_lib.role_kind("scaffolder"), "write")
        self.assertEqual(acs_lib.role_kind("build-checker"), "judge")

    def test_the_two_agent_files_exist_and_no_planner_does(self):
        self.assertTrue(os.path.isfile(SCAFFOLDER))
        self.assertTrue(os.path.isfile(BUILD_CHECKER))
        for gone in ("planner", "executor", "verifier"):
            self.assertFalse(os.path.exists(
                os.path.join(AGENTS, "create-project-%s.md" % gone)), gone)

    def test_the_prose_never_spawns_a_planner(self):
        for path in (SKILL, SCAFFOLDER, BUILD_CHECKER):
            body = read(path)
            self.assertNotIn("acs:create-project-planner", body)
            self.assertNotIn("iter-1-plan.md", body)
            self.assertNotIn("iter-<n>-plan.md", body)
        self.assertNotRegex(read(SKILL), r"(?i)spawn (exactly )?one .{0,40}planner")
        self.assertNotIn('phase="plan"', read(SKILL))

    def test_the_prose_says_there_is_no_plan_phase(self):
        body = norm(read(SKILL))
        self.assertRegex(body, r"(?i)## Reflection loop — scaffold -> build-check")
        self.assertRegex(body, r"(?i)no plan phase")
        self.assertIn('phase="scaffolder"', body)
        self.assertIn('phase="build-checker"', body)
        for gone in ('phase="execute"', 'phase="verify"'):
            self.assertNotIn(gone, body)

    def test_no_unnegated_replan_instruction(self):
        body = read(SKILL)
        negating = re.compile(r"(?i)never|no |not|without|instead of")
        for m in re.finditer(r"(?i)re-?plan\w*", body):
            window = body[max(0, m.start() - 60):m.end() + 60]
            self.assertRegex(window, negating,
                             "un-negated 're-plan' instruction found: %r" % window)


class ScaffoldBuildCheckLoopTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.body = read(SKILL)
        cls.norm = norm(cls.body)

    def test_cap_is_three_scaffold_build_check_rounds(self):
        self.assertRegex(self.norm, r"(?i)(at most|max) 3 iterations")
        self.assertIn("After iteration 3", self.norm)
        self.assertRegex(self.norm, r"(?i)an iteration counts:\*\* one scaffold -> build-check round")

    def test_iteration_one_surveys_then_writes(self):
        self.assertRegex(self.norm, r"(?i)iteration 1'?s scaffolder reads the architecture doc set \(or, under the no-architecture fallback, the confirmed `C-n` entries\), pins the scaffold")
        self.assertRegex(self.norm, r"(?i)findings go verbatim into the next scaffolder `<task>` `<context>`")

    def test_the_scaffolder_writes_frozen_notes_and_the_build_checker_reads_them(self):
        self.assertIn("iter-1-authoring.md", self.body)
        scaffolder = read(SCAFFOLDER)
        self.assertIn("iter-1-authoring.md", scaffolder)
        self.assertIn("## Survey — what you establish before you write (iteration 1)", scaffolder)
        self.assertRegex(norm(scaffolder), r"(?i)authored exactly once and never rewritten")
        self.assertIn("iter-<n>/scaffolder.json", scaffolder)
        checker = read(BUILD_CHECKER)
        self.assertIn("iter-1-authoring.md", checker)
        self.assertRegex(norm(checker), r"(?i)run the notes'? build command")
        self.assertIn("iter-<n>/build-checker.md", checker)

    def test_each_role_runs_on_its_kind_s_model_tier(self):
        self.assertEqual(acs_lib.model_tier("scaffolder"), "executor")
        self.assertEqual(acs_lib.model_tier("build-checker"), "verifier")
        self.assertRegex(self.norm, r"(?i)scaffolder \(a `write` role\) runs on the `executor` tier")
        self.assertRegex(self.norm, r"(?i)build-checker \(a `judge` role\) on the `verifier` tier")

    def test_findings_feed_the_scaffolder_context_with_no_plan_phase_in_between(self):
        no_plan_re = re.compile(r"(?i)(no|never|without)\W{0,20}plan(ner| phase)")
        for m in re.finditer(r"(?i)findings", self.norm):
            window = self.norm[max(0, m.start() - 300):m.end() + 300]
            if ("scaffolder" in window.lower() and "<context>" in window
                    and no_plan_re.search(window)):
                return
        self.fail("create-project/SKILL.md must co-locate 'findings', 'scaffolder', "
                  "'<context>' and a no-plan-phase clause within ~300 chars")

    def test_no_lane_driven_verify_depth_machinery_introduced(self):
        for token in ("verify_depth", "VERIFY_ITERATION_CAP", "TRIVIAL", "COMPLEX"):
            self.assertNotIn(token, self.body)

    def test_resume_never_reintroduces_a_plan_artifact(self):
        self.assertRegex(self.norm, r"(?i)no plan artifact to reuse")
        self.assertNotRegex(self.norm, r"(?i)second planner")

class BuildCheckerIndependenceTest(unittest.TestCase):
    """The build-checker still RUNS build, lint and tests itself, from the notes'
    commands — the plan's removal changed who pins the commands, never who
    re-runs them."""

    def test_skill_build_check_phase_keeps_independent_command_rerun_clauses(self):
        body_norm = norm(read(SKILL))
        self.assertRegex(body_norm, r"(?i)The build-checker MUST actually run, from `<checkout_root>`, the exact commands the notes pinned, and see them pass")

    def test_build_checker_still_refuses_to_trust_the_scaffolder_report(self):
        body = norm(read(BUILD_CHECKER))
        self.assertRegex(body, r"(?i)never accept the scaffolder report's word")
        self.assertIn("Never rubber-stamp", body)
        self.assertRegex(body, r"(?i)plan-conformance.{0,80}every file in the notes'? manifest exists")


if __name__ == "__main__":
    unittest.main()
