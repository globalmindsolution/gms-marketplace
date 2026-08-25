"""Prose-contract tests for the citation-corroboration mechanism shared by the
create-quality/-standards/-operations/-principles planner and verifier
charters.

This module currently covers only the planner half: each of the 4 planners'
`Upstream inventory` section must mandate a verbatim quoted excerpt per
citation, state the citation grammar, mark the line/range advisory-only, and
(create-standards only) keep its `principles/ N/A: <why>` note, explicitly
exempted from the new grammar. Later commits extend this same module with
the verifier-side (`plan-conformance` dimension invoking the shared
`citation_check.py` floor) and SKILL.md-mirror coverage.

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


if __name__ == "__main__":
    unittest.main()
