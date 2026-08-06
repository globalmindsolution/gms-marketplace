"""Contract test for the shared, importable test fixture module (MAR-175).

Pins acs_case.py's public surface -- AcsWorkspaceCase, load_module(),
run_main(), pushd(), fake_gh() -- so sibling test modules can depend on it
without importing (or editing) the 223KB test_acs_plugin.py.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TESTS_ACS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TESTS_ACS)

import acs_case  # noqa: E402

THIS_MODULE = os.path.abspath(__file__)
ACS_CASE_MODULE = os.path.join(TESTS_ACS, "acs_case.py")


class TestFixtureUsableFromANewFile(acs_case.AcsWorkspaceCase):
    """AC-6: subclassing acs_case.AcsWorkspaceCase alone gives a working fixture."""

    def test_repo_workspace_and_settings_files_after_a_run(self):
        self.assertTrue(os.path.isdir(self.repo))
        self.assertTrue(os.path.isfile(os.path.join(self.repo, ".acs", "settings.json")))
        self.assertTrue(os.path.isfile(
            os.path.join(self.repo, ".acs", "settings.local.json")))
        out = self.run_script("new-ticket.py", "--title", "Fixture check", "--type", "task")
        self.assertEqual(out.returncode, 0, out.stderr)
        payload = json.loads(out.stdout)
        self.assertIn("ticket_id", payload)
        # The workspace dir is created lazily by the first hook invocation.
        self.assertTrue(os.path.isdir(self.ws))


class TestLoadModule(unittest.TestCase):
    """AC-6: load_module() fresh-imports a hyphenated script by path."""

    def test_load_module_loads_hyphenated_script_fresh(self):
        first = acs_case.load_module("new-ticket.py")
        second = acs_case.load_module("new-ticket.py")
        self.assertIsNot(first, second)
        # Each load pops acs_lib from sys.modules first, so the hyphenated
        # script's own `import acs_lib as lib` re-imports a fresh object.
        self.assertIsNot(first.lib, second.lib)


class TestRunMain(unittest.TestCase):
    """AC-6: run_main() drives a loaded module's main() in-process."""

    def test_run_main_captures_systemexit_and_stdout(self):
        mod = acs_case.load_module("new-ticket.py")
        code, out, _err = acs_case.run_main(mod, ["--help"])
        self.assertEqual(code, 0)
        self.assertIn("usage", out.lower())

    def test_run_main_returns_cli_exit_code_without_raising(self):
        mod = acs_case.load_module("new-ticket.py")
        # No args at all -- argparse's own required-argument error, must be
        # captured as a return value, never propagate as a real SystemExit.
        try:
            code, _out, err = acs_case.run_main(mod, [])
        except SystemExit:
            self.fail("run_main must catch SystemExit, not let it propagate")
        self.assertEqual(code, 2)
        self.assertTrue(err)


class TestPushd(unittest.TestCase):
    """AC-6: pushd() restores the original cwd, including when the body raises."""

    def test_pushd_restores_cwd(self):
        original = os.getcwd()
        with acs_case.pushd(REPO_ROOT):
            self.assertEqual(os.getcwd(), REPO_ROOT)
        self.assertEqual(os.getcwd(), original)

    def test_pushd_restores_cwd_on_exception(self):
        original = os.getcwd()
        with self.assertRaises(ValueError):
            with acs_case.pushd(REPO_ROOT):
                raise ValueError("boom")
        self.assertEqual(os.getcwd(), original)


class TestFakeGh(unittest.TestCase):
    """AC-6: fake_gh() shims gh on PATH so no real GitHub auth/network is needed."""

    def test_fake_gh_is_used_instead_of_real_gh(self):
        bindir = tempfile.mkdtemp(prefix="acs-case-fakebin-")
        try:
            env = acs_case.fake_gh(bindir, "echo '{\"ok\": true}'")
            result = subprocess.run(["gh"], capture_output=True, text=True, env=env)
            self.assertEqual(result.returncode, 0)
            self.assertIn("ok", result.stdout)
        finally:
            shutil.rmtree(bindir, ignore_errors=True)

    def test_fake_gh_none_body_simulates_absent_binary(self):
        env = acs_case.fake_gh("/unused", None)
        # Assert the real property -- gh must be genuinely unresolvable on the
        # returned PATH -- not merely absent as a literal PATH-directory name.
        self.assertIsNone(shutil.which("gh", path=env.get("PATH", "")))


class TestPy39Compatibility(unittest.TestCase):
    """AC-9: neither this module nor acs_case.py uses 3.11+-only syntax."""

    # Built via concatenation so the forbidden phrase never appears as a
    # contiguous run in this file's own source -- otherwise this check would
    # always match itself. A real usage elsewhere still trips it.
    _FORBIDDEN = (
        "contextlib" + ".chdir",
        "from contextlib import " + "chdir",
    )

    def test_new_test_code_is_py39_compatible(self):
        for path in (THIS_MODULE, ACS_CASE_MODULE):
            with open(path, encoding="utf-8") as fh:
                source = fh.read()
            for marker in self._FORBIDDEN:
                self.assertNotIn(marker, source, path)


if __name__ == "__main__":
    unittest.main()
