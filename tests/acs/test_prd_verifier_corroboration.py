"""Prose-contract tests for MAR-304's create-prd charter contract change:
dimension 7 ("Plan conformance") of `create-prd-verifier.md` gains an
independent, deterministic corroboration floor (the new
`prd_conformance_check.py`, Task 1) plus a mandatory semantic ceiling, and
`create-prd-planner.md` / `create-prd/SKILL.md` / `docs/requirements/
functional/skills.md` mirror the contract change.

Also pins the negative/regression space this ticket must not disturb:
`create-prd-verifier.md` never names `citation_check.py` or `tests/`
literally (AC-4), and its 11 numbered dimensions keep their labels, numbers
and order (`structure`/`audience-style` trailing).

Mirrors the reading/extraction helper shapes from
`test_citation_corroboration_verifiers.py` (`read`, `_label_pattern`,
`dimension_block`, `dimension_present`, `verify_phase_region`).

Stdlib-only (re, os, unittest). Run:
  python3 -m unittest tests.acs.test_prd_verifier_corroboration -v
"""

import os
import re
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN = os.path.join(REPO_ROOT, "plugins", "acs")
AGENTS = os.path.join(PLUGIN, "agents")
SKILLS = os.path.join(PLUGIN, "skills")
DOCS = os.path.join(REPO_ROOT, "docs")

PRD_PLANNER = os.path.join(AGENTS, "create-prd-planner.md")
PRD_VERIFIER = os.path.join(AGENTS, "create-prd-verifier.md")
PRD_SKILL = os.path.join(SKILLS, "create-prd", "SKILL.md")
SKILLS_MD = os.path.join(DOCS, "requirements", "functional", "skills.md")

HELPER_PATH = "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/prd_conformance_check.py"

PRD_VERIFIER_DIMENSIONS = (
    "Required sections", "Feature -> goal traceability",
    "Measurable success metrics", "Prioritization discipline",
    "Constraint consistency", "Roadmap coverage", "Plan conformance",
    "Amend-mode diff discipline", "Iteration 2+ regression check",
)


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _norm(text):
    """Whitespace-normalize (collapse runs, strip ends) for cross-line-wrap
    substring assertions — a prose block line-wrapped by the markdown editor
    must not defeat a phrase check."""
    return re.sub(r"\s+", " ", text).strip()


def _label_pattern(label):
    """A numbered check-dimension label: **bold**, `backtick`, or the
    bold+backtick `**`label`**` form (mirrors the sibling verifier test
    modules' mixed bold/backtick dimension styles)."""
    esc = re.escape(label)
    return r"(?:\*\*`%s`\*\*|\*\*%s\*\*|`%s`)" % (esc, esc, esc)


def dimension_block(body, label, next_label=None):
    """Extract a numbered check-dimension list item: from the line matching
    `^\\d+. **label**` up to (not including) the next numbered item (or, when
    `next_label` is given, up to that specific item)."""
    start_m = re.search(r"(?m)^\d+\.\s+%s" % _label_pattern(label), body)
    assert start_m is not None, "dimension %r not found" % label
    rest = body[start_m.end():]
    if next_label:
        end_m = re.search(r"(?m)^\d+\.\s+%s" % _label_pattern(next_label), rest)
    else:
        end_m = re.search(r"(?m)^(?:\d+\.\s+(?:\*\*|`)|Also verify|#{2,3} )", rest)
    end = start_m.end() + end_m.start() if end_m else len(body)
    return body[start_m.start():end]


def dimension_present(body, label):
    """True if `label` is a numbered check-dimension entry (bold, backtick, or
    bold+backtick-wrapped)."""
    return re.search(r"(?m)^\d+\.\s+%s" % _label_pattern(label), body) is not None


def verify_phase_region(skill_md_body, skill_name):
    """Bounded window over the SKILL.md text that describes what gets
    spawned/passed to the verifier: from the first line naming the Verify
    phase to the next top-level (`##`) heading."""
    m = re.search(r"(?m)^(?:#{2,3}\s+(?:Verify|Phase: verify).*|3\.\s+\*\*Verify\*\*.*)$",
                  skill_md_body)
    assert m is not None, "no Verify-phase heading/list-item found in %s/SKILL.md" % skill_name
    rest = skill_md_body[m.end():]
    end_m = re.search(r"(?m)^## ", rest)
    end = m.end() + end_m.start() if end_m else len(skill_md_body)
    return skill_md_body[m.start():end]


