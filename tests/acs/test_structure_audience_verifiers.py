"""MAR-150 — audience-style verifier dimension advisory -> BLOCKING + waiver
+ extend to create-spec (reverses MAR-138 / ADR 0057's advisory carve-out).

Prose-contract tests over the 8 producer `*-verifier.md` agents that declare
an `audience_style_profile` (create-prd, create-architecture, create-design,
create-principles, create-standards, create-quality, create-operations,
create-requirements): each carries an APPENDED, deterministic, blocking
`structure` dimension (invokes structure_lint.py) and — after this change — a
BLOCKING `audience-style` dimension (`severity="blocking"` for an UNWAIVED
register mismatch; a coordinator-recorded waiver via
`clarify.py --source assumption` makes it `severity="info"`, which does not
block). ADR 0057's advisory carve-out sentences ("except the advisory" /
"except the sanctioned") are reversed in every producer charter.

create-spec is extended net-new (AC-2): `create-spec/SKILL.md` declares an
`audience_style_profile` (`engineers (implementation-contract prose)`) forwarded
into its verify task, and `create-spec-verifier.md` gains a NET-NEW blocking
`audience-style` dimension — scoped to audience-style only (no `structure`
dimension; MAR-151 adds that). create-project stays N/A (AC-3) — locked here
by a negative test. create-design/SKILL.md is unchanged (clarification C-1):
it has no advisory carve-out to reverse, only the `audience_style_profile`
declaration, which stays.

Reuses the bold/backtick dimension-label helpers (`read`, `_label_pattern`,
`dimension_block`, `dimension_present`, `verify_phase_region`); the label
matcher additionally handles create-spec-verifier's `**`label`**` bold+backtick
form.

Stdlib-only (re, os, unittest). Run:
  python3 -m unittest tests.acs.test_structure_audience_verifiers -v
"""

import os
import re
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN = os.path.join(REPO_ROOT, "plugins", "acs")
AGENTS = os.path.join(PLUGIN, "agents")
SKILLS = os.path.join(PLUGIN, "skills")
DOCS = os.path.join(REPO_ROOT, "docs")

HELPER_PATH = "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/structure_lint.py"

CREATE_PROJECT_VERIFIER = os.path.join(AGENTS, "create-project-verifier.md")
CREATE_PROJECT_SKILL = os.path.join(SKILLS, "create-project", "SKILL.md")
CREATE_SPEC_VERIFIER = os.path.join(AGENTS, "create-spec-verifier.md")
CREATE_SPEC_SKILL = os.path.join(SKILLS, "create-spec", "SKILL.md")
CREATE_DESIGN_SKILL = os.path.join(SKILLS, "create-design", "SKILL.md")

ADR_0063 = os.path.join(
    DOCS, "adr",
    "0063-audience-style-verifier-dimension-advisory-to-blocking-create-spec.md")
CHANGELOG = os.path.join(PLUGIN, "CHANGELOG.md")

# verifier path -> (last pre-existing dimension label, all listed dimension labels)
VERIFIERS = {
    "create-prd-verifier.md": (
        "Iteration 2+ regression check",
        (
            "Required sections", "Feature -> goal traceability",
            "Measurable success metrics", "Prioritization discipline",
            "Constraint consistency", "Roadmap coverage", "Plan conformance",
            "Amend-mode diff discipline", "Iteration 2+ regression check",
        ),
    ),
    "create-architecture-verifier.md": (
        "docs-only-changeset",
        (
            "doc-set-completeness", "prd-coverage", "codebase-match",
            "mermaid-diagrams", "internal-consistency",
            "diagram-prose-agreement", "hld-lld-consistency",
            "plan-conformance", "docs-only-changeset",
        ),
    ),
    "create-design-verifier.md": (
        "completeness",
        ("alternatives", "consistency", "feasibility", "nfr", "completeness"),
    ),
    "create-principles-verifier.md": (
        "consistency",
        (
            "doc-set-completeness", "architecture-conformance",
            "required-sections", "plan-conformance", "docs-only-changeset",
            "consistency",
        ),
    ),
    "create-standards-verifier.md": (
        "consistency",
        (
            "doc-set-completeness", "architecture-conformance",
            "required-sections", "plan-conformance", "docs-only-changeset",
            "consistency",
        ),
    ),
    "create-quality-verifier.md": (
        "consistency",
        (
            "doc-set-completeness", "architecture-conformance",
            "required-sections", "plan-conformance", "docs-only-changeset",
            "consistency",
        ),
    ),
    "create-operations-verifier.md": (
        "consistency",
        (
            "doc-set-completeness", "architecture-conformance",
            "required-sections", "plan-conformance", "docs-only-changeset",
            "consistency",
        ),
    ),
    "create-requirements-verifier.md": (
        "Interactive-confirm discipline",
        (
            "Required-file-presence", "Mode-conformance", "Plan-conformance",
            "Iteration 2+ regression check",
            "Coverage (≥90%, 0 silent omissions)", "Citation (100%)",
            "DRAFT marker", "No-fabrication",
            "Functional/non-functional routing spot-check",
            "Augment-only-absent / no-overwrite",
            "Interactive-confirm discipline", "structure", "audience-style",
        ),
    ),
}

