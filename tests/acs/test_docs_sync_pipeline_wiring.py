"""MAR-160 spec 02 — pipeline/ship wiring for the new docs-sync hooked skill.

Covers ship/SKILL.md's "Pipeline order" table and "Picking the next step"
walk gaining docs-sync between test and create-pr, and the file-content-token
regression guard for the two mechanisms the AC-7 scope-boundary guard
(git-history diff check, retired by MAR-162 — see
test_code_skill_and_verifier_absent_from_this_branch_diff) used to protect:
`code/SKILL.md`'s retained product-doc reconciliation step and
`code-verifier.md`'s blocking Documentation dimension.

Run:  python3 -m unittest tests.acs.test_docs_sync_pipeline_wiring -v
"""

import os
import re
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN = os.path.join(REPO_ROOT, "plugins", "acs")
SHIP_SKILL = os.path.join(PLUGIN, "skills", "ship", "SKILL.md")
CODE_SKILL = os.path.join(PLUGIN, "skills", "code", "SKILL.md")
CODE_VERIFIER = os.path.join(PLUGIN, "agents", "code-verifier.md")


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def section(body, heading):
    """Return the text of a markdown section: from the line whose start is
    `heading` up to the next same-or-higher-level heading (or end of file)."""
    m = re.search(r"(?m)^" + re.escape(heading) + r".*$", body)
    if m is None:
        raise AssertionError("heading %r not found" % heading)
    start = m.start()
    level = len(heading) - len(heading.lstrip("#"))
    nxt = re.search(r"(?m)^#{1,%d} \S" % level, body[m.end():])
    end = m.end() + nxt.start() if nxt else len(body)
    return body[start:end]


class PipelineOrderTableTest(unittest.TestCase):
    def test_pipeline_order_table_has_docs_sync_between_test_and_create_pr(self):
        table = section(read(SHIP_SKILL), "## Pipeline order")
        rows = re.findall(r"(?m)^\|\s*\d+\s*\|\s*(\S[^|]*?)\s*\|", table)
        self.assertIn("docs-sync", rows, "Pipeline order table must have a docs-sync row: %r" % rows)
        test_idx = next(i for i, r in enumerate(rows) if r.startswith("test"))
        docs_sync_idx = rows.index("docs-sync")
        create_pr_idx = rows.index("create-pr")
        self.assertLess(test_idx, docs_sync_idx,
                        "docs-sync must be positioned after test")
        self.assertLess(docs_sync_idx, create_pr_idx,
                        "docs-sync must be positioned before create-pr")


class PickingNextStepWalkTest(unittest.TestCase):
    def test_walk_contains_docs_sync_between_test_and_create_pr(self):
        body = read(SHIP_SKILL)
        section_start = body.index("## Picking the next step")
        next_heading = re.search(r"\n## ", body[section_start + 1:])
        walk_section = body[section_start:section_start + 1 + next_heading.start()] \
            if next_heading else body[section_start:]
        normalized = re.sub(r"\s+", " ", walk_section)
        self.assertIn("test (when the gate is active", normalized)
        m = re.search(r"test \(when the gate is active.*?\) → (\S+) → create-pr", normalized)
        self.assertIsNotNone(
            m, "the walk must name a step between the test-gate clause and create-pr")
        self.assertEqual(m.group(1), "docs-sync")


class Ac7ScopeBoundaryTest(unittest.TestCase):
    """AC-7: code/SKILL.md's step 4 and code-verifier.md's dimension 11 stay
    fully functional and untouched by this ticket."""

    def test_code_skill_and_verifier_absent_from_this_branch_diff(self):
        """MAR-160's scope-boundary carve-out guard; superseded by MAR-162,
        which legitimately touches code/SKILL.md and code-verifier.md to
        retire the old mechanism. Retired as a documented skip, never a bare
        deletion — see test_code_doc_authoring_retired.py for the guard that
        replaces it (asserts what was retired, not merely that these files
        changed)."""
        self.skipTest(
            "superseded by MAR-162: code/SKILL.md and code-verifier.md are "
            "legitimately touched by the ticket that retires /code's "
            "in-loop doc-sync")

    def test_code_skill_still_has_product_doc_reconciliation_step(self):
        self.assertIn("Product-doc factual reconciliation", read(CODE_SKILL))

    def test_code_verifier_still_has_blocking_documentation_dimension(self):
        self.assertIn('severity="blocking" dimension="documentation"', read(CODE_VERIFIER))


if __name__ == "__main__":
    unittest.main()
