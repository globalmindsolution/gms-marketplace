"""/acs:create-docs runs author -> review, one pair per doc set, with no
planner (ADR-0092 class D, ADR-0094).

The four doc-set legs each ran a plan-once/execute-verify loop with a planner
whose deliverable was a plan for a template-bootstrapped document -- a second
copy of the writing. The folded skill owns exactly two subagents: an author
that writes each set and a reviewer that judges it. This module pins that
topology so a planner (or the retired generic executor/verifier names) cannot
creep back in through prose, the agents tree, or an agent file.

Run:  python3 -m unittest tests.acs.test_create_docs_loop_topology -v
"""

import os
import re
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN = os.path.join(REPO_ROOT, "plugins", "acs")
SKILL = os.path.join(PLUGIN, "skills", "create-docs", "SKILL.md")
AGENTS = os.path.join(PLUGIN, "agents")
AUTHOR = os.path.join(AGENTS, "create-docs-author.md")
REVIEWER = os.path.join(AGENTS, "create-docs-reviewer.md")
sys.path.insert(0, os.path.join(PLUGIN, "hooks", "scripts"))

import acs_lib  # noqa: E402


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def norm(text):
    return re.sub(r"\s+", " ", text)


def contract():
    """The skill's contract: SKILL.md plus the references it points at.

    The resume/handoff seam moved into `references/resume-and-handoff.md` --
    a fresh run that finishes in one session never reads it. The pin is that
    the rule EXISTS, not which file states it.
    """
    import glob
    parts = [read(SKILL)]
    refs = os.path.join(PLUGIN, "skills", "create-docs", "references", "*.md")
    parts.extend(read(q) for q in sorted(glob.glob(refs)))
    return "\n".join(parts)


class NoPlannerTest(unittest.TestCase):

    def test_the_tree_declares_author_and_reviewer_only(self):
        self.assertEqual(acs_lib.skill_agents()["create-docs"], ["author", "reviewer"])

    def test_the_two_agent_files_exist_and_no_planner_does(self):
        self.assertTrue(os.path.isfile(AUTHOR))
        self.assertTrue(os.path.isfile(REVIEWER))
        for role in ("planner", "executor", "verifier"):
            self.assertFalse(os.path.exists(os.path.join(AGENTS, "create-docs-%s.md" % role)))
        for leg in ("quality", "operations", "principles", "standards"):
            for role in ("planner", "executor", "verifier", "author", "reviewer"):
                self.assertFalse(os.path.exists(os.path.join(AGENTS, "create-%s-%s.md" % (leg, role))),
                                 "the leg agent files were folded away")

    def test_the_prose_never_spawns_a_planner(self):
        body = read(SKILL)
        self.assertNotIn("acs:create-docs-planner", body)
        self.assertNotRegex(body, r"(?i)spawn (exactly )?one .{0,40}planner")
        self.assertNotIn("iter-1-plan.md", body)
        self.assertNotIn("iter-<n>-plan.md", body)

    def test_the_prose_says_nothing_plans_ahead_of_the_author(self):
        body = norm(read(SKILL))
        self.assertRegex(body, r"(?i)author → review, one pair per set")
        self.assertRegex(body, r"(?i)Nothing plans the set ahead of the author")