# every audience-style-gated verifier: the 8 producers + net-new create-spec.
AUDIENCE_VERIFIERS = list(VERIFIERS) + ["create-spec-verifier.md"]

# SKILL.md name -> whether it uses per-file required_sections:<file> constraints.
# The 7 MAR-138 prose skills whose declarations MAR-150 leaves untouched
# (create-requirements declares its sections differently; create-spec is
# net-new and checked by CreateSpecDeclarationTest below).
SKILLS_MULTI_FILE = {
    "create-prd": False,
    "create-architecture": True,
    "create-design": False,
    "create-principles": False,
    "create-standards": True,
    "create-quality": True,
    "create-operations": True,
}


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _label_pattern(label):
    """A numbered check-dimension label: **bold**, `backtick`, or the
    bold+backtick `**`label`**` form create-spec-verifier's dimensions use
    (the 8 producers mix **bold** and `backtick`; create-spec-verifier wraps
    its labels in both)."""
    esc = re.escape(label)
    return r"(?:\*\*`%s`\*\*|\*\*%s\*\*|`%s`)" % (esc, esc, esc)


def dimension_block(body, label, next_label=None):
    """Extract a numbered check-dimension list item: from the line matching
    `^\\d+. **label**` / `^\\d+. `label`` / `^\\d+. **`label`**` up to (not
    including) the next numbered item (or, when `next_label` is given, up to
    that specific item)."""
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
    phase (`### Verify`, `### Phase: verify`, or the numbered `**Verify**`
    Phases-list item) to the next top-level (`##`) heading."""
    m = re.search(r"(?m)^(?:#{2,3}\s+(?:Verify|Phase: verify).*|3\.\s+\*\*Verify\*\*.*)$",
                  skill_md_body)
    assert m is not None, "no Verify-phase heading/list-item found in %s/SKILL.md" % skill_name
    rest = skill_md_body[m.end():]
    end_m = re.search(r"(?m)^## ", rest)
    end = m.end() + end_m.start() if end_m else len(skill_md_body)
    return skill_md_body[m.start():end]


class StructureDimensionTest(unittest.TestCase):
    """Every one of the 8 producer verifiers carries an appended,
    deterministic, blocking `structure` dimension invoking structure_lint.py.
    Unchanged by MAR-150 — the flip is surgical to audience-style only."""

    def test_all_producers_invoke_helper_and_block(self):
        for fname in VERIFIERS:
            with self.subTest(verifier=fname):
                body = read(os.path.join(AGENTS, fname))
                block = dimension_block(body, "structure")
                self.assertIn(HELPER_PATH, block,
                               "%s structure dimension must invoke %s" % (fname, HELPER_PATH))
                self.assertIn('severity="blocking"', block)
                self.assertIn('dimension="structure"', block)

    def test_no_tests_path_hardcode_anywhere_in_file(self):
        for fname in VERIFIERS:
            with self.subTest(verifier=fname):
                body = read(os.path.join(AGENTS, fname))
                self.assertNotIn("tests/", body)

    def test_architecture_omits_ordered_flag(self):
        # create-architecture's per-file section lists are derived, not
        # skill-declared literal headings — order is never enforced.
        block = dimension_block(read(os.path.join(AGENTS, "create-architecture-verifier.md")),
                                 "structure")
        self.assertNotIn("--ordered", block)


class AudienceStyleDimensionTest(unittest.TestCase):
    """AC-1: every one of the 8 producer verifiers now carries a BLOCKING
    `audience-style` dimension — `severity="blocking"` for an unwaived
    mismatch, and no residual advisory self-description."""

    def test_all_producers_have_blocking_dimension(self):
        for fname in VERIFIERS:
            with self.subTest(verifier=fname):
                body = read(os.path.join(AGENTS, fname))
                block = dimension_block(body, "audience-style")
                self.assertIn('severity="blocking"', block,
                               "%s audience-style dimension must emit a blocking finding" % fname)
                self.assertIn('dimension="audience-style"', block)

    def test_dimension_no_longer_self_describes_as_advisory(self):
        for fname in VERIFIERS:
            with self.subTest(verifier=fname):
                body = read(os.path.join(AGENTS, fname))
                block = dimension_block(body, "audience-style")
                for banned in ("ADVISORY", "never blocking",
                               "the ONE deliberate exception", "still a PASS"):
                    self.assertNotIn(banned, block,
                                      "%s audience-style dimension still reads as advisory (%r)"
                                      % (fname, banned))


class CarveOutTest(unittest.TestCase):
    """AC-1: every ADR-0057 advisory carve-out sentence is reversed — neither
    "except the advisory" nor "except the sanctioned" survives in any producer
    charter, and create-design's two former carve-out anchors now assert
    blocking."""

    def test_no_advisory_carveout_anywhere(self):
        for fname in VERIFIERS:
            with self.subTest(verifier=fname):
                body = read(os.path.join(AGENTS, fname))
                self.assertNotIn("except the advisory", body,
                                  "%s still carries an 'except the advisory' carve-out" % fname)
                self.assertNotIn("except the sanctioned", body,
                                  "%s still carries an 'except the sanctioned' carve-out" % fname)

    def test_design_both_anchors_now_blocking(self):
        # create-design carried the carve-out at TWO anchors (preamble +
        # findings-format); both now assert audience-style blocks with the rest.
        body = read(os.path.join(AGENTS, "create-design-verifier.md"))
        self.assertEqual(
            body.count("including the `audience-style` dimension"), 2,
            "create-design must assert the audience-style dimension blocks at both anchors")


class WaiverClauseTest(unittest.TestCase):
    """AC-4: each of the 9 audience-style dimension bodies (8 producers +
    create-spec) states the block condition is an UNWAIVED mismatch and names
    the clarify-ledger waiver lever."""

    def test_every_dimension_states_unwaived_and_waiver_lever(self):
        for fname in AUDIENCE_VERIFIERS:
            with self.subTest(verifier=fname):
                body = read(os.path.join(AGENTS, fname))
                block = dimension_block(body, "audience-style")
                lowered = block.lower()
                self.assertIn("unwaived", lowered,
                               "%s audience-style dimension must name the UNWAIVED bar" % fname)
                self.assertTrue(
                    "--source assumption" in block or "waiver" in lowered
                    or "waived" in lowered,
                    "%s audience-style dimension must name the waiver lever" % fname)


class DimensionListRegressionTest(unittest.TestCase):
    """Surgical-edit proof: every dimension that existed before this change is
    still present, by name, in each of the 8 producer verifiers, and
    audience-style still follows structure at the end of each list."""

    def test_all_pre_existing_dimensions_present(self):
        for fname, (_last, labels) in VERIFIERS.items():
            body = read(os.path.join(AGENTS, fname))
            for label in labels:
                with self.subTest(verifier=fname, dimension=label):
                    self.assertTrue(
                        dimension_present(body, label),
                        "dimension %r must remain a numbered check-dimension entry in %s"
                        % (label, fname))

    def test_new_dimensions_appended_after_last_pre_existing(self):
        for fname, (last_label, _labels) in VERIFIERS.items():
            with self.subTest(verifier=fname):
                body = read(os.path.join(AGENTS, fname))
                last_block_start = re.search(
                    r"(?m)^\d+\.\s+%s" % _label_pattern(last_label), body).start()
                structure_start = re.search(
                    r"(?m)^\d+\.\s+%s" % _label_pattern("structure"), body).start()
                audience_start = re.search(
                    r"(?m)^\d+\.\s+%s" % _label_pattern("audience-style"), body).start()
                self.assertLess(last_block_start, structure_start,
                                 "%s: structure must be appended after %r" % (fname, last_label))
                self.assertLess(structure_start, audience_start,
                                 "%s: audience-style must directly follow structure" % fname)


class DesignCompletenessDiagramUntouchedTest(unittest.TestCase):
    """MAR-137 no-disturb: create-design dim 5's byte-pinned completeness
    body is not disturbed by MAR-150's audience-style-only edits."""

    def test_completeness_core_text_survives(self):
        body = read(os.path.join(AGENTS, "create-design-verifier.md"))
        block = dimension_block(body, "completeness")
        self.assertIn("all six required sections present and substantive", block)
        self.assertIn(
            "A Mermaid `sequenceDiagram` exists for EVERY new\n"
            "   or changed runtime flow named by the ticket and plan",
            block,
        )


