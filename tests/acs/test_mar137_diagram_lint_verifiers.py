"""MAR-137 spec 02 — wire the diagram-lint gate into the two verifiers.

Prose-contract tests over `plugins/acs/agents/create-architecture-verifier.md`
(dimension `mermaid-diagrams`) and `plugins/acs/agents/create-design-verifier.md`
(dimension `completeness`): both dimensions must invoke the Spec-01-promoted
`mermaid_lint.py` helper via `${CLAUDE_PLUGIN_ROOT}/hooks/scripts/mermaid_lint.py`
and map any finding to `severity="blocking"`, replacing the old soft/LLM-judgment
checks, with no `tests/`-path hardcode and no regression to any neighboring
check-dimension (surgical-edit proof, since sibling MAR-138 touches the same
two files next).

Mirrors the reading/extraction helpers from
`test_mar119_design_verifier_standards.py:28-60` (`read`, `dimension_block`).

GOTCHA (plan Risk R-D): the mar119 `dimension_block` helper matches ONLY
backtick-wrapped labels (`` `label` ``) — that is enough for the design
verifier (its dimensions are backtick-wrapped), but the ARCHITECTURE
verifier's dimensions are **bold**-wrapped (e.g. `4. **mermaid-diagrams**`).
A naive copy of the mar119 regex would silently fail to locate the arch
dimension (a false red/green). `dimension_block` below accepts BOTH
`**label**` and `` `label` `` for exactly this reason.

Stdlib-only (re, os, unittest). Run:
  python3 -m unittest tests.acs.test_mar137_diagram_lint_verifiers -v
"""

import os
import re
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN = os.path.join(REPO_ROOT, "plugins", "acs")

ARCH_VERIFIER = os.path.join(PLUGIN, "agents", "create-architecture-verifier.md")
DESIGN_VERIFIER = os.path.join(PLUGIN, "agents", "create-design-verifier.md")

HELPER_PATH = "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/mermaid_lint.py"

ARCH_DIMENSIONS = (
    "doc-set-completeness", "prd-coverage", "codebase-match", "mermaid-diagrams",
    "internal-consistency", "diagram-prose-agreement", "hld-lld-consistency",
    "plan-conformance", "docs-only-changeset",
)
DESIGN_DIMENSIONS = ("alternatives", "consistency", "feasibility", "nfr", "completeness")


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _label_pattern(label):
    """A numbered check-dimension label, bold- or backtick-wrapped (see the
    module docstring's bold-vs-backtick gotcha)."""
    return r"(?:\*\*%s\*\*|`%s`)" % (re.escape(label), re.escape(label))


def dimension_block(body, label, next_label=None):
    """Extract a numbered check-dimension list item: from the line matching
    `^\\d+. **label**` or `^\\d+. `label`` up to (not including) the next
    numbered item (or, when `next_label` is given, up to that specific item).
    Bounded window over a single dimension entry regardless of how much prose
    it carries."""
    start_m = re.search(r"(?m)^\d+\.\s+%s" % _label_pattern(label), body)
    assert start_m is not None, "dimension %r not found" % label
    rest = body[start_m.end():]
    if next_label:
        end_m = re.search(r"(?m)^\d+\.\s+%s" % _label_pattern(next_label), rest)
    else:
        end_m = re.search(r"(?m)^(?:\d+\.\s+(?:\*\*|`)|Also verify)", rest)
    end = start_m.end() + end_m.start() if end_m else len(body)
    return body[start_m.start():end]


def dimension_present(body, label):
    """True if `label` is a numbered check-dimension entry (bold or
    backtick-wrapped)."""
    return re.search(r"(?m)^\d+\.\s+%s" % _label_pattern(label), body) is not None


class ArchitectureMermaidDiagramsDimensionTest(unittest.TestCase):
    """AC-2: create-architecture-verifier.md dimension 4 (mermaid-diagrams)
    invokes the promoted helper as a blocking gate, replacing the old
    mmdc-render-or-grep clause."""

    def _block(self):
        body = read(ARCH_VERIFIER)
        return dimension_block(body, "mermaid-diagrams", "internal-consistency")

    def test_invokes_promoted_helper(self):
        self.assertIn(HELPER_PATH, self._block())

    def test_any_finding_is_blocking(self):
        self.assertIn('severity="blocking"', self._block())

    def test_no_tests_path_hardcode_anywhere_in_file(self):
        # AC-4: not just the dimension block — a stray tests/ reference
        # anywhere else in the file would equally break consumer-generality.
        body = read(ARCH_VERIFIER)
        self.assertNotIn("tests/", body)

    def test_old_mmdc_grep_clause_removed(self):
        block = self._block()
        self.assertNotIn("mmdc", block)
        self.assertNotIn("grep for the common", block)


class DesignCompletenessDiagramSubCheckTest(unittest.TestCase):
    """AC-3: create-design-verifier.md dimension 5 (completeness) diagram
    sub-clause invokes the promoted helper as a blocking gate, replacing the
    old 'syntactically plausible' LLM-judgment clause. The dimension label
    stays `completeness` — no new numbered dimension."""

    def _block(self):
        body = read(DESIGN_VERIFIER)
        return dimension_block(body, "completeness")

    def test_invokes_promoted_helper(self):
        self.assertIn(HELPER_PATH, self._block())

    def test_any_finding_is_blocking(self):
        self.assertIn('severity="blocking"', self._block())

    def test_no_tests_path_hardcode_anywhere_in_file(self):
        body = read(DESIGN_VERIFIER)
        self.assertNotIn("tests/", body)

    def test_old_syntactically_plausible_clause_removed(self):
        self.assertNotIn("syntactically plausible", self._block())

    def test_other_completeness_subchecks_preserved_byte_for_byte(self):
        # These sub-checks are unrelated to the diagram-syntax clause and
        # must survive the surgical edit untouched.
        block = self._block()
        self.assertIn("all six required sections present and substantive", block)
        self.assertIn(
            "A Mermaid `sequenceDiagram` exists for EVERY new\n"
            "   or changed runtime flow named by the ticket and plan",
            block,
        )
        self.assertIn("an ER diagram exists", block)
        self.assertIn("when the data model changes", block)
        self.assertIn("`### Decision records` is", block)
        self.assertIn(
            "present if and only if the task constraints say `adr_path` is configured.",
            block,
        )


class DimensionListRegressionTest(unittest.TestCase):
    """Surgical-edit proof: neither rewrite drops, renames, or renumbers a
    neighboring check dimension (protects sibling MAR-138's rebase surface)."""

    def test_all_nine_architecture_dimensions_present(self):
        body = read(ARCH_VERIFIER)
        for label in ARCH_DIMENSIONS:
            self.assertTrue(
                dimension_present(body, label),
                "dimension %r must remain a numbered check-dimension entry" % label)

    def test_all_five_design_dimensions_present(self):
        body = read(DESIGN_VERIFIER)
        for label in DESIGN_DIMENSIONS:
            self.assertTrue(
                dimension_present(body, label),
                "dimension %r must remain a numbered check-dimension entry" % label)


if __name__ == "__main__":
    unittest.main()
