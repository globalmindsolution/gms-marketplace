"""front_matter_check.py — the deterministic backstop for a doc's front matter.

`structure_lint.py` checks a generated doc's SECTIONS; this checks the
machine-read half. It exists because `analysis.md`'s `api_surface` decides
whether `/acs:create-api-contract` runs at all (`workflows/ship.yaml`'s
`api_surface_changed` predicate and the create-api-contract gate both read it),
so a missing key, a string where a boolean belongs, or a block outside the YAML
subset is a pipeline defect that would otherwise surface one skill too late.

The parse is `acs_lib.yamlsubset` — the same parser the gate uses — so these
tests also pin the promise that a draft this checker accepts cannot be rejected
downstream for its front matter.

Run:  python3 -m unittest tests.acs.test_front_matter_check -v
"""

import contextlib
import io
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN = os.path.join(REPO_ROOT, "plugins", "acs")
HOOKS = os.path.join(PLUGIN, "hooks", "scripts")
SCRIPT = os.path.join(HOOKS, "front_matter_check.py")

sys.path.insert(0, HOOKS)

import front_matter_check as fmc  # noqa: E402

ANALYSIS_SPEC = ("ticket: str; ready_for_planning: bool; api_surface: bool; "
                 "stakes_recommendation: normal|high; needs_design_recommendation: bool")

GOOD_ANALYSIS = """---
ticket: SHOP-123
ready_for_planning: true
api_surface: false
stakes_recommendation: high
needs_design_recommendation: false
---

# Analysis — SHOP-123

## Verdict
Ready.
"""


def rules(findings):
    return [f.rule for f in findings]


class TestParseSpec(unittest.TestCase):

    def test_pairs_are_split_and_stripped(self):
        self.assertEqual(fmc.parse_spec(" ticket: str ; items: int "),
                         [("ticket", "str"), ("items", "int")])

    def test_a_value_set_is_kept_verbatim(self):
        self.assertEqual(fmc.parse_spec("stakes: normal|high"),
                         [("stakes", "normal|high")])

    def test_trailing_separator_is_tolerated(self):
        self.assertEqual(fmc.parse_spec("ticket: str;"), [("ticket", "str")])

    def test_a_malformed_entry_raises_rather_than_checking_nothing(self):
        for raw in ("ticket", "ticket:", ": str", ""):
            with self.subTest(raw=raw):
                with self.assertRaises(ValueError):
                    fmc.parse_spec(raw)


