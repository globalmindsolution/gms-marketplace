"""ADR-0138 doc facts: /acs:breakdown-ticket, create-ticket's type authors and
reviewer, and the `bug` ticket type.

Pins the documentation side of the change — the ADR, its index row and the
status lines it adds to ADR-0069, 0075, 0109, 0118, 0120 and 0129 (whose
decisions stay as written); the CHANGELOG's `### Added` bullets and its
breaking `### Changed` bullet with a **Migration**; the INTERNALS role,
states and ticket-type facts; the plugin README's skill table; the living
requirements; and the rule that no live document still tells a reader to run
`/acs:create-ticket --fan-out` or `split`. The skill, agent, hook and schema
files are pinned by their own tests.

Stdlib only.
"""

import os
import re
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ADR_DIR = os.path.join(REPO_ROOT, "docs", "architecture", "adr")
ADR_0138 = os.path.join(ADR_DIR, "0138-breakdown-ticket-and-typed-ticket-authors.md")
AMENDED = {
    "0069": "0069-oversized-ticket-two-lever-split-control.md",
    "0075": "0075-planning-implementation-pipeline-split-epics-never-implemented.md",
    "0109": "0109-subagents-per-skill-logic-and-no-skill-manifest.md",
    "0118": "0118-discovery-design-development-phases.md",
    "0120": "0120-design-document-catalog-and-ticket-features.md",
    "0129": "0129-discovery-design-development-regroup.md",
}
ADR_README = os.path.join(ADR_DIR, "README.md")
CHANGELOG = os.path.join(REPO_ROOT, "plugins", "acs", "CHANGELOG.md")
INTERNALS = os.path.join(REPO_ROOT, "plugins", "acs", "docs", "INTERNALS.md")
AUTHORING = os.path.join(REPO_ROOT, "plugins", "acs", "docs", "AUTHORING.md")
PLUGIN_README = os.path.join(REPO_ROOT, "plugins", "acs", "README.md")
REQ = os.path.join(REPO_ROOT, "docs", "requirements", "functional")
SKILLS_MD = os.path.join(REQ, "skills.md")
WORKFLOW_MD = os.path.join(REQ, "workflow.md")
STATE_MD = os.path.join(REQ, "workspace-and-state.md")
HOOKS_MD = os.path.join(REQ, "hooks.md")
REFLECTION_MD = os.path.join(REQ, "reflection.md")
ROADMAP = os.path.join(REPO_ROOT, "docs", "product", "roadmap.md")

LINK = "(0138-breakdown-ticket-and-typed-ticket-authors.md)"
AUTHORS = ("create-ticket-epic-author", "create-ticket-story-author",
           "create-ticket-task-author", "create-ticket-bug-author")
BUG_FIELDS = ("severity", "reproduction", "expected", "actual", "environment")

#: Live documents a reader follows today. Decision logs, ADRs and the
#: CHANGELOG are history and may name the old modes.
LIVE_DOCS = (
    "plugins/acs/README.md",
    "plugins/acs/docs/INTERNALS.md",
    "plugins/acs/docs/AUTHORING.md",
    "docs/requirements/functional/skills.md",
    "docs/requirements/functional/workflow.md",
    "docs/requirements/functional/usage.md",
    "docs/requirements/functional/reflection.md",
    "docs/requirements/functional/workspace-and-state.md",
    "docs/architecture/lld/acs/flows/ship-pipeline.md",
    "docs/architecture/lld/acs/flows/state-ticket.md",
    "docs/architecture/lld/acs/flows/ticket-lifecycle.md",
)


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _norm(text):
    return re.sub(r"\s+", " ", text)


def _status_line(text):
    for line in text.splitlines():
        if line.startswith("**Status**"):
            return line
    return ""


def _index_row(adr):
    for line in _read(ADR_README).splitlines():
        if line.startswith("| [%s](" % adr):
            return line
    return ""


def _unreleased(heading):
    text = _read(CHANGELOG)
    start = text.index("## [Unreleased]")
    end = text.index("\n## [", start + 1)
    if not text[start + len("## [Unreleased]"):end].strip():
        # right after a cut [Unreleased] is empty and the notes sit in the newest dated section
        end = text.find("\n## [", end + 1)
        # the newest dated section (0.6.1) sits above the one with these notes (0.6.0)
        end = text.find("\n## [", end + 1) if end != -1 else end
        end = len(text) if end == -1 else end
    section = text[start:end]
    at = section.index(heading)
    nxt = section.find("\n### ", at + 1)
    return section[at:nxt if nxt != -1 else len(section)]


def _bullets(section, marker):
    return [_norm(b) for b in re.split(r"\n(?=- \*\*)", section) if marker in b]


