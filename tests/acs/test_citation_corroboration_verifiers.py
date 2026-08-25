"""Prose-contract tests for the citation-corroboration mechanism shared by the
create-quality/-standards/-operations/-principles planner and verifier
charters.

Covers both halves: the planner half (each of the 4 planners' `Upstream
inventory` section must mandate a verbatim quoted excerpt per citation, state
the citation grammar, mark the line/range advisory-only, and (create-standards
only) keep its `principles/ N/A: <why>` note, explicitly exempted from the new
grammar) and the verifier half (each of the 4 verifiers' `plan-conformance`
dimension invokes the shared `citation_check.py` floor, maps every finding and
exit 2 to a blocking finding, and additionally requires a substantiation
judgment over the script's resolved-citations manifest — the hybrid shape).
Also pins the negative/regression space this ticket must not disturb:
`create-prd-verifier.md` untouched, loop topology unchanged in all 5
bootstrap-doc skills, and dimension 4's name/number/position/"eight" count
unchanged.

Mirrors the reading/extraction helper shapes from
`test_structure_audience_verifiers.py` and `test_diagram_lint_verifiers.py`
(`read`, `_label_pattern`, `dimension_block`, `dimension_present`,
`verify_phase_region`).

Stdlib-only (re, os, unittest). Run:
  python3 -m unittest tests.acs.test_citation_corroboration_verifiers -v
"""

import os
import re
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN = os.path.join(REPO_ROOT, "plugins", "acs")
AGENTS = os.path.join(PLUGIN, "agents")
SKILLS = os.path.join(PLUGIN, "skills")

HELPER_PATH = "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/citation_check.py"

PLANNERS = (
    "create-quality-planner.md",
    "create-operations-planner.md",
    "create-principles-planner.md",
    "create-standards-planner.md",
)

VERIFIERS = (
    "create-quality-verifier.md",
    "create-standards-verifier.md",
    "create-operations-verifier.md",
    "create-principles-verifier.md",
)

PRD_VERIFIER = "create-prd-verifier.md"

# create-prd-verifier.md's 9 pre-existing dimension labels (AC-5 negative
# pin) — mirrors the VERIFIERS["create-prd-verifier.md"] entry in
# test_structure_audience_verifiers.py:56-64.
PRD_VERIFIER_DIMENSIONS = (
    "Required sections", "Feature -> goal traceability",
    "Measurable success metrics", "Prioritization discipline",
    "Constraint consistency", "Roadmap coverage", "Plan conformance",
    "Amend-mode diff discipline", "Iteration 2+ regression check",
)

