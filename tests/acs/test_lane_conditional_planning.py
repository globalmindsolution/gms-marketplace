"""MAR-72 (slice 2 of MAR-69) — the lane-conditional plan phase: its author
is the coordinator itself on TRIVIAL/SMALL (zero planner spawns), while
STANDARD/COMPLEX keep MAR-71's one-planner-spawn-per-run behavior unchanged.
The skills-independence refactor moved that phase out of /acs:code into
/acs:create-impl-plan, so the fork's own prose pins now live in
tests/acs/test_create_impl_plan.py::LaneForkTest and
::PlanPhaseContractTest; what remains here is this ticket's documentation
half — ADR-0074, the ADR-0034 amendment, and the reflection.md/prd.md/
roadmap.md updates — plus the two /acs:code-side pins that survive the move.

Every assertion is by file plus whitespace-normalized substring/regex, never
by line number (line numbers drift as prose is revised) — the house style of
tests/acs/test_code_loop_topology.py. Stdlib only (glob, os, re, unittest).
Run:
  python3 -m unittest tests.acs.test_lane_conditional_planning -v
"""

import glob
import os
import re
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN = os.path.join(REPO_ROOT, "plugins", "acs")
CODE_SKILL = os.path.join(PLUGIN, "skills", "code", "SKILL.md")
CODE_VERIFIER = os.path.join(PLUGIN, "agents", "code-verifier.md")
ADR_DIR = os.path.join(REPO_ROOT, "docs", "adr")
ADR_README = os.path.join(ADR_DIR, "README.md")
REFLECTION = os.path.join(REPO_ROOT, "docs", "requirements", "functional", "reflection.md")
PRD = os.path.join(REPO_ROOT, "docs", "product", "prd.md")
ROADMAP = os.path.join(REPO_ROOT, "docs", "product", "roadmap.md")


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def norm(body):
    """Collapse whitespace runs so markdown line-wrap can never break a
    phrase-spanning match."""
    return re.sub(r"\s+", " ", body)


def mermaid_block_and_after(body, after_len=800):
    """Return (fenced ```mermaid block text, prose immediately following it)."""
    start = body.index("```mermaid")
    tail = body[start:]
    end_rel = tail.index("```", len("```mermaid"))
    end = start + end_rel + 3
    return body[start:end], body[end:end + after_len]


class CoordinatorPlanContractTest(unittest.TestCase):
    """AC-2, /acs:code side: the plan artifact still reaches the verifier's
    inputs in every lane, and the verifier still judges a coordinator-authored
    plan identically. The plan-artifact CONTENT contract (six headings, the
    five fold sections, the no-stub rule) moved with the phase — see
    tests/acs/test_create_impl_plan.py::PlanPhaseContractTest."""

    @classmethod
    def setUpClass(cls):
        cls.skill_body = read(CODE_SKILL)
        cls.skill_norm = norm(cls.skill_body)
        cls.verifier_norm = norm(read(CODE_VERIFIER))

    def test_plan_artifact_still_passed_to_verifier_inputs_every_lane(self):
        start = re.search(r"(?m)^### Verify \(per iteration\)", self.skill_body)
        end = re.search(r"(?m)^### Coverage hard fail", self.skill_body)
        self.assertIsNotNone(start)
        self.assertIsNotNone(end)
        verify_section = self.skill_body[start.start():end.start()]
        self.assertIn("plan.md", verify_section)

    def test_verifier_states_coordinator_authored_no_waiver(self):
        self.assertRegex(self.verifier_norm, r"(?i)coordinator-authored")
        self.assertRegex(
            self.verifier_norm,
            r"(?i)never waived.{0,40}authorship|no waiver.{0,40}authorship|"
            r"authorship grounds")
        self.assertRegex(self.verifier_norm, r"(?i)dimensions 1, 8, 9,? and 13")


class Adr0074Test(unittest.TestCase):
    """AC-3: ADR-0074 written and linked."""

    def test_adr_0074_exists_exactly_once(self):
        matches = glob.glob(os.path.join(ADR_DIR, "0074-*.md"))
        self.assertEqual(len(matches), 1,
                          "expected exactly one docs/adr/0074-*.md file, found %r" % matches)

    def test_adr_0074_has_required_sections(self):
        matches = glob.glob(os.path.join(ADR_DIR, "0074-*.md"))
        self.assertTrue(matches, "docs/adr/0074-*.md must exist")
        body = read(matches[0])
        for token in ("**Status**", "## Context", "## Decision", "## Consequences"):
            self.assertIn(token, body)

    def test_adr_readme_links_0074(self):
        matches = glob.glob(os.path.join(ADR_DIR, "0074-*.md"))
        self.assertTrue(matches, "docs/adr/0074-*.md must exist")
        filename = os.path.basename(matches[0])
        readme = read(ADR_README)
        self.assertIn("[0074](%s)" % filename, readme)

    def test_adr_0034_carries_mar72_amendment_naming_0074(self):
        matches = glob.glob(os.path.join(ADR_DIR, "0034-*.md"))
        self.assertTrue(matches, "docs/adr/0034-*.md must exist")
        body = read(matches[0])
        self.assertIn("MAR-72", body)
        self.assertIn("0074", body)

    def test_reflection_references_0074(self):
        body = read(REFLECTION)
        self.assertIn("0074", body)


