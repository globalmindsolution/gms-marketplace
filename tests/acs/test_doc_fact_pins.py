"""Doc-fact pins for MAR-166: roadmap spec_template retirement, README skill
count, and ADR index completeness.

Every "expected" value is derived from disk (skill directory listing, ADR
file listing) rather than a hardcoded literal, so these guards cannot
themselves re-drift from the doc content they pin.
"""

import os
import re
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ROADMAP = os.path.join(REPO_ROOT, "docs", "product", "roadmap.md")
ADR_README = os.path.join(REPO_ROOT, "docs", "adr", "README.md")
ADR_DIR = os.path.join(REPO_ROOT, "docs", "adr")
ACS_README = os.path.join(REPO_ROOT, "plugins", "acs", "README.md")
SKILLS_DIR = os.path.join(REPO_ROOT, "plugins", "acs", "skills")
sys.path.insert(0, os.path.join(REPO_ROOT, "plugins", "acs", "hooks", "scripts"))

import acs_lib as lib  # noqa: E402


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
    the on-disk skill directory count, never a hardcoded literal.

    The design-phase entry-point fold moved the row half of this pin with the
    fact it pins. Before the fold every skill on disk was a `/acs:<name>`
    command, so one `| `/acs:` row per directory was the whole truth. Six
    skills are now INTERNAL LEGS (`workflows/phases.yaml`'s `internal` map):
    they keep their SKILL.md, agents, hooks and gate and stay Skill-invocable,
    but they are not commands a user runs, so the table renders them as legs
    (`| `<leg>` | `/acs:<entry point>` | …`) and not as commands. The pin is
    therefore: command rows == the on-disk set MINUS the legs, leg rows ==
    the `internal` map exactly, and the two together still cover every
    directory. Both halves stay derived from disk and from the registry.
    """

    def _skill_dirs(self):
        return {
            d
            for d in os.listdir(SKILLS_DIR)
            if os.path.isdir(os.path.join(SKILLS_DIR, d))
        }

    def _actual_skill_count(self):
        return len(self._skill_dirs())

    def _command_rows(self):
        return re.findall(r"(?m)^\| `/acs:([a-z0-9-]+)`", _read(ACS_README))

    def _leg_rows(self):
        return re.findall(r"(?m)^\| `([a-z0-9-]+)` \| `/acs:([a-z0-9-]+)`",
                          _read(ACS_README))

    def test_heading_matches_disk_count(self):
        text = _read(ACS_README)
        match = re.search(r"^## The (\d+) skills$", text, re.MULTILINE)
        self.assertIsNotNone(match, "expected a '## The N skills' heading")
        heading_count = int(match.group(1))
        self.assertEqual(heading_count, self._actual_skill_count())

    def test_command_rows_are_the_user_facing_skills(self):
        """Every skill on disk that is NOT an internal leg has exactly one
        `/acs:<name>` row, and no leg has one."""
        legs = set(lib.skill_legs())
        self.assertEqual(sorted(self._command_rows()),
                         sorted(self._skill_dirs() - legs))

    def test_leg_rows_are_the_registry_internal_map(self):
        """Each internal leg has exactly one row, presented as a leg of its
        entry point rather than as a command."""
        self.assertEqual(dict(self._leg_rows()), lib.skill_legs())

    def test_command_rows_and_leg_rows_cover_every_skill_on_disk(self):
        covered = set(self._command_rows()) | {leg for leg, _ in self._leg_rows()}
        self.assertEqual(covered, self._skill_dirs())
        self.assertEqual(len(self._command_rows()) + len(self._leg_rows()),
                         self._actual_skill_count())


class TestingStrategyInvocationClassPinTest(unittest.TestCase):
    """The design-phase entry-point fold moved a fact this document asserts.

    testing-strategy.md's Trigger bullet explains WHY two skills carry a
    routing tick in a column otherwise defined by model routing: they are the
    only skills that set `disable-model-invocation: true`, so they can only be
    probed by an explicit command. The fold gave that flag to the six internal
    legs as well, so "the 2 user-only skills, both disable-model-invocation:
    true" is no longer a complete account of who carries it -- and the reason
    matters, because a DESCRIPTION probe can never route to a skill that
    carries it. The number here is derived from disk, never a literal.
    """

    STRATEGY = os.path.join(REPO_ROOT, "docs", "quality", "testing-strategy.md")
    SKILLS = os.path.join(REPO_ROOT, "plugins", "acs", "skills")

    def _carriers(self):
        found = set()
        for name in sorted(os.listdir(self.SKILLS)):
            path = os.path.join(self.SKILLS, name, "SKILL.md")
            if not os.path.isfile(path):
                continue
            head = _read(path).split("---")[1] if _read(path).startswith("---") else ""
            if re.search(r"(?m)^disable-model-invocation: true$", head):
                found.add(name)
        return found

    def test_carriers_are_the_two_user_only_skills_plus_every_leg(self):
        """Ground truth, from disk and the registry."""
        self.assertEqual(self._carriers(),
                         {"update", "install-hooks"} | set(lib.skill_legs()))

    def test_strategy_does_not_claim_only_two_skills_carry_the_flag(self):
        body = _read(self.STRATEGY)
        self.assertNotIn(
            "the 2 user-only skills\n  (`install-hooks`, `update`, both "
            "`disable-model-invocation: true`)", body,
            "testing-strategy.md still claims install-hooks and update are the "
            "only disable-model-invocation skills; the fold added %d legs"
            % len(lib.skill_legs()))

    def test_strategy_states_the_legs_carry_the_flag_too(self):
        body = _read(self.STRATEGY)
        self.assertIn("internal leg", body)
        self.assertRegex(
            body, r"(?s)disable-model-invocation.{0,1500}description probe can "
                  r"never route")


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
