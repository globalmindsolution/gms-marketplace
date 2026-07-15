"""MAR-144 spec 01 — /acs:create-requirements greenfield elicitation mode,
3-way mode classifier, uniform DRAFT/interactive-confirm discipline, and the
finalized per-file format (AC-1..AC-4, AC-6 prose half).

Prose-contract tests (string/regex over the coordinator + triad bodies, no
execution of the skill) proving the deferred greenfield stub is now a real
elicitation mode across SKILL.md + planner/executor/verifier, that greenfield
is a distinct third classifier branch (not a brownfield fallthrough), that the
DRAFT/confirm gate spans all three modes uniformly (C-22), that the per-file
format is finalized, and that the new greenfield write prose uses
settings-resolved layout placeholders rather than hardcoded marketplace literals
(C-20). Mirrors the read()+assert style of
test_mar143_create_requirements_skill.py.

Stdlib-only (os, re, unittest). Run:
  python3 -m unittest tests.acs.test_mar144_greenfield_amend_modes -v
"""

import os
import re
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN = os.path.join(REPO_ROOT, "plugins", "acs")
SKILL_PATH = os.path.join(PLUGIN, "skills", "create-requirements", "SKILL.md")
PLANNER_PATH = os.path.join(PLUGIN, "agents", "create-requirements-planner.md")
EXECUTOR_PATH = os.path.join(PLUGIN, "agents", "create-requirements-executor.md")
VERIFIER_PATH = os.path.join(PLUGIN, "agents", "create-requirements-verifier.md")

GF_MARK = re.compile(r"(?i)\*\*greenfield\*\*")


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def gf_regions(body, radius):
    """Windows anchored at each bold **greenfield** mode marker — the mode
    bullets, excluding plain inline mentions in examples/prose."""
    return [body[m.start(): m.start() + radius] for m in GF_MARK.finditer(body)]


class Mar144GreenfieldRealCase(unittest.TestCase):
    """AC-1: greenfield is a real elicitation mode, not a deferral."""

    @classmethod
    def setUpClass(cls):
        cls.skill = read(SKILL_PATH)
        cls.planner = read(PLANNER_PATH)
        cls.executor = read(EXECUTOR_PATH)

    def test_greenfield_not_deferred(self):
        # No residual deferral language in the coordinator/planner/executor bodies.
        for name, body in (
            ("SKILL.md", self.skill),
            ("planner.md", self.planner),
            ("executor.md", self.executor),
        ):
            self.assertNotIn(
                "MAR-144", body,
                "%s still names MAR-144 as a greenfield deferral target" % name)
            self.assertNotRegex(
                body, r"(?is)greenfield.{0,200}deferred",
                "%s still describes greenfield as deferred" % name)
            self.assertNotRegex(
                body, r"(?is)deferred.{0,200}greenfield",
                "%s still describes greenfield as deferred" % name)

    def test_greenfield_elicits_and_authors_files(self):
        # Each body's greenfield mode bullet elicits from the user and names the
        # settings-resolved functional/non-functional target files.
        for name, body in (
            ("SKILL.md", self.skill),
            ("planner.md", self.planner),
            ("executor.md", self.executor),
        ):
            regions = gf_regions(body, 500)
            self.assertTrue(regions, "%s has no bold greenfield mode bullet" % name)
            joined = "\n".join(regions)
            self.assertRegex(
                joined, r"(?i)elicit",
                "%s greenfield bullet does not state it elicits" % name)
            self.assertIn(
                "<functional_subdir>", joined,
                "%s greenfield bullet does not name the functional target" % name)
            self.assertIn(
                "<non_functional_subdir>", joined,
                "%s greenfield bullet does not name the non-functional target" % name)

    def test_greenfield_draft_marked(self):
        # The executor greenfield branch states the DRAFT marker applies here too.
        region = "\n".join(gf_regions(self.executor, 400))
        self.assertIn(
            "DRAFT", region,
            "executor greenfield branch must mark its output DRAFT")


class Mar144ThreeWayClassifierCase(unittest.TestCase):
    """AC-2: brownfield/greenfield/amend are three distinct classifier branches;
    greenfield is not a brownfield fallthrough; the amend byte-for-byte contract
    survives this spec's edits."""

    @classmethod
    def setUpClass(cls):
        cls.skill = read(SKILL_PATH)
        cls.planner = read(PLANNER_PATH)
        cls.executor = read(EXECUTOR_PATH)

    def test_three_way_classifier_present(self):
        for name, body in (("SKILL.md", self.skill), ("planner.md", self.planner)):
            for mode in ("brownfield", "greenfield", "amend"):
                self.assertRegex(
                    body, r"(?i)\*\*%s\*\*" % mode,
                    "%s must name **%s** as a distinct mode branch" % (name, mode))
            # greenfield carries its own elicitation behavior — not a fallthrough.
            self.assertRegex(
                "\n".join(gf_regions(body, 500)), r"(?i)elicit",
                "%s greenfield must be a distinct elicit branch" % name)

    def test_amend_byte_for_byte_preserved(self):
        # Regression guard: the amend git-diff self-check + byte preservation text
        # is untouched by the greenfield edits.
        self.assertIn("byte-for-byte", self.executor)
        self.assertIn("git diff -- <requirements_path>", self.executor)
        self.assertIn("byte-identical", self.skill)


