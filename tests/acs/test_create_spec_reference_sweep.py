"""MAR-164 spec 03 — create-spec reference sweep + DR-1 + CHANGELOG.

Covers AC-2 (no live code-level reference to the deleted /acs:create-spec
skill remains anywhere in plugins/acs/{skills,agents}/**), the consistency
half of AC-4 (every Rule-1 site names /acs:code as the positive replacement,
never merely absence-of-token; every Rule-2 site re-flows without a
duplicated stage), and the sweep's share of AC-5 (no regression to the
5-provenance-line/3-file survivor set or the backward-compat schema/hooks
surface).

This is the LAST of the ticket's three executor tasks: its assertion-1
predicate asserts the FINAL whole-tree state of plugins/acs/{skills,agents}/**
and only holds once spec 01 has already removed create-ticket/SKILL.md's own
two create-spec lines. Every assertion here is by file + substring (line-hit
COUNTS, not line NUMBERS), so ordinary edits above a clause elsewhere in a
touched file can never spuriously break this suite.

Stdlib-only (os, re, sys, unittest). Run:
  python3 -m unittest tests.acs.test_create_spec_reference_sweep -v
"""

import os
import re
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN = os.path.join(REPO_ROOT, "plugins", "acs")
SKILLS_DIR = os.path.join(PLUGIN, "skills")
AGENTS_DIR = os.path.join(PLUGIN, "agents")
HOOKS_SCRIPTS = os.path.join(PLUGIN, "hooks", "scripts")
SCHEMAS_DIR = os.path.join(PLUGIN, "schemas")

sys.path.insert(0, HOOKS_SCRIPTS)
import acs_lib as lib  # noqa: E402

# --- The 3 files the AC-2 predicate says must still contain "create-spec" ---
CODE_SKILL = os.path.join(SKILLS_DIR, "code", "SKILL.md")
CODE_PLANNER = os.path.join(AGENTS_DIR, "code-planner.md")
CODE_VERIFIER = os.path.join(AGENTS_DIR, "code-verifier.md")

# --- This spec's sweep-set files ---
CREATE_DESIGN_SKILL = os.path.join(SKILLS_DIR, "create-design", "SKILL.md")
CREATE_TICKET_SKILL = os.path.join(SKILLS_DIR, "create-ticket", "SKILL.md")
INIT_SKILL = os.path.join(SKILLS_DIR, "init", "SKILL.md")
HANDOFF_SKILL = os.path.join(SKILLS_DIR, "handoff", "SKILL.md")
CREATE_ARCHITECTURE_SKILL = os.path.join(SKILLS_DIR, "create-architecture", "SKILL.md")
CREATE_QUALITY_SKILL = os.path.join(SKILLS_DIR, "create-quality", "SKILL.md")
CREATE_OPERATIONS_SKILL = os.path.join(SKILLS_DIR, "create-operations", "SKILL.md")
CREATE_PRINCIPLES_SKILL = os.path.join(SKILLS_DIR, "create-principles", "SKILL.md")
CREATE_STANDARDS_SKILL = os.path.join(SKILLS_DIR, "create-standards", "SKILL.md")
CREATE_DESIGN_EXECUTOR = os.path.join(AGENTS_DIR, "create-design-executor.md")
CREATE_TICKET_EXECUTOR = os.path.join(AGENTS_DIR, "create-ticket-executor.md")

RULE2_IDENTICAL_FILES = [
    CREATE_ARCHITECTURE_SKILL, CREATE_QUALITY_SKILL, CREATE_OPERATIONS_SKILL,
    CREATE_PRINCIPLES_SKILL, CREATE_STANDARDS_SKILL,
]
# Every file a Rule-2 rewrite touches (the 5 identical ones, plus init and
# handoff whose Rule-2 rewrites are each shaped differently).
RULE2_AFFECTED_FILES = [INIT_SKILL, HANDOFF_SKILL] + RULE2_IDENTICAL_FILES

# --- Untouched backward-compat / out-of-scope surface (negative guards) ---
SHIP_SKILL = os.path.join(SKILLS_DIR, "ship", "SKILL.md")
CHANGELOG = os.path.join(PLUGIN, "CHANGELOG.md")
XSD = os.path.join(SCHEMAS_DIR, "acs-messages.xsd")
SKILL_STATE_SCHEMA = os.path.join(SCHEMAS_DIR, "skill-state.schema.json")
CLARIFICATIONS_SCHEMA = os.path.join(SCHEMAS_DIR, "clarifications.schema.json")
STATUSLINE_PY = os.path.join(HOOKS_SCRIPTS, "statusline.py")
SUBAGENT_STATUSLINE_PY = os.path.join(HOOKS_SCRIPTS, "subagent-statusline.py")
VALIDATE_XML_PY = os.path.join(HOOKS_SCRIPTS, "validate_xml.py")

