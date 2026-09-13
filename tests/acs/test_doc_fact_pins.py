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

    def test_the_re_derivation_hint_is_real_not_a_placeholder(self):
        """The Trigger bullet tells a reader to re-derive its two figures. An
        elided `python3 -c "...; ..."` stub is not a command anyone can run --
        the hint must name the module that actually derives them."""
        body = _read(self.STRATEGY)
        self.assertNotRegex(body, r"python3 -c \"[^\"]*\.\.\.")
        self.assertIn("test_eval_trigger_detection.py", body)
        self.assertIn("UNPROBED", body)

    def test_strategy_states_the_legs_carry_the_flag_too(self):
        body = _read(self.STRATEGY)
        self.assertIn("internal leg", body)
        self.assertRegex(
            body, r"(?s)disable-model-invocation.{0,1500}description probe can "
                  r"never route")


class LegResumeFormPinTest(unittest.TestCase):
    """The fold's docs say a leg's own command survives for RESUME. Two of them
    spelled that as a single universal template, `/acs:<leg> <ticket-id>` --
    which is false for a leg whose own frontmatter takes no argument at all
    (`create-project`, argument-hint `(no arguments)`, resumes by finding its
    own unfinished scaffold ticket in `tickets-index.json`). The legs and their
    argument-hints come from disk; only the claim is pinned here.
    """

    ADR = os.path.join(ADR_DIR, "0091-design-phase-entry-point-fold.md")
    TEMPLATE = "`/acs:<leg> <ticket-id>`"

    def _argumentless_legs(self):
        found = set()
        for leg in lib.skill_legs():
            fm = _read(os.path.join(SKILLS_DIR, leg, "SKILL.md")).split("---")[1]
            if re.search(r'(?m)^argument-hint: "\(no arguments\)"$', fm):
                found.add(leg)
        return found

    def test_a_leg_that_takes_no_argument_exists(self):
        """Ground truth: without one, the pin below would be vacuous."""
        self.assertIn("create-project", self._argumentless_legs())

    def test_no_doc_claims_one_universal_ticket_id_resume_form(self):
        for path in (ACS_README, self.ADR):
            with self.subTest(doc=os.path.basename(path)):
                self.assertNotIn(self.TEMPLATE, _read(path),
                                 "%s presents %s as every leg's resume form, but "
                                 "%s take no argument"
                                 % (os.path.basename(path), self.TEMPLATE,
                                    ", ".join(sorted(self._argumentless_legs()))))


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


class SkillCountDenominatorPinTest(unittest.TestCase):
    """MAR-522/ADR-0091 rot guard: the skill-count denominators in
    testing-strategy.md must match what is actually on disk.

    These went stale twice without anything noticing -- the refactor moved the
    inventory and the doc kept quoting the old totals in three separate places,
    contradicting itself. Nothing pinned them, so CI stayed green. Every
    expected value here is derived, so adding or removing a skill fails this
    test until the prose is updated with it.
    """

    @classmethod
    def setUpClass(cls):
        cls.text = _read(os.path.join(REPO_ROOT, "docs", "quality", "testing-strategy.md"))
        cls.skills = len([n for n in os.listdir(SKILLS_DIR)
                          if os.path.isdir(os.path.join(SKILLS_DIR, n)) and not n.startswith(".")])
        cls.hooked = len(lib.HOOKED_SKILLS)
        cls.unhooked = len(lib.UNHOOKED_SKILLS)

    def test_the_registry_split_adds_up_to_the_directory_count(self):
        """Sanity on the derivation itself, so a wrong pin cannot look right."""
        self.assertEqual(self.hooked + self.unhooked, self.skills)

    def test_every_denominator_in_the_doc_is_a_live_count(self):
        """EXHAUSTIVE, deliberately. Asserting that a correct "32 of 32" appears
        somewhere is not enough: this doc states the same fact in three separate
        places, and the rot that prompted this guard was two of them being left
        behind while the third was updated. Every `N of M` must check out.
        """
        allowed = {self.skills, self.hooked}
        wrong = []
        for match in re.finditer(r"(\d+) of (\d+)(?P<tail>[^\n]{0,6})", self.text):
            if match.group("tail").startswith(" runs"):
                continue  # a mutant-survival figure, not a skill denominator
            if int(match.group(2)) not in allowed:
                wrong.append("%r (denominators must be %s)"
                             % (match.group(0).strip(), sorted(allowed)))
        self.assertEqual(wrong, [], "stale denominators in testing-strategy.md:\n  "
                                    + "\n  ".join(wrong))

    def test_the_three_coverage_claims_are_each_present(self):
        """Pins the numerators too, so a claim cannot quietly vanish."""
        for needle in ("%d of %d" % (self.skills, self.skills),
                       "%d of %d hooked" % (self.hooked, self.hooked),
                       "only 3 of %d" % self.skills):
            with self.subTest(needle=needle):
                self.assertIn(needle, self.text)

    def test_the_registry_split_prose_matches_acs_lib(self):
        for needle in ("**%d hooked**" % self.hooked, "**%d unhooked**" % self.unhooked):
            with self.subTest(needle=needle):
                self.assertIn(needle, self.text)

    def test_the_re_derive_note_reports_the_live_numbers(self):
        """The doc tells a reader how to re-derive; those figures must be live too."""
        self.assertIn("(→ `%d`)" % self.skills, self.text)
        self.assertIn("(→ `%d %d`)" % (self.hooked, self.unhooked), self.text)


