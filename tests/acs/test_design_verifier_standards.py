"""MAR-119 spec 02 — create-design-verifier + create-design/SKILL.md
standards re-anchor.

Prose-contract tests over `plugins/acs/agents/create-design-verifier.md` and
`plugins/acs/skills/create-design/SKILL.md`: the `consistency`/`nfr`
dimensions gain a `standards` sub-check reading `standards/` at
`standards_path`, applied to the design decisions this design.md introduces,
with the same changeset-scoped block/surface + graceful-degradation rule as
the code-verifier's re-anchor (spec 01), emitting `dimension="standards"`
findings, and wired into both files' Input-contract / settings-fields
sections.

Stdlib-only (re, os, unittest). Run:
  python3 -m unittest tests.acs.test_mar119_design_verifier_standards -v
"""

import os
import re
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN = os.path.join(REPO_ROOT, "plugins", "acs")

VERIFIER = os.path.join(PLUGIN, "agents", "create-design-verifier.md")
SKILL = os.path.join(PLUGIN, "skills", "create-design", "SKILL.md")


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


def dimension_block(body, label, next_label=None):
    """Extract a numbered check-dimension list item: from the line matching
    `^\\d+. `label`` up to (not including) the next numbered item (or, when
    `next_label` is given, up to that specific item) — bounded window over a
    single dimension entry regardless of how much prose it carries."""
    start_m = re.search(r"(?m)^\d+\.\s+`%s`" % re.escape(label), body)
    assert start_m is not None, "dimension `%s` not found" % label
    rest = body[start_m.end():]
    if next_label:
        end_m = re.search(r"(?m)^\d+\.\s+`%s`" % re.escape(next_label), rest)
    else:
        end_m = re.search(r"(?m)^(?:\d+\.\s+`|Also verify)", rest)
    end = start_m.end() + end_m.start() if end_m else len(body)
    return body[start_m.start():end]


class DimensionPreambleTest(unittest.TestCase):
    """AC-3: the 'Use these exact dimension attribute values' preamble
    documents `standards` as a valid finding dimension used by the sub-check
    under dimensions 2/4 — the reader hits this note before the mismatch
    (finding dimension != check-dimension name) is otherwise confusing."""

    def test_preamble_names_standards_as_valid_dimension(self):
        body = read(VERIFIER)
        m = re.search(r"(?m)^Use these exact `dimension` attribute values:", body)
        self.assertIsNotNone(m, "preamble line not found in create-design-verifier.md")
        nxt = re.search(r"(?m)^1\.\s+`alternatives`", body[m.end():])
        self.assertIsNotNone(nxt, "numbered dimension list not found after preamble")
        window = body[m.end():m.end() + nxt.start()]
        self.assertIn("standards", window,
                       "preamble between the dimension-values line and item 1 "
                       "must note 'standards' as a valid finding dimension")


class ConsistencyDimensionStandardsCheckTest(unittest.TestCase):
    """AC-3: dimension 2 (`consistency`) is the PRIMARY anchor — full
    changeset-scoped block/surface + graceful-degradation rule lives here."""

    def _block(self):
        body = read(VERIFIER)
        return dimension_block(body, "consistency", "feasibility")

    def test_names_standards_doc_set(self):
        block = self._block()
        self.assertIn("standards/", block)
        self.assertIn("standards_path", block)

    def test_block_surface_wording(self):
        block = self._block()
        self.assertIn('severity="blocking"', block)
        self.assertIn("standards", block)
        self.assertRegex(block, r"introduc\w*",
                          "consistency block must use an 'introduc*' stem for "
                          "the changeset-introduced blocking case")
        self.assertIn("pre-existing", block)
        self.assertTrue(
            re.search(r"note|surfaced|not blocking", block, re.I),
            "consistency block must describe the pre-existing case as a "
            "note/surfaced/not-blocking outcome")

    def test_graceful_degradation_wording(self):
        block = self._block()
        self.assertIn("standards_path", block)
        self.assertTrue(
            re.search(r"N/A|unset|absent", block),
            "consistency block must cover the unset/absent standards_path case")
        self.assertTrue(
            re.search(r"never a|not a", block, re.I),
            "consistency block must negate a false block for the "
            "unset/absent case")
        self.assertIn("block", block.lower())


