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
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN = os.path.join(REPO_ROOT, "plugins", "acs")
sys.path.insert(0, os.path.join(PLUGIN, "hooks", "scripts"))
import acs_lib as lib  # noqa: E402
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
    """The order MAR-160 wired into ship/SKILL.md's prose table moved into
    workflows/ship.yaml when the skills-independence refactor landed: the
    table is gone from the skill, and docs-sync's position is declared as a
    step whose `needs` name code, with create-pr needing docs-sync in turn.
    Assert the position where it now lives, not where it used to be."""

    def test_ship_yaml_orders_docs_sync_after_code_and_before_create_pr(self):
        doc = lib.load_workflow(lib.default_workflow_path())[0]
        steps = {step["id"]: step for step in doc["steps"]}
        self.assertIn("docs-sync", steps, "ship.yaml must declare a docs-sync step")
        self.assertIn("code", steps["docs-sync"].get("needs") or [],
                      "docs-sync must need code")
        self.assertIn("docs-sync", steps["create-pr"].get("needs") or [],
                      "create-pr must need docs-sync")

    def test_ship_skill_no_longer_carries_a_prose_order_table(self):
        self.assertNotIn("## Pipeline order", read(SHIP_SKILL))


class PickingNextStepWalkTest(unittest.TestCase):
    """The walk is computed by `acs.py workflow next`; the skill delegates to
    it instead of restating an order."""

    def test_the_skill_delegates_the_walk_to_workflow_next(self):
        walk_section = section(read(SHIP_SKILL), "## The loop")
        self.assertIn("acs.py", walk_section)
        self.assertIn("workflow next", walk_section)

    def test_the_skill_states_no_hard_coded_order(self):
        body = re.sub(r"\s+", " ", read(SHIP_SKILL))
        self.assertIn("never hard-code a step sequence", body)


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