class Mar144UniformDraftConfirmCase(unittest.TestCase):
    """AC-3: the DRAFT / interactive-confirm discipline is uniform across all
    three modes (C-22 human gate)."""

    @classmethod
    def setUpClass(cls):
        cls.skill = read(SKILL_PATH)

    def test_draft_confirm_present_all_three_modes(self):
        for mode in ("greenfield", "brownfield", "amend"):
            idxs = [m.start() for m in re.finditer(r"(?i)\*\*%s\*\*" % mode, self.skill)]
            self.assertTrue(idxs, "SKILL.md must name mode %r" % mode)
            joined = "\n".join(self.skill[max(0, i - 60): i + 500] for i in idxs)
            self.assertRegex(
                joined, r"(?i)draft|confirm",
                "SKILL.md %r neighborhood lacks DRAFT/confirm language" % mode)

    def test_nothing_authoritative_without_confirm(self):
        # Whitespace-tolerant: the uniformity sentence is hard-wrapped prose.
        self.assertRegex(self.skill, r"uniformly to all three\s+modes")
        self.assertIn("human gate", self.skill)
        self.assertIn("C-22", self.skill)


class Mar144FormatAndG36Case(unittest.TestCase):
    """AC-4: the per-file format is finalized and the G36 self-declaration is
    still intact."""

    @classmethod
    def setUpClass(cls):
        cls.skill = read(SKILL_PATH)

    def test_required_sections_and_audience_profile_still_declared(self):
        self.assertIn("required_sections", self.skill)
        self.assertIn("engineers (behavioral-contract prose)", self.skill)

    def test_per_file_format_specified(self):
        i = self.skill.find("Per-file format")
        self.assertNotEqual(i, -1, "SKILL.md lacks the finalized per-file format subsection")
        block = self.skill[i: i + 700]
        self.assertIn("<functional_subdir>/<feature>.md", block)
        self.assertIn("<non_functional_subdir>/<item>.md", block)
        self.assertIn("DRAFT", block)
        for token in ("MUST", "SHOULD", "MAY", "[OPEN]", "[ASSUMPTION]"):
            self.assertIn(token, block, "format subsection missing %r vocab" % token)


class Mar144VerifierModeAwareCase(unittest.TestCase):
    """AC-1/AC-2: the verifier's mode-conformance + coverage/citation/no-fabrication
    dimensions are greenfield-aware (branch text, NOT new dimensions — count stays 13)."""

    @classmethod
    def setUpClass(cls):
        cls.verifier = read(VERIFIER_PATH)

    def test_verifier_greenfield_mode_aware(self):
        self.assertNotRegex(
            self.verifier, r"(?is)greenfield.{0,120}deferred",
            "verifier still treats greenfield as deferred")
        # Dimension 2 now describes greenfield as producing elicited files.
        self.assertRegex(
            self.verifier, r"(?is)greenfield produced.{0,200}(elicited|DRAFT)",
            "verifier dim 2 must describe greenfield as producing elicited DRAFT files")

    def test_verifier_dimension_count_still_13(self):
        self.assertIn("13. **audience-style", self.verifier)
        self.assertIsNone(
            re.search(r"(?m)^14\.\s", self.verifier),
            "a 14th verifier dimension was added — the count must stay 13")


class Mar144ConsumerGeneralCase(unittest.TestCase):
    """AC-6 (prose half): the new greenfield write prose uses settings-resolved
    layout placeholders, never hardcoded marketplace path literals (C-20)."""

    def test_greenfield_uses_settings_resolved_paths(self):
        for name, path in (
            ("SKILL.md", SKILL_PATH),
            ("planner.md", PLANNER_PATH),
            ("executor.md", EXECUTOR_PATH),
        ):
            body = read(path)
            for region in gf_regions(body, 300):
                self.assertIn(
                    "<functional_subdir>", region,
                    "%s greenfield prose must use the <functional_subdir> "
                    "placeholder, not a literal" % name)
                self.assertNotIn(
                    "docs/requirements", region,
                    "%s greenfield prose hardcodes docs/requirements (C-20)" % name)
                self.assertNotIn(
                    "functional/", region,
                    "%s greenfield prose hardcodes a functional/ path literal "
                    "instead of <functional_subdir>/ (C-20)" % name)


if __name__ == "__main__":
    unittest.main()