class AdrTest(unittest.TestCase):

    def test_adr_is_accepted_and_dated(self):
        text = _read(ADR_0138)
        self.assertTrue(text.startswith("# 0138 — "), text[:80])
        # Accepted, possibly amended later (ADR-0139 amends its needs_design facts).
        self.assertRegex(text, r"\*\*Status\*\*: Accepted( — amended by [^\n]*)? · \*\*Date\*\*: 2026-10-05")

    def test_adr_names_what_it_amends(self):
        text = _read(ADR_0138)
        amends = text[text.index("**Amends**"):text.index("## Context")]
        for adr, name in AMENDED.items():
            self.assertIn("[%s](%s)" % (adr, name), amends, adr)

    def test_adr_records_the_decision(self):
        text = _norm(_read(ADR_0138))
        for fact in AUTHORS + (
                "`create-ticket-reviewer`", "`skills/create-ticket/references/authoring-rules.md`",
                "`steps/create-ticket/iter-<n>/draft.json`", "`acs.py write`",
                "**two iterations**", "`new-ticket.py --parent`", "**keeps its id**",
                "`TYPE_OPTIONS[\"bug\"] = \"Bug\"`", "`bug-default`", "`gate_breakdown_ticket`",
                "`--fan-out` and `split …` now **refuse**", "30 skills",
                "40 agent files, all reachable",
                "`models.create-ticket.{epic-author,story-author,task-author,bug-author,reviewer}`"):
            self.assertTrue(fact in text, fact)
        for field in BUG_FIELDS:
            self.assertIn("`%s`" % field, text, field)
        for case in ("`breakdown-ticket-epic-into-children`",
                     "`breakdown-ticket-split-oversized-story`", "`create-ticket-bug-report`"):
            self.assertIn(case, text, case)

    def test_amended_adrs_carry_a_status_line_and_keep_their_decision(self):
        for adr, name in AMENDED.items():
            self.assertIn(LINK, _status_line(_read(os.path.join(ADR_DIR, name))), adr)
        # The decisions themselves are not edited: each still says what it decided.
        self.assertIn("`/acs:create-ticket split <id>`",
                      _read(os.path.join(ADR_DIR, AMENDED["0069"])))
        self.assertIn("`create-ticket <epic-id> --fan-out`",
                      _read(os.path.join(ADR_DIR, AMENDED["0075"])))
        self.assertIn("| create-ticket, create-pr, merge-pr | none:",
                      _read(os.path.join(ADR_DIR, AMENDED["0109"])))
        self.assertIn("`breakdown-ticket` replacing `create-ticket --fan-out`",
                      _norm(_read(os.path.join(ADR_DIR, AMENDED["0118"]))))
        self.assertIn("(and `breakdown-ticket` when it ships)",
                      _read(os.path.join(ADR_DIR, AMENDED["0129"])))

    def test_index_row_and_amended_rows(self):
        row = _index_row("0138")
        self.assertIn(LINK, row)
        self.assertRegex(row, r"\(amends 0069, 0075, 0109, 0118, 0120, 0129\) \| Accepted"
                              r"( — amended by [^|]*)? \|$")
        self.assertIn("30 skills, 40 agent files", row)
        for adr in AMENDED:
            self.assertIn(LINK, _index_row(adr).rsplit("|", 2)[-2], adr)


class ChangelogTest(unittest.TestCase):

    def test_added_bullets(self):
        added = _unreleased("### Added")
        skill = _bullets(added, "**`/acs:breakdown-ticket`** (ADR-0138)")
        self.assertEqual(len(skill), 1, "one ### Added bullet for /acs:breakdown-ticket")
        for fact in ("one grouped confirmation", "`new-ticket.py --parent`",
                     "keeps its id", "30 skills"):
            self.assertIn(fact, skill[0], fact)
        bug = _bullets(added, "**`bug` is a ticket type** (ADR-0138)")
        self.assertEqual(len(bug), 1, "one ### Added bullet for the bug type")
        for field in BUG_FIELDS:
            self.assertIn("`%s`" % field, bug[0], field)
        self.assertIn("`templates/bug-default.md`", bug[0])

    def test_changed_bullet_is_breaking_with_a_migration(self):
        changed = _unreleased("### Changed")
        bullets = _bullets(changed, "(ADR-0138)")
        self.assertEqual(len(bullets), 1, "one ### Changed bullet cites ADR-0138")
        bullet = bullets[0]
        self.assertTrue(bullet.startswith("- **⚠️ BREAKING:"), bullet[:60])
        self.assertIn("**Migration:**", bullet)
        for fact in AUTHORS + ("`create-ticket-reviewer`", "40 agent files",
                               "`/acs:breakdown-ticket <epic-id>`",
                               "`/acs:create-ticket <epic-id> --fan-out`",
                               "`/acs:create-ticket split <id>`"):
            self.assertIn(fact, bullet, fact)


