"""MAR-115 spec 01 — shared ADR-0012 design-time doc-consistency planner step.

Prose-contract unit tests for the canonical "Design-time doc-consistency step
(ADR 0012)" block, transcribed byte-identically into the planner phase of all
six design-producing skills' planner agents, plus the C-1 verifier-dimension
expansion (create-quality-verifier.md / create-operations-verifier.md) and the
doc tail (ADR 0012 status flip, CHANGELOG bullet, skills.md notes).

Stdlib-only (hashlib, os, re, unittest), mirroring the bounded-window
`section()` helper from tests/acs/test_mar112_quality_path_init.py and the
presence-in-all-six loop style of
tests/acs/test_skill_contracts.py::test_grounding_section_everywhere, so a
stray mention elsewhere in a file can never satisfy an assertion meant for the
canonical block.

Run:  python3 -m unittest discover -s tests
"""

import hashlib
import os
import re
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN = os.path.join(REPO_ROOT, "plugins", "acs")
AGENTS = os.path.join(PLUGIN, "agents")
SKILLS = os.path.join(PLUGIN, "skills")
CHANGELOG = os.path.join(PLUGIN, "CHANGELOG.md")
ADR_0012 = os.path.join(REPO_ROOT, "docs", "adr", "0012-design-time-doc-consistency.md")
ADR_0011 = os.path.join(REPO_ROOT, "docs", "adr", "0011-sdlc-doc-sets-quality-and-operations.md")
SKILLS_MD = os.path.join(REPO_ROOT, "docs", "requirements", "functional", "skills.md")

PLANNERS = [
    "create-prd-planner.md",
    "create-architecture-planner.md",
    "create-design-planner.md",
    "create-spec-planner.md",
    "create-quality-planner.md",
    "create-operations-planner.md",
]

NEW_VERIFIERS = ["create-quality-verifier.md", "create-operations-verifier.md"]

CANONICAL_HEADING = "### Design-time doc-consistency step (ADR 0012)"

FORBIDDEN_NEW_MECHANISM_MARKERS = [
    "/doctor",
    "pre-commit",
    "CI gate",
    "new subagent",
    "pre-mar115",
    "post-mar115",
]


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def section(body, heading):
    """Return the text of a markdown section: from the line whose start is
    `heading` (matched at line-start) up to the next same-or-higher-level
    heading (or end of file)."""
    m = re.search(r"(?m)^" + re.escape(heading) + r".*$", body)
    if m is None:
        raise AssertionError("heading %r not found" % heading)
    start = m.start()
    level = len(heading) - len(heading.lstrip("#"))
    nxt = re.search(r"(?m)^#{1,%d} \S" % level, body[m.end():])
    end = m.end() + nxt.start() if nxt else len(body)
    return body[start:end]


def planner_path(name):
    return os.path.join(AGENTS, name)


def verifier_path(name):
    return os.path.join(AGENTS, name)


