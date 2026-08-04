"""MAR-164 spec 02 — bounded ADR-0012 doc-graph-gap check in code-planner.md
(Gap 2, Decision 2, Option C).

Covers AC-3 (a design decision for gap 2 is recorded and implemented: a
narrow doc-graph-gap clause, not the full ADR-0012 step and not retirement),
the Gap-2 half of AC-4 (the same E1-E4 list, or an explicit reference to it,
plus the same non-coverage bound, across code-planner.md, skills.md's
`/code` section, and ADR 0012's third amendment), and the Gap-2 half of
AC-5 (no regression to the existing 5-planner ADR-0012 canonical block or
its md5-identity test).

Every assertion is by file + substring/regex, never by line number (line
numbers drift as spec 03 lands on this branch next). Multi-word phrase
checks match against whitespace-normalized text (markdown word-wrap must
never break an otherwise-present clause).

Stdlib-only (os, re, unittest, importlib.util). Run:
  python3 -m unittest tests.acs.test_code_plan_doc_graph_gap -v
"""

import importlib.util
import os
import re
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN = os.path.join(REPO_ROOT, "plugins", "acs")
AGENTS_DIR = os.path.join(PLUGIN, "agents")

CODE_PLANNER = os.path.join(AGENTS_DIR, "code-planner.md")
CODE_SKILL = os.path.join(PLUGIN, "skills", "code", "SKILL.md")
ADR_0012 = os.path.join(REPO_ROOT, "docs", "adr", "0012-design-time-doc-consistency.md")
SKILLS_REQ = os.path.join(REPO_ROOT, "docs", "requirements", "functional", "skills.md")
CONSISTENCY_FINDINGS = os.path.join(PLUGIN, "hooks", "scripts", "consistency_findings.py")
DOC_CONSISTENCY_STEP_TEST = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "test_doc_consistency_step.py")

CANONICAL_HEADING = "### Design-time doc-consistency step (ADR 0012)"

# The four bounded doc-graph edges this spec adds (design.md:600-626).
EDGE_TARGET_DOCS = {
    "E1": ("hld/c4-component.md",),
    "E2": ("hld/data-model.md",),
    "E3": ("lld/flows/",),
    "E4": ("prd.md", "roadmap.md"),
}

# No-supersede regex guard (R3, load-bearing): flags a claim that docs-sync
# supersedes/is-equivalent-to/is-a-replacement-for the design-time step, in
# either token order, within a bounded window (checked on normalized text,
# so a word-wrap can never hide or fake a match). MUST stay absent from the
# amendment text; never weaken or drop this guard.
SUPERSEDE_CLAIM_RE = re.compile(
    r"(?i)(supersede\w*|equivalent to|replacement for).{0,120}docs-sync"
    r"|docs-sync.{0,120}(supersede\w*|equivalent to|replacement for)"
)


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def norm(text):
    """Collapse all whitespace runs (including newlines) to a single space,
    so a phrase-spanning check can never fail solely because markdown
    word-wrap happened to insert a line break between two words."""
    return re.sub(r"\s+", " ", text)


def phrase_re(phrase):
    """Build a whitespace-tolerant regex from a literal phrase."""
    return re.compile(r"\s+".join(re.escape(tok) for tok in phrase.split()))


def section(body, heading):
    """Slice a markdown section: from the line starting with `heading` up to
    the next same-or-higher-level heading, or EOF. Mirrors
    tests/acs/test_doc_consistency_step.py::section."""
    m = re.search(r"(?m)^" + re.escape(heading) + r".*$", body)
    if m is None:
        raise AssertionError("heading %r not found" % heading)
    start = m.start()
    level = len(heading) - len(heading.lstrip("#"))
    nxt = re.search(r"(?m)^#{1,%d} \S" % level, body[m.end():])
    end = m.end() + nxt.start() if nxt else len(body)
    return body[start:end]


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def live_canonical_block_count():
    """Recompute at test-run time — must never be hardcoded (assertion 4)."""
    count = 0
    for name in os.listdir(AGENTS_DIR):
        if not name.endswith(".md"):
            continue
        with open(os.path.join(AGENTS_DIR, name), encoding="utf-8") as fh:
            count += fh.read().count(CANONICAL_HEADING)
    return count


def assert_edges_and_targets_present(testcase, text):
    for edge, targets in EDGE_TARGET_DOCS.items():
        with testcase.subTest(edge=edge):
            testcase.assertIn(edge, text, "%s missing" % edge)
            for t in targets:
                testcase.assertIn(t, text, "%s's target doc %r missing" % (edge, t))


