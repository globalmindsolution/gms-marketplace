"""Behavior tests for codeowners.py -- CODEOWNERS parsing + owner resolution.

Originating ticket: MAR-172. codeowners.py resolves the raw CODEOWNERS-matched
owner set for a PR's changed files (git's own file-precedence order, last
pattern wins). The scenario matrix here reproduces the 9-fixture set reviewed
in tests/acs/cov_codeowners.py (left in place; retiring that harness is a
separate ticket), reauthored as isolated unittest methods against the shared
acs_case.py fixture (MAR-175) instead of that harness's own private helpers.
"""

import json
import os
import shutil
import tempfile
import unittest

TESTS_ACS = os.path.dirname(os.path.abspath(__file__))
import sys  # noqa: E402
sys.path.insert(0, TESTS_ACS)

import acs_case  # noqa: E402

MODULE_FILENAME = "codeowners.py"


def _tmp_repo(case):
    """Create a throwaway repo_root that cleans itself up after the test."""
    path = tempfile.mkdtemp(prefix="acs-codeowners-test-")
    case.addCleanup(shutil.rmtree, path, True)
    return path


def _write(path, text):
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


class TestNoCodeownersFile(unittest.TestCase):
    """AC-3: the live path in this repo -- no CODEOWNERS file anywhere."""

    def setUp(self):
        self.mod = acs_case.load_module(MODULE_FILENAME)

    def test_resolve_reports_no_codeowners_file_with_empty_owners(self):
        empty_root = _tmp_repo(self)
        result = self.mod.resolve(empty_root, ["src/foo.py"])
        self.assertEqual(
            result,
            {"source": None, "owners": [], "reason": "no_codeowners_file"},
        )

    def test_find_codeowners_file_returns_none_when_absent(self):
        empty_root = _tmp_repo(self)
        self.assertIsNone(self.mod.find_codeowners_file(empty_root))


class TestPatternMatching(unittest.TestCase):
    """AC-4: matched glob, no_pattern_matched, later-pattern-wins, @org/team owners."""

    def setUp(self):
        self.mod = acs_case.load_module(MODULE_FILENAME)

    def test_matched_glob_returns_owner_and_source(self):
        root = _tmp_repo(self)
        _write(os.path.join(root, "CODEOWNERS"), "*.py @alice\n")
        result = self.mod.resolve(root, ["src/foo.py"])
        self.assertEqual(
            result,
            {"source": "CODEOWNERS", "owners": ["@alice"], "reason": None},
        )

    def test_no_pattern_matched_when_nothing_matches(self):
        root = _tmp_repo(self)
        _write(os.path.join(root, "CODEOWNERS"), "*.rb @alice\n")
        result = self.mod.resolve(root, ["src/foo.py"])
        self.assertEqual(
            result,
            {"source": "CODEOWNERS", "owners": [], "reason": "no_pattern_matched"},
        )

    def test_later_pattern_wins(self):
        root = _tmp_repo(self)
        _write(os.path.join(root, "CODEOWNERS"),
               "*.py @alice\nsrc/*.py @bob @carol\n")
        matched = self.mod.resolve(root, ["src/foo.py"])
        self.assertEqual(matched["owners"], ["@bob", "@carol"])
        unmatched_by_later = self.mod.resolve(root, ["other/bar.py"])
        self.assertEqual(unmatched_by_later["owners"], ["@alice"])

    def test_org_team_and_individual_owners_pass_through(self):
        root = _tmp_repo(self)
        _write(os.path.join(root, "CODEOWNERS"),
               "src/*.py @org/team-fe @dana\n")
        result = self.mod.resolve(root, ["src/app.py"])
        self.assertEqual(result["owners"], ["@org/team-fe", "@dana"])


class TestParse(unittest.TestCase):
    """parse_codeowners: comment/blank skipping, rule order, multi-owner lines."""

    def setUp(self):
        self.mod = acs_case.load_module(MODULE_FILENAME)

    def test_comments_and_blank_lines_are_skipped(self):
        rules = self.mod.parse_codeowners(
            "# top comment\n\n   \n*.py @alice\n# trailing comment\n"
        )
        self.assertEqual(rules, [("*.py", ["@alice"])])

    def test_rules_keep_file_order_and_all_owner_tokens(self):
        rules = self.mod.parse_codeowners("# c\n\n*.py @x\ndocs/** @y @z\n")
        self.assertEqual(rules, [("*.py", ["@x"]), ("docs/**", ["@y", "@z"])])


class TestMatchOwners(unittest.TestCase):
    """match_owners: cross-file union with first-seen dedupe, empty edge cases."""

    def setUp(self):
        self.mod = acs_case.load_module(MODULE_FILENAME)

    def test_union_across_files_is_deduped_in_first_seen_order(self):
        rules = [("*.py", ["@alice"]), ("src/*.py", ["@bob", "@carol"])]
        union = self.mod.match_owners(
            rules, ["src/foo.py", "src/baz.py", "other/bar.py"]
        )
        self.assertEqual(union, ["@bob", "@carol", "@alice"])

    def test_empty_rules_and_unmatched_file_yield_no_owners(self):
        self.assertEqual(self.mod.match_owners([], ["a.py"]), [])
        rules = [("*.py", ["@alice"]), ("src/*.py", ["@bob", "@carol"])]
        self.assertEqual(self.mod.match_owners(rules, ["nomatch.txt"]), [])