class LiveDocsTest(unittest.TestCase):

    def test_internals_roles_states_and_types(self):
        text = _read(INTERNALS)
        lines = text.splitlines()
        row = next(l for l in lines if l.startswith("| `create-ticket` |"))
        for role in ("`epic-author`", "`story-author`", "`task-author`", "`bug-author`",
                     "`reviewer` (judge"):
            self.assertIn(role, row, role)
        self.assertTrue(any(l.startswith("| `breakdown-ticket`, `create-pr`, `merge-pr` | none")
                            for l in lines))
        states = next(l for l in lines if l.startswith("| breakdown-ticket |"))
        for key in ("`ticket_id`", "`converted_from`", "`minted: [ids]`", "`design_status`"):
            self.assertIn(key, states, key)
        norm = _norm(text)
        self.assertIn("`TICKET_TYPES` is `epic`, `story`, `task` and `bug`", norm)
        self.assertIn("**A child inherits its parent's `features`.**", norm)
        self.assertIn("`/acs:breakdown-ticket <id>` next step", norm)
        self.assertIn("inline from `references/` (`breakdown-ticket`, `create-pr`, `merge-pr`)",
                      _norm(_read(AUTHORING)))

    def test_plugin_readme_rows(self):
        lines = _read(PLUGIN_README).splitlines()
        create = next(l for l in lines if l.startswith("| `/acs:create-ticket` |"))
        self.assertIn("`bug`", create)
        self.assertIn("`/acs:breakdown-ticket`", create)
        breakdown = next(l for l in lines if l.startswith("| `/acs:breakdown-ticket` |"))
        self.assertIn(LINK.strip("()"), breakdown)
        self.assertIn("keeps its id", breakdown)
        self.assertIn("## The 30 skills", _read(PLUGIN_README))

    def test_requirements_sections(self):
        skills = _norm(_read(SKILLS_MD))
        section = skills[skills.index("## 1a. `/breakdown-ticket` (utility)"):
                         skills.index("## 2. `/create-tech-design`")]
        for fact in ("`gate_breakdown_ticket`", "ONE grouped confirmation",
                     "`new-ticket.py --parent <id>`", "**epic that keeps its id**",
                     "never block", "`converted_from`", "`minted`"):
            self.assertTrue(fact in section, fact)
        create = skills[skills.index("## 1. `/create-ticket`"):
                        skills.index("## 1a. `/breakdown-ticket`")]
        for fact in AUTHORS + ("`create-ticket-reviewer`",
                               "`skills/create-ticket/references/authoring-rules.md`",
                               "MUST refuse, naming `/acs:breakdown-ticket`"):
            self.assertTrue(fact in create, fact)
        self.assertIn("reproduce first", skills)
        self.assertIn("failing **reproduction test**", skills)
        workflow = _norm(_read(WORKFLOW_MD))
        self.assertIn("Children are minted by **`/acs:breakdown-ticket`**", workflow)
        state = _read(STATE_MD)
        for field in BUG_FIELDS:
            self.assertTrue(any(l.startswith("| `%s` |" % field) for l in state.splitlines()),
                            field)
        self.assertTrue(any(l.startswith("| `/breakdown-ticket` | `pre-breakdown-ticket.py`")
                            for l in _read(HOOKS_MD).splitlines()))
        self.assertTrue(any(l.startswith("| create-ticket | — | ONE of `create-ticket-epic-author`")
                            for l in _read(REFLECTION_MD).splitlines()))

    def test_roadmap_marks_p8_delivered(self):
        self.assertIn("(P8 delivered, [ADR-0138]", _read(ROADMAP))

    def test_no_live_doc_still_directs_to_the_old_modes(self):
        """`--fan-out` and `split` may be named only as what refuses or what
        breakdown-ticket replaced -- never as the command to run."""
        for rel in LIVE_DOCS:
            text = _norm(_read(os.path.join(REPO_ROOT, rel)))
            for m in re.finditer(r"create-ticket[^ ]* (<[a-z-]+> --fan-out|split <id>)", text):
                window = text[max(0, m.start() - 160):m.end() + 160]
                self.assertTrue(
                    re.search(r"refuse|replaced|absorbs|breakdown-ticket", window),
                    "%s still directs to %r" % (rel, m.group(0)))


if __name__ == "__main__":
    unittest.main()
