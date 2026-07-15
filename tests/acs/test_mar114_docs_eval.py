"""MAR-114 spec 04 — docs / eval / ADR / CHANGELOG consistency sweep.

Prose-contract tests over every consumer-repo doc this spec touches: the
`contracts.md` settings-key list, `configuration.md`'s Keys table, the
`skills.md` count + new `/acs:test` section, one new `s04` routing CASE, the
CHANGELOG's durable MAR-114 entry, ADR 0011's status flip (with ADR 0012 left
untouched as a regression guard), and the two new ADRs.

Stdlib-only (ast, os, re, unittest). Run:
  python3 -m unittest tests.acs.test_mar114_docs_eval -v
"""

import ast
import glob
import os
import re
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN = os.path.join(REPO_ROOT, "plugins", "acs")
ADR_DIR = os.path.join(REPO_ROOT, "docs", "adr")


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


class ContractsMdSettingsKeyListTest(unittest.TestCase):
    """Approach item 1: contracts.md settings-key list gains suites +
    e2e-deprecated-alias note, plus the boy-scout quality_path/operations_path
    repair."""

    def _contracts(self):
        return read(os.path.join(REPO_ROOT, "docs", "architecture", "lld", "contracts.md"))

    def test_settings_key_list_has_suites_and_e2e_alias_note(self):
        body = self._contracts()
        window = section(body, "## Settings (consumer repo)")
        self.assertIn("suites", window,
                      "contracts.md's settings-key list must gain `suites`")
        m = re.search(r"e2e", window)
        self.assertIsNotNone(m, "contracts.md must still mention `e2e`")
        after = window[m.start():m.start() + 300]
        self.assertIsNotNone(
            re.search(r"(?i)deprecated|alias", after),
            "contracts.md must note `e2e` is a deprecated alias near its mention")

    def test_settings_key_list_boy_scout_repair(self):
        """Boy-scout repair: quality_path/operations_path were missing from
        this list (MAR-112/113 drift) — MAR-114 repairs the whole list."""
        body = self._contracts()
        window = section(body, "## Settings (consumer repo)")
        self.assertIn("quality_path", window,
                      "contracts.md's settings-key list must gain `quality_path` (boy-scout repair)")
        self.assertIn("operations_path", window,
                      "contracts.md's settings-key list must gain `operations_path` (boy-scout repair)")


class ConfigurationMdKeysTableTest(unittest.TestCase):
    """Approach item 2: configuration.md gains a suites row after e2e, and
    the e2e row's description notes deprecation while its shape (Type/
    Default/Required) stays unchanged."""

    def _configuration(self):
        return read(os.path.join(REPO_ROOT, "docs", "requirements", "functional", "configuration.md"))

    def test_suites_row_exists_and_mentions_e2e_and_test_consumer(self):
        body = self._configuration()
        m = re.search(r"(?m)^\|\s*`suites`\s*\|.*$", body)
        self.assertIsNotNone(m, "configuration.md must have a `| `suites` |` row")
        row = m.group(0)
        self.assertIsNotNone(
            re.search(r"(?i)e2e", row),
            "the suites row must mention e2e (the auto-populated reserved name)")
        self.assertIsNotNone(
            re.search(r"(?i)`?/?acs:test`?|\btest\b", row),
            "the suites row must reference /acs:test (or 'test') as a consumer")

    def test_e2e_row_deprecated_but_shape_preserved(self):
        body = self._configuration()
        m = re.search(r"(?m)^\|\s*`e2e`\s*\|.*$", body)
        self.assertIsNotNone(m, "configuration.md must still have a `| `e2e` |` row")
        row = m.group(0)
        self.assertIsNotNone(
            re.search(r"(?i)deprecated|alias", row),
            "the e2e row's description must note deprecation/alias status")
        self.assertIn("object", row,
                      "the e2e row's Type column ('object') must be unchanged")
        self.assertIn("unset", row,
                      "the e2e row's Default column ('unset') must be unchanged")


class SkillsMdCountAndTestSectionTest(unittest.TestCase):
    """Approach item 3: intro count Eighteen -> Nineteen, plus a new
    ## /acs:test utility section after ## /usage."""

    def _skills_req(self):
        return read(os.path.join(REPO_ROOT, "docs", "requirements", "functional", "skills.md"))

    def test_intro_reads_nineteen_not_eighteen(self):
        # The literal skill-count word churns as later skills land (MAR-117
        # moved it Nineteen -> Twenty); pin only that the stale "Eighteen"
        # this test originally guarded against does not recur.
        body = self._skills_req()
        intro = body[:400]
        self.assertNotIn("Eighteen skills", intro,
                         "skills.md intro must NOT still read 'Eighteen skills'")

    def test_acs_test_section_exists_with_expected_content(self):
        body = self._skills_req()
        m = re.search(r"(?m)^## .*/acs:test.*$", body)
        self.assertIsNotNone(m, "skills.md must have a '## /acs:test' section")
        window = section(body, m.group(0))
        self.assertIn("--suite", window,
                      "the /acs:test section must state the --suite argument contract")
        self.assertIsNotNone(
            re.search(r"(?i)unhooked|no planner", window),
            "the /acs:test section must state it is unhooked / has no planner triad")
        self.assertIn("suites", window,
                      "the /acs:test section must reference the suites map")


