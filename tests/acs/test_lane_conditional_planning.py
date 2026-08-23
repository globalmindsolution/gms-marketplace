"""MAR-72 (slice 2 of MAR-69) — /acs:code's coordinator authors `plan.md`
itself on TRIVIAL/SMALL (zero `acs:code-planner` spawns), while STANDARD/
COMPLEX keep MAR-71's one-planner-spawn-per-run behavior unchanged. Also
covers ADR-0074, the ADR-0034 amendment, and the reflection.md/prd.md/
roadmap.md updates this ticket requires.

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
CODE_PLANNER = os.path.join(PLUGIN, "agents", "code-planner.md")
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


def section(body, start_heading, end_heading):
    return body[body.index(start_heading):body.index(end_heading)]


def mermaid_block_and_after(body, after_len=800):
    """Return (fenced ```mermaid block text, prose immediately following it)."""
    start = body.index("```mermaid")
    tail = body[start:]
    end_rel = tail.index("```", len("```mermaid"))
    end = start + end_rel + 3
    return body[start:end], body[end:end + after_len]


class NoPlannerSpawnOnFastLanesTest(unittest.TestCase):
    """AC-1: TRIVIAL/SMALL completes with zero planner spawns and a
    coordinator-authored plan.md."""

    @classmethod
    def setUpClass(cls):
        cls.skill_body = read(CODE_SKILL)
        cls.skill_norm = norm(cls.skill_body)
        cls.planner_norm = norm(read(CODE_PLANNER))

    def test_fast_lane_no_spawn_contract_colocated(self):
        for m in re.finditer(r"TRIVIAL/SMALL", self.skill_norm):
            window = self.skill_norm[max(0, m.start() - 400):m.end() + 400]
            if ("SMALL" in window
                    and re.search(r"(?i)zero.{0,60}(acs:code-planner|planner).{0,20}spawn", window)
                    and "coordinator" in window.lower()
                    and "plan.md" in window):
                return
        self.fail(
            "code/SKILL.md must co-locate TRIVIAL/SMALL, a zero-planner-"
            "spawn phrase, 'coordinator', and 'plan.md' within one bounded "
            "window")

    def test_exactly_one_clause_is_lane_qualified_standard_complex(self):
        for m in re.finditer(r"exactly one", self.skill_norm, re.IGNORECASE):
            window = self.skill_norm[max(0, m.start() - 200):m.end() + 200]
            if "acs:code-planner" in window and re.search(r"(?i)\bwhole run\b", window):
                self.assertRegex(
                    window, r"(?i)STANDARD/COMPLEX",
                    "the surviving 'exactly one ... acs:code-planner ... "
                    "whole run' clause must be lane-qualified to "
                    "STANDARD/COMPLEX")
                return
        self.fail("no 'exactly one ... acs:code-planner ... whole run' clause found")

    def test_mar71_pin_still_passes_after_lane_qualification(self):
        # Regression: the original MAR-71 pin (test_code_loop_topology.py)
        # must still find the phrase intact within an 80-char window.
        for m in re.finditer(r"exactly one", self.skill_norm, re.IGNORECASE):
            window = self.skill_norm[max(0, m.start() - 80):m.end() + 80]
            if "acs:code-planner" in window and re.search(r"(?i)\b(run|whole run)\b", window):
                return
        self.fail("MAR-71 pin regressed: exactly-one/acs:code-planner/run "
                  "co-location lost")

    def test_code_planner_states_standard_complex_only_spawn(self):
        self.assertRegex(
            self.planner_norm,
            r"(?i)spawned only.{0,40}STANDARD.{0,10}(/|or).{0,10}COMPLEX")


class CoordinatorPlanContractTest(unittest.TestCase):
    """AC-2: code-verifier's 4 plan-dependent dimensions have a valid input
    on TRIVIAL/SMALL."""

    @classmethod
    def setUpClass(cls):
        cls.skill_body = read(CODE_SKILL)
        cls.skill_norm = norm(cls.skill_body)
        cls.verifier_norm = norm(read(CODE_VERIFIER))

    def test_fast_lane_contract_names_six_planner_headings(self):
        for heading in ("## Spec analysis", "## Executor tasks & file map",
                        "## Test strategy", "## Documentation map",
                        "## Risks", "## Verifier checklist"):
            self.assertIn(heading, self.skill_body,
                          "code/SKILL.md fast-lane contract must name %r" % heading)

    def test_fast_lane_contract_names_five_fold_headings_and_lint_literal(self):
        for heading in ("Scope", "Approach", "API/data changes", "Test plan",
                        "Out of scope"):
            self.assertIn(heading, self.skill_body)
        self.assertIn(
            'structure_lint.py --sections "Scope; Approach; API/data '
            'changes; Test plan; Out of scope"', self.skill_body)

    def test_fast_lane_contract_states_no_content_stub_rule(self):
        self.assertRegex(
            self.skill_norm,
            r"(?i)never.{0,60}(empty|placeholder|see ticket)")

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


class FoldInvariantsTest(unittest.TestCase):
    """Regression pins: the fold's activating condition, mandatory clauses,
    D-3/D-4 statements survive the MAR-72 edit."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(CODE_SKILL)
        cls.norm = norm(cls.body)

    def test_fold_activating_condition_stays_lane_agnostic(self):
        self.assertIsNotNone(
            re.search(r"specs/.{0,40}(absent or empty|empty or absent)", self.body))
        self.assertNotRegex(
            self.body, r"(?i)TRIVIAL.{0,10}(or|/).{0,10}SMALL lanes? with no specs")

    def test_mandatory_verbatim_clauses_survive(self):
        self.assertIn(
            "no separate /acs:create-spec invocation and no separate "
            "create-spec planner subagent", self.norm)
        self.assertIn(
            "every ticket.acceptance_criteria entry maps to at least one "
            "test the folded plan will write", self.norm)

    def test_escalation_never_retro_spawns_planner(self):
        self.assertRegex(
            self.norm, r"(?i)never.{0,60}(spawn|retro-spawn)s? a planner")

    def test_no_plan_xml_message_on_fast_lanes(self):
        self.assertRegex(
            self.norm,
            r'(?i)no.{0,20}<task phase="plan">.{0,100}(message is sent|is sent)')


if __name__ == "__main__":
    unittest.main()