# all 5 bootstrap-doc skills whose loop topology (per-iteration planner
# re-spawn) must stay unchanged (AC-5).
BOOTSTRAP_DOC_SKILLS = (
    "create-quality", "create-standards", "create-operations",
    "create-principles", "create-prd",
)


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _label_pattern(label):
    """A numbered check-dimension label: **bold**, `backtick`, or the
    bold+backtick `**`label`**` form (mirrors the sibling verifier test
    modules' mixed bold/backtick dimension styles)."""
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
    phase to the next top-level (`##`) heading."""
    m = re.search(r"(?m)^(?:#{2,3}\s+(?:Verify|Phase: verify).*|3\.\s+\*\*Verify\*\*.*)$",
                  skill_md_body)
    assert m is not None, "no Verify-phase heading/list-item found in %s/SKILL.md" % skill_name
    rest = skill_md_body[m.end():]
    end_m = re.search(r"(?m)^## ", rest)
    end = m.end() + end_m.start() if end_m else len(skill_md_body)
    return skill_md_body[m.start():end]


def upstream_inventory_bullet(body, planner_name):
    """The `Upstream inventory` top-level bullet: from its
    `- **Upstream inventory**` line up to (not including) the next top-level
    `- **` bullet (or end of file)."""
    m = re.search(r"(?m)^-\s+\*\*Upstream inventory\*\*.*$", body)
    assert m is not None, "%s: Upstream inventory bullet not found" % planner_name
    rest = body[m.end():]
    end_m = re.search(r"(?m)^-\s+\*\*", rest)
    end = m.end() + end_m.start() if end_m else len(body)
    return body[m.start():end]


def citation_excerpt_clause(bullet_text):
    """The shared mandatory-verbatim-excerpt sentence pair, whitespace-
    normalized for cross-planner identity comparison (AC-4)."""
    m = re.search(
        r"Each citation is one line of the shape.*?never a paraphrase\.",
        bullet_text, re.DOTALL)
    assert m is not None, "citation excerpt clause not found in Upstream inventory bullet"
    return re.sub(r"\s+", " ", m.group(0)).strip()


def corroboration_clause(block):
    """The shared citation-corroboration prose inside dimension 4's
    plan-conformance block, whitespace-normalized for cross-verifier
    identity comparison (AC-4)."""
    m = re.search(
        r"Independently re-open and check every upstream-fact citation.*?"
        r"with no lesser severity ever emitted\.",
        block, re.DOTALL)
    assert m is not None, "corroboration clause not found in plan-conformance dimension"
    return re.sub(r"\s+", " ", m.group(0)).strip()


class PlannerExcerptClauseTest(unittest.TestCase):
    """AC-2/AC-4: each of the 4 planners' `Upstream inventory` bullet
    mandates a verbatim quoted excerpt per citation, states the citation
    grammar, marks the line/range advisory-only, and — for create-standards
    only — still carries its `principles/ N/A: <why>` note, explicitly
    exempted from the new grammar."""

    def test_all_four_planners_have_upstream_inventory_bullet(self):
        for fname in PLANNERS:
            with self.subTest(planner=fname):
                body = read(os.path.join(AGENTS, fname))
                bullet = upstream_inventory_bullet(body, fname)
                self.assertTrue(bullet)

    def test_all_four_mandate_verbatim_quoted_excerpt(self):
        for fname in PLANNERS:
            with self.subTest(planner=fname):
                body = read(os.path.join(AGENTS, fname))
                bullet = upstream_inventory_bullet(body, fname)
                lowered = bullet.lower()
                self.assertIn(
                    "verbatim", lowered,
                    "%s Upstream inventory bullet must mandate a verbatim excerpt" % fname)
                self.assertIn(
                    "excerpt", lowered,
                    "%s Upstream inventory bullet must name the excerpt" % fname)
                self.assertIn(
                    "paraphrase", lowered,
                    "%s Upstream inventory bullet must forbid a paraphrase" % fname)

    def test_all_four_state_citation_grammar(self):
        for fname in PLANNERS:
            with self.subTest(planner=fname):
                body = read(os.path.join(AGENTS, fname))
                bullet = upstream_inventory_bullet(body, fname)
                self.assertIn("<claim text>", bullet)
                self.assertIn("<relative-path>", bullet)
                self.assertIn("<verbatim excerpt>", bullet)

    def test_all_four_mark_line_range_advisory_only(self):
        for fname in PLANNERS:
            with self.subTest(planner=fname):
                body = read(os.path.join(AGENTS, fname))
                bullet = upstream_inventory_bullet(body, fname)
                self.assertIn("advisory only", bullet.lower())

    def test_clause_identical_across_four_planners(self):
        clauses = {}
        for fname in PLANNERS:
            body = read(os.path.join(AGENTS, fname))
            bullet = upstream_inventory_bullet(body, fname)
            clauses[fname] = citation_excerpt_clause(bullet)
        unique = set(clauses.values())
        self.assertEqual(
            len(unique), 1,
            "excerpt clause drifted across planners (not identical): %r" % clauses)

    def test_standards_principles_na_note_preserved(self):
        body = read(os.path.join(AGENTS, "create-standards-planner.md"))
        bullet = upstream_inventory_bullet(body, "create-standards-planner.md")
        self.assertIn("principles/ N/A:", bullet)
        self.assertIn("<why>", bullet)

    def test_standards_principles_na_note_exempted_from_grammar(self):
        body = read(os.path.join(AGENTS, "create-standards-planner.md"))
        bullet = upstream_inventory_bullet(body, "create-standards-planner.md")
        self.assertIn("exempt", bullet.lower())

    def test_other_three_planners_have_no_principles_na_note(self):
        # only create-standards carries the principles/N/A carve-out
        for fname in ("create-quality-planner.md", "create-operations-planner.md",
                      "create-principles-planner.md"):
            with self.subTest(planner=fname):
                body = read(os.path.join(AGENTS, fname))
                bullet = upstream_inventory_bullet(body, fname)
                self.assertNotIn("principles/ N/A:", bullet)


class DimensionFourInvocationTest(unittest.TestCase):
    """AC-2: all 4 verifiers' `plan-conformance` dimension invokes the shared
    citation_check.py script with --plan/--root against the current
    iteration's plan artifact; create-standards additionally names a
    principles root."""

    def test_all_four_invoke_helper_with_plan_and_root(self):
        for fname in VERIFIERS:
            with self.subTest(verifier=fname):
                body = read(os.path.join(AGENTS, fname))
                block = dimension_block(body, "plan-conformance")
                self.assertIn(HELPER_PATH, block,
                              "%s plan-conformance dimension must invoke %s" % (fname, HELPER_PATH))
                self.assertIn("--plan", block)
                self.assertIn("--root", block)
                self.assertIn("iter-<n>-plan.md", block)

    def test_standards_names_principles_root(self):
        body = read(os.path.join(AGENTS, "create-standards-verifier.md"))
        block = dimension_block(body, "plan-conformance")
        self.assertIn("principles", block.lower())


class PrdRootDeclaredTest(unittest.TestCase):
    """AC-2/C-7: all 4 verifiers' input-contract `<constraints>` enumeration
    now names `prd_path` (baseline: 0 matches in all four)."""

    def test_all_four_declare_prd_path_constraint(self):
        for fname in VERIFIERS:
            with self.subTest(verifier=fname):
                body = read(os.path.join(AGENTS, fname))
                self.assertIn(
                    "prd_path", body,
                    "%s must declare prd_path as a verify-task constraint" % fname)


class BlockingFindingMappingTest(unittest.TestCase):
    """AC-3/D3-a: each dim-4 block maps every stderr finding, and exit 2
    itself, to severity="blocking" dimension="plan-conformance"; no
    severity="info" path exists anywhere in the block."""

    def test_maps_findings_and_exit_two_to_blocking(self):
        for fname in VERIFIERS:
            with self.subTest(verifier=fname):
                body = read(os.path.join(AGENTS, fname))
                block = dimension_block(body, "plan-conformance")
                self.assertIn('severity="blocking"', block)
                self.assertIn('dimension="plan-conformance"', block)
                self.assertIn("exit 2", block)

    def test_no_info_severity_in_block(self):
        for fname in VERIFIERS:
            with self.subTest(verifier=fname):
                body = read(os.path.join(AGENTS, fname))
                block = dimension_block(body, "plan-conformance")
                self.assertNotIn('severity="info"', block)


class SemanticCeilingTest(unittest.TestCase):
    """AC-1/AC-3 (design R3, honest prose-only pin): each dim-4 block
    requires the verifier to re-open every resolved citation from the
    script's manifest and judge substantiation."""

    def test_requires_reopening_and_judging_substantiation(self):
        for fname in VERIFIERS:
            with self.subTest(verifier=fname):
                body = read(os.path.join(AGENTS, fname))
                block = dimension_block(body, "plan-conformance")
                lowered = block.lower()
                self.assertIn("resolved", lowered)
                self.assertIn("substantiat", lowered)
                self.assertIn("manifest", lowered)


