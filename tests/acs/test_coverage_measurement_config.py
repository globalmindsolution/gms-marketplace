"""Guard test pinning the coverage measurement configuration (MAR-175, MAR-174).

Coverage.py does not measure subprocesses by default, and the deterministic
suite drives the real hook CLIs via subprocess.run (tests/acs/acs_case.py:49-54's
run_script, 169 call sites) -- a relative `source`, `data_file`, or
`COVERAGE_PROCESS_START` each silently degrades measured coverage back
toward ~62% with no error. This module pins the committed configuration
that avoids that: `.coveragerc`'s [run] parallel/source/data_file/omit
shape, the `.gitignore` parallel-data-file entry, the `tests.setup`
coverage-version floor, and `tests.command`'s measurement wiring plus
`coverage combine`.

`tests.command` runs repo-wide: it orders `coverage combine` before
`coverage report`, and it contains no `diff_cover` step -- both properties
are asserted below.
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
    """AC-5: tests.command wires measurement, runs coverage combine, then reports repo-wide."""

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
        self.assertEqual(self.command, self.FINAL_FORM)

    def test_tests_command_reports_after_combine(self):
        combine_idx = self.command.index("coverage combine")
        report_idx = self.command.index("coverage report")
        self.assertLess(combine_idx, report_idx)

    def test_tests_command_has_no_diff_cover_step(self):
        self.assertNotIn("diff_cover", self.command)
        self.assertNotIn("diff-cover", self.command)


class TestNoHandRolledSitecustomize(unittest.TestCase):
    """A repo-root sitecustomize.py shadows Homebrew's own and breaks the parent interpreter."""

    def test_no_repo_root_sitecustomize(self):
        self.assertFalse(os.path.isfile(os.path.join(REPO_ROOT, "sitecustomize.py")))


if __name__ == "__main__":
    unittest.main()