class TestCheckFrontMatter(unittest.TestCase):

    def check(self, text, spec=ANALYSIS_SPEC, ticket=None):
        return fmc.check_front_matter(text, fmc.parse_spec(spec), ticket=ticket)

    def test_a_conforming_block_has_no_findings(self):
        self.assertEqual(self.check(GOOD_ANALYSIS, ticket="SHOP-123"), [])

    def test_a_doc_with_no_block_is_one_finding(self):
        findings = self.check("# Analysis\n\nno front matter here\n")
        self.assertEqual(rules(findings), ["front-matter-missing"])
        self.assertEqual(findings[0].line, 1)

    def test_a_block_outside_the_subset_reports_the_parser_line(self):
        text = "---\nticket: SHOP-1\n\tapi_surface: true\n---\n\nbody\n"
        findings = self.check(text)
        self.assertEqual(rules(findings), ["front-matter-unparseable"])
        self.assertEqual(findings[0].line, 3)

    def test_a_missing_key_is_reported_per_key(self):
        text = "---\nticket: SHOP-1\n---\n\nbody\n"
        findings = self.check(text)
        self.assertEqual(rules(findings), ["missing-key"] * 4)
        self.assertIn("ready_for_planning", findings[0].message)

    def test_an_explicit_null_counts_as_missing(self):
        text = GOOD_ANALYSIS.replace("api_surface: false", "api_surface: null")
        self.assertEqual(rules(self.check(text)), ["missing-key"])

    def test_a_string_where_a_boolean_belongs_is_wrong_type(self):
        text = GOOD_ANALYSIS.replace("api_surface: false", 'api_surface: "false"')
        findings = self.check(text)
        self.assertEqual(rules(findings), ["wrong-type"])
        self.assertIn("api_surface", findings[0].message)

    def test_a_boolean_is_not_an_integer(self):
        """`items: true` must not pass an `int` declaration — bool is an int in
        Python, and a count that is a boolean is a real authoring defect."""
        text = "---\nticket: SHOP-1\nitems: true\n---\n\nbody\n"
        findings = self.check(text, spec="ticket: str; items: int")
        self.assertEqual(rules(findings), ["wrong-type"])

    def test_an_integer_and_a_list_pass_their_declarations(self):
        text = '---\nticket: SHOP-1\nitems: 3\ncontract_files: ["docs/api/openapi.yaml"]\n---\n\nbody\n'
        self.assertEqual(self.check(text, spec="ticket: str; items: int; contract_files: list"), [])

    def test_an_empty_list_still_satisfies_list(self):
        text = "---\nticket: SHOP-1\ncontract_files: []\n---\n\nbody\n"
        self.assertEqual(self.check(text, spec="ticket: str; contract_files: list"), [])

    def test_an_empty_string_does_not_satisfy_str(self):
        text = '---\nticket: ""\n---\n\nbody\n'
        self.assertEqual(rules(self.check(text, spec="ticket: str")), ["wrong-type"])

    def test_a_value_outside_the_declared_set_is_bad_value(self):
        text = GOOD_ANALYSIS.replace("stakes_recommendation: high",
                                     "stakes_recommendation: critical")
        findings = self.check(text)
        self.assertEqual(rules(findings), ["bad-value"])
        self.assertIn("normal, high", findings[0].message)

    def test_any_accepts_whatever_is_present(self):
        text = "---\nticket: SHOP-1\nnote: 7\n---\n\nbody\n"
        self.assertEqual(self.check(text, spec="note: any"), [])

    def test_a_mismatched_ticket_is_its_own_finding(self):
        findings = self.check(GOOD_ANALYSIS, ticket="SHOP-999")
        self.assertEqual(rules(findings), ["ticket-mismatch"])
        self.assertIn("SHOP-123", findings[0].message)

    def test_the_ticket_check_is_skipped_when_no_id_is_given(self):
        self.assertEqual(self.check(GOOD_ANALYSIS), [])

    def test_findings_carry_the_source_name(self):
        findings = fmc.check_front_matter("# no block\n", fmc.parse_spec("ticket: str"),
                                          source="analysis.md")
        self.assertEqual(findings[0].source, "analysis.md")


class TestCheckFile(unittest.TestCase):

    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="acs-fmc-")
        self.addCleanup(shutil.rmtree, self.dir, True)

    def write(self, text, name="doc.md"):
        path = os.path.join(self.dir, name)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        return path

    def test_check_file_reads_and_reports_the_path(self):
        path = self.write(GOOD_ANALYSIS.replace("ticket: SHOP-123", "ticket: SHOP-9"))
        findings = fmc.check_file(path, fmc.parse_spec(ANALYSIS_SPEC), ticket="SHOP-123")
        self.assertEqual(rules(findings), ["ticket-mismatch"])
        self.assertEqual(findings[0].source, path)

    def test_a_conforming_file_is_clean(self):
        path = self.write(GOOD_ANALYSIS)
        self.assertEqual(fmc.check_file(path, fmc.parse_spec(ANALYSIS_SPEC),
                                        ticket="SHOP-123"), [])


