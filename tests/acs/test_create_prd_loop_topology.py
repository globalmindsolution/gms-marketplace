"""/acs:create-prd runs surveyor -> author -> review (the per-skill topology).

MAR-305 first dropped the per-iteration re-plan (plan once, then execute ->
verify). ADR-0092 followed that to its conclusion: a PRD is a document, so a
plan for it is a second copy of the writing. The per-skill topology then
split the one executor along its own seam: a read-only **surveyor** runs on
iteration 1 only (mode, outline, open questions, the three corroboration
sections the reviewer's deterministic floor parses) and writes the authoring
notes; the coordinator relays the open questions to the user; an **author**
writes the set from the notes plus the answers; a **reviewer** judges it.
Iterations 2+ are author <- reviewer findings -> reviewer; the surveyor never
re-runs. This module pins that topology so neither a planner nor a second
survey can creep back in through prose, the registry, or an agent file.

Run:  python3 -m unittest tests.acs.test_create_prd_loop_topology -v
"""

import os
import re
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN = os.path.join(REPO_ROOT, "plugins", "acs")
PRD_SKILL = os.path.join(PLUGIN, "skills", "create-prd", "SKILL.md")
AGENTS = os.path.join(PLUGIN, "agents")
PRD_SURVEYOR = os.path.join(AGENTS, "create-prd-surveyor.md")
PRD_AUTHOR = os.path.join(AGENTS, "create-prd-author.md")
PRD_REVIEWER = os.path.join(AGENTS, "create-prd-reviewer.md")
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


class TopologyTest(unittest.TestCase):

    def test_the_registry_declares_surveyor_author_reviewer(self):
        self.assertEqual(sorted(acs_lib.skill_agents()["create-prd"]),
                         ["author", "reviewer", "surveyor"])

    def test_the_role_kinds(self):
        self.assertEqual(acs_lib.role_kind("surveyor"), "survey")
        self.assertEqual(acs_lib.role_kind("author"), "write")
        self.assertEqual(acs_lib.role_kind("reviewer"), "judge")

    def test_the_three_agent_files_exist_and_no_triad_file_does(self):
        for path in (PRD_SURVEYOR, PRD_AUTHOR, PRD_REVIEWER):
            self.assertTrue(os.path.isfile(path), path)
        for stale in ("planner", "executor", "verifier"):
            self.assertFalse(os.path.exists(
                os.path.join(AGENTS, "create-prd-%s.md" % stale)), stale)

    def test_the_prose_spawns_the_three_roles_and_no_planner(self):
        body = read(PRD_SKILL)
        for role in ("surveyor", "author", "reviewer"):
            self.assertIn("acs:create-prd-%s" % role, body)
            self.assertIn('phase="%s"' % role, body)
        for stale in ("planner", "executor", "verifier"):
            self.assertNotIn("acs:create-prd-%s" % stale, body)
        self.assertNotRegex(body, r"(?i)spawn (exactly )?one .{0,40}planner")
        self.assertNotIn("iter-1-plan.md", body)
        self.assertNotIn('phase="plan"', body)

    def test_the_prose_names_the_loop(self):
        self.assertRegex(norm(read(PRD_SKILL)), r"(?i)surveyor → author → review")

    def test_each_role_uses_its_models_tier(self):
        body = norm(read(PRD_SKILL))
        for role, tier in (("surveyor", "planner"), ("author", "executor"),
                           ("reviewer", "verifier")):
            self.assertEqual(acs_lib.model_tier(role), tier)
            self.assertRegex(body, r"\| %s \|[^|]*\|[^|]*\| `context\.models\.%s` \|"
                             % (role, tier))

    def test_no_unnegated_replan_instruction(self):
        negating = re.compile(r"(?i)never|no |not|without|instead of")
        for m in re.finditer(r"(?i)re-?plan\w*", read(PRD_SKILL)):
            window = read(PRD_SKILL)[max(0, m.start() - 60):m.end() + 60]
            self.assertRegex(window, negating,
                             "un-negated 're-plan' instruction found: %r" % window)


class SurveyAuthorReviewLoopTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.body = read(PRD_SKILL)
        cls.norm = norm(cls.body)

    def test_cap_is_three_author_review_rounds(self):
        self.assertIn("max 3 iterations", self.norm)
        self.assertIn("After iteration 3", self.norm)
        self.assertRegex(self.norm, r"(?i)an iteration counts:\*\* one author -> review round")

    def test_iteration_one_surveys_then_the_author_writes(self):
        self.assertRegex(self.norm, r"(?i)Iteration 1 runs the surveyor once")
        self.assertRegex(self.norm, r"(?i)returns `needs_input` with the open questions before any file is written")
        self.assertRegex(self.norm, r"(?i)findings go verbatim into the next author `<task>` `<context>`")

    def test_the_surveyor_writes_the_notes_the_author_and_reviewer_read(self):
        self.assertIn("iter-<n>/authoring.md", self.body)
        surveyor = read(PRD_SURVEYOR)
        self.assertIn("iter-1/authoring.md", surveyor)
        self.assertIn("## Survey — what you establish (iteration 1)", surveyor)
        for heading in ("## Code evidence", "## Answer fidelity", "## Roadmap milestones"):
            self.assertIn(heading, surveyor)
        self.assertIn("iter-<n>/surveyor.json", surveyor)
        author = read(PRD_AUTHOR)
        self.assertIn("steps/create-prd/iter-1/authoring.md", author)
        self.assertIn("iter-<n>/authoring.md", author)
        reviewer = read(PRD_REVIEWER)
        self.assertIn("--plan steps/create-prd/iter-<n>/authoring.md", reviewer)
        self.assertNotIn("iter-<n>-plan.md", reviewer)

    def test_the_surveyor_is_read_only_and_never_writes_the_prd(self):
        surveyor = norm(read(PRD_SURVEYOR))
        self.assertIn("You are read-only on the repo", surveyor)
        self.assertIn("You never write `prd.md` or `roadmap.md` yourself", surveyor)

    def test_findings_feed_the_author_context_and_the_survey_never_reruns(self):
        rerun_re = re.compile(r"(?i)surveyor (does not|never) (re-?run|runs? again)")
        for m in re.finditer(r"(?i)findings", self.norm):
            window = self.norm[max(0, m.start() - 300):m.end() + 300]
            if ("author" in window.lower() and "<context>" in window
                    and rerun_re.search(window)):
                return
        self.fail("create-prd/SKILL.md must co-locate 'findings', 'author', "
                  "'<context>' and a surveyor-does-not-re-run clause within ~300 chars")

    def test_author_charter_still_requires_fixing_every_listed_finding(self):
        self.assertIn("On iteration 2+, fix EVERY finding listed in `<context>`", norm(read(PRD_AUTHOR)))

    def test_no_lane_driven_review_depth_machinery_introduced(self):
        for token in ("verify_depth", "VERIFY_ITERATION_CAP", "TRIVIAL", "COMPLEX"):
            self.assertNotIn(token, self.body)

    def test_resume_never_reruns_the_survey_or_reintroduces_a_plan(self):
        window = section(self.norm, "## Resume & reconcile", "## Reflection loop")
        self.assertNotIn("iter-1-plan.md", window)
        self.assertRegex(window, r"(?i)never re-runs the surveyor once its notes exist")


class ReviewerIndependenceUnchangedTest(unittest.TestCase):

    def test_skill_review_phase_keeps_artifact_only_independence_clause(self):
        body_norm = norm(read(PRD_SKILL))
        self.assertIn("with ONLY artifact references", body_norm)
        self.assertIn("never the author's reasoning", body_norm)
        self.assertIn("repo_root", body_norm)

    def test_reviewer_agent_still_refuses_to_trust_the_author_report(self):
        body = read(PRD_REVIEWER)
        self.assertIn("Never rubber-stamp: re-run every cheap check yourself", norm(body))
        self.assertIn("prd_conformance_check.py", body)
        self.assertIn("independently and deterministically re-checks three families", norm(body))


def slice_table(body, first_id):
    """{slice id: (dimension numbers, owns-the-run-of cell)} from the reviewer
    slice table that opens with the `first_id` row."""
    rows = {}
    for line in body.splitlines():
        m = re.match(r"^\| `([a-z-]+)` \| ([^|]+) \| (.+) \|$", line)
        if m:
            rows[m.group(1)] = ([int(n) for n in re.findall(r"(?:^|, )(\d+) ", m.group(2))],
                                m.group(3))
    assert first_id in rows, "slice table with %r row not found" % first_id
    return rows


