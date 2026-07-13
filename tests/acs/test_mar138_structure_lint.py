"""Unit tests for the structure/section-conformance linter (`structure_lint`).

Mirrors `tests/acs/test_mermaid_diagrams.py`'s shape: unit tests for the
linter rules, then tests for the `main(argv)` CLI entry point.
"""

import contextlib
import io
import os
import shutil
import sys
import tempfile
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO_ROOT, "plugins", "acs", "hooks", "scripts"))
import structure_lint  # noqa: E402


def _write_md(content):
    fd, path = tempfile.mkstemp(suffix=".md")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(content)
    return path


class TestLintStructureRules(unittest.TestCase):
    """Unit tests for lint_structure()'s three rules."""

    def test_all_sections_present_and_non_empty_returns_no_findings(self):
        text = (
            "# Doc\n\n"
            "## Context\n"
            "Some context.\n\n"
            "## Decision\n"
            "Some decision.\n\n"
            "## Consequences\n"
            "Some consequences.\n"
        )
        findings = structure_lint.lint_structure(
            text, ["Context", "Decision", "Consequences"], ordered=True)
        self.assertEqual(findings, [])

    def test_missing_section_is_flagged(self):
        text = "## Context\nSome context.\n"
        findings = structure_lint.lint_structure(text, ["Context", "Decision"], ordered=False)
        self.assertEqual([f.rule for f in findings], ["missing-section"])

    def test_empty_section_is_flagged(self):
        # Context is immediately followed by another heading with no body;
        # Decision has real content and must not be flagged.
        text = "## Context\n## Decision\nSome decision.\n"
        findings = structure_lint.lint_structure(text, ["Context", "Decision"], ordered=False)
        self.assertEqual([f.rule for f in findings], ["empty-section"])

    def test_section_order_flagged_when_reversed_and_ordered(self):
        text = (
            "## Consequences\nSome consequences.\n\n"
            "## Decision\nSome decision.\n\n"
            "## Context\nSome context.\n"
        )
        findings = structure_lint.lint_structure(
            text, ["Context", "Decision", "Consequences"], ordered=True)
        self.assertIn("section-order", [f.rule for f in findings])

    def test_section_order_not_checked_when_not_ordered(self):
        text = (
            "## Consequences\nSome consequences.\n\n"
            "## Decision\nSome decision.\n\n"
            "## Context\nSome context.\n"
        )
        findings = structure_lint.lint_structure(
            text, ["Context", "Decision", "Consequences"], ordered=False)
        self.assertNotIn("section-order", [f.rule for f in findings])

    def test_ambiguous_duplicate_declared_section_relaxes_order_check(self):
        # "Intro" is declared twice -> ambiguous -> excluded from the order
        # check rather than false-blocking on an unresolvable comparison.
        text = "## Intro\nFirst part.\n\n## Body\nMiddle part.\n"
        findings = structure_lint.lint_structure(
            text, ["Intro", "Body", "Intro"], ordered=True)
        self.assertNotIn("section-order", [f.rule for f in findings])

    def test_ambiguous_repeated_heading_in_doc_relaxes_order_check(self):
        # "Intro" heading appears twice in the doc -> ambiguous mapping to
        # the single declared "Intro" entry -> excluded from order check.
        text = (
            "## Intro\nFirst part.\n\n"
            "## Body\nMiddle part.\n\n"
            "## Intro\nSecond part.\n"
        )
        findings = structure_lint.lint_structure(
            text, ["Intro", "Body"], ordered=True)
        self.assertNotIn("section-order", [f.rule for f in findings])


class TestSectionsDelimiterParsing(unittest.TestCase):
    """--sections is semicolon-delimited; '&' inside a name is never a delimiter."""

    def test_semicolon_split_trims_whitespace(self):
        self.assertEqual(structure_lint._parse_sections("A; B; C"), ["A", "B", "C"])

    def test_ampersand_is_not_a_delimiter(self):
        parsed = structure_lint._parse_sections(
            "Goals & success metrics; Out of scope")
        self.assertEqual(parsed, ["Goals & success metrics", "Out of scope"])