# The 5 pinned past-tense provenance substrings (Decision 3) — deliberately
# permanent, asserted present, never removed.
PROVENANCE_SUBSTRINGS = [
    (CODE_SKILL,
     "the spec content a standalone create-spec planner would once have produced"),
    (CODE_SKILL,
     "no separate /acs:create-spec invocation and no separate create-spec planner"),
    (CODE_PLANNER, "migrated from the deleted create-spec-planner.md"),
    (CODE_VERIFIER, "create-spec-verifier's `consistency` dimension"),
    (CODE_VERIFIER,
     "now that create-spec's separately-authored spec set no longer exists"),
]

# The 7 Rule-1 lines assertion 4 covers (create-design's 7 sites plus the
# create-ticket "Next" line's two occurrences, tested separately below).
CREATE_DESIGN_ROUTING_PHRASES = [
    "tickets without the flag skip straight to /acs:code.",
    "verifier before it gates `/acs:code`.",
    "INHERIT this design via cross-partition read in their /acs:code; never",
    "the /acs:code gate stays closed until it succeeds.",
    "the next step (`/acs:code <id>`; for an epic, /acs:code on",
    "`<next-step>/acs:code <id></next-step>`.",
    "**Next**: `/acs:code <ticket-id>`",
]


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def norm(text):
    """Collapse whitespace runs (incl. newlines) to a single space, so a
    phrase-spanning check can't fail solely because markdown word-wrap
    happened to insert a line break between two words."""
    return re.sub(r"\s+", " ", text)


def phrase_re(phrase):
    """Whitespace-tolerant regex built from a literal phrase."""
    return re.compile(r"\s+".join(re.escape(tok) for tok in phrase.split()))


def line_hit_counts(root_dirs):
    """Counting basis: LINE hits (a line containing the substring counts
    once, regardless of how many times the substring appears on it) — the
    same unit the AC-2 predicate and its sweep table operate on. Mirrors
    `grep -rn "create-spec" <root_dirs>` without shelling out."""
    counts = {}
    for root_dir in root_dirs:
        for dirpath, _dirnames, filenames in os.walk(root_dir):
            for name in filenames:
                path = os.path.join(dirpath, name)
                try:
                    with open(path, encoding="utf-8") as fh:
                        lines = fh.readlines()
                except (UnicodeDecodeError, OSError):
                    continue
                n = sum(1 for ln in lines if "create-spec" in ln)
                if n:
                    counts[path] = n
    return counts


def changelog_unreleased_section(body):
    m = re.search(r"(?m)^## \[Unreleased\]\s*$", body)
    if m is None:
        raise AssertionError("plugins/acs/CHANGELOG.md must retain the "
                              "'## [Unreleased]' heading")
    start = m.end()
    nxt = re.search(r"(?m)^## \[", body[start:])
    end = start + nxt.start() if nxt else len(body)
    return body[start:end]


class Ac2ExactSetPredicateTest(unittest.TestCase):
    """Assertion 1 (load-bearing): after the sweep, the set of files under
    plugins/acs/{skills,agents}/** containing "create-spec" is exactly
    {code/SKILL.md, code-planner.md, code-verifier.md} with per-file
    line-hit counts {2, 1, 2}. Requires spec 01 already landed (see the
    spec's "Why this spec is last")."""

    @classmethod
    def setUpClass(cls):
        cls.counts = line_hit_counts([SKILLS_DIR, AGENTS_DIR])

    def test_exact_file_set(self):
        expected_files = {CODE_SKILL, CODE_PLANNER, CODE_VERIFIER}
        self.assertEqual(
            set(self.counts.keys()), expected_files,
            "plugins/acs/{skills,agents}/** must contain \"create-spec\" in "
            "exactly {code/SKILL.md, code-planner.md, code-verifier.md} "
            "after the sweep, got: %r" % (sorted(self.counts.keys()),))

    def test_per_file_line_hit_counts(self):
        expected = {CODE_SKILL: 2, CODE_PLANNER: 1, CODE_VERIFIER: 2}
        for path, n in expected.items():
            with self.subTest(path=path):
                self.assertEqual(
                    self.counts.get(path), n,
                    "%s must carry exactly %d create-spec line hit(s), "
                    "found %r" % (path, n, self.counts.get(path)))


class ProvenanceSurvivorsTest(unittest.TestCase):
    """Assertion 2: each of the 5 surviving lines matches one of the five
    pinned past-tense provenance substrings — positive match, never absence
    of token (Decision 3: "zero occurrences" is not an available predicate
    because code/SKILL.md's clause is itself test-pinned elsewhere)."""

    def test_each_pinned_provenance_substring_present(self):
        for path, phrase in PROVENANCE_SUBSTRINGS:
            with self.subTest(path=path, phrase=phrase):
                self.assertRegex(norm(read(path)), phrase_re(phrase))

    def test_code_planner_adr_reference_present(self):
        self.assertIn("ADR 0037-0039", read(CODE_PLANNER))


