"""SKILL.md and agent files have a size budget; the ones over it can only shrink.

AUTHORING.md asks for 180-330 lines per SKILL.md and 60-140 per agent. Nothing
checked it, and the files drifted far past it: analyze-requirements reached 1,065
lines, most of it procedure a run reads only in some arms. Progressive disclosure
(`references/*.md`, read when a condition holds) is the remedy; this test is the
ratchet that keeps the remedy from rotting.

Two budgets, softer than AUTHORING's so that a new file has room:
- a SKILL.md stays at or under ``SKILL_BUDGET`` lines;
- an agent stays at or under ``AGENT_BUDGET`` lines.

A file already over its budget is named in ``CEILINGS`` with the size it may not
grow past. The list is honest both ways: an entry for a file that no longer
exists, or that has come back under the budget, fails -- delete the entry, so
the next growth is caught by the budget itself. Trimming a listed file means
lowering its ceiling in the same change.
"""

import glob
import os
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN = os.path.join(REPO_ROOT, "plugins", "acs")

SKILL_BUDGET = 400
AGENT_BUDGET = 200

#: Plugin-relative path -> the most lines it may have. Each is today's size
#: rounded up to ten; lower it when the file is trimmed.
CEILINGS = {
    "skills/analyze-requirements/SKILL.md": 450,
    "skills/create-api-contract/SKILL.md": 410,
    "skills/create-impl-plan/SKILL.md": 450,
    "skills/create-architecture/SKILL.md": 630,
    "skills/create-e2e-tests/SKILL.md": 720,
    "skills/create-flows/SKILL.md": 410,
    "skills/create-pr/SKILL.md": 620,
    "skills/create-test-docs/SKILL.md": 640,
    "skills/docs-sync/SKILL.md": 580,
    "skills/merge-pr/SKILL.md": 490,
    "skills/run-e2e-tests/SKILL.md": 410,
    "agents/analyze-requirements-analyst.md": 300,
    "agents/analyze-requirements-impact-reviewer.md": 270,
    "agents/code-implementer.md": 290,
    "agents/create-api-contract-contract-author.md": 270,
    "agents/create-architecture-architect.md": 340,
    "agents/create-architecture-reviewer.md": 230,
    "agents/create-e2e-tests-suite-runner.md": 230,
    "agents/create-e2e-tests-test-writer.md": 280,
    "agents/create-impl-plan-plan-reviewer.md": 240,
    "agents/create-impl-plan-planner.md": 350,
    "agents/create-prd-reviewer.md": 230,
    "agents/create-prd-surveyor.md": 240,
    "agents/create-tech-design-designer.md": 300,
    "agents/create-tech-design-reviewer.md": 260,
    "agents/create-test-docs-test-designer.md": 270,
    "agents/docs-sync-doc-updater.md": 310,
}


def line_count(path):
    with open(path, encoding="utf-8") as fh:
        return sum(1 for _ in fh)


def sized_files():
    """(plugin-relative path, lines, budget) for every SKILL.md and agent."""
    for path in sorted(glob.glob(os.path.join(PLUGIN, "skills", "*", "SKILL.md"))):
        yield os.path.relpath(path, PLUGIN), line_count(path), SKILL_BUDGET
    for path in sorted(glob.glob(os.path.join(PLUGIN, "agents", "*.md"))):
        yield os.path.relpath(path, PLUGIN), line_count(path), AGENT_BUDGET


class SkillSizeBudgetTest(unittest.TestCase):

    def test_no_file_is_over_its_budget_or_ceiling(self):
        over = []
        for rel, lines, budget in sized_files():
            limit = CEILINGS.get(rel, budget)
            if lines > limit:
                over.append("%s: %d lines > %d" % (rel, lines, limit))
        self.assertEqual(over, [], "move procedure into references/*.md: %s" % over)

    def test_every_ceiling_names_a_file_still_over_the_budget(self):
        sizes = {rel: (lines, budget) for rel, lines, budget in sized_files()}
        stale = []
        for rel in sorted(CEILINGS):
            if rel not in sizes:
                stale.append("%s: no such file" % rel)
            elif sizes[rel][0] <= sizes[rel][1]:
                stale.append("%s: %d lines, back under %d" % ((rel,) + sizes[rel]))
        self.assertEqual(stale, [], "delete these CEILINGS entries: %s" % stale)

    def test_a_ceiling_is_above_the_budget(self):
        for rel, ceiling in CEILINGS.items():
            budget = SKILL_BUDGET if rel.startswith("skills/") else AGENT_BUDGET
            self.assertGreater(ceiling, budget, rel)


if __name__ == "__main__":
    unittest.main()
