"""ADR-0140 doc facts: tickets link their documents.

Pins the documentation side of the change — the ADR, its index row and the
status lines it adds to ADR-0088 and ADR-0138 (whose decisions stay as
written); the CHANGELOG's `### Added` bullets; the INTERNALS facts (the ticket's
`references`, the CLI rows, `context.references` and `requirements.md`'s
`## References`, the forge table's non-critical `tracker refresh`); the CLI
LLD; the plugin README; the HLD data model; and the living requirements. The
code, schemas, templates, skills and evals are pinned by their own tests.

Stdlib only.
"""

import os
import re
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ADR_DIR = os.path.join(REPO_ROOT, "docs", "architecture", "adr")
ADR_0140 = os.path.join(ADR_DIR, "0140-tickets-link-their-documents.md")
AMENDED = {
    "0088": "0088-gh-only-github-transport-and-criticality-classification.md",
    "0138": "0138-breakdown-ticket-and-typed-ticket-authors.md",
}
ADR_README = os.path.join(ADR_DIR, "README.md")
CHANGELOG = os.path.join(REPO_ROOT, "plugins", "acs", "CHANGELOG.md")
INTERNALS = os.path.join(REPO_ROOT, "plugins", "acs", "docs", "INTERNALS.md")
PLUGIN_README = os.path.join(REPO_ROOT, "plugins", "acs", "README.md")
CLI_MD = os.path.join(REPO_ROOT, "docs", "architecture", "lld", "acs", "api", "cli.md")
DATA_MODEL = os.path.join(REPO_ROOT, "docs", "architecture", "hld", "data-model.md")
REQ = os.path.join(REPO_ROOT, "docs", "requirements")
SKILLS_MD = os.path.join(REQ, "functional", "skills.md")
WORKFLOW_MD = os.path.join(REQ, "functional", "workflow.md")
STATE_MD = os.path.join(REQ, "functional", "workspace-and-state.md")
REQ_README = os.path.join(REQ, "README.md")

LINK = "(0140-tickets-link-their-documents.md)"


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


def _section(text, start, end=None):
    at = text.index(start)
    stop = text.index(end, at + len(start)) if end else len(text)
    return text[at:stop]


def _unreleased(heading):
    text = _read(CHANGELOG)
    start = text.index("## [Unreleased]")
    end = text.index("\n## [", start + 1)
    section = text[start:end]
    at = section.index(heading)
    nxt = section.find("\n### ", at + 1)
    return section[at:nxt if nxt != -1 else len(section)]


def _bullets(section, marker):
    return [_norm(b) for b in re.split(r"\n(?=- \*\*)", section) if marker in b]