class ParallelFanOutTest(unittest.TestCase):
    """The parallel fan-out: sliced surveys over disjoint repo areas, ONE
    author (the PRD and roadmap are coupled), sliced reviewers over disjoint
    dimensions, every join by `acs.py notes merge`, a synthesis after each."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(PRD_SKILL)
        cls.norm = norm(cls.body)

    def test_fan_out_spawns_in_one_message_and_joins_deterministically(self):
        self.assertIn("### Fan-out — slices, the join, the cap", self.body)
        self.assertRegex(self.norm, r"spawn N instances of the SAME agent in ONE message")
        self.assertIn('slice="<id>"', self.body)
        self.assertIn("iter-<n>/<role>-<id>-message.xml", self.body)
        self.assertIn('hooks/scripts/acs.py" notes merge', self.body)
        self.assertIn("never prose-merging by you", self.norm)

    def test_cap_is_four_with_waves(self):
        self.assertIn("`max_parallel = 4`", self.body)
        self.assertRegex(self.norm, r"(?i)beyond the cap, run the slices in waves of 4")

    def test_survey_slices_partition_rule(self):
        self.assertIn("#### Survey slices — brownfield/amend over disjoint repo areas", self.body)
        self.assertRegex(self.norm, r"\*\*two or more disjoint top-level areas\*\*")
        self.assertIn("Greenfield never slices", self.norm)
        self.assertIn("Slice `lead` owns", self.norm)
        self.assertIn("no directory belongs to two slices", self.norm)
        self.assertIn('<constraint name="survey_area">', self.body)
        self.assertIn("--out <partition>/steps/create-prd/iter-1/authoring.md", self.norm)
        self.assertIn("iter-1/authoring-lead.md", self.body)

    def test_one_grouped_ask_for_all_survey_slices(self):
        self.assertIn("ONE grouped clarification-ledger ask", self.norm)
        self.assertIn("The open questions of ALL surveyor slices are one batch", self.norm)

    def test_survey_consumer_keeps_a_synthesis_section(self):
        self.assertIn("a mechanical join is not a synthesis", self.norm)
        self.assertIn("`## Synthesis`", self.body)
        self.assertIn("never silently picks one side", self.norm)
        author = norm(read(PRD_AUTHOR))
        self.assertIn("**Synthesis of a sliced survey**", author)
        self.assertIn("`## Synthesis`", author)
        self.assertIn("Never silently pick one side", author)

    def test_the_author_is_never_sliced_and_says_why(self):
        self.assertIn("**One author, never sliced — on every iteration.**", self.norm)
        self.assertIn("`roadmap.md` derives from `prd.md`", self.norm)
        self.assertNotRegex(self.norm, r"(?i)MAY run two authors in parallel")
        self.assertNotIn("-<k>", read(PRD_AUTHOR))
        self.assertIn("No integration pass follows", self.norm)

    def test_reviewer_slices_cover_every_dimension_exactly_once(self):
        rows = slice_table(self.body, "substance")
        self.assertEqual(sorted(rows), ["delta", "floor", "substance"])
        dims = sorted(d for ds, _ in rows.values() for d in ds)
        self.assertEqual(dims, list(range(1, 12)))

    def test_the_deterministic_floor_runs_in_exactly_one_slice(self):
        rows = slice_table(self.body, "substance")
        for checker in ("prd_conformance_check.py", "structure_lint.py"):
            owners = [sid for sid, (_, owns) in rows.items() if checker in owns]
            self.assertEqual(owners, ["floor"], checker)
        self.assertEqual(sorted(rows["floor"][0]), [1, 7, 10])

    def test_reviewer_slices_join_dedup_and_pass_rule(self):
        self.assertIn("--out <partition>/steps/create-prd/iter-<n>/reviewer.md", self.norm)
        for sid in ("substance", "floor", "delta", "dedup"):
            self.assertIn("iter-<n>/reviewer-%s.md" % sid, self.body)
        self.assertIn("the same location and the same defect", self.norm)
        self.assertIn("keeping the one with the higher severity", self.norm)
        self.assertIn("`## De-duplicated findings`", self.body)
        self.assertIn("the iteration passes only if EVERY slice returned "
                      "`status=\"completed\"` with zero blocking findings", self.norm)
        self.assertIn("never \"pass with a missing slice\"", self.norm)

    def test_resume_reruns_only_missing_slices(self):
        window = section(self.norm, "## Resume & reconcile", "## Reflection loop")
        self.assertIn("re-run ONLY the slices whose own report is missing", window)
        self.assertIn("<role>-slices.json", window)

    def test_agents_carry_their_slice_sections(self):
        surveyor = norm(read(PRD_SURVEYOR))
        self.assertIn("## When you are one slice", surveyor)
        self.assertIn("iter-1/authoring-<id>.md", surveyor)
        self.assertIn("iter-1/surveyor-<id>.json", surveyor)
        self.assertIn('phase="surveyor" slice="<id>"', surveyor)
        reviewer = norm(read(PRD_REVIEWER))
        self.assertIn("## When you are one slice", reviewer)
        self.assertIn("Run ONLY the listed dimensions", reviewer)
        self.assertIn("iter-<n>/reviewer-<id>.md", reviewer)
        self.assertIn('<constraint name="dimensions">', reviewer)
        self.assertIn('phase="reviewer" slice="<id>"', reviewer)
        self.assertIn("police grounding", reviewer)


if __name__ == "__main__":
    unittest.main()