class ScriptPathReferencesResolveTest(unittest.TestCase):
    """MAR-522 rot guard: a doc or test that names a hook-script path must name
    one that exists.

    `acs_lib.py` became the package `acs_lib/`, and 47 files went on citing the
    vanished file -- some with line numbers into it. Nothing caught that either.
    Any reference to a path under plugins/acs/hooks/scripts must resolve, unless
    it is listed below as a deliberate mention of history.
    """

    SCRIPTS = os.path.join(REPO_ROOT, "plugins", "acs", "hooks", "scripts")
    #: (path, needle) -> why this mention of a non-existent file is correct.
    ALLOWED = {
        ("plugins/acs/CHANGELOG.md", "acs_lib.py"):
            "a changelog records what past releases did; rewriting it would falsify history",
        ("tests/acs/acs_case.py", "acs_lib.py"):
            "describes the MAR-522 split itself (what reading acs_lib.py used to give)",
        ("tests/acs/test_evidence_sidecar_topology.py", "acs_lib.py"):
            "notes that MAR-522 split acs_lib.py into a package",
        ("tests/acs/test_setup_skill_reference_sweep.py", "acs_lib.py"):
            "explains why a guard went vacuous once MAR-522 deleted acs_lib.py",
        ("tests/acs/test_ship_fix_retest_loop.py", "acs_lib.py"):
            "asserts a false claim is ABSENT from a skill body; the string must stay verbatim",
        ("tests/acs/test_testing_conventions_guard.py", "acs_lib.py"):
            "deliberate stale-path fixture proving the allowlist-staleness detector fires",
        ("tests/acs/test_ticket_id_reconciliation.py", "acs_lib.py"):
            "live code: a filename comparison when listing the scripts directory",
        ("tests/acs/test_doc_fact_pins.py", "acs_lib.py"):
            "this guard's own allowlist must name the path it allows; the "
            "load-bearing test below keeps every entry honest",
    }
    #: Module docstrings that record their own extraction are allowed wholesale.
    EXTRACTION_NOTE = "extracted from acs_lib.py by MAR-522"

    def _referring_files(self):
        for sub in ("docs", "tests", "plugins"):
            for root, dirs, names in os.walk(os.path.join(REPO_ROOT, sub)):
                dirs[:] = [d for d in dirs if d not in {"__pycache__", ".git"}]
                for name in names:
                    if name.endswith((".md", ".py")):
                        yield os.path.join(root, name)

    def test_every_hook_script_path_named_in_a_doc_or_test_exists(self):
        pattern = re.compile(r"(?<![\w.])(acs_lib(?:/[A-Za-z0-9_]+)?\.py)")
        unresolved = []
        for path in self._referring_files():
            rel = os.path.relpath(path, REPO_ROOT)
            with open(path, "r", encoding="utf-8") as fh:
                text = fh.read()
            for lineno, line in enumerate(text.split("\n"), 1):
                if self.EXTRACTION_NOTE in line:
                    continue
                for ref in pattern.findall(line):
                    if os.path.exists(os.path.join(self.SCRIPTS, ref)):
                        continue
                    if (rel, ref) in self.ALLOWED:
                        continue
                    unresolved.append("%s:%d names %s, which does not exist" % (rel, lineno, ref))
        self.assertEqual(unresolved, [], "\n  " + "\n  ".join(unresolved))

    def test_every_allowlist_entry_is_still_load_bearing(self):
        """An allowlist that outlives its reason is how the next rot hides."""
        stale = []
        for (rel, needle), reason in self.ALLOWED.items():
            full = os.path.join(REPO_ROOT, rel)
            if not os.path.exists(full):
                stale.append("%s no longer exists (reason: %s)" % (rel, reason))
                continue
            with open(full, "r", encoding="utf-8") as fh:
                if needle not in fh.read():
                    stale.append("%s no longer mentions %s (reason: %s)" % (rel, needle, reason))
        self.assertEqual(stale, [], "\n  " + "\n  ".join(stale))