class TestPrecedence(unittest.TestCase):
    """find_codeowners_file / resolve: git's own .github > docs > root order."""

    def setUp(self):
        self.mod = acs_case.load_module(MODULE_FILENAME)

    def test_github_beats_docs_and_root(self):
        root = _tmp_repo(self)
        os.makedirs(os.path.join(root, ".github"))
        os.makedirs(os.path.join(root, "docs"))
        _write(os.path.join(root, "CODEOWNERS"), "*.py @root_owner\n")
        _write(os.path.join(root, "docs", "CODEOWNERS"), "*.py @docs_owner\n")
        _write(os.path.join(root, ".github", "CODEOWNERS"), "*.py @github_owner\n")
        result = self.mod.resolve(root, ["a.py"])
        self.assertEqual(result["source"], ".github/CODEOWNERS")
        self.assertEqual(result["owners"], ["@github_owner"])

    def test_docs_beats_root_when_github_absent(self):
        root = _tmp_repo(self)
        os.makedirs(os.path.join(root, "docs"))
        _write(os.path.join(root, "CODEOWNERS"), "*.py @root_owner\n")
        _write(os.path.join(root, "docs", "CODEOWNERS"), "*.py @docs_owner\n")
        result = self.mod.resolve(root, ["a.py"])
        self.assertEqual(result["source"], "docs/CODEOWNERS")
        self.assertEqual(result["owners"], ["@docs_owner"])

    def test_codeowners_path_override_bypasses_the_search(self):
        empty_root = _tmp_repo(self)
        tmp = _tmp_repo(self)
        override_path = os.path.join(tmp, "override_CODEOWNERS")
        _write(override_path, "*.py @override_owner\n")
        result = self.mod.resolve(empty_root, ["a.py"], codeowners_path=override_path)
        self.assertEqual(result["source"], override_path)
        self.assertEqual(result["owners"], ["@override_owner"])


class TestFileTooLarge(unittest.TestCase):
    """resolve: a CODEOWNERS at/over MAX_LINES is rejected; under-cap is fine."""

    def setUp(self):
        self.mod = acs_case.load_module(MODULE_FILENAME)

    def test_file_at_or_above_max_lines_is_rejected(self):
        root = _tmp_repo(self)
        big = "\n".join("*.py @owner%d" % i for i in range(5000)) + "\n"
        _write(os.path.join(root, "CODEOWNERS"), big)
        result = self.mod.resolve(root, ["a.py"])
        self.assertEqual(
            result, {"source": None, "owners": [], "reason": "file_too_large"}
        )

        root_ok = _tmp_repo(self)
        small = "\n".join("*.py @owner%d" % i for i in range(10)) + "\n"
        _write(os.path.join(root_ok, "CODEOWNERS"), small)
        result_ok = self.mod.resolve(root_ok, ["a.py"])
        self.assertIsNone(result_ok["reason"])


class TestCli(unittest.TestCase):
    """main(): argv/stdin plumbing, JSON stdout, exit codes -- in-process."""

    def setUp(self):
        self.mod = acs_case.load_module(MODULE_FILENAME)

    def test_resolve_from_a_changed_files_path_prints_json_and_exits_0(self):
        root = _tmp_repo(self)
        _write(os.path.join(root, "CODEOWNERS"),
               "*.py @alice\nsrc/*.py @bob @carol\n")
        tmp = _tmp_repo(self)
        changed_path = os.path.join(tmp, "changed.txt")
        _write(changed_path, "src/foo.py\nother/bar.py\n")

        code, out, err = acs_case.run_main(
            self.mod,
            ["resolve", "--repo-root", root, "--changed-files", changed_path],
        )
        self.assertEqual(code, 0, err)
        payload = json.loads(out)
        self.assertEqual(payload["owners"], ["@bob", "@carol", "@alice"])
        self.assertEqual(payload["source"], "CODEOWNERS")
        self.assertIsNone(payload["reason"])

    def test_resolve_reads_changed_files_from_stdin_when_dash(self):
        root = _tmp_repo(self)
        _write(os.path.join(root, "CODEOWNERS"),
               "*.py @alice\nsrc/*.py @bob @carol\n")

        code, out, err = acs_case.run_main(
            self.mod,
            ["resolve", "--repo-root", root, "--changed-files", "-"],
            stdin="src/foo.py\n\nother/bar.py\n",
        )
        self.assertEqual(code, 0, err)
        payload = json.loads(out)
        self.assertEqual(payload["owners"], ["@bob", "@carol", "@alice"])

    def test_missing_required_argument_exits_2(self):
        root = _tmp_repo(self)
        code, _out, err = acs_case.run_main(
            self.mod, ["resolve", "--repo-root", root]
        )
        self.assertEqual(code, 2)
        self.assertTrue(err)

    def test_no_subcommand_exits_2(self):
        code, _out, err = acs_case.run_main(self.mod, [])
        self.assertEqual(code, 2)
        self.assertTrue(err)


class TestCliSubprocess(acs_case.AcsWorkspaceCase):
    """Real subprocess CLI contract -- the only way to reach the __main__ guard."""

    def test_real_cli_invocation_prints_json_and_exits_0(self):
        _write(os.path.join(self.repo, "CODEOWNERS"), "*.py @alice\n")
        out = self.run_script(
            "codeowners.py", "resolve",
            "--repo-root", self.repo, "--changed-files", "-",
            stdin="a.py\n",
        )
        self.assertEqual(out.returncode, 0, out.stderr)
        payload = json.loads(out.stdout)
        self.assertEqual(
            payload,
            {"source": "CODEOWNERS", "owners": ["@alice"], "reason": None},
        )


if __name__ == "__main__":
    unittest.main()