class Mar115CanonicalBlockCase(unittest.TestCase):
    """Fixture: read all six planners once, extract the canonical block."""

    @classmethod
    def setUpClass(cls):
        cls.bodies = {name: read(planner_path(name)) for name in PLANNERS}
        cls.blocks = {}
        for name, body in cls.bodies.items():
            cls.blocks[name] = section(body, CANONICAL_HEADING)

    # AC-1: presence in all six planners
    def test_ac1_canonical_block_present_in_all_six_planners(self):
        for name in PLANNERS:
            with self.subTest(planner=name):
                self.assertIn(
                    CANONICAL_HEADING, self.bodies[name],
                    "%s missing the canonical ADR-0012 doc-consistency block" % name,
                )

    # AC-2: cross-six md5 identity of the extracted block
    def test_ac2_canonical_block_is_md5_identical_across_all_six(self):
        digests = {
            name: hashlib.md5(block.encode("utf-8")).hexdigest()
            for name, block in self.blocks.items()
        }
        unique = set(digests.values())
        self.assertEqual(
            len(unique), 1,
            "canonical block drifted across planners (not byte-identical): %r" % digests,
        )

    # AC-3: both upstream and downstream named, within the block, all six
    def test_ac3_upstream_and_downstream_both_named(self):
        for name in PLANNERS:
            with self.subTest(planner=name):
                block = self.blocks[name]
                self.assertIn("upstream", block, name)
                self.assertIn("downstream", block, name)

    # AC-4: gap and staleness both named, within the block, all six
    def test_ac4_gap_and_staleness_both_named(self):
        for name in PLANNERS:
            with self.subTest(planner=name):
                block = self.blocks[name]
                self.assertIn("gap", block, name)
                self.assertIn("staleness", block, name)

    # AC-5: finding shape keys + kind literal values, within the block, all six
    def test_ac5_finding_shape_keys_present(self):
        keys = ["kind", "upstream", "downstream", "description", "recommendation"]
        for name in PLANNERS:
            with self.subTest(planner=name):
                block = self.blocks[name]
                for key in keys:
                    self.assertIn('"%s"' % key, block, "%s missing shape key %s" % (name, key))
                self.assertIn('"gap"', block, name)
                self.assertIn('"staleness"', block, name)

    # AC-6: existing clarification-ledger output path + negative new-mechanism markers
    def test_ac6_existing_output_channel_no_new_tooling(self):
        for name in PLANNERS:
            with self.subTest(planner=name):
                block = self.blocks[name]
                self.assertTrue(
                    "<questions>" in block or "clarification ledger" in block,
                    "%s canonical block does not reference the existing output channel" % name,
                )
                for marker in FORBIDDEN_NEW_MECHANISM_MARKERS:
                    self.assertNotIn(
                        marker, block,
                        "%s canonical block leaks rejected ADR-0012 alternative marker %r" % (name, marker),
                    )

    # AC-7: D4 lifecycle - three clauses (user decides, executor updates, verifier confirms)
    def test_ac7_d4_lifecycle_three_clauses(self):
        for name in PLANNERS:
            with self.subTest(planner=name):
                block = self.blocks[name]
                self.assertIn("user decides", block, name)
                self.assertIn("executor updates", block, name)
                self.assertIn("verifier confirms", block, name)

    # AC-8: /acs:test never named as a consistency participant except "unaffected" framing
    def test_ac8_acs_test_unaffected_negative_assertion(self):
        for name in PLANNERS:
            with self.subTest(planner=name):
                body = self.bodies[name]
                for m in re.finditer(re.escape("/acs:test"), body):
                    window = body[max(0, m.start() - 200):m.end() + 200]
                    self.assertIn(
                        "unaffected", window,
                        "%s names /acs:test outside an 'unaffected' framing near: %r" % (name, window),
                    )


class Mar115StandingBehaviorReplaceCase(unittest.TestCase):
    """R4: quality/operations planners must REPLACE the old upstream-only
    item-4 hint with the canonical block, not append alongside it."""

    def test_quality_planner_old_upstream_only_hint_removed(self):
        body = read(planner_path("create-quality-planner.md"))
        self.assertNotRegex(
            body,
            r"Read the upstream doc-graph slice.*for gaps or\s*\n?\s*staleness",
            "create-quality-planner.md still carries the old upstream-only hint alongside the new block",
        )

    def test_operations_planner_old_upstream_only_hint_removed(self):
        body = read(planner_path("create-operations-planner.md"))
        self.assertNotRegex(
            body,
            r"Read the upstream doc-graph slice.*for gaps or\s*\n?\s*staleness",
            "create-operations-planner.md still carries the old upstream-only hint alongside the new block",
        )


class Mar115ConsistencyVerifierDimensionCase(unittest.TestCase):
    """C-1: create-quality-verifier.md and create-operations-verifier.md gain
    a sixth `consistency` check dimension."""

    def test_new_verifiers_have_consistency_dimension(self):
        for name in NEW_VERIFIERS:
            with self.subTest(verifier=name):
                body = read(verifier_path(name))
                m = re.search(r"(?m)^\d+\.\s+\*\*consistency\*\*", body)
                self.assertIsNotNone(
                    m, "%s missing a numbered `consistency` check dimension" % name
                )

    def _bounded_window(self, body, marker, window=1200):
        idx = body.find(marker)
        if idx == -1:
            raise AssertionError("marker %r not found" % marker)
        # bound the window at the next top-level ## heading (or end of file)
        nxt = re.search(r"(?m)^## \S", body[idx:])
        end = idx + nxt.start() if nxt else min(len(body), idx + window)
        return body[idx:end]

    def test_quality_skillmd_verify_list_names_consistency(self):
        body = read(os.path.join(SKILLS, "create-quality", "SKILL.md"))
        verify_section = self._bounded_window(body, "3. **Verify**")
        self.assertIn("consistency", verify_section)

    def test_operations_skillmd_verify_list_names_consistency(self):
        body = read(os.path.join(SKILLS, "create-operations", "SKILL.md"))
        verify_section = self._bounded_window(body, "3. **Verify**")
        self.assertIn("consistency", verify_section)


