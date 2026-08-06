"""Guard test pinning the coverage measurement configuration (MAR-175).

Coverage.py does not measure subprocesses by default, and the deterministic
suite drives the real hook CLIs via subprocess.run (test_acs_plugin.py's
run_script, 169 call sites) -- a relative `source`, `data_file`, or
`COVERAGE_PROCESS_START` each silently degrades measured coverage back
toward ~62% with no error. This module pins the committed configuration
that avoids that: `.coveragerc`'s [run] parallel/source/data_file/omit
shape, the `.gitignore` parallel-data-file entry, the `tests.setup`
coverage-version floor, and `tests.command`'s measurement wiring plus
`coverage combine`.

Deliberately absent, by design (do not add): an assertion that
`tests.command` orders `coverage combine` before `coverage report`, and an
assertion that `tests.command` does not contain `diff_cover`. Both
properties hold only after a later change flips `tests.command` from this
diff-scoped diff-cover form to the repo-wide `coverage report
--fail-under=$ACS_COVERAGE` form -- that flip is out of scope here, and
asserting either property on this branch would fail this PR's own required
"Tests & coverage" check, which still runs the diff-scoped form.
"""

import configparser
import json
import os
import re
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRIPTS_DIR = os.path.join(REPO_ROOT, "plugins", "acs", "hooks", "scripts")
COVERAGERC = os.path.join(REPO_ROOT, ".coveragerc")
SETTINGS = os.path.join(REPO_ROOT, ".acs", "settings.json")
GITIGNORE = os.path.join(REPO_ROOT, ".gitignore")
THIS_MODULE = os.path.abspath(__file__)


def _read_coveragerc():
    """Parse the committed .coveragerc with stdlib configparser."""
    cp = configparser.ConfigParser()
    read_ok = cp.read(COVERAGERC)
    if not read_ok:
        raise AssertionError(".coveragerc must exist and be readable at %s" % COVERAGERC)
    return cp


def _read_settings():
    """Load the committed .acs/settings.json."""
    with open(SETTINGS, encoding="utf-8") as fh:
        return json.load(fh)


def _true_forwarders():
    """Every pre-*/post-* script with no def main() -- a thin argument forwarder shim."""
    names = []
    for fname in sorted(os.listdir(SCRIPTS_DIR)):
        if not fname.endswith(".py"):
            continue
        if not (fname.startswith("pre-") or fname.startswith("post-")):
            continue
        with open(os.path.join(SCRIPTS_DIR, fname), encoding="utf-8") as fh:
            body = fh.read()
        if "def main(" not in body:
            names.append(fname)
    return names


class TestCoveragercRunSection(unittest.TestCase):
    """AC-1: [run] parallel is on, source/data_file are absolute via ${ACS_COV_ROOT}."""

    def setUp(self):
        self.cp = _read_coveragerc()

    def test_run_section_parallel_enabled(self):
        self.assertTrue(self.cp.getboolean("run", "parallel"))

    def test_source_is_absolute_var_substituted(self):
        source = self.cp.get("run", "source")
        self.assertEqual(source, "${ACS_COV_ROOT}/plugins/acs/hooks/scripts")
        self.assertIn("${", source)
        self.assertTrue(os.path.isabs(source.replace("${ACS_COV_ROOT}", "/dummy-root")))

    def test_data_file_is_absolute_var_substituted(self):
        data_file = self.cp.get("run", "data_file")
        self.assertEqual(data_file, "${ACS_COV_ROOT}/.coverage")
        self.assertIn("${", data_file)
        self.assertTrue(os.path.isabs(data_file.replace("${ACS_COV_ROOT}", "/dummy-root")))


class TestCoveragercOmitList(unittest.TestCase):
    """AC-2: omit lists exactly the true forwarders, lives under [run], keeps post-merge-pr.py measured."""

    def setUp(self):
        self.cp = _read_coveragerc()

    def _omit_entries(self):
        raw = self.cp.get("run", "omit")
        return [line.strip() for line in raw.splitlines() if line.strip()]

    def test_omit_lists_exactly_the_true_forwarders(self):
        entries = self._omit_entries()
        expected = {
            "${ACS_COV_ROOT}/plugins/acs/hooks/scripts/%s" % fname
            for fname in _true_forwarders()
        }
        self.assertEqual(set(entries), expected)
        self.assertEqual(len(entries), 29)
        for entry in entries:
            self.assertTrue(entry.startswith("${ACS_COV_ROOT}/"), entry)

    def test_post_merge_pr_not_omitted(self):
        entries = self._omit_entries()
        self.assertNotIn(
            "${ACS_COV_ROOT}/plugins/acs/hooks/scripts/post-merge-pr.py", entries)

    def test_omit_not_in_report_section(self):
        if self.cp.has_section("report"):
            self.assertFalse(self.cp.has_option("report", "omit"))


