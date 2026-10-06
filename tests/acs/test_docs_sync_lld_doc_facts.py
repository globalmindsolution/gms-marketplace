"""ADR-0137 doc facts: /acs:docs-sync keeps the feature's LLD current and moves
a matching design to `implemented`.

Pins the documentation side of the change — the ADR, its index row and the
status lines it adds to ADR-0122, ADR-0126 and ADR-0134; the CHANGELOG entry
(under `[Unreleased]` / `### Changed`, not breaking); the INTERNALS role table,
derived-states table and design-lifecycle paragraph; the plugin README; the
living requirements; and the agent-file count every live document states,
which must equal the files on disk. The skill and agent files themselves are
pinned by their own tests.

Stdlib only.
"""

import os
import re
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ADR_DIR = os.path.join(REPO_ROOT, "docs", "architecture", "adr")
ADR_0137 = os.path.join(ADR_DIR, "0137-docs-sync-keeps-the-feature-lld-current.md")
AMENDED = {
    "0122": os.path.join(ADR_DIR, "0122-design-versions-and-gap-detection.md"),
    "0126": os.path.join(ADR_DIR, "0126-lld-data-design-and-flows.md"),
    "0134": os.path.join(ADR_DIR, "0134-api-contract-is-a-design-document.md"),
}
ADR_README = os.path.join(ADR_DIR, "README.md")
CHANGELOG = os.path.join(REPO_ROOT, "plugins", "acs", "CHANGELOG.md")
INTERNALS = os.path.join(REPO_ROOT, "plugins", "acs", "docs", "INTERNALS.md")
PLUGIN_README = os.path.join(REPO_ROOT, "plugins", "acs", "README.md")
SKILLS_MD = os.path.join(REPO_ROOT, "docs", "requirements", "functional", "skills.md")
REFLECTION = os.path.join(REPO_ROOT, "docs", "requirements", "functional", "reflection.md")
AGENTS_DIR = os.path.join(REPO_ROOT, "plugins", "acs", "agents")

LINK = "(0137-docs-sync-keeps-the-feature-lld-current.md)"

#: Live documents that state the agent-file count, and the phrase each uses.
COUNT_PHRASES = {
    "plugins/acs/docs/INTERNALS.md": "{n} agent files named `<skill>-<role>`",
    "docs/requirements/functional/reflection.md": "{n} agent files exist on disk in total",
    "docs/requirements/non-functional/packaging-distribution.md":
        "{n} agent files exist on disk and {n} are reachable",
    "docs/product/prd.md": "{n} agent files exist on disk and only {n} are reachable",
    "docs/product/roadmap.md": "`ls plugins/acs/agents` = {n}",
    "docs/architecture/hld/c4-component.md": "**{n} agent files, all reachable**",
    "docs/architecture/hld/c4-container.md": "{n} x agent .md (all reachable)",
    "docs/architecture/hld/tech-stack.md": "Subagents ({n} files, all reachable)",
}


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


def _unreleased_changed():
    text = _read(CHANGELOG)
    start = text.index("## [Unreleased]")
    end = text.index("\n## [", start + 1)
    section = text[start:end]
    changed = section.index("### Changed")
    nxt = section.find("\n### ", changed + 1)
    return section[changed:nxt if nxt != -1 else len(section)]


def _agent_files():
    return sorted(f for f in os.listdir(AGENTS_DIR) if f.endswith(".md"))


