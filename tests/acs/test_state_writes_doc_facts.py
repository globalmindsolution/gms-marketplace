"""ADR-0136 doc facts: state files are written through `acs.py write`, never the
Write tool, and the workspace stays at `<main-checkout>/.acs/state-machine`.

Pins the documentation side of the decision — the ADR, its index row; the
CHANGELOG entry; the AUTHORING rule and tool table; the INTERNALS section and
the setup paragraph's sandbox write rule; the CLAUDE.md "State and settings"
paragraph; the living requirements — and guards that no live document still
places the workspace in the git directory or describes a migration to it (an
earlier draft of ADR-0136 did, and never shipped).

Stdlib only.
"""

import os
import re
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ADR_DIR = os.path.join(REPO_ROOT, "docs", "architecture", "adr")
ADR_NAME = "0136-state-is-written-through-acs-write.md"
ADR_0136 = os.path.join(ADR_DIR, ADR_NAME)
NOT_AMENDED = {
    "0086": os.path.join(ADR_DIR, "0086-in-repo-anchored-state-machine.md"),
    "0102": os.path.join(ADR_DIR, "0102-documents-are-found-not-configured.md"),
    "0105": os.path.join(ADR_DIR, "0105-acs-runs-without-setup.md"),
}
ADR_README = os.path.join(ADR_DIR, "README.md")
CHANGELOG = os.path.join(REPO_ROOT, "plugins", "acs", "CHANGELOG.md")
AUTHORING = os.path.join(REPO_ROOT, "plugins", "acs", "docs", "AUTHORING.md")
INTERNALS = os.path.join(REPO_ROOT, "plugins", "acs", "docs", "INTERNALS.md")
CLAUDE_MD = os.path.join(REPO_ROOT, "CLAUDE.md")
WORKSPACE_AND_STATE = os.path.join(REPO_ROOT, "docs", "requirements", "functional",
                                   "workspace-and-state.md")
SKILLS_REQ = os.path.join(REPO_ROOT, "docs", "requirements", "functional", "skills.md")
CONTRACTS = os.path.join(REPO_ROOT, "docs", "architecture", "lld", "acs", "api", "cli.md")

LINK = "(%s)" % ADR_NAME
ROOT = "<main-checkout>/.acs/state-machine"
SANDBOX_KEY = "sandbox.filesystem.allowWrite"
WRITE_FORM = ('python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" write <path> '
              "<<'ACS_EOF'")

#: Where the documentation lives: every Markdown file under these, plus the
#: top-level files, is scanned for the withdrawn git-dir placement.
DOC_TREES = ("docs", os.path.join("plugins", "acs", "docs"))
DOC_FILES = ("README.md", "CLAUDE.md", os.path.join("plugins", "acs", "README.md"),
             os.path.join("plugins", "acs", "CHANGELOG.md"))

#: The withdrawn draft: the workspace under the git directory, its migration
#: note and doctor field, and the ADR's old filename.
WITHDRAWN = re.compile(r"\.git[/]acs\b|<git-common-dir>/acs/|state-machine\.MOVED|"
                       r"legacy_leftover|0136-state-in-the-git-common-dir")


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _norm(text):
    return re.sub(r"\s+", " ", text)


def _status(path):
    return [l for l in _read(path).splitlines() if l.startswith("**Status**")][0]


def _doc_paths():
    for rel in DOC_FILES:
        yield os.path.join(REPO_ROOT, rel)
    for tree in DOC_TREES:
        for base, _dirs, files in os.walk(os.path.join(REPO_ROOT, tree)):
            for name in files:
                if name.endswith(".md"):
                    yield os.path.join(base, name)


