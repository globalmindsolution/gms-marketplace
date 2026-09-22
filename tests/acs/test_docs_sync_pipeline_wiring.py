"""MAR-160 spec 02 — pipeline/ship wiring for the new docs-sync hooked skill.

Covers ship/SKILL.md's "Pipeline order" table and "Picking the next step"
walk gaining docs-sync between test and create-pr, and the file-content-token
regression guard for the two mechanisms the AC-7 scope-boundary guard
(git-history diff check, retired by MAR-162 — see
test_code_skill_and_verifier_absent_from_this_branch_diff) used to protect:
`code/SKILL.md`'s retained product-doc reconciliation step and the blocking
documentation check the review carries.

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
#: ADR-0095 split /acs:code into a dispatcher plus the references its four
#: delivery paths share, so what used to be one SKILL.md body is read from
#: the reference that carries it: the execute instruction.
CODE_SKILL = os.path.join(PLUGIN, "skills", "code", "references", "execute.md")
#: The review left /acs:code for /acs:review-code in v0.5.0, so the
#: documentation check is read where it now lives.
REVIEW_CODE_SKILL = os.path.join(PLUGIN, "skills", "review-code", "SKILL.md")


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
    workflows/ship.yaml: the table is gone from the skill, and docs-sync's
    position is the LIST's. v0.5.0 removed `needs:` with every other
    per-step key -- the declared order IS the dependency order -- so the
    position is asserted as an index, which is what the engine reads."""

    def test_ship_yaml_orders_docs_sync_after_code_and_before_create_pr(self):
        steps = lib.steps_of(lib.validate_workflow_file(lib.default_workflow_path()))
        for name in ("code", "docs-sync", "create-pr"):
            self.assertIn(name, steps, "ship.yaml must declare a %s step" % name)
        self.assertLess(steps.index("code"), steps.index("docs-sync"),
                        "docs-sync must follow code")
        self.assertLess(steps.index("docs-sync"), steps.index("create-pr"),
                        "create-pr must follow docs-sync")

    def test_ship_skill_no_longer_carries_a_prose_order_table(self):
        self.assertNotIn("## Pipeline order", read(SHIP_SKILL))


class PickingNextStepWalkTest(unittest.TestCase):
    """The next step is the run's cursor, printed by `acs.py run next`; the
    skill delegates to it instead of restating an order."""

    def test_the_skill_delegates_the_next_step_to_run_next(self):
        walk_section = section(read(SHIP_SKILL), "## The loop")
        self.assertIn("acs.py", walk_section)
        self.assertIn("run next", walk_section)

    def test_the_skill_states_no_hard_coded_order(self):
        body = re.sub(r"\s+", " ", read(SHIP_SKILL))
        self.assertIn("never hard-code a step sequence", body)


class Ac7ScopeBoundaryTest(unittest.TestCase):
    """AC-7: /acs:code's product-doc reconciliation and the review's blocking
    documentation check stay fully functional."""

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

    def test_the_review_still_blocks_on_documentation(self):
        """The check outlived the verifier that carried it: it is lens A's
        acceptance scope now, and `kind` replaced the dimension number."""
        body = re.sub(r"\s+", " ", read(REVIEW_CODE_SKILL))
        self.assertIsNotNone(
            re.search(r"(?i)judges the change's own documentation, and blocks "
                      r"on it", body),
            "the review must still block on the change's own documentation")
        self.assertIsNotNone(
            re.search(r"(?i)distinct from `/acs:docs-sync`", body),
            "and must say how that differs from the docs-sync step")


if __name__ == "__main__":
    unittest.main()
