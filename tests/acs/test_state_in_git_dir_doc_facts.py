"""ADR-0136 doc facts: acs state lives in the git common directory, and state
files are written through `acs.py write`.

Pins the documentation side of the move — the ADR, its index row and the status
lines it adds to ADR-0086, ADR-0102 and ADR-0105; the CHANGELOG entry and its
Migration note; the AUTHORING rule and tool table; the INTERNALS section; the
CLAUDE.md "State and settings" paragraph; the living requirements — and guards
that a live document names the old in-checkout root only as the legacy path a
migration moves from. History (ADRs, dated rows, released CHANGELOG sections)
keeps the old path and is not scanned.

Stdlib only.
"""

import os
import re
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ADR_DIR = os.path.join(REPO_ROOT, "docs", "architecture", "adr")
ADR_0136 = os.path.join(ADR_DIR, "0136-state-in-the-git-common-dir.md")
AMENDED = {
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
CONTRACTS = os.path.join(REPO_ROOT, "docs", "architecture", "lld", "contracts.md")

LINK = "(0136-state-in-the-git-common-dir.md)"
NEW_ROOT = "<git-common-dir>/acs/state-machine"
WRITE_FORM = ('python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" write <path> '
              "<<'ACS_EOF'")

#: Live documents: they describe acs as it is, so they may name the old
#: in-checkout root only as the legacy location the migration moves from.
LIVE_DOCS = (
    "README.md",
    "CLAUDE.md",
    "plugins/acs/README.md",
    "plugins/acs/docs/INTERNALS.md",
    "plugins/acs/docs/AUTHORING.md",
    "docs/requirements/functional/configuration.md",
    "docs/requirements/functional/hooks.md",
    "docs/requirements/functional/skills.md",
    "docs/requirements/functional/usage.md",
    "docs/requirements/functional/workflow.md",
    "docs/requirements/functional/workspace-and-state.md",
    "docs/requirements/non-functional/portability.md",
    "docs/operations/observability.md",
    "docs/architecture/hld/overview.md",
    "docs/architecture/hld/deployment.md",
    "docs/architecture/hld/c4-context.md",
    "docs/architecture/hld/c4-container.md",
    "docs/architecture/hld/c4-component.md",
    "docs/architecture/lld/contracts.md",
    "docs/architecture/lld/flows/state-root-resolution.md",
    "docs/architecture/lld/flows/setup-state-root-setup.md",
)

#: The old root as a location (not the ignore entry `.acs/state-machine/`
#: setup still writes, and not the `.MOVED` note).
OLD_ROOT = re.compile(r"\.acs/state-machine(?!\.MOVED|/`|/$| again|/ to | for )")
LEGACY_WORDS = re.compile(r"ADR-0136|\blegacy\b|\bold\b|MOVED|\bmove[sd]?\b|migrat|\byet\b")


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _norm(text):
    return re.sub(r"\s+", " ", text)


def _status(path):
    return [l for l in _read(path).splitlines() if l.startswith("**Status**")][0]


class Adr0136RecordTest(unittest.TestCase):

    def test_adr_is_accepted_dated_and_amends_the_state_root_adrs(self):
        body = _read(ADR_0136)
        self.assertTrue(body.startswith("# 0136 — "))
        self.assertIn("**Status**: Accepted · **Date**: 2026-10-05", body)
        amends = body[body.index("**Amends**"):body.index("## Context")]
        for path in AMENDED.values():
            self.assertIn("(%s)" % os.path.basename(path), amends)

    def test_adr_records_the_decisions(self):
        body = _norm(_read(ADR_0136))
        for fact in ("`%s/`" % NEW_ROOT, "`<main-checkout>/.acs/state-machine`",
                     "`repo.default_state_root()`", "`<main-checkout>/.acs/state-machine.MOVED`",
                     "`acs.py doctor`", "`acs.py write <path> [--append] [--run R]`",
                     "exit 2", "`.acs/settings.json`", "`.acs/settings.local.json`",
                     "`.acs/state-machine/`", "`Write`", "worktree", "sandbox"):
            self.assertIn(fact, body)
        self.assertIn(WRITE_FORM, _read(ADR_0136))

    def test_index_row_and_amended_status_lines(self):
        index = _read(ADR_README)
        row = [l for l in index.splitlines() if l.startswith("| [0136]%s" % LINK)]
        self.assertEqual(len(row), 1, "ADR index must carry exactly one 0136 row")
        self.assertTrue(row[0].rstrip().endswith("| Accepted |"))
        self.assertIn("(amends 0086, 0102, 0105)", row[0])
        for num, path in AMENDED.items():
            line = [l for l in index.splitlines() if l.startswith("| [%s]" % num)][0]
            self.assertIn("[0136]%s" % LINK, line.rsplit("|", 2)[1], num)
            self.assertIn("[0136]%s" % LINK, _status(path), num)


class ChangelogEntryTest(unittest.TestCase):

    def _bullet(self):
        text = _read(CHANGELOG)
        start = text.index("## [Unreleased]")
        unreleased = text[start:text.index("\n## [", start + 1)]
        changed = unreleased[unreleased.index("### Changed"):unreleased.index("### Removed")]
        head = "- **acs state lives in the git directory, and state files are written through"
        self.assertIn(head, changed)
        bullet = changed[changed.index(head):]
        nxt = bullet.find("\n- ", 1)
        return _norm(bullet if nxt < 0 else bullet[:nxt])

    def test_changed_bullet_is_not_breaking_and_says_migration_is_automatic(self):
        bullet = self._bullet()
        self.assertNotIn("BREAKING", bullet)
        self.assertIn("(ADR-0136)", bullet)
        self.assertIn("`acs.py write <path> [--append] [--run R]`", bullet)
        migration = bullet[bullet.index("**Migration:**"):]
        for fact in ("none to run", "`.acs/state-machine.MOVED`", "`acs.py doctor`",
                     "idempotent", "`.acs/settings.json`"):
            self.assertIn(fact, migration)


class AuthoringRuleTest(unittest.TestCase):

    def test_the_write_rule_and_its_form(self):
        body = _read(AUTHORING)
        self.assertIn("- **State files are written through `acs.py write`, never the Write tool", body)
        self.assertIn("<<'ACS_EOF'", body)

    def test_tool_table_drops_write_from_survey_and_judge_roles(self):
        body = _read(AUTHORING)
        self.assertIn("| Survey and judge roles | `tools: Read, Glob, Grep, Bash` |", body)
        self.assertNotIn("`tools: Read, Glob, Grep, Bash, Write`", body)
        self.assertNotIn("Read, Glob, Grep, Bash, Write", body)


class InternalsSectionTest(unittest.TestCase):

    def test_section_names_root_migration_and_write(self):
        body = _read(INTERNALS)
        start = body.index("### Where the workspace is, and how state is written (ADR-0136)")
        section = _norm(body[start:body.index("\n### ", start + 1)])
        for fact in ("`%s`" % NEW_ROOT, "`acs_lib/state_root.py`", "`O_EXCL`",
                     "`rewrite_stored_paths`", "`state_root: {path, legacy, legacy_leftover, message}`",
                     "`acs_write_commands.py`", "`--run R`", "`run.json`",
                     "`steps/<skill>/state.json`", "`os.replace`"):
            self.assertIn(fact, section)
        self.assertIn("never the `Write` tool", _norm(body))


class ClaudeMdTest(unittest.TestCase):

    def test_state_and_settings_paragraph(self):
        body = _read(CLAUDE_MD)
        start = body.index("### State and settings")
        section = _norm(body[start:body.index("\n## ", start)])
        for fact in ("`%s/<repo-id>/`" % NEW_ROOT, "ADR-0136", "`acs.py write <path>`",
                     "**never the Write tool**"):
            self.assertIn(fact, section)


class LivingRequirementsTest(unittest.TestCase):

    def test_workspace_folder_requirements(self):
        body = _read(WORKSPACE_AND_STATE)
        start = body.index("## Workspace folder")
        section = _norm(body[start:body.index("\n## ", start + 1)])
        for fact in ("`%s`" % NEW_ROOT, "`acs.py write <path> [--append] [--run R]`",
                     "MUST be refused with exit 2", "`.acs/state-machine.MOVED`",
                     "`acs.py doctor`", "keep resolving"):
            self.assertIn(fact, section)

    def test_contracts_list_the_write_verb_and_doctor(self):
        body = _read(CONTRACTS)
        self.assertIn("| `acs.py write <path> [--append] [--run R]`", body)
        self.assertIn("| `acs.py doctor` |", body)


class LiveDocsNameTheNewRootTest(unittest.TestCase):
    """A live document may name `.acs/state-machine` as a location only as the
    legacy root a migration moves from: within three lines of a word saying so."""

    def test_old_root_only_as_legacy(self):
        stray = []
        for rel in LIVE_DOCS:
            lines = _read(os.path.join(REPO_ROOT, rel)).splitlines()
            for i, line in enumerate(lines):
                if not OLD_ROOT.search(line):
                    continue
                window = "\n".join(lines[max(0, i - 3):i + 4])
                if not LEGACY_WORDS.search(window):
                    stray.append("%s:%d: %s" % (rel, i + 1, line.strip()[:120]))
        self.assertEqual(stray, [], "\n  " + "\n  ".join(stray))


if __name__ == "__main__":
    unittest.main()