class HybridMechanismTest(unittest.TestCase):
    """AC-1 (D1-C): both halves co-exist in every dim-4 block — the
    deterministic script invocation AND the substantiation judgment; neither
    half alone is present."""

    def test_both_deterministic_and_semantic_present(self):
        for fname in VERIFIERS:
            with self.subTest(verifier=fname):
                body = read(os.path.join(AGENTS, fname))
                block = dimension_block(body, "plan-conformance")
                self.assertIn(HELPER_PATH, block,
                              "%s missing the deterministic invocation half" % fname)
                self.assertGreater(
                    block.lower().count("substantiat"), 0,
                    "%s missing the semantic substantiation-judgment half" % fname)


class SharedIdenticallyTest(unittest.TestCase):
    """AC-4: exactly one citation_check.py exists under
    plugins/acs/hooks/scripts/, and the corroboration clause normalizes
    identically across the 4 verifiers."""

    def test_exactly_one_citation_check_script(self):
        found = []
        for root, _dirs, files in os.walk(PLUGIN):
            for f in files:
                if f == "citation_check.py":
                    found.append(os.path.join(root, f))
        self.assertEqual(
            found, [os.path.join(PLUGIN, "hooks", "scripts", "citation_check.py")],
            "expected exactly one citation_check.py, under hooks/scripts/: %r" % found)

    def test_verifier_clause_identical_across_four(self):
        clauses = {}
        for fname in VERIFIERS:
            body = read(os.path.join(AGENTS, fname))
            block = dimension_block(body, "plan-conformance")
            clauses[fname] = corroboration_clause(block)
        unique = set(clauses.values())
        self.assertEqual(
            len(unique), 1,
            "corroboration clause drifted across verifiers (not identical): %r" % clauses)