class CreateProjectNegativeTest(unittest.TestCase):
    """AC-3: create-project is explicitly N/A — no structure dimension, no
    audience-style dimension, no structure_lint.py reference, and its SKILL.md
    declares neither required_sections nor audience_style_profile."""

    def test_verifier_has_no_structure_lint_reference(self):
        body = read(CREATE_PROJECT_VERIFIER)
        self.assertNotIn("structure_lint.py", body)

    def test_verifier_has_no_structure_or_audience_style_dimension(self):
        body = read(CREATE_PROJECT_VERIFIER)
        self.assertFalse(dimension_present(body, "structure"))
        self.assertFalse(dimension_present(body, "audience-style"))

    def test_all_eleven_pre_existing_dimensions_untouched(self):
        body = read(CREATE_PROJECT_VERIFIER)
        for label in ("build", "lint", "tests", "coverage-tooling", "vertical-slice",
                       "layout", "tech-stack", "ci", "pre-commit", "repo-hygiene",
                       "plan-conformance"):
            with self.subTest(dimension=label):
                self.assertTrue(dimension_present(body, label))

    def test_skill_declares_neither_constraint(self):
        body = read(CREATE_PROJECT_SKILL)
        self.assertNotIn("required_sections", body)
        self.assertNotIn("audience_style_profile", body)


