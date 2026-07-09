"""MAR-119 spec 01 — code-verifier standards re-anchor (D3a Option A) +
code/SKILL.md `standards_path` wiring.

Prose-contract tests over `plugins/acs/agents/code-verifier.md` dimension 7
"Technical standards" (re-anchored to read `standards/` at `standards_path`,
changeset-scoped block/surface verdict, graceful degradation) and
`plugins/acs/skills/code/SKILL.md`'s settings-fields + Verify sections (which
must read and pass `standards_path` to the verifier).

Stdlib-only (os, re, unittest). Run:
  python3 -m unittest tests.acs.test_mar119_code_verifier_standards -v
"""

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


class CodeVerifierDimensionReanchorTest(unittest.TestCase):
    """AC-1: dimension 7 "Technical standards" is re-anchored to read
    standards/ at standards_path, retaining the dimension label."""

    def _agent(self):
        return read(os.path.join(PLUGIN, "agents", "code-verifier.md"))

    def _dim7_window(self):
        body = self._agent()
        m = re.search(r"(?m)^7\.\s+\*\*Technical standards\*\*.*$", body)
        self.assertIsNotNone(
            m, "code-verifier.md must have a '7. **Technical standards**' "
               "dimension item")
        # Window through the next numbered dimension item (item 8).
        nxt = re.search(r"(?m)^8\.\s+\*\*", body[m.end():])
        end = m.end() + nxt.start() if nxt else len(body)
        return body[m.start():end]

    def test_dimension_label_retained(self):
        window = self._dim7_window()
        self.assertIn(
            "Technical standards", window,
            "dimension 7 must retain the label 'Technical standards' "
            "(re-anchor-not-add constraint)")

    def test_dimension_reads_standards_dir_at_standards_path(self):
        window = self._dim7_window()
        self.assertIn("standards/", window,
                       "dimension 7 must mention reading standards/")
        self.assertIn("standards_path", window,
                       "dimension 7 must mention standards_path")

    def test_dimension_falls_back_to_documented_architecture(self):
        window = self._dim7_window()
        self.assertIn(
            "documented architecture", window,
            "unset/absent standards_path must fall back to 'documented "
            "architecture'")
        self.assertRegex(
            window, r"never a\b.*\bblock",
            "the fallback must be explicit that it is never a false block")

    def test_dimension_block_on_changeset_introduced_violation(self):
        window = self._dim7_window()
        self.assertIn('severity="blocking"', window,
                       "an introduced standards violation must be "
                       "severity=\"blocking\"")
        self.assertIn('dimension="technical standards"', window,
                       "the blocking finding must reuse "
                       "dimension=\"technical standards\"")
        self.assertRegex(
            window, r"(?is)introduc\w*.*?changeset|changeset.*?introduc\w*",
            "the blocking case must pair 'introduced' with 'changeset'")

    def test_dimension_surfaces_preexisting_as_note_not_block(self):
        window = self._dim7_window()
        self.assertIn("pre-existing", window,
                       "a pre-existing violation must be named explicitly")
        self.assertRegex(
            window, r"(?is)pre-existing.{0,400}?(note|surfaced|not.{0,20}block"
                     r"|never.{0,20}block)",
            "pre-existing violations must be distinguished from the "
            "blocking outcome (note/surfaced/not-blocking)")


class CodeVerifierInputContractTest(unittest.TestCase):
    """AC-4 code half: Input contract names standards_path when set."""

    def test_input_contract_mentions_standards_path(self):
        body = read(os.path.join(PLUGIN, "agents", "code-verifier.md"))
        window = section(body, "## Input contract")
        self.assertIn("standards_path", window,
                       "code-verifier.md Input contract must mention "
                       "standards_path")
        self.assertIn("architecture_path", window,
                       "sanity: Input contract still mentions "
                       "architecture_path")
        self.assertIn("adr_path", window,
                       "sanity: Input contract still mentions adr_path")


class CodeSkillMdWiringTest(unittest.TestCase):
    """AC-4 code half: code/SKILL.md reads and passes standards_path to the
    verifier's constraints."""

    def _skill(self):
        return read(os.path.join(PLUGIN, "skills", "code", "SKILL.md"))

    def test_settings_fields_bullet_mentions_standards_path(self):
        body = self._skill()
        window = section(body, "## Start")
        self.assertIn("standards_path", window,
                       "the Start settings-fields bullet must mention "
                       "standards_path")

    def test_verify_section_passes_standards_path_to_verifier(self):
        body = self._skill()
        window = section(body, "### Verify (per iteration) — this IS the changeset review")
        self.assertIn("standards_path", window,
                       "the Verify section must state standards_path is "
                       "passed to the verifier's constraints")


if __name__ == "__main__":
    unittest.main()
