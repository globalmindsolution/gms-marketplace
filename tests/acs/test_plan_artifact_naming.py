"""MAR-70 — /acs:code's plan artifact renamed to plan.md, with axis (b)/(c)
protection. MAR-73 retired the resume-only read-both compat fallback MAR-70
introduced: `plan.md` is now unconditionally the only name ever read or
written for the plan artifact, so this module no longer tests for (or
bounds) any legacy-literal carve-out — zero `iter-<n>-plan.md` /
`iter-*-plan.md` literal occurrences are expected anywhere in code/SKILL.md
or its two agent files. The plan phase itself moved to
/acs:create-impl-plan, which publishes the artifact; its Publish section is
pinned here for the same naming rule.

Three naming axes touch these files: (a) the plan artifact itself (`.md`,
renamed by MAR-70, fallback retired by MAR-73), (b) per-iteration XML
message persistence (`iter-<n>-<phase>.xml`, unchanged), (c) execute/verify
phase artifacts (`iter-<n>-execute*.json` / `iter-<n>-verify*.md`,
unchanged). This module asserts axis (a) moved (and its fallback is gone)
and axes (b)/(c) did not.

Stdlib-only (os, re, unittest). Run:
  python3 -m unittest tests.acs.test_plan_artifact_naming -v
"""

import glob
import os
import re
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN = os.path.join(REPO_ROOT, "src", "acs")
AGENTS_DIR = os.path.join(PLUGIN, "agents")

CODE_SKILL = os.path.join(PLUGIN, "skills", "code", "SKILL.md")
CODE_EXECUTOR = os.path.join(AGENTS_DIR, "code-executor.md")
IMPL_PLAN_SKILL = os.path.join(PLUGIN, "skills", "create-impl-plan", "SKILL.md")

# The plan phase left /acs:code for /acs:create-impl-plan, so the code side is
# a dyad: the executor and the verifier READ the plan the other skill wrote.
TRIAD_AGENT_FILES = [CODE_EXECUTOR,]

# .md-anchored only — iter-<n>-plan.xml (axis b) must NOT match this literal.
LEGACY = re.compile(r"iter-(?:<n>|\{n\}|\*|\d+)-plan\.md")


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def code_contract():
    """/acs:code's contract as one text: the dispatcher, the four delivery-path
    legs, and the references they share.

    ADR-0095 split one body across these files. Every assertion below is about
    what the SKILL SAYS, never which of its files says it, so reading the
    concatenation keeps the pin honest while the layout stays free to change —
    and a naming rule that genuinely vanishes still fails."""
    skills = os.path.join(PLUGIN, "skills")
    parts = []
    for name in ("code", "code-trivial", "code-small", "code-standard",
                 "code-complex"):
        path = os.path.join(skills, name, "SKILL.md")
        if os.path.isfile(path):
            parts.append(read(path))
    for path in sorted(glob.glob(os.path.join(skills, "code", "references",
                                              "*.md"))):
        parts.append(read(path))
    return "\n".join(parts)


def code_contract_files():
    skills = os.path.join(PLUGIN, "skills")
    paths = [os.path.join(skills, name, "SKILL.md")
             for name in ("code", "code-trivial", "code-small",
                          "code-standard", "code-complex")]
    paths += sorted(glob.glob(os.path.join(skills, "code", "references",
                                           "*.md")))
    return [p for p in paths if os.path.isfile(p)]


def section_span(body, heading):
    """Char offsets (start, end) of the section at `heading`, up to the next
    level-1/2/3 heading or end of file."""
    start = body.index(heading)
    rest = body[start + len(heading):]
    m = re.search(r"\n#{1,3} ", rest)
    end = start + len(heading) + (m.start() if m else len(rest))
    return start, end


class FreshRunNamingTest(unittest.TestCase):
    """AC-1: plan.md is the artifact name on a fresh run.

    There is ONE plan, at `steps/create-impl-plan/plan.md` -- the skill that
    wrote it keeps it, and everything else reads it there. The approval mirror
    at `steps/code/plan.md` is gone with the two-path resolution that needed
    it (§6): a copy that can differ from its original is exactly the drift the
    mirror was invented to detect."""

    def test_plan_md_is_named_at_its_one_path(self):
        for label, body in [("the /acs:code contract", code_contract())] + [
                (path, read(path)) for path in TRIAD_AGENT_FILES]:
            with self.subTest(source=label):
                self.assertIn("plan.md", body)
                self.assertNotIn("phases/code/plan.md", body)

    def test_publishing_skill_names_plan_md_with_no_legacy_literal(self):
        body = read(IMPL_PLAN_SKILL)
        start, end = section_span(body, "### Publish")
        section = body[start:end]
        self.assertIn("plan.md", section)
        self.assertEqual(LEGACY.findall(section), [],
                          "create-impl-plan/SKILL.md's Publish section must "
                          "name no legacy plan literal")


class NoLegacyLiteralInTriadTest(unittest.TestCase):
    """AC-3 (post-MAR-73): zero iter-<n>-plan.md legacy literal survives
    anywhere in the code skill and its agents' own source — the MAR-70 read-both fallback
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
        for path in code_contract_files():
            matches = LEGACY.findall(read(path))
            self.assertEqual(matches, [],
                              "%s must carry zero legacy plan literal now that "
                              "the MAR-70 read-both fallback is retired, found "
                              "%r" % (path, matches))


class PhaseArtifactPersistenceTest(unittest.TestCase):
    """The mandate survives the layout change: every phase output is persisted
    at its boundary, BEFORE the next phase starts.

    What changed is where and in what. The iteration is a DIRECTORY now --
    `steps/<skill>/iter-<n>/` -- rather than a filename prefix, and the
    snapshots are JSON: the XSD and its second validator are gone (§6). The
    rule is the same rule; only the path and the format moved."""

    def test_the_persistence_mandate_still_present(self):
        body = code_contract()
        self.assertIn("steps/code/iter-<n>/", body)
        self.assertRegex(body, r"(?i)BEFORE starting the next phase")

    def test_the_prefix_scheme_is_gone(self):
        """`iter-<n>-execute.json` and its siblings sorted lexically, which is
        how `iter-1-execute-superseded-1.json` came to be "the current one"."""
        body = code_contract()
        self.assertNotIn("iter-<n>-execute", body)
        self.assertNotIn("iter-<n>-verify", body)
        self.assertNotIn(".xml", body)