class Adr0136RecordTest(unittest.TestCase):

    def test_adr_is_accepted_dated_and_amends_nothing(self):
        body = _read(ADR_0136)
        self.assertTrue(body.startswith("# 0136 — "))
        self.assertIn("**Status**: Accepted · **Date**: 2026-10-06", body)
        self.assertNotIn("**Amends**", body)
        self.assertFalse(os.path.exists(os.path.join(ADR_DIR, "0136-state-in-the-git-common-dir.md")))

    def test_adr_records_the_decisions(self):
        body = _norm(_read(ADR_0136))
        for fact in ("`%s/<repo-id>/`" % ROOT, "`repo.default_state_root()`",
                     "`acs.py write <path> [--append] [--run R]`", "exit 2", "`os.replace`",
                     "`run.json`", "`steps/<skill>/state.json`", "`Write`", "`Read, Glob, Grep, Bash`",
                     "worktree", "Bash sandbox", "`sandbox.filesystem.allowWrite`",
                     "`.claude/settings.local.json`", "`.claude/settings.json`",
                     "absolute", "Nothing to migrate", "`.acs/state-machine/`",
                     "`run_id`", "`run_dir`"):
            self.assertIn(fact, body)
        self.assertIn(WRITE_FORM, _read(ADR_0136))
        self.assertIn('{"sandbox": {"filesystem": {"allowWrite": ["<absolute main checkout>/.acs/state-machine"]}}}',
                      body)

    def test_index_row(self):
        index = _read(ADR_README)
        row = [l for l in index.splitlines() if l.startswith("| [0136]%s" % LINK)]
        self.assertEqual(len(row), 1, "ADR index must carry exactly one 0136 row")
        self.assertTrue(row[0].rstrip().endswith("| Accepted |"))
        for fact in ("`acs.py write <path> [--append] [--run R]`", "`<main-checkout>/.acs/state-machine`",
                     "`sandbox.filesystem.allowWrite`", "`.claude/settings.local.json`"):
            self.assertIn(fact, row[0])

    def test_the_state_root_adrs_are_not_amended(self):
        index = _read(ADR_README)
        for num, path in NOT_AMENDED.items():
            line = [l for l in index.splitlines() if l.startswith("| [%s]" % num)][0]
            self.assertNotIn("0136", line.rsplit("|", 2)[1], num)
            self.assertNotIn("0136", _status(path), num)


class ChangelogEntryTest(unittest.TestCase):

    def _bullet(self):
        text = _read(CHANGELOG)
        start = text.index("## [Unreleased]")
        end = text.index("\n## [", start + 1)
        if not text[start + len("## [Unreleased]"):end].strip():
            # right after a cut [Unreleased] is empty and the notes sit in the newest dated section
            end = text.find("\n## [", end + 1)
            # the newest dated section (0.6.1) sits above the one with these notes (0.6.0)
            end = text.find("\n## [", end + 1) if end != -1 else end
            end = len(text) if end == -1 else end
        unreleased = text[start:end]
        changed = unreleased[unreleased.index("### Changed"):unreleased.index("### Removed")]
        head = "- **State files are written through `acs.py write`, never the Write tool**"
        self.assertIn(head, changed)
        bullet = changed[changed.index(head):]
        nxt = bullet.find("\n- ", 1)
        return _norm(bullet if nxt < 0 else bullet[:nxt])

    def test_changed_bullet(self):
        bullet = self._bullet()
        self.assertNotIn("BREAKING", bullet)
        for fact in ("(ADR-0136)", "`acs.py write <path> [--append] [--run R]`",
                     "`<main-checkout>/.acs/state-machine`", "`sandbox.filesystem.allowWrite`",
                     "`.claude/settings.local.json`", "`sandbox_rule`",
                     "**Migration:** none"):
            self.assertIn(fact, bullet)


class AuthoringRuleTest(unittest.TestCase):

    def test_the_write_rule_and_its_form(self):
        body = _read(AUTHORING)
        self.assertIn("- **State files are written through `acs.py write`, never the Write tool", body)
        self.assertIn("<<'ACS_EOF'", body)
        self.assertIn("The workspace is `%s`" % ROOT, _norm(body))

    def test_tool_table_drops_write_from_survey_and_judge_roles(self):
        body = _read(AUTHORING)
        self.assertIn("| Survey and judge roles | `tools: Read, Glob, Grep, Bash` |", body)
        self.assertNotIn("Read, Glob, Grep, Bash, Write", body)