class TestCli(unittest.TestCase):
    """The interface the skills actually call: exit 0 clean, 1 findings, 2 misuse."""

    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="acs-fmc-cli-")
        self.addCleanup(shutil.rmtree, self.dir, True)

    def doc(self, text, name="doc.md"):
        path = os.path.join(self.dir, name)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        return path

    def run_cli(self, *args):
        return subprocess.run([sys.executable, SCRIPT] + list(args),
                              capture_output=True, text=True)

    def test_clean_doc_exits_zero_and_says_nothing(self):
        out = self.run_cli("--require", ANALYSIS_SPEC, "--ticket", "SHOP-123",
                           self.doc(GOOD_ANALYSIS))
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(out.stderr, "")
        self.assertEqual(out.stdout, "")

    def test_findings_exit_one_and_print_rule_and_key(self):
        path = self.doc(GOOD_ANALYSIS.replace("api_surface: false", "api_surface: nope"))
        out = self.run_cli("--require", ANALYSIS_SPEC, path)
        self.assertEqual(out.returncode, 1)
        self.assertIn("[wrong-type]", out.stderr)
        self.assertIn("api_surface", out.stderr)
        self.assertIn("1 front-matter finding(s).", out.stderr)

    def test_missing_require_is_usage(self):
        out = self.run_cli(self.doc(GOOD_ANALYSIS))
        self.assertEqual(out.returncode, 2)
        self.assertIn("usage:", out.stderr)

    def test_a_dangling_flag_is_usage(self):
        out = self.run_cli("--require")
        self.assertEqual(out.returncode, 2)
        self.assertIn("usage:", out.stderr)

    def test_a_non_markdown_target_is_usage(self):
        out = self.run_cli("--require", "ticket: str", os.path.join(self.dir, "doc.txt"))
        self.assertEqual(out.returncode, 2)
        self.assertIn("usage:", out.stderr)

    def test_a_malformed_require_spec_is_rejected_not_silently_empty(self):
        out = self.run_cli("--require", "ticket", self.doc(GOOD_ANALYSIS))
        self.assertEqual(out.returncode, 2)
        self.assertIn("malformed", out.stderr)

    def test_an_unreadable_doc_is_exit_two(self):
        out = self.run_cli("--require", "ticket: str",
                           os.path.join(self.dir, "absent.md"))
        self.assertEqual(out.returncode, 2)
        self.assertIn("error reading", out.stderr)


class TestMainDirectly(unittest.TestCase):
    """main() is the covered path; the CLI tests above prove the wiring."""

    def test_main_returns_the_exit_code(self):
        directory = tempfile.mkdtemp(prefix="acs-fmc-main-")
        self.addCleanup(shutil.rmtree, directory, True)
        path = os.path.join(directory, "doc.md")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(GOOD_ANALYSIS)
        errors = io.StringIO()
        with contextlib.redirect_stderr(errors):
            clean = fmc.main(["front_matter_check.py", "--require", ANALYSIS_SPEC,
                              "--ticket", "SHOP-123", path])
            mismatched = fmc.main(["front_matter_check.py", "--require", ANALYSIS_SPEC,
                                   "--ticket", "OTHER-1", path])
        self.assertEqual(clean, 0)
        self.assertEqual(mismatched, 1)
        self.assertIn("ticket-mismatch", errors.getvalue())

    def test_main_reports_misuse_in_process_too(self):
        """Each exit-2 arm, called directly: a dangling flag, no --require, a
        malformed spec, and a document that cannot be read."""
        directory = tempfile.mkdtemp(prefix="acs-fmc-misuse-")
        self.addCleanup(shutil.rmtree, directory, True)
        absent = os.path.join(directory, "absent.md")
        cases = [
            (["--require"], "usage:"),
            ([os.path.join(directory, "doc.md")], "usage:"),
            (["--require", "ticket", absent], "malformed"),
            (["--require", "ticket: str", absent], "error reading"),
        ]
        for argv, expected in cases:
            with self.subTest(argv=argv):
                errors = io.StringIO()
                with contextlib.redirect_stderr(errors):
                    code = fmc.main(["front_matter_check.py"] + argv)
                self.assertEqual(code, 2)
                self.assertIn(expected, errors.getvalue())


if __name__ == "__main__":
    unittest.main()
