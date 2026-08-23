"""MAR-70 — /acs:code's plan artifact renamed to plan.md, with axis (b)/(c)
protection. MAR-73 retired the resume-only read-both compat fallback MAR-70
introduced: `plan.md` is now unconditionally the only name ever read or
written for the plan artifact, so this module no longer tests for (or
bounds) any legacy-literal carve-out — zero `iter-<n>-plan.md` /
`iter-*-plan.md` literal occurrences are expected anywhere in the code
triad's own SKILL.md/agent files.

Three naming axes touch these files: (a) the plan artifact itself (`.md`,
renamed by MAR-70, fallback retired by MAR-73), (b) per-iteration XML
message persistence (`iter-<n>-<phase>.xml`, unchanged), (c) execute/verify
phase artifacts (`iter-<n>-execute*.json` / `iter-<n>-verify*.md`,
unchanged). This module asserts axis (a) moved (and its fallback is gone)
and axes (b)/(c) did not.

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


class NoLegacyLiteralInTriadTest(unittest.TestCase):
    """AC-3 (post-MAR-73): zero iter-<n>-plan.md legacy literal survives
    anywhere in the code triad's own source — the MAR-70 read-both fallback
    section that used to carve out a bounded exception is retired, so there
    is no allowance left for any occurrence, in any file."""

    def test_agent_files_have_zero_legacy_literal(self):
        for path in TRIAD_AGENT_FILES:
            body = read(path)
            matches = LEGACY.findall(body)
            self.assertEqual(matches, [],
                              "%s must carry zero legacy plan literal, found %r"
                              % (path, matches))

    def test_skill_md_has_zero_legacy_literal(self):
        body = read(CODE_SKILL)
        matches = LEGACY.findall(body)
        self.assertEqual(matches, [],
                          "%s must carry zero legacy plan literal now that "
                          "the MAR-70 read-both fallback is retired, found %r"
                          % (CODE_SKILL, matches))


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