class NfrDimensionStandardsCheckTest(unittest.TestCase):
    """AC-3: dimension 4 (`nfr`) is the SECONDARY anchor — cross-references
    dimension 2 for the full rule but still names standards/standards_path
    itself (a bare 'see dimension 2' does not satisfy the spec)."""

    def _block(self):
        body = read(VERIFIER)
        return dimension_block(body, "nfr", "completeness")

    def test_names_standards_doc_set(self):
        block = self._block()
        self.assertIn("standards/", block)
        self.assertIn("standards_path", block)


class FindingLabelTest(unittest.TestCase):
    """AC-3: the standards sub-check's finding carries dimension="standards"
    — a deliberate exception to 'finding dimension = check-dimension name'
    (design.md:484-490)."""

    def test_dimension_standards_finding_shape_present(self):
        body = read(VERIFIER)
        self.assertIn('dimension="standards"', body)


class DimensionListRegressionTest(unittest.TestCase):
    """The re-anchor must not drop or rename an existing check dimension."""

    def test_all_five_original_dimensions_present(self):
        body = read(VERIFIER)
        for label in ("alternatives", "consistency", "feasibility", "nfr",
                      "completeness"):
            self.assertRegex(
                body, r"(?m)^\d+\.\s+`%s`" % re.escape(label),
                "dimension `%s` must remain a numbered check-dimension entry" % label)


class InputContractWiringTest(unittest.TestCase):
    """Design half of AC-4: the agent's Input contract names standards_path."""

    def test_input_contract_mentions_standards_path(self):
        body = read(VERIFIER)
        window = section(body, "## Input contract")
        self.assertIn("standards_path", window)


class SkillStartSettingsFieldsTest(unittest.TestCase):
    """Design half of AC-4: create-design/SKILL.md's Start-phase settings
    parenthetical (architecture_path/prd_path/adr_path) gains standards_path."""

    def test_settings_fields_bullet_mentions_standards_path(self):
        body = read(SKILL)
        m = re.search(r"(?m)^- Parse the printed context JSON\..*", body)
        self.assertIsNotNone(m, "Start-phase settings-fields bullet not found")
        nxt = re.search(r"(?m)^- ", body[m.end():])
        end = m.end() + nxt.start() if nxt else len(body)
        window = body[m.start():end]
        self.assertIn("architecture_path", window)
        self.assertIn("prd_path", window)
        self.assertIn("adr_path", window)
        self.assertIn("standards_path", window)


class SkillVerifyPhaseWiringTest(unittest.TestCase):
    """Design half of AC-4: verify-phase section extends consistency/nfr
    bullets with the standards sub-check and states standards_path is passed
    into the verify <task>'s <constraints> when set."""

    def _window(self):
        body = read(SKILL)
        return section(body, "### Phase: verify —")

    def test_standards_path_present(self):
        window = self._window()
        self.assertIn("standards_path", window)

    def test_standards_mentioned_alongside_consistency_and_nfr(self):
        window = self._window()
        self.assertIn("standards", window)
        self.assertIn("consistency", window)
        self.assertIn("nfr", window)

    def test_conditional_pass_when_set_wording(self):
        window = self._window()
        self.assertTrue(
            re.search(r"when set|present only when set|configured", window, re.I),
            "verify-phase section must state standards_path is passed "
            "conditionally, mirroring the other conditional constraints")

    def test_dimension_list_not_regressed(self):
        window = self._window()
        for label in ("`alternatives`", "`consistency`", "`feasibility`",
                      "`nfr`", "`completeness`"):
            self.assertIn(label, window)


if __name__ == "__main__":
    unittest.main()
