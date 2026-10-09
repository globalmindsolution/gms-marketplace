"""ADR-0139 doc facts: tickets carry no design flag, and a tech design runs
when the user asks for one.

Pins the documentation side of the change — the ADR, its index row and the
status lines it adds to ADR-0008, 0101, 0128, 0133, 0135 and 0138 (whose
decisions stay as written); the CHANGELOG's breaking `### Changed` bullet and
its **Migration**; the INTERNALS facts (ticket fields, `context.design`, the
refine keys, the analysis front matter); the plugin README; the living
requirements; and the rule that no live document still describes
`needs_design` as something a ticket, a requirement or an analysis carries.
The code, schemas, skills and evals are pinned by their own tests.

Stdlib only.
"""

import os
import re
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ADR_DIR = os.path.join(REPO_ROOT, "docs", "architecture", "adr")
ADR_0139 = os.path.join(ADR_DIR, "0139-tickets-carry-no-design-flag.md")
AMENDED = {
    "0008": "0008-conditional-steps-as-ticket-data.md",
    "0101": "0101-gating-skills-that-are-not-workflow-steps.md",
    "0128": "0128-requirements-from-any-container.md",
    "0133": "0133-analysis-is-a-folder-by-bounded-context.md",
    "0135": "0135-create-tech-design.md",
    "0138": "0138-breakdown-ticket-and-typed-ticket-authors.md",
}
ADR_README = os.path.join(ADR_DIR, "README.md")
CHANGELOG = os.path.join(REPO_ROOT, "plugins", "acs", "CHANGELOG.md")
INTERNALS = os.path.join(REPO_ROOT, "plugins", "acs", "docs", "INTERNALS.md")
PLUGIN_README = os.path.join(REPO_ROOT, "plugins", "acs", "README.md")
REQ = os.path.join(REPO_ROOT, "docs", "requirements")
SKILLS_MD = os.path.join(REQ, "functional", "skills.md")
WORKFLOW_MD = os.path.join(REQ, "functional", "workflow.md")
STATE_MD = os.path.join(REQ, "functional", "workspace-and-state.md")
HOOKS_MD = os.path.join(REQ, "functional", "hooks.md")
REQ_README = os.path.join(REQ, "README.md")

LINK = "(0139-tickets-carry-no-design-flag.md)"

