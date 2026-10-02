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


class ParallelismTest(unittest.TestCase):
    """The audit runs as category slices joined by `acs.py notes merge` into the
    frozen notes, scaffolders fan out per allowlist slice from iteration 1, and
    the additive-checker runs as dimension slices with the additive-only check
    whole in one of them."""

    @classmethod
    def setUpClass(cls):
        cls.norm = norm(read(SKILL))
        cls.auditor = norm(read(AUDITOR))
        cls.scaffolder = norm(read(SCAFFOLDER))
        cls.checker = norm(read(CHECKER))

    def test_every_fan_out_is_one_message_capped_at_four(self):
        self.assertIn("### Parallelism — audit slices, scaffolder slices, additive-checker slices", self.norm)
        self.assertRegex(self.norm, r"spawn the N instances of the SAME agent in ONE message")
        self.assertIn("`max_parallel = 4`", self.norm)
        self.assertRegex(self.norm, r"(?i)in waves of four")

    def test_audit_slices_split_the_categories_and_join_into_the_frozen_notes(self):
        self.assertIn("**Audit slices — iteration 1, the default.**", self.norm)
        for slice_id in ("`structure`", "`docsets`", "`tooling`"):
            self.assertIn("| %s |" % slice_id, self.norm)
        self.assertIn('<constraint name="audit_categories">', self.norm)
        self.assertRegex(self.norm, r"Only the `tooling` slice writes the `## Additive-surface allowlist` and `## Task list` sections, so the frozen allowlist has exactly one author")
        self.assertIn("--out <partition>/steps/standardize-project/iter-1/authoring.md", self.norm)
        for slice_id in ("structure", "docsets", "tooling"):
            self.assertIn("iter-1/authoring-%s.md" % slice_id, self.norm)
        self.assertRegex(self.norm, r"Open questions from ALL slices go to the user in ONE grouped clarification-ledger ask")

    def test_scaffolder_slices_partition_the_task_list_by_path_from_iteration_one(self):
        self.assertIn("**Scaffolder slices — the default, from iteration 1.**", self.norm)
        for slice_id in ("`ci`", "`precommit`", "`coverage`", "`e2e`"):
            self.assertIn("| %s |" % slice_id, self.norm)
        self.assertRegex(self.norm, r"\*\*The no-overlap guarantee:\*\* slices are drawn by target PATH, never by concern")
        self.assertIn('<constraint name="files">', self.norm)
        self.assertRegex(self.norm, r"Scaffolders write files only — you commit once, after the pass")
        self.assertNotIn("On iterations 2-3 you MAY run several scaffolders in parallel", self.norm)

    def test_additive_checker_slices_keep_the_additive_only_check_whole(self):
        self.assertIn("**Additive-checker slices — the default, every iteration.**", self.norm)
        for slice_id in ("`diff`", "`conformance`"):
            self.assertIn("| %s |" % slice_id, self.norm)
        self.assertIn('<constraint name="dimensions">', self.norm)
        self.assertIn("The additive-only check stays whole in the `diff` slice", self.norm)
        self.assertIn("Grounding policing applies in every slice", self.norm)
        self.assertIn("--out <partition>/steps/standardize-project/iter-<n>/additive-checker.md", self.norm)
        for slice_id in ("diff", "conformance"):
            self.assertIn("iter-<n>/additive-checker-%s.md" % slice_id, self.norm)

    def test_the_sliced_judge_pass_rule(self):
        self.assertRegex(self.norm, r"\*\*Pass rule for sliced judges:\*\* the iteration passes only if EVERY slice returned `status=\"completed\"` with zero blocking findings")
        self.assertIn('never "pass with a missing slice"', self.norm)
        self.assertRegex(self.norm, r"all slices' findings go verbatim to the next scaffolders")

    def test_resume_reruns_only_the_missing_slices(self):
        self.assertRegex(self.norm, r"A resumed iteration re-runs only the slices whose report is missing")
        self.assertIn("iter-<n>/<phase>-<slice>-message.xml", self.norm)

    def test_the_agents_know_how_to_run_as_one_slice(self):
        for body in (self.auditor, self.scaffolder, self.checker):
            self.assertIn("## When you are one slice", body)
        self.assertIn("iter-1/authoring-<slice>.md", self.auditor)
        self.assertIn("iter-1/auditor-<slice>.json", self.auditor)
        self.assertIn("### slice: <id>", self.auditor)
        self.assertIn("iter-<n>/scaffolder-<slice>.json", self.scaffolder)
        self.assertIn("iter-<n>/additive-checker-<slice>.md", self.checker)
        self.assertRegex(self.checker, r"\*\*Grounding policing always applies\*\*")
        self.assertRegex(self.checker, r"never calls `classify_additive_diff` and never raises an `additive-only` finding")

    def test_an_integration_pass_synthesizes_the_slices_before_the_additive_check(self):
        self.assertIn("**The integration pass — synthesis before the additive-check.**", self.norm)
        self.assertRegex(self.norm, r"BEFORE the additive-checker, spawn ONE more scaffolder with `slice=\"integration\"`")
        self.assertIn("reconciles ONLY the seams between slices, never a slice's substance", self.norm)
        for seam in ("**config files touched by more than one slice**", "**the README**",
                     "**the survey synthesis**"):
            self.assertIn(seam, self.norm)
        self.assertRegex(self.norm, r"Its writable surface is the frozen allowlist and nothing more")
        self.assertIn("iter-<n>/scaffolder-integration.json", self.norm)
        self.assertRegex(self.norm, r"The integration pass is skipped when only one scaffolder ran")
        self.assertIn('slice="integration"', self.scaffolder)
        self.assertRegex(self.checker, r"You judge the INTEGRATED result")

    def test_the_consumer_of_the_merged_audit_notes_keeps_a_synthesis(self):
        self.assertIn("**Synthesis of the audit slices.**", self.norm)
        self.assertRegex(self.norm, r"records the resolution with the evidence under a `## Synthesis` section of its own notes, `iter-1/scaffolder-notes\.md`, or raises it as an open question — never silently picks one")
        self.assertRegex(self.scaffolder, r"`## Synthesis` section of your own notes, `iter-1/scaffolder-notes\.md`")
        self.assertRegex(self.scaffolder, r"do not pick a side")

    def test_the_join_is_followed_by_judge_de_duplication(self):
        self.assertIn("**De-duplicate after the join.**", self.norm)
        self.assertRegex(self.norm, r"Drop a finding that cites the same location and the same defect as another slice's finding, keeping the higher severity")
        self.assertIn("`## De-duplicated findings`", self.norm)

if __name__ == "__main__":
    unittest.main()
