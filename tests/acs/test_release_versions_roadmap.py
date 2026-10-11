"""MAR-130 — first-class release versions in the roadmap (/acs:manage-roadmap's since ADR-0145).

Pins the populated "Release versions" mapping table in `roadmap.md` (the
0-orphan milestone->version coverage invariant), the manage-roadmap SKILL.md +
agent-charter contract text that mandates the table, and the conformance-doc
notes in `contracts.md`/`skills.md`.

Stdlib-only (re, unittest). Run:
  python3 -m unittest tests.acs.test_mar130_release_versions_roadmap -v
"""

import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from skill_text import skill_contract  # noqa: E402

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN = os.path.join(REPO_ROOT, "plugins", "acs")

# Version-homed units the table must cover at minimum (AC-4/AC-8 coverage floor).
MIN_VERSIONS = {
    "v0.3.5", "v0.3.6", "v0.3.7",  # M2.6 trio
    # v0.4.3 shipped generated-doc quality (G36). v0.4.4 shipped the brownfield
    # requirements-extraction epic (G37, MAR-142). v0.4.5 shipped the
    # readable-docs + doc-templates epic (G38/G39, MAR-149) — the first Wave-4
    # slice to land — so the remaining Wave 4 (org policy G12/G24 + polish)
    # re-homed to the open-ended v0.4.6+ (MAR-153 roadmap reconcile). "v0.4.4",
    # "v0.4.5", and "v0.4.6+" are now real table rows. Team-shared delivery
    # state (G23) stays deferred behind GA to a post-GA milestone (M8).
    "v0.3.8", "v0.4.0", "v0.4.1", "v0.4.2", "v0.4.3", "v0.4.4", "v0.4.5", "v0.4.6+",
}

EXPECTED_HEADER = ["Release version", "Milestone / Wave", "Epic(s) delivered", "Status"]


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def section(body, heading):
    """Return the text of a markdown section: from the line whose start is
    `heading` (matched at line-start) up to the next same-or-higher-level
    heading (or end of file)."""
    m = re.search(r"(?m)^" + re.escape(heading) + r".*$", body)
    if m is None:
        raise AssertionError("heading %r not found" % heading)
    start = m.start()
    level = len(heading) - len(heading.lstrip("#"))
    nxt = re.search(r"(?m)^#{1,%d} \S" % level, body[m.end():])
    end = m.end() + nxt.start() if nxt else len(body)
    return body[start:end]


def _table_rows(section_text):
    """Parse a markdown table's data rows (skip header + separator lines)."""
    lines = [ln for ln in section_text.splitlines() if ln.strip().startswith("|")]
    if len(lines) < 3:
        raise AssertionError("no markdown table (header+separator+row) found in section")
    header = [c.strip() for c in lines[0].strip().strip("|").split("|")]
    rows = []
    for ln in lines[2:]:
        cells = [c.strip() for c in ln.strip().strip("|").split("|")]
        rows.append(cells)
    return header, rows


class RoadmapReleaseVersionsTableTest(unittest.TestCase):
    """AC-4/AC-8: the table exists, has the right shape, and meets the
    coverage floor."""

    def _roadmap(self):
        return read(os.path.join(REPO_ROOT, "docs", "product", "roadmap.md"))

    def _section(self):
        return section(self._roadmap(), "## Release versions")

    def test_heading_and_header_row_present(self):
        header, rows = _table_rows(self._section())
        self.assertEqual(header, EXPECTED_HEADER)
        self.assertGreater(len(rows), 0, "table has no data rows")

    def test_section_sits_above_acs_plugin_track(self):
        body = self._roadmap()
        rel_pos = body.index("## Release versions")
        track_pos = body.index("## acs plugin track")
        self.assertLess(rel_pos, track_pos,
                         "## Release versions must sit above ## acs plugin track")

    def test_coverage_floor_known_versions_present(self):
        header, rows = _table_rows(self._section())
        versions = {r[0] for r in rows}
        missing = MIN_VERSIONS - versions
        self.assertFalse(missing, "table missing required version rows: %r" % missing)


class ZeroOrphanMilestoneInvariantTest(unittest.TestCase):
    """AC-2/AC-8: every milestone/wave cell resolves to exactly one version;
    no Release-version or Epic(s)-delivered cell is empty (the G17
    100%-mapping metric)."""

    def _rows(self):
        body = read(os.path.join(REPO_ROOT, "docs", "product", "roadmap.md"))
        header, rows = _table_rows(section(body, "## Release versions"))
        return rows

    def test_no_empty_version_or_epics_cells(self):
        for row in self._rows():
            version, milestone, epics, status = row[0], row[1], row[2], row[3]
            self.assertTrue(version, "empty Release version cell in row %r" % (row,))
            self.assertTrue(epics, "empty Epic(s) delivered cell in row %r" % (row,))
            self.assertTrue(milestone, "empty Milestone / Wave cell in row %r" % (row,))

    def test_each_milestone_maps_to_exactly_one_version(self):
        mapping = {}
        for row in self._rows():
            version, milestone = row[0], row[1]
            mapping.setdefault(milestone, set()).add(version)
        orphans = {m: v for m, v in mapping.items() if len(v) != 1}
        self.assertFalse(
            orphans,
            "milestone(s) not mapping to exactly one version: %r" % (orphans,))