class AdrTest(unittest.TestCase):

    def test_adr_is_accepted_and_dated(self):
        text = _read(ADR_0140)
        self.assertTrue(text.startswith("# 0140 — Tickets link their documents"), text[:80])
        self.assertIn("**Status**: Accepted · **Date**: 2026-10-06", text)

    def test_adr_names_what_it_amends(self):
        text = _read(ADR_0140)
        amends = text[text.index("**Amends**"):text.index("## Context")]
        for adr, name in AMENDED.items():
            self.assertIn("[%s](%s)" % (adr, name), amends, adr)

    def test_adr_context(self):
        context = _norm(_section(_read(ADR_0140), "## Context", "## Decision"))
        self.assertIn("A ticket alone lacks the design context", context)
        self.assertIn("A local path is not clickable in a tracker", context)

    def test_adr_records_the_decision(self):
        text = _norm(_section(_read(ADR_0140), "## Decision", "## Consequences"))
        for fact in (
                "found from the standard layout, never configured or chosen",
                "`acs_lib/doc_links.py`", "**everything for the feature, with no selection step**",
                "`{kind, path, title, status, version, published, url}`",
                "`<base>/blob/<default>/<path>`", "**pending: not on `<default>` yet**",
                "**Every ticket has a `## References` section.**",
                "`<!-- acs:references -->`", "`<!-- /acs:references -->`",
                "`templates/{epic,story,task,bug}-default.md`",
                "an optional `references` array",
                "`acs.py tracker refresh (--ticket ID | --pending) [--dry-run]`",
                "the refresh is **non-critical** (ADR-0088)",
                "`record-external.py --url`", "`context.references`",
                "`requirements.materialise`", "so the two cannot drift",
                "never searches the repo for them",
                "`acs.py ticket references (--ticket ID | --features a,b [--parent ID]) [--fetch] [--write] [--render]`",
                "`acs.py tracker refresh --pending` after a merge",
                "writes each child's `tracker-body.md` before the sync",
                "A ticket with no `features` falls back to an id glob"):
            self.assertIn(fact, text, fact)
        for kind in ("`prd`", "`analysis`", "`hld`", "`lld`", "`design`", "`development`"):
            self.assertIn(kind, text, kind)

    def test_adr_consequences(self):
        text = _norm(_read(ADR_0140).split("## Consequences", 1)[1])
        for fact in ("**No link 404s.**", "**Pending entries wait for a merge.**",
                     "`/acs:merge-pr`'s `tracker refresh --pending` turns it into a link",
                     "**Old tickets work.**", "**No selection.**"):
            self.assertIn(fact, text, fact)

    def test_amended_adrs_carry_a_status_line_and_keep_their_decision(self):
        for adr, name in AMENDED.items():
            self.assertIn(LINK, _status_line(_read(os.path.join(ADR_DIR, name))), adr)
        keep = {
            "0088": "**Critical per ticket, soft per batch** — `create-ticket/SKILL.md`'s Step 5 "
                    "`gh issue create` tracker-sync call",
            "0138": "syncs them through create-ticket's existing tracker-sync reference",
        }
        for adr, phrase in keep.items():
            self.assertIn(phrase, _norm(_read(os.path.join(ADR_DIR, AMENDED[adr]))), adr)

    def test_index_row_and_amended_rows(self):
        row = _index_row("0140")
        self.assertIn(LINK, row)
        self.assertTrue(row.endswith("(amends 0088, 0138) | Accepted |"), row[-60:])
        for fact in ("`acs_lib/doc_links.py`", "with no selection step",
                     "`https://<host>/<owner>/<repo>/blob/<default>/<path>`",
                     "`acs.py tracker refresh (--ticket ID | --pending)`", "(non-critical)",
                     "`record-external.py --url`", "`context.references`"):
            self.assertIn(fact, row, fact)
        for adr in AMENDED:
            self.assertIn(LINK, _index_row(adr).rsplit("|", 2)[-2], adr)
        rows = [l for l in _read(ADR_README).splitlines() if l.startswith("| [01")]
        at = next(i for i, l in enumerate(rows) if l.startswith("| [0140]("))
        self.assertTrue(rows[at - 1].startswith("| [0139]("), "the 0140 row follows the 0139 row")


class ChangelogTest(unittest.TestCase):

    def test_added_bullets(self):
        added = _unreleased("### Added")
        bullets = _bullets(added, "(ADR-0140)")
        self.assertEqual(len(bullets), 4, bullets)
        main = next(b for b in bullets if b.startswith("- **Tickets link their documents**"))
        for fact in ("`## References`", "no selection step", "not on `origin/<default>` yet",
                     "`context.references`", "`tracker-body.md`", "**Migration:** none."):
            self.assertIn(fact, main, fact)
        self.assertTrue(any(b.startswith("- **`acs.py ticket references`**") for b in bullets))
        self.assertTrue(any(b.startswith("- **`acs.py tracker refresh") and "non-critical" in b
                            for b in bullets))
        self.assertTrue(any(b.startswith("- **`record-external.py --url`**") for b in bullets))
        self.assertNotIn("(ADR-0140)", _unreleased("### Changed"))


