"""/acs:standardize-project runs audit (iteration 1), then scaffold -> additive-check.

MAR-302 froze the planner's allowlist at iteration 1 so the writable surface could only shrink. ADR-0092 removed the planner and folded the audit into the executor. The per-skill subagent topology split that executor by logic: a read-only **auditor** (a survey role, iteration 1 only) writes the frozen Additive-surface allowlist into the authoring notes; a **scaffolder** (the write role) scaffolds exactly within it and remediates from the same notes on iterations 2-3; the **additive-checker** (the judge) enforces the additive-only diff classification against those notes every iteration. This module pins that topology so a planner (or the generic executor/verifier pair) cannot creep back in
through prose, the registry, or an agent file. Mirrors
tests/acs/test_create_docs_loop_topology.py.

Run:  python3 -m unittest tests.acs.test_standardize_project_loop_topology -v
"""

import os
import re
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN = os.path.join(REPO_ROOT, "plugins", "acs")
SKILL = os.path.join(PLUGIN, "skills", "standardize-project", "SKILL.md")
AGENTS = os.path.join(PLUGIN, "agents")
AUDITOR = os.path.join(AGENTS, "standardize-project-auditor.md")
SCAFFOLDER = os.path.join(AGENTS, "standardize-project-scaffolder.md")
CHECKER = os.path.join(AGENTS, "standardize-project-additive-checker.md")
sys.path.insert(0, os.path.join(PLUGIN, "hooks", "scripts"))

import acs_lib  # noqa: E402


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def norm(body):
    return re.sub(r"\s+", " ", body)


class NoPlannerTest(unittest.TestCase):

    def test_the_registry_declares_auditor_scaffolder_and_additive_checker_only(self):
        self.assertEqual(sorted(acs_lib.skill_agents()["standardize-project"]),
                         ["additive-checker", "auditor", "scaffolder"])
        self.assertEqual(acs_lib.role_kind("auditor"), "survey")
        self.assertEqual(acs_lib.role_kind("scaffolder"), "write")
        self.assertEqual(acs_lib.role_kind("additive-checker"), "judge")

    def test_the_three_agent_files_exist_and_no_planner_does(self):
        for path in (AUDITOR, SCAFFOLDER, CHECKER):
            self.assertTrue(os.path.isfile(path), path)
        for gone in ("planner", "executor", "verifier"):
            self.assertFalse(os.path.exists(
                os.path.join(AGENTS, "standardize-project-%s.md" % gone)), gone)

    def test_the_prose_never_spawns_a_planner(self):
        for path in (SKILL, AUDITOR, SCAFFOLDER, CHECKER):
            body = read(path)
            self.assertNotIn("acs:standardize-project-planner", body)
            self.assertNotIn("iter-1-plan.md", body)
            self.assertNotIn("iter-<n>-plan.md", body)
        self.assertNotRegex(read(SKILL), r"(?i)spawn (exactly )?one .{0,40}planner")
        self.assertNotIn('phase="plan"', read(SKILL))

    def test_the_prose_says_there_is_no_plan_phase(self):
        body = norm(read(SKILL))
        self.assertRegex(body, r"(?i)## Reflection loop — audit, then scaffold -> additive-check")
        self.assertRegex(body, r"(?i)no plan phase")
        for role in ("auditor", "scaffolder", "additive-checker"):
            self.assertIn('phase="%s"' % role, body)
        for gone in ('phase="execute"', 'phase="verify"'):
            self.assertNotIn(gone, body)

    def test_no_unnegated_replan_instruction(self):
        body = read(SKILL)
        negating = re.compile(r"(?i)never|no |not|without|instead of")
        for m in re.finditer(r"(?i)re-?plan\w*", body):
            window = body[max(0, m.start() - 60):m.end() + 60]
            self.assertRegex(window, negating,
                             "un-negated 're-plan' instruction found: %r" % window)


class AuditScaffoldCheckLoopTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.body = read(SKILL)
        cls.norm = norm(cls.body)

    def test_cap_is_three_scaffold_additive_check_rounds(self):
        self.assertRegex(self.norm, r"(?i)(at most|max) 3 iterations")
        self.assertIn("After iteration 3", self.norm)
        self.assertRegex(self.norm, r"(?i)an iteration counts:\*\* one scaffold -> additive-check round")

    def test_iteration_one_audits_then_scaffolds(self):
        self.assertRegex(self.norm, r"(?i)Runs on \*\*iteration 1 only\*\*, before anything is scaffolded: it AUDITS the repo \(read-only\) and writes the run's authoring notes")
        self.assertRegex(self.norm, r"(?i)auditor \(iteration 1\) → scaffolder → additive-checker; iterations 2-3 are scaffolder ← findings → additive-checker")
        self.assertRegex(self.norm, r"(?i)findings go verbatim into the next scaffolder `<task>` `<context>`")
        self.assertRegex(self.norm, r"(?i)the audit is never re-run")

    def test_the_auditor_writes_frozen_notes_and_the_others_read_them(self):
        self.assertIn("iter-1-authoring.md", self.body)
        auditor = read(AUDITOR)
        self.assertIn("iter-1-authoring.md", auditor)
        self.assertIn("## Survey — what you establish before you write (iteration 1)", auditor)
        self.assertRegex(norm(auditor), r"(?i)authored exactly once and never rewritten")
        self.assertIn("iter-1/auditor.json", auditor)
        scaffolder = read(SCAFFOLDER)
        self.assertIn("iter-1-authoring.md", scaffolder)
        self.assertRegex(norm(scaffolder), r"(?i)never rewritten — not by you, on any iteration")
        self.assertNotIn("## Survey", scaffolder)
        checker = read(CHECKER)
        self.assertIn("iter-1-authoring.md", checker)
        self.assertRegex(norm(checker), r"(?i)read at their literal frozen path `iter-1-authoring.md` every iteration")

    def test_the_auditor_is_read_only_on_the_repo(self):
        fm = read(AUDITOR).split("---\n", 2)[1]
        self.assertRegex(fm, r"(?m)^tools: Read, Glob, Grep, Bash, Write$")
        self.assertRegex(norm(read(AUDITOR)), r"(?i)Read-only on the repo: never create, edit, rename, move, or delete a repo file")

    def test_each_role_runs_on_its_kind_s_model_tier(self):
        self.assertEqual(acs_lib.model_tier("auditor"), "planner")
        self.assertEqual(acs_lib.model_tier("scaffolder"), "executor")
        self.assertEqual(acs_lib.model_tier("additive-checker"), "verifier")
        self.assertRegex(self.norm, r"(?i)`planner` for the auditor, `executor` for the scaffolder, `verifier` for the additive-checker")

    def test_findings_feed_the_scaffolder_context_with_no_plan_phase_in_between(self):
        no_plan_re = re.compile(r"(?i)(no|never|without)\W{0,20}plan(ner| phase)")
        for m in re.finditer(r"(?i)findings", self.norm):
            window = self.norm[max(0, m.start() - 300):m.end() + 300]
            if ("scaffolder" in window.lower() and "<context>" in window
                    and no_plan_re.search(window)):
                return
        self.fail("standardize-project/SKILL.md must co-locate 'findings', 'scaffolder', "
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
        self.assertRegex(body, r"(?i)The auditor authors the Additive-surface allowlist exactly once, in its iteration-1 authoring notes")
        self.assertRegex(body, r"(?i)monotonically non-increasing across iterations 1-3")

    def test_additive_checker_checks_the_allowlist_categories_itself(self):
        body = norm(read(CHECKER))
        self.assertRegex(body, r"(?i)the allowlist itself draws only from the two sanctioned categories")
        self.assertIn("classify_additive_diff", body)
        self.assertRegex(body, r"(?i)fixed against the same frozen `iter-1-authoring.md`")

    def test_scaffolder_refuses_findings_outside_the_frozen_allowlist(self):
        body = norm(read(SCAFFOLDER))
        self.assertRegex(body, r"(?i)outside the frozen iteration-1 Additive-surface allowlist is \*\*NOT executable\*\*")


if __name__ == "__main__":
    unittest.main()
