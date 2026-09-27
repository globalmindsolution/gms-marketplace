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


class ParallelismTest(unittest.TestCase):
    """Scaffolders fan out over disjoint file sets from iteration 1, the
    build-checker runs as dimension slices with its one build/lint/test run in
    exactly one of them, and the slices are joined by `acs.py notes merge`."""

    @classmethod
    def setUpClass(cls):
        cls.norm = norm(read(SKILL))
        cls.scaffolder = norm(read(SCAFFOLDER))
        cls.checker = norm(read(BUILD_CHECKER))

    def test_every_fan_out_is_one_message_capped_at_four(self):
        self.assertIn("### Parallelism — scaffolder slices and build-checker slices", self.norm)
        self.assertRegex(self.norm, r"spawn the N instances of the SAME agent in ONE message")
        self.assertIn("`max_parallel = 4`", self.norm)
        self.assertRegex(self.norm, r"(?i)in waves of four")

    def test_iteration_one_pins_once_then_builds_in_parallel_slices(self):
        self.assertIn("**Scaffolder slices — the default, from iteration 1.**", self.norm)
        self.assertRegex(self.norm, r"ONE un-sliced scaffolder runs the \*\*pin pass\*\*")
        self.assertIn('<constraint name="pass">pin</constraint>', self.norm)
        self.assertIn('slice="<id>"', self.norm)
        self.assertIn('<constraint name="files">', self.norm)
        self.assertNotIn("Iteration 1 runs a single scaffolder (the notes and the build are one act)",
                         self.norm)

    def test_the_partition_rule_names_the_slices_and_what_stays_together(self):
        for slice_id in ("`core`", "`ci`", "`precommit`", "`docs`"):
            self.assertIn("| %s |" % slice_id, self.norm)
        self.assertRegex(self.norm, r"\*\*What must stay in one slice:\*\* everything the four commands need to go green together")
        self.assertRegex(self.norm, r"`core` is the only slice that installs dependencies or runs the four commands")
        self.assertRegex(self.norm, r"\*\*The no-overlap guarantee:\*\* the notes' Slices section assigns every manifest file to exactly one slice id")

    def test_slices_share_the_branch_without_forcing(self):
        self.assertIn("`git add -- <its files>`, never `git add -A`", self.norm)
        self.assertRegex(self.norm, r"on git `index\.lock` contention it waits briefly and retries the commit — it never forces anything")

    def test_build_checker_slices_keep_the_single_run_in_one_slice(self):
        self.assertIn("**Build-checker slices — the default, every iteration.**", self.norm)
        for slice_id in ("`run`", "`structure`", "`wiring`"):
            self.assertIn("| %s |" % slice_id, self.norm)
        self.assertIn('<constraint name="dimensions">', self.norm)
        self.assertIn("The build/lint/test run stays in exactly one slice", self.norm)
        self.assertIn("Grounding policing applies in every slice", self.norm)

    def test_judge_slices_are_joined_by_notes_merge(self):
        self.assertIn('acs.py" notes merge', self.norm)
        self.assertIn("--out <partition>/steps/create-project/iter-<n>/build-checker.md", self.norm)
        for slice_id in ("run", "structure", "wiring"):
            self.assertIn("iter-<n>/build-checker-%s.md" % slice_id, self.norm)

    def test_the_sliced_judge_pass_rule(self):
        self.assertRegex(self.norm, r"\*\*Pass rule for sliced judges:\*\* the iteration passes only if EVERY slice returned `status=\"completed\"` with zero blocking findings")
        self.assertIn('never "pass with a missing slice"', self.norm)
        self.assertRegex(self.norm, r"all slices' findings go verbatim to the next scaffolders")

    def test_resume_reruns_only_the_missing_slices(self):
        self.assertRegex(self.norm, r"A resumed iteration re-runs only the slices whose report is missing")
        self.assertIn("iter-<n>/<phase>-<slice>-message.xml", self.norm)

    def test_the_survey_is_not_sliced_and_says_why(self):
        self.assertRegex(self.norm, r"\*\*Survey — not sliced\.\*\* The pin pass .{0,200}greenfield repo that has no top-level areas")

    def test_the_agents_know_how_to_run_as_one_slice(self):
        self.assertIn("## When you are one slice", self.scaffolder)
        self.assertIn("iter-<n>/scaffolder-<slice>.json", self.scaffolder)
        self.assertRegex(self.scaffolder, r"never check out, create or switch a branch")
        self.assertRegex(self.scaffolder, r"wait briefly and retry the commit — never force anything")
        self.assertIn("## When you are one slice", self.checker)
        self.assertIn("iter-<n>/build-checker-<slice>.md", self.checker)
        self.assertRegex(self.checker, r"\*\*Grounding policing always applies\*\*")
        self.assertRegex(self.checker, r"Only the `run` slice executes the toolchain")
        self.assertIn('slice="run"', self.checker)

    def test_an_integration_pass_synthesizes_the_slices_before_the_build_check(self):
        self.assertIn("**The integration pass — synthesis before the build-check.**", self.norm)
        self.assertRegex(self.norm, r"BEFORE the build-checker, spawn ONE more scaffolder with `slice=\"integration\"`")
        self.assertIn("reconciles ONLY the seams between slices, never a slice's substance", self.norm)
        for seam in ("**config files touched by more than one slice**", "**the README**",
                     "**the whole tree green together**"):
            self.assertIn(seam, self.norm)
        self.assertIn("iter-<n>/scaffolder-integration.json", self.norm)
        self.assertRegex(self.norm, r"The integration pass is skipped when only one scaffolder built")
        self.assertRegex(self.norm, r"a finding on a seam .{0,320}goes to the integration pass")
        self.assertIn('slice="integration"', self.scaffolder)
        self.assertRegex(self.scaffolder, r"`seams` array — one `\{file, what, why, slices\}` entry per seam")
        self.assertRegex(self.checker, r"You judge the INTEGRATED result")

    def test_the_join_is_followed_by_judge_de_duplication(self):
        self.assertIn("**De-duplicate after the join.**", self.norm)
        self.assertRegex(self.norm, r"Drop a finding that cites the same location and the same defect as another slice's finding, keeping the higher severity")
        self.assertIn("`## De-duplicated findings`", self.norm)

    def test_no_survey_slices_means_nothing_to_synthesize(self):
        self.assertIn("there are no survey slices to synthesize", self.norm)

if __name__ == "__main__":
    unittest.main()