class AuthorReviewLoopTest(unittest.TestCase):

    def test_cap_is_three_author_review_rounds(self):
        body = norm(read(SKILL))
        self.assertRegex(body, r"(?i)author → review, max 3 iterations")
        self.assertRegex(body, r"(?i)an iteration counts:\*\* one author → review round")

    def test_iteration_one_authors_and_later_ones_remediate(self):
        body = norm(read(SKILL))
        self.assertRegex(body, r"(?i)iteration 1'?s author reads the upstream inputs, decides the mode, authors the set")
        self.assertRegex(body, r"(?i)findings go verbatim into the next author `<task>` `<context>`")

    def test_phase_is_the_role(self):
        body = read(SKILL)
        self.assertIn('<task skill="create-docs" phase="author"', body)
        self.assertIn('phase="reviewer"', body)
        self.assertNotIn('phase="execute"', body)
        self.assertNotIn('phase="verify"', body)
        self.assertIn('<result skill="create-docs" phase="author"', read(AUTHOR))
        self.assertIn('<result skill="create-docs" phase="reviewer"', read(REVIEWER))

    def test_each_role_names_its_model_tier(self):
        body = norm(read(SKILL))
        self.assertIn("`context.models.executor.model` / `.effort` for the author", body)
        self.assertIn("`context.models.verifier.model` / `.effort` for the reviewer", body)

    def test_the_author_writes_authoring_notes_and_the_reviewer_reads_them(self):
        skill = read(SKILL)
        self.assertIn("iter-<n>/authoring.md", skill)
        self.assertIn("iter-<n>/author.json", skill)
        self.assertIn("iter-<n>/reviewer.md", skill)
        author = read(AUTHOR)
        self.assertIn("iter-<n>/authoring.md", author)
        self.assertIn("steps/create-docs/iter-<n>/author.json", author)
        self.assertIn("- **Upstream inventory**", author)
        reviewer = read(REVIEWER)
        self.assertIn("iter-<n>/authoring.md", reviewer)
        self.assertIn("steps/create-docs/iter-<n>/reviewer.md", reviewer)
        self.assertRegex(reviewer, r"(?m)^4\.\s+\*\*authoring-conformance\*\*")
        for body in (skill, author, reviewer):
            self.assertNotIn("execute.json", body)
            self.assertNotIn("verify.md", body)

    def test_the_set_travels_in_constraints_not_in_agent_names(self):
        for path in (AUTHOR, REVIEWER):
            body = read(path)
            self.assertIn("`doc_set`", body)
            self.assertRegex(norm(body), r"(?i)the same agent file serves every set")

    def test_resume_never_reintroduces_a_plan_artifact(self):
        body = norm(contract())
        self.assertRegex(body, r"(?i)an author with no review → review it")
        self.assertNotRegex(body, r"(?i)second planner")


