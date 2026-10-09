#!/usr/bin/env python3
"""create-pr's critical GitHub calls must be REST, not GraphQL porcelain.

A Claude Code session refuses GraphQL (HTTP 403), and `gh repo view`,
`gh pr list/view/create/edit` all use it, so /acs:create-pr stopped at its base
detect in such a session although `gh api` REST was served. The critical calls
now go through `gh api`, documented in references/rest-transport.md (ADR-0141).
"""

import os
import re
import unittest

SKILL = os.path.join(os.path.dirname(__file__), "..", "..", "plugins", "acs", "skills", "create-pr")
PORCELAIN = re.compile(r"`gh (repo view|pr (list|view|create|edit))\b")


def read(*parts):
    with open(os.path.join(SKILL, *parts), encoding="utf-8") as fh:
        return fh.read()


class CreatePrUsesRestForItsCriticalCalls(unittest.TestCase):

    def test_no_instruction_runs_a_graphql_porcelain_command(self):
        for rel in (("SKILL.md",), ("references", "publish.md"), ("references", "resume.md")):
            text = read(*rel)
            # The one sentence that NAMES the commands to avoid is allowed.
            text = text.replace(
                "Use the REST calls in `references/rest-transport.md`, not `gh pr\n"
                "   create` / `gh pr edit` / `gh pr view` / `gh pr list` / `gh repo view`:", "")
            with self.subTest(file=os.path.join(*rel)):
                self.assertIsNone(PORCELAIN.search(text), PORCELAIN.search(text))

    def test_the_rest_reference_covers_every_critical_call(self):
        text = read("references", "rest-transport.md")
        for needle in ("--jq .default_branch", "/pulls?head=", "/pulls -f title=",
                       "-X PATCH", "/issues/<number>/labels", "ready_for_review"):
            with self.subTest(needle=needle):
                self.assertIn(needle, text)

    def test_the_skill_points_at_the_reference(self):
        self.assertIn("references/rest-transport.md", read("SKILL.md"))


if __name__ == "__main__":
    unittest.main()