#: Live documents a reader follows today. Decision logs, ADRs, spikes and the
#: CHANGELOG are history and may describe the flag as it was.
LIVE_DOCS = (
    "plugins/acs/README.md",
    "plugins/acs/docs/INTERNALS.md",
    "plugins/acs/docs/AUTHORING.md",
    "docs/requirements/functional/skills.md",
    "docs/requirements/functional/workflow.md",
    "docs/requirements/functional/hooks.md",
    "docs/requirements/functional/workspace-and-state.md",
    "docs/requirements/non-functional/quality-gates.md",
    "docs/architecture/hld/data-model.md",
    "docs/architecture/lld/acs/api/cli.md",
    "docs/architecture/lld/acs/flows/hook-gated-skill-run.md",
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
        text = _read(ADR_0139)
        self.assertTrue(text.startswith("# 0139 — "), text[:80])
        self.assertIn("**Status**: Accepted · **Date**: 2026-10-06", text)

    def test_adr_names_what_it_amends(self):
        text = _read(ADR_0139)
        amends = text[text.index("**Amends**"):text.index("## Context")]
        for adr, name in AMENDED.items():
            self.assertIn("[%s](%s)" % (adr, name), amends, adr)

    def test_adr_context_cites_the_user_and_adr_0095(self):
        context = _norm(_read(ADR_0139).split("## Context", 1)[1].split("## Decision", 1)[0])
        self.assertIn("runs `/acs:create-tech-design` by hand", context)
        self.assertIn("left tickets with ADR-0095", context)

    def test_adr_records_the_decision(self):
        text = _norm(_read(ADR_0139))
        for fact in (
                "`new-ticket.py --needs-design` is removed: argparse rejects it (exit 2)",
                "drops `needs_design_recommendation`",
                "`requirements.REFINE_KEYS`", "**refuses** with a `GateError` naming ADR-0139",
                "`gate_create_tech_design` stays in `SUBJECT_GATES`",
                "`_refuse_recorded_no_design` is deleted",
                "`design_source(ctx, tdir, ticket, rdir)`", "`(exists, dir, source)`",
                "`context.design = {exists, dir, source}`",
                "`source: own`", "`source: parent`", "a legacy `design.md` still read",
                "no advisory, no warning", "`artifacts._FRONT_MATTER_ORDER`",
                "`delivery_path`"):
            self.assertIn(fact, text, fact)

    def test_adr_consequences_keep_old_state_loading(self):
        text = _norm(_read(ADR_0139).split("## Consequences", 1)[1])
        for fact in ("**Old state still loads.**", "`additionalProperties` stays `true`",
                     "`requirements-refined.json`", "`needs_design_recommendation`",
                     "**Breaking.**", "`new-ticket.py --needs-design` exits 2",
                     "(when you want a design)",
                     "`tests/acs/test_needs_design_epic_only.py` is deleted"):
            self.assertIn(fact, text, fact)

    def test_amended_adrs_carry_a_status_line_and_keep_their_decision(self):
        for adr, name in AMENDED.items():
            self.assertIn(LINK, _status_line(_read(os.path.join(ADR_DIR, name))), adr)
        # The decisions themselves are not edited: each still says what it decided.
        keep = {
            "0008": "`needs_design` (gates /create-design from both sides)",
            "0101": "precondition is a flag on the ticket (`needs_design`)",
            "0128": "`/acs:create-design`'s gate reads `needs_design` from the run's",
            "0133": "`ready_for_planning`, `api_surface`, `needs_design_recommendation`",
            "0135": "brake as before: `needs_design` from the refined requirements or the ticket",
            "0138": "`{\"type\": \"epic\", \"needs_design\": true}`",
        }
        for adr, phrase in keep.items():
            self.assertIn(phrase, _norm(_read(os.path.join(ADR_DIR, AMENDED[adr]))), adr)

    def test_index_row_and_amended_rows(self):
        row = _index_row("0139")
        self.assertIn(LINK, row)
        self.assertTrue(row.endswith("(amends 0008, 0101, 0128, 0133, 0135, 0138) | Accepted |"),
                        row[-80:])
        for fact in ("`--needs-design` is removed and exits 2", "`needs_design_recommendation`",
                     "`context.design = {exists, dir, source}`"):
            self.assertIn(fact, row, fact)
        for adr in AMENDED:
            self.assertIn(LINK, _index_row(adr).rsplit("|", 2)[-2], adr)
        rows = [l for l in _read(ADR_README).splitlines() if l.startswith("| [01")]
        at = next(i for i, l in enumerate(rows) if l.startswith("| [0139]("))
        self.assertTrue(rows[at - 1].startswith("| [0138]("), "the 0139 row follows the 0138 row")


class ChangelogTest(unittest.TestCase):

    def test_changed_bullet_is_breaking_with_a_migration(self):
        bullets = _bullets(_unreleased("### Changed"), "(ADR-0139)")
        self.assertEqual(len(bullets), 1, "one ### Changed bullet cites ADR-0139")
        bullet = bullets[0]
        self.assertTrue(bullet.startswith("- **⚠️ BREAKING:"), bullet[:60])
        self.assertIn("**Migration:**", bullet)
        migration = bullet.split("**Migration:**", 1)[1]
        for fact in ("`new-ticket.py --needs-design` was removed and exits 2",
                     "`acs.py requirements refine` refuses a `needs_design` key",
                     "Old tickets, index entries, refined requirements and analyses are fine",
                     "Run `/acs:create-tech-design <id>`"):
            self.assertIn(fact, migration, fact)
        self.assertIn("`context.design = {exists, dir, source}`", bullet)


class LiveDocsTest(unittest.TestCase):

    def test_internals_facts(self):
        text = _norm(_read(INTERNALS))
        for fact in (
                "**No design flag** (ADR-0139). A ticket carries no `needs_design`",
                "`new-ticket.py --needs-design` exits 2",
                "**The tech design is found, not required** (ADR-0139)",
                "`design: {exists, dir, source}`", "`gates.design_source(ctx, tdir, ticket, rdir)`",
                "`source: own`", "`source: parent`",
                "A `needs_design` key is refused with a GateError naming ADR-0139",
                "a `needs_design_recommendation` left by one published before ADR-0139, "
                "is ignored, never refused"):
            self.assertIn(fact, text, fact)
        self.assertIn("`{path, sources, acceptance_criteria, features, feature}`", text)
        self.assertIn("acceptance_criteria, features, feature, phase, feature_analysis, refined}`",
                      text)
        lines = _read(INTERNALS).splitlines()
        states = next(l for l in lines if l.startswith("| create-ticket |"))
        self.assertNotIn("needs_design", states)

    def test_plugin_readme(self):
        text = _read(PLUGIN_README)
        row = next(l for l in text.splitlines() if l.startswith("| `/acs:create-tech-design` |"))
        self.assertIn(LINK.strip("()"), row)
        self.assertIn("no design flag is read", row)
        create = next(l for l in text.splitlines() if l.startswith("| `/acs:create-ticket` |"))
        self.assertIn("a ticket carries no design flag", create)
        self.assertIn("(when you want a design)", create)

    def test_requirements(self):
        skills = _norm(_read(SKILLS_MD))
        section = skills[skills.index("## 2. `/create-tech-design`"):
                         skills.index("## 2a.") if "## 2a." in skills else None]
        for fact in ("Runs **when the user invokes it**", "`gate_create_tech_design`",
                     "`context.design = {exists, dir, source}`"):
            self.assertIn(fact, section, fact)
        self.assertIn("MUST NOT ask about, record or recommend a design", skills)
        self.assertIn("`{ticket | feature, ready_for_planning}`", skills)
        workflow = _norm(_read(WORKFLOW_MD))
        self.assertIn("`/create-tech-design` runs **when the user asks for it**", workflow)
        self.assertIn("when you want a design", workflow)
        hooks = next(l for l in _read(HOOKS_MD).splitlines()
                     if l.startswith("| `/create-tech-design` | requirements resolve"))
        self.assertIn("no design flag is read", hooks)
        state = _read(STATE_MD)
        self.assertFalse(any(l.startswith("| `needs_design` |") for l in state.splitlines()))
        self.assertIn("A ticket carries **no design flag**", state)
        log = next(l for l in _read(REQ_README).splitlines()
                   if l.startswith("| 2026-10-06 | **Tickets carry no design flag"))
        self.assertIn("ADR 0139", log)

    def test_no_live_doc_still_describes_the_flag_as_current(self):
        """`needs_design` may be named only as what was removed, is ignored or
        refused -- never as a field a ticket, requirement or analysis carries."""
        for rel in LIVE_DOCS:
            text = _norm(_read(os.path.join(REPO_ROOT, rel)))
            for m in re.finditer(r"needs[_-]design", text):
                window = text[max(0, m.start() - 200):m.end() + 200]
                self.assertTrue(
                    re.search(r"ADR[- ]0139|removed|ignored|refuse|no longer|left ", window),
                    "%s still describes %r as current: …%s…"
                    % (rel, m.group(0), text[max(0, m.start() - 80):m.end() + 80]))


if __name__ == "__main__":
    unittest.main()