class SkillDeclarationTest(unittest.TestCase):
    """Each of the producer SKILL.md files that declare an
    `audience_style_profile` still declares required_sections AND a non-empty
    audience_style_profile, both referenced within the verify-phase region."""

    def test_required_sections_declared(self):
        for skill, multi in SKILLS_MULTI_FILE.items():
            with self.subTest(skill=skill):
                body = read(os.path.join(SKILLS, skill, "SKILL.md"))
                names = re.findall(r'name="required_sections(:[^"]+)?"', body)
                self.assertTrue(names, "%s/SKILL.md declares no required_sections constraint"
                                 % skill)
                if multi:
                    self.assertTrue(any(n for n in names),
                                     "%s is multi-file: expected required_sections:<file>" % skill)
                else:
                    self.assertIn("", names,
                                   "%s is single-doc-list: expected a flat required_sections"
                                   % skill)

    def test_audience_style_profile_declared_non_empty(self):
        for skill in SKILLS_MULTI_FILE:
            with self.subTest(skill=skill):
                body = read(os.path.join(SKILLS, skill, "SKILL.md"))
                m = re.search(r'<constraint name="audience_style_profile">([^<]+)</constraint>',
                               body)
                self.assertIsNotNone(m, "%s/SKILL.md declares no audience_style_profile" % skill)
                self.assertTrue(m.group(1).strip(), "%s audience_style_profile is empty" % skill)

    def test_both_referenced_in_verify_phase_region(self):
        for skill in SKILLS_MULTI_FILE:
            with self.subTest(skill=skill):
                body = read(os.path.join(SKILLS, skill, "SKILL.md"))
                region = verify_phase_region(body, skill)
                self.assertIn("required_sections", region,
                               "%s: verify-phase region does not mention required_sections"
                               % skill)
                self.assertIn("audience_style_profile", region,
                               "%s: verify-phase region does not mention audience_style_profile"
                               % skill)


