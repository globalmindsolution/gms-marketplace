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


if __name__ == "__main__":
    unittest.main()
