"""MAR-138 spec 02 — declare + wire the structure and audience-style gates
across the 7 prose-doc skills.

Prose-contract tests over the 7 prose-doc `*-verifier.md` agents
(create-prd, create-architecture, create-design, create-principles,
create-standards, create-quality, create-operations): each gains an
APPENDED, deterministic, blocking `structure` dimension (invokes Spec 01's
`structure_lint.py`) and an APPENDED, advisory `audience-style` dimension
(`severity="info"` only, never blocking) — plus a matching declaration of
`required_sections` and `audience_style_profile` in the corresponding
SKILL.md, passed into the verify task. `create-project` is explicitly N/A
(AC-5) — locked here by a negative test, not by omission alone.

Reuses `test_diagram_lint_verifiers.py`'s bold+backtick helpers
(`read`, `_label_pattern`, `dimension_block`, `dimension_present`) — NOT the
backtick-only `test_design_verifier_standards.py` base, which would
silently miss the bold-labelled dimensions in 6 of these 7 files.

Stdlib-only (re, os, unittest). Run:
  python3 -m unittest tests.acs.test_mar138_structure_audience_verifiers -v
"""

import os
import re
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN = os.path.join(REPO_ROOT, "plugins", "acs")
AGENTS = os.path.join(PLUGIN, "agents")
SKILLS = os.path.join(PLUGIN, "skills")

HELPER_PATH = "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/structure_lint.py"

CREATE_PROJECT_VERIFIER = os.path.join(AGENTS, "create-project-verifier.md")
CREATE_PROJECT_SKILL = os.path.join(SKILLS, "create-project", "SKILL.md")

# verifier path -> (last pre-existing dimension label, all pre-existing dimension labels)
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
}

# SKILL.md name -> whether it uses per-file required_sections:<file> constraints
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
    """A numbered check-dimension label, bold- or backtick-wrapped (mirrors
    test_diagram_lint_verifiers.py's bold-vs-backtick gotcha: the
    7 prose verifiers this spec touches mix **bold** (prd, architecture,
    principles, standards, quality, operations) and `backtick` (design)
    dimension-label markup)."""
    return r"(?:\*\*%s\*\*|`%s`)" % (re.escape(label), re.escape(label))


def dimension_block(body, label, next_label=None):
    """Extract a numbered check-dimension list item: from the line matching
    `^\\d+. **label**` or `^\\d+. `label`` up to (not including) the next
    numbered item (or, when `next_label` is given, up to that specific
    item)."""
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
    """True if `label` is a numbered check-dimension entry (bold or
    backtick-wrapped)."""
    return re.search(r"(?m)^\d+\.\s+%s" % _label_pattern(label), body) is not None


def verify_phase_region(skill_md_body, skill_name):
    """Bounded window over the SKILL.md text that describes what gets
    spawned/passed to the verifier: from the first line naming the Verify
    phase (`### Verify`, `### Phase: verify`, or the numbered `**Verify**`
    Phases-list item) to the next top-level (`##`) heading. Mirrors AC-6's
    'verify-spawn prose' — where each SKILL.md states what the verify task
    receives."""
    m = re.search(r"(?m)^(?:#{2,3}\s+(?:Verify|Phase: verify).*|3\.\s+\*\*Verify\*\*.*)$",
                  skill_md_body)
    assert m is not None, "no Verify-phase heading/list-item found in %s/SKILL.md" % skill_name
    rest = skill_md_body[m.end():]
    end_m = re.search(r"(?m)^## ", rest)
    end = m.end() + end_m.start() if end_m else len(skill_md_body)
    return skill_md_body[m.start():end]


class StructureDimensionTest(unittest.TestCase):
    """AC-3: every one of the 7 prose verifiers gains an appended,
    deterministic, blocking `structure` dimension invoking Spec 01's
    structure_lint.py."""

    def test_all_seven_verifiers_invoke_helper_and_block(self):
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
        # R2/R5: create-architecture's per-file section lists are derived,
        # not skill-declared literal headings — order is never enforced.
        block = dimension_block(read(os.path.join(AGENTS, "create-architecture-verifier.md")),
                                 "structure")
        self.assertNotIn("--ordered", block)


