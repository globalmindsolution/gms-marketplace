"""Prose-contract tests for the citation-corroboration mechanism's surviving
surface. Written for MAR-303 against four planner/verifier pairs; ADR-0094
folded those into /acs:create-docs, and ADR-0124 removed that skill, its
author and its reviewer -- the charters whose `Upstream inventory` grammar and
`authoring-conformance` corroboration most of this module pinned.

What is left is what other skills still rely on: exactly one
`citation_check.py` (which `prd_conformance_check.py` imports unchanged),
`create-prd-reviewer.md` untouched by it with its nine dimensions, and
create-prd's loop surveying once rather than re-planning every iteration.

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

PRD_VERIFIER = "create-prd-reviewer.md"  # create-prd's judge

# create-prd-reviewer.md's 9 pre-existing dimension labels (AC-5 negative
# pin) — mirrors the VERIFIERS["create-prd-reviewer.md"] entry in
# test_structure_audience_verifiers.py:56-64.
PRD_VERIFIER_DIMENSIONS = (
    "Required sections", "Feature -> goal traceability",
    "Measurable success metrics", "Prioritization discipline",
    "Constraint consistency", "Roadmap coverage", "Plan conformance",
    "Amend-mode diff discipline", "Iteration 2+ regression check",
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


def dimension_present(body, label):
    """True if `label` is a numbered check-dimension entry (bold, backtick, or
    bold+backtick-wrapped)."""
    return re.search(r"(?m)^\d+\.\s+%s" % _label_pattern(label), body) is not None



class SharedIdenticallyTest(unittest.TestCase):
    """AC-4: exactly one citation_check.py exists, under
    plugins/acs/hooks/scripts/."""

    def test_exactly_one_citation_check_script(self):
        found = []
        for root, _dirs, files in os.walk(PLUGIN):
            for f in files:
                if f == "citation_check.py":
                    found.append(os.path.join(root, f))
        self.assertEqual(
            found, [os.path.join(PLUGIN, "hooks", "scripts", "citation_check.py")],
            "expected exactly one citation_check.py, under hooks/scripts/: %r" % found)


class CreatePrdUntouchedTest(unittest.TestCase):
    """AC-5: create-prd-reviewer.md contains no citation_check.py reference
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


class LoopTopologyMigratedTest(unittest.TestCase):
    """AC-5 (MAR-305): create-prd's SKILL.md carries no per-iteration planner
    re-spawn sentence (plan -> execute -> verify); it surveys exactly once
    per run (its surveyor, iteration 1 only), then authors and reviews."""

    def test_loop_topology_migrated_by_mar305(self):
        body = read(os.path.join(SKILLS, "create-prd", "SKILL.md"))
        self.assertNotRegex(
            body.lower(), r"plan -> execute -> verify",
            "create-prd/SKILL.md must no longer carry the per-iteration "
            "re-spawn sentence (MAR-305 drops it)")
        norm = re.sub(r"\s+", " ", body)
        for stale in ("planner", "executor", "verifier"):
            self.assertNotIn("acs:create-prd-%s" % stale, norm)
        self.assertRegex(norm, r"(?i)Iteration 1 runs the surveyor once")
        self.assertRegex(norm, r"(?i)the surveyor never runs again")


if __name__ == "__main__":
    unittest.main()