class TestGitignoreParallelDataFiles(unittest.TestCase):
    """AC-3: .gitignore ignores .coverage.* alongside the existing .coverage/coverage.xml."""

    def test_gitignore_ignores_parallel_data_files(self):
        with open(GITIGNORE, encoding="utf-8") as fh:
            lines = [line.strip() for line in fh]
        self.assertIn(".coverage.*", lines)
        self.assertIn(".coverage", lines)
        self.assertIn("coverage.xml", lines)


class TestSettingsCoverageFloor(unittest.TestCase):
    """AC-4: tests.setup pins a coverage version floor shipping the subprocess startup hook."""

    def test_tests_setup_pins_coverage_version_floor(self):
        setup = _read_settings()["tests"]["setup"]
        match = re.search(r"coverage>=(\d+)\.(\d+)\.(\d+)", setup)
        self.assertIsNotNone(match, "tests.setup must pin a coverage>=N.N.N floor: %r" % setup)
        floor = tuple(int(part) for part in match.groups())
        self.assertGreaterEqual(floor, (7, 14, 2))
        self.assertNotIn("quiet coverage jsonschema", setup,
                          "coverage must be version-constrained, not the bare package name")


class TestSettingsTestsCommand(unittest.TestCase):
    """AC-5: tests.command wires measurement, runs coverage combine, keeps diff-cover reporting."""

    INTERMEDIATE_FORM = (
        "export ACS_COV_ROOT=$PWD COVERAGE_PROCESS_START=$PWD/.coveragerc; "
        "python3 -m coverage run -m unittest discover -s tests && "
        "python3 -m coverage combine && "
        "python3 -m coverage xml -o coverage.xml && "
        "python3 -m diff_cover.diff_cover_tool coverage.xml "
        "--compare-branch \"origin/${GITHUB_BASE_REF:-main}\" --fail-under $ACS_COVERAGE"
    )
    # The final, repo-wide form a later change alone introduces -- listed here
    # only so the pinned-form check is a disjunction, never asserted as this
    # branch's own value.
    FINAL_FORM = (
        "export ACS_COV_ROOT=$PWD COVERAGE_PROCESS_START=$PWD/.coveragerc; "
        "python3 -m coverage run -m unittest discover -s tests && "
        "python3 -m coverage combine && "
        "python3 -m coverage report --fail-under=$ACS_COVERAGE"
    )

    def setUp(self):
        self.command = _read_settings()["tests"]["command"]

    def test_coverage_process_start_is_absolute_for_the_whole_chain(self):
        self.assertTrue(self.command.startswith(
            "export ACS_COV_ROOT=$PWD COVERAGE_PROCESS_START=$PWD/.coveragerc;"))

    def test_tests_command_runs_coverage_combine_after_run(self):
        run_idx = self.command.index("coverage run")
        combine_idx = self.command.index("coverage combine")
        self.assertGreater(combine_idx, run_idx)

    def test_tests_command_enforces_fail_under_acs_coverage(self):
        self.assertIn("--fail-under", self.command)
        self.assertIn("$ACS_COVERAGE", self.command)

    def test_tests_command_matches_a_pinned_form(self):
        self.assertIn(self.command, (self.INTERMEDIATE_FORM, self.FINAL_FORM))
        # On this branch the diff-cover reporting step must be retained --
        # only a later, out-of-scope change flips to the repo-wide FINAL_FORM.
        self.assertEqual(self.command, self.INTERMEDIATE_FORM)


class TestGuardScopeExcludesLaterOnlyProperties(unittest.TestCase):
    """AC-7 negative scope: this guard must never gain the two post-flip-only assertions."""

    # Built via concatenation so the forbidden phrase itself never appears as
    # a contiguous run in this file's own source -- otherwise this very
    # assertion would match itself. A future literal addition of either
    # phrase (the natural way to write the forbidden assertion) still trips
    # this check, since the concatenation only hides it from a plain read.
    _FORBIDDEN_MARKERS = (
        "in" + 'dex("coverage report")',
        "in" + "dex('coverage report')",
        "assertNotIn(" + '"diff_cover"',
        "assertNotIn(" + "'diff_cover'",
    )

    def test_does_not_assert_combine_before_report_or_diff_cover_absence(self):
        with open(THIS_MODULE, encoding="utf-8") as fh:
            source = fh.read()
        for marker in self._FORBIDDEN_MARKERS:
            self.assertNotIn(marker, source)


class TestNoHandRolledSitecustomize(unittest.TestCase):
    """A repo-root sitecustomize.py shadows Homebrew's own and breaks the parent interpreter."""

    def test_no_repo_root_sitecustomize(self):
        self.assertFalse(os.path.isfile(os.path.join(REPO_ROOT, "sitecustomize.py")))


if __name__ == "__main__":
    unittest.main()
