"""Doc-fact pins for MAR-166: roadmap spec_template retirement, README skill
count, and ADR index completeness.

Every "expected" value is derived from disk (skill directory listing, ADR
file listing) rather than a hardcoded literal, so these guards cannot
themselves re-drift from the doc content they pin.
"""

import os
import re
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ROADMAP = os.path.join(REPO_ROOT, "docs", "product", "roadmap.md")
ADR_README = os.path.join(REPO_ROOT, "docs", "adr", "README.md")
ADR_DIR = os.path.join(REPO_ROOT, "docs", "adr")
ACS_README = os.path.join(REPO_ROOT, "plugins", "acs", "README.md")
SKILLS_DIR = os.path.join(REPO_ROOT, "plugins", "acs", "skills")


def _read(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


class RoadmapSpecTemplateRetirementTest(unittest.TestCase):
    """AC-1: the G38/G39 bullet stops promising formats.spec_template /
    create-spec extension as live, without rewriting the shipped-v0.4.5
    record."""

    def _bullet_window(self):
        text = _read(ROADMAP)
        start = text.index("Epic: readable audience-aware docs + configurable doc templates")
        end = text.index("Epic: onboarding polish", start)
        return text[start:end]

    def test_shipped_v045_closer_kept_verbatim(self):
        window = self._bullet_window()
        self.assertIn(
            "(Shipped in v0.4.5 — G38/G39 epic MAR-149: MAR-150 #284, MAR-151 #285, MAR-152 #286.)",
            window,
        )

    def test_retirement_annotation_present(self):
        window = self._bullet_window()
        self.assertIn("MAR-156", window)
        self.assertRegex(window, r"spec_template")
        self.assertRegex(window, r"create-spec")

    def test_design_template_still_asserted_live(self):
        window = self._bullet_window()
        self.assertIn("formats.design_template", window)


class ReadmeSkillCountPinTest(unittest.TestCase):
    """AC-2: plugins/acs/README.md's skill-table heading is pinned against
    the on-disk skill directory count, never a hardcoded literal."""

    def _actual_skill_count(self):
        return len(
            [
                d
                for d in os.listdir(SKILLS_DIR)
                if os.path.isdir(os.path.join(SKILLS_DIR, d))
            ]
        )

    def test_heading_matches_disk_count(self):
        text = _read(ACS_README)
        match = re.search(r"^## The (\d+) skills$", text, re.MULTILINE)
        self.assertIsNotNone(match, "expected a '## The N skills' heading")
        heading_count = int(match.group(1))
        self.assertEqual(heading_count, self._actual_skill_count())

    def test_table_row_count_matches_disk_count(self):
        text = _read(ACS_README)
        rows = re.findall(r"^\| `/acs:", text, re.MULTILINE)
        self.assertEqual(len(rows), self._actual_skill_count())


class AdrIndexCompletenessTest(unittest.TestCase):
    """AC-3/AC-4: docs/adr/README.md's index table stays complete against the
    on-disk ADR files, bidirectionally, so the gap cannot silently reopen."""

    NAMED_SEVENTEEN = [
        "0030",
        "0031",
        "0032",
        "0033",
        "0034",
        "0042",
        "0043",
        "0044",
        "0055",
        "0056",
        "0057",
        "0060",
        "0061",
        "0062",
        "0063",
        "0064",
        "0065",
    ]

    def _table_ids(self):
        text = _read(ADR_README)
        return set(re.findall(r"^\| \[(\d{4})\]", text, re.MULTILINE))

    def _disk_ids(self):
        ids = set()
        for name in os.listdir(ADR_DIR):
            if name == "README.md" or not name.endswith(".md"):
                continue
            match = re.match(r"^(\d{4})-", name)
            if match:
                ids.add(match.group(1))
        return ids

    def test_seventeen_named_adrs_present(self):
        table_ids = self._table_ids()
        for adr_id in self.NAMED_SEVENTEEN:
            self.assertIn(adr_id, table_ids)

    def test_every_disk_file_has_a_row(self):
        missing = self._disk_ids() - self._table_ids()
        self.assertEqual(missing, set(), f"ADR files with no index row: {sorted(missing)}")

    def test_every_row_has_a_disk_file(self):
        extra = self._table_ids() - self._disk_ids()
        self.assertEqual(extra, set(), f"index rows with no ADR file: {sorted(extra)}")


if __name__ == "__main__":
    unittest.main()