class CreateSpecDeclarationTest(unittest.TestCase):
    """AC-2: create-spec gains the audience gate net-new — SKILL.md declares
    `engineers (implementation-contract prose)` and forwards it into verify;
    create-spec-verifier.md carries a blocking `audience-style` dimension
    appended after `consistency`. MAR-151 (Decision C) subsequently layered
    a blocking `structure` dimension on top (see
    test_verifier_has_structure_dimension_and_lint below)."""

    def test_skill_declares_profile(self):
        body = read(CREATE_SPEC_SKILL)
        m = re.search(r'<constraint name="audience_style_profile">([^<]+)</constraint>', body)
        self.assertIsNotNone(m, "create-spec/SKILL.md declares no audience_style_profile")
        value = m.group(1)
        self.assertIn("engineers", value)
        self.assertIn("implementation-contract", value)

    def test_skill_forwards_profile_into_verify_region(self):
        body = read(CREATE_SPEC_SKILL)
        region = verify_phase_region(body, "create-spec")
        self.assertIn("audience_style_profile", region,
                       "create-spec verify-phase region does not mention audience_style_profile")

    def test_verifier_has_blocking_audience_dimension(self):
        body = read(CREATE_SPEC_VERIFIER)
        self.assertTrue(dimension_present(body, "audience-style"),
                         "create-spec-verifier lacks a numbered audience-style dimension")
        block = dimension_block(body, "audience-style")
        self.assertIn('severity="blocking"', block)
        self.assertIn('dimension="audience-style"', block)

    def test_verifier_audience_appended_after_consistency(self):
        body = read(CREATE_SPEC_VERIFIER)
        consistency_start = re.search(
            r"(?m)^\d+\.\s+%s" % _label_pattern("consistency"), body).start()
        audience_start = re.search(
            r"(?m)^\d+\.\s+%s" % _label_pattern("audience-style"), body).start()
        self.assertLess(consistency_start, audience_start,
                         "create-spec-verifier: audience-style must be appended after consistency")

    def test_verifier_has_structure_dimension_and_lint(self):
        # Serialize guard (design R5): MAR-151 (Decision C) owns the structure
        # dimension for create-spec — now landed, layered on top of MAR-150's
        # audience-style dimension. (This guard was the RED->GREEN flip of the
        # MAR-150-era `test_verifier_has_no_structure_dimension_or_lint`.)
        body = read(CREATE_SPEC_VERIFIER)
        self.assertTrue(dimension_present(body, "structure"),
                         "create-spec-verifier must gain a structure dimension (MAR-151)")
        self.assertIn("structure_lint", body,
                       "create-spec-verifier must reference structure_lint (MAR-151)")

    def test_verifier_input_contract_names_profile(self):
        body = read(CREATE_SPEC_VERIFIER)
        input_contract = body.split("## Check dimensions")[0]
        self.assertIn("audience_style_profile", input_contract,
                       "create-spec-verifier input-contract <constraints> must name audience_style_profile")


class CreateDesignSkillGroundingTest(unittest.TestCase):
    """AC-1 / clarification C-1: create-design/SKILL.md carries no audience-style
    advisory carve-out to reverse (no `severity="info"` audience language) — its
    `audience_style_profile` declaration stays; the flip lives in the verifier
    charters, not this SKILL."""

    def test_skill_has_no_info_severity_carveout(self):
        body = read(CREATE_DESIGN_SKILL)
        self.assertNotIn('severity="info"', body)

    def test_skill_retains_profile_declaration(self):
        body = read(CREATE_DESIGN_SKILL)
        self.assertIn("audience_style_profile", body)


class ADRAndChangelogTest(unittest.TestCase):
    """AC-5: ADR 0063 authored (reverses ADR 0057) and a CHANGELOG entry records
    the advisory -> blocking promotion — under [Unreleased] before a release cut
    or its dated semver section after (a cut legitimately graduates it)."""

    def test_adr_0063_exists_and_references_0057(self):
        self.assertTrue(os.path.exists(ADR_0063),
                         "ADR 0063 (advisory->blocking) is missing at %s" % ADR_0063)
        body = read(ADR_0063)
        self.assertIn("0057", body, "ADR 0063 must reference ADR 0057 as the decision it reverses")

    def test_changelog_records_promotion(self):
        # Durable-invariant CHANGELOG assertion (mirrors ChangelogMar143EntryTest):
        # the MAR-150 audience-style promotion entry lives under [Unreleased] OR
        # the dated semver heading it graduated into at a release cut — never a
        # literal pin to [Unreleased], which churns on every cut.
        body = read(CHANGELOG)
        spans = [m.start() for m in re.finditer(r"## \[[^\]]*\]", body)] + [len(body)]
        section_text = None
        for start, end in zip(spans, spans[1:]):
            candidate = body[start:end]
            if re.search(r"\(MAR-150\b", candidate):
                section_text = candidate
                break
        self.assertIsNotNone(
            section_text, "CHANGELOG.md must contain '(MAR-150)' inside a section span")
        heading = section_text[:section_text.index("\n")] if "\n" in section_text else section_text
        self.assertRegex(
            heading, r"## \[(Unreleased|\d+\.\d+\.\d+)\]",
            "the '(MAR-150)' audience-style entry must live under [Unreleased] or "
            "a dated semver release heading (release cuts legitimately graduate it)")
        self.assertIn("audience-style", section_text,
                       "the MAR-150 CHANGELOG entry must name the audience-style dimension")
        lowered = section_text.lower()
        self.assertIn("advisory", lowered)
        self.assertIn("blocking", lowered)


if __name__ == "__main__":
    unittest.main()