class Mar115SkillMdPointerCase(unittest.TestCase):
    """AC step 3: each of the six SKILL.md files gains a one-line plan-phase
    pointer sentence referencing the shared ADR-0012 step."""

    SKILL_DIRS = [
        "create-prd",
        "create-architecture",
        "create-design",
        "create-spec",
        "create-quality",
        "create-operations",
    ]

    def test_each_skillmd_mentions_adr_0012_step(self):
        for skill in self.SKILL_DIRS:
            with self.subTest(skill=skill):
                body = read(os.path.join(SKILLS, skill, "SKILL.md"))
                self.assertRegex(
                    body, r"ADR[ -]0012",
                    "%s/SKILL.md missing the planner-phase ADR-0012 pointer sentence" % skill,
                )


class Mar115DocTailCase(unittest.TestCase):
    """AC-9: ADR 0012 -> Accepted, ADR 0011 unchanged, CHANGELOG bullet,
    skills.md count unchanged + six sections gained a sentence."""

    def test_adr_0012_status_accepted(self):
        body = read(ADR_0012)
        m = re.search(r"(?m)^\*\*Status\*\*:\s*(\S+)", body)
        self.assertIsNotNone(m, "ADR 0012 missing a Status line")
        self.assertEqual(m.group(1).rstrip(" ·"), "Accepted")

    def test_adr_0011_status_unchanged_still_present(self):
        # Non-regression pin: MAR-115 does not touch ADR 0011's Status line.
        # We only assert a Status line is present (whatever MAR-114 set it
        # to) — the literal value is owned by MAR-114, not this ticket.
        body = read(ADR_0011)
        m = re.search(r"(?m)^\*\*Status\*\*:\s*(\S+)", body)
        self.assertIsNotNone(m, "ADR 0011 missing a Status line")

    def test_changelog_has_mar115_bullet_durable(self):
        # Durable invariant: the MAR-115 entry must live under [Unreleased] or a
        # dated semver heading — a release cut legitimately graduates it from
        # [Unreleased] into a versioned section (never pin the literal
        # [Unreleased] anchor).
        body = read(CHANGELOG)
        spans = [m.start() for m in re.finditer(r"## \[[^\]]*\]", body)] + [len(body)]
        section_text = None
        for start, end in zip(spans, spans[1:]):
            if "MAR-115" in body[start:end]:
                section_text = body[start:end]
                break
        self.assertIsNotNone(
            section_text, "CHANGELOG.md must contain a MAR-115 bullet in a section span")
        heading = section_text[:section_text.index("\n")]
        self.assertRegex(
            heading, r"## \[(Unreleased|\d+\.\d+\.\d+)\]",
            "the MAR-115 entry must live under [Unreleased] or a dated semver heading")

    def test_skills_md_count_line_unchanged_nineteen(self):
        # MAR-115 itself did not touch this line (its own non-regression
        # pin); a later legitimate skill-count bump (MAR-117: Twenty)
        # supersedes the literal word this test originally asserted, so only
        # the "in total" shape is pinned here, not a specific count word.
        body = read(SKILLS_MD)
        head = body[:200]
        self.assertIn("skills in total", head)

    def test_skills_md_six_sections_gained_doc_consistency_sentence(self):
        body = read(SKILLS_MD)
        headings = [
            "## `/create-prd` (product-level)",
            "## `/create-architecture` (product-level)",
            "## `/acs:create-quality` (product-level)",
            "## `/acs:create-operations` (product-level)",
            "## 2. `/create-design` *(conditional)*",
            "## 3. `/create-spec`",
        ]
        for heading in headings:
            with self.subTest(heading=heading):
                sect = section(body, heading)
                self.assertRegex(
                    sect, r"ADR[ -]0012",
                    "skills.md section %r missing the planner-phase ADR-0012 sentence" % heading,
                )


if __name__ == "__main__":
    unittest.main()