class CodePlannerItem4DocGraphGapTest(unittest.TestCase):
    """Assertion 1 + 8: code-planner.md item 4 names E1-E4 with target docs,
    the problems carrier, the touched-area bound, the explicit non-coverage
    of requirements_path/adr_path edges, and the silent-degradation rule."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(CODE_PLANNER)
        start = cls.body.index(
            "4. **Documentation map — docs are part of the change.**")
        end = cls.body.index("5. **Risks.**")
        cls.item4 = cls.body[start:end]
        cls.item4_norm = norm(cls.item4)

    def test_all_four_edges_named_with_target_docs(self):
        assert_edges_and_targets_present(self, self.item4)

    def test_problems_carrier_stated(self):
        self.assertIn("`problems`", self.item4)

    def test_touched_area_bound_stated(self):
        self.assertRegex(self.item4_norm, r"(?i)touched-area only")

    def test_explicit_non_coverage_stated(self):
        self.assertIn("requirements_path", self.item4)
        self.assertIn("adr_path", self.item4)
        self.assertRegex(self.item4_norm, r"(?i)not\b.{0,60}covered")

    def test_silent_degradation_stated(self):
        self.assertRegex(
            self.item4_norm,
            r"(?i)no architecture doc set on disk.{0,200}(no finding|never fails|never blocks)",
            "code-planner.md item 4 must state the silent-degradation bound "
            "(no architecture doc set on disk -> finds nothing, no finding, "
            "never fails or blocks)")

    def test_no_new_create_spec_substring(self):
        self.assertNotIn("create-spec", self.item4)


class CodeSkillPointerSentenceTest(unittest.TestCase):
    """Assertion 2: code/SKILL.md's documentation-map bullet carries the
    mirroring pointer sentence naming code-planner's item-4 participation."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(CODE_SKILL)
        start = cls.body.index("- The documentation map: whether any factual")
        end = cls.body.index(
            "- On iterations 2-3: how the plan remediates")
        cls.bullet = cls.body[start:end]
        cls.bullet_norm = norm(cls.bullet)

    def test_pointer_names_code_planner_item_4(self):
        self.assertIn("code-planner", self.bullet)
        self.assertRegex(self.bullet_norm, r"(?i)item 4")

    def test_pointer_names_bounded_touched_area(self):
        self.assertRegex(self.bullet_norm, r"(?i)bounded")
        self.assertRegex(self.bullet_norm, r"(?i)touched-area")

    def test_pointer_distinguishes_from_full_step_without_restating_table(self):
        # Scaled-down pattern mirroring create-design/SKILL.md:125-126 — must
        # not restate the E1-E4 table, only point at it, and must name that
        # this is narrower than the full shared design-time step.
        self.assertRegex(self.bullet_norm, r"(?i)not the full")
        self.assertNotIn("E2", self.bullet)
        self.assertNotIn("hld/data-model.md", self.bullet)

    def test_no_new_create_spec_substring(self):
        self.assertNotIn("create-spec", self.bullet)


