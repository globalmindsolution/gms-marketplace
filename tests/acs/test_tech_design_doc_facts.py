"""ADR-0135 doc facts: `/acs:create-design` became `/acs:create-tech-design`.

Pins the documentation side of the rename — the ADR and its index row, the
status lines it adds to ADR-0118 and ADR-0130, the CHANGELOG's breaking entry,
the living requirements, and the user-facing README — and guards that every
live document that still names the old skill does so only as a legacy note
beside the new name. History (other ADRs, dated rows, released CHANGELOG
sections) keeps the old name and is not scanned.

Stdlib only.
"""

import os
import re
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ADR_DIR = os.path.join(REPO_ROOT, "docs", "architecture", "adr")
ADR_0135 = os.path.join(ADR_DIR, "0135-create-tech-design.md")
ADR_0118 = os.path.join(ADR_DIR, "0118-discovery-design-development-phases.md")
ADR_0130 = os.path.join(ADR_DIR, "0130-prd-versions-and-set-doc-status.md")
ADR_README = os.path.join(ADR_DIR, "README.md")
CHANGELOG = os.path.join(REPO_ROOT, "plugins", "acs", "CHANGELOG.md")
ACS_README = os.path.join(REPO_ROOT, "plugins", "acs", "README.md")
SKILLS_MD = os.path.join(REPO_ROOT, "docs", "requirements", "functional", "skills.md")

#: Live documents: they describe acs as it is, so the old name may appear in
#: them only as a legacy note within a few lines of the new one.
LIVE_DOCS = (
    "README.md",
    "plugins/acs/README.md",
    "plugins/acs/docs/INTERNALS.md",
    "plugins/acs/docs/AUTHORING.md",
    "docs/requirements/functional/configuration.md",
    "docs/requirements/functional/hooks.md",
    "docs/requirements/functional/skills.md",
    "docs/requirements/functional/usage.md",
    "docs/requirements/functional/workflow.md",
    "docs/requirements/functional/workspace-and-state.md",
    "docs/requirements/non-functional/packaging-distribution.md",
    "docs/requirements/non-functional/quality-gates.md",
    "docs/architecture/hld/c4-component.md",
    "docs/architecture/hld/overview.md",
    "docs/architecture/lld/acs/api/coordinator-subagent.md",
    "docs/architecture/lld/acs/api/cli.md",
    "docs/architecture/lld/acs/api/delivery-path.md",
    "docs/architecture/lld/acs/api/guard-audit.md",
    "docs/architecture/lld/acs/api/state-files.md",
    "docs/architecture/lld/acs/api/settings.md",
    "docs/architecture/lld/acs/flows/hook-gated-skill-run.md",
    "docs/architecture/lld/acs/flows/ship-pipeline.md",
    "docs/product/operating-model.md",
    "docs/quality/testing-strategy.md",
    "docs/quality/behavioural-eval-rubric.md",
)

OLD_NAME = re.compile(r"(?<![\w-])(?:create-design(?![\w-])|design-reviewer|gate_create_design)")

SECTIONS_IN_ORDER = ("**Decision & options**", "**HLD views affected**", "**LLD**",
                     "**API**", "**Data**", "**Flows**", "**Components**",
                     "**NFRs**", "**Risks**", "**Open")


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _norm(text):
    return re.sub(r"\s+", " ", text)


class Adr0135RecordTest(unittest.TestCase):

    def test_adr_is_accepted_dated_and_amends_0118_and_0130(self):
        body = _read(ADR_0135)
        self.assertTrue(body.startswith("# 0135 — "))
        # Accepted, possibly amended later (ADR-0139 amends its brake).
        self.assertRegex(body, r"\*\*Status\*\*: Accepted( — amended by [^\n]*)? · \*\*Date\*\*: 2026-10-05")
        amends = body[body.index("**Amends**"):body.index("## Context")]
        self.assertIn("(0118-discovery-design-development-phases.md)", amends)
        self.assertIn("(0130-prd-versions-and-set-doc-status.md)", amends)

    def test_adr_records_the_decisions(self):
        body = _norm(_read(ADR_0135))
        for fact in ("`/acs:create-tech-design`", "`create-tech-design-designer`",
                     "`create-tech-design-reviewer`", "`gate_create_tech_design`",
                     "`tech-design.md`", "`design.md`", "`steps/create-design/`",
                     "`/acs:set-doc-status approved <feature>`",
                     "`models.create-tech-design`", "`migrate_settings`",
                     "`## Decision & options`", "`## HLD views affected`", "`## LLD`",
                     "`## NFRs`", "`## Risks`", "`## Open questions`"):
            self.assertIn(fact, body)

    def test_index_row_and_amended_status_lines(self):
        index = _read(ADR_README)
        row = [l for l in index.splitlines() if l.startswith("| [0135](0135-create-tech-design.md)")]
        self.assertEqual(len(row), 1, "ADR index must carry exactly one 0135 row")
        self.assertRegex(row[0].rstrip(), r"\(amends 0118, 0130\) \| Accepted( — amended by [^|]*)? \|$")
        for num in ("0118", "0130"):
            line = [l for l in index.splitlines() if l.startswith("| [%s]" % num)][0]
            self.assertIn("[0135](0135-create-tech-design.md)", line.rsplit("|", 2)[1])
        for path in (ADR_0118, ADR_0130):
            status = [l for l in _read(path).splitlines() if l.startswith("**Status**")][0]
            self.assertIn("[0135](0135-create-tech-design.md)", status)


