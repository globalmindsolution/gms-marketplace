"""Unit tests for the PR-convention helper CLI (MAR-72 spec 01).

plugins/acs/hooks/scripts/pr-conventions.py gives SKILL prose a deterministic
way to self-check a PR body against what CI checks -- that it names its ticket
(ADR-0106) -- by driving check-conventions.py's evaluate(), never a divergent
re-implementation of the rule.

Loaded via the same importlib file-path pattern as
tests/acs/test_conventions_check.py, so these tests exercise the shipped file
directly, not an installed copy.

Run:  python3 -m unittest discover -s tests -v
"""

import importlib.util
import os
import unittest
from unittest import mock

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TARGET = os.path.join(REPO_ROOT, "plugins", "acs", "hooks", "scripts", "pr-conventions.py")

_spec = importlib.util.spec_from_file_location("acs_pr_conventions", TARGET)
pc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pc)


def conforming_body():
    return (
        "## Summary\nSome summary text.\n\n"
        "## Ticket\n\n- **MAR-72** — Fix thing (task)\n\n"
        "## Changes\n\n- did stuff\n\n"
        "## Test plan\n\n- ran tests\n"
    )


class TestCheckPasses(unittest.TestCase):
    """Case 3: check passes a body that names its ticket."""

    def test_check_passes_a_body_naming_its_ticket(self):
        result = pc.run_check(
            body=conforming_body(),
            ticket_prefix="MAR",
        )
        self.assertTrue(result["passed"])
        self.assertEqual(result["errors"], [])


class TestCheckFailures(unittest.TestCase):
    """Cases 4-7: no ticket named / what is no longer judged / placeholder / comment."""

    def test_check_fails_a_body_naming_no_ticket(self):
        # Case 4: the one rule CI enforces (ADR-0106).
        result = pc.run_check(body="## Summary\nDid a thing.\n", ticket_prefix="MAR")
        self.assertFalse(result["passed"])
        self.assertIn("ticket_link", [e["heading"] for e in result["errors"]])

    def test_check_no_longer_judges_title_sections_or_label(self):
        # Case 5: a body with no section headings still passes when it names
        # the ticket -- CI no longer checks sections, the title or a label.
        result = pc.run_check(body="Work for MAR-72.", ticket_prefix="MAR")
        self.assertTrue(result["passed"], result["errors"])

    def test_check_fails_unrendered_placeholder(self):
        # Case 6: a literal {summary} token survived in the body.
        body = conforming_body() + "\n{summary}\n"
        result = pc.run_check(
            body=body,
            ticket_prefix="MAR",
        )
        self.assertFalse(result["passed"])
        headings = [e["heading"] for e in result["errors"]]
        self.assertIn("unrendered_placeholder", headings)

    def test_check_fails_leftover_template_comment(self):
        # Case 7: an un-deleted HTML guidance comment survived.
        body = conforming_body() + "\n<!-- fill this in -->\n"
        result = pc.run_check(
            body=body,
            ticket_prefix="MAR",
        )
        self.assertFalse(result["passed"])
        headings = [e["heading"] for e in result["errors"]]
        self.assertIn("leftover_template_comment", headings)


class TestScopingRegression(unittest.TestCase):
    """Case 8: no regression to base-branch detection or tracker sync."""

    def test_no_branch_name_or_commit_message_finding_ever(self):
        # The helper never receives a branch or commit subjects, and CI's PR
        # mode checks neither, so neither can ever be reported here.
        result = pc.run_check(
            body=conforming_body(),
            ticket_prefix="MAR",
        )
        headings = [e["heading"] for e in result["errors"]]
        self.assertNotIn("branch_name", headings)
        self.assertNotIn("commit_message", headings)

    def test_helper_module_has_no_git_or_tracker_reference(self):
        # Behavioral: the helper's own EXECUTABLE source never touches git,
        # base-branch detection, or tracker-sync logic — nothing to regress.
        # (Module-level prose documenting the caller's contract, e.g. "pass
        # verbatim to gh pr create/edit --title", is not executable logic and
        # is excluded by stripping the leading module docstring first.)
        with open(TARGET, "r", encoding="utf-8") as fh:
            src = fh.read()
        _, _, code_after_docstring = src.partition('"""')
        _, _, code = code_after_docstring.partition('"""')
        self.assertNotIn("subprocess", code)
        self.assertNotIn("import git", code)
        self.assertNotIn("gh issue", code)
        self.assertNotIn("acli jira", code)