def input_contract_section(body):
    """The '## Input contract' section of an agent charter: from its heading
    up to the next top-level heading."""
    m = re.search(r"(?m)^## Input contract$", body)
    assert m is not None, "no '## Input contract' heading found"
    rest = body[m.end():]
    end_m = re.search(r"(?m)^## ", rest)
    end = m.end() + end_m.start() if end_m else len(body)
    return body[m.start():end]


def contract_bullet(section_text, tag):
    """A top-level `- \\`<tag>\\` ...` bullet within a bounded section, up to
    (not including) the next top-level `- \\`` bullet."""
    m = re.search(r"(?m)^-\s+`%s`.*$" % re.escape(tag), section_text)
    assert m is not None, "%r bullet not found" % tag
    rest = section_text[m.end():]
    end_m = re.search(r"(?m)^-\s+`", rest)
    end = m.end() + end_m.start() if end_m else len(section_text)
    return section_text[m.start():end]


class Dimension7ContractTest(unittest.TestCase):
    """AC-2: dimension 7 stays `7. **Plan conformance**`; its block invokes
    the new deterministic script with its full flag set, maps every stderr
    finding and exit 2 to a blocking Plan-conformance finding, names all
    three rule families, and states the mandatory semantic ceiling
    (including the every-N/A-judged rule and the greenfield code-evidence
    carve-out)."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(PRD_VERIFIER)
        cls.block = _norm(dimension_block(cls.body, "Plan conformance"))

    def test_dimension_seven_still_plan_conformance(self):
        self.assertIsNotNone(
            re.search(r"(?m)^7\.\s+\*\*Plan conformance\*\*", self.body),
            "dimension 7 must stay exactly '7. **Plan conformance**'")

    def test_invokes_the_new_script(self):
        self.assertIn(HELPER_PATH, self.block)

    def test_all_six_flags_named(self):
        for flag in ("--plan", "--mode", "--repo-root", "--clarifications",
                     "--prd", "--roadmap"):
            with self.subTest(flag=flag):
                self.assertIn(flag, self.block)

    def test_added_heading_flag_scoped_to_amend(self):
        self.assertIn("--added-heading", self.block)
        self.assertIn("amend", self.block.lower())

    def test_maps_findings_and_exit_two_to_blocking_plan_conformance(self):
        self.assertIn('severity="blocking" dimension="Plan conformance"', self.block)
        self.assertIn("exit 2", self.block)

    def test_names_all_three_families(self):
        for family in ("code-evidence", "answer-fidelity", "roadmap-outline"):
            with self.subTest(family=family):
                self.assertIn(family, self.block)

    def test_states_mandatory_semantic_ceiling(self):
        self.assertIn("not contradicted", self.block)
        self.assertIn("substantiates", self.block)
        self.assertIn("maps to the intended epic", self.block)

    def test_every_na_must_be_judged_never_silently_accepted(self):
        lowered = self.block.lower()
        self.assertIn("n/a", lowered)
        self.assertIn("never silently accepted", lowered)

    def test_greenfield_code_evidence_never_a_block(self):
        lowered = self.block.lower()
        self.assertIn("n/a in greenfield", lowered)
        self.assertIn("never a block", lowered)


class VerifierInputContractTest(unittest.TestCase):
    """D8: the verify-task `<inputs>` bullet names `clarifications.json`; the
    `<constraints>` bullet names the repo root."""

    @classmethod
    def setUpClass(cls):
        cls.section = input_contract_section(read(PRD_VERIFIER))

    def test_inputs_name_clarifications_json(self):
        bullet = contract_bullet(self.section, "<inputs>")
        self.assertIn("clarifications.json", bullet)

    def test_constraints_name_repo_root(self):
        bullet = contract_bullet(self.section, "<constraints>")
        self.assertIn("repo_root", bullet)


class PlannerContractTest(unittest.TestCase):
    """D7: the required-heading list names the three new sections; each
    one-line grammar appears verbatim (including the greenfield
    `Code evidence: N/A` form); the ADR-0012 canonical block is untouched."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(PRD_PLANNER)

    def test_required_heading_list_names_three_new_sections(self):
        m = re.search(r"(?s)Required headings:.*?\n\n", self.body)
        self.assertIsNotNone(m, "planner 'Required headings:' paragraph not found")
        paragraph = _norm(m.group(0))
        for heading in ("## Code evidence", "## Answer fidelity", "## Roadmap milestones"):
            with self.subTest(heading=heading):
                self.assertIn(heading, paragraph)

    def test_code_evidence_grammar_line_verbatim(self):
        self.assertIn(
            '- <claim text> — `<relative-path>[:<line>|:<line-start>-<line-end>]` — "<verbatim excerpt>"',
            self.body)

    def test_greenfield_code_evidence_na_form_stated(self):
        self.assertIn(
            "Code evidence: N/A — greenfield, no code to cite", _norm(self.body))

    def test_answer_fidelity_grammar_lines_verbatim(self):
        self.assertIn('- C-<n> — <prd.md|roadmap.md> — "<verbatim anchor text>"', self.body)
        self.assertIn("- C-<n> N/A: <why this answer produces no anchor>", self.body)

    def test_roadmap_milestones_grammar_line_verbatim(self):
        self.assertIn(
            '- Milestone: "### M2.6 — v0.3.5–v0.3.7 fast-follows — '
            'complete tracker & PR metadata sync; dynamic lane correctness"',
            self.body)

    def test_adr_0012_canonical_block_untouched(self):
        # md5-identical across six planners (test_doc_consistency_step.py);
        # here we just re-assert the exact heading and its immediately
        # following sentence are still present byte-for-byte.
        self.assertIn(
            "### Design-time doc-consistency step (ADR 0012)", self.body)
        self.assertIn(
            "1. Read the related slice of the doc graph", self.body)
        self.assertIn(
            '"kind": "staleness"', self.body)