class LiveDocsTest(unittest.TestCase):

    def test_internals_ticket_and_context_facts(self):
        text = _norm(_read(INTERNALS))
        for fact in (
                "**References** (ADR-0140). A ticket may carry `references`",
                "placed after `features` in `_FRONT_MATTER_ORDER`",
                "`{kind, path, title, status, version, published, url}`",
                "derived by `acs_lib/doc_links.py` from the STANDARD LAYOUT — never chosen",
                "**The run's references are found, not searched for** (ADR-0140)",
                "`doc_links.references_for_ticket(ctx, ticket)`",
                "`doc_links.references_for_features(ctx, features)`",
                "`requirements.md`'s `## References` section",
                "design source, references, post_hook path",
                "`_No documents for this ticket's features yet._`"):
            self.assertIn(fact, text, fact)

    def test_internals_cli_rows_and_criticality(self):
        lines = _read(INTERNALS).splitlines()
        refs = next(l for l in lines if l.startswith("| `acs ticket references "))
        self.assertIn("references, default_branch, web_base, web_base_reason, remote_checked, written}`", refs)
        self.assertIn("## Forge metadata: three commands, two failure policies", lines)
        refresh = next(l for l in lines if l.startswith("| `acs.py tracker refresh "))
        for fact in ("`gh issue view <key> --json body`", "`gh issue edit <key> --body-file <tmp>`",
                     "**non-critical** (ADR-0088)", "`--pending`", "`--dry-run`"):
            self.assertIn(fact, refresh, fact)
        self.assertIn("a `local` ticket or one with no issue is `skipped`", refresh)
        text = _norm(_read(INTERNALS))
        self.assertIn("`external.url` (`record-external.py --url`)", text)
        self.assertIn("`forge.GH_FLOW_CRITICALITY`", text)
        self.assertIn("`requirements.run_references(ctx, rdir)`", text)

    def test_cli_lld(self):
        text = _read(CLI_MD)
        self.assertIn('status: "proposed"', text.split("---", 2)[1])
        lines = text.splitlines()
        for start, fact in (
                ("| `acs.py ticket references ", "references, default_branch, web_base, web_base_reason, remote_checked, written}`"),
                ("| `acs.py tracker refresh ", "non-critical finding (ADR-0088)"),
                ("| `record-external.py ", "`external.url`"),
                ("| `acs.py step start ", "`references`")):
            row = next(l for l in lines if l.startswith(start))
            self.assertIn(fact, row, start)

    def test_plugin_readme(self):
        text = _read(PLUGIN_README)
        rows = {name: next(l for l in text.splitlines() if l.startswith("| `/acs:%s` |" % name))
                for name in ("create-ticket", "breakdown-ticket", "merge-pr")}
        self.assertIn(LINK.strip("()"), rows["create-ticket"])
        self.assertIn("`## References`", rows["create-ticket"])
        self.assertIn("stores each child's references", rows["breakdown-ticket"])
        self.assertIn("`acs.py tracker refresh --pending`", rows["merge-pr"])
        self.assertIn("**A ticket links its documents**", text)

    def test_data_model(self):
        text = _read(DATA_MODEL)
        self.assertRegex(text, r"array references \"optional: [^\"]*\(ADR-0140\)\"")

    def test_requirements(self):
        skills = _norm(_read(SKILLS_MD))
        general = _section(skills, "### A run's references: found from the standard layout",
                           "## `/setup`")
        for fact in ("there is no selection step", "`context.references`",
                     "MUST NOT search the repo for them", "`/breakdown-ticket`"):
            self.assertIn(fact, general, fact)
        create = _section(skills, "## 1. `/create-ticket`", "## 1a.")
        for fact in ("**References (ADR-0140).**", "`acs.py ticket references --features …",
                     "`acs.py ticket references --ticket ID --write`",
                     "`acs.py tracker refresh --ticket ID`", "pending entries marked"):
            self.assertIn(fact, create, fact)
        breakdown = _section(skills, "## 1a. `/breakdown-ticket`", "## 2.")
        for fact in ("`acs.py ticket references --ticket <child> --write`",
                     "each child's `tracker-body.md`", "`acs.py tracker refresh --ticket <epic>`"):
            self.assertIn(fact, breakdown, fact)
        merge = _section(skills, "## 6. `/merge-pr`")
        self.assertIn("**Reference refresh (ADR-0140):**", merge)
        self.assertIn("`acs.py tracker refresh --pending`, best-effort", merge)
        workflow = _norm(_read(WORKFLOW_MD))
        self.assertIn("the step-start context's `references` lists every document", workflow)
        state = _read(STATE_MD)
        self.assertTrue(any(l.startswith("| `references` | object[] |") for l in state.splitlines()))
        self.assertIn("`## References` section", _norm(state))
        log = next(l for l in _read(REQ_README).splitlines()
                   if l.startswith("| 2026-10-06 | **Tickets link their documents**"))
        self.assertIn("ADR 0140", log)


if __name__ == "__main__":
    unittest.main()
