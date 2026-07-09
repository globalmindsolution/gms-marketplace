"""MAR-118 spec 03 — docs / eval / CHANGELOG sweep for /acs:create-standards.

Prose-contract tests over every consumer-repo doc this spec touches: the
`skills.md` count + new `/acs:create-standards` section, the
`configuration.md` `standards_path` row, the five C4/architecture count-and-
list files (repaired to the post-this-child totals 21/39/33/ten), one new
`s04` routing CASE, and the CHANGELOG's durable MAR-118 entry.

Stdlib-only (ast, os, re, unittest). Run:
  python3 -m unittest tests.acs.test_mar118_docs_eval -v
"""

import ast
import os
import re
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN = os.path.join(REPO_ROOT, "plugins", "acs")


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


class SkillsMdCountAndSectionTest(unittest.TestCase):
    """AC-10: intro count Twenty -> Twenty-one, plus a new
    ## /acs:create-standards product-level section."""

    def _skills_req(self):
        return read(os.path.join(REPO_ROOT, "docs", "requirements", "skills.md"))

    def test_intro_reads_twentyone_not_twenty(self):
        body = self._skills_req()
        intro = body[:400]
        self.assertIn("Twenty-one skills", intro,
                      "skills.md intro must read 'Twenty-one skills'")
        self.assertNotIn("Twenty skills", intro,
                         "skills.md intro must NOT still read 'Twenty skills'")

    def test_intro_lists_create_standards_as_product_level(self):
        body = self._skills_req()
        intro = body[:600]
        self.assertIn("create-standards", intro,
                      "skills.md intro must list create-standards among the "
                      "product-level skills")

    def test_create_standards_section_exists_with_expected_content(self):
        body = self._skills_req()
        m = re.search(r"(?m)^## .*/acs:create-standards.*$", body)
        self.assertIsNotNone(
            m, "skills.md must have a '## /acs:create-standards' section")
        window = section(body, m.group(0))
        self.assertIn("standards_path", window,
                      "the /acs:create-standards section must mention "
                      "standards_path")
        self.assertIn("create-standards-planner", window,
                      "the /acs:create-standards section must mention the "
                      "planner agent (ADR-0012 doc-consistency step)")
        self.assertIn("docs/standards", window,
                      "the /acs:create-standards section must mention the "
                      "default docs/standards location")
        self.assertIn("principles_path", window,
                      "the /acs:create-standards section must mention the "
                      "principles_path upstream read (D1)")


class ConfigurationMdStandardsPathRowTest(unittest.TestCase):
    """AC-10: configuration.md gains a standards_path row mirroring
    principles_path's shape."""

    def _configuration(self):
        return read(os.path.join(REPO_ROOT, "docs", "requirements", "configuration.md"))

    def test_standards_path_row_exists(self):
        body = self._configuration()
        m = re.search(r"(?m)^\|\s*`standards_path`\s*\|.*$", body)
        self.assertIsNotNone(
            m, "configuration.md must have a `| `standards_path` |` row")
        row = m.group(0)
        self.assertIn("docs/standards", row,
                      "the standards_path row must state default docs/standards")
        self.assertIn("create-standards", row,
                      "the standards_path row must reference /acs:create-standards")