class AdrTest(unittest.TestCase):

    def test_adr_is_accepted_and_dated(self):
        text = _read(ADR_0137)
        self.assertTrue(text.startswith("# 0137 — "), text[:80])
        self.assertIn("**Status**: Accepted · **Date**: 2026-10-05", text)

    def test_adr_names_what_it_amends(self):
        text = _read(ADR_0137)
        amends = text[text.index("**Amends**"):text.index("## Context")]
        for adr, path in AMENDED.items():
            self.assertIn("[%s](%s)" % (adr, os.path.basename(path)), amends, adr)

    def test_adr_records_the_decision(self):
        text = _norm(_read(ADR_0137))
        for fact in ("`lld`", "`docs-sync-gap-analyst`", "`implemented-candidate`",
                     "`acs.py write`", "`acs.py notes merge`", "`iter-1/gaps.md`",
                     "`states.implemented`", "`lld-currency`", "`placement`",
                     "--set implemented --by acs", "`deprecated`: never touched",
                     "`needs_input`", "35 agent files"):
            self.assertIn(fact, text, fact)
        for verdict in ("**matches**", "**unimplemented**", "**undocumented**",
                        "**drifted**"):
            self.assertIn(verdict, text, verdict)

    def test_amended_adrs_carry_a_status_line_and_keep_their_decision(self):
        for adr, path in AMENDED.items():
            text = _read(path)
            self.assertIn(LINK, _status_line(text), adr)
            # The decision text itself is not edited: 0122 still gives the move
            # to docs-sync, 0126 and 0134 still record the gap they had.
        self.assertIn("`/acs:docs-sync` moves a design to `implemented` once its code lands",
                      _norm(_read(AMENDED["0122"])))
        self.assertIn("`/acs:docs-sync` does not yet keep `lld/<feature>/` current",
                      _norm(_read(AMENDED["0126"])))
        self.assertIn("`/acs:docs-sync` still does not keep `lld/<feature>/` current",
                      _norm(_read(AMENDED["0134"])))

    def test_index_row_and_amended_rows(self):
        row = _index_row("0137")
        self.assertIn(LINK, row)
        self.assertTrue(row.endswith("(amends 0122, 0126, 0134) | Accepted |"), row[-80:])
        for adr in AMENDED:
            self.assertIn(LINK, _index_row(adr).rsplit("|", 2)[-2], adr)


class ChangelogTest(unittest.TestCase):

    def test_changed_bullet_is_present_and_not_breaking(self):
        changed = _unreleased_changed()
        bullets = [b for b in re.split(r"\n(?=- \*\*)", changed) if "(ADR-0137)" in b]
        self.assertEqual(len(bullets), 1, "one ### Changed bullet cites ADR-0137")
        bullet = _norm(bullets[0])
        self.assertNotIn("BREAKING", bullet)
        for fact in ("`docs-sync-gap-analyst`", "`states.implemented`", "`lld-currency`",
                     "`models.docs-sync.gap-analyst`", "35 agent files"):
            self.assertIn(fact, bullet, fact)


class LiveDocsTest(unittest.TestCase):

    def test_internals_no_longer_says_docs_sync_does_not_run_the_move(self):
        text = _norm(_read(INTERNALS))
        self.assertNotIn("does not run it yet", text)
        self.assertIn("assigns the move to `implemented` to `/acs:docs-sync`, and "
                      "docs-sync runs it (ADR-0137)", text)

    def test_internals_role_table_and_derived_states(self):
        text = _read(INTERNALS)
        row = next(l for l in text.splitlines() if l.startswith("| `docs-sync` |"))
        for role in ("`doc-updater` (write", "`gap-analyst` (survey", "`drift-reviewer` (judge"):
            self.assertIn(role, row)
        self.assertIn("`requirements`, `architecture`, `lld`, `adr`, `general`", row)
        self.assertIn("**Six `states` keys are DERIVED", text)
        self.assertIn("(`verifier_passed`, `tests`, `pr`, `review`, `implemented`)", text)
        self.assertTrue(any(l.startswith("| `implemented` (`docs-sync` only")
                            for l in text.splitlines()))

    def test_plugin_readme_docs_sync_row(self):
        row = next(l for l in _read(PLUGIN_README).splitlines()
                   if l.startswith("| `/acs:docs-sync` |"))
        self.assertIn("lld/<feature>/", row)
        self.assertIn("`approved → implemented`", row)
        self.assertIn(LINK.strip("()"), row)

    def test_requirements_docs_sync_section(self):
        text = _norm(_read(SKILLS_MD))
        section = text[text.index("## 4. `/docs-sync`"):text.index("## 5. `/create-pr`")]
        for fact in ("`docs-sync-gap-analyst`", "`implemented-candidate`", "`lld-currency`",
                     "`states.implemented`", "never edits a run's record folder",
                     "A `deprecated` document is never touched"):
            self.assertIn(fact, section, fact)
        reflection = _read(REFLECTION)
        self.assertTrue(any(l.startswith("| docs-sync | `docs-sync-gap-analyst`")
                            for l in reflection.splitlines()))

    def test_every_stated_agent_count_matches_the_files_on_disk(self):
        n = len(_agent_files())
        self.assertIn("docs-sync-gap-analyst.md", _agent_files())
        for rel, phrase in COUNT_PHRASES.items():
            body = _read(os.path.join(REPO_ROOT, rel))
            self.assertIn(phrase.format(n=n), _norm(body),
                          "%s must state %d agent files" % (rel, n))


if __name__ == "__main__":
    unittest.main()
