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
an agent file. Mirrored tests/acs/test_create_docs_loop_topology.py, which
ADR-0124 removed with its skill.

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

    def test_each_role_is_spawned_under_its_configured_agent_name(self):
        self.assertIn("`context.agents.<role>`", self.norm)
        self.assertIn("generated `acs-docs-sync-<role>` copy", self.norm)
        self.assertNotIn("context.models", self.norm)

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


class ParallelFanOutTest(unittest.TestCase):
    """The doc-updater runs one instance per doc area from iteration 1
    (disjoint by longest-prefix ownership, committing on the shared branch
    with pathspec commits and an index.lock retry); the drift-reviewer's six
    dimensions run as three slices; both joins are `acs.py notes merge`."""

    AREAS = ("requirements", "architecture", "adr", "general")
    SLICES = {"coverage": (1, 6), "content": (2, 3), "placement": (4, 5)}

    @classmethod
    def setUpClass(cls):
        cls.skill = read(SKILL)
        cls.norm = norm(cls.skill)
        cls.doc_updater = read(DOC_UPDATER)
        cls.drift_reviewer = read(DRIFT_REVIEWER)

    def test_one_doc_updater_per_area_from_iteration_one(self):
        self.assertRegex(self.norm, r"(?i)runs \*\*one instance per doc area, from iteration 1\*\*")
        for area in self.AREAS:
            self.assertRegex(self.skill, r"(?m)^\| `%s` \|" % area)
            self.assertIn("iter-<n>/authoring-%s.md" % area, self.skill)

    def test_partition_rule_is_longest_prefix_with_a_general_fallback(self):
        self.assertRegex(self.norm, r"(?i)\*\*longest matching prefix\*\*, and to `general` when none matches")
        self.assertRegex(self.norm, r"(?i)two doc-updaters can never write the same file")

    def test_shared_branch_commits_are_pathspec_scoped_with_lock_retry(self):
        for body in (self.norm, norm(self.doc_updater)):
            self.assertIn('git commit -m "<msg>" -- <paths>', body)
            self.assertRegex(body, r"(?i)never `git add -A`, `git add \.` or `git commit -a`")
            self.assertRegex(body, r"(?i)`index\.lock` contention .{0,120}wait briefly and retry the same command")
            self.assertRegex(body, r"(?i)never delete the lock, never force anything")

    def test_every_instance_of_a_phase_spawns_in_one_message_under_the_cap(self):
        self.assertRegex(self.norm, r"(?i)spawn every instance of a phase in ONE message")
        self.assertIn("`settings.parallel.max_agents` (default 4) instances per message", self.norm)

    def test_both_joins_use_notes_merge(self):
        self.assertIn('acs.py" notes merge', self.skill)
        self.assertIn("--out <partition>/steps/docs-sync/iter-<n>/authoring.md", self.skill)
        self.assertIn("<partition>/steps/docs-sync/iter-<n>/drift-reviewer.md", self.norm)
        self.assertRegex(self.norm, r"(?i)never by merging prose yourself")

    def test_drift_review_slices_cover_the_six_dimensions_once(self):
        seen = []
        for slice_id, dims in self.SLICES.items():
            row = re.search(r"(?m)^\| `%s` \| ([^|]+)\|" % slice_id, self.skill)
            self.assertIsNotNone(row, "no table row for drift-review slice %r" % slice_id)
            got = tuple(int(n) for n in re.findall(r"\b(\d)\b", row.group(1)))
            self.assertEqual(got, dims)
            seen.extend(got)
        self.assertEqual(sorted(seen), list(range(1, 7)))

    def test_pass_rule_requires_every_slice(self):
        self.assertRegex(self.norm, r"(?i)passes only if EVERY slice returned `status=\"completed\"` with zero blocking findings")
        self.assertRegex(self.norm, r"(?i)every slice'?s findings \(after de-duplication\) go verbatim to the next doc-updaters")
        self.assertIn('never "pass with a missing slice"', self.norm)

    def test_open_questions_from_every_area_are_one_grouped_ask(self):
        self.assertRegex(self.norm, r"(?i)resolve ALL the areas'? open questions in ONE grouped ledger ask")

    def test_resume_reruns_only_missing_slices(self):
        self.assertRegex(self.norm, r"(?i)re-runs ONLY the slices whose report is missing")
        self.assertIn("iter-<n>/doc-updater-<area>.json", self.skill)

    def test_integration_pass_runs_after_the_areas_and_before_the_judge(self):
        self.assertIn("**Integration pass — synthesis, not just a join.**", self.skill)
        self.assertIn('`slice="integration"`', self.skill)
        self.assertRegex(self.norm, r"(?i)after every area has returned and BEFORE the drift-reviewer, spawn ONE more `acs:docs-sync-doc-updater`")
        integ = self.skill.index("**Integration pass")
        self.assertLess(integ, self.skill.index("### Drift-review slices"))
        self.assertLess(integ, self.skill.index("**Join.**"),
                        "the notes join includes the integration notes, so it follows the pass")
        self.assertIn("iter-<n>/authoring-integration.md", self.skill)
        self.assertIn("iter-<n>/doc-updater-integration.json", self.skill)

    def test_integration_pass_is_skipped_for_a_single_writer(self):
        self.assertRegex(self.norm, r"(?i)\*\*Skipped when only one area had changes\*\*")

    def test_integration_pass_names_its_seams(self):
        for seam in ("**docs index pages**", "**cross-links between areas**",
                     "**each area's \"Out-of-area impact\" notes**"):
            self.assertIn(seam, self.skill)
        self.assertRegex(self.norm, r"(?i)every out-of-area item must be applied by the owning area or explicitly resolved")
        self.assertRegex(self.norm, r"(?i)It commits only the seam files, with the same pathspec rule")
        self.assertRegex(self.norm, r"(?i)It never rewrites an area'?s substance")

    def test_integration_pass_synthesizes_contradictions(self):
        for body in (self.norm, norm(self.doc_updater)):
            self.assertIn("`## Synthesis`", body)
            self.assertRegex(body, r"(?i)never silently picks? one")

    def test_seam_findings_route_to_the_integration_pass(self):
        self.assertRegex(self.norm, r"(?i)A \*\*seam finding\*\* .{0,200}goes to that iteration'?s integration pass")
        self.assertRegex(norm(self.drift_reviewer), r"(?i)a seam inconsistency .{0,200}is a finding")

    def test_judge_slices_are_de_duplicated_after_the_join(self):
        self.assertIn("**De-duplicate after the join.**", self.skill)
        self.assertRegex(self.norm, r"(?i)drop a finding that cites the same location .{0,40}and the same defect as another slice'?s finding, keeping the one with the higher severity")
        self.assertIn("## De-duplicated findings", self.skill)

    def test_doc_updater_knows_the_integration_role(self):
        self.assertIn('## When you are the integration pass (`slice="integration"`)', self.doc_updater)
        body = norm(self.doc_updater)
        self.assertIn("steps/docs-sync/iter-<n>/doc-updater-integration.json", body)
        self.assertRegex(body, r"(?i)Never rewrite an area'?s substance")
        self.assertIn('`{"file", "what", "why", "areas"}`', body)

    def test_agents_know_how_to_be_one_slice(self):
        self.assertIn("## When you are one slice (a doc area)", self.doc_updater)
        self.assertIn("steps/docs-sync/iter-<n>/authoring-<area>.md", self.doc_updater)
        self.assertIn("steps/docs-sync/iter-<n>/doc-updater-<area>.json", self.doc_updater)
        self.assertIn('<result skill="docs-sync" phase="doc-updater" slice="general"', self.doc_updater)
        self.assertIn("## When you are one slice", self.drift_reviewer)
        body = norm(self.drift_reviewer)
        self.assertIn("steps/docs-sync/iter-<n>/drift-reviewer-<slice>.md", body)
        self.assertRegex(body, r"(?i)Run ONLY the listed dimensions")
        self.assertRegex(body, r"(?i)Police grounding in every slice")
        self.assertRegex(body, r"(?i)the independent re-derivation rule binds every slice")
        self.assertIn('<result skill="docs-sync" phase="drift-reviewer" slice="placement"', self.drift_reviewer)


class StateFragmentTest(unittest.TestCase):
    """`states.docs_committed` is the list of paths SKILL.md and the
    post-hook's result carry, not a boolean; `commits` and `review` are
    declared beside it."""

    def test_docs_committed_is_an_array_of_paths(self):
        import json
        with open(os.path.join(PLUGIN, "skills", "docs-sync", "state.schema.json"), encoding="utf-8") as fh:
            states = json.load(fh)["properties"]["states"]["properties"]
        self.assertEqual(states["docs_committed"]["type"], "array")
        self.assertEqual(states["docs_committed"]["items"], {"type": "string"})
        self.assertEqual(states["commits"]["type"], "array")
        self.assertEqual(set(states["review"]["properties"]), {"iterations", "findings_open", "guard_denials"})
        self.assertIn('"docs_committed": ["docs/api/import.md", "README.md"]', read(SKILL))


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