class C4CountAndListFilesTest(unittest.TestCase):
    """AC-10: the five C4/architecture files read the post-this-child totals
    (skill 21 / agent-file 39 / reachable-agent 33 / ten triads) and the
    stale strings are absent."""

    def test_c4_container_skill_and_agent_counts(self):
        body = read(os.path.join(REPO_ROOT, "docs", "architecture", "hld", "c4-container.md"))
        self.assertIn("21 x SKILL.md", body)
        self.assertNotIn("20 x SKILL.md", body)
        self.assertIn("39 x agent .md (33 reachable)", body)
        self.assertNotIn("36 x agent .md (30 reachable)", body)

    def test_c4_container_triad_skill_list_names_all_ten(self):
        body = read(os.path.join(REPO_ROOT, "docs", "architecture", "hld", "c4-container.md"))
        self.assertNotIn("nine triad-keeping skills", body)
        m = re.search(r"triad for the ten triad-keeping skills \(([^)]*)\)", body)
        self.assertIsNotNone(
            m, "c4-container.md must state 'ten triad-keeping skills' with "
               "the enumerated list")
        enumerated = m.group(1)
        for suffix in (
            "prd", "architecture", "project", "quality", "operations",
            "principles", "standards", "design", "spec",
        ):
            self.assertIn(
                suffix, enumerated,
                "c4-container.md triad-skill prose must name -%s" % suffix)
        self.assertIn("code", body)

    def test_tech_stack_skill_and_agent_counts(self):
        body = read(os.path.join(REPO_ROOT, "docs", "architecture", "hld", "tech-stack.md"))
        self.assertIn("acs Skills (21)", body)
        self.assertNotIn("acs Skills (20)", body)
        self.assertIn("39 files, 33 reachable", body)
        self.assertNotIn("36 files, 30 reachable", body)

    def test_overview_triad_list_names_all_ten_not_nine(self):
        body = read(os.path.join(REPO_ROOT, "docs", "architecture", "hld", "overview.md"))
        self.assertNotIn("nine triad-keeping skills", body)
        window = section(body, "## Quality attributes (drive the design)")
        self.assertIn("create-principles", window)
        self.assertIn("create-standards", window)
        self.assertIn("create-quality", window)
        self.assertIn("create-operations", window)

    def test_hook_gated_skill_run_triad_list_names_all_ten_not_nine(self):
        body = read(os.path.join(
            REPO_ROOT, "docs", "architecture", "lld", "flows", "hook-gated-skill-run.md"))
        self.assertNotIn("nine triad-keeping skills", body)
        self.assertIn("create-principles", body)
        self.assertIn("create-standards", body)
        self.assertIn("create-quality", body)
        self.assertIn("create-operations", body)

    def test_c4_component_triad_and_reachable_counts(self):
        body = read(os.path.join(REPO_ROOT, "docs", "architecture", "hld", "c4-component.md"))
        self.assertIn("ten triad-keeping skills", body)
        self.assertNotIn("nine triad-keeping skills", body)
        self.assertIn("10 active triads (30 agents", body)
        self.assertNotIn("9 active triads (27 agents", body)
        self.assertIn("33 reachable agents", body)
        self.assertNotIn("30 reachable agents", body)
        self.assertIn("create-standards", body)


class S04SkillTriggersCaseTest(unittest.TestCase):
    """AC-12: one new create-standards routing CASE, structurally parsed
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

    def test_create_standards_case_present_and_internally_consistent(self):
        cases = self._cases()
        matches = [c for c in cases if c[0] == "create-standards"]
        self.assertTrue(
            matches, "s04 CASES must contain an entry labeled 'create-standards'")
        case = matches[0]
        self.assertEqual(
            case[-1], "create-standards",
            "the 'create-standards' CASE's expected-skill (last element) "
            "must be 'create-standards'")
        self.assertNotIn(
            "create-standards", case[2],
            "the probe request must describe intent without naming the skill")


class ChangelogMar118EntryTest(unittest.TestCase):
    """AC-11: durable-invariant CHANGELOG entry — never pins the literal
    '[Unreleased]' or a dated version string as a fixed anchor."""

    def _changelog(self):
        return read(os.path.join(PLUGIN, "CHANGELOG.md"))

    def test_changelog_mar118_entry_in_topmost_section(self):
        body = self._changelog()
        spans = [m.start() for m in re.finditer(r"## \[[^\]]*\]", body)] + [len(body)]
        section_text = None
        for start, end in zip(spans, spans[1:]):
            candidate = body[start:end]
            if "(MAR-118)" in candidate:
                section_text = candidate
                break
        self.assertIsNotNone(
            section_text,
            "CHANGELOG.md must contain '(MAR-118)' inside a section span")
        heading = section_text[:section_text.index("\n")] if "\n" in section_text else section_text
        self.assertRegex(
            heading, r"## \[(Unreleased|\d+\.\d+\.\d+)\]",
            "the '(MAR-118)' entry must live under [Unreleased] or a dated "
            "semver release heading (release cuts legitimately graduate it)")
        self.assertIsNotNone(
            re.search(r"standards_path", section_text),
            "the MAR-118 CHANGELOG entry must mention standards_path")
        self.assertIsNotNone(
            re.search(r"create-standards", section_text),
            "the MAR-118 CHANGELOG entry must mention create-standards")


if __name__ == "__main__":
    unittest.main()