class InternalsTest(unittest.TestCase):

    def test_write_section(self):
        body = _read(INTERNALS)
        start = body.index("### How state is written: `acs.py write` (ADR-0136)")
        section = _norm(body[start:body.index("\n### ", start + 1)])
        for fact in ("`%s`" % ROOT, "**The root does not move.**", "`acs_write_commands.py`",
                     "`--run R`", "`run.json`", "`steps/<skill>/state.json`", "`os.replace`",
                     "`sandbox.filesystem.allowWrite`", "**absolute**"):
            self.assertIn(fact, section)
        self.assertIn("never the `Write` tool", _norm(body))

    def test_setup_offers_the_sandbox_rule(self):
        body = _read(INTERNALS)
        start = body.index("## Bootstrap: `/acs:setup` is a conversation over a wizard")
        section = _norm(body[start:body.index("\n## ", start + 1)])
        for fact in ('`{"sandbox": {"filesystem": {"allowWrite": ["<abs main checkout>/.acs/state-machine"]}}}`',
                     "`.claude/settings.local.json`", "never the team file", "`sandbox_rule`",
                     "(ADR-0136)"):
            self.assertIn(fact, section)


class ClaudeMdTest(unittest.TestCase):

    def test_state_and_settings_paragraph(self):
        body = _read(CLAUDE_MD)
        start = body.index("### State and settings")
        section = _norm(body[start:body.index("\n## ", start)])
        for fact in ("`.acs/state-machine/<repo-id>/`", "**main checkout's**", "ADR-0136",
                     "`acs.py write <path>`", "**never the Write tool**", "`allowWrite`"):
            self.assertIn(fact, section)


class LivingRequirementsTest(unittest.TestCase):

    def test_workspace_folder_requirements(self):
        body = _read(WORKSPACE_AND_STATE)
        start = body.index("## Workspace folder")
        section = _norm(body[start:body.index("\n## ", start + 1)])
        for fact in ("`%s`" % ROOT, "`acs.py write <path> [--append] [--run R]`",
                     "MUST be refused with exit 2", "`sandbox.filesystem.allowWrite`",
                     "`.claude/settings.local.json`", "nothing to migrate"):
            self.assertIn(fact, section)

    def test_setup_requirement_offers_the_sandbox_rule(self):
        body = _read(SKILLS_REQ)
        start = body.index("## `/setup` (optional)")
        section = _norm(body[start:body.index("\n## ", start + 1)])
        for fact in ("MUST also offer the Bash sandbox write rule",
                     '`{"sandbox": {"filesystem": {"allowWrite": ["<absolute main checkout>/.acs/state-machine"]}}}`',
                     "main checkout's `.claude/settings.local.json`", "never the committed `.claude/settings.json`"):
            self.assertIn(fact, section)

    def test_contracts_list_the_write_verb_and_doctor(self):
        body = _read(CONTRACTS)
        self.assertIn("| `acs.py write <path> [--append] [--run R]`", body)
        doctor = [l for l in body.splitlines() if l.startswith("| `acs.py doctor` |")]
        self.assertEqual(len(doctor), 1)
        self.assertIn("`state_root` is `{path, error}`", doctor[0])


class NoWithdrawnPlacementTest(unittest.TestCase):
    """No document places the workspace in the git directory, describes the
    migration to it, or links the ADR's withdrawn filename."""

    def test_docs_do_not_name_the_git_dir_workspace(self):
        stray = []
        for path in _doc_paths():
            for i, line in enumerate(_read(path).splitlines(), 1):
                if WITHDRAWN.search(line):
                    stray.append("%s:%d: %s" % (os.path.relpath(path, REPO_ROOT), i, line.strip()[:120]))
        self.assertEqual(stray, [], "\n  " + "\n  ".join(stray))


if __name__ == "__main__":
    unittest.main()