class ReflectionConditionalTriadTest(unittest.TestCase):
    """AC-4: reflection.md updated (triad list, loop-back statement, mermaid)."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(REFLECTION)
        cls.norm = norm(cls.body)

    def test_twelve_survives_and_code_marked_conditional_triad(self):
        self.assertIn("**twelve**", self.body)
        self.assertNotIn("**eleven**", self.body)
        self.assertRegex(self.norm, r"(?i)`code`.{0,40}conditional triad")

    def test_loop_back_bullet_states_fast_lane_no_planner_case(self):
        self.assertRegex(
            self.norm,
            r"(?i)TRIVIAL/SMALL.{0,300}no planner to feed back into")
        self.assertRegex(
            self.norm,
            r"(?i)never retro-spawns? a planner")

    def test_mermaid_has_lane_conditional_edge_and_prose_names_spawn(self):
        block, after = mermaid_block_and_after(self.body)
        self.assertRegex(block, r"(?i)TRIVIAL/SMALL")
        self.assertRegex(
            norm(after),
            r"(?i)lane-conditional.{0,80}MAR-72|MAR-72.{0,80}lane-conditional")
        self.assertRegex(norm(after), r"(?i)STANDARD/COMPLEX")
        self.assertRegex(norm(after), r"(?i)zero.{0,20}`?code-planner`?.{0,10}spawns?")


class G14ScopingTest(unittest.TestCase):
    """AC-5: G14 claims scoped honestly per lane."""

    @classmethod
    def setUpClass(cls):
        matches = glob.glob(os.path.join(ADR_DIR, "0074-*.md"))
        cls.adr_body = read(matches[0]) if matches else ""
        cls.adr_norm = norm(cls.adr_body)

    def test_adr_names_g14_iteration_cap_and_disclaims_wholesale_reduction(self):
        self.assertTrue(self.adr_body, "docs/adr/0074-*.md must exist and be readable")
        self.assertIn("G14", self.adr_body)
        self.assertRegex(self.adr_norm, r"ADR-0034|0034-light-verify-one-iteration-cap")
        self.assertRegex(self.adr_norm, r"(?i)\*\*1\*\* iteration|1-iteration cap")
        self.assertRegex(
            self.adr_norm,
            r"(?i)not.{0,20}a.{0,20}wholesale.{0,40}(reduction|≥\s*60%)")

    def test_adr_names_g16_and_four_plan_dependent_verifier_inputs(self):
        self.assertIn("G16", self.adr_body)
        self.assertRegex(self.adr_norm, r"(?i)completeness")
        self.assertRegex(self.adr_norm, r"(?i)architecture")
        self.assertRegex(self.adr_norm, r"(?i)system design")
        self.assertRegex(self.adr_norm, r"(?i)audience-style")

    def test_prd_g14_metric_text_byte_identical_to_main(self):
        body = read(PRD)
        self.assertIn(
            "A trivial, human-supervised ticket is delivered for substantially "
            "less wall-clock time and token/cost than the full pipeline. "
            "**Metric:** median wall-clock time AND median token/cost for a "
            "TRIVIAL-lane ticket are each reduced **≥ 60%** vs the same "
            "ticket run through the full plan-execute-verify ladder, "
            "measured on the dogfood repo within **1 release** of the "
            "capability shipping.",
            body)

    def test_prd_g16_metric_text_byte_identical_to_main(self):
        body = read(PRD)
        self.assertIn(
            "Reducing process volume on simple work must not lower "
            "defect-catch. The verifier gates on every lane "
            "(autonomous-first); lighter lanes reduce only the "
            "verify-iteration ceiling, never whether the verifier or the "
            "TDD/coverage gate runs. **Metric:** **0 regression** in the "
            "code verifier's defect-catch rate",
            body)


class ProductDocFactsTest(unittest.TestCase):
    """DoD/regression: prd.md and roadmap.md factual claims reconciled."""

    def test_prd_standard_bullet_no_longer_claims_only_verify_depth_differs(self):
        body = read(PRD)
        self.assertNotIn("differing only in **verify\ndepth**", body)
        self.assertNotRegex(body, r"differing only in \*\*verify\s+depth\*\*")

    def test_prd_trivial_bullet_disambiguates_no_separate_planner_subagent(self):
        body_norm = norm(read(PRD))
        self.assertRegex(
            body_norm,
            r"(?i)no separate planner subagent.{0,500}code-planner.{0,200}"
            r"(never spawned|not spawned|zero.{0,20}spawn|also never spawned)")

    def test_roadmap_names_fast_lane_no_planner_behavior(self):
        body_norm = norm(read(ROADMAP))
        self.assertRegex(
            body_norm,
            r"(?i)plans once per run.{0,300}TRIVIAL/SMALL.{0,200}"
            r"(coordinator-authored|zero.{0,20}(code-planner|spawn))")


class FoldMovedOutOfCodeTest(unittest.TestCase):
    """The fold's activating condition, its mandatory clauses and the
    D-3/D-4 statements are pinned against their new home
    (tests/acs/test_create_impl_plan.py); what is pinned here is that they
    left /acs:code rather than being duplicated in it."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(CODE_SKILL)

    def test_fold_prose_no_longer_lives_in_code(self):
        for literal in ("Spec authoring fold",
                        "no separate /acs:create-spec invocation",
                        "structure_lint.py --sections"):
            with self.subTest(literal=literal):
                self.assertNotIn(literal, self.body)

    def test_code_names_create_impl_plan_as_the_plan_author(self):
        self.assertIn("/acs:create-impl-plan", self.body)


if __name__ == "__main__":
    unittest.main()