class ManageRoadmapSkillContractTest(unittest.TestCase):
    """AC-8, moved by ADR-0145: the Release versions table is
    /acs:manage-roadmap's, not create-prd's. Its contract (SKILL.md with its
    references inlined) states the table and the 0-orphan coverage rule, and
    its floor is the script that enforces it."""

    def _skill_md(self):
        return skill_contract("manage-roadmap")

    def test_the_contract_states_the_table_and_its_coverage(self):
        body = self._skill_md()
        self.assertIn("## Release versions", body)
        self.assertIn("exactly one release version", body)
        self.assertIn("0 orphan", body)

    def test_the_review_runs_the_floor_that_enforces_it(self):
        window = section(self._skill_md(), "### Review — the floor, then the reviewer")
        self.assertIn("roadmap_check.py", window)
        script = read(os.path.join(PLUGIN, "hooks", "scripts", "roadmap_check.py"))
        for rule in ("version-unmapped", "version-orphan", "version-duplicate"):
            self.assertIn(rule, script)

    def test_create_prd_no_longer_owns_the_table(self):
        body = skill_contract("create-prd")
        self.assertNotIn("Release versions", body)
        self.assertNotIn("0 orphan milestones", body)


class ManageRoadmapAgentCharterContractTest(unittest.TestCase):
    """AC-3/AC-8: the author writes the table; neither create-prd agent does."""

    def test_author_charter_mirrors_duty(self):
        body = read(os.path.join(PLUGIN, "agents", "manage-roadmap-author.md"))
        self.assertIn("Release versions", body)

    def test_reviewer_judges_the_versions(self):
        body = read(os.path.join(PLUGIN, "agents", "manage-roadmap-reviewer.md"))
        self.assertIn("**Versions**", body)

    def test_create_prd_agents_do_not(self):
        for role in ("author", "reviewer", "surveyor"):
            body = read(os.path.join(PLUGIN, "agents", "create-prd-%s.md" % role))
            self.assertNotIn("Release versions", body, role)


class AdditiveGuardTest(unittest.TestCase):
    """AC-5/C-8: pre-existing wave/version labels and markers survive
    verbatim; no forbidden mar123-pinned substring is introduced."""

    def _roadmap(self):
        return read(os.path.join(REPO_ROOT, "docs", "product", "roadmap.md"))

    def test_preexisting_markers_survive(self):
        body = self._roadmap()
        # "Wave 3 (LEAD)" graduated to shipped when v0.4.2 was cut (MAR-134
        # roadmap reconciliation): Wave 3's release-versions half shipped in
        # v0.4.2 and G23 became the new LEAD at v0.4.3, so the LEAD label is
        # intentionally no longer on Wave 3. The additive guard still holds for
        # the pre-existing wave/version labels that survive the reconciliation.
        for marker in ("Wave 3", "v0.4.2", "16 → 19"):
            self.assertIn(marker, body, "pre-existing marker %r missing" % marker)

    def test_no_forbidden_mar123_substrings_introduced(self):
        body = self._roadmap()
        for stale in ("16 skills + 27 agent files", "= 16,", "= 27);",
                      "six triad-keeping skills", "today 27 vs 21 reachable"):
            self.assertNotIn(stale, body, "forbidden substring %r present in roadmap.md" % stale)


class DecouplingGuardTest(unittest.TestCase):
    """AC-6: the table's caption states the decoupling from the cut skill."""

    def test_caption_states_decoupling(self):
        body = read(os.path.join(REPO_ROOT, "docs", "product", "roadmap.md"))
        window = section(body, "## Release versions")
        # scope to the caption (text before the table itself)
        table_start = window.index("|")
        caption = window[:table_start]
        has_release_ref = "/acs:release" in caption or "cut skill" in caption
        has_decouple_ref = "never read" in caption or "decoupled" in caption
        self.assertTrue(has_release_ref, "caption missing '/acs:release'/'cut skill' reference")
        self.assertTrue(has_decouple_ref, "caption missing 'never read'/'decoupled' phrasing")


class ConformanceDocsTest(unittest.TestCase):
    """AC-7: contracts.md's conformance-chain area (now the settings
    interface, lld/acs/api/settings.md) and skills.md's create-prd section
    document the release-versions mapping-table output."""

    def test_contracts_md_conformance_chain_area_mentions_table(self):
        body = read(os.path.join(REPO_ROOT, "docs", "architecture", "lld", "acs", "api",
                                 "settings.md"))
        m = re.search(r"(?m)^Conformance chain:.*$", body)
        self.assertIsNotNone(m, "contracts.md conformance-chain line not found")
        window = body[max(0, m.start() - 200):m.end() + 800]
        self.assertIn("create-prd", window)
        self.assertTrue(
            "release versions" in window.lower() or "mapping table" in window.lower(),
            "contracts.md conformance-chain area missing the release-versions "
            "mapping-table note")

    def test_skills_md_create_prd_section_documents_table(self):
        body = read(os.path.join(REPO_ROOT, "docs", "requirements", "functional", "skills.md"))
        window = section(body, "## `/create-prd` (product-level)")
        self.assertTrue(
            "Release versions" in window or "mapping table" in window,
            "skills.md create-prd section missing the release-versions "
            "mapping-table output bullet")


if __name__ == "__main__":
    unittest.main()