class CreatePrdUntouchedTest(unittest.TestCase):
    """AC-5: create-prd-verifier.md contains no citation_check.py reference
    and its 9 pre-existing dimension labels all remain."""

    def test_no_citation_check_reference(self):
        body = read(os.path.join(AGENTS, PRD_VERIFIER))
        self.assertNotIn("citation_check.py", body)

    def test_all_nine_dimensions_present(self):
        body = read(os.path.join(AGENTS, PRD_VERIFIER))
        for label in PRD_VERIFIER_DIMENSIONS:
            with self.subTest(dimension=label):
                self.assertTrue(
                    dimension_present(body, label),
                    "dimension %r must remain present in %s" % (label, PRD_VERIFIER))


class LoopTopologyUnchangedTest(unittest.TestCase):
    """AC-5: all 5 bootstrap-doc SKILL.md files still carry the
    per-iteration planner re-spawn sentence (plan -> execute -> verify)."""

    def test_all_five_carry_plan_execute_verify(self):
        for skill in BOOTSTRAP_DOC_SKILLS:
            with self.subTest(skill=skill):
                body = read(os.path.join(SKILLS, skill, "SKILL.md"))
                self.assertRegex(
                    body.lower(), r"plan -> execute -> verify",
                    "%s/SKILL.md must still carry the per-iteration re-spawn sentence" % skill)


CORROBORATION_SKILLS = (
    "create-quality", "create-standards", "create-operations", "create-principles",
)


def verify_constraints_sentence(region, skill_name):
    """The 'The verify task's `<constraints>` also carry ...' paragraph
    inside a SKILL.md's verify-phase region, up to the next blank line."""
    m = re.search(
        r"The verify task's `<constraints>` also carry.*?(?=\n\n)",
        region, re.DOTALL)
    assert m is not None, (
        "%s/SKILL.md: verify-task <constraints> sentence not found" % skill_name)
    return m.group(0)