class Adr0012ThirdAmendmentTest(unittest.TestCase):
    """Assertions 3, 4, 7: the third `## Amendment —` section, its
    bounded-participant/residual/no-supersede content, the live-recomputed
    DR-2 participant count, and the E1-E4 + non-coverage echo."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(ADR_0012)
        cls.amendment_headings = re.findall(r"(?m)^## Amendment — .*$", cls.body)
        cls.amendment = section(cls.body, "## Amendment — MAR-164")
        cls.amendment_norm = norm(cls.amendment)

    def test_exactly_three_amendment_headings_third_is_mar164(self):
        self.assertEqual(
            len(self.amendment_headings), 3,
            "ADR 0012 must carry exactly three '## Amendment —' headings, "
            "got: %r" % (self.amendment_headings,))
        self.assertEqual(self.amendment_headings[-1], "## Amendment — MAR-164")

    def test_code_named_as_bounded_touched_area_post_plan_participant(self):
        self.assertRegex(self.amendment_norm, r"(?i)/acs:code")
        self.assertRegex(self.amendment_norm, r"(?i)bounded")
        self.assertRegex(self.amendment_norm, r"(?i)touched-area")
        self.assertRegex(self.amendment_norm, r"(?i)post-plan")

    def test_true_residual_named(self):
        self.assertRegex(
            self.amendment_norm,
            phrase_re("trace-link gap detection for `needs_design: false` tickets"))

    def test_no_supersede_or_equivalence_claim_about_docs_sync(self):
        self.assertIsNone(
            SUPERSEDE_CLAIM_RE.search(self.amendment_norm),
            "ADR 0012's MAR-164 amendment must not claim docs-sync "
            "supersedes/is-equivalent-to/is-a-replacement-for the "
            "design-time step (R3/R8 — load-bearing, premise-correction).")

    def test_dr2_participant_count_matches_live_recomputation(self):
        live_count = live_canonical_block_count()
        m = re.search(
            r"\*\*(\d+)\*\*\s+planner\s+agents\s+actually\s+carry\s+the\s+canonical",
            self.amendment_norm)
        self.assertIsNotNone(
            m, "amendment must state the reconciled participant count "
            "next to '**N** planner agents actually carry the canonical'")
        stated_count = int(m.group(1))
        self.assertEqual(
            stated_count, live_count,
            "ADR 0012's MAR-164 amendment states %d participants but "
            "grep -c over plugins/acs/agents/ finds %d live carriers of %r "
            "today — the assertion must self-recompute so it cannot re-drift"
            % (stated_count, live_count, CANONICAL_HEADING))

    def test_code_planner_explicitly_excluded_from_reconciled_carrier_list(self):
        self.assertRegex(
            self.amendment_norm,
            r"(?i)code-planner\.md.{0,60}not\b.{0,60}(one of the|8)",
            "amendment must explicitly state code-planner.md is not one of "
            "the reconciled carrier list")

    def test_amendment_carries_e1_e4_list_and_non_coverage_bound(self):
        # AC-4's third leg (added in iteration 3, assertion 7): within the
        # amendment slice ONLY, either the full E1-E4 labels+targets, or an
        # explicit reference to code-planner.md's item-4 table.
        has_full_table = True
        for edge, targets in EDGE_TARGET_DOCS.items():
            if edge not in self.amendment:
                has_full_table = False
            for t in targets:
                if t not in self.amendment:
                    has_full_table = False
        has_explicit_reference = bool(
            re.search(r"(?i)code-planner\.md.{0,60}item\s+4", self.amendment_norm))
        self.assertTrue(
            has_full_table or has_explicit_reference,
            "the MAR-164 amendment must carry the E1-E4 list itself, or an "
            "explicit reference to code-planner.md's item-4 table")
        self.assertIn("requirements_path", self.amendment)
        self.assertIn("adr_path", self.amendment)
        self.assertRegex(self.amendment_norm, r"(?i)not\b.{0,60}covered")


class SkillsReqCodeSectionAdr0012ClauseTest(unittest.TestCase):
    """Assertion 5: skills.md's `/code` section carries the participation
    clause with the same E1-E4 list (or explicit reference) and the same
    non-coverage bound — the second leg of AC-4's three-way agreement."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(SKILLS_REQ)
        cls.section = section(cls.body, "## 3. `/code`")
        cls.section_norm = norm(cls.section)

    def test_code_section_no_longer_silent_on_adr_0012(self):
        self.assertIn("0012", self.section)

    def test_e1_e4_list_or_explicit_reference_present(self):
        has_full_table = all(
            edge in self.section for edge in EDGE_TARGET_DOCS)
        has_explicit_reference = bool(
            re.search(r"(?i)code-planner\.md.{0,60}item\s+4", self.section_norm))
        self.assertTrue(
            has_full_table or has_explicit_reference,
            "skills.md's /code section must carry the E1-E4 list, or an "
            "explicit reference to code-planner.md's item-4 table")

    def test_non_coverage_bound_present(self):
        self.assertIn("requirements_path", self.section)
        self.assertIn("adr_path", self.section)
        self.assertRegex(self.section_norm, r"(?i)not\b.{0,60}covered")

    def test_no_new_create_spec_substring(self):
        self.assertNotIn("create-spec", self.section)


class NegativeGuardsTest(unittest.TestCase):
    """Assertion 6: code-planner.md must not be added to
    test_doc_consistency_step.py's PLANNERS list; the canonical heading must
    not appear anywhere in code-planner.md; consistency_findings.py must be
    unchanged with no new finding kind."""

    def test_code_planner_not_in_doc_consistency_step_planners(self):
        mod = load_module("test_doc_consistency_step", DOC_CONSISTENCY_STEP_TEST)
        self.assertNotIn("code-planner.md", mod.PLANNERS)

    def test_canonical_heading_absent_from_code_planner(self):
        body = read(CODE_PLANNER)
        self.assertNotIn(CANONICAL_HEADING, body)

    def test_consistency_findings_shape_unchanged(self):
        mod = load_module("consistency_findings", CONSISTENCY_FINDINGS)
        self.assertEqual(mod.VALID_KINDS, ("gap", "staleness"))


if __name__ == "__main__":
    unittest.main()