class AudienceStyleDimensionTest(unittest.TestCase):
    """AC-4: every one of the 7 prose verifiers gains an appended, advisory
    `audience-style` dimension — severity="info" only, never blocking."""

    def test_all_seven_verifiers_have_advisory_dimension(self):
        for fname in VERIFIERS:
            with self.subTest(verifier=fname):
                body = read(os.path.join(AGENTS, fname))
                block = dimension_block(body, "audience-style")
                self.assertIn('severity="info"', block)
                self.assertIn('dimension="audience-style"', block)
                lowered = block.lower()
                self.assertTrue("advisory" in lowered or "never block" in lowered
                                 or "non-blocking" in lowered,
                                 "%s audience-style dimension must document itself as advisory"
                                 % fname)

    def test_never_emits_blocking_severity(self):
        for fname in VERIFIERS:
            with self.subTest(verifier=fname):
                body = read(os.path.join(AGENTS, fname))
                block = dimension_block(body, "audience-style")
                self.assertNotIn('severity="blocking"', block)


class CarveOutTest(unittest.TestCase):
    """Decision C-sub: every verifier's pre-existing 'ALL findings block' /
    'no advisory findings' hard-rule sentence(s) carry the audience-style
    carve-out, so no residual sentence contradicts the new advisory
    dimension."""

    def test_all_blocking_sentence_carved_out(self):
        for fname in VERIFIERS:
            with self.subTest(verifier=fname):
                body = read(os.path.join(AGENTS, fname))
                self.assertIn("audience-style", body)
                # The carve-out must sit near an "all findings block"-style
                # sentence, not just anywhere in the new dimension bodies.
                m = re.search(r"(?is)all findings (?:are )?block(?:ing)?.*?(?=\n\n|\Z)", body)
                self.assertIsNotNone(m, "%s has no 'all findings block' sentence to carve out"
                                      % fname)
                self.assertIn("audience-style", m.group(0),
                               "%s's all-findings-block sentence lacks the carve-out" % fname)

    def test_design_both_anchors_carved_out(self):
        # create-design carries the assertion TWICE (preamble + findings-format).
        body = read(os.path.join(AGENTS, "create-design-verifier.md"))
        matches = list(re.finditer(
            r"(?is)(?:all findings block|every `<finding>` carries[^\n]*blocking|"
            r"finding is `severity=\"blocking\"`).*?(?=\n\n|\Z)", body))
        self.assertGreaterEqual(len(matches), 2,
                                 "expected both create-design carve-out anchors")
        for m in matches:
            self.assertIn("audience-style", m.group(0))


class DimensionListRegressionTest(unittest.TestCase):
    """Surgical-edit proof (R1 mitigation): every dimension that existed
    before this spec is still present, by name, in each of the 7 verifiers —
    including sibling MAR-137's create-architecture dim 4 (mermaid-diagrams)
    and create-design dim 5 (completeness), presence-only, never
    byte-inspected here (that pin belongs to test_mar137)."""

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
    body (owned by test_diagram_lint_verifiers.py) is not touched by
    this spec's edits beyond the one permitted carve-out sentence — checked
    here only by confirming the byte-pinned substrings test_mar137 asserts
    are still present verbatim; the exhaustive pin itself stays in
    test_mar137."""

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
    """AC-5 / Decision D1: create-project is explicitly N/A — no structure
    dimension, no audience-style dimension, no structure_lint.py reference,
    and its SKILL.md declares neither required_sections nor
    audience_style_profile."""

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
    """AC-1 + AC-6: each of the 7 prose SKILL.md declares required_sections
    (flat, or required_sections:<file> per produced prose file) AND a
    non-empty audience_style_profile, and both are referenced within the
    file's verify-phase region (proving the coordinator passes them into
    the verify task, not just declares them in isolation)."""

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


if __name__ == "__main__":
    unittest.main()