class TestEvaluateReuse(unittest.TestCase):
    """Case 9: check path calls the importlib-loaded cc.evaluate — pins AC-3."""

    def test_check_calls_cc_evaluate_with_expected_args(self):
        with mock.patch.object(pc.cc, "evaluate", wraps=pc.cc.evaluate) as spy:
            pc.run_check(
                body=conforming_body(),
                ticket_prefix="MAR",
            )
        spy.assert_called_once()
        args, kwargs = spy.call_args
        settings, ctx, mode = args
        self.assertEqual(mode, "pr")
        self.assertEqual(settings, {"ticket_prefix": "MAR"})
        self.assertEqual(ctx["body"], conforming_body())
        self.assertEqual(ctx["labels"], [], "a PR about to be opened is never exempt")


class TestMain(unittest.TestCase):
    """Drive main() end-to-end (argparse plumbing, stdout/exit-code contract)."""

    def _run_main(self, argv):
        import io
        import sys
        real_argv = sys.argv[:]
        real_stdout = sys.stdout
        sys.argv = ["pr-conventions.py"] + argv
        sys.stdout = io.StringIO()
        try:
            try:
                pc.main()
                code = 0
            except SystemExit as exc:
                code = exc.code if exc.code is not None else 0
            out = sys.stdout.getvalue()
        finally:
            sys.argv = real_argv
            sys.stdout = real_stdout
        return code, out

    def test_main_check_pass(self):
        import tempfile
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as fh:
            fh.write(conforming_body())
            body_path = fh.name
        try:
            code, out = self._run_main([
                "check", "--body-file", body_path, "--ticket-prefix", "MAR",
            ])
            # An older skill invocation still runs: the retired flags are
            # accepted and ignored.
            legacy_code, legacy_out = self._run_main([
                "check",
                "--title", "[MAR-72] Fix thing",
                "--body-file", body_path,
                "--require-label", "ACS",
                "--pr-title-format", "[{ticket_id}] {title}",
                "--sections", "Summary,Ticket,Changes,Test plan",
                "--ticket-prefix", "MAR",
            ])
        finally:
            os.unlink(body_path)
        self.assertEqual(code, 0)
        self.assertIn('"passed": true', out)
        self.assertEqual((legacy_code, legacy_out), (code, out))

    def test_main_check_fail_exits_nonzero(self):
        import tempfile
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as fh:
            fh.write("no ticket named here")
            body_path = fh.name
        try:
            code, out = self._run_main([
                "check", "--body-file", body_path, "--ticket-prefix", "MAR",
            ])
        finally:
            os.unlink(body_path)
        self.assertEqual(code, 1)
        self.assertIn('"passed": false', out)

    def test_main_usage_error_missing_required_arg(self):
        import contextlib
        import io as io_
        with contextlib.redirect_stderr(io_.StringIO()):
            code, _out = self._run_main(["check"])
        self.assertEqual(code, 2)


def conforming_body_with_closes_link(key="156"):
    body = conforming_body()
    return body.replace(
        "## Ticket\n\n- **MAR-72** — Fix thing (task)\n\n",
        "## Ticket\n\n- **MAR-72** — Fix thing (task)\n- Closes #%s\n\n" % key,
    )


class TestIssueLinkNonRegression(unittest.TestCase):
    """MAR-75 spec 02: convention non-regression proof for the reconciliation
    mechanism (acs-ticket-id <-> GitHub issue/PR) spec 01 implements. No
    product code changes — reuses conforming_body()/pc.run_check/pc.build_title
    exactly as the rest of this module does, with new input data only."""

    def test_check_passes_with_closes_link_in_ticket_section(self):
        # AC-2/AC-3: a Closes #<key> bullet inside the Ticket section does not
        # trip the hygiene scans, and it names the ticket in its own right.
        result = pc.run_check(
            body=conforming_body_with_closes_link("156"),
            ticket_prefix="MAR",
        )
        self.assertTrue(result["passed"])
        self.assertEqual(result["errors"], [])

    def test_unsynced_external_key_empty_renders_no_closes_line_and_passes_check(self):
        # AC-4 (dedicated, explicit): the unsynced fixture (external_key="",
        # no Closes # bullet) still passes check, and the fixture itself
        # carries no Closes # substring.
        body = conforming_body()
        self.assertNotIn("Closes #", body)
        result = pc.run_check(
            body=body,
            ticket_prefix="MAR",
        )
        self.assertTrue(result["passed"])
        self.assertEqual(result["errors"], [])

    def test_closes_link_absent_is_still_conforming_baseline(self):
        # AC-4 (regression baseline): the same call as
        # TestCheckPasses.test_check_passes_a_body_naming_its_ticket, pinning
        # that conforming_body()'s shared meaning is unchanged.
        result = pc.run_check(
            body=conforming_body(),
            ticket_prefix="MAR",
        )
        self.assertTrue(result["passed"])
        self.assertEqual(result["errors"], [])


if __name__ == "__main__":
    unittest.main()