class TestFindingShapeAndAPI(unittest.TestCase):

    def test_finding_has_four_fields(self):
        self.assertEqual(
            structure_lint.Finding._fields,
            ("source", "line", "rule", "message"))

    def test_lint_structure_returns_list_of_finding_namedtuples(self):
        findings = structure_lint.lint_structure("## A\n", ["A", "B"], ordered=False)
        self.assertIsInstance(findings, list)
        self.assertTrue(all(isinstance(f, structure_lint.Finding) for f in findings))

    def test_lint_file_reads_path_and_returns_findings(self):
        path = _write_md("## Context\nSome context.\n")
        try:
            findings = structure_lint.lint_file(path, ["Context", "Decision"], ordered=False)
            self.assertEqual([f.rule for f in findings], ["missing-section"])
            self.assertEqual(findings[0].source, path)
        finally:
            os.unlink(path)


class TestMainCLI(unittest.TestCase):
    """Tests for the main(argv) CLI entry point."""

    def _run_main(self, argv):
        buf = io.StringIO()
        with contextlib.redirect_stderr(buf):
            code = structure_lint.main(argv)
        return code, buf.getvalue()

    def test_no_arguments_exits_2(self):
        code, err = self._run_main(["structure_lint.py"])
        self.assertEqual(code, 2)
        self.assertIn("usage", err.lower())

    def test_missing_sections_flag_exits_2(self):
        path = _write_md("## Context\nbody\n")
        try:
            code, err = self._run_main(["structure_lint.py", path])
            self.assertEqual(code, 2)
        finally:
            os.unlink(path)

    def test_sections_flag_with_no_value_exits_2(self):
        code, err = self._run_main(["structure_lint.py", "--sections"])
        self.assertEqual(code, 2)
        self.assertIn("usage", err.lower())

    def test_non_md_positional_exits_2(self):
        code, _ = self._run_main(
            ["structure_lint.py", "--sections", "Context", "/tmp/notes.txt"])
        self.assertEqual(code, 2)

    def test_multiple_positional_args_exits_2(self):
        code, _ = self._run_main(
            ["structure_lint.py", "--sections", "Context", "a.md", "b.md"])
        self.assertEqual(code, 2)

    def test_unreadable_nonexistent_file_exits_2(self):
        code, err = self._run_main([
            "structure_lint.py", "--sections", "Context",
            "/tmp/does_not_exist_mar138.md",
        ])
        self.assertEqual(code, 2)
        self.assertIn("error", err.lower())

    def test_directory_as_file_argument_exits_2(self):
        dirpath = tempfile.mkdtemp(suffix=".md")
        try:
            code, _ = self._run_main(
                ["structure_lint.py", "--sections", "Context", dirpath])
            self.assertEqual(code, 2)
        finally:
            shutil.rmtree(dirpath)

    def test_clean_doc_exits_0_no_stderr(self):
        path = _write_md("## Context\nSome context.\n")
        try:
            code, err = self._run_main(
                ["structure_lint.py", "--sections", "Context", path])
            self.assertEqual(code, 0)
            self.assertEqual(err, "")
        finally:
            os.unlink(path)

    def test_missing_section_doc_exits_1_with_finding(self):
        path = _write_md("## Context\nSome context.\n")
        try:
            code, err = self._run_main([
                "structure_lint.py", "--sections", "Context; Decision", path,
            ])
            self.assertEqual(code, 1)
            self.assertIn("missing-section", err)
        finally:
            os.unlink(path)

    def test_ordered_flag_enables_order_check(self):
        path = _write_md(
            "## Decision\nSome decision.\n\n## Context\nSome context.\n")
        try:
            code, err = self._run_main([
                "structure_lint.py", "--sections", "Context; Decision",
                "--ordered", path,
            ])
            self.assertEqual(code, 1)
            self.assertIn("section-order", err)
        finally:
            os.unlink(path)

    def test_without_ordered_flag_reversed_order_passes(self):
        path = _write_md(
            "## Decision\nSome decision.\n\n## Context\nSome context.\n")
        try:
            code, _ = self._run_main([
                "structure_lint.py", "--sections", "Context; Decision", path,
            ])
            self.assertEqual(code, 0)
        finally:
            os.unlink(path)

    def test_stderr_line_format_matches_source_line_rule_message(self):
        path = _write_md("## Context\nSome context.\n")
        try:
            code, err = self._run_main([
                "structure_lint.py", "--sections", "Context; Decision", path,
            ])
            self.assertEqual(code, 1)
            finding_lines = [l for l in err.splitlines() if l.startswith(path + ":")]
            self.assertTrue(finding_lines)
            self.assertRegex(finding_lines[0], r"^.+:\d+: \[[a-z-]+\] .+$")
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()
