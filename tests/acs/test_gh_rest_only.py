"""acs reaches GitHub through `gh api` REST only (ADR-0149).

gh's porcelain -- `gh pr …`, `gh issue …`, `gh label …`, `gh repo view`,
`gh release list` -- runs on GitHub's GraphQL API, and a Claude Code session
refuses GraphQL with HTTP 403. /acs:release's open-PR probe was `gh pr list`,
so every cut in such a session stopped at its first step; the same call shape
sat in merge-pr's readiness reads, create-pr's metadata fill and
create-ticket's tracker sync. This guard keeps the class from coming back:

* shipped Python may build a `gh` argv only as `gh api <endpoint>` (never
  `gh api graphql`), or `gh project …` -- Projects v2 has no REST surface, so
  those calls stay GraphQL and stay non-critical (forge.py);
* skill, agent and docs text may not tell a model to run a porcelain command.
  A paragraph that names one to say it runs on GraphQL, or that it is never
  run, is describing the rule, not following the old habit.
"""

import ast
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN = os.path.join(ROOT, "plugins", "acs")

#: The gh subcommands a shipped argv may start with.
ALLOWED_SUBCOMMANDS = {"api", "project"}

#: A porcelain invocation: the command group plus a verb.
PORCELAIN = re.compile(
    r"\bgh (pr|issue|repo|label|release) (list|view|create|edit|checks|diff|merge|"
    r"update-branch|comment|close|reopen|ready|status|delete)\b")

#: Text that names a porcelain command only to state the rule.
RULE_WORDS = re.compile(r"(?i)graphql|\bnever\b")


def _python_files():
    for base, dirs, files in os.walk(PLUGIN):
        dirs[:] = [d for d in dirs if d not in ("__pycache__", "evals")]
        for name in files:
            if name.endswith(".py"):
                yield os.path.join(base, name)


def _markdown_files():
    for sub in ("skills", "agents", "docs", "templates"):
        for base, dirs, files in os.walk(os.path.join(PLUGIN, sub)):
            for name in files:
                if name.endswith(".md"):
                    yield os.path.join(base, name)


def gh_argv_violations(source, path="<source>"):
    """[(path, line, argv-head)] for every `gh` argv literal that is not REST."""
    out = []
    for node in ast.walk(ast.parse(source, path)):
        if not isinstance(node, ast.List) or len(node.elts) < 2:
            continue
        head = [e.value if isinstance(e, ast.Constant) else None for e in node.elts[:3]]
        if head[0] != "gh" or not isinstance(head[1], str):
            continue
        if head[1] not in ALLOWED_SUBCOMMANDS or (head[1] == "api" and head[2] == "graphql"):
            out.append((path, node.lineno, " ".join(str(h) for h in head if h)))
    return out


def porcelain_instructions(text, path="<text>"):
    """[(path, paragraph-start-line, command)] for porcelain a model would run."""
    out, line = [], 1
    for paragraph in re.split(r"\n\s*\n", text):
        if not RULE_WORDS.search(paragraph):
            for match in PORCELAIN.finditer(paragraph):
                out.append((path, line, match.group(0)))
        line += paragraph.count("\n") + 2
    return out


class ShippedCodeIsRestOnlyTest(unittest.TestCase):

    def test_no_shipped_python_builds_a_porcelain_or_graphql_argv(self):
        found = []
        for path in _python_files():
            with open(path, encoding="utf-8") as fh:
                found += gh_argv_violations(fh.read(), os.path.relpath(path, ROOT))
        self.assertEqual(found, [], "GraphQL-backed gh calls in shipped code (ADR-0149): "
                                    "build them with acs_lib.gh_rest instead")

    def test_no_skill_agent_or_doc_tells_a_model_to_run_porcelain(self):
        found = []
        for path in _markdown_files():
            with open(path, encoding="utf-8") as fh:
                found += porcelain_instructions(fh.read(), os.path.relpath(path, ROOT))
        self.assertEqual(found, [], "porcelain gh commands in skill text (ADR-0149): "
                                    "write the `gh api repos/{owner}/{repo}/…` call")


class GuardCatchesTheClassTest(unittest.TestCase):
    """The guard fails on the shapes it exists for, so a silent pass means clean."""

    def test_the_release_probe_shape_is_caught(self):
        source = 'argv = ["gh", "pr", "list", "--head", branch]\n'
        self.assertEqual(len(gh_argv_violations(source)), 1)

    def test_graphql_through_gh_api_is_caught(self):
        self.assertEqual(len(gh_argv_violations('["gh", "api", "graphql", "-f", q]\n')), 1)

    def test_rest_and_projects_pass(self):
        source = ('a = ["gh", "api", "repos/{owner}/{repo}/pulls"]\n'
                  'b = ["gh", "project", "item-list", "1"]\n')
        self.assertEqual(gh_argv_violations(source), [])

    def test_a_porcelain_instruction_is_caught(self):
        text = "Then run:\n\n```bash\ngh pr merge 42 --squash\n```\n"
        self.assertEqual([hit[2] for hit in porcelain_instructions(text)],
                         ["gh pr merge"])

    def test_a_paragraph_stating_the_rule_passes(self):
        text = "`gh pr create` runs on GraphQL, which a session refuses.\n"
        self.assertEqual(porcelain_instructions(text), [])


if __name__ == "__main__":
    unittest.main()