class Rule2HygieneTest(unittest.TestCase):
    """Assertion 3 (load-bearing): none of the 7 Rule-2-affected files
    contains a duplicated stage after the rewrite — the regression test for
    the exact failure a blind find-and-replace on a Rule-2 line would
    introduce."""

    def test_no_duplicated_acs_code_stage_on_any_line(self):
        for path in RULE2_AFFECTED_FILES:
            body = read(path)
            for lineno, line in enumerate(body.splitlines(), 1):
                with self.subTest(path=path, lineno=lineno):
                    self.assertLessEqual(
                        line.count("/acs:code"), 1,
                        "%s:%d duplicates the /acs:code stage: %r"
                        % (path, lineno, line))

    def test_no_duplicated_bare_code_stage(self):
        for path in RULE2_AFFECTED_FILES:
            body = read(path)
            self.assertIsNone(
                re.search(r"\bcode\b\s*,\s*\bcode\b", body),
                "%s contains a duplicated bare 'code' stage" % path)


class Rule1CreateDesignRoutingTest(unittest.TestCase):
    """Assertion 4 (part 1): create-design/SKILL.md's 7 Rule-1 lines each
    now name /acs:code — a positive replacement check, not merely an
    absence-of-create-spec check (a silent deletion would also pass an
    absence check while dropping the routing target)."""

    def test_all_seven_lines_route_to_code(self):
        body_norm = norm(read(CREATE_DESIGN_SKILL))
        for phrase in CREATE_DESIGN_ROUTING_PHRASES:
            with self.subTest(phrase=phrase):
                self.assertRegex(body_norm, phrase_re(phrase))


class Rule1CreateTicketNextLineBothOccurrencesTest(unittest.TestCase):
    """Assertion 4 (part 2): create-ticket/SKILL.md's "Next" line carries the
    token twice (ticket branch + epic-child branch) — a partial fix that
    corrects only one occurrence must fail this assertion."""

    def test_next_line_both_occurrences_route_to_code(self):
        body_norm = norm(read(CREATE_TICKET_SKILL))
        self.assertRegex(body_norm, phrase_re(
            "**Next**: `/acs:create-design <id>` when `needs_design` is "
            "true, else `/acs:code <id>`; for an epic, each child continues "
            "with `/acs:code <child-id>` after the epic's design"))


class Rule1RemainingSitesTest(unittest.TestCase):
    """Assertion 8: the 5 Rule-1 sites assertion 4 does not reach —
    create-ticket/SKILL.md's other 3 lines, create-design-executor.md, and
    create-ticket-executor.md — each proven REPLACED, not merely absent."""

    def test_create_ticket_pipeline_starts_at_code(self):
        body_norm = norm(read(CREATE_TICKET_SKILL))
        self.assertRegex(
            body_norm, phrase_re("their pipeline starts at /acs:code"))

    def test_create_ticket_epic_children_next_step_pair(self):
        body_norm = norm(read(CREATE_TICKET_SKILL))
        self.assertRegex(body_norm, phrase_re(
            "`/acs:code <id>` (epic children each continue with"))
        self.assertRegex(body_norm, phrase_re(
            "`/acs:code <child-id>` after the epic's design). "
            "Under /acs:ship: return"))

    def test_create_design_executor_inherit_phrase(self):
        body_norm = norm(read(CREATE_DESIGN_EXECUTOR))
        self.assertRegex(body_norm, phrase_re(
            "child tickets inherit this design in their /acs:code"))

    def test_create_ticket_executor_capture_phrase(self):
        body_norm = norm(read(CREATE_TICKET_EXECUTOR))
        self.assertRegex(
            body_norm,
            phrase_re("/acs:code. Capture each printed `ticket_id`"))


class Rule2OutcomeTextTest(unittest.TestCase):
    """Assertion 9: the Rule-2 rewrites produced the positive re-flowed
    outcome text, not merely a token deletion — proves the list was
    re-flowed rather than the surrounding clause deleted wholesale."""

    def test_five_identical_lines_now_two_item_form(self):
        for path in RULE2_IDENTICAL_FILES:
            with self.subTest(path=path):
                self.assertIn(
                    "/acs:create-design and /acs:code are not involved):",
                    read(path))

    def test_init_pipeline_recital_adjacency(self):
        body = read(INIT_SKILL)
        self.assertRegex(
            norm(body), phrase_re("`/acs:create-design` → `/acs:code`"))
        self.assertNotIn("create-spec", body)