class SkillMirrorTest(unittest.TestCase):
    """create-prd/SKILL.md's plan-task example names the three new plan
    sections; its verify paragraph names `clarifications.json`, the repo
    root, and the `git diff -- <prd_path>` derivation of `--added-heading`."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(PRD_SKILL)
        cls.verify_region = verify_phase_region(cls.body, "create-prd")

    def test_plan_task_example_names_three_new_sections(self):
        m = re.search(r"(?m)^\s*<objective>.*</objective>\s*$", self.body)
        self.assertIsNotNone(m, "plan-task <objective> line not found")
        for heading in ("Code evidence", "Answer fidelity", "Roadmap milestones"):
            with self.subTest(heading=heading):
                self.assertIn(heading, m.group(0))

    def test_verify_paragraph_names_clarifications_and_repo_root(self):
        norm = _norm(self.verify_region)
        self.assertIn("clarifications.json", norm)
        self.assertIn("repo_root", norm)

    def test_verify_paragraph_names_added_heading_git_diff_derivation(self):
        norm = _norm(self.verify_region)
        self.assertIn("--added-heading", norm)
        self.assertIn("git diff -- <settings.prd_path>", norm)

    def test_loop_topology_unchanged(self):
        self.assertRegex(
            self.body.lower(), r"plan -> execute -> verify",
            "create-prd/SKILL.md must still carry the per-iteration re-spawn sentence")


class Drift1Test(unittest.TestCase):
    """C-4(ii): the DRIFT-1 stop-reason example is repaired from '7 of 9' to
    '9 of 11'."""

    def test_nine_of_eleven_present(self):
        body = read(PRD_VERIFIER)
        self.assertIn("9 of 11 dimensions pass, 2 blocking findings", body)

    def test_seven_of_nine_gone(self):
        body = read(PRD_VERIFIER)
        self.assertNotIn("7 of 9 dimensions", body)


class RequirementsBulletTest(unittest.TestCase):
    """C-4(i): the `/create-prd` section of docs/requirements/functional/
    skills.md names the corroboration mechanism and prd_conformance_check.py."""

    @classmethod
    def setUpClass(cls):
        body = read(SKILLS_MD)
        m = re.search(r"(?m)^## `/create-prd` \(product-level\)$", body)
        assert m is not None, "'/create-prd' section not found in skills.md"
        rest = body[m.end():]
        end_m = re.search(r"(?m)^## ", rest)
        end = m.end() + end_m.start() if end_m else len(body)
        cls.section = body[m.start():end]

    def test_names_corroboration_mechanism(self):
        self.assertIn("corroboration", self.section.lower())

    def test_names_the_new_script(self):
        self.assertIn("prd_conformance_check.py", self.section)


class CitationCheckUntouchedTest(unittest.TestCase):
    """AC-4: create-prd-verifier.md never names citation_check.py or tests/
    literally; citation_check.py's own public surface (heading name, rule
    strings, usage string) is unchanged by this ticket."""

    def test_no_citation_check_literal(self):
        body = read(PRD_VERIFIER)
        self.assertNotIn("citation_check.py", body)

    def test_no_tests_literal(self):
        body = read(PRD_VERIFIER)
        self.assertNotIn("tests/", body)

    def test_citation_check_upstream_heading_unchanged(self):
        import sys
        sys.path.insert(0, os.path.join(PLUGIN, "hooks", "scripts"))
        import citation_check  # noqa: E402
        self.assertEqual(citation_check._UPSTREAM_HEADING, "Upstream inventory")
        self.assertEqual(
            citation_check.main.__doc__,
            "CLI entry point: parse --plan/--root, print findings+manifest, return the exit code.")

    def test_citation_check_rule_strings_unchanged(self):
        body = read(os.path.join(PLUGIN, "hooks", "scripts", "citation_check.py"))
        for rule in ("citation-unresolved", "citation-excerpt-not-found",
                     "citation-inventory-empty"):
            with self.subTest(rule=rule):
                self.assertIn('"%s"' % rule, body)

    def test_citation_check_usage_string_unchanged(self):
        body = read(os.path.join(PLUGIN, "hooks", "scripts", "citation_check.py"))
        self.assertIn(
            'usage = ("usage: citation_check.py --plan <plan.md> "\n'
            '              "--root <name>=<path> [--root <name>=<path> ...]")',
            body)


class DimensionOrderUnchangedTest(unittest.TestCase):
    """AC-4/K4: all 9 pre-existing dimension labels remain, in order, and
    `structure`/`audience-style` stay the trailing pair — no dimension
    renamed, renumbered or reordered by this ticket's rewrite of dimension
    7's body."""

    def test_all_nine_pre_existing_labels_present(self):
        body = read(PRD_VERIFIER)
        for label in PRD_VERIFIER_DIMENSIONS:
            with self.subTest(dimension=label):
                self.assertTrue(
                    dimension_present(body, label),
                    "dimension %r must remain present" % label)

    def test_dimensions_in_original_order(self):
        body = read(PRD_VERIFIER)
        positions = []
        for label in PRD_VERIFIER_DIMENSIONS:
            m = re.search(r"(?m)^\d+\.\s+%s" % _label_pattern(label), body)
            self.assertIsNotNone(m, "dimension %r not found" % label)
            positions.append(m.start())
        self.assertEqual(positions, sorted(positions),
                          "dimensions must stay in their original relative order")

    def test_structure_then_audience_style_trailing(self):
        body = read(PRD_VERIFIER)
        structure_m = re.search(r"(?m)^10\.\s+%s" % _label_pattern("structure"), body)
        audience_m = re.search(r"(?m)^11\.\s+%s" % _label_pattern("audience-style"), body)
        self.assertIsNotNone(structure_m, "dimension 10 'structure' not found")
        self.assertIsNotNone(audience_m, "dimension 11 'audience-style' not found")
        self.assertLess(structure_m.start(), audience_m.start())


class Adr0081DecisionRecordTest(unittest.TestCase):
    """AC-1: docs/adr/0081-...md exists, is Accepted, and names all nine
    decision records; docs/adr/README.md carries a 0081 row (Task 3)."""

    ADR_PATH = os.path.join(
        DOCS, "adr", "0081-create-prd-plan-conformance-corroboration-three-family-mechanism.md")
    ADR_README = os.path.join(DOCS, "adr", "README.md")

    @classmethod
    def setUpClass(cls):
        assert os.path.isfile(cls.ADR_PATH), "%s does not exist" % cls.ADR_PATH
        cls.body = read(cls.ADR_PATH)

    def test_adr_file_exists_and_is_accepted(self):
        self.assertIn("**Status**: Accepted", self.body)

    def test_all_nine_decision_records_named(self):
        for record in ("D1-A", "D2-a", "D3.1/D3.2-a", "D4-b+ii", "D5-fold",
                        "D6", "D7", "D8", "D9"):
            with self.subTest(record=record):
                self.assertIn(record, self.body)

    def test_readme_carries_0081_row(self):
        readme = read(self.ADR_README)
        self.assertIn("0081", readme)


if __name__ == "__main__":
    unittest.main()
