"""MAR-151 (Decision C of epic MAR-149, ADR 0065) — skill + verifier
structure-gate wiring (spec 02).

Prose-contract tests over the enforcement/wiring layer for configurable
design/spec templates. The config/data foundation (schema keys, built-in
templates, docs) is spec 01, covered by
`test_configurable_doc_templates_schema.py`; THIS module pins the wiring:

- `create-design/SKILL.md` sources `required_sections` from the resolved
  `formats.design_template` / `enforcement.design_sections` (3-tier resolution
  identical to `create-pr`'s `pr_description_template`), no longer a hardcoded
  literal — while KEEPING the six-heading literal present as the default
  (the byte-identical guard in the schema module greps this SKILL for it).
- `create-spec/SKILL.md` gains a `formats.spec_template` resolution and a
  `required_sections` constraint (from `enforcement.spec_sections`) on the
  execute AND verify tasks, alongside the existing `audience_style_profile`.
- `create-design-verifier.md` dim `structure` notes the section list is the
  CONFIGURED one.
- `create-spec-verifier.md` gains a NET-NEW blocking `structure` dimension
  invoking `structure_lint.py` — layered ON TOP of MAR-150's `audience-style`
  dimension (which stays intact), taking the verifier from 5 -> 6 dimensions.
- `docs/architecture/lld/contracts.md` notes create-spec now runs
  `structure_lint`.

Stdlib-only (os, re, unittest); reuses the bold/backtick dimension-label
matching style of `test_structure_audience_verifiers.py`.

Run:  python3 -m unittest tests.acs.test_configurable_doc_templates_wiring -v
"""

import os
import re
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN = os.path.join(REPO_ROOT, "plugins", "acs")
AGENTS = os.path.join(PLUGIN, "agents")
SKILLS = os.path.join(PLUGIN, "skills")
DOCS = os.path.join(REPO_ROOT, "docs")

CREATE_DESIGN_SKILL = os.path.join(SKILLS, "create-design", "SKILL.md")
CREATE_SPEC_SKILL = os.path.join(SKILLS, "create-spec", "SKILL.md")
CREATE_DESIGN_VERIFIER = os.path.join(AGENTS, "create-design-verifier.md")
CREATE_SPEC_VERIFIER = os.path.join(AGENTS, "create-spec-verifier.md")
CONTRACTS = os.path.join(DOCS, "architecture", "lld", "contracts.md")

HELPER_PATH = "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/structure_lint.py"

DESIGN_SIX = ("Context & constraints", "Options considered", "Decision & rationale",
              "Architecture", "Impact & risks", "Rollout/migration")


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _label_pattern(label):
    esc = re.escape(label)
    return r"(?:\*\*`%s`\*\*|\*\*%s\*\*|`%s`)" % (esc, esc, esc)


def dimension_present(body, label):
    return re.search(r"(?m)^\d+\.\s+%s" % _label_pattern(label), body) is not None


def dimension_block(body, label):
    start_m = re.search(r"(?m)^\d+\.\s+%s" % _label_pattern(label), body)
    assert start_m is not None, "dimension %r not found" % label
    rest = body[start_m.end():]
    end_m = re.search(r"(?m)^(?:\d+\.\s+(?:\*\*|`)|Also verify|#{2,3} )", rest)
    end = start_m.end() + end_m.start() if end_m else len(body)
    return body[start_m.start():end]


def verify_region(body):
    """From the `### Verify` heading to the next top-level `## ` heading."""
    m = re.search(r"(?m)^#{2,3}\s+(?:Verify|Phase: verify).*$", body)
    assert m is not None, "no Verify-phase heading found"
    rest = body[m.end():]
    end_m = re.search(r"(?m)^## ", rest)
    end = m.end() + end_m.start() if end_m else len(body)
    return body[m.start():end]


def execute_region(body):
    """From the `### Execute`/`### Phase: execute` heading to the next `## `/`### `."""
    m = re.search(r"(?m)^#{2,3}\s+(?:Execute|Phase: execute).*$", body)
    assert m is not None, "no Execute-phase heading found"
    rest = body[m.end():]
    end_m = re.search(r"(?m)^#{2,3} ", rest)
    end = m.end() + end_m.start() if end_m else len(body)
    return body[m.start():end]


class CreateDesignSkillResolutionTest(unittest.TestCase):
    """AC-1/AC-3/AC-4: create-design SKILL resolves formats.design_template
    (3-tier) and sources required_sections from enforcement.design_sections —
    while keeping the six-heading literal present as the byte-identical
    default."""

    def setUp(self):
        self.skill = read(CREATE_DESIGN_SKILL)

    def test_references_design_template_key(self):
        self.assertIn("formats.design_template", self.skill,
                      "create-design SKILL must name the configured formats.design_template key")

    def test_describes_three_tier_resolution(self):
        # identical resolution to create-pr's pr_description_template
        self.assertIn("${CLAUDE_PLUGIN_ROOT}/templates/", self.skill)
        self.assertIn(".acs/templates/", self.skill)
        self.assertIn("absolute path", self.skill)

    def test_required_sections_sourced_from_enforcement_key(self):
        self.assertIn("enforcement.design_sections", self.skill,
                      "required_sections must be sourced from enforcement.design_sections, "
                      "not a sole hardcoded literal")

    def test_six_heading_literal_still_present(self):
        # R-A: the schema module's byte-identical test greps THIS constraint;
        # spec 02 must NOT delete it — only reframe it as the default.
        m = re.search(r'<constraint name="required_sections">(.*?)</constraint>',
                      self.skill, re.DOTALL)
        self.assertIsNotNone(m, "create-design SKILL must keep the required_sections literal")
        literal = m.group(1).replace("&amp;", "&")
        literal = re.sub(r"\s+", " ", literal).strip()
        self.assertEqual(literal, "; ".join(DESIGN_SIX))

    def test_audience_style_profile_unchanged(self):
        # whitespace-robust: the constraint legitimately wraps across lines.
        collapsed = re.sub(r"\s+", " ", self.skill)
        self.assertIn(
            '<constraint name="audience_style_profile">reviewers '
            '(decision + trade-off narrative)</constraint>',
            collapsed,
            "MAR-150 audience_style_profile constraint must remain intact")