class Dr1HandoffScanOrderTest(unittest.TestCase):
    """Assertion 5: handoff/SKILL.md Step 2 bullet 3 references
    acs_lib.HOOKED_SKILLS instead of restating the list, carries no
    create-spec token, and any skill count it states matches
    len(acs_lib.HOOKED_SKILLS) computed live so the assertion cannot itself
    re-drift if HOOKED_SKILLS changes again later."""

    @classmethod
    def setUpClass(cls):
        body = read(HANDOFF_SKILL)
        start = body.index("3. **Scan**")
        end = body.index("If no skill is in flight")
        cls.bullet = body[start:end]
        cls.bullet_norm = norm(cls.bullet)

    def test_references_hooked_skills_constant(self):
        self.assertIn("acs_lib.HOOKED_SKILLS", self.bullet)
        self.assertIn("acs_lib.py", self.bullet)

    def test_no_create_spec_token(self):
        self.assertNotIn("create-spec", self.bullet)

    def test_no_restated_skill_list(self):
        # A restated enumeration looks like `name`, `name`, `name` (3+ in a
        # row) — the exact shape DR-1 says drifted; must not reappear.
        self.assertIsNone(
            re.search(r"(`[a-z][a-z-]*`,\s*){3,}", self.bullet),
            "handoff/SKILL.md must not restate the skill list — reference "
            "acs_lib.HOOKED_SKILLS instead (DR-1)")

    def test_do_not_restate_rationale_present(self):
        self.assertRegex(self.bullet_norm, r"(?i)do not restate")

    def test_same_order_as_handoff_py_claim_still_present(self):
        self.assertRegex(
            self.bullet_norm, r"(?i)handoff\.py.{0,40}(scans|itself scans)")

    def test_stated_counts_match_live_hooked_skills(self):
        product_n = len(lib.PRODUCT_SKILLS)
        workflow_n = len(lib.WORKFLOW_SKILLS)
        total_n = len(lib.HOOKED_SKILLS)
        self.assertIn(
            "%d product" % product_n, self.bullet,
            "bullet's stated product-skill count must equal "
            "len(acs_lib.PRODUCT_SKILLS) (%d) computed live" % product_n)
        self.assertIn(
            "%d workflow" % workflow_n, self.bullet,
            "bullet's stated workflow-skill count must equal "
            "len(acs_lib.WORKFLOW_SKILLS) (%d) computed live" % workflow_n)
        self.assertIn(
            str(total_n), self.bullet,
            "bullet must state the total skill count matching "
            "len(acs_lib.HOOKED_SKILLS) (%d) computed live" % total_n)


class ChangelogUnreleasedEntryTest(unittest.TestCase):
    """Assertion 6: the [Unreleased] section names both mechanism-gap
    closures and the sweep; nothing at/below [0.4.5] is disturbed."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(CHANGELOG)
        cls.section = changelog_unreleased_section(cls.body)
        cls.section_norm = norm(cls.section)

    def test_unreleased_section_non_empty(self):
        self.assertTrue(
            self.section.strip(),
            "plugins/acs/CHANGELOG.md's [Unreleased] section must be "
            "non-empty")

    def test_gap1_closure_named(self):
        self.assertRegex(self.section_norm, r"(?i)oversiz\w*|split")

    def test_gap2_closure_named(self):
        self.assertRegex(
            self.section_norm, r"(?i)adr[- ]?0012|doc-consistency|doc-graph")

    def test_sweep_named(self):
        self.assertRegex(self.section_norm, r"(?i)create-spec")

    def test_0_4_5_heading_undisturbed(self):
        self.assertIn("## [0.4.5] - 2026-07-23", self.body)


class NegativeGuardsBackwardCompatTest(unittest.TestCase):
    """Assertion 7 (over-eager-sweep catch): plugins/acs/hooks/** and
    plugins/acs/schemas/** still carry their backward-compat create-spec
    anchors — asserted PRESENT, not absent; ship/SKILL.md stays free of the
    token."""

    def test_xsd_enum_present(self):
        self.assertIn(
            '<xs:enumeration value="create-spec"/>', read(XSD))

    def test_skill_state_schema_enum_present(self):
        self.assertIn('"create-spec"', read(SKILL_STATE_SCHEMA))

    def test_clarifications_schema_enum_present(self):
        self.assertIn('"create-spec"', read(CLARIFICATIONS_SCHEMA))

    def test_statusline_py_pair_present(self):
        self.assertIn('("create-spec", "spec")', read(STATUSLINE_PY))

    def test_subagent_statusline_alternation_present(self):
        self.assertIn("create-spec", read(SUBAGENT_STATUSLINE_PY))

    def test_validate_xml_py_set_member_present(self):
        self.assertIn('"create-spec"', read(VALIDATE_XML_PY))

    def test_ship_skill_free_of_create_spec(self):
        self.assertNotIn("create-spec", read(SHIP_SKILL))


if __name__ == "__main__":
    unittest.main()