class S04SkillTriggersCaseTest(unittest.TestCase):
    """Approach item 4: one new /acs:test routing CASE, structurally parsed
    (no paid model call)."""

    def _cases(self):
        path = os.path.join(REPO_ROOT, "evals", "acs", "scenarios", "s04_skill_triggers.py")
        tree = ast.parse(read(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == "CASES" for t in node.targets
            ):
                return ast.literal_eval(node.value)
        raise AssertionError("CASES list not found in s04_skill_triggers.py")

    def test_test_case_present_and_internally_consistent(self):
        cases = self._cases()
        matches = [c for c in cases if c[0] == "test"]
        self.assertTrue(matches, "s04 CASES must contain an entry labeled 'test'")
        case = matches[0]
        self.assertEqual(case[-1], "test",
                          "the 'test' CASE's expected-skill (last element) must be 'test'")


class ChangelogMar114EntryTest(unittest.TestCase):
    """Approach item 5: durable-invariant CHANGELOG entry — never pins the
    literal '[Unreleased]' string as a fixed anchor."""

    def _changelog(self):
        return read(os.path.join(PLUGIN, "CHANGELOG.md"))

    def test_changelog_mar114_entry_in_topmost_section(self):
        body = self._changelog()
        spans = [m.start() for m in re.finditer(r"## \[[^\]]*\]", body)] + [len(body)]
        section_text = None
        for start, end in zip(spans, spans[1:]):
            candidate = body[start:end]
            if "(MAR-114)" in candidate:
                section_text = candidate
                break
        self.assertIsNotNone(
            section_text,
            "CHANGELOG.md must contain '(MAR-114)' inside a section span")
        heading = section_text[:section_text.index("\n")] if "\n" in section_text else section_text
        self.assertRegex(
            heading, r"## \[(Unreleased|\d+\.\d+\.\d+)\]",
            "the '(MAR-114)' entry must live under [Unreleased] or a dated "
            "semver release heading (release cuts legitimately graduate it)")
        self.assertIsNotNone(
            re.search(r"(?i)test|suites", section_text),
            "the MAR-114 CHANGELOG entry must mention test or suites")


class AdrStatusFlipTest(unittest.TestCase):
    """Approach item 7 / constraint adr-0011-only: MAR-114 flips ONLY 0011 to
    Accepted; 0012's own flip is MAR-115's job (now landed)."""

    def test_0011_is_accepted(self):
        body = read(os.path.join(ADR_DIR, "0011-sdlc-doc-sets-quality-and-operations.md"))
        self.assertIn("**Status**: Accepted", body,
                      "ADR 0011 must be flipped to Accepted (C-2)")
        self.assertNotIn("**Status**: Proposed", body,
                         "ADR 0011 must no longer read Proposed")

    def test_0012_is_accepted(self):
        body = read(os.path.join(ADR_DIR, "0012-design-time-doc-consistency.md"))
        self.assertIn("**Status**: Accepted", body,
                      "ADR 0012 must be flipped to Accepted (MAR-115)")


class NewAdrsExistTest(unittest.TestCase):
    """Approach item 6: two new ADRs beyond the pre-existing 0001-0042 set."""

    def _new_adr_files(self):
        files = sorted(glob.glob(os.path.join(ADR_DIR, "0[0-9][0-9][0-9]-*.md")))
        numbered = []
        for path in files:
            base = os.path.basename(path)
            m = re.match(r"(\d{4})-", base)
            if m:
                numbered.append((int(m.group(1)), path))
        return [p for n, p in numbered if n > 42]

    def test_baseline_two_adrs_present_beyond_0042(self):
        # Durable invariant: MAR-114's own two ADRs (0043, 0044) exist beyond
        # the pre-existing 0001-0042 set. NOT an exact-count pin -- later
        # tickets legitimately add further ADRs (e.g. MAR-125's 0045-0047)
        # without regressing this guard.
        basenames = {os.path.basename(p) for p in self._new_adr_files()}
        self.assertTrue(
            any(b.startswith("0043-") for b in basenames),
            "ADR 0043 (suites map generalization) must exist beyond 0042")
        self.assertTrue(
            any(b.startswith("0044-") for b in basenames),
            "ADR 0044 (acs-test closed-loop ticketing) must exist beyond 0042")

    def test_new_adrs_cover_suites_and_closed_loop_ticketing(self):
        new_files = self._new_adr_files()
        bodies = [read(p) for p in new_files]
        suites_adr = [b for b in bodies if "suites" in b and "e2e" in b]
        ticketing_adr = [
            b for b in bodies
            if "new-ticket.py" in b and re.search(r"(?i)regression|recurrence", b)
        ]
        self.assertTrue(suites_adr, "one new ADR must mention suites + e2e")
        self.assertTrue(ticketing_adr,
                        "one new ADR must mention new-ticket.py + regression/recurrence")


if __name__ == "__main__":
    unittest.main()