class CreateSpecSkillResolutionTest(unittest.TestCase):
    """AC-1/AC-3: create-spec SKILL gains a spec_template resolution and a
    required_sections constraint on the execute AND verify tasks, alongside
    the existing audience_style_profile."""

    def setUp(self):
        self.skill = read(CREATE_SPEC_SKILL)

    def test_references_spec_template_key(self):
        self.assertIn("formats.spec_template", self.skill,
                      "create-spec SKILL must name the configured formats.spec_template key")

    def test_describes_three_tier_resolution(self):
        self.assertIn("${CLAUDE_PLUGIN_ROOT}/templates/", self.skill)
        self.assertIn(".acs/templates/", self.skill)
        self.assertIn("absolute path", self.skill)

    def test_required_sections_sourced_from_enforcement_key(self):
        self.assertIn("enforcement.spec_sections", self.skill)

    def test_required_sections_constraint_declared(self):
        self.assertIn('name="required_sections"', self.skill,
                      "create-spec SKILL must declare a required_sections constraint")

    def test_execute_and_verify_both_carry_required_sections(self):
        self.assertIn("required_sections", execute_region(self.skill),
                      "execute-phase region must reference required_sections")
        self.assertIn("required_sections", verify_region(self.skill),
                      "verify-phase region must reference required_sections")

    def test_audience_style_profile_still_present(self):
        # MAR-150 declaration must not be disturbed.
        self.assertIn("audience_style_profile", self.skill)
        self.assertIn("implementation-contract", self.skill)


class CreateDesignVerifierConfiguredSectionsTest(unittest.TestCase):
    """AC-3: create-design-verifier dim `structure` still invokes structure_lint
    AND now notes the section list is the CONFIGURED one."""

    def setUp(self):
        self.body = read(CREATE_DESIGN_VERIFIER)
        self.block = dimension_block(self.body, "structure")

    def test_structure_still_invokes_helper_and_blocks(self):
        self.assertIn(HELPER_PATH, self.block)
        self.assertIn('severity="blocking"', self.block)
        self.assertIn('dimension="structure"', self.block)

    def test_structure_notes_configured_list(self):
        self.assertIn("design_sections", self.block,
                      "create-design-verifier structure dim must note the "
                      "configured enforcement.design_sections list")


class CreateSpecVerifierStructureDimensionTest(unittest.TestCase):
    """AC-3: create-spec-verifier gains a NET-NEW blocking `structure`
    dimension (dimension 6), layered on top of MAR-150's audience-style
    dimension (which stays intact)."""

    def setUp(self):
        self.body = read(CREATE_SPEC_VERIFIER)

    def test_structure_dimension_present(self):
        self.assertTrue(dimension_present(self.body, "structure"),
                        "create-spec-verifier must declare a numbered structure dimension")

    def test_structure_invokes_helper_and_blocks(self):
        block = dimension_block(self.body, "structure")
        self.assertIn(HELPER_PATH, block,
                      "structure dimension must invoke structure_lint.py")
        self.assertIn('severity="blocking"', block)
        self.assertIn('dimension="structure"', block)

    def test_structure_runs_over_specs_not_design(self):
        block = dimension_block(self.body, "structure")
        self.assertIn("specs/", block,
                      "create-spec structure dim must lint the spec files")

    def test_dimension_count_is_six(self):
        # regex mirrors test_skill_contracts.py's pin (bold-led numbered items)
        dims = re.findall(r"(?m)^[0-9]+\.\s+\*\*", self.body)
        self.assertEqual(len(dims), 6,
                         "create-spec-verifier must declare exactly 6 numbered "
                         "dimensions (5 + MAR-151 structure); found %d" % len(dims))

    def test_audience_style_dimension_intact(self):
        # MAR-150 negative guard: audience-style still present, still blocking.
        self.assertTrue(dimension_present(self.body, "audience-style"))
        block = dimension_block(self.body, "audience-style")
        self.assertIn('severity="blocking"', block)
        self.assertIn('dimension="audience-style"', block)

    def test_input_contract_names_required_sections(self):
        input_contract = self.body.split("## Check dimensions")[0]
        self.assertIn("required_sections", input_contract,
                      "create-spec-verifier input-contract <constraints> must name "
                      "the required_sections constraint the coordinator now passes")


class ContractsNoteTest(unittest.TestCase):
    """AC-5: contracts.md notes create-spec now runs structure_lint / carries a
    blocking structure dimension, mirroring create-design."""

    def test_contracts_notes_create_spec_structure_lint(self):
        text = read(CONTRACTS)
        self.assertRegex(
            text, r"create-spec[^\n]*structure_lint",
            "contracts.md must note create-spec now runs structure_lint")


if __name__ == "__main__":
    unittest.main()
