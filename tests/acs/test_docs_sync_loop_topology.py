"""/acs:docs-sync runs doc-updater -> drift-reviewer with no planner
(ADR-0092 class D).

MAR-300 first dropped the per-iteration re-plan (plan once, then execute ->
verify). ADR-0092 followed that to its conclusion: the doc-delta list is a
derivation only its own writer uses, so iteration 1's doc-updater re-derives
the doc impact from the six-input contract into its authoring notes and
commits the doc updates from them; the drift-reviewer re-derives the impact
itself and judges the result fresh. The per-skill subagents replaced the
generic executor/verifier pair with those two roles. This module pins that
topology so a planner cannot creep back in through prose, the agents tree, or
an agent file. Mirrors tests/acs/test_create_docs_loop_topology.py.

Run:  python3 -m unittest tests.acs.test_docs_sync_loop_topology -v
"""

import os
import re
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN = os.path.join(REPO_ROOT, "plugins", "acs")
SKILL = os.path.join(PLUGIN, "skills", "docs-sync", "SKILL.md")
AGENTS = os.path.join(PLUGIN, "agents")
DOC_UPDATER = os.path.join(AGENTS, "docs-sync-doc-updater.md")
DRIFT_REVIEWER = os.path.join(AGENTS, "docs-sync-drift-reviewer.md")
sys.path.insert(0, os.path.join(PLUGIN, "hooks", "scripts"))

import acs_lib  # noqa: E402


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def norm(body):
    return re.sub(r"\s+", " ", body)


class NoPlannerTest(unittest.TestCase):

    def test_the_tree_declares_doc_updater_and_drift_reviewer_only(self):
        self.assertEqual(acs_lib.skill_agents()["docs-sync"], ["doc-updater", "drift-reviewer"])

    def test_the_two_agent_files_exist_and_no_planner_does(self):
        self.assertTrue(os.path.isfile(DOC_UPDATER))
        self.assertTrue(os.path.isfile(DRIFT_REVIEWER))
        for role in ("planner", "executor", "verifier"):
            self.assertFalse(os.path.exists(os.path.join(AGENTS, "docs-sync-%s.md" % role)))

    def test_the_prose_never_spawns_a_planner(self):
        for path in (SKILL, DOC_UPDATER, DRIFT_REVIEWER):
            body = read(path)
            self.assertNotIn("acs:docs-sync-planner", body)
            self.assertNotIn("iter-1-plan.md", body)
            self.assertNotIn("iter-<n>-plan.md", body)
        self.assertNotRegex(read(SKILL), r"(?i)spawn (exactly )?one .{0,40}planner")
        self.assertNotIn('phase="plan"', read(SKILL))

    def test_the_prose_says_there_is_no_plan_phase(self):
        body = norm(read(SKILL))
        self.assertRegex(body, r"(?i)doc-updater → drift-reviewer")
        self.assertRegex(body, r"(?i)no planner, no plan phase")

    def test_no_unnegated_replan_instruction(self):
        body = read(SKILL)
        negating = re.compile(r"(?i)never|no |not|without|instead of")
        for m in re.finditer(r"(?i)re-?plan\w*", body):
            window = body[max(0, m.start() - 60):m.end() + 60]
            self.assertRegex(window, negating,
                             "un-negated 're-plan' instruction found: %r" % window)


class DocUpdaterDriftReviewerLoopTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.body = read(SKILL)
        cls.norm = norm(cls.body)

    def test_cap_is_three_rounds(self):
        self.assertIn("max 3 iterations", self.norm)
        self.assertIn("After iteration 3", self.norm)
        self.assertRegex(self.norm, r"(?i)an iteration counts:\*\* one doc-updater → drift-reviewer round")

    def test_iteration_one_derives_then_commits(self):
        self.assertRegex(self.norm, r"(?i)iteration 1'?s doc-updater re-derives the doc impact from the six inputs")
        self.assertRegex(self.norm, r"(?i)findings go verbatim into the next doc-updater `<task>` `<context>`")

    def test_phase_is_the_role(self):
        self.assertIn('phase="doc-updater"', self.body)
        self.assertIn('phase="drift-reviewer"', self.body)
        self.assertNotIn('phase="execute"', self.body)
        self.assertNotIn('phase="verify"', self.body)
        self.assertIn('<result skill="docs-sync" phase="doc-updater"', read(DOC_UPDATER))
        self.assertIn('<result skill="docs-sync" phase="drift-reviewer"', read(DRIFT_REVIEWER))

    def test_each_role_names_its_model_tier(self):
        self.assertIn("`context.models.executor.model` / `.effort` for the doc-updater", self.norm)
        self.assertIn("`context.models.verifier.model` / `.effort` for the drift-reviewer", self.norm)

    def test_the_doc_updater_writes_authoring_notes_and_the_drift_reviewer_reads_them(self):
        self.assertIn("iter-<n>/authoring.md", self.body)
        self.assertIn("iter-<n>/doc-updater.json", self.body)
        self.assertIn("iter-<n>/drift-reviewer.md", self.body)
        doc_updater = read(DOC_UPDATER)
        self.assertIn("iter-<n>/authoring.md", doc_updater)
        self.assertIn("steps/docs-sync/iter-<n>/doc-updater.json", doc_updater)
        self.assertIn("## Survey — what you establish before you write (iteration 1)", doc_updater)
        drift_reviewer = read(DRIFT_REVIEWER)
        self.assertIn("iter-<n>/authoring.md", drift_reviewer)
        self.assertIn("steps/docs-sync/iter-<n>/drift-reviewer.md", drift_reviewer)
        self.assertRegex(drift_reviewer, r"(?m)^6\. `authoring-conformance`")
        for body in (self.body, doc_updater, drift_reviewer):
            self.assertNotIn("docs-sync/iter-<n>/execute.json", body)
            self.assertNotIn("docs-sync/iter-<n>/verify.md", body)

    def test_code_reports_are_read_under_their_new_names(self):
        """/acs:code's writer is the implementer now and it has no verifier;
        docs-sync reads the implementer reports and the review verdict."""
        for body in (self.body, read(DOC_UPDATER)):
            self.assertIn("steps/code/iter-<n>/implementer*.json", body)
            self.assertIn("steps/review-code/verdict.json", body)
            self.assertNotIn("steps/code/iter-<n>/verify.md", body)

    def test_findings_feed_the_doc_updater_context_with_no_plan_phase_in_between(self):
        no_plan_re = re.compile(r"(?i)(no|never|without)\W{0,20}plan(ner| phase)")
        for m in re.finditer(r"(?i)findings", self.norm):
            window = self.norm[max(0, m.start() - 300):m.end() + 300]
            if ("doc-updater" in window.lower() and "<context>" in window
                    and no_plan_re.search(window)):
                return
        self.fail("docs-sync/SKILL.md must co-locate 'findings', 'doc-updater', "
                  "'<context>' and a no-plan-phase clause within ~300 chars")

    def test_doc_updater_input_contract_still_carries_iteration_2plus_findings(self):
        body_norm = norm(read(DOC_UPDATER))
        self.assertRegex(body_norm, r"on iteration >= 2, the drift-reviewer findings your output must fix")

    def test_doc_updater_charter_still_requires_fixing_every_listed_finding(self):
        self.assertRegex(norm(read(DOC_UPDATER)), r"(?i)fix every finding listed in `<context>` and nothing beyond what your notes cover")

    def test_no_lane_driven_verify_depth_machinery_introduced(self):
        for token in ("verify_depth", "VERIFY_ITERATION_CAP", "TRIVIAL", "COMPLEX"):
            self.assertNotIn(token, self.body)

    def test_resume_never_reintroduces_a_plan_artifact(self):
        self.assertRegex(self.norm, r"(?i)no plan artifact to reuse")
        self.assertNotRegex(self.norm, r"(?i)second planner")


class DriftReviewerIndependenceUnchangedTest(unittest.TestCase):
    """The drift-reviewer still re-derives the doc impact from the same
    six-input contract itself — it never trusts the doc-updater's doc-delta
    list as the definition of completeness."""

    def test_skill_review_phase_keeps_independent_rederivation_clause(self):
        body_norm = norm(read(SKILL))
        self.assertIn("re-derives doc impact from the same six-input contract itself", body_norm)
        self.assertIn("not exempt from the independent-re-derivation rule", body_norm)

    def test_drift_reviewer_agent_still_refuses_to_trust_the_doc_updater_report(self):
        body = norm(read(DRIFT_REVIEWER))
        self.assertIn("re-derive the diff-to-doc-impact mapping yourself", body)
        self.assertIn("do not just read the notes' own claims", body)

    def test_six_input_contract_still_read_by_every_phase(self):
        body_norm = norm(read(SKILL))
        self.assertIn("every phase (doc-updater and drift-reviewer alike) reads all six, independently", body_norm)
        doc_updater = norm(read(DOC_UPDATER))
        self.assertIn("the six-input contract below", doc_updater)


if __name__ == "__main__":
    unittest.main()