class ChangelogBreakingEntryTest(unittest.TestCase):

    def _unreleased_changed(self):
        text = _read(CHANGELOG)
        start = text.index("## [Unreleased]")
        end = text.index("\n## [", start + 1)
        if not text[start + len("## [Unreleased]"):end].strip():
            # right after a cut [Unreleased] is empty and the notes sit in the newest dated section
            # these notes sit in the 0.6.0 section; later releases stack above it
            anchor = text.index("\n## [0.6.0]", start)
            start = anchor
            end = text.find("\n## [", anchor + 1)
            end = len(text) if end == -1 else end
        unreleased = text[start:end]
        changed = unreleased.index("### Changed")
        removed = unreleased.index("### Removed", changed)
        return unreleased[changed:removed]

    def test_breaking_bullet_with_migration(self):
        section = self._unreleased_changed()
        head = "- **⚠️ BREAKING: `/acs:create-design` is renamed `/acs:create-tech-design`"
        self.assertIn(head, section)
        bullet = section[section.index(head):]
        nxt = bullet.find("\n- ", 1)
        bullet = _norm(bullet if nxt < 0 else bullet[:nxt])
        self.assertIn("(ADR-0135)", bullet)
        migration = bullet[bullet.index("**Migration:**"):]
        for fact in ("`/acs:create-tech-design`", "`models.create-design`",
                     "`models.create-tech-design`", "automatically", "`design.md`",
                     "`/acs:set-doc-status approved <feature>`"):
            self.assertIn(fact, migration)


class LivingRequirementsTest(unittest.TestCase):

    def _section(self):
        body = _read(SKILLS_MD)
        start = body.index("## 2. `/create-tech-design` *(conditional)*")
        end = body.index("\n## ", start + 1)
        return _norm(body[start:end])

    def test_old_heading_is_gone(self):
        self.assertNotIn("## 2. `/create-design`", _read(SKILLS_MD))

    def test_sections_are_listed_in_order(self):
        section = self._section()
        produces = section[section.index("Produces **`tech-design.md`**"):]
        positions = [produces.index(name) for name in SECTIONS_IN_ORDER]
        self.assertEqual(positions, sorted(positions))

    def test_approval_fallback_and_reviewer(self):
        section = self._section()
        for fact in ("`acs.py design init`", "`/acs:set-doc-status approved <feature>`",
                     "falls back to a legacy `design.md`", "- The `create-tech-design-reviewer` checks:",
                     "snapshot freshness", "`models.create-tech-design`"):
            self.assertIn(fact, section)

    def test_set_doc_status_lists_the_tech_design_only(self):
        body = _norm(_read(SKILLS_MD))
        self.assertIn("MUST list `tech-design.md` only", body)


class ReadmeTest(unittest.TestCase):

    def test_design_row_names_the_document_and_the_approval(self):
        rows = [l for l in _read(ACS_README).splitlines() if l.startswith("| `/acs:create-tech-design` |")]
        self.assertEqual(len(rows), 1)
        for fact in ("`tech-design.md`", "`/acs:set-doc-status approved <feature>`",
                     "0135-create-tech-design.md"):
            self.assertIn(fact, rows[0])
        self.assertNotIn("| `/acs:create-design` |", _read(ACS_README))


class LiveDocsNameTheNewSkillTest(unittest.TestCase):
    """A live document may name the old skill, its old reviewer role or its old
    gate only as a legacy note: within three lines of `tech-design`."""

    def test_old_name_only_beside_the_new_one(self):
        stray = []
        for rel in LIVE_DOCS:
            lines = _read(os.path.join(REPO_ROOT, rel)).splitlines()
            for i, line in enumerate(lines):
                if not OLD_NAME.search(line):
                    continue
                window = "\n".join(lines[max(0, i - 3):i + 4])
                if "tech-design" not in window:
                    stray.append("%s:%d: %s" % (rel, i + 1, line.strip()[:120]))
        self.assertEqual(stray, [], "\n  " + "\n  ".join(stray))


if __name__ == "__main__":
    unittest.main()