class ParallelFanOutTest(unittest.TestCase):
    """Parallel writers are one author per set (never finer); the reviewer's
    eight dimensions run as two dimension slices per set, joined by
    `acs.py notes merge`, with every slice required to pass."""

    #: slice id -> the dimension numbers it owns, as the SKILL.md table says.
    SLICES = {"files": (1, 3, 5, 7), "content": (2, 4, 6, 8)}

    @classmethod
    def setUpClass(cls):
        cls.skill = read(SKILL)
        cls.norm = norm(cls.skill)
        cls.contract = norm(contract())
        cls.reviewer = read(REVIEWER)

    def test_writer_partition_rule_is_one_author_per_set(self):
        self.assertIn("**Partition rule — one writer per set, never finer.**", self.skill)
        self.assertRegex(self.norm, r"(?i)two authors cannot write the same file")
        self.assertRegex(self.norm, r"(?i)A set is NOT split further into per-file authors")

    def test_every_instance_of_a_phase_spawns_in_one_message(self):
        self.assertRegex(self.norm, r"(?i)spawn every instance of a phase in ONE message")
        self.assertRegex(self.norm, r"(?i)join their outputs before the next phase starts")

    def test_dimension_slice_table_covers_the_eight_dimensions_once(self):
        seen = []
        for slice_id, dims in self.SLICES.items():
            row = re.search(r"(?m)^\| `%s` \| ([^|]+)\|" % slice_id, self.skill)
            self.assertIsNotNone(row, "no table row for dimension slice %r" % slice_id)
            got = tuple(int(n) for n in re.findall(r"\b(\d)\b", row.group(1)))
            self.assertEqual(got, dims)
            seen.extend(got)
        self.assertEqual(sorted(seen), list(range(1, 9)))

    def test_each_checker_runs_in_exactly_one_slice(self):
        self.assertRegex(self.skill, r"(?m)^\| `files` \|.*`structure_lint\.py` \|$")
        self.assertRegex(self.skill, r"(?m)^\| `content` \|.*`citation_check\.py` \|$")

    def test_review_join_is_notes_merge_into_reviewer_md(self):
        self.assertIn('acs.py" notes merge', self.skill)
        self.assertIn("--out <partition>/steps/create-docs/iter-<n>/reviewer.md", self.skill)
        self.assertIn("iter-<n>/reviewer-files.md", self.skill)
        self.assertIn("iter-<n>/reviewer-content.md", self.skill)
        self.assertRegex(self.norm, r"(?i)never by merging prose yourself")

    def test_sliced_task_carries_slice_and_dimensions(self):
        self.assertIn('<task skill="create-docs" phase="reviewer" slice="files"', self.skill)
        self.assertIn('<constraint name="dimensions">', self.skill)
        self.assertIn("iter-<n>/reviewer-<slice>-message.xml", self.skill)

    def test_pass_rule_requires_every_slice(self):
        self.assertRegex(self.norm, r"(?i)passes only when EVERY one of its dimension slices returned `status=\"completed\"` with zero blocking findings")
        self.assertRegex(self.norm, r"(?i)every slice'?s findings \(after de-duplication\) go verbatim to that set'?s next author")
        self.assertIn('never "pass with a missing slice"', self.norm)

    def test_cap_holds_at_four_reviewers_per_message(self):
        self.assertIn("max_parallel = 2", self.skill)
        self.assertRegex(self.norm, r"(?i)at most 4 reviewer instances")
        self.assertRegex(self.contract, r"(?i)2 × `max_parallel` = \*\*4\*\* reviewer instances")

    def test_resume_reruns_only_missing_slices(self):
        self.assertRegex(self.contract, r"(?i)re-run ONLY the dimension slices whose `iter-<n>/reviewer-<slice>\.md` is missing")

    def test_judge_slices_are_de_duplicated_after_the_join(self):
        self.assertIn("**De-duplicate after the join.**", self.skill)
        self.assertRegex(self.norm, r"(?i)drop a finding that cites the same location .{0,40}and the same defect as another slice'?s finding, keeping the one with the higher severity")
        self.assertIn("## De-duplicated findings", self.skill)

    def test_sets_are_fully_independent_so_no_integration_pass(self):
        self.assertIn("**No integration pass — the sets are fully independent.**", self.skill)
        self.assertNotIn('slice="integration"', self.skill)
        self.assertRegex(self.norm, r"(?i)keeps out of the same batch")

    def test_reviewer_agent_knows_how_to_be_one_slice(self):
        self.assertIn("## When you are one slice", self.reviewer)
        body = norm(self.reviewer)
        self.assertIn("steps/create-docs/iter-<n>/reviewer-<slice>.md", body)
        self.assertRegex(body, r"(?i)Run ONLY the listed dimensions")
        self.assertRegex(body, r"(?i)Police grounding in every slice")
        self.assertRegex(body, r"(?i)`structure_lint\.py` only when you own 7")
        self.assertRegex(body, r"(?i)`citation_check\.py` only when you own 4")
        self.assertIn('<result skill="create-docs" phase="reviewer" slice="content"', self.reviewer)


class ReviewerIndependenceTest(unittest.TestCase):

    def test_reviewer_judges_from_artifacts_only(self):
        body = norm(read(REVIEWER))
        self.assertRegex(body, r"(?i)never see the author'?s reasoning")
        self.assertRegex(body, r"(?i)NEVER rubber-stamp")

    def test_every_finding_blocks_except_the_waived_register(self):
        body = norm(read(REVIEWER))
        self.assertIn("ALL findings block", body)
        self.assertIn('severity="info"', body)


if __name__ == "__main__":
    unittest.main()
