"""MAR-70 — /acs:code's plan artifact renamed to plan.md, with a bounded
resume-only read-both compat fallback and axis (b)/(c) protection.

Three naming axes touch these files: (a) the plan artifact itself (`.md`,
renamed here), (b) per-iteration XML message persistence
(`iter-<n>-<phase>.xml`, unchanged), (c) execute/verify phase artifacts
(`iter-<n>-execute*.json` / `iter-<n>-verify*.md`, unchanged). This module
asserts axis (a) moved and axes (b)/(c) did not.

Stdlib-only (os, re, unittest). Run:
  python3 -m unittest tests.acs.test_plan_artifact_naming -v
"""

import os
import re
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN = os.path.join(REPO_ROOT, "plugins", "acs")
AGENTS_DIR = os.path.join(PLUGIN, "agents")

CODE_SKILL = os.path.join(PLUGIN, "skills", "code", "SKILL.md")
CODE_PLANNER = os.path.join(AGENTS_DIR, "code-planner.md")
CODE_EXECUTOR = os.path.join(AGENTS_DIR, "code-executor.md")
CODE_VERIFIER = os.path.join(AGENTS_DIR, "code-verifier.md")

TRIAD_AGENT_FILES = [CODE_PLANNER, CODE_EXECUTOR, CODE_VERIFIER]

# .md-anchored only — iter-<n>-plan.xml (axis b) must NOT match this literal.
LEGACY = re.compile(r"iter-(?:<n>|\{n\}|\*|\d+)-plan\.md")
ALLOWED_SECTION = "### Plan artifact resolution (read-both compat)"


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def section_span(body, heading):
    """Char offsets (start, end) of the section at `heading`, up to the next
    level-1/2/3 heading or end of file."""
    start = body.index(heading)
    rest = body[start + len(heading):]
    m = re.search(r"\n#{1,3} ", rest)
    end = start + len(heading) + (m.start() if m else len(rest))
    return start, end


class FreshRunNamingTest(unittest.TestCase):
    """AC-1: plan.md is the artifact name on a fresh run."""

    def test_plan_md_named_in_coordinator_and_all_three_agents(self):
        for path in [CODE_SKILL] + TRIAD_AGENT_FILES:
            body = read(path)
            self.assertIn("phases/code/plan.md", body,
                           "%s must name phases/code/plan.md" % path)

    def test_planner_phase_artifact_section_names_plan_md_with_no_legacy_literal(self):
        body = read(CODE_PLANNER)
        start, end = section_span(body, "## Phase artifact")
        section = body[start:end]
        self.assertIn("plan.md", section)
        self.assertEqual(LEGACY.findall(section), [],
                          "code-planner.md's ## Phase artifact section must "
                          "name no legacy plan literal")


class ReadBothCompatTest(unittest.TestCase):
    """AC-2: resume-only read-both compat, one named section."""

    @classmethod
    def setUpClass(cls):
        cls.body = read(CODE_SKILL)

    def _section(self):
        start, end = section_span(self.body, ALLOWED_SECTION)
        return self.body[start:end]

    def test_section_exists_exactly_once(self):
        self.assertEqual(self.body.count(ALLOWED_SECTION), 1)

    def test_section_states_the_glob_and_highest_selection(self):
        sub = self._section()
        self.assertIn("iter-*-plan.md", sub)
        self.assertRegex(sub, r"(?i)highest")

    def test_section_is_resume_scoped(self):
        sub = self._section()
        self.assertRegex(sub, r"(?i)resume")

    def test_section_states_one_release(self):
        sub = self._section()
        self.assertIn("one release", sub)

    def test_section_states_fresh_run_never_writes_iteration_numbered_plan(self):
        sub = self._section()
        self.assertRegex(sub, r"(?i)fresh")
        self.assertRegex(sub, r"(?i)never")

    def test_section_reserves_plan_superseded(self):
        sub = self._section()
        self.assertIn("plan-superseded-<k>.md", sub)
        self.assertRegex(sub, r"(?i)reserved")


class NoLegacyLiteralInTriadTest(unittest.TestCase):
    """AC-3: no iter-<n>-plan.md literal survives in the code triad's own
    source outside the one read-both fallback section, bounded."""

    def test_agent_files_have_zero_legacy_literal(self):
        for path in TRIAD_AGENT_FILES:
            body = read(path)
            matches = LEGACY.findall(body)
            self.assertEqual(matches, [],
                              "%s must carry zero legacy plan literal, found %r"
                              % (path, matches))

    def test_skill_md_legacy_literal_confined_to_allowed_section_and_bounded(self):
        body = read(CODE_SKILL)
        start, end = section_span(body, ALLOWED_SECTION)
        offsets_outside = [m.start() for m in LEGACY.finditer(body)
                            if not (start <= m.start() < end)]
        self.assertEqual(offsets_outside, [],
                          "legacy plan literal found outside the allowed "
                          "section at offsets %r" % offsets_outside)
        count_inside = len(LEGACY.findall(body[start:end]))
        self.assertLessEqual(count_inside, 3,
                              "read-both section must carry at most 3 legacy "
                              "literal occurrences (loophole bound), found %d"
                              % count_inside)


class XmlPersistenceUnchangedTest(unittest.TestCase):
    """AC-4: axis (b) XML persistence and axis (c) execute/verify names are
    still present and unaffected by the .md rename."""

    def test_xml_persistence_mandate_still_present(self):
        body = read(CODE_SKILL)
        self.assertIn("<partition>/phases/code/iter-<n>-<phase>.xml", body)

    def test_axis_c_execute_and_verify_names_still_present(self):
        body = read(CODE_SKILL)
        self.assertIn("iter-<n>-execute", body)
        self.assertIn("iter-<n>-verify", body)