class SkillMirrorTest(unittest.TestCase):
    """AC-2: each of the 4 SKILL.md 'the plan was followed exactly' bullets
    is extended to also name citation corroboration — never by adding a new
    bullet, since create-standards/SKILL.md's 'the six dimensions above'
    count would then silently go stale (K4)."""

    def test_bullet_extended_to_name_citation_corroboration(self):
        for skill in CORROBORATION_SKILLS:
            with self.subTest(skill=skill):
                body = read(os.path.join(SKILLS, skill, "SKILL.md"))
                region = verify_phase_region(body, skill)
                m = re.search(
                    r"(?m)^\s*-\s+the plan was followed exactly.*?;",
                    region, re.DOTALL)
                self.assertIsNotNone(
                    m,
                    "%s/SKILL.md: 'the plan was followed exactly' bullet not found" % skill)
                self.assertIn(
                    "citation", m.group(0).lower(),
                    "%s/SKILL.md: bullet must be extended to name citation "
                    "corroboration" % skill)

    def test_standards_six_dimensions_count_still_accurate(self):
        # extending the existing bullet must not add a new one — the mirror
        # verifier's own "checks ONLY ... the six dimensions above" count
        # must stay unchanged (K4).
        body = read(os.path.join(SKILLS, "create-standards", "SKILL.md"))
        self.assertRegex(body.lower(), r"the six dimensions\s+above")
        region = verify_phase_region(body, "create-standards")
        bullets = re.findall(r"(?m)^   -\s+", region.split("**This producer verifier")[0])
        self.assertEqual(
            len(bullets), 6,
            "create-standards/SKILL.md verify checklist must still list exactly "
            "six top-level bullets (extend, don't add): %r" % bullets)


class SkillVerifyConstraintPrdPathTest(unittest.TestCase):
    """C-7: each of the 4 SKILL.md verify-task `<constraints>` sentences
    names `prd_path`, so the coordinator actually renders the root the
    verifier's new plan-conformance constraint needs."""

    def test_verify_constraints_sentence_names_prd_path(self):
        for skill in CORROBORATION_SKILLS:
            with self.subTest(skill=skill):
                body = read(os.path.join(SKILLS, skill, "SKILL.md"))
                region = verify_phase_region(body, skill)
                sentence = verify_constraints_sentence(region, skill)
                self.assertIn(
                    "prd_path", sentence,
                    "%s/SKILL.md: verify-task <constraints> sentence must name "
                    "prd_path" % skill)


class DimensionFourStillNumberedFourTest(unittest.TestCase):
    """D4-fold/R5: plan-conformance remains the 4th numbered dimension in
    all 4 verifiers, between required-sections and docs-only-changeset, and
    "eight" (never "nine") still names the dimension count."""

    def test_plan_conformance_is_dimension_four(self):
        for fname in VERIFIERS:
            with self.subTest(verifier=fname):
                body = read(os.path.join(AGENTS, fname))
                self.assertIsNotNone(
                    re.search(r"(?m)^4\.\s+\*\*plan-conformance\*\*", body),
                    "%s: plan-conformance must stay numbered 4." % fname)

    def test_between_required_sections_and_docs_only_changeset(self):
        for fname in VERIFIERS:
            with self.subTest(verifier=fname):
                body = read(os.path.join(AGENTS, fname))
                req = re.search(r"(?m)^3\.\s+\*\*required-sections\*\*", body)
                pc = re.search(r"(?m)^4\.\s+\*\*plan-conformance\*\*", body)
                docs = re.search(r"(?m)^5\.\s+\*\*docs-only-changeset\*\*", body)
                self.assertIsNotNone(req)
                self.assertIsNotNone(pc)
                self.assertIsNotNone(docs)
                self.assertLess(req.start(), pc.start())
                self.assertLess(pc.start(), docs.start())

    def test_eight_unchanged_no_ninth_dimension(self):
        for fname in VERIFIERS:
            with self.subTest(verifier=fname):
                body = read(os.path.join(AGENTS, fname))
                self.assertIn("eight", body)
                self.assertIsNone(
                    re.search(r"(?m)^9\.\s+(?:\*\*|`)", body),
                    "%s must not gain a 9th numbered dimension" % fname)


if __name__ == "__main__":
    unittest.main()
